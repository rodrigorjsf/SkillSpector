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

"""Tests for the gated ``framework_deepagents`` Analyzer and its resolution boundary.

Every test enters through ``node(state)`` with a synthetic state.
:mod:`skillspector.deepagents.host_config` gets no test of its own on purpose:
a resolution decision that cannot be observed as a Finding is a decision that
should not exist, and a suite that asserted the resolver's return shapes would
go green on an Analyzer that never called it.

Many assertions read the ledger rows and status rather than the Finding list.
A green suite is not evidence the Analyzer ran: ``guard_analyzer_node`` turns any
exception into an empty Finding list plus a ``"failed"`` status, and an empty
Finding list is also the correct answer on a configuration that fully resolves --
so a test that only checked ``findings == []`` would pass on a completely broken
Analyzer. The rows are what separate the two.
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

# The four boundary cases, one module each, each written the way upstream's own
# documentation writes it.

RUNTIME_SKILLS_PY = """from deepagents import create_deep_agent

SKILLS_BY_ROLE = {
    "engineering": ["/skills/code-review/"],
    "support": ["/skills/runbook/"],
}


def build(user_role: str):
    return create_deep_agent(
        model="claude-sonnet-5",
        skills=SKILLS_BY_ROLE.get(user_role, []),
    )
"""

HELPER_BACKEND_PY = """from deepagents import create_deep_agent

from .infra import backend_for_tenant

agent = create_deep_agent(
    model="claude-sonnet-5",
    backend=backend_for_tenant("acme"),
    skills=["/skills/"],
)
"""

HELPER_PERMISSIONS_PY = """from deepagents import create_deep_agent

from .policy import rules_for_tenant

agent = create_deep_agent(
    model="claude-sonnet-5",
    skills=["/skills/"],
    permissions=rules_for_tenant("acme"),
)
"""

ROUTED_STORE_PY = """from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

agent = create_deep_agent(
    model="claude-sonnet-5",
    skills=["/skills/"],
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": StoreBackend(
                namespace=lambda rt: (rt.server_info.assistant_id,),
            ),
        },
    ),
)
"""

# The controls. Each resolves through the boundary rather than falling on it.

MODULE_CONSTANT_PY = """from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

SKILL_PATHS = ["/skills/shared/", "/skills/personal/"]
BACKEND = FilesystemBackend(root_dir="./app")

agent = create_deep_agent(
    model="claude-sonnet-5",
    backend=BACKEND,
    skills=SKILL_PATHS,
    permissions=[
        FilesystemPermission(operations=["write"], paths=["/skills/shared/**"], mode="deny"),
    ],
)
"""

NO_ARGUMENTS_PY = """from deepagents import create_deep_agent

agent = create_deep_agent(model="claude-sonnet-5")
"""


def _messages(result: dict[str, Any]) -> list[str]:
    """The Finding messages a node call produced, in the order it produced them."""
    return [finding.message for finding in result["findings"]]


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


class TestTheResolutionBoundary:
    """``DA-UNRESOLVED``: the four things this Scan refuses to guess at."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            pytest.param(RUNTIME_SKILLS_PY, "Skill source list", id="skill-list"),
            pytest.param(HELPER_BACKEND_PY, "backend is built", id="backend"),
            pytest.param(HELPER_PERMISSIONS_PY, "permission rules", id="permissions"),
            pytest.param(ROUTED_STORE_PY, "/skills/", id="routed-store"),
        ],
    )
    def test_each_case_raises_one_finding_that_names_what_was_unresolvable(
        self, source: str, expected: str
    ) -> None:
        result = analyzer.node(make_state({"agent.py": source}))

        assert [finding.rule_id for finding in result["findings"]] == ["DA-UNRESOLVED"]
        assert expected in result["findings"][0].message
        assert result["findings"][0].severity == "MEDIUM"
        assert result["findings"][0].file == "agent.py"

    def test_the_four_messages_do_not_all_read_the_same(self) -> None:
        """The criterion the report is judged on: which surface went unexamined.

        Asserted across the four rather than per case, because the failure this
        guards against -- one message reused -- is invisible from inside any
        single one of them.
        """
        messages = {
            _messages(analyzer.node(make_state({"agent.py": source})))[0]
            for source in (
                RUNTIME_SKILLS_PY,
                HELPER_BACKEND_PY,
                HELPER_PERMISSIONS_PY,
                ROUTED_STORE_PY,
            )
        }

        assert len(messages) == 4

    def test_the_finding_points_at_the_argument_rather_than_the_call(self) -> None:
        """A multi-line call is the ordinary shape, so the top of it is not enough."""
        result = analyzer.node(make_state({"agent.py": HELPER_PERMISSIONS_PY}))

        lines = HELPER_PERMISSIONS_PY.splitlines()
        assert "rules_for_tenant" in lines[result["findings"][0].start_line - 1]

    def test_the_pattern_catalog_supplies_the_reported_prose(self) -> None:
        """Read from ``pattern_defaults``, not restated in the node."""
        finding = analyzer.node(make_state({"agent.py": RUNTIME_SKILLS_PY}))["findings"][0]

        assert finding.category == "Deep Agents Framework"
        assert finding.pattern == "Unresolvable Host Configuration"
        assert finding.explanation
        assert finding.remediation


class TestWhatResolvesRaisesNothing:
    """The boundary is only worth anything if ordinary code lands on the other side."""

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(WRITABLE_SKILLS_PY, id="literal-list"),
            pytest.param(MODULE_CONSTANT_PY, id="same-module-constants"),
            pytest.param(NO_ARGUMENTS_PY, id="no-arguments"),
        ],
    )
    def test_a_resolvable_configuration_is_silent(self, source: str) -> None:
        assert analyzer.node(make_state({"agent.py": source}))["findings"] == []

    def test_an_absent_argument_is_a_configuration_rather_than_a_silence(self) -> None:
        """No Skills, no rules and the default backend are answers, not boundaries."""
        result = analyzer.node(make_state({"agent.py": NO_ARGUMENTS_PY}))

        assert result["findings"] == []
        assert result["analyzer_status_events"][0]["status"] == "completed"

    def test_a_name_assigned_twice_at_module_level_resolves_to_nothing(self) -> None:
        """Which assignment reaches the call is control flow, so it is a boundary.

        The control is ``MODULE_CONSTANT_PY`` above: the same shape assigned
        once is silent, so this Finding comes from the reassignment rather than
        from same-module constants being unsupported.
        """
        source = MODULE_CONSTANT_PY.replace(
            'BACKEND = FilesystemBackend(root_dir="./app")',
            'BACKEND = FilesystemBackend(root_dir="./app")\nBACKEND = FilesystemBackend(root_dir="./other")',
        )

        assert _messages(analyzer.node(make_state({"agent.py": source}))) == [
            _messages(analyzer.node(make_state({"agent.py": HELPER_BACKEND_PY})))[0]
        ]

    def test_a_route_that_covers_no_skill_source_path_raises_nothing(self) -> None:
        """A store routed somewhere the agent was never given Skills from."""
        source = ROUTED_STORE_PY.replace('skills=["/skills/"]', 'skills=["/vetted/"]')

        assert analyzer.node(make_state({"agent.py": source}))["findings"] == []

    def test_an_unresolved_skill_list_is_not_also_reported_as_an_opaque_route(self) -> None:
        """One silence, described once, in the vocabulary that fits it."""
        source = ROUTED_STORE_PY.replace(
            'skills=["/skills/"]', "skills=SKILLS_BY_ROLE.get(user_role, [])"
        )

        assert _messages(analyzer.node(make_state({"agent.py": source}))) == [
            _messages(analyzer.node(make_state({"agent.py": RUNTIME_SKILLS_PY})))[0]
        ]

    def test_a_non_python_component_produces_no_finding(self) -> None:
        """A requirement file and a manifest are opened and listed, and nothing more."""
        result = analyzer.node(
            make_state({"pyproject.toml": PYPROJECT, "skills/ops/SKILL.md": SKILL_MD})
        )

        assert result["findings"] == []
        assert len(result["inspection_ledger"]) == 2


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

    def test_a_fully_resolved_configuration_emits_no_finding_at_all(self) -> None:
        """A literal Skill list resolves, so there is no boundary to report."""
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

    def test_a_finding_is_accounted_for_on_the_row_of_the_file_it_came_from(self) -> None:
        result = analyzer.node(
            make_state({"agent.py": RUNTIME_SKILLS_PY, "pyproject.toml": PYPROJECT})
        )

        emitted = {
            event["path"]: event["emitted_finding_ids"] for event in result["inspection_ledger"]
        }
        assert emitted["pyproject.toml"] == []
        assert emitted["agent.py"] == [finding.finding_id for finding in result["findings"]]
        assert len(emitted["agent.py"]) == 1


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
