---
name: upstream-sync
description: "Measure how far this fork has drifted from NVIDIA/SkillSpector, and merge upstream's new work in."
disable-model-invocation: true
---

# Syncing this fork with NVIDIA/SkillSpector

This fork carries **inherited** code — everything it did not write — and that inheritance goes stale.
Upstream ships fixes to the very analyzers this fork extends. **Drift** is the gap; this skill closes
it.

One fact governs every step. Everywhere else in this repository, a Behavior Snapshot that moves means
you broke something. **An upstream merge is the one case where a snapshot delta is correct** — upstream
changed what a Rule finds, and the fork inherits that change. So the gate stops being a pass/fail and
becomes a ledger: every delta must be **attributable** to a named upstream commit. A delta you cannot
name is the merge going wrong, and it is the only signal that will tell you.

## 1. Measure the drift

```bash
git fetch upstream && git fetch origin
MB=$(git merge-base upstream/main origin/main)
git log --oneline $MB..upstream/main          # what upstream did
git rev-list --count $MB..origin/main         # how far the fork has gone
git diff --name-only $MB upstream/main | sort > /tmp/up.txt
git diff --name-only $MB origin/main | sort > /tmp/fk.txt
comm -12 /tmp/up.txt /tmp/fk.txt              # the conflict surface
```

The **conflict surface** is the third command's output: files both sides changed. It is the whole of
the work — everything else merges itself.

**Done when** you can name every upstream commit and every file on the conflict surface. If
`$MB..upstream/main` is empty, the fork is current: say so and stop.

## 2. Read the commits, not the diff

An upstream commit that changes a Rule's behavior is the reason snapshots will move in step 5, and its
message is the only place that reason is written. Read each one, and note which touch
`nodes/analyzers/`, `build_context.py`, `state.py` or `report.py` — those reach the fork's gate.

**Done when** every upstream commit is labelled either *behavior-affecting* or *not*, with the
behavior-affecting ones matched to the fixtures you expect to move.

## 3. Merge onto a branch of its own

Branch from an up-to-date `main`, named for the sync rather than for a feature, and
`git merge upstream/main`. Let it conflict — resolving is step 4, and a merge you reshaped before
reading the conflicts hides which side changed what.

## 4. Resolve, keeping both intents

Each conflict is upstream's change meeting the fork's. The fork's rules decide the resolution:

- **`README.md`** — above the `# Inherited documentation` marker is the fork's own contract; upstream
  never touches it. Below the marker, take upstream's text and keep the diff **append-only**. The
  `NVIDIA/skillspector` URLs there are provenance, so they survive the merge unchanged.
- **`pyproject.toml`** — take upstream's `version`. The fork does not fork the version number; a fork
  version *below* upstream's is drift, not a decision. Keep the fork's added dependencies.
- **Inherited docs the fork edited** — `docs/DEVELOPMENT.md`, `docs/OWASP-AST10-COVERAGE.md`. These
  describe upstream's own behavior, so upstream's text wins wherever the two describe the same thing,
  and the fork's additions sit beside it. A coverage claim upstream revised is a fact about the
  scanner, not an opinion the fork gets to keep.
- **Analyzer modules the fork extended** — upstream's fix and the fork's extension are usually
  disjoint hunks. Where they are not, upstream's logic wins and the fork's extension is re-applied on
  top, because the fork's promise is to extend upstream rather than to replace it.
- **`CLAUDE.md`, `docs/adr/`, `.claude/rules/`, `src/skillspector/langchain4j/`,
  `src/skillspector/deepagents/`** — fork-owned. Upstream has no opinion; keep the fork's.

Where upstream deleted something the fork built on, that is a real design question, not a merge
decision — stop and put it to the user with the upstream commit that did it.

**Done when** `git diff --check` is clean, no conflict marker survives anywhere, and you can say for
each resolved file which side's intent you kept and why.

## 5. Turn the gate into a ledger

```bash
make update-snapshots && git status --short
```

Now account for the output. **Every** modified snapshot is matched to the upstream commit that
explains it — a Rule upstream tightened, a pattern it added. Read the actual diff of the snapshot, not
just its filename.

A snapshot that moved with no upstream commit behind it is the merge having gone wrong. So is an
*unchanged* snapshot for a fixture a behavior-affecting upstream commit should have moved — that means
the fix did not survive the resolution.

**Done when** every modified snapshot has a named upstream commit beside it, and every
behavior-affecting commit from step 2 has produced the delta you predicted. Write that mapping down;
it is the PR body.

## 6. Close it out

`make test-unit`, `make lint`, `make format-check`. Upstream ships its own tests — a failure among
them is a resolution defect, not a flaky test.

Then hand off to **`/license-audit`** — it is user-invoked, so ask the user to run it against this
branch before the PR is called ready, and say why. A merge is exactly when license drift enters:
upstream files arrive, files the fork had modified gain upstream hunks, and `pyproject.toml` may gain
a dependency `THIRD_PARTY_NOTICES.md` does not know about.

Open the PR against `main` with the step-5 mapping as its body, and say plainly that snapshots moved
and why — a reviewer who sees a snapshot diff in this repository assumes a regression until told
otherwise. **A human merges it.**

File whatever the sync surfaced and could not close as its own issue, per `CLAUDE.md`.
