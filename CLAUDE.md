# SkillSpector

LangGraph pipeline that scans `SKILL.md` skill directories for vulnerabilities and emits SARIF plus a 0–100 risk score.

## Tooling

- Every `make` target assumes a venv is already created **and activated** — `uv venv .venv && source .venv/bin/activate`, then `make install-dev`.
- Test: `make test-unit` · Lint: `make lint` and `make format-check`.
- `mypy` is configured in `pyproject.toml` but invoked by nothing — not `make lint`, not CI, not pre-commit. Ruff is the only enforced check.
- `pytest` `addopts` deselects the `integration` and `provider` markers, so a bare `pytest` silently skips them. Use `make test-integration` / `make test-provider [openai|anthropic|nv_build]`.

## Commits

- **Atomic** — one scope of change per commit. Never mix unrelated scopes; split instead.
- **Conventional Commits, strictly** — `type(scope): subject`, imperative mood, no trailing period. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`. Breaking changes use `!` after the scope and a `BREAKING CHANGE:` footer.
- Every commit needs a `Signed-off-by:` trailer — use `git commit -s`. CI's DCO job walks each commit in the PR range and fails without it.

## Critical Constraints

- New source files need the SPDX + Apache-2.0 header block (copy from any neighbour). Convention only — nothing enforces it.
- `skillspector.constants` resolves the active provider and validates the model config **at import time**; importing it raises when `SKILLSPECTOR_STRICT_MODEL_VALIDATION=true` and a model is unknown.
- This repo is a fork of NVIDIA/SkillSpector and still merges upstream. Prefer new files in new paths; where an existing file must change, keep the diff append-only.
- Active goal: extend scanning to LangChain4j and Deep Agents skills. **Existing behavior on existing inputs must not change** — new analyzers are gated, never unconditionally wired.

## Context

- `contrib/batch_scan/` — batch scanner with its own runners, excluded from `make test`.

## References

- Architecture, node and provider walkthroughs, env vars — `docs/DEVELOPMENT.md`
- Extending the scanner to LangChain4j and Deep Agents skills — `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md`
- Captured upstream framework docs — `docs/references/README.md`
