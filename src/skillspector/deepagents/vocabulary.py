# SPDX-FileCopyrightText: Copyright (c) 2026 SkillSpector-Polyglot contributors
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

ADR 0005's second half is copied too, and issue #75 is where it landed: the
stability claim below is measured rather than asserted. Every published release
of the distribution was swept -- 78 of them -- and ``OBSERVED_VERSION_RANGE``
records how far, so a reader can tell how stale the claim is. What re-runs that
sweep, and what obliges someone to, is ``docs/VOCABULARY_REMEASUREMENT.md``.

Issue #70 seeded this module with two spellings while the Analyzer that owns them
carried no Rule, so the guard would be in force from the first Rule rather than
retrofitted around five. Issue #71 is that first Rule -- the resolution boundary
``DA-UNRESOLVED`` -- and it is what started importing from here. Issue #72 added
what ``DA-SKILL-WRITABLE`` reads by name: the three keyword arguments of a
permission rule, the two ``mode`` values upstream documents, the write operation,
and the tool-level approval gate. Issues #73 and #74 add the rest of the
inventory ADR 0008 enumerates; none of them writes a spelling anywhere else.
Issue #74 is the last of them, and it added one spelling rather than the several
a subagent definition is written with -- ADR 0008's amendment records why, and it
is the same reason ``name`` is absent below.

**A section of its own, because four of these spellings are ordinary English
words.** ``skills`` and ``permissions`` are also an Agent Skills manifest field,
a repository directory name and a CLI report key; ``mode`` is the keyword
argument of a call to ``open``; ``write`` is a capability in an MCP tool map. And
:mod:`skillspector` writes all of them as bare literals in modules that have
nothing to do with Deep Agents -- ``build_context``, ``mcp_least_privilege``,
``repository_scan``, ``cli``, ``behavioral_taint_tracking``,
``static_patterns_supply_chain``. Making the guard demand those call sites import a
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
<https://docs.langchain.com/labs/deep-agents/skills>), and cross-checked against
the published PyPI distributions by ``contrib/vocabulary_sweep``.

Measured on 2026-08-03 by ``contrib/vocabulary_sweep``. Every final release was
swept for the spellings below: 78 versions, ``0.0.1`` through ``0.7.3``, read out
of the wheels rather than off the documentation.
**No spelling here has ever been removed.** Most were added during that history,
which is what a distribution still on ``0.x`` looks like, and the table under
``OBSERVED_VERSION_RANGE`` records each one's first release.
"""

from __future__ import annotations

from typing import Final

# The releases the sweep covered, oldest and newest. Every spelling below was
# observed in the *role* upstream writes it in -- defined as a name, bound as a
# parameter or field, or written as a string value -- rather than merely
# occurring somewhere in the archive, which for ordinary English words such as
# ``skills`` and ``mode`` would have measured nothing.
#
# When each spelling first appears, for the ones that are not in the first
# release. Nothing was ever removed, so each is present from its release to the
# end of the range:
#
#   0.0.6   write_file, edit_file
#   0.0.8   interrupt_on
#   0.2.0   CompositeBackend, StoreBackend, StateBackend, FilesystemBackend,
#           backend, routes, root_dir
#   0.2.8   paths
#   0.3.2   skills
#   0.5.2   FilesystemPermission, permissions, operations, mode, deny,
#           interrupt, write
#
# ``create_deep_agent``, ``subagents`` and the distribution name itself span the
# whole range. The practical floor is therefore **0.5.2**, the release where the
# permission vocabulary arrives and every spelling here exists together; the
# ``deepagents>=0.6.8`` in the captured reference is a floor for a different
# question -- filesystem-permission interrupts -- and sits above it.
#
# One annotation is a human's correction rather than the sweep's raw output.
# ``interrupt`` is a bare string value, and a sweep for one cannot tell the
# ``mode`` value from any other use of the word: 0.5.0 and 0.5.1 write
# ``multitask_strategy="interrupt"`` in an unrelated middleware. The permission
# value arrives at 0.5.2 with the rest of its cluster, and 0.5.2 is what is
# recorded. ``docs/VOCABULARY_REMEASUREMENT.md`` names this as the one step a
# re-measurement cannot leave to the tool.
OBSERVED_VERSION_RANGE: Final[tuple[str, str]] = ("0.0.1", "0.7.3")


# -- The Framework itself ---------------------------------------------------- #

# The constructor every host-side setting is passed to. Upstream names it in the
# first line of every example on the captured page.
CREATE_DEEP_AGENT: Final[str] = "create_deep_agent"

# The distribution that provides it, as a Python requirement file spells it.
DISTRIBUTION: Final[str] = "deepagents"

# -- What the constructor is configured with --------------------------------- #

# The declarative permission rule. The resolver in
# :mod:`skillspector.deepagents.host_config` still reads it without caring which
# keyword arguments it carries -- it requires every one of them to resolve to a
# literal and nothing more. The three below are inventoried because
# ``DA-SKILL-WRITABLE`` reads them *by name* to compute its verdict.
FILESYSTEM_PERMISSION: Final[str] = "FilesystemPermission"

# Which operations a rule governs, which paths it governs them on, and what it
# does where it applies. Upstream writes all three on every rule it documents.
OPERATIONS: Final[str] = "operations"
PATHS: Final[str] = "paths"

# The two `mode` values upstream documents. A covering rule written with any
# other value decides nothing this Scan can read, and reaches the boundary Rule
# rather than a verdict.
DENY: Final[str] = "deny"
INTERRUPT: Final[str] = "interrupt"

# The tool-level approval gate, and the two write tools it is written over.
# Unlike `mode="interrupt"`, which mitigates only its own rule's paths, this one
# "requires approval for all filesystem writes, not only skills paths".
INTERRUPT_ON: Final[str] = "interrupt_on"
WRITE_FILE: Final[str] = "write_file"
EDIT_FILE: Final[str] = "edit_file"

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

# The directory a `FilesystemBackend` roots its agent-visible paths at. It is the
# only argument that turns a configured Skill source path into a place a Scan can
# open, so `DA-SHADOW` cannot confirm a name collision without it.
#
# The manifest field that Rule compares across sources is deliberately *not*
# inventoried beside it. Upstream overrides *"skills with the same name"*, but
# ``name`` is an Agent Skills manifest field rather than a Deep Agents spelling:
# it moves on the specification's clock, exactly as ``SKILL.md`` itself does in
# :mod:`skillspector.deepagents.signals`.
ROOT_DIR: Final[str] = "root_dir"

# The list of subagent definitions the agent delegates to. A custom subagent
# does not inherit the main agent's Skills, so a definition written without a
# `SKILLS` key of its own runs without them.
#
# The keys a definition is written with -- the identifier it is named by, the
# description it is chosen on, the prompt it runs -- are deliberately *not*
# inventoried beside it. The captured reference documents this argument in prose
# only and shows no example of the shape, so those spellings would be asserted
# rather than captured; `DA-SUBAGENT-SKILLS` therefore reads one key it already
# owns and reports a line rather than a name.
SUBAGENTS: Final[str] = "subagents"

# -- Homonyms: owned here, exempt from the sweep ------------------------------ #
#
# All four are ordinary English words this repository already writes inline for
# unrelated reasons -- an Agent Skills manifest field, a discovery directory
# name, a CLI report key, the ``mode=`` of a call to ``open``, the ``write`` of
# an MCP capability map. See the module docstring: the exemption is asserted
# against real occurrences elsewhere in the tree, not merely declared.

# The Skill source paths the agent is given.
SKILLS: Final[str] = "skills"

# The declarative rules that decide what the agent may do to those paths.
PERMISSIONS: Final[str] = "permissions"

# What a permission rule does where it applies.
MODE: Final[str] = "mode"

# The operation a Skill file is rewritten by, and therefore the only one
# ``DA-SKILL-WRITABLE`` asks a rule about.
WRITE: Final[str] = "write"
