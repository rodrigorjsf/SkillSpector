# Behavior-snapshot projection: measured findings

**Issue:** #6 (prototype spike under #4) · **Date:** 2026-08-01 · **Status:** measurement complete

This records what a Scan's graph-state projection actually looks like when executed, so that #7
designs the snapshot test against evidence rather than expectation. No production code was changed;
the probe scripts are throwaway and are not committed.

**Note on the corpus unit.** Earlier planning counted the corpus as **11 top-level directories** under
`tests/fixtures/`. That is not the scan unit: `sdi/`, `sqp/`, and `ssd/` are families whose skills live
one level down. Counting skills, there are **23 directories bearing a `SKILL.md`**, plus
`mcp_registry/` which bears none — **24 leaf scan targets**. The three family parents were additionally
scanned as targets in their own right (§7), for **27 total**. Sizes in §5 are for the 24 leaves.

**Decided:** the corpus for the gate is the **24 leaves**. The three family parents stay out — they
are fixture-layout containers, not Skills. #8 inherits 24, not 11.

---

## 1. Toolchain — the commands that worked

```bash
uv venv .venv          # selected CPython 3.13.13, NOT the ambient 3.14.6
uv sync --all-extras   # == `make install-dev`; installs the project plus dev extras
.venv/bin/python -m pytest -m "not integration and not provider" tests/
```

- `pyproject.toml:11` pins `requires-python = ">=3.12,<3.15"`. The ambient interpreter is 3.14.6,
  which satisfies that range, but `uv venv` selected 3.13.13 on its own. No pin was needed.
- **Result of the first test run in this fork's life:** `1704 passed, 12 skipped, 34 deselected,
  4 xfailed` in 97s. Three `PytestUnknownMarkWarning` for `pytest.mark.timeout`
  (`tests/nodes/analyzers/test_mp2_regex_backtracking.py:71,84,97`) — the marker is not registered
  in `pyproject.toml` and `pytest-timeout` is absent, so those three timeouts do not apply. Pre-existing,
  unrelated to this spike, not fixed here.
- Shell note: this environment is fish and shell state does not persist between tool calls. Invoke
  `.venv/bin/python` by absolute path rather than relying on `activate`.

## 2. Credential-free execution — answered, yes

Every measurement below ran under `env -i` (an **empty** environment except `PATH` and `HOME`), so no
API key of any kind was reachable. The ambient environment was also checked first and carried no
`*_API_KEY`, no provider variable, and no `SKILLSPECTOR_*` variable.

- `import skillspector` succeeds.
- All 27 scan targets complete through `graph.invoke(..., use_llm=False)`; zero exceptions.
- `skillspector.constants` import-time validation raises only under
  `SKILLSPECTOR_STRICT_MODEL_VALIDATION=true`, which was never set. Confirmed by execution, not
  by reading.

## 3. Determinism — one source of variance, and it is not ordering

Each fixture was scanned twice in one process, and the whole suite was additionally re-run in a
**second process** under `PYTHONHASHSEED=1` (vs `0`) to expose any set-derived ordering that a
same-process comparison structurally cannot see.

**Raw comparison — five state keys differ, in 14 of 24 fixtures** (the 14 that produce at least one
Finding): `findings`, `filtered_findings`, `effective_finding_ids`, `inspection_ledger`,
`sarif_report`. Identical results intra-process and cross-process.

**Cause — `finding_id` is a fresh `uuid4()` per Finding.** `src/skillspector/models.py:65-67`:

```python
def _new_finding_id() -> str:
    """Return an opaque, run-unique identity for one logical finding."""
    return f"finding-{uuid4().hex}"
```

The identifier is *documented* as run-unique. It is not derived from content, so it changes every run
by design.

**After normalizing those identifiers, every projection is byte-identical** — all 24 fixtures, both
intra-process and cross-process, `PYTHONHASHSEED` 0 vs 1:

> All identical after normalization: True (failures: [])

Normalization used: rewrite each `finding-<32 hex>` to `finding-NNN`, numbered by order of first
appearance. That preserves the referential links between a Finding and the ledger/SARIF entries that
cite it, which a blanket redaction would destroy.

**The pipeline is sort → normalize, in that order, and it was verified in that order.** Sorting
changes which Finding appears first, so ordinals assigned before sorting would not survive it. The
sort key is therefore computed on pre-normalization data and must never include `finding_id` — that
would sort by the very thing being normalized away. Re-running the whole equivalence test as
sort-then-normalize, with the §4 keys applied, over all **27 targets × 2 processes × 2 runs**:

> identical after sort+normalize: True (failures: [])

**List order was never a source of variance.** `rule_id` sequences, `analyzer_status_events` order,
and SARIF `results` order were identical across every pair compared. Concurrency in the analyzer
fan-out does not leak into state ordering.

### The five paths that carry a run-unique identifier

```
$.findings[].finding_id
$.filtered_findings[].finding_id
$.effective_finding_ids[]
$.inspection_ledger[].emitted_finding_ids[]
$.sarif_report.runs[].results[].properties.findingId
```

`$.inspection_ledger[].input_finding_ids` exists in the model but was empty in every fixture; it
holds the same identifier type and must be normalized too.

### Machine-specific strings

Serialized every state key and searched for the repo root and `/home/`. Only two keys leak the host
path, and both are already excluded: `report_body` and `skill_path`. Nothing else in state embeds an
absolute path — finding `file` values and SARIF `physicalLocation` URIs are all skill-relative.

## 4. Proposed canonical sort — required even though order proved stable

Relying on an incidentally-stable order is how a suite becomes flaky a year later. Every list in the
projection gets an explicit key. Sorts must be **total** (ties broken to a unique key) or they
reintroduce the nondeterminism they exist to remove.

| Path | Max len | Sort key |
|---|---|---|
| `$.findings`, `$.filtered_findings` | 9 | `(file, start_line, end_line, rule_id, message)` |
| `$.findings[].tags` | 2 | the string |
| `$.effective_finding_ids` | 9 | normalized ordinal — i.e. sorted by the referenced Finding's key above |
| `$.inspection_ledger` | 35 | `(phase, analyzer_id, record_type, path, start_line, end_line, work_id)` |
| `$.inspection_ledger[].emitted_finding_ids` | 5 | normalized ordinal |
| `$.analyzer_status_events` | 24 | `(analyzer_id, status, message)` |
| `$.analyzer_status_events[].planned_work` | 2 | `(path, start_line, end_line, work_id)` |
| `$.analysis_completeness.analyzer_statuses` | 24 | `analyzer_id` |
| `$.analysis_completeness.limitations` | 4 | the string — **note duplicates**, see below |
| `$.components` | 2 | the string (already sorted by the producer) |
| `$.component_metadata` | 2 | `path` |
| `$.manifest.permissions`, `$.manifest.triggers` | 5 / 3 | the string |
| `$.manifest.parameters` | 1 | `name` |
| `$.sarif_report.runs[].results` | 9 | same key as `$.findings` |
| `$.sarif_report.runs[].results[].properties.tags` | 2 | the string |
| `$.sarif_report.runs[].tool.driver.rules` | 7 | `id` |
| `$.sarif_report.runs[].invocations[].toolExecutionNotifications` | 4 | `(level, message)` |

`limitations` contains repeated identical strings (`"Analyzer was disabled by the requested
configuration."` × 3 for a `use_llm=False` scan). Sort it, do not deduplicate — the count is
behavior.

### Totality of these keys — checked, not assumed

A sort key that ties leaves the tied elements in whatever order the producer emitted them, which is
exactly the nondeterminism the sort exists to remove. Every key above was checked for duplicates
across all 27 targets:

| Path | Verdict |
|---|---|
| `$.inspection_ledger` (maxlen 161) | unique |
| `$.analyzer_status_events` (maxlen 24) | unique |
| `$.analysis_completeness.analyzer_statuses` | unique |
| `$.component_metadata` | unique |
| `$.sarif_report..tool.driver.rules` | unique |
| `$.findings`, `$.filtered_findings` | **collides** — 2 duplicate keys in `malicious_skill` |
| `$.sarif_report..results` | **collides** — same two |
| `$.sarif_report..invocations[].toolExecutionNotifications` | **collides** — 2–3 per fixture, everywhere |

The findings collision is real: two Findings share
`("scripts/helper.py", 21, null, "E1", "External Transmission")` because the proposed key omits the
fields that distinguish them (`matched_text`, `code_snippet`, `confidence`, …).

**Resolution — append the element's full canonical serialization as the final tie-breaker**, with
`finding_id` (and SARIF's `properties.findingId`) excluded from that serialization. Verified: with
that tie-break, no two Findings and no two SARIF results are indistinguishable in any fixture, so
the key becomes total.

The `toolExecutionNotifications` collisions are a different case and need no fix: the tied elements
are **byte-identical in full** (2–3 exact duplicates of a 3–4 element list, in all 27 targets — the
repeated "Analyzer was disabled" notice). Interchangeable elements cannot produce a diff whichever
order they take.

## 5. Size

> **Correction.** This section originally measured *whole graph state minus four excluded keys* and
> concluded the projection was unreviewable. That is not the projection anyone proposed. Issue #4
> specifies an **allow-list** of state keys, which is far smaller. The measurement below is retained
> because it bounds the worst case and it is what the reduction analysis was run against, but the
> conclusion drawn from it was wrong and is retracted in §5.1. **The breadth decision is not
> reopened.**

### 5.0 Whole state minus exclusions — the upper bound, not the proposal

`json.dumps(projection, indent=2, sort_keys=True)`, identifiers normalized, after excluding
`model_config`, `report_body`, `skill_path`, and `temp_dir_for_cleanup`:

| Fixture | Lines | Bytes |
|---|---:|---:|
| mcp_poisoned_tool | 1904 | 68863 |
| mcp_underdeclared_skill | 1649 | 61237 |
| malicious_skill | 1638 | 59749 |
| mcp_mismatched_skill | 1556 | 52686 |
| mcp_overprivileged_skill | 1541 | 48387 |
| sdi2_inappropriate | 1476 | 50498 |
| sdi1_mismatch | 1467 | 50881 |
| sqp2_clean | 1396 | 46537 |
| sdi3_scope_creep | 1383 | 43617 |
| mcp_clean_skill | 1320 | 44310 |
| sdi_clean | 1314 | 43441 |
| sqp2_missing_warnings | 1309 | 42264 |
| sdi4_divergence | 1302 | 40221 |
| sqp3_clean | 1079 | 32916 |
| sqp3_locale_forcing | 1079 | 32442 |
| mcp_registry | 1057 | 34018 |
| ssd4_narrative_deception | 903 | 27369 |
| sqp1_clean | 804 | 23778 |
| safe_skill | 803 | 23444 |
| ssd1_semantic_injection | 803 | 23798 |
| ssd2_novel_phrasing | 803 | 23928 |
| ssd3_nl_exfiltration | 803 | 23879 |
| ssd_clean | 803 | 23758 |
| sqp1_vague_triggers | 800 | 23245 |
| **Total (24 leaves)** | **28992** | **945266** |

The three family parents, if ever scanned as targets, are far larger still — `sdi` alone is 4141
lines (156 KB), `sqp` 3630, `ssd` 1895. They are not part of the 24 and #8 should not add them; see §7.

Where the weight sits, for `mcp_poisoned_tool`:

| Key | Lines | Bytes |
|---|---:|---:|
| `sarif_report` | 389 | 14807 |
| `inspection_ledger` | 436 | 13218 |
| `findings` | 204 | 10000 |
| `filtered_findings` | 204 | 10000 |
| `analyzer_status_events` | 360 | 9940 |
| `analysis_completeness` | 246 | 5981 |
| `file_cache` | 4 | 703 |
| everything else | ~60 | ~1200 |

### Reduction candidates, measured

| Variant | Excludes | Corpus lines | Largest fixture |
|---|---|---:|---:|
| A — full state | — | 28992 | 1904 |
| B | `sarif_report` | 25689 | 1515 |
| C | `sarif_report`, `inspection_ledger`, `analyzer_status_events` | 9574 | 719 |
| D | C plus `analysis_completeness`, `filtered_findings`, `file_cache` | 2294 | 265 |

Two redundancies make part of this free:

- **`findings` and `filtered_findings` are byte-identical in all 24 fixtures.** No fixture exercises
  suppression (`suppressed_findings` is empty everywhere). Snapshotting both doubles the largest
  section to detect nothing. Recommend keeping `findings` and asserting `filtered_findings ==
  findings` structurally, so the day they diverge is a visible test failure rather than a silent
  doubling.
- **`file_cache` echoes fixture file contents into the snapshot.** It is a verbatim copy of files
  already in the repo next to the test. Recommend excluding it and asserting only its key set —
  which files were read is behavior; their contents are the fixture.

`sarif_report` is a projection of `findings` plus rule metadata, so it is largely derived. Excluding
it is defensible **only if** something else covers the SARIF mapping; it is the artifact consumers
actually receive.

### 5.1 The allow-list projection — what #4 actually specifies

Issue #4's *Projection contents* names eight state keys. Measured, identifiers normalized:

| Projection | Per fixture | Corpus (24) |
|---|---|---|
| #4 allow-list as written (8 keys) | 275–489 lines | 7 908 |
| **As decided — 9 keys, `finding_id` dropped, SARIF minus `tool.driver.version`** | **323–859 lines** | **11 079** |
| ~~Whole state minus 4 exclusions (§5.0)~~ | ~~800–1904~~ | ~~28 992~~ |

A 300–900 line JSON file with a semantic sort order is an ordinary golden file, and a behavior change
touches a handful of lines inside it. **User story 27 of #4 — "a snapshot small enough to read in a
pull request" — is satisfied by the specified projection.** The size question does not reopen the
breadth decision; it confirms it.

Where the second row's extra ~3 200 lines go: `sarif_report`, included by decision so that the
Finding→SARIF mapping is not left unguarded. See §6.

## 6. Decisions carried into #7

These were settled after this spike, in the session that reviewed it. Recorded in
`docs/adr/0003-behavior-snapshot-projection.md`; repeated here so the measurement and the decision it
produced sit together.

1. **Drop `finding_id` from the projection entirely** — do not normalize it. It is an opaque
   `uuid4()`, so it is not behavior, and in the allow-list it is referenced by nothing else:
   `effective_finding_ids`, `inspection_ledger`, and SARIF `properties.findingId` are all outside the
   projection or stripped. With the field gone the projection has no nondeterminism by construction,
   and the whole sort→normalize pipeline collapses to a sort. Ordinal normalization was measured to
   work (§3) and was rejected as machinery with nothing left to do.
2. **Include `sarif_report`, minus `tool.driver.version`** and minus `results[].properties.findingId`.
   The exclusion reason #4 gives — "reintroduces the timestamp" — is false: SARIF in state carries no
   clock and no absolute path. It carries the scanner version, which is the one field a release bump
   would churn, and stripping just that field closes a coverage limit #8 had accepted for a reason
   that no longer holds. Cost: +3 200 lines corpus-wide.
3. **Nine projected keys:** `findings`, `risk_score`, `risk_severity`, `risk_recommendation`,
   `component_metadata`, `has_executable_scripts`, `manifest`, `analysis_completeness`,
   `sarif_report`.
4. **Excluded, with reason:** `model_config` (environment-dependent), `report_body` (wall clock +
   absolute path), `skill_path` (absolute path), `temp_dir_for_cleanup` (absolute path).
   `file_cache` is outside the allow-list; had it been in, it would be excluded for echoing fixture
   file contents verbatim into the snapshot. `filtered_findings` is outside it too, and is byte-identical
   to `findings` in all 24 fixtures because no fixture exercises suppression.
5. **Sort every list** by a named key plus the element's full canonical serialization as the final
   tie-breaker — the named part keeps the golden file readable by file and line, the serialization
   makes the order total. Verified total in §4.
6. **The breadth decision stands.** It is not reopened. See the correction in §5.

## 7. Two facts discovered along the way

### Four fixture directories have no `SKILL.md` and scan as anonymous skills

`tests/fixtures/mcp_registry` bears no `SKILL.md`, and neither do the three family parents. Scanning
any of them does not fail:

| Target | `manifest` | components | findings | risk |
|---|---|---:|---:|---:|
| `mcp_registry` | `{}` | 2 | 0 | 0 |
| `sdi` | `{}` | 10 | 8 | 48 |
| `sqp` | `{}` | 10 | 3 | 48 |
| `ssd` | `{}` | 5 | 0 | 0 |

This is the same anonymous-skill failure mode already recorded for a Java repo in
`docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` §3.7, reproduced here on *existing* fixtures: a directory
with no skill manifest scans as one clean-manifest skill rather than reporting that there was nothing
to scan. `sdi` and `sqp` make it sharper — a manifest-less directory can still return a MEDIUM risk
score of 48 while claiming an empty manifest.

`mcp_registry` is one of the 24 and is snapshotted as-is: it is current behavior and the gate's job
is to hold it still. The three family parents are containers, not Skills, and stay out of the corpus.
The failure mode itself is tracked as its own issue — fixing it is a deliberate behavior change that
regenerates snapshots, which is exactly the workflow the gate exists to make visible.

### `tests/integration/` tests do **not** run in `make test-unit`

An earlier handoff asserted they do, on the grounds that those files carry no marker. They carry no
*inline* marker, but `tests/integration/conftest.py:21-24` applies one automatically:

```python
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
```

With `addopts = "-m 'not integration and not provider'"` (`pyproject.toml:112`) they are deselected —
confirmed by the `34 deselected` in §1.

**Consequence for #7:** the constraint is on the *path*, not the marker. The guard is a substring test
over the full file path, so a snapshot test must not have `integration` anywhere in its path. Placing
it under `tests/integration/` and leaving it unmarked produces a test that never runs.

---

## Reproduction

Throwaway scripts lived in the session scratchpad and are intentionally not committed. The method:
scan each target twice per process via `graph.invoke({"skill_path": ..., "output_format": "json",
"use_llm": False})`; coerce the returned state to JSON; drop the four excluded keys; sort every list
per §4; rewrite `finding-<hex>` to ordinals; compare with `json.dumps(..., indent=2,
sort_keys=True)`. Repeat the whole suite in a second process under a different `PYTHONHASHSEED` and
compare across processes. Totality was checked by counting duplicate sort keys per list per target.
