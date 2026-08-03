"""PROTOTYPE -- throwaway. Drives the LangChain4j Analyzer over a scenario matrix.

The question this answers is written in ``README.md``. In one line: *which Rules
actually fire on a LangChain4j Tool mode application, so the fixture issue #53
commits is chosen from measurement rather than guessed?*

Two tiers, because #53 asks two different questions and one driver cannot answer
both.

* :func:`drive` -- the **fast tier**. Calls ``framework_langchain4j.node`` over a
  synthetic ``file_cache``, so a scenario costs a parse rather than a Scan. This
  is what the matrix is built from.
* :func:`full_scan` -- the **full tier**. Materializes a tree and calls
  ``tests.behavior.projection.scan``, the same function ``make update-snapshots``
  calls. Only the chosen candidate goes through it, because "benign classes whose
  silence the snapshot pins" is a claim about the *whole* snapshot: the static
  pattern Analyzers run over Java sources too, and a class the LangChain4j
  Analyzer is silent about can still trip one of them.

Nothing here prints. ``drive.py`` is the shell.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Scenario:
    """One case in the matrix.

    ``expected`` is what I predicted *before* running the case. It is written
    down so a disagreement between prediction and measurement is visible in the
    output rather than rationalized away while reading it -- that disagreement is
    the only thing a prototype is for.
    """

    name: str
    asks: str
    expected: tuple[str, ...]
    files: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Fired:
    """One Finding the Analyzer emitted, reduced to what the matrix compares."""

    rule_id: str
    path: str
    line: int
    message: str


@dataclass(frozen=True)
class Outcome:
    """What the Analyzer did with one scenario."""

    status: str
    reason: str | None
    planned_work: int
    fired: tuple[Fired, ...]

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """The distinct Rules that fired, in first-seen order."""
        seen: list[str] = []
        for finding in self.fired:
            if finding.rule_id not in seen:
                seen.append(finding.rule_id)
        return tuple(seen)


def drive(scenario: Scenario) -> Outcome:
    """Run the LangChain4j Analyzer over one scenario's files.

    The Framework is set rather than detected: detection is a separate predicate
    and it was verified independently (a ``pom.xml`` declaring only
    ``dev.langchain4j:langchain4j-skills`` detects as ``langchain4j``). Forcing it
    here keeps a scenario free to carry a single Java file with no build file at
    all, which is a case the matrix needs.
    """
    from skillspector.framework import Framework
    from skillspector.nodes.analyzers import framework_langchain4j

    response: dict[str, Any] = framework_langchain4j.node(
        {
            "framework": Framework.LANGCHAIN4J,
            "file_cache": dict(scenario.files),
            "components": sorted(scenario.files),
        }
    )

    events = response.get("analyzer_status_events") or []
    event = events[0] if events else {}
    return Outcome(
        status=event.get("status", "<no status event>"),
        reason=event.get("reason_code"),
        planned_work=len(event.get("planned_work") or []),
        fired=tuple(
            Fired(
                rule_id=finding.rule_id,
                path=finding.file or "",
                line=finding.start_line or 0,
                message=finding.message,
            )
            for finding in response.get("findings", [])
        ),
    )


def full_scan(files: dict[str, str]) -> dict[str, Any]:
    """Materialize *files* as a tree and return its Behavior Snapshot projection.

    This is the output shape that would be committed under
    ``tests/behavior/snapshots/`` if these files became a fixture, produced by the
    same code path ``make update-snapshots`` runs.
    """
    from tests.behavior.projection import scan

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for relative, source in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            # newline="" keeps the fixture bytes the scan sees identical to the
            # bytes committed: the corpus enforces Unix line endings.
            target.write_text(source, encoding="utf-8", newline="")
        return scan(root)


def analyzer_status(projection: dict[str, Any], analyzer_id: str) -> dict[str, Any] | None:
    """One Analyzer's row out of a projection's completeness block."""
    for status in projection["analysis_completeness"]["analyzer_statuses"]:
        if status["analyzer_id"] == analyzer_id:
            return status
    return None
