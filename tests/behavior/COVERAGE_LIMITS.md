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

- **All 26 leaf scan targets**, one committed snapshot each, laid out to mirror `tests/fixtures/`
  (`snapshots/sdi/sdi1_mismatch.json`). Measured at 11 079 lines across the original 24, 323–859 per
  fixture. 23 of the 26 bear a `SKILL.md`; `mcp_registry` bears none and is in the corpus anyway,
  because it is a scan target in practice, and the two `*_detection` fixtures (#21) bear none because
  they carry one Framework signal and nothing else.
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
  `analysis_completeness.scope_exclusions` is empty in all 26 and a change to the skip set cannot
  move any snapshot. A test asserts the emptiness, so the day a fixture populates it, this limit is
  revisited rather than quietly becoming false.
- **Suppression is unguarded.** `suppressed_findings` is empty in every fixture and
  `filtered_findings` is byte-identical to `findings` throughout, so no fixture exercises a Baseline.
- **The anonymous-Skill failure mode is reported, not resolved.** `mcp_registry`'s snapshot records a
  directory with no `SKILL.md` scanning as one Skill with an empty Manifest and a Risk Score of 0.
  #11 landed as a visible diff on exactly that snapshot: the Scan now also reports
  `manifest_status: absent`, so the report says *why* the Manifest is empty. The Scan still returns a
  scored verdict for a directory that is not a Skill — changing that was explicitly out of #11's
  scope, and no fixture guards it.
- **`manifest_status` is guarded in one direction only.** It is one of the two projected keys carried
  conditionally: dropped when it holds `present` (ADR 0003), so 23 of the 26 snapshots carry no
  `manifest_status` byte at all. A Skill whose Manifest regressed to any other status still fails the
  byte compare, because the key would appear. The reverse — `mcp_registry` reverting to `present` —
  is caught by its own snapshot, and by nothing else. A test holds the rule non-vacuous by requiring
  that some fixture carry the key and some fixture not.
- **`framework` is guarded the same way, and by design carries nothing today.** Detection (#21) is
  the second conditionally carried key, dropped when it holds `agent_skills`, which is what every
  input scanned before detection existed detects as. Only the two `*_detection` fixtures carry the
  key, so the rule stays non-vacuous — but no fixture exercises a Framework *Analyzer*, because none
  exists yet. What is guarded is that a pre-existing input must never start detecting as another
  Framework: the key would appear in its snapshot and the byte compare would fail.
- **SARIF is no longer a coverage limit.** It was previously listed here as unguarded on the grounds
  that it is derived and reintroduces the timestamp; the timestamp claim was measured false, and
  `sarif_report` is in the projection minus `tool.driver.version` (ADR 0003).

## State the projection excludes

Four state keys are outside the projection, each for a stated reason: `model_config` (environment
dependent), `report_body` (wall clock plus absolute path), `skill_path` and `temp_dir_for_cleanup`
(absolute paths). Their behavior is therefore unguarded here:

- **Report rendering is unguarded.** `report_body` is where the Markdown and JSON report text is
  produced. A change to phrasing, section order, or the JSON report shape does not move the snapshot.
  This limit became load-bearing with #11: the Manifest status reaches a reader only through
  `report_body` — `skill.manifest_status` in the JSON report and the `Manifest:` line in the terminal
  and Markdown ones — so none of that rendering is behind the gate. `tests/nodes/test_manifest_status`
  covers it instead.
- **Input resolution is unguarded.** `skill_path` and `temp_dir_for_cleanup` are what `resolve_input`
  produces for a git URL, a zip, or a single file. The gate only ever scans a local directory.
- **Model selection is unguarded**, by construction. That is the point of excluding it, and the test
  suite demonstrates the exclusion by projecting identically under two provider settings.

State keys outside the ten-key allow-list are likewise unguarded, notably `inspection_ledger`,
`analyzer_status_events`, `effective_finding_ids`, `filtered_findings`, `file_cache`, and
`llm_call_log`. `analysis_completeness` is projected, so an Analyzer's *status* is guarded even
though the ledger row behind it is not — that is what gives
[ADR 0002](../../docs/adr/0002-gated-analyzers-decline-silently.md) its teeth.

`filtered_findings` was measured byte-identical to `findings` in every fixture, because no fixture
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
  `scope_exclusions` are empty in **all 26** fixtures, not just in `malicious_skill`, so their named
  key has still never ordered anything. Widening the corpus did not close this. Its shape was
  checked against `InspectionLedgerException` (`src/skillspector/inspection_ledger.py`) rather than
  against data — every field it reads is a `str` or an `int | None`.
- **The gate costs three interpreter spawns plus 53 in-process `graph.invoke` calls** — two per
  fixture, for the gate itself and the consecutive-run check, plus one on `malicious_skill` for the
  pre-strip control — for about eight seconds of `make test-unit`. The out-of-process checks did **not**
  scale with the corpus: `regenerate.py --emit-all` projects the whole corpus per spawn, so three
  child interpreters cover 26 fixtures against two hash seeds and two providers.
- **A fixture's line endings are part of the frozen behavior.** The projection carries each
  component's `size_bytes`, so a checkout that rewrites `\n` to `\r\n` inflates every recorded size
  by one byte per line. `tests/fixtures/.gitattributes` pins the corpus to LF for exactly this
  reason. Without it the gate passes on a CRLF development checkout and fails every fixture in
  continuous integration — the state #9 found on the first real workflow run. Any fixture added
  outside `tests/fixtures/` needs its own pin.
- Every list is sorted, including nested lists with no named key registered; those fall back to the
  canonical serialization alone, which is total. So **list order is never guarded** — a change that
  only reorders a list is invisible here. #6 measured order to be stable anyway; the sort exists so
  that an incidentally-stable order can never become a flaky suite.
