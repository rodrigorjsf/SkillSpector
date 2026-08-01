# What the behavior gate does not cover

The Behavior Snapshot is a committed, canonical projection of one Scan, compared by a blocking test
so that a change to existing behavior surfaces as a reviewable file diff. What it projects is
specified by [ADR 0003](../../docs/adr/0003-behavior-snapshot-projection.md) and measured in
[the #6 findings](../../docs/behavior-snapshot-projection-findings.md).

This file records the other side: what a green gate does **not** prove. Every limit below is
accepted deliberately. A limit that stops being acceptable is closed by widening the projection and
regenerating every snapshot — not by filtering something quietly.

## Corpus

- **One fixture.** `malicious_skill` only. It exercises the most projected surface in a single target
  — 6 Findings, `has_executable_scripts` true, a populated Manifest, a CRITICAL Risk Score of 93 —
  and it is the one fixture measured to contain a colliding named sort key, so it is what keeps the
  tie-breaker covered. Issue #8 grows the corpus to the 24 leaf scan targets. Until then a behavior
  change that touches no rule `malicious_skill` triggers passes the gate unseen.
- **The three fixture family parents (`sdi/`, `sqp/`, `ssd/`) are out of the corpus** and will stay
  out: they are fixture-layout containers, not Skills.

## State the projection excludes

Four state keys are outside the projection, each for a stated reason: `model_config` (environment
dependent), `report_body` (wall clock plus absolute path), `skill_path` and `temp_dir_for_cleanup`
(absolute paths). Their behavior is therefore unguarded here:

- **Report rendering is unguarded.** `report_body` is where the Markdown and JSON report text is
  produced. A change to phrasing, section order, or the JSON report shape does not move the snapshot.
- **Input resolution is unguarded.** `skill_path` and `temp_dir_for_cleanup` are what `resolve_input`
  produces for a git URL, a zip, or a single file. The gate only ever scans a local directory.
- **Model selection is unguarded**, by construction. That is the point of excluding it, and the test
  suite demonstrates the exclusion by projecting identically under two provider settings.

State keys outside the nine-key allow-list are likewise unguarded, notably `inspection_ledger`,
`analyzer_status_events`, `effective_finding_ids`, `filtered_findings`, `file_cache`, and
`llm_call_log`. `analysis_completeness` is projected, so an Analyzer's *status* is guarded even
though the ledger row behind it is not — that is what gives
[ADR 0002](../../docs/adr/0002-gated-analyzers-decline-silently.md) its teeth.

`filtered_findings` was measured byte-identical to `findings` in all 24 fixtures, because no fixture
exercises suppression. Suppression and baselines are entirely outside the gate.

## Fields stripped from inside the projection

- **`findings[].finding_id`** — a `uuid4()`, dropped rather than normalized. Nothing that consumes
  the identifier is inside the projection, so identifier *linkage* between a Finding, the ledger and
  SARIF is unguarded.
- **`sarif_report..tool.driver.version`** — a release bump is not a behavior change. A regression that
  emitted the *wrong* version, or none, would not be caught here.

## The LLM path

The Scan is driven with `use_llm=False`, pinned in code rather than read from the environment. Every
LLM-backed Analyzer therefore declines, and **no semantic finding is covered by the gate at all**.
The snapshot records that decline — `analysis_completeness.limitations` carries the
"Analyzer was disabled by the requested configuration" entries — so a change to *how* an Analyzer
declines is caught, while a change to what it would have found is not.

## Shape choices worth knowing when reading a diff

- A Finding is projected via `dataclasses.asdict`, not `Finding.to_dict`. `asdict` carries the full
  dataclass — including `message`, which the §4 named sort key needs and `to_dict` does not emit.
  Line counts therefore do not match the `to_dict`-shaped tables in the #6 findings document.
- A projected key absent from the returned state is absent from the snapshot rather than recorded as
  `null`. A key that stops being emitted is a behavior change and shows as a diff either way.
- **Two registered sort keys are unexercised.** `analysis_completeness.ledger_exceptions` and
  `scope_exclusions` are both empty for `malicious_skill`, so their named key has never ordered
  anything. Its shape was checked against `InspectionLedgerException`
  (`src/skillspector/inspection_ledger.py`) rather than against data — every field it reads is a
  `str` or an `int | None`. #8 is the first corpus that can populate them.
- **The gate costs three interpreter spawns plus four in-process `graph.invoke` calls**, about five
  seconds of `make test-unit` for one fixture. Three of those runs are the out-of-process
  determinism checks, which do not need repeating per fixture; #8 should scale the per-fixture part
  only.
- Every list is sorted, including nested lists with no named key registered; those fall back to the
  canonical serialization alone, which is total. So **list order is never guarded** — a change that
  only reorders a list is invisible here. #6 measured order to be stable anyway; the sort exists so
  that an incidentally-stable order can never become a flaky suite.
