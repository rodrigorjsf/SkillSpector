# What the behavior gate does not cover

The Behavior Snapshot is a committed, canonical projection of one Scan, compared by a blocking test
so that a change to existing behavior surfaces as a reviewable file diff. What it projects is
specified by [ADR 0003](../../docs/adr/0003-behavior-snapshot-projection.md) and measured in
[the #6 findings](../../docs/behavior-snapshot-projection-findings.md).

This file records the other side: what a green gate does **not** prove. Every limit below is
accepted deliberately. A limit that stops being acceptable is closed by widening the projection and
regenerating every snapshot — not by filtering something quietly.

## What a green gate does prove — the demonstrated red

A gate that has never failed is evidence of nothing, and a perturbation chosen for convenience proves
only that the test *can* fail. The demonstration therefore used a change class the gate exists for:
removing `".py"` from `_EXECUTABLE_EXTENSIONS` (`src/skillspector/nodes/build_context.py:68`), one of
the two changes §3.4 of the design document defers as behavior-affecting.

One edit moved three projected surfaces — `has_executable_scripts`, `component_metadata[].executable`
and the Risk Score multiplier that depends on the flag — and failed **exactly the 13 fixtures** where
`has_executable_scripts` is true, in both the in-process and the out-of-process gate (26 failures,
208 passed). The other 11 stayed green. `malicious_skill` went 93 → 77 with 6 → 5 Findings;
`mcp_overprivileged_skill` went 12 → 0 with 5 → 0. The change was then reverted and the working tree
confirmed clean. Full per-fixture numbers are in the #8 close-out comment.

## Corpus

- **All 24 leaf scan targets**, one committed snapshot each, laid out to mirror `tests/fixtures/`
  (`snapshots/sdi/sdi1_mismatch.json`). Measured at 11 079 lines total, 323–859 per fixture. 23 of
  the 24 bear a `SKILL.md`; `mcp_registry` bears none and is in the corpus anyway, because it is a
  scan target in practice.
- **The three fixture family parents (`sdi/`, `sqp/`, `ssd/`) are out of the corpus** and will stay
  out: they are fixture-layout containers, not Skills. Scanned as targets they behave as anonymous
  Skills — `sdi` and `sqp` at Risk Score 48 with an empty Manifest (#11).
- The corpus is checked against the fixture tree on every run, so a fixture added without a snapshot
  fails rather than joining silently.
- **The gate proves preservation over this fixture corpus, not over arbitrary user input.** What the
  corpus does not contain, it cannot guard. It holds 23 markdown, 13 Python, 2 YAML and 2 JSON files
  and nothing else — notably **no JVM source file**, which means adding JVM extensions to the
  file-type map genuinely cannot change any existing fixture. §3.4 of the design document overstates
  the risk for those specific extensions.

## Change classes the corpus cannot see

- **Skip-directory changes are unguarded.** No fixture contains a skippable directory, so
  `analysis_completeness.scope_exclusions` is empty in all 24 and a change to the skip set cannot
  move any snapshot. A test asserts the emptiness, so the day a fixture populates it, this limit is
  revisited rather than quietly becoming false.
- **Suppression is unguarded.** `suppressed_findings` is empty in every fixture and
  `filtered_findings` is byte-identical to `findings` throughout, so no fixture exercises a Baseline.
- **The anonymous-Skill failure mode is frozen, not fixed.** `mcp_registry`'s snapshot records a
  directory with no `SKILL.md` scanning as one Skill with an empty Manifest and a Risk Score of 0.
  That is current behavior and the gate holds it still; #11 tracks changing it, and will land as a
  visible diff on this snapshot.
- **SARIF is no longer a coverage limit.** It was previously listed here as unguarded on the grounds
  that it is derived and reintroduces the timestamp; the timestamp claim was measured false, and
  `sarif_report` is in the projection minus `tool.driver.version` (ADR 0003).

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
- **Two registered sort keys are still unexercised.** `analysis_completeness.ledger_exceptions` and
  `scope_exclusions` are empty in **all 24** fixtures, not just in `malicious_skill`, so their named
  key has still never ordered anything. Widening the corpus did not close this. Its shape was
  checked against `InspectionLedgerException` (`src/skillspector/inspection_ledger.py`) rather than
  against data — every field it reads is a `str` or an `int | None`.
- **The gate costs three interpreter spawns plus 26 in-process `graph.invoke` calls** — one per
  fixture, plus two on `malicious_skill` for the consecutive-run and pre-strip checks — for about
  seven seconds of `make test-unit` across all 24. The out-of-process determinism checks did **not**
  scale with the corpus: `regenerate.py --emit-all` projects the whole corpus per spawn, so three
  child interpreters cover 24 fixtures against two hash seeds and two providers.
- Every list is sorted, including nested lists with no named key registered; those fall back to the
  canonical serialization alone, which is total. So **list order is never guarded** — a change that
  only reorders a list is invisible here. #6 measured order to be stable anyway; the sort exists so
  that an incidentally-stable order can never become a flaky suite.
