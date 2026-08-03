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

**No Rules today, deliberately.** Issue #70 built this Analyzer carrying nothing
so that the behavioral cost of a gated Framework Analyzer -- one status row in
one Behavior Snapshot -- is demonstrated in isolation, before any Finding makes
the diff hard to read. Issues #71 through #74 add the Rules ADR 0008 scoped:
a resolution boundary, one composed writability verdict per Skill source path,
Skill-name shadowing across sources, and a subagent defined without its own
skills. Opening a Component here therefore means reading it far enough to say it
was readable, and nothing more.

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

from skillspector.deepagents import signals
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
from skillspector.state import AnalyzerNodeResponse, SkillspectorState

ANALYZER_ID = "framework_deepagents"
logger = get_logger(__name__)

_PHASE = "static"


def _decline() -> AnalyzerNodeResponse:
    """Return the empty response a Framework-mismatched Analyzer declines with."""
    return {"findings": []}


def _open(path: str, source: str) -> InspectionLedgerEvent:
    """Open one applicable Component and record what came of it.

    A Python module is parsed, because that is what every Rule this Analyzer
    will carry needs and because a file that does not parse was not inspected
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
            ast.parse(source)
        except SyntaxError:
            return ledger_event(
                outcome=LedgerOutcome.SKIPPED,
                phase=_PHASE,
                analyzer_id=ANALYZER_ID,
                path=path,
                reason=LedgerReason.SYNTAX_ERROR,
            )
    return ledger_event(
        outcome=LedgerOutcome.COMPLETED,
        phase=_PHASE,
        analyzer_id=ANALYZER_ID,
        path=path,
        emitted_finding_ids=[],
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

    # Every file opened gets a row, whether or not it yielded a Finding -- and
    # in this slice none of them can. Once this Analyzer runs, an absence of
    # Findings must be distinguishable from an absence of inspection.
    #
    # Iterated over the same result the gate tested, never recomputed from
    # `file_cache`: two definitions of "applicable" a few lines apart are what
    # ADR 0006 exists to prevent recurring.
    events = [_open(path, source) for path, source in sorted(applicable.items())]

    # The status is derived from these events rather than written here.
    # `analyzer_status_for_events` owns the cascade, and `DEGRADED` -- which a
    # skipped file produces -- is reserved to it; see
    # `.claude/rules/analyzer-status.md`.
    logger.info("%s: opened %d components, 0 findings", ANALYZER_ID, len(events))
    return {
        "findings": [],
        "inspection_ledger": events,
        "analyzer_status_events": [analyzer_status_for_events(ANALYZER_ID, events)],
    }
