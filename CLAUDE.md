# SkillSpector

LangGraph pipeline that scans `SKILL.md` skill directories for vulnerabilities and emits SARIF plus a 0–100 risk score.

## Tooling

- Every `make` target assumes a venv is already created **and activated** — `uv venv .venv && source .venv/bin/activate`, then `make install-dev`.
- Test: `make test-unit` · Lint: `make lint` and `make format-check`.
- `mypy` is configured in `pyproject.toml` but invoked by nothing — not `make lint`, not CI, not pre-commit. Ruff is the only enforced check.
- `pytest` `addopts` deselects the `integration` and `provider` markers, so a bare `pytest` silently skips them. Use `make test-integration` / `make test-provider [openai|anthropic|nv_build]`.
- On fish, venv activation does not survive between non-interactive commands. Two autoloaded functions in `~/.config/fish/functions/` avoid it entirely — `sspy <args>` runs `.venv/bin/python`, and `sspytest [paths]` runs the unit selection (`pytest -m "not integration and not provider"`). Examples: `sspy -c 'import skillspector'`, `sspytest tests/unit -q`. They are user-local, not checked in; `sspy` exits 127 with the setup command if the venv is missing.

## Code search

Order of preference: **`codegraph_explore` MCP tool → `codegraph explore` CLI → grep/find.** This repo is indexed (`.codegraph/`); the MCP tool is often not exposed, the CLI always works.

- Both take symbol names or a plain question, and return verbatim line-numbered source plus a **blast radius**: every caller and which tests cover each symbol. That coverage signal is what grep cannot give you and what tells you whether a change is safe.
- `maxFiles` truncates by file without re-ranking, so a low cap can drop a file the blast radius just named. Narrow the query rather than the cap.
- Use grep for non-code text (markdown, YAML, logs) and literal string matching.

## Commits

- **Atomic** — one scope of change per commit. Never mix unrelated scopes; split instead.
- **Conventional Commits, strictly** — `type(scope): subject`, imperative mood, no trailing period. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`. Breaking changes use `!` after the scope and a `BREAKING CHANGE:` footer.
- Every commit needs a `Signed-off-by:` trailer — use `git commit -s`. CI's DCO job walks each commit in the PR range and fails without it.

## Spec execution workflow

Applies whenever a Spec — a parent issue plus its child Tickets, as published by `/to-spec` — is
being implemented. Every Ticket is implemented through the `/implement` skill, never ad hoc.

1. **Cut the Umbrella Branch first.** Before the first Ticket, `git fetch origin` and branch the
   whole Spec off an up-to-date `main` (this repo's default branch — there is no `master`). Name it
   for the feature, not for a Ticket.
2. **One branch per Ticket, cut from the Umbrella Branch** — never from `main`. It implements that
   Ticket completely.
3. **Close out each Ticket on merge.** Open a PR from the Ticket branch **into the Umbrella Branch**,
   merge it, and delete the branch local and remote — `delete_branch_on_merge` is off on this repo,
   so nothing is cleaned up for you. Then edit the Ticket issue: tick its acceptance-criteria
   checkboxes, and comment whatever the Ticket did not anticipate — a rejected approach, a discovered
   constraint, a deferred follow-up.
4. **Close out the Spec.** When every Ticket is merged into the Umbrella Branch, update the parent
   issue, then open a PR from the Umbrella Branch into `main`. **A human merges that PR — an agent
   never does.**

Within a Spec, the Umbrella Branch is the only branch that targets `main` — a Ticket branch never
does. **Outside a Spec** this workflow does not apply: standalone work such as a documentation
correction or a one-off fix branches from `main`, opens a PR against `main`, and is merged by
whoever the user says. Do not manufacture an Umbrella Branch for a single PR.

## Critical Constraints

- New source files need the SPDX + Apache-2.0 header block (copy from any neighbour). Convention only — nothing enforces it.
- `skillspector.constants` resolves the active provider and validates the model config **at import time**; importing it raises when `SKILLSPECTOR_STRICT_MODEL_VALIDATION=true` and a model is unknown.
- This repo is a fork of NVIDIA/SkillSpector and still merges upstream. Prefer new files in new paths; where an existing file must change, keep the diff append-only.
- Active goal: extend scanning to LangChain4j and Deep Agents skills. **Existing behavior on existing inputs must not change** — new analyzers are gated, never unconditionally wired.

## Agent skills

- Issues are tracked in GitHub Issues — `docs/agents/issue-tracker.md`
- Triage labels follow the canonical five roles — `docs/agents/triage-labels.md`
- Domain-doc and ADR conventions — `docs/agents/domain.md`

## References

- Domain glossary — use these terms, not their synonyms — `CONTEXT.md`
- Architecture, node and provider walkthroughs, env vars — `docs/DEVELOPMENT.md`
- Extending the scanner to LangChain4j and Deep Agents skills — `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md`
- Captured upstream framework docs — `docs/references/README.md`
- Batch scanner, own runners, excluded from `make test` — `contrib/batch_scan/CLAUDE.md`

## Applied Learning

When something fails repeatedly, when User has to re-explain, or when a workaround is found for a platform/tool limitation, add a one-line bullet here. Keep each bullet under 15 words. No explanations. Only add things that will save time in future sessions.

- `gh issue view` fails with a projectCards GraphQL error; use `--json`.
- `tests/integration/conftest.py` auto-marks by path; never put a unit test there.
- Fish shell: activate does not persist between calls — invoke `.venv/bin/python` directly.
