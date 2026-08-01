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
