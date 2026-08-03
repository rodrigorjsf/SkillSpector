---
paths:
  - "src/skillspector/nodes/analyzers/*.py"
  - "src/skillspector/nodes/analyzers/**/*.py"
---

# Analyzer nodes

Full walkthrough: `docs/DEVELOPMENT.md` §9. Signatures and the registration facts that doc omits:

- A node is `node(state: SkillspectorState) -> AnalyzerNodeResponse`, returning `{"findings": list[Finding]}`.
- A static pattern module exposes `analyze(content: str, file_path: str, file_type: str) -> list[AnalyzerFinding]` and is driven by `static_runner.run_static_patterns`. Take category and remediation text from `pattern_defaults`.
- Registering means editing `nodes/analyzers/__init__.py` twice, in the same relative order: append the id to `ANALYZER_NODE_IDS` and add the matching key to `ANALYZER_NODES`. `graph.py` needs no change — its edges are generated from `ANALYZER_NODE_IDS` in a loop.
- Then update `EXPECTED_ANALYZER_NODE_IDS` in `tests/nodes/analyzers/test_registry.py`. It is an exact, order-sensitive list asserted for equality; a new id in the wrong position fails the suite.
- `guard_analyzer_node` wraps every node and converts any exception into `{"findings": []}` plus a `"failed"` ledger status. A broken analyzer will not fail the run or a test that only checks `graph.invoke()` succeeded — assert on findings directly.
- Adding the id to `_MODEL_SLOTS` in `constants.py` is optional and only enables the `SKILLSPECTOR_MODEL_<SLOT>` override; an unlisted id falls back to `model_config["default"]`.
- Every analyzer runs on every scan — `build_context` fans out to all of them unconditionally. An analyzer that should only apply to certain inputs must return early on its own gate.
- Only a **Framework** mismatch returns bare `{"findings": []}` (ADR 0002). Past that gate the analyzer reports a status on every input: applicability is one named predicate, the gate tests its result for emptiness, the planned work derives from that same result, and an empty result emits `not_applicable` with `LedgerReason.NO_APPLICABLE_FILES` and no ledger event. Two expressions for "applicable" is the defect ADR 0006 records.
- Statuses come from `AnalyzerStatus` in `inspection_ledger.py`, never from a bare string: `analyzer_status_event` raises on an undeclared spelling, and `tests/unit/test_analyzer_status.py` fails a status written inline. Import the member.
