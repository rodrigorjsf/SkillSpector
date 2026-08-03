"""PROTOTYPE -- throwaway. Prints what the LangChain4j Analyzer fires, per case.

    sspy prototypes/langchain4j_tool_mode/drive.py            # the matrix
    sspy prototypes/langchain4j_tool_mode/drive.py --candidate # the chosen fixture, full Scan

Batch, not interactive: issue #53 asks the prototype to *print* what fires per
case, and there is no state to drive by hand -- the value is reading the whole
matrix side by side, once.

A row marked SURPRISE is one where the Rules that fired disagree with what
``Scenario.expected`` predicted before the run. Those rows are the output.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The prototype imports both `skillspector` and `tests.behavior.projection`, so
# the repository root has to be on the path however this file is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from prototypes.langchain4j_tool_mode.matrix import (  # noqa: E402
    Outcome,
    Scenario,
    analyzer_status,
    drive,
    full_scan,
)
from prototypes.langchain4j_tool_mode.scenarios import SCENARIOS  # noqa: E402

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RESET = "\x1b[0m"

ANALYZER_ID = "framework_langchain4j"

# The Rules whose ids the matrix reports on their own. Anything else that fires
# came out of the content Analyzers, through resolved Skill content.
L4J_RULES = ("L4J-SHELL", "L4J-UNRESOLVED", "L4J-TOOL-DESC", "L4J-MCP-FILTER", "L4J-WORKDIR")


def _fired_summary(outcome: Outcome) -> str:
    own = [rule for rule in outcome.rule_ids if rule in L4J_RULES]
    borrowed = [rule for rule in outcome.rule_ids if rule not in L4J_RULES]
    parts = list(own)
    if borrowed:
        parts.append(f"+{len(borrowed)} content ({', '.join(borrowed)})")
    return ", ".join(parts) if parts else f"{DIM}-- silent --{RESET}"


def _is_surprise(scenario: Scenario, outcome: Outcome) -> bool:
    """Whether the measurement disagrees with the prediction written beforehand.

    Only the Rule ids this Analyzer owns are compared. A prediction phrased as
    prose -- "static pattern Findings", "status not_applicable" -- is checked by
    reading the detail block, not here.
    """
    # Matched by containment, not equality: a prediction is free to be a
    # sentence ("L4J-MCP-FILTER: a false positive if upstream renames it") and
    # still be the same claim about which Rule fires.
    predicted = {rule for rule in L4J_RULES if any(rule in item for item in scenario.expected)}
    fired = {rule for rule in outcome.rule_ids if rule in L4J_RULES}
    if predicted != fired:
        return True
    if any(item.startswith("status ") for item in scenario.expected):
        return outcome.status != scenario.expected[0].removeprefix("status ")
    return outcome.status != "completed"


def print_matrix() -> list[tuple[Scenario, Outcome]]:
    results = [(scenario, drive(scenario)) for scenario in SCENARIOS]

    width = max(len(scenario.name) for scenario in SCENARIOS)
    print(f"\n{BOLD}LangChain4j Analyzer -- what fires, per case{RESET}")
    print(f"{DIM}{len(SCENARIOS)} scenarios, driven through framework_langchain4j.node{RESET}\n")
    print(f"{BOLD}{'scenario'.ljust(width)}  {'status'.ljust(15)}  fired{RESET}")
    print(DIM + "-" * (width + 40) + RESET)

    for scenario, outcome in results:
        mark = f"{RED}!{RESET}" if _is_surprise(scenario, outcome) else " "
        print(
            f"{mark}{scenario.name.ljust(width)}  {outcome.status.ljust(15)}  "
            f"{_fired_summary(outcome)}"
        )

    print(f"\n{BOLD}Detail{RESET}\n")
    for scenario, outcome in results:
        surprised = _is_surprise(scenario, outcome)
        head = f"{RED}SURPRISE{RESET}" if surprised else f"{GREEN}as predicted{RESET}"
        print(f"{BOLD}{scenario.name}{RESET}  [{head}]")
        print(f"  {DIM}asks     {RESET} {scenario.asks}")
        print(f"  {DIM}predicted{RESET} {', '.join(scenario.expected) or 'silence'}")
        print(
            f"  {DIM}status   {RESET} {outcome.status}"
            + (f" ({outcome.reason})" if outcome.reason else "")
            + f", planned work {outcome.planned_work}"
        )
        if not outcome.fired:
            print(f"  {DIM}fired    {RESET} nothing")
        for finding in outcome.fired:
            own = finding.rule_id in L4J_RULES
            colour = "" if own else DIM
            print(
                f"  {colour}fired    {RESET} {colour}{finding.rule_id}{RESET} "
                f"{DIM}{finding.path}:{finding.line}{RESET}"
            )
            print(f"           {DIM}{finding.message[:110]}{RESET}")
        print()

    surprises = [scenario.name for scenario, outcome in results if _is_surprise(scenario, outcome)]
    if surprises:
        print(f"{RED}{BOLD}{len(surprises)} surprise(s):{RESET} {', '.join(surprises)}\n")
    else:
        print(f"{GREEN}Every case matched its prediction.{RESET}\n")
    return results


def print_candidate() -> None:
    """Full-tier: the chosen fixture, scanned exactly as the snapshot gate scans it."""
    from prototypes.langchain4j_tool_mode.candidate import CANDIDATE

    print(f"\n{BOLD}Candidate fixture -- full Scan{RESET}")
    print(
        f"{DIM}tests.behavior.projection.scan, the same call make update-snapshots makes{RESET}\n"
    )
    for path in sorted(CANDIDATE):
        print(f"  {DIM}{path}{RESET}")

    projection = full_scan(CANDIDATE)
    status = analyzer_status(projection, ANALYZER_ID)

    print(f"\n{BOLD}What the committed snapshot would assert{RESET}")
    print(f"  framework             {projection['framework']}")
    print(f"  has_executable_scripts {projection['has_executable_scripts']}")
    print(f"  manifest_status       {projection['manifest_status']}")
    print(f"  risk_score            {projection['risk_score']}")
    print(f"  risk_severity         {projection['risk_severity']}")
    print(f"  {ANALYZER_ID}:")
    print(f"    status              {status['status'] if status else '<absent>'}")
    print(f"    planned_work        {status['planned_work'] if status else '-'}")
    print(f"    completed           {status['completed'] if status else '-'}")
    print(f"    unaccounted         {status['unaccounted'] if status else '-'}")

    print(f"\n{BOLD}Every Finding the snapshot would pin{RESET}")
    for finding in projection["findings"]:
        print(
            f"  {finding.get('rule_id')}  {DIM}{finding.get('file')}:"
            f"{finding.get('start_line')}{RESET}  {finding.get('severity')}"
        )

    print(f"\n{BOLD}Every Analyzer that ran on this tree{RESET}")
    for row in projection["analysis_completeness"]["analyzer_statuses"]:
        if row["status"] in ("completed",) or row["completed"]:
            print(
                f"  {row['analyzer_id'].ljust(32)} {row['status']}  "
                f"{DIM}planned {row['planned_work']}, completed {row['completed']}{RESET}"
            )
    print()


def write_candidate(destination: Path) -> None:
    """Materialize the chosen fixture so its exact bytes can be read.

    The handoff to ``/implement``: the tree written here is what would land under
    ``tests/fixtures/langchain4j_tool_mode/``. Unix line endings, because the
    corpus is compared byte-exact.
    """
    from prototypes.langchain4j_tool_mode.candidate import CANDIDATE

    for relative, source in sorted(CANDIDATE.items()):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8", newline="")
        print(f"wrote {target}")


def main(argv: list[str]) -> int:
    if "--candidate" in argv:
        print_candidate()
    elif "--write" in argv:
        write_candidate(Path(argv[argv.index("--write") + 1]))
    else:
        print_matrix()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
