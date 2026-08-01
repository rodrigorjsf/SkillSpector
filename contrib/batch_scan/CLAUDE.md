# Batch scanner — wraps the core `graph.invoke()` with a multi-key API pool to scan large fixture corpora in parallel.

## Tooling

- **Excluded from `make test`** — the root `pyproject.toml` sets `testpaths = ["tests"]`, so nothing here runs in the default suite.
- Tests are standalone scripts, not pytest: `python contrib/batch_scan/tests/test_pool_wiring.py`, `python contrib/batch_scan/tests/tests-pro/random_numbered.py` (seeded unittest runner), `python contrib/batch_scan/tests/tests-pro/mutation_max.py` (mutation framework).
- Run the scanner with `python -m contrib.batch_scan.batch_scan ...`.
- One exception to the isolation: `tests/test_batch_scan_reports.py` lives in the **root** pytest tree and does exercise `contrib.batch_scan.reports`.

## Conventions

- **Dual-patch pool wiring**: patch both `llm_utils.get_chat_model` and `llm_analyzer_base.get_chat_model`. The latter holds a local `from ... import` reference, so patching only the former silently misses it.
- Inject attributes into the instance `__dict__` rather than patching class attributes — class-level patching is not thread-safe under the pool.
- `_verify_patch_targets()` runs before applying patches and fails closed if an upstream signature changed. Keep it current when core signatures move.
- Prior art before changing anything here: `CONTRIBUTING.md`, `docs/DESIGN.md`, `docs/archive/PITFALLS.md`.
