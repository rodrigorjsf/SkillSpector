---
paths:
  - "*.py"
  - "**/*.py"
  - "*.md"
  - "**/*.md"
  - "*.toml"
  - "*.yaml"
  - "*.yml"
  - "**/*.yaml"
  - "**/*.yml"
---

# Apache-2.0 compliance, inherited from NVIDIA/SkillSpector

This repository is a fork of [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector), licensed
Apache-2.0 with `Copyright 2026 NVIDIA CORPORATION & AFFILIATES`. Everything here is a Derivative
Work under §1 of that license, and the obligations in §4 bind **every** change, not just releases.
People install this fork; the license has to be right from the first commit, not retrofitted before
a release that may never be cut.

The four §4 obligations, and what each means concretely here:

| §4 | Obligation | State in this repository |
|---|---|---|
| (a) | Recipients get a copy of the License | `LICENSE` at the root, unmodified. **Never edit, relicense, or remove it**, and never change the NVIDIA copyright line inside it. |
| (b) | Modified files carry prominent notices stating that You changed them | Per file for anything carrying a comment header — see below. A build or documentation file with no comment syntax (`Makefile`, `pyproject.toml`, `README.md`, `docs/`) is covered instead by the Transparency bullet in `README.md`, which states that this fork modifies inherited files. Keep that bullet; it is the notice for everything a header cannot reach. |
| (c) | Retain every copyright, patent, trademark and attribution notice from the Source form | Never delete an existing `SPDX-FileCopyrightText` line. Add beside it. |
| (d) | Propagate a `NOTICE` file if the Work has one | Upstream ships **no** `NOTICE` — verified against `upstream/main`. Nothing to propagate. If upstream ever adds one, this row changes and the fork must carry it. |

## Copyright headers

Upstream's header block is the SPDX two-liner plus the Apache boilerplate. Which copyright line it
carries depends on who wrote the file:

- **A file inherited from upstream, unmodified** — leave the header exactly as it is.
- **A file inherited from upstream and modified here** — keep NVIDIA's line and add the fork's
  beneath it. Two lines, upstream first. This is §4(b) and §4(c) in one place, and it is the reason
  the fork line is added rather than substituted.
- **A file created in this fork** — the fork's line **only**. NVIDIA holds no copyright in code
  NVIDIA did not write, and asserting otherwise is a false attribution in both directions: it
  credits upstream for work they did not do, and it leaves the actual authors unnamed.

The fork's line is:

```
# SPDX-FileCopyrightText: Copyright (c) 2026 SkillSpector-Polyglot contributors
```

The `SPDX-License-Identifier: Apache-2.0` line and the Apache boilerplate stay on every file
regardless — the fork is Apache-2.0 too, and §4 offers no option to relicense a Derivative Work's
inherited portions.

**Do not copy a header "from any neighbour" without reading whose file it is.** That shortcut is how
the fork's headers went wrong in the first place: every file it authored carried NVIDIA's copyright
line and nobody else's. `#95` swept the tree against `upstream/main` and corrected it — every
fork-authored file given the fork's line alone, every inherited-and-modified file given both, every
inherited-and-untouched file left as it is. `/license-audit` re-measures those three buckets, so ask
it for the counts rather than reading a number here; the shortcut is what would put the tree back.

## Third-party dependencies

`THIRD_PARTY_NOTICES.md` is upstream's record of the licenses the distribution pulls in. **A pull
request that adds a runtime dependency to `pyproject.toml` adds its entry to that file in the same
pull request.** The fork's own additions — `tree-sitter` and `tree-sitter-java` — are recorded there
as of `#95`; the four inherited ones the file had always omitted are recorded as of `#102`.

`tests/unit/test_third_party_notices.py` enforces the rule in both directions: every name in
`project.dependencies` has an entry, and no entry outlives its dependency. It compares normalised
names as **sets** — a containment check would pass with `tree-sitter` deleted, because the string
survives inside `tree-sitter-java`. It does **not** cover `project.optional-dependencies`; `mcp` is
redistributed and remains unaudited, tracked as `#109`.

The license and copyright line for a new entry are **read, never recalled** — `#95` would have
guessed two of two wrong. Read them from the installed `dist-info`: its license file, or its
`NOTICE` when the license file is bare Apache text (`boto3`). A `dist-info` may ship neither —
`langsmith` 0.9.1's `RECORD` has no license row at all — in which case read the `LICENSE` at the
**installed version's tag** in the project's own repository, and say in the commit body that you
did. Do not normalise a line to look like its neighbours: `langsmith`'s is
`Copyright (c) 2023 LangChain`, without the `, Inc.` its three LangChain neighbours carry.

## What never happens

- Opening a pull request or issue against `NVIDIA/SkillSpector`. Upstream is a read-only sync source
  (see the Remote section of `CLAUDE.md`); the license grants no right to push to it.
- Removing, rewording, or "cleaning up" an inherited copyright notice, an SPDX line, or the
  provenance URLs below the `# Inherited documentation` marker in `README.md`. Those are §4(c)
  material, not stale links.
- Presenting fork-authored behavior as upstream's, or upstream's as the fork's, in `README.md`, an
  ADR, or a Finding message. Attribution accuracy is the substance of §4, not a formality.
- Adding a dependency whose license is incompatible with Apache-2.0 redistribution — GPL and AGPL
  most obviously. Check before adding, not at release time.

## When this rule is in doubt

Do not guess and do not proceed. Apache-2.0 questions are the user's call, not a routine judgment:
state what the license text says, what the repository actually does, and where the two differ, then
ask. A wrong guess here is shipped to everyone who installs the fork.
