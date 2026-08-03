# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Every Deep Agents spelling SkillSpector's Rules match on, and nothing else.

The reason is the one ``docs/adr/0005-langchain4j-upstream-vocabulary.md`` gives
for the Java track and ``docs/adr/0008-deepagents-analyzer-resolves-one-module-deep.md``
copies for this one: when upstream renames a keyword argument or a type, a Rule
that matches it stops producing Findings and **nothing says so**. The Scan still
succeeds, the Analyzer still reports itself as having run, and the report reads
as clean. So the spellings live in one file, and
``tests/unit/test_deepagents_vocabulary.py`` fails the build when one is written
inline anywhere else in the source tree.

What ADR 0005's second half is *not* copied: it measured the stability claim
rather than asserting it -- seventeen Maven releases swept, recorded in
``OBSERVED_VERSION_RANGE``. No equivalent measurement exists for Deep Agents yet.
Producing it, and the re-measurement procedure for both Frameworks, is issue #75.
Until that lands this module carries no version range, deliberately, rather than
carrying an unmeasured one.

Issue #70 seeded this module with two spellings while the Analyzer that owns them
carried no Rule, so the guard would be in force from the first Rule rather than
retrofitted around five. Issue #71 is that first Rule -- the resolution boundary
``DA-UNRESOLVED`` -- and it is what starts importing from here. Issues #72
through #74 add the rest of the inventory ADR 0008 enumerates; none of them
writes a spelling anywhere else.

**Two sections, because two of these spellings are ordinary English words.**
``skills`` and ``permissions`` are also an Agent Skills manifest field, a
repository directory name and a CLI report key, and
:mod:`skillspector` writes all three as bare literals in modules that have
nothing to do with Deep Agents -- ``build_context``, ``mcp_least_privilege``,
``repository_scan``, ``cli``. Making the guard demand those call sites import a
Deep Agents constant would be wrong rather than strict: they are homonyms, not
leaks. So the inventory still owns them -- an upstream rename is still one edit
here -- and the guard's *sweep* exempts them, on evidence rather than on
assertion: ``tests/unit/test_deepagents_vocabulary.py`` requires each exempted
spelling to really occur inline elsewhere in the tree, so an exemption that stops
being a homonym stops being allowed.

**These are a second copy of what :mod:`skillspector.framework` matches on for
detection, and that is deliberate.** ADR 0008 rejected sharing one inventory
between detection and the Rules outright: they answer different questions -- "is
this tree Deep Agents at all" versus "what does this call configure" -- and an
upstream rename that legitimately moves one of them should not silently move the
other. The guard therefore sweeps the whole source tree *except* ``framework.py``.

Deliberately import-free, so nothing here can fail to load.

Provenance
----------

Captured from ``docs/references/langchain-deepagents-skills.md`` (upstream
<https://docs.langchain.com/labs/deep-agents/skills>).
"""

from __future__ import annotations

from typing import Final

# -- The Framework itself ---------------------------------------------------- #

# The constructor every host-side setting is passed to. Upstream names it in the
# first line of every example on the captured page.
CREATE_DEEP_AGENT: Final[str] = "create_deep_agent"

# The distribution that provides it, as a Python requirement file spells it.
DISTRIBUTION: Final[str] = "deepagents"

# -- What the constructor is configured with --------------------------------- #

# The declarative permission rule. Its own keyword arguments are deliberately
# *not* inventoried: the resolver requires every one of them to resolve to a
# literal without caring which they are, so it never spells `operations`,
# `paths` or `mode`. The Rule that reads those three by name is issue #72.
FILESYSTEM_PERMISSION: Final[str] = "FilesystemPermission"

# The keyword argument that decides whether the Skill files are on disk at all,
# and therefore whether any writability verdict is knowable.
BACKEND: Final[str] = "backend"

# The four backends upstream ships. Only `CompositeBackend` is walked into,
# through `ROUTES`; the other three are recognized so that naming one is a
# resolved backend rather than an unreadable expression.
COMPOSITE_BACKEND: Final[str] = "CompositeBackend"
STORE_BACKEND: Final[str] = "StoreBackend"
STATE_BACKEND: Final[str] = "StateBackend"
FILESYSTEM_BACKEND: Final[str] = "FilesystemBackend"

# `CompositeBackend`'s path-prefix map. A route key that is a literal resolves a
# Skill path without resolving what the path is routed to.
ROUTES: Final[str] = "routes"

# -- Homonyms: owned here, exempt from the sweep ------------------------------ #
#
# Both are ordinary English words this repository already writes inline for
# unrelated reasons -- an Agent Skills manifest field, a discovery directory
# name, a CLI report key. See the module docstring: the exemption is asserted
# against real occurrences elsewhere in the tree, not merely declared.

# The Skill source paths the agent is given.
SKILLS: Final[str] = "skills"

# The declarative rules that decide what the agent may do to those paths.
PERMISSIONS: Final[str] = "permissions"
