# What the Behavior Snapshot projects

Status: accepted

A Behavior Snapshot is a committed, canonical projection of one Scan, compared by a blocking test so
that a change to existing behavior surfaces as a reviewable file diff. What it projects *is* the
project's working definition of observable behavior, so the choice is worth recording: once 24
snapshots are committed, changing the projection means regenerating all of them and losing the
ability to say whether a diff was behavior or reformatting.

The projection is taken from the state `graph.invoke` returns — never from rendered report text,
which injects the wall clock and the absolute input path.

**Ten state keys are projected:** `findings`, `risk_score`, `risk_severity`, `risk_recommendation`,
`component_metadata`, `has_executable_scripts`, `manifest`, `manifest_status`,
`analysis_completeness`, `sarif_report`.

**One of them is carried conditionally.** `manifest_status` (issue #11) is dropped from the
projection when it holds `present`, so a Skill that declares a Manifest keeps the snapshot it had
before the status existed. The alternative — projecting it unconditionally — would have regenerated
all 24 snapshots for a change that alters nothing about 23 of them, and destroyed the evidence that
the change was additive. The omission is not a hole in the gate: a Skill whose Manifest regressed to
any other status *gains* the key, and the byte-compare fails on its appearance. The rule lives in
`OMITTED_WHEN` in `tests/behavior/projection.py`, keyed by state key and by the one value it drops,
and `test_the_conditionally_carried_key_is_carried_by_some_fixture_and_not_others` holds it
non-vacuous — one fixture must carry the key and another must not.

**Four are excluded, each for a stated reason:** `model_config` is derived from environment variables
and would make a snapshot machine-specific; `report_body` carries both the timestamp and the absolute
path; `skill_path` is an absolute path; `temp_dir_for_cleanup` likewise.

**Two fields are stripped from inside the projection.** `findings[].finding_id` is a fresh `uuid4()`
per Finding (`src/skillspector/models.py:65`) and is therefore the only source of nondeterminism
measured anywhere in state. `sarif_report.runs[].tool.driver.version` is the scanner version, and a
release bump is not a behavior change. SARIF's `results[].properties.findingId` goes with the first.

**Every list is sorted by a named key plus the element's full canonical serialization** as the final
tie-breaker. The named part keeps the golden file grouped by file and line, which is how a reviewer
reads a security diff. The serialization makes the order total: distinct elements always separate,
and elements that are identical in full are interchangeable and cannot produce a diff.

## Considered Options

**Normalizing `finding_id` to ordinals** rather than dropping it. This was prototyped and measured to
work — rewriting `finding-<hex>` to `finding-000`, `finding-001`… after the sort produced projections
byte-identical across 27 targets, two processes, and two `PYTHONHASHSEED` values. It was rejected
because the projection references the identifier nowhere else: `effective_finding_ids` and
`inspection_ledger` are outside the projection, and SARIF's copy is stripped. Normalization would be
machinery preserving links that no longer exist, and it forces a sort→normalize ordering rule
(the sort key must never include the field being normalized) that is easy to get wrong later.
Dropping the field removes the nondeterminism by construction instead. If the projection ever grows
to include the Ledger, this decision is revisited — not worked around.

**Excluding `sarif_report`**, which is what issue #4 originally specified. Its stated reason —
that SARIF "reintroduces the timestamp" — was checked against a real Scan and is false: SARIF in
state carries no clock and no absolute path. The real costs are that it is largely derived from
`findings`, and that it adds roughly 3 200 lines across the corpus. Against that, the Finding→SARIF
mapping — level, properties, the rules table — is live logic, SARIF is the artifact consumers
actually receive, and #8 had already written down "SARIF report shape is unguarded" as an accepted
coverage limit. Closing a self-inflicted hole for 3 200 lines was judged worth it.

**Sorting by canonical serialization alone**, with no named key. Total by construction and free of
per-list maintenance, but it orders elements by whichever field sorts first alphabetically —
`category` before `file` — so the committed snapshot loses semantic grouping and the diff becomes
harder to judge. **Named fields alone** was also rejected: the natural key
`(file, start_line, end_line, rule_id, message)` was measured to collide in `malicious_skill`, where
two Findings share every one of those fields.

## Consequences

Issue #4's *Projection contents* and *Stated coverage limits* are superseded by this record on two
points: SARIF is in, and its accepted coverage limit is withdrawn. Its exclusion of "the scanner
version string" is narrowed to exactly one field, since `tool.driver.version` is the only place in
state where a version appears.

Including `analysis_completeness` is what gives ADR 0002 teeth. That decision — a gated Analyzer
declines silently — has no enforcement of its own; `analyzer_statuses` lives inside
`analysis_completeness`, so an Analyzer that emits a status event out of habit changes every
fixture's snapshot and fails the build.

The projection has no clock, no path, and no random value in it, so a snapshot mismatch always means
a real change. That is the property the gate depends on, and it is why every exclusion above carries
its reason rather than being filtered quietly.

Measurements behind all of this are in `docs/behavior-snapshot-projection-findings.md`.
