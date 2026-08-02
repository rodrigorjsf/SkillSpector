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

"""The Manifest status: every cause of an empty Manifest, and how it reports.

Issue #11. A directory with no ``SKILL.md`` Scans as an anonymous Skill with an
empty Manifest -- indistinguishable from four other causes that also yield
``{}``. These tests pin each cause to its own status and pin the report to
saying so.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from skillspector.manifest_status import MANIFEST_STATUS_MESSAGES, ManifestStatus
from skillspector.nodes.build_context import build_context
from skillspector.nodes.report import report
from skillspector.state import SkillspectorState

# One cause per row: the ``SKILL.md`` body to write (None writes no file at all),
# and the status the Scan must report for it.
CAUSES: tuple[tuple[str, str | None, ManifestStatus], ...] = (
    ("no_file", None, ManifestStatus.ABSENT),
    ("no_opening_fence", "name: nofence\n", ManifestStatus.UNPARSEABLE),
    ("no_closing_fence", "---\nname: unterminated\n", ManifestStatus.UNPARSEABLE),
    ("empty_fence", "---\n---\n", ManifestStatus.UNPARSEABLE),
    ("not_a_mapping", "---\n- one\n- two\n---\n", ManifestStatus.UNPARSEABLE),
    ("invalid_yaml", "---\nname: [unclosed\n---\n", ManifestStatus.UNPARSEABLE),
    ("mapping_without_fields", "---\nunrelated: value\n---\n", ManifestStatus.EMPTY),
    ("declared", "---\nname: real-skill\ndescription: d\n---\n", ManifestStatus.PRESENT),
)


EVERY_CAUSE = pytest.mark.parametrize(
    ("body", "expected"),
    [(body, expected) for _name, body, expected in CAUSES],
    ids=[name for name, _body, _expected in CAUSES],
)


def _skill_dir(root: Path, body: str | None) -> Path:
    """Write one scan target carrying ``body`` as its ``SKILL.md``, or none."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.py").write_text("print(1)\n", encoding="utf-8")
    if body is not None:
        (root / "SKILL.md").write_text(body, encoding="utf-8")
    return root


@EVERY_CAUSE
def test_every_cause_of_an_empty_manifest_reports_its_own_status(
    tmp_path: Path, body: str | None, expected: ManifestStatus
) -> None:
    """Each cause maps to one status; none falls through to a default."""
    state: SkillspectorState = {"skill_path": str(_skill_dir(tmp_path / "target", body))}

    result = build_context(state)

    assert result["manifest_status"] == expected


@EVERY_CAUSE
def test_the_manifest_itself_is_unchanged_by_the_status(
    tmp_path: Path, body: str | None, expected: ManifestStatus
) -> None:
    """The status is additive: ``manifest`` keeps its type and its contents."""
    state: SkillspectorState = {"skill_path": str(_skill_dir(tmp_path / "target", body))}

    manifest = build_context(state)["manifest"]

    assert isinstance(manifest, dict)
    if expected is ManifestStatus.ABSENT or expected is ManifestStatus.UNPARSEABLE:
        assert manifest == {}
    elif expected is ManifestStatus.EMPTY:
        # A mapping always yields the four list keys, all of them empty.
        assert manifest == {
            "triggers": [],
            "permissions": [],
            "allowed-tools": [],
            "parameters": [],
        }
    else:
        assert manifest["name"] == "real-skill"


def test_the_causes_between_them_reach_every_status_but_unreadable() -> None:
    """Guard against an unreachable member: the table covers the enum.

    ``unreadable`` is the one member no fixture can produce portably -- it needs
    a file that exists and raises on read -- so it is named here rather than
    left silently uncovered.
    """
    reached = {expected for _name, _body, expected in CAUSES}

    assert reached == set(ManifestStatus) - {ManifestStatus.UNREADABLE}
    assert set(MANIFEST_STATUS_MESSAGES) == set(ManifestStatus)


def _report_body(manifest_status: object, output_format: str) -> str:
    """Render one report for a Skill whose Manifest carries ``manifest_status``."""
    state: SkillspectorState = {
        "filtered_findings": [],
        "component_metadata": [],
        "has_executable_scripts": False,
        "manifest": {},
        "skill_path": None,
        "output_format": output_format,
    }
    if manifest_status is not None:
        state["manifest_status"] = manifest_status  # type: ignore[typeddict-item]
    return str(report(state)["report_body"])


@pytest.mark.parametrize("output_format", ["json", "markdown", "terminal"])
def test_an_absent_skill_is_distinguishable_from_an_empty_manifest_in_the_report(
    output_format: str,
) -> None:
    """The reader can tell the two apart from the report, not the exit code."""
    absent = _report_body(ManifestStatus.ABSENT, output_format)
    empty = _report_body(ManifestStatus.EMPTY, output_format)

    assert absent != empty
    assert "absent" in absent
    assert "absent" not in empty


def test_the_json_report_names_the_status_and_says_what_it_means() -> None:
    """A machine reader gets the status; a human reader gets the sentence."""
    data = json.loads(_report_body(ManifestStatus.ABSENT, "json"))

    assert data["skill"]["manifest_status"] == "absent"
    assert (
        data["skill"]["manifest_status_detail"] == MANIFEST_STATUS_MESSAGES[ManifestStatus.ABSENT]
    )


def _without_the_clock(body: str) -> list[str]:
    """Drop the wall-clock line every format stamps, so two reports compare.

    Matched by the date itself rather than by its label: the labels differ per
    format, and one of them is a prefix of wording the status notice also uses.
    """
    return [line for line in body.splitlines() if not re.search(r"\d{4}-\d{2}-\d{2}", line)]


@pytest.mark.parametrize("output_format", ["json", "markdown", "terminal"])
def test_a_declared_manifest_reports_exactly_what_it_reported_before(
    output_format: str,
) -> None:
    """``present`` adds nothing, and a state carrying no status behaves as one.

    Compared against a state with the key missing entirely, which is what every
    caller that assembles state by hand supplies.
    """
    declared = _report_body(ManifestStatus.PRESENT, output_format)
    unset = _report_body(None, output_format)

    assert "manifest_status" not in declared
    assert "Manifest:" not in declared
    assert _without_the_clock(declared) == _without_the_clock(unset)
    # The comparison would pass on any two reports if the status never rendered.
    assert _without_the_clock(
        _report_body(ManifestStatus.ABSENT, output_format)
    ) != _without_the_clock(unset)


def test_an_unrecognized_status_on_state_is_read_as_present() -> None:
    """A hand-assembled state cannot make the report claim a status it lacks."""
    assert "manifest_status" not in _report_body("not-a-status", "json")
