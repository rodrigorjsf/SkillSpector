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

"""What ``--recursive`` does today, recorded so a change to it is visible.

Every other behavior in this project is fenced by the Behavior Snapshot gate.
This flag is not: ``tests/behavior/projection.py`` Scans by calling
``graph.invoke({"skill_path": ...})`` directly and never imports ``cli``, so all
27 committed snapshots stay green through any change to ``--recursive``,
including one that breaks it outright.

These tests are therefore not assertions that the recorded behavior is *right*.
Several of them record shapes that read as defects and are decisions -- the
two-Skill threshold, the root short-circuit, an ``--output`` that is not valid
SARIF. Issue #39 exists to decide what to do about them; the point of recording
them first is that any of its three paths then becomes reviewable as a diff of
observed behavior rather than an argument about what the flag used to do.

The unit-level companion is ``tests/test_multi_skill.py``, which tests
``detect_skills`` in isolation. What is here is the CLI, driven end to end over
a real directory tree, because the flag's behavior is the composition of
detection with what ``cli`` then chooses to do about it.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from skillspector.cli import app

runner = CliRunner()


def _write_skill(directory: Path, name: str) -> Path:
    """A minimal, clean Skill at *directory*. Deliberately raises no Finding."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: A skill that does nothing of note.\n---\n\n"
        "Summarise the input.\n",
        encoding="utf-8",
    )
    return directory


class TestWhenRecursiveEngagesAtAll:
    """The detection half, observed through the CLI rather than through the API."""

    def test_two_child_skills_are_scanned_separately(self, tmp_path: Path) -> None:
        """The baseline the other cases in this class are departures from."""
        _write_skill(tmp_path / "alpha", "alpha")
        _write_skill(tmp_path / "beta", "beta")
        output = tmp_path / "combined.json"

        result = runner.invoke(
            app,
            ["scan", str(tmp_path), "--recursive", "--no-llm", "-f", "json", "-o", str(output)],
        )

        assert result.exit_code == 0, result.output
        combined = json.loads(output.read_text(encoding="utf-8"))
        assert [entry["name"] for entry in combined["skills"]] == ["alpha", "beta"]

    def test_one_child_skill_is_below_the_threshold_and_says_nothing(self, tmp_path: Path) -> None:
        """``detect_skills`` requires two, so a lone child Skill does not engage.

        It falls through to Scanning *the parent* as one anonymous Skill: the
        parent holds no ``SKILL.md``, so the Manifest is ``absent``, the name is
        ``unknown``, and the Risk Score is computed over the child's files as
        though they were the parent's own. Under ``--repo-scan`` the same tree
        reports the one Skill it holds.

        And it is silent about it. ``cli`` guards its "no sub-skills detected"
        warning on ``len(detection.skills) == 0``, which is false here -- one
        Skill *was* detected, it was just below the threshold -- so the case the
        warning exists for is the one case it does not cover. Recorded because
        #39 describes this fall-through as warned; measured, it is not.
        """
        _write_skill(tmp_path / "only", "only")
        output = tmp_path / "report.json"

        result = runner.invoke(
            app,
            ["scan", str(tmp_path), "--recursive", "--no-llm", "-f", "json", "-o", str(output)],
        )

        assert result.exit_code == 0, result.output
        assert "sub-skill" not in result.output
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["skill"]["name"] == "unknown"
        assert report["skill"]["manifest_status"] == "absent"

    def test_a_root_skill_short_circuits_every_nested_one(self, tmp_path: Path) -> None:
        """A ``SKILL.md`` at the root wins, and the nested Skills are not reported.

        ``detect_skills`` returns early on the root Skill without ever listing
        the children, so ``--recursive`` behaves as though the flag were absent.
        """
        _write_skill(tmp_path, "root")
        _write_skill(tmp_path / "alpha", "alpha")
        _write_skill(tmp_path / "beta", "beta")

        result = runner.invoke(app, ["scan", str(tmp_path), "--recursive", "--no-llm"])

        assert result.exit_code == 0, result.output
        assert "Multi-skill directory detected" not in result.output

    def test_only_immediate_children_are_looked_at(self, tmp_path: Path) -> None:
        """Depth one. A monorepo layout finds nothing and Scans the tree as one Skill.

        This is the trap #39 names: ``skills/`` one level down is invisible to
        ``--recursive``, which is precisely the wrong-shaped Scan ``--repo-scan``
        was built to prevent.
        """
        _write_skill(tmp_path / "modules" / "billing" / "skills" / "invoice", "invoice")
        _write_skill(tmp_path / "modules" / "shipping" / "skills" / "label", "label")

        result = runner.invoke(app, ["scan", str(tmp_path), "--recursive", "--no-llm"])

        assert result.exit_code == 0, result.output
        assert "no sub-skills detected" in result.output

    def test_a_jvm_build_directory_is_not_skipped(self, tmp_path: Path) -> None:
        """``target/`` holding a ``SKILL.md`` counts toward the threshold.

        ``JVM_BUILD_DIRECTORIES`` is a Repository Scan concept. ``detect_skills``
        walks ``iterdir()`` with no skip set at all, so a Skill copied into build
        output is reported as a Skill -- and, with one real sibling, is what
        pushes the directory over the two-Skill threshold in the first place.
        """
        _write_skill(tmp_path / "alpha", "alpha")
        _write_skill(tmp_path / "target", "alpha-copy")
        output = tmp_path / "combined.json"

        result = runner.invoke(
            app,
            ["scan", str(tmp_path), "--recursive", "--no-llm", "-f", "json", "-o", str(output)],
        )

        assert result.exit_code == 0, result.output
        combined = json.loads(output.read_text(encoding="utf-8"))
        assert [entry["path"] for entry in combined["skills"]] == ["alpha", "target"]


class TestTheAdvisoryOnAnOrdinaryScan:
    """``cli`` calls ``detect_skills`` on every directory Scan, only to advise."""

    def test_a_multi_skill_directory_is_pointed_at_recursive(self, tmp_path: Path) -> None:
        _write_skill(tmp_path / "alpha", "alpha")
        _write_skill(tmp_path / "beta", "beta")

        result = runner.invoke(app, ["scan", str(tmp_path), "--no-llm"])

        assert result.exit_code == 0, result.output
        assert "Found 2 skills" in result.output


class TestTheOutputContracts:
    """What the combined file holds. Two different shapes, chosen by ``--format``."""

    def test_combined_json_carries_the_documented_keys(self, tmp_path: Path) -> None:
        """The shape a CI consumer parses. Renaming any of these breaks them."""
        _write_skill(tmp_path / "alpha", "alpha")
        _write_skill(tmp_path / "beta", "beta")
        output = tmp_path / "combined.json"

        runner.invoke(
            app,
            ["scan", str(tmp_path), "--recursive", "--no-llm", "-f", "json", "-o", str(output)],
        )
        combined = json.loads(output.read_text(encoding="utf-8"))

        assert combined["multi_skill"] is True
        assert combined["skill_count"] == 2
        assert set(combined) == {
            "multi_skill",
            "skill_count",
            "max_risk_score",
            "execution_successful",
            "skills",
        }
        assert {"name", "path", "risk_score", "risk_severity", "finding_count"} <= set(
            combined["skills"][0]
        )

    def test_sarif_output_is_concatenated_documents_not_one_log(self, tmp_path: Path) -> None:
        """``--format sarif --output`` writes text separators between SARIF bodies.

        The file is therefore **not parseable as SARIF**, which the code says in
        as many words (``cli.py``: "not merged SARIF"). ``--repo-scan`` answers
        the same question with one valid log carrying one run per Skill. Anything
        that makes ``--recursive`` produce valid SARIF is an improvement *and* a
        behavior change for whoever splits this file on the separator today.
        """
        _write_skill(tmp_path / "alpha", "alpha")
        _write_skill(tmp_path / "beta", "beta")
        output = tmp_path / "combined.sarif"

        result = runner.invoke(
            app,
            ["scan", str(tmp_path), "--recursive", "--no-llm", "-f", "sarif", "-o", str(output)],
        )

        assert result.exit_code == 0, result.output
        written = output.read_text(encoding="utf-8")
        assert written.startswith("--- alpha ---")
        assert "\n--- beta ---\n" in written
        try:
            json.loads(written)
        except json.JSONDecodeError:
            pass
        else:  # pragma: no cover - a pass here means the contract changed
            raise AssertionError("the concatenated output parsed as JSON; see issue #39")
