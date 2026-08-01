# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The behavior gate: one Scan, projected, compared against a committed file.

Carries no pytest marker, and its path contains no ``integration`` segment, so
it runs under ``make test-unit``. Both matter -- see ``tests/behavior/__init__``.

A mismatch is a real behavior change. The snapshot is only ever rewritten by
``make snapshots``, in its own commit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from skillspector.graph import graph
from tests.behavior import projection as proj

FIXTURE = "malicious_skill"
REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# The gate itself
# --------------------------------------------------------------------------- #


def test_scan_matches_committed_snapshot() -> None:
    """The Scan's projection is byte-identical to the committed snapshot."""
    committed = proj.snapshot_path(FIXTURE).read_text(encoding="utf-8")
    assert proj.serialize(proj.scan(proj.CORPUS[FIXTURE])) == committed


def test_missing_snapshot_fails_rather_than_regenerating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deleted snapshot raises; nothing writes one back."""
    monkeypatch.setattr(proj, "SNAPSHOT_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        proj.load_snapshot(FIXTURE)
    assert list(tmp_path.iterdir()) == []


def test_corrupt_snapshot_fails_rather_than_regenerating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupt snapshot raises; the corruption is not silently overwritten."""
    monkeypatch.setattr(proj, "SNAPSHOT_DIR", tmp_path)
    corrupt = tmp_path / f"{FIXTURE}.json"
    corrupt.write_text('{"findings": [', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        proj.load_snapshot(FIXTURE)
    assert corrupt.read_text(encoding="utf-8") == '{"findings": ['


# --------------------------------------------------------------------------- #
# What the projection carries, and what it drops
# --------------------------------------------------------------------------- #


def test_committed_snapshot_carries_the_projected_keys_only() -> None:
    """Exactly the nine ADR 0003 keys; none of the four excluded ones."""
    snapshot = proj.load_snapshot(FIXTURE)
    assert sorted(snapshot) == sorted(proj.PROJECTED_STATE_KEYS)
    assert not set(snapshot) & set(proj.EXCLUDED_STATE_KEYS)


def test_committed_snapshot_carries_neither_stripped_field() -> None:
    """Neither ``finding_id`` nor the driver version survives into the file."""
    snapshot = proj.load_snapshot(FIXTURE)
    assert all("finding_id" not in finding for finding in snapshot["findings"])
    for run in snapshot["sarif_report"]["runs"]:
        assert "version" not in run["tool"]["driver"]
        for result in run["results"]:
            assert "findingId" not in result["properties"]


def test_stripping_removes_fields_that_are_actually_there() -> None:
    """Guard against a vacuous strip: the raw Scan carries all three fields."""
    state = graph.invoke({"skill_path": str(proj.CORPUS[FIXTURE]), "use_llm": False})
    assert all(finding.finding_id for finding in state["findings"])
    run = state["sarif_report"]["runs"][0]
    assert run["tool"]["driver"]["version"]
    assert all("findingId" in result["properties"] for result in run["results"])


def test_stripping_leaves_neighbouring_version_fields_alone() -> None:
    """Stripping is addressed by path, so SARIF's own version fields survive."""
    snapshot = proj.load_snapshot(FIXTURE)
    assert snapshot["sarif_report"]["version"]
    assert snapshot["sarif_report"]["runs"][0]["tool"]["driver"]["name"]


# --------------------------------------------------------------------------- #
# Sorting: named key plus canonical-serialization tie-breaker
# --------------------------------------------------------------------------- #


def _named_finding_keys(snapshot: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    return [proj._finding_key(finding) for finding in snapshot["findings"]]


def test_named_finding_key_collides_so_the_tie_break_is_exercised() -> None:
    """``malicious_skill`` holds two Findings the named key cannot separate.

    This is why the key carries the canonical serialization as its final
    component. If the fixture ever stops colliding, the tie-break stops being
    covered -- so the collision is asserted rather than assumed.
    """
    keys = _named_finding_keys(proj.load_snapshot(FIXTURE))
    assert len(keys) - len(set(keys)) >= 1, "no colliding pair left to exercise"


def test_every_list_is_ordered_by_named_key_then_serialization() -> None:
    """Sorting the committed snapshot again is a no-op, at every depth."""
    snapshot = proj.load_snapshot(FIXTURE)
    assert proj._sort(snapshot, "$") == snapshot


def test_tied_elements_are_separated_by_their_serialization() -> None:
    """The colliding pair is ordered, and ordered by the full element."""
    snapshot = proj.load_snapshot(FIXTURE)
    findings = snapshot["findings"]
    keys = _named_finding_keys(snapshot)
    tied = [i for i in range(len(keys) - 1) if keys[i] == keys[i + 1]]
    assert tied, "expected an adjacent tied pair"
    for index in tied:
        left, right = findings[index], findings[index + 1]
        assert left != right, "a genuinely identical pair cannot produce a diff"
        assert proj._canonical(left) < proj._canonical(right)


# --------------------------------------------------------------------------- #
# Determinism, across runs and across processes
# --------------------------------------------------------------------------- #


def test_two_consecutive_runs_produce_identical_projections() -> None:
    """Two Scans in one process project byte-identically."""
    first = proj.serialize(proj.scan(proj.CORPUS[FIXTURE]))
    second = proj.serialize(proj.scan(proj.CORPUS[FIXTURE]))
    assert first == second


CREDENTIAL_FREE_ENV = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "HOME": os.environ.get("HOME", "/tmp"),
}


def _run_out_of_process(*, hash_seed: str, provider: str) -> dict[str, Any]:
    """Project one Scan in a fresh interpreter under a controlled environment.

    A separate process is required for two of these checks. ``PYTHONHASHSEED``
    is fixed before the interpreter starts, and the provider that decides
    ``model_config`` is resolved when ``skillspector.constants`` is imported --
    neither can be varied inside a running test.

    The environment is built from nothing but ``PATH`` and ``HOME``, so no API
    key of any kind is reachable: the Scan runs with no LLM credentials.
    """
    env = dict(CREDENTIAL_FREE_ENV)
    env["PYTHONHASHSEED"] = hash_seed
    env["SKILLSPECTOR_PROVIDER"] = provider
    assert not [key for key in env if key.endswith("_API_KEY")]

    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-m", "tests.behavior.regenerate", "--emit", FIXTURE],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.fixture(scope="module")
def baseline_run() -> dict[str, Any]:
    return _run_out_of_process(hash_seed="0", provider="openai")


@pytest.fixture(scope="module")
def other_hash_seed_run() -> dict[str, Any]:
    return _run_out_of_process(hash_seed="1", provider="openai")


@pytest.fixture(scope="module")
def other_provider_run() -> dict[str, Any]:
    return _run_out_of_process(hash_seed="0", provider="anthropic")


def test_scan_completes_without_llm_credentials(baseline_run: dict[str, Any]) -> None:
    """The Scan runs to a projection in an environment holding no API key."""
    assert baseline_run["projection"]["risk_score"] >= 0
    assert baseline_run["projection"]["findings"]


def test_projection_matches_snapshot_out_of_process(baseline_run: dict[str, Any]) -> None:
    """A fresh interpreter reproduces the committed snapshot."""
    assert baseline_run["projection"] == proj.load_snapshot(FIXTURE)


def test_a_different_hash_seed_produces_the_same_projection(
    baseline_run: dict[str, Any], other_hash_seed_run: dict[str, Any]
) -> None:
    """No set-derived ordering leaks into the projection."""
    assert other_hash_seed_run["projection"] == baseline_run["projection"]


def test_two_providers_produce_the_same_projection(
    baseline_run: dict[str, Any], other_provider_run: dict[str, Any]
) -> None:
    """``model_config`` is excluded, demonstrated against two live settings.

    The control comes first: the two runs must genuinely resolve different model
    configurations, or the equality below would prove nothing.
    """
    assert other_provider_run["model_config"] != baseline_run["model_config"]
    assert other_provider_run["projection"] == baseline_run["projection"]
