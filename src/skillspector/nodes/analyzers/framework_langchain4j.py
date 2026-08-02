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

"""LangChain4j Framework analyzer node.

Gated on the LangChain4j Framework. On every other input it returns no Findings
and emits nothing at all: no ledger event, no analyzer status. That silence is
the decision in ``docs/adr/0002-gated-analyzers-decline-silently.md`` -- an
Analyzer whose gate does not open plans no Work Item, so there is no unaccounted
work -- and it is what keeps a Scan of an Agent Skills Skill byte-for-byte
unchanged by this module's existence.

Two Rules today.

``L4J-SHELL`` (HIGH). LangChain4j's shell mode hands the model a single
``run_shell_command`` tool that runs in the host process with no sandboxing,
containerization or privilege restriction; upstream documents it as unsafe. It
is the risk that scheduled the Java track ahead of Deep Agents in
``docs/adr/0004-langchain4j-before-deepagents.md``.

``L4J-UNRESOLVED`` (MEDIUM). A Java-defined Skill's content, name, description
or loader path can be assembled at runtime, and then the instruction text the
model reads exists in no file this Scan can open. Resolving arbitrary Java
dataflow is out of scope; reporting the boundary is not. Silence there would let
the report read as clean on the one surface that was never examined.

What *is* resolvable -- a text block, a string literal, a same-unit constant --
is scanned by the existing content Analyzers, so a Skill body written in Java
gets the scrutiny a ``SKILL.md`` body gets.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import ModuleType
from typing import TYPE_CHECKING

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
from skillspector.nodes.analyzers.pattern_defaults import (
    get_category,
    get_explanation,
    get_pattern_name,
    get_remediation,
)
from skillspector.state import AnalyzerNodeResponse, SkillspectorState

if TYPE_CHECKING:  # Importing it at runtime would pull tree-sitter in at module top.
    from skillspector.langchain4j.skill_definitions import BuilderArgument

ANALYZER_ID = "framework_langchain4j"
logger = get_logger(__name__)

_RULE_ID = "L4J-SHELL"
_UNRESOLVED_RULE_ID = "L4J-UNRESOLVED"
_TAGS = ["ASI02"]
_SEVERITY = "HIGH"
_UNRESOLVED_SEVERITY = "MEDIUM"

# What a non-literal argument means depends on which one it is, so the Finding
# says so rather than making every unresolved argument read the same.
_UNRESOLVED_MESSAGES = {
    "content": (
        "Skill content is not statically resolvable, so the instruction surface the model reads "
        "was not scanned. It exists in no file this Scan could open."
    ),
    "name": (
        "The Skill name is built dynamically, so the Scan cannot say which Skill this definition "
        "declares."
    ),
    "description": (
        "The Skill description is built dynamically, so the text that decides when this Skill "
        "activates was not scanned."
    ),
}
_UNRESOLVED_CONFIDENCE = 1.0

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


def _finding(
    rule_id: str,
    path: str,
    start_line: int,
    message: str,
    confidence: float,
    severity: str = _SEVERITY,
) -> Finding:
    """Build one Finding for this Analyzer.

    Category, name, explanation and remediation are read from
    ``pattern_defaults`` rather than restated here. They are the same strings a
    report would fall back to anyway, and a second copy in this module would be
    free to drift from the catalogue the README and the AST10 crosswalk cite.
    """
    return Finding(
        rule_id=rule_id,
        message=message,
        severity=severity,
        confidence=confidence,
        file=path,
        start_line=start_line,
        category=get_category(rule_id),
        pattern=get_pattern_name(rule_id),
        tags=list(_TAGS),
        explanation=get_explanation(rule_id),
        remediation=get_remediation(rule_id),
    )


def _content_pattern_modules() -> list[ModuleType]:
    """The static pattern modules that examine Skill instruction text.

    Derived from the registry rather than listed, so a pattern family added
    upstream examines resolved Java content too without anyone remembering to
    come back here. Imported lazily: the registry imports this module, so naming
    it at module top would close an import cycle.
    """
    from importlib import import_module  # noqa: PLC0415

    from skillspector.nodes.analyzers import ANALYZER_NODE_IDS  # noqa: PLC0415

    return [
        import_module(f"skillspector.nodes.analyzers.{node_id}")
        for node_id in ANALYZER_NODE_IDS
        if node_id.startswith("static_patterns_")
    ]


def _scan_resolved_content(
    path: str, source: str, skill_name: str | None, argument: BuilderArgument
) -> list[Finding]:
    """Run the content Analyzers over one resolved Skill body.

    The text is scanned under a synthetic ``<skill>/SKILL.md`` path, not under
    the Java file's, because that is what it *is*: a Skill declaration body. The
    static runner's file-type filters treat a ``SKILL.md`` differently from an
    unrecognized extension -- code-example downweighting, documentation-prose
    exemptions -- so scanning it as Java would grade the same text on the wrong
    curve. The synthetic path never leaves this function.

    Each Finding is then relocated onto the Java file and line it really came
    from, so the report sends a reviewer to the source and SARIF points at a
    file that exists.

    A Finding whose matched text sits verbatim on that same raw line is dropped.
    Java sources are in ``file_cache`` and the ordinary static pass reads them,
    so a text block written inline is scanned twice -- once as Java, once as
    resolved content -- and reporting both would be the same string at the same
    location, twice. What survives is what reading the file directly would not
    have shown: text pulled from a constant declared elsewhere in the unit, or
    text whose escapes only become line structure once resolved.
    """
    from skillspector.nodes.analyzers.static_runner import run_static_patterns  # noqa: PLC0415

    body = argument.value
    if not body:
        return []
    synthetic_path = f"{skill_name or 'skill'}/SKILL.md"
    raw_lines = source.splitlines()

    relocated: list[Finding] = []
    for finding in run_static_patterns(
        {"components": [synthetic_path], "file_cache": {synthetic_path: body}},
        _content_pattern_modules(),
    ):
        java_line = argument.value_start_line + finding.start_line - 1
        raw_line = raw_lines[java_line - 1] if 0 < java_line <= len(raw_lines) else ""
        if finding.matched_text and finding.matched_text in raw_line:
            continue
        finding.file = path
        finding.start_line = java_line
        finding.end_line = None
        relocated.append(finding)
    return relocated


def _skill_definition_findings(path: str, source: str) -> list[Finding]:
    """``L4J-UNRESOLVED`` for what Java hides, content Findings for what it shows."""
    from skillspector.langchain4j import skill_definitions  # noqa: PLC0415

    findings: list[Finding] = []
    for definition in skill_definitions.find_skill_definitions(source):
        name_argument = definition.argument("name")
        skill_name = name_argument.value if name_argument else None
        for argument in definition.arguments:
            if argument.value is None:
                findings.append(
                    _finding(
                        _UNRESOLVED_RULE_ID,
                        path,
                        argument.line,
                        _UNRESOLVED_MESSAGES[argument.setter],
                        _UNRESOLVED_CONFIDENCE,
                        severity=_UNRESOLVED_SEVERITY,
                    )
                )
            elif argument.setter == "content":
                findings.extend(_scan_resolved_content(path, source, skill_name, argument))

    # A loader whose path is not a literal is the same silence in another shape:
    # the Skills it reads are not in view, and no content Analyzer saw them.
    for call in skill_definitions.find_skill_loader_calls(source):
        if call.directory is None:
            findings.append(
                _finding(
                    _UNRESOLVED_RULE_ID,
                    path,
                    call.line,
                    (
                        f"{call.loader}.{call.method} is called with a path that is not a literal, "
                        "so the Skills it loads were not located or scanned."
                    ),
                    _UNRESOLVED_CONFIDENCE,
                    severity=_UNRESOLVED_SEVERITY,
                )
            )
    return findings


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
    shell_declarations = signals.shell_artifact_declaration_lines(file_cache)

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
            inspected[path].append(
                _finding(_RULE_ID, path, usage_line, _WIRING_MESSAGE, _WIRING_CONFIDENCE)
            )
        inspected[path].extend(_skill_definition_findings(path, source))

    for path, declaration_line in shell_declarations.items():
        inspected.setdefault(path, []).append(
            _finding(
                _RULE_ID, path, declaration_line, _DECLARATION_MESSAGE, _DECLARATION_CONFIDENCE
            )
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
