---
name: license-audit
description: "Audit this fork against NVIDIA's Apache-2.0 §4 obligations, and fix the drift it finds."
disable-model-invocation: true
---

# Auditing the inherited Apache-2.0 obligations

This fork is a Derivative Work of NVIDIA/SkillSpector. §4 of Apache-2.0 asks four things of it, and
three of them turn on one question: **who wrote this file?** Get the **attribution** right and §4(b)
and §4(c) follow; get it wrong and the distribution credits upstream for work upstream did not do and
leaves the real authors unnamed.

`.claude/rules/license-compliance.md` states the target. This skill measures the distance to it.

Everything here is measured against `upstream/main`, never assumed. Run `git fetch upstream` first.

## 1. Classify every file

Three buckets, and every source file is in exactly one:

```bash
MB=$(git merge-base upstream/main HEAD)
git diff --name-only --diff-filter=A $MB HEAD -- src tests contrib   # fork-authored
git diff --name-only --diff-filter=M $MB HEAD                        # inherited, modified here
```

Anything with a header that appears in neither list is inherited and untouched.

Pin `$MB` explicitly. A file upstream added *after* the merge-base and edited here classifies
differently depending on the ref you diff against, and getting that backwards inverts the fix.

**Done when** every file carrying an `SPDX-FileCopyrightText` line sits in exactly one bucket, and the
three counts add up to `grep -rl "SPDX-FileCopyrightText" src/ tests/ contrib/ | wc -l`.

## 2. Audit the headers against the buckets

| Bucket | Correct header |
|---|---|
| Inherited, untouched | NVIDIA's line, unchanged |
| Inherited, modified here | NVIDIA's line **and** the fork's, upstream first — §4(c) retains, §4(b) notices |
| Fork-authored | the fork's line **only** |

Every file keeps `SPDX-License-Identifier: Apache-2.0` and the Apache boilerplate regardless: §4 offers
no option to relicense inherited portions, and the fork is Apache-2.0 too.

A file under `tests/fixtures/` carrying no header is **correct**, not a gap. Fixtures are analyzer
input; a header there is content the Scan reads, and adding one moves that fixture's Behavior
Snapshot. Audit files that carry a header, and leave the ones that deliberately do not.

**Done when** you have a count of files in each bucket whose header is wrong, and the list of them.

## 3. Audit the third-party notices

`THIRD_PARTY_NOTICES.md` is upstream's record of what the distribution pulls in. Compare it against
every runtime dependency the fork added:

```bash
git diff $MB HEAD -- pyproject.toml | grep '^+' | grep -v '^+++'
```

For each added dependency, confirm both that it appears in the file and that its stated license is
compatible with Apache-2.0 redistribution.

**Done when** every fork-added runtime dependency is either present in the file or on your fix list.

## 4. Audit the license itself

- `LICENSE` is byte-identical to upstream's: `git diff $MB HEAD -- LICENSE` is empty.
- **§4(d):** check whether upstream ships a `NOTICE` file —
  `git ls-tree --name-only upstream/main | grep -i notice`. If it does, this fork must carry it. If it
  does not, §4(d) has nothing to propagate; record that you checked rather than that you assumed.

**Done when** both are verified against upstream, not against memory.

## 5. Report, then fix what you may

Report every finding with its measured count and the command that produced it. Then fix — with one
exception.

**The fork's copyright line is the user's decision, and it blocks the header sweep.**
`Copyright (c) 2026 SkillSpector-Polyglot contributors`, a personal name, a legal entity: all are
valid, and an agent picking one puts a name on a legal notice. Ask, and hold the header fix until the
answer comes. Notices and dependency entries do not depend on it and proceed.

When you do sweep headers, sweep by classification rather than by path. A blanket rewrite over `src/`
reaches `tests/fixtures/`, whose files are analyzer *input* — editing a fixture moves its Behavior
Snapshot's `size_bytes` and rewrites snapshots for reasons that have nothing to do with licensing.
Prove the sweep additive the way this repository proves everything else: `make update-snapshots`, then
`git status` showing no snapshot modified. Include `contrib/`, which `make test` never runs.

**Done when** every finding is either fixed on the branch or written down as blocked on a named
decision — and neither state is left implicit.
