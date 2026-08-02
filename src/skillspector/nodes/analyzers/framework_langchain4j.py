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

"""LangChain4j Framework analyzer node -- ``L4J-SHELL``.

Gated on the LangChain4j Framework. On every other input it returns no Findings
and emits nothing at all: no ledger event, no analyzer status. That silence is
the decision in ``docs/adr/0002-gated-analyzers-decline-silently.md`` -- an
Analyzer whose gate does not open plans no Work Item, so there is no unaccounted
work -- and it is what keeps a Scan of an Agent Skills Skill byte-for-byte
unchanged by this module's existence.

The Rule it carries is ``L4J-SHELL``. LangChain4j's shell mode hands the model a
single ``run_shell_command`` tool that runs in the host process with no
sandboxing, containerization or privilege restriction; upstream documents it as
unsafe. It is the risk that scheduled the Java track ahead of Deep Agents in
``docs/adr/0004-langchain4j-before-deepagents.md``.
"""

from __future__ import annotations

from collections.abc import Mapping

from skillspector.framework import Framework
from skillspector.inspection_ledger import (
    LedgerOutcome,
    PlannedWorkTarget,
    analyzer_status_event,
    inspection_work_id,
    ledger_event,
)
from skillspector.langchain4j import signals
from skillspector.logging_config import get_logger
from skillspector.models import Finding
from skillspector.state import AnalyzerNodeResponse, SkillspectorState

ANALYZER_ID = "framework_langchain4j"
logger = get_logger(__name__)

_RULE_ID = "L4J-SHELL"
_CATEGORY = "LangChain4j Framework"
_TAGS = ["ASI02"]
_SEVERITY = "HIGH"

# The wiring is the decision; the declaration only puts the capability within
# reach. Both are HIGH -- an application that ships the shell module can reach
# shell mode -- but the wiring is the one there is nothing left to doubt about.
_WIRING_CONFIDENCE = 0.95
_DECLARATION_CONFIDENCE = 0.85

_WIRING_MESSAGE = (
    "LangChain4j shell mode is wired here: the agent is given a run_shell_command tool that "
    "executes arbitrary commands in the host process with no sandboxing or privilege restriction."
)
_DECLARATION_MESSAGE = (
    f"The build file declares {signals.SHELL_ARTIFACT_ID}, putting LangChain4j's unsandboxed "
    "shell mode on the classpath where any wiring can reach it."
)
_EXPLANATION = (
    "In shell mode LangChain4j replaces the activate_skill tool surface with a single "
    "run_shell_command tool and lets the model read Skill files off the filesystem itself. "
    "Commands run directly in the host process environment -- LangChain4j's own documentation "
    "states there is no sandboxing, containerization or privilege restriction. A prompt-injected "
    "or misbehaving model therefore executes arbitrary commands on the machine running the "
    "application."
)
_REMEDIATION = (
    "Prefer tool mode (Skills.from(...)) so the model reaches only the tools the Skill declares. "
    "Where shell mode is genuinely required, confine the process: run it in a container or under "
    "a restricted user, and set RunShellCommandToolConfig.workingDirectory rather than inheriting "
    "the JVM's."
)


def _finding(path: str, start_line: int, message: str, confidence: float) -> Finding:
    return Finding(
        rule_id=_RULE_ID,
        message=message,
        severity=_SEVERITY,
        confidence=confidence,
        file=path,
        start_line=start_line,
        category=_CATEGORY,
        tags=list(_TAGS),
        explanation=_EXPLANATION,
        remediation=_REMEDIATION,
    )


def _planned_target(path: str) -> PlannedWorkTarget:
    """The work target for one inspected file, keyed exactly as its event will be.

    Derived from the same ``(analyzer_id, path, start_line, end_line)`` tuple the
    event's ``work_id`` comes from, so status and ledger cannot drift into the
    unaccounted-work error ``finalize_ledger`` raises when they disagree.
    """
    return {
        "work_id": inspection_work_id(ANALYZER_ID, path, None, None),
        "path": path,
        "start_line": None,
        "end_line": None,
    }


def _decline() -> AnalyzerNodeResponse:
    """Return the empty response a gated Analyzer declines with."""
    return {"findings": []}


def node(state: SkillspectorState) -> AnalyzerNodeResponse:
    """Report LangChain4j shell mode on a LangChain4j Scan; decline on any other."""
    if state.get("framework") != Framework.LANGCHAIN4J:
        return _decline()

    file_cache: Mapping[str, str] = state.get("file_cache") or {}
    java_sources = signals.java_sources(file_cache)
    shell_declarations = signals.find_shell_artifact_declarations(file_cache)

    # Applicability, second and last gate. With no Java to parse and no build
    # file already naming the shell module, this Analyzer holds nothing it can
    # inspect. It declines in the same total silence as a Framework mismatch.
    #
    # ADR 0002 *deferred* rather than approved that silence: it names a matching
    # Framework with nothing applicable as the case that should eventually carry
    # a `not_applicable` status, because unlike a gate mismatch it does have
    # planned work. Emitting one today would add a row to `analysis_completeness`
    # for `tests/fixtures/langchain4j_detection`, whose committed Behavior
    # Snapshot this increment must leave byte-identical. Reopen with the status,
    # and regenerate that snapshot deliberately, when the gate stops being the
    # thing holding it shut.
    if not java_sources and not shell_declarations:
        logger.info("%s: no Java and no shell declaration, declining", ANALYZER_ID)
        return _decline()

    # Every file opened gets a row, whether or not it yielded a Finding: once
    # this Analyzer runs, an absence of Findings must be distinguishable from an
    # absence of inspection.
    inspected: dict[str, list[Finding]] = {
        path: [] for path in (*java_sources, *signals.jvm_build_files(file_cache))
    }

    # The parser enters here and nowhere earlier. At module top an absent
    # tree-sitter would break importing the analyzer registry itself; inside the
    # node it reaches `guard_analyzer_node`, which records the Analyzer as
    # `failed` with a fatal ledger exception -- so the Scan exits non-zero and
    # says why, rather than reporting an empty Finding list as a clean result.
    # It is deliberately not wrapped: swallowing the ImportError here is exactly
    # the silent failure this ordering exists to prevent.
    from skillspector.langchain4j import shell_skills  # noqa: PLC0415

    for path, source in java_sources.items():
        usage_line = shell_skills.find_shell_skills_usage(source)
        if usage_line is not None:
            inspected[path].append(_finding(path, usage_line, _WIRING_MESSAGE, _WIRING_CONFIDENCE))

    for path, declaration_line in shell_declarations.items():
        inspected.setdefault(path, []).append(
            _finding(path, declaration_line, _DECLARATION_MESSAGE, _DECLARATION_CONFIDENCE)
        )

    ordered = sorted(inspected.items())
    events = [
        ledger_event(
            analyzer_id=ANALYZER_ID,
            outcome=LedgerOutcome.COMPLETED,
            phase="static",
            path=path,
            emitted_finding_ids=[finding.finding_id for finding in findings],
        )
        for path, findings in ordered
    ]
    findings = [finding for _path, file_findings in ordered for finding in file_findings]

    logger.info("%s: %d findings across %d files", ANALYZER_ID, len(findings), len(ordered))
    return {
        "findings": findings,
        "inspection_ledger": events,
        "analyzer_status_events": [
            analyzer_status_event(
                analyzer_id=ANALYZER_ID,
                status="completed",
                planned_work=[_planned_target(path) for path, _findings in ordered],
            )
        ],
    }
