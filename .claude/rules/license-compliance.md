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
| (b) | Modified files carry prominent notices stating that You changed them | Enforced per file — see below. |
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
the current state arose: every one of the 128 files this fork authored carries NVIDIA's copyright
line and nobody else's. `#95` carries the sweep that corrects it; until that lands, a new file still
gets the *correct* header rather than matching its neighbours.

## Third-party dependencies

`THIRD_PARTY_NOTICES.md` is upstream's record of the licenses the distribution pulls in. **A pull
request that adds a runtime dependency to `pyproject.toml` adds its entry to that file in the same
pull request.** The fork has already added `tree-sitter` and `tree-sitter-java` without doing so.
Nothing enforces this — no CI job reads the file — so it is on the change author.

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
