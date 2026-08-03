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

"""Deep Agents Framework analyzer node.

Gated on the Deep Agents Framework. On every other input it returns no Findings
and emits nothing at all: no ledger event, no analyzer status. That silence is
the decision in ``docs/adr/0002-gated-analyzers-decline-silently.md`` -- an
Analyzer whose gate does not open plans no Work Item, so there is no unaccounted
work -- and it is what keeps a Scan of an Agent Skills Skill byte-for-byte
unchanged by this module's existence.

On a Deep Agents Scan it reports exactly one Analyzer Status, and what it opens
is one predicate: ``signals.applicable_files``, the Python modules, Python
requirement files and Agent Skills manifests of the Scan. Both the gate and the
planned work derive from that single result, so the Analyzer cannot open a
Component it does not report.
``docs/adr/0006-langchain4j-applicability-is-what-it-opens.md`` records why, and
``docs/adr/0008-deepagents-analyzer-resolves-one-module-deep.md`` §3 records why
the set reaches past Python into every ``SKILL.md``.

One Rule today.

``DA-UNRESOLVED`` (MEDIUM). A Deep Agents application can assemble its Skill list
per request, build its backend in a helper this Scan cannot follow, or route a
literal Skill path to a store whose namespace is computed from the caller. In
each of those the configuration that decides whether the agent can rewrite its
own instructions exists in no file this Scan can open, and saying nothing there
would let the report read as clean on the surface that was never examined. So
the Rule and the resolution boundary are one thing seen from two sides:
:mod:`skillspector.deepagents.host_config` resolves a literal and a same-module
constant and refuses to guess at anything else, and every refusal becomes a
Finding that names *which* thing was unresolvable. ADR 0008 §1 settled the
boundary and copied it deliberately from the Java track's
``L4J-UNRESOLVED``, so the project keeps one resolution rule rather than one per
Framework.

The Rule reports where the Scan stopped looking; it does not judge what it did
see. Whether a resolved Skill source path is actually writable is
``DA-SKILL-WRITABLE``, issue #72, and this Rule is deliberately built first
because that verdict needs somewhere to fall when it cannot decide. Issues #73
and #74 add Skill-name shadowing across sources and a subagent defined without
its own Skills.

**The ``not_applicable`` branch cannot be reached through the graph.** Every
signal ``skillspector.framework`` detects Deep Agents by is a Python module or a
Python requirement file, and both are exactly what this Analyzer opens.
``build_context`` derives ``framework`` and ``file_cache`` from the same values
in one return, and ``--repo-scan`` changes nothing about that -- it runs the
ordinary graph once per discovered Skill directory, so detection re-runs over
each narrowed tree. So a Scan that reaches this node having detected Deep Agents
always has at least one applicable Component. The branch is kept because ADR 0006
makes it the shape of an Applicability gate rather than an observed case, and
later Tickets only widen the predicate; it is exercised from synthetic state, and
it is the one thing issue #70's acceptance criteria assumed wrongly.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping

from skillspector.deepagents import host_config, signals
from skillspector.framework import Framework
from skillspector.inspection_ledger import (
    AnalyzerStatus,
    InspectionLedgerEvent,
    LedgerOutcome,
    LedgerReason,
    analyzer_status_event,
    analyzer_status_for_events,
    ledger_event,
)
from skillspector.logging_config import get_logger
from skillspector.models import Finding
from skillspector.nodes.analyzers.pattern_defaults import (
    get_category,
    get_explanation,
    get_pattern_name,
    get_remediation,
)
from skillspector.state import AnalyzerNodeResponse, SkillspectorState

ANALYZER_ID = "framework_deepagents"
logger = get_logger(__name__)

_PHASE = "static"

_UNRESOLVED_RULE_ID = "DA-UNRESOLVED"
_UNRESOLVED_SEVERITY = "MEDIUM"
_TAGS = ["ASI02"]

# The boundary is a fact about the shape of the source -- an argument that is
# not a literal and not a name bound in this module -- rather than an inference
# from it, so there is nothing left to doubt about the report.
_UNRESOLVED_CONFIDENCE = 1.0

# Four cases, four messages. A report that said the same sentence about an
# unknown Skill list and an unknown backend would leave a reviewer to work out
# which surface went unexamined, which is the work this Rule exists to save.
_UNRESOLVED_SKILL_LIST = (
    "The Skill source list is assembled at runtime, so the Scan cannot say which Skill "
    "directories this agent was given and examined none of them."
)
_UNRESOLVED_BACKEND = (
    "The backend is built somewhere this Scan cannot follow, so whether the agent's Skill files "
    "are on disk at all -- and whether anything can write to them -- was not determined."
)
_UNRESOLVED_PERMISSIONS = (
    "The filesystem permission rules are not statically resolvable, so what this agent is allowed "
    "to do to its Skill files was not determined."
)


def _unresolved_route_message(path: str) -> str:
    """The ``DA-UNRESOLVED`` message for a resolved path routed into a store.

    Names the path because this is the half-resolved case: the reviewer can see
    the path in their own configuration and the Finding has to say that seeing
    it is not the same as knowing what lives there.
    """
    return (
        f"The Skill source path {path} resolves, but it is routed to a store whose contents are "
        "computed per request, so its writability was not determined."
    )


def _decline() -> AnalyzerNodeResponse:
    """Return the empty response a Framework-mismatched Analyzer declines with."""
    return {"findings": []}


def _finding(path: str, start_line: int, message: str) -> Finding:
    """Build one ``DA-UNRESOLVED`` Finding.

    Category, name, explanation and remediation are read from
    ``pattern_defaults`` rather than restated here. They are the same strings a
    report would fall back to anyway, and a second copy in this module would be
    free to drift from the catalogue the README and the AST10 crosswalk cite.
    """
    return Finding(
        rule_id=_UNRESOLVED_RULE_ID,
        message=message,
        severity=_UNRESOLVED_SEVERITY,
        confidence=_UNRESOLVED_CONFIDENCE,
        file=path,
        start_line=start_line,
        category=get_category(_UNRESOLVED_RULE_ID),
        pattern=get_pattern_name(_UNRESOLVED_RULE_ID),
        tags=list(_TAGS),
        explanation=get_explanation(_UNRESOLVED_RULE_ID),
        remediation=get_remediation(_UNRESOLVED_RULE_ID),
    )


def _boundary_findings(path: str, tree: ast.Module) -> list[Finding]:
    """Every place one Python module's host configuration stopped resolving.

    An argument that is absent is not a boundary: no ``skills`` is no Skills, no
    ``permissions`` is no rules, no ``backend`` is the default one. Each of those
    is a configuration the later Rules judge, not a silence this one reports.
    """
    findings: list[Finding] = []
    for configuration in host_config.find_agent_configurations(tree):
        for resolution, message in (
            (configuration.skill_paths, _UNRESOLVED_SKILL_LIST),
            (configuration.backend, _UNRESOLVED_BACKEND),
            (configuration.permission_rules, _UNRESOLVED_PERMISSIONS),
        ):
            if resolution is not None and resolution.unresolved:
                findings.append(_finding(path, resolution.line, message))
        findings.extend(
            _finding(path, route.line, _unresolved_route_message(route.path))
            for route in configuration.opaque_routes
        )
    return findings


def _open(path: str, source: str) -> tuple[InspectionLedgerEvent, list[Finding]]:
    """Open one applicable Component and record what came of it.

    A Python module is parsed, because that is what every Rule this Analyzer
    carries needs and because a file that does not parse was not inspected
    however clean the report looks. The skip shape is
    ``behavioral_ast.py``'s -- ``LedgerOutcome.SKIPPED`` with
    ``LedgerReason.SYNTAX_ERROR`` -- so a reader meets one vocabulary for an
    unparseable Python file rather than one per Analyzer.

    Anything else applicable is a requirement file or a Skill manifest. Neither
    has a Rule reading it yet, so opening it is listing it; ADR 0008 §3 states
    that cost rather than leaving it to be discovered in a snapshot.

    *source* is never ``None``: everything applicable came out of ``file_cache``
    and therefore was readable. Which kind of Component it is is asked of the
    path, not inferred from a missing content -- ``behavioral_ast`` reads absent
    content as ``MISSING_FILE_CACHE``, and the two must not look alike here.
    """
    if signals.is_python_source(path):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return (
                ledger_event(
                    outcome=LedgerOutcome.SKIPPED,
                    phase=_PHASE,
                    analyzer_id=ANALYZER_ID,
                    path=path,
                    reason=LedgerReason.SYNTAX_ERROR,
                ),
                [],
            )
        findings = _boundary_findings(path, tree)
    else:
        findings = []
    return (
        ledger_event(
            outcome=LedgerOutcome.COMPLETED,
            phase=_PHASE,
            analyzer_id=ANALYZER_ID,
            path=path,
            emitted_finding_ids=[finding.finding_id for finding in findings],
        ),
        findings,
    )


def node(state: SkillspectorState) -> AnalyzerNodeResponse:
    """Report what this Analyzer opened on a Deep Agents Scan; decline on any other."""
    if state.get("framework") != Framework.DEEPAGENTS:
        return _decline()

    file_cache: Mapping[str, str] = state.get("file_cache") or {}

    applicable = signals.applicable_files(file_cache)
    if not applicable:
        logger.info("%s: nothing applicable, reporting not_applicable", ANALYZER_ID)
        return {
            "findings": [],
            "analyzer_status_events": [
                analyzer_status_event(
                    analyzer_id=ANALYZER_ID,
                    status=AnalyzerStatus.NOT_APPLICABLE,
                    reason=LedgerReason.NO_APPLICABLE_FILES,
                )
            ],
        }

    # Every file opened gets a row, whether or not it yielded a Finding. Once
    # this Analyzer runs, an absence of Findings must be distinguishable from an
    # absence of inspection.
    #
    # Iterated over the same result the gate tested, never recomputed from
    # `file_cache`: two definitions of "applicable" a few lines apart are what
    # ADR 0006 exists to prevent recurring.
    opened = [_open(path, source) for path, source in sorted(applicable.items())]
    events = [event for event, _findings in opened]
    findings = [finding for _event, file_findings in opened for finding in file_findings]

    # The status is derived from these events rather than written here.
    # `analyzer_status_for_events` owns the cascade, and `DEGRADED` -- which a
    # skipped file produces -- is reserved to it; see
    # `.claude/rules/analyzer-status.md`. It builds `planned_work` from the same
    # events, so status and ledger cannot drift into unaccounted work.
    logger.info("%s: %d findings across %d components", ANALYZER_ID, len(findings), len(events))
    return {
        "findings": findings,
        "inspection_ledger": events,
        "analyzer_status_events": [analyzer_status_for_events(ANALYZER_ID, events)],
    }
