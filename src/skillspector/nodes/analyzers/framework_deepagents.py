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

Two Rules today, and they partition every ``create_deep_agent(...)`` call
between them: what resolved is judged, and what did not is reported as not
having been.

``DA-SKILL-WRITABLE`` (MEDIUM, LOW where a human approves the write). The verdict
the Deep Agents work exists for: *can this agent rewrite its own instructions?*
Upstream states the default in as many words -- agents can write to Skill files
unless a permission rule blocks the path -- so the unsafe configuration is the
one a developer gets by following the tutorial, and two applications differing by
exactly that produced identical Scans before this Rule. One Finding **per
resolved Skill source path**, so a reviewer who consciously accepts a writable
personal directory can Baseline that path and still be told about a writable
shared library. It is one composed Rule rather than three, and the mitigations
lower its severity rather than raising Findings of their own;
``docs/adr/0008-deepagents-analyzer-resolves-one-module-deep.md`` §2 settled
both, and :mod:`skillspector.deepagents.writability` computes the verdict --
walking the rules in the order they were written, because that order is what
upstream's own advice to place specific rules before broad ones depends on.

**The Ticket's "read-only backend" does not exist upstream, and this is the
record of it.** Issue #72 asked for a path routed to a read-only backend not to
be reported as writable. The captured reference documents four backends and none
of them is read-only -- the only read-only-ness it describes is a ``deny`` rule.
So the backend contributes unknowability rather than a verdict: a Skill path
routed into a store whose contents are computed per request is reported by the
Rule below and reaches no verdict at all.

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
see. It was deliberately built first, because the verdict above needs somewhere
to fall when it cannot decide, and a fifth case joined it with that verdict: a
permission rule written in a shape this Scan cannot read leaves the ordered walk
undecided for every path, so the whole configuration reaches the boundary rather
than a guess. Issues #73 and #74 add Skill-name shadowing across sources and a
subagent defined without its own Skills.

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

from skillspector.deepagents import host_config, signals, writability
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
_WRITABLE_RULE_ID = "DA-SKILL-WRITABLE"
_TAGS = ["ASI02"]

# The boundary is a fact about the shape of the source -- an argument that is
# not a literal and not a name bound in this module -- rather than an inference
# from it, so there is nothing left to doubt about the report.
_UNRESOLVED_CONFIDENCE = 1.0

# The writability verdict is an inference: three arguments read together, walked
# in order, against what upstream documents the default to be. So it carries the
# confidence the LangChain4j absence Rules carry rather than the boundary's --
# `framework_langchain4j.py` sets 0.9 for the same reason.
_WRITABLE_CONFIDENCE = 0.9

# MEDIUM unmitigated, LOW where a human is put in front of the write. ADR 0008
# §2 is why the mitigation moves the severity rather than clearing the Finding
# or raising one of its own: an approval prompt is not a denial, and an
# application that requires approval has still given the agent its own
# instructions to rewrite.
_WRITABLE_SEVERITY = "MEDIUM"
_WRITABLE_MITIGATED_SEVERITY = "LOW"

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


_UNREADABLE_PERMISSION_RULE = (
    "A filesystem permission rule is written in a shape this Scan does not recognize, so which "
    "rule decides a Skill path -- and therefore what the agent may do to it -- was not determined."
)


def _writable_message(path: str, mitigated: bool) -> str:
    """The ``DA-SKILL-WRITABLE`` message for one Skill source path.

    Names the path, because one Finding per path is what lets a reviewer accept
    a writable personal directory without also accepting a writable shared
    library, and a message that did not say which path was which would take that
    back.
    """
    if mitigated:
        return (
            f"The agent is given the Skill source path {path} and nothing denies it write access, "
            "so it can rewrite the instructions it runs on. A human is asked to approve the write."
        )
    return (
        f"The agent is given the Skill source path {path} and nothing denies it write access, so "
        "it can rewrite the instructions it runs on and no human is asked."
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


def _finding(
    rule_id: str, severity: str, confidence: float, path: str, start_line: int, message: str
) -> Finding:
    """Build one Finding of either Rule.

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


def _unresolved(path: str, start_line: int, message: str) -> Finding:
    """Build one ``DA-UNRESOLVED`` Finding."""
    return _finding(
        _UNRESOLVED_RULE_ID, _UNRESOLVED_SEVERITY, _UNRESOLVED_CONFIDENCE, path, start_line, message
    )


def _boundary_findings(path: str, configuration: host_config.AgentConfiguration) -> list[Finding]:
    """Every place one host configuration stopped resolving.

    An argument that is absent is not a boundary: no ``skills`` is no Skills, no
    ``permissions`` is no rules, no ``backend`` is the default one. Each of those
    is a configuration the writability verdict judges, not a silence this one
    reports.
    """
    findings = [
        _unresolved(path, resolution.line, message)
        for resolution, message in (
            (configuration.skill_paths, _UNRESOLVED_SKILL_LIST),
            (configuration.backend, _UNRESOLVED_BACKEND),
            (configuration.permission_rules, _UNRESOLVED_PERMISSIONS),
        )
        if resolution is not None and resolution.unresolved
    ]
    findings.extend(
        _unresolved(path, route.line, _unresolved_route_message(route.path))
        for route in configuration.opaque_routes
    )
    return findings


def _configuration_findings(
    path: str, configuration: host_config.AgentConfiguration
) -> list[Finding]:
    """Both Rules over one ``create_deep_agent(...)`` call.

    The boundary is reported first because it is what the verdict falls back to:
    :func:`skillspector.deepagents.writability.assess` returns nothing for a
    configuration whose Skill list, backend or permission rules did not resolve,
    so the two Rules partition the call rather than overlapping on it. A rule
    written in a shape the verdict cannot read is the same partition seen from
    the other side -- it lands on the boundary, and this is where it is spelled.
    """
    findings = _boundary_findings(path, configuration)
    assessment = writability.assess(configuration)
    findings.extend(
        _unresolved(path, line, _UNREADABLE_PERMISSION_RULE)
        for line in assessment.unreadable_rule_lines
    )
    findings.extend(
        _finding(
            _WRITABLE_RULE_ID,
            _WRITABLE_MITIGATED_SEVERITY if writable.mitigated else _WRITABLE_SEVERITY,
            _WRITABLE_CONFIDENCE,
            path,
            writable.line,
            _writable_message(writable.path, writable.mitigated),
        )
        for writable in assessment.writable
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
        findings = [
            finding
            for configuration in host_config.find_agent_configurations(tree)
            for finding in _configuration_findings(path, configuration)
        ]
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
