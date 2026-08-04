# SkillSpector-Polyglot

LangGraph pipeline that scans `SKILL.md` skill directories for vulnerabilities and emits SARIF plus a 0–100 risk score. This fork extends that to skills embedded in a programming-language framework's own source tree — LangChain4j and Deep Agents, both shipped. The Deep Agents Analyzer carries `DA-UNRESOLVED`, `DA-SKILL-WRITABLE`, `DA-SHADOW` and `DA-SUBAGENT-SKILLS`; both Frameworks' upstream vocabularies carry a measured version range, re-measured by `docs/VOCABULARY_REMEASUREMENT.md`.

The GitHub repository is `SkillSpector-Polyglot`; the distribution, the package under `src/skillspector/`, and the console script stay `skillspector`. Renaming them would break upstream merges and existing installs — never propose it as a cleanup.

## Tooling

- Every `make` target assumes a venv is already created **and activated** — `uv venv .venv && source .venv/bin/activate`, then `make install-dev`.
- Test: `make test-unit` · Lint: `make lint` and `make format-check`.
- `mypy` is configured in `pyproject.toml` but invoked by nothing — not `make lint`, not CI, not pre-commit. Ruff is the only enforced check.
- `pytest` `addopts` deselects the `integration` and `provider` markers, so a bare `pytest` silently skips them. Use `make test-integration` / `make test-provider [openai|anthropic|nv_build]`.
- On fish, venv activation does not survive between non-interactive commands. Two autoloaded functions in `~/.config/fish/functions/` avoid it entirely — `sspy <args>` runs `.venv/bin/python`, and `sspytest [paths]` runs the unit selection (`pytest -m "not integration and not provider"`). Examples: `sspy -c 'import skillspector'`, `sspytest tests/unit -q`. They are user-local, not checked in; `sspy` exits 127 with the setup command if the venv is missing.

## Code search

This repo is indexed (`.codegraph/`), so CodeGraph applies to every code lookup here.

- The MCP tool and the CLI both take symbol names or a plain question, and return verbatim line-numbered source plus a **blast radius**: every caller and which tests cover each symbol. That coverage signal is what grep cannot give you and what tells you whether a change is safe.
- `maxFiles` truncates by file without re-ranking, so a low cap can drop a file the blast radius just named. Narrow the query rather than the cap.
- Use grep for non-code text (markdown, YAML, logs) and literal string matching.

## Remote

This repo is a fork. **Every git and GitHub operation targets `rodrigorjsf/SkillSpector-Polyglot` — never the
upstream `NVIDIA/SkillSpector`.** Pushes, branches, pull requests, issues, issue comments, releases
and workflow runs all belong to the fork. Upstream is a read-only sync source: fetch from it, never
push to it and never open a pull request or issue against it. `gh` resolves the upstream remote by
default on a fork, so pass `--repo rodrigorjsf/SkillSpector-Polyglot` whenever the target is not
unambiguous.

## README is part of the change

`README.md` opens with this fork's own documentation — mission, framework support matrix, audience,
install, usage, configuration, transparency — and only then the inherited upstream README under the
`# Inherited documentation` marker. **The fork sections above that marker are not a snapshot; they
are a contract.** A pull request that adds or alters a rule, a framework, a CLI flag, an environment
variable, an exit code or an output format updates them in the *same* pull request — never a
follow-up. The README's own "Contributing, and keeping these docs true" table maps each kind of
change to the section it must update; keep that table correct too.

Below the marker, keep the diff append-only and leave the `NVIDIA/skillspector` URLs alone — they
are upstream provenance, not stale links.

## Commits

- **Atomic** — one scope of change per commit. Never mix unrelated scopes; split instead.
- **Conventional Commits, strictly** — `type(scope): subject`, imperative mood, no trailing period. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`. Breaking changes use `!` after the scope and a `BREAKING CHANGE:` footer.
- Every commit needs a `Signed-off-by:` trailer — use `git commit -s`. CI's DCO job walks each commit in the PR range and fails without it.

## Pull requests

**Only call a PR ready — or recommend merging it — once everything that belongs in it is
finished.** Not started, not queued, not "running in the background": finished, with its output
read. Before saying it is ready, all of these must be true.

- **Validations green.** `make test-unit`, `make lint`, `make format-check`, and
  `make update-snapshots` leaving the tree clean.
- **Reviews closed out.** Every review or adversarial pass complete, with each finding either
  fixed on the branch or written into the PR body as a deliberate deferral.
- **Subagents finished.** A background subagent is unfinished work, not a parallel activity the
  merge can race. Wait for it and read its result — one has already caught a defect after the PR
  was green and the human had been told to merge.
- **Nothing left to add.** A `CLAUDE.md` edit, an Applied Learning bullet, or a documentation
  correction the work exposed rides **this** PR. Never a follow-up.
- **CI verified against the right commit.** `gh pr checks` must be green on a `headRefOid` equal
  to `git rev-parse HEAD`, with `state` still `OPEN`.

If anything is outstanding, say what it is instead of saying the PR is ready. A human merges on
that word, and a merged PR ignores later pushes — a commit that lands afterwards is lost from
`main` and costs a second PR to recover.

**Every merged PR leaves an orphan branch. Delete it, local and remote.**
`delete_branch_on_merge` is off on this repository, so nothing is cleaned up automatically and
merged branches accumulate. `gh pr merge --delete-branch` handles both sides when the agent does
the merge; when a human merges, delete it afterwards with `git branch -d` and
`git push origin --delete <branch>`. A merge is not closed out until its branch is gone.

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
4. **Close out the Spec.** When every Ticket is merged into the Umbrella Branch, audit the parent's
   stories for gaps no Ticket owned, comment that audit on the parent issue, then open a PR from the
   Umbrella Branch into `main`. **A human merges that PR — an agent never does.**
5. **Close the parent after the merge.** A Spec parent does not close itself: merging the Umbrella
   PR leaves it open. Once `main` carries the work, verify it there, delete the Umbrella Branch local
   and remote, file whatever the audit surfaced as its own issue, and close the parent referencing
   the merge commit. A Spec is not done while its parent is open.

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
- Triage labels pair one state role from the canonical five with one category — `docs/agents/triage-labels.md`
- Domain-doc and ADR conventions — `docs/agents/domain.md`

## References

- Domain glossary — use these terms, not their synonyms — `CONTEXT.md`
- Architecture, node and provider walkthroughs, env vars — `docs/DEVELOPMENT.md`
- Extending the scanner to LangChain4j and Deep Agents skills — `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md`
- Captured upstream framework docs — `docs/references/README.md`
- Re-measuring a Framework vocabulary's version range, and its trigger — `docs/VOCABULARY_REMEASUREMENT.md`
- Batch scanner, own runners, excluded from `make test` — `contrib/batch_scan/CLAUDE.md`
- Vocabulary sweep, own runner, excluded from `make test` — `contrib/vocabulary_sweep/CLAUDE.md`

## Applied Learning

When something fails repeatedly, when User has to re-explain, or when a workaround is found for a platform/tool limitation, add a one-line bullet here. Keep each bullet under 15 words. No explanations. Only add things that will save time in future sessions.

- A worktree needs its own venv; the main checkout's editable install imports its dirty `src/`.
- `gh issue view` fails with a projectCards GraphQL error; use `--json`.
- `gh pr edit` hits the same error; PATCH the body via `gh api` instead.
- `gh api --jq .body_html` needs `Accept: application/vnd.github.html+json`, else empty.
- CI only triggers on `main`-targeting PRs; empty `gh pr checks` is not a pass.
- `make` needs `export PATH="$PWD/.venv/bin:$PATH"`; sourcing `activate.fish` fails in Bash.
- Empty `git diff` plus `M` status means `core.autocrlf`, not a real change.
- Fork Actions need the Actions-tab enable button clicked once; only a human can.
- Squash-merge Ticket PRs; DCO checks every merge commit inside the PR range.
- `CONTEXT.md` `_Avoid_` terms bind docstrings and test names, not just prose.
- `CONTEXT.md` entries define terms only; symbol names belong in `DEVELOPMENT.md`.
- Link sub-issues via `gh api -F sub_issue_id=<id>`; `-f` sends a string and 422s.
- Prove a snapshot change additive with `git status` after `make update-snapshots`.
- Corpus counts are prose in six files; grep the phrasing, not just the number.
- Commit-time CRLF warnings are harmless when `git ls-files --eol` shows `i/lf`.
- Faking an absent module needs `delattr` on the package, not just `sys.modules`.
- New fixtures also need a `DETECTION_FIXTURES` row in `test_framework_detection.py`.
- After shipping, grep docs for text still claiming the feature is unbuilt.
- Truncated subagent result: resume it with `SendMessage`, never re-run it.
- `gh api search/code` matches terms, not phrases; use WebSearch for exact phrases.
- `agentskills.io/llms.txt` lists every spec page; grep all before claiming absence.
- Guarding literals: match spellings exactly — containment hits Finding-message prose.
- Fixture comments are scanned; never name the capability a fixture lacks.
- Rule `paths`: `**/*.py` skips the base dir; pair it with `*.py`.
- Run the CLI as `.venv/bin/skillspector`; `python -m skillspector` has no `__main__`.
- JSON report nests findings under `issues`, keyed `id` — not `findings`/`rule_id`.
- Undo a mutation test by hand; `git checkout --` drops the whole file's edits.
- Mutate a module constant in a throwaway script instead; nothing to undo.
- `Closes #N` no-ops in a Ticket PR; only a default-branch merge closes an issue.
- Vocabulary guard: exempt a homonym spelling by call site, never globally.
- Bare `python` is absent; run throwaway scripts with `.venv/bin/python`.
- A new `deepagents/` module must join the vocabulary guard's explicit module list.
- A new vocabulary spelling also needs its guard test's `_EXPECTED_SPELLINGS` set.
- Editing `pattern_defaults` prose rewrites every snapshot carrying that rule.
- Upstream docs can name a method no release ships; sweep the artifacts, not the pages.
- A non-spelling vocabulary constant needs the guard's `_NOT_A_SPELLING` set.
- Renaming a vocabulary constant: fix both `vocabulary_sweep/roles.py` maps; no test covers them.
