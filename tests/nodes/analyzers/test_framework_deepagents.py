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

"""Tests for the gated ``framework_deepagents`` Analyzer, which carries no Rules.

Every assertion reads the ledger rows and status the node returns. A green suite
is not evidence the Analyzer ran: ``guard_analyzer_node`` turns any exception
into an empty Finding list plus a ``"failed"`` status, and this Analyzer's
correct Finding list is empty either way -- so a test that only checked
``findings == []`` would pass on a completely broken Analyzer. The rows are what
separate the two.
"""

from __future__ import annotations

from typing import Any

import pytest

from skillspector.framework import Framework
from skillspector.inspection_ledger import (
    LedgerOutcome,
    LedgerReason,
    finalize_ledger,
    inspection_work_id,
)
from skillspector.nodes.analyzers import framework_deepagents as analyzer

WRITABLE_SKILLS_PY = """from deepagents import create_deep_agent

agent = create_deep_agent(model="claude-sonnet-5", skills=["/skills/"])
"""

PYPROJECT = """[project]
name = "ops-agent"
version = "0.1.0"
dependencies = ["deepagents>=0.6.8"]
"""

SKILL_MD = """---
name: ops-runbook
description: Restart the ingest service.
---

# Ops runbook
"""

UNPARSEABLE_PY = """from deepagents import create_deep_agent

agent = create_deep_agent(model=, skills=[
"""


def make_state(
    file_cache: dict[str, str],
    framework: Framework = Framework.DEEPAGENTS,
) -> dict[str, Any]:
    """Build the slice of Scan state the Analyzer reads."""
    return {
        "framework": framework,
        "file_cache": dict(file_cache),
        "components": sorted(file_cache),
    }


class TestTheFrameworkGate:
    """The gate is the first statement, and a declining Analyzer emits nothing."""

    @pytest.mark.parametrize(
        "framework", [member for member in Framework if member is not Framework.DEEPAGENTS]
    )
    def test_another_framework_produces_no_findings_and_no_ledger(
        self, framework: Framework
    ) -> None:
        """Every Framework but this one, so a Framework added later is covered too."""
        result = analyzer.node(
            make_state(
                {"agent.py": WRITABLE_SKILLS_PY, "pyproject.toml": PYPROJECT},
                framework=framework,
            )
        )

        assert result["findings"] == []
        assert result.get("inspection_ledger", []) == []
        assert result.get("analyzer_status_events", []) == []

    def test_a_missing_framework_key_declines(self) -> None:
        result = analyzer.node({"file_cache": {"agent.py": WRITABLE_SKILLS_PY}})

        assert result["findings"] == []
        assert result.get("inspection_ledger", []) == []
        assert result.get("analyzer_status_events", []) == []


class TestApplicability:
    """A matching Framework always reports exactly one Analyzer Status.

    Applicability is one predicate -- the Components this Analyzer opens -- and
    both the gate and the accounting derive from it, so a Component that is
    opened is always a Component that is reported.
    """

    def test_all_three_applicable_kinds_are_opened_and_reported(self) -> None:
        result = analyzer.node(
            make_state(
                {
                    "agent.py": WRITABLE_SKILLS_PY,
                    "pyproject.toml": PYPROJECT,
                    "requirements-dev.txt": "deepagents>=0.6.8\n",
                    "skills/ops/SKILL.md": SKILL_MD,
                    "README.md": "# Ops agent\n",
                    "Makefile": "test:\n\tpytest\n",
                }
            )
        )

        assert [event["path"] for event in result["inspection_ledger"]] == [
            "agent.py",
            "pyproject.toml",
            "requirements-dev.txt",
            "skills/ops/SKILL.md",
        ]
        assert all(
            event["outcome"] is LedgerOutcome.COMPLETED for event in result["inspection_ledger"]
        )
        statuses = result["analyzer_status_events"]
        assert len(statuses) == 1
        assert statuses[0]["status"] == "completed"

    def test_a_component_that_produced_nothing_still_gets_a_work_item(self) -> None:
        """The whole point of this slice: no Rules, and still a row per Component."""
        result = analyzer.node(make_state({"pyproject.toml": PYPROJECT}))

        assert result["findings"] == []
        status = result["analyzer_status_events"][0]
        assert status["status"] == "completed"
        assert [target["path"] for target in status["planned_work"]] == ["pyproject.toml"]

    def test_an_unrecognized_file_alone_reports_not_applicable(self) -> None:
        """Synthetic state only -- the real graph cannot produce this input.

        Every signal ``detect_framework`` reads Deep Agents from is a Python
        module or a Python requirement file, and both are applicable here, from
        the same ``file_cache``. So a Scan that detected Deep Agents always has
        something for this Analyzer to open. The branch is ADR 0006's required
        gate shape rather than an observed case, and issue #70's criterion
        asking for it to be driven through the real graph assumed otherwise.
        """
        result = analyzer.node(make_state({"README.md": "# Ops agent\n"}))

        assert result["findings"] == []
        assert result.get("inspection_ledger", []) == []
        statuses = result["analyzer_status_events"]
        assert len(statuses) == 1
        assert statuses[0]["status"] == "not_applicable"
        assert statuses[0]["reason_code"] is LedgerReason.NO_APPLICABLE_FILES
        assert statuses[0]["planned_work"] == []

    def test_a_not_applicable_status_does_not_make_a_scan_incomplete(self) -> None:
        """Asserted through the projection rather than assumed from the reason code."""
        components = ["README.md"]
        result = analyzer.node(make_state({components[0]: "# Ops agent\n"}))

        completeness, _effective = finalize_ledger(
            {
                "components": components,
                "findings": [],
                "effective_finding_ids": [],
                "inspection_ledger": [],
                "analyzer_status_events": result["analyzer_status_events"],
            }
        )

        assert completeness["limitations"] == []
        assert completeness["is_complete"] is True
        assert completeness["execution_successful"] is True


class TestAnUnparseablePythonFile:
    """A file that does not parse was not inspected, however clean the report looks."""

    def test_it_is_skipped_with_the_syntax_error_reason(self) -> None:
        result = analyzer.node(make_state({"agent.py": UNPARSEABLE_PY}))

        events = result["inspection_ledger"]
        assert [event["outcome"] for event in events] == [LedgerOutcome.SKIPPED]
        assert events[0]["reason_code"] is LedgerReason.SYNTAX_ERROR

    def test_the_status_is_derived_rather_than_written_here(self) -> None:
        """``degraded`` is reserved to the ledger's own cascade.

        The control for that is the sibling test above: the same Analyzer
        reports ``completed`` when nothing is skipped, so this status is coming
        from the events rather than being a constant.
        """
        result = analyzer.node(
            make_state({"agent.py": UNPARSEABLE_PY, "pyproject.toml": PYPROJECT})
        )

        assert result["analyzer_status_events"][0]["status"] == "degraded"

    def test_a_parseable_file_alongside_it_is_still_opened(self) -> None:
        result = analyzer.node(
            make_state({"agent.py": UNPARSEABLE_PY, "worker.py": WRITABLE_SKILLS_PY})
        )

        outcomes = {event["path"]: event["outcome"] for event in result["inspection_ledger"]}
        assert outcomes == {
            "agent.py": LedgerOutcome.SKIPPED,
            "worker.py": LedgerOutcome.COMPLETED,
        }


class TestTheLedgerContract:
    """Planned work and emitted rows are the same set, keyed the same way."""

    def test_planned_work_matches_the_emitted_rows(self) -> None:
        result = analyzer.node(
            make_state({"agent.py": WRITABLE_SKILLS_PY, "pyproject.toml": PYPROJECT})
        )

        status = result["analyzer_status_events"][0]
        assert [target["work_id"] for target in status["planned_work"]] == [
            event["work_id"] for event in result["inspection_ledger"]
        ]
        assert [target["work_id"] for target in status["planned_work"]] == [
            inspection_work_id(analyzer.ANALYZER_ID, path, None, None)
            for path in ("agent.py", "pyproject.toml")
        ]

    def test_the_analyzer_emits_no_finding_at_all(self) -> None:
        """This slice carries no Rules; issues #71-#74 add them."""
        result = analyzer.node(
            make_state(
                {
                    "agent.py": WRITABLE_SKILLS_PY,
                    "pyproject.toml": PYPROJECT,
                    "skills/ops/SKILL.md": SKILL_MD,
                }
            )
        )

        assert result["findings"] == []
        assert all(event["emitted_finding_ids"] == [] for event in result["inspection_ledger"])


class TestTheDetectionFixtureThroughTheRealGraph:
    """The one committed Deep Agents input, driven end to end.

    Its Behavior Snapshot is the pre-Analyzer baseline this Ticket moves by
    exactly one status row. Reading the row out of a live Scan is what says the
    row is produced rather than merely committed.
    """

    @staticmethod
    def _scan() -> dict[str, Any]:
        from tests.behavior.projection import FIXTURES_DIR, scan_state

        return dict(scan_state(FIXTURES_DIR / "deepagents_detection"))

    def test_the_analyzer_reports_completed_over_the_requirement_file(self) -> None:
        statuses = self._scan()["analysis_completeness"]["analyzer_statuses"]
        mine = [status for status in statuses if status["analyzer_id"] == analyzer.ANALYZER_ID]

        assert len(mine) == 1
        assert mine[0]["status"] == "completed"
        assert mine[0]["planned_work"] == 1
        assert mine[0]["completed"] == 1
        assert mine[0]["skipped"] == 0
        assert mine[0]["failed"] == 0
        assert mine[0]["unaccounted"] == 0

    def test_it_contributes_no_limitation_and_moves_no_coverage(self) -> None:
        """The behavioral cost of this Ticket is one status row and nothing else."""
        completeness = self._scan()["analysis_completeness"]

        # The three limitations are the disabled semantic Analyzers, and they
        # are why `is_complete` is False on this fixture -- unchanged by a
        # Framework Analyzer that reports `completed`.
        assert len(completeness["limitations"]) == 3
        assert analyzer.ANALYZER_ID not in " ".join(completeness["limitations"])
        assert completeness["is_complete"] is False
        assert completeness["execution_successful"] is True
        assert completeness["coverage_percent"] == 100.0
        assert completeness["fully_inspected_files"] == 1
        assert completeness["entirely_uninspected_files"] == 0
        assert completeness["ledger_exceptions"] == []
