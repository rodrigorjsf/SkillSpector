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

"""Every LangChain4j spelling SkillSpector matches on, and nothing else.

LangChain4j's Skills API is published as beta -- upstream's own words, captured
in ``docs/references/langchain4j-skills.md``, are *"The Skills API is
experimental. APIs and behavior may still change in future releases."* So the
type names, method names and artifact ids below are expected to move.

When one moves, a Rule that matches it stops producing Findings and **nothing
says so**. The Scan still succeeds, the Analyzer still reports itself as having
run, and the report reads as clean. That is why the spellings live in one file
rather than in the six modules that consume them, and why
``tests/unit/test_langchain4j_vocabulary.py`` fails the build when one is
written inline somewhere else.

Deliberately parser-free and import-free. The Analyzer decides applicability
before importing tree-sitter (see :mod:`skillspector.langchain4j`), and
``skillspector.framework`` reads its LangChain4j signals from here during
detection, which runs on every Scan.

Upgrading the LangChain4j dependency
------------------------------------

1. Read the release's own notes and ``docs/references/langchain4j-skills.md``
   against the entries below. Each carries the upstream section it was captured
   from and the version range it was observed across, so a rename is either in
   this file or irrelevant to SkillSpector.
2. Edit what moved, here and only here.
3. ``make test-unit`` -- the enforcement test proves the inventory is still the
   single home, and the Analyzer suite proves the Rules still match.
4. ``make update-snapshots`` and read ``git status``. A clean tree means no
   Scan's observable output changed. A snapshot diff means a Rule started or
   stopped matching, and is the thing to explain before merging.

What is *not* here: Maven and Gradle build file names, the Java source suffix,
the generic ``builder()`` / ``toBuilder()`` entry methods, and the bare Maven
resource root. Those change on Maven's and Java's clock, not LangChain4j's, and
they stay in the modules that use them.

Provenance
----------

Captured from ``docs/references/langchain4j-skills.md`` (upstream
<https://docs.langchain4j.dev/tutorials/skills/>), and cross-checked against the
published Maven metadata of ``dev.langchain4j:langchain4j-skills`` and
``dev.langchain4j:langchain4j-experimental-skills-shell``.

Every published release was swept for the identifiers below: 17 versions,
``1.12.1-beta21`` through ``1.18.1-beta28``, the two Skills artifacts released
in lockstep. **No identifier here has ever been removed.** Two were added at
``1.13.0-beta23`` -- ``ClassPathSkillLoader`` and the ``tools`` builder argument
-- and each is annotated below.

Re-measured on 2026-08-03 by ``contrib/vocabulary_sweep``, under the procedure in
``docs/VOCABULARY_REMEASUREMENT.md``, which is also what obliges the next
re-measurement. That re-run confirmed the range and corrected the original claim
twice.

**The ``tools`` addition was invisible to the first measurement.** It compared
*class listings* between the first and latest release, and a builder argument
added to a class that already existed changes no listing. So the original record
said ``ClassPathSkillLoader`` was the only change; reading each release's own
method tables says otherwise, and this is the corrected claim.

**``toolFilter`` has never been published.** No release of ``langchain4j-mcp``
declares it -- the builder method is ``filter``, at ``1.12.1-beta21`` as at
``1.18.1-beta28``. It is in this inventory because upstream's Skills tutorial
writes ``.toolFilter(...)`` in an example that upstream's own MCP tutorial
contradicts. The spelling is left as it is here on purpose: what ``L4J-MCP-FILTER``
should match instead is a Rule change, tracked as issue #82, not a rename this
record can make quietly. See the constant's own comment.

``OBSERVED_VERSION_RANGE`` records the sweep so the stability claim is evidence
rather than assertion, and so a reader can tell at a glance how stale it is.
"""

from __future__ import annotations

from typing import Final

# The releases the sweep covered. Every *identifier* below -- the types, methods
# and builder arguments -- was observed across this whole range unless its own
# comment narrows it. The three entries under "Framework detection signals" are
# not identifiers and were not observed that way; their own section says how
# they were established instead.
OBSERVED_VERSION_RANGE: Final[tuple[str, str]] = ("1.12.1-beta21", "1.18.1-beta28")


# -- Defining a Skill in Java ------------------------------------------------ #
# Upstream: "Creating skills -- Programmatically".

# The two builders that define a Skill. ``SkillResource`` carries a Skill's
# attached files; ``Skill`` carries the Skill itself.
SKILL_BUILDER: Final[str] = "Skill"
SKILL_RESOURCE_BUILDER: Final[str] = "SkillResource"
SKILL_BUILDERS: Final[frozenset[str]] = frozenset({SKILL_BUILDER, SKILL_RESOURCE_BUILDER})

# The builder arguments that carry text a model reads. ``relativePath`` is not
# one of them: it names a file rather than instructions.
CONTENT_SETTER: Final[str] = "content"
NAME_SETTER: Final[str] = "name"
DESCRIPTION_SETTER: Final[str] = "description"
TEXT_SETTERS: Final[tuple[str, ...]] = (CONTENT_SETTER, NAME_SETTER, DESCRIPTION_SETTER)

# The builder argument that attaches a class's ``@Tool`` methods to a Skill.
# Added at 1.13.0-beta23, on ``AbstractSkill$BaseBuilder``; absent from
# 1.12.1-beta21 and 1.12.2-beta22. The 2026-08-02 measurement missed it because a
# builder argument added to an existing class changes no class listing.
TOOLS_SETTER: Final[str] = "tools"


# -- Loading a Skill from disk or the classpath ------------------------------ #
# Upstream: "Creating skills -- From the file system" and "From the classpath".

FILESYSTEM_SKILL_LOADER: Final[str] = "FileSystemSkillLoader"
# Added at 1.13.0-beta23; absent from 1.12.1-beta21 and 1.12.1-beta22.
CLASSPATH_SKILL_LOADER: Final[str] = "ClassPathSkillLoader"
SKILL_LOADERS: Final[frozenset[str]] = frozenset({FILESYSTEM_SKILL_LOADER, CLASSPATH_SKILL_LOADER})

LOAD_SKILLS_METHOD: Final[str] = "loadSkills"
LOAD_SKILL_METHOD: Final[str] = "loadSkill"
LOADER_METHODS: Final[frozenset[str]] = frozenset({LOAD_SKILLS_METHOD, LOAD_SKILL_METHOD})

# The directory a LangChain4j project conventionally keeps its Skills in, below
# the Maven resource root. The ``skills/`` segment is LangChain4j's convention;
# the prefix is Maven's, which is why the bare resource root is not inventoried
# here and stays with the module that resolves classpath loader paths.
#
# A documented convention rather than a class identifier, so the release sweep
# did not observe it either: it is upstream's own example layout under "From the
# classpath", unchanged across every capture of that page.
CLASSPATH_SKILL_LAYOUT: Final[str] = "src/main/resources/skills/"


# -- Shell mode -------------------------------------------------------------- #
# Upstream: "Modes -- Shell mode (experimental)". The highest-severity Rule in
# the Analyzer rests on these three spellings.

# The type that selects shell mode. ``Skills`` is the safe sibling.
SHELL_SKILLS_TYPE: Final[str] = "ShellSkills"

SHELL_COMMAND_CONFIG: Final[str] = "RunShellCommandToolConfig"
WORKING_DIRECTORY_SETTER: Final[str] = "workingDirectory"

# The Maven artifact id of shell mode. Its presence on the classpath is the
# capability. The only spelling ever published: 17 releases, the whole of
# ``OBSERVED_VERSION_RANGE``.
#
# It is also the one entry here that upstream has told us in advance it intends
# to change -- the artifact is named ``experimental``, and graduation drops that
# word. So the Rule does not match this literal; it matches
# ``SHELL_ARTIFACT_PATTERN`` below, which this spelling is one instance of.
# Kept inventoried because it is what a build file says today, and because the
# tests that prove the pattern still recognises the published artifact need a
# name for it.
SHELL_ARTIFACT_ID: Final[str] = "langchain4j-experimental-skills-shell"

# What ``L4J-SHELL``'s dependency half actually matches: any ``langchain4j-``
# artifact id whose own name contains ``shell``. Held as pattern *source* rather
# than a compiled pattern so this module stays import-free, and so the guard in
# ``tests/unit/test_langchain4j_vocabulary.py`` can read it like any other entry.
#
# Deliberately wider than the two spellings a graduation would produce.
# ``docs/adr/0007-l4j-shell-survives-the-graduation-rename.md`` records the
# measurement behind that: ``dev.langchain4j`` has never renamed an artifact out
# of ``experimental``, so the graduated spelling cannot be derived, only guessed
# -- and a pattern over the capability word needs no guess. The character class
# is the artifact-id alphabet, so a match is confined to one hyphenated token
# and ``langchain4j-skills``, the safe sibling, cannot satisfy it.
SHELL_ARTIFACT_PATTERN: Final[str] = r"langchain4j-[a-z0-9-]*shell[a-z0-9-]*"


# -- The tool surface -------------------------------------------------------- #
# Upstream: "Modes -- Skill-scoped tools", and LangChain4j's MCP tutorial.

# The annotation whose text a model is shown as a tool's description.
TOOL_ANNOTATION: Final[str] = "Tool"

MCP_TOOL_PROVIDER: Final[str] = "McpToolProvider"

# **Never published.** ``McpToolProvider.Builder`` declares ``filter`` and
# ``filterToolNames``, and has since ``1.12.1-beta21``; no release of
# ``langchain4j-mcp`` has ever declared ``toolFilter``. The spelling comes from
# upstream's Skills tutorial, whose MCP example writes ``.toolFilter(...)`` --
# contradicted by upstream's own MCP tutorial and by every jar it publishes.
#
# ``L4J-MCP-FILTER`` reports a ``McpToolProvider`` builder chain that never
# called this setter, so host code written against a *published* release is
# reported as unfiltered whatever it does. Left uncorrected here because
# changing it changes what a Scan reports, which the measurement this comment
# belongs to deliberately does not.
TOOL_FILTER_SETTER: Final[str] = "toolFilter"


# -- Framework detection signals --------------------------------------------- #
# Read by ``skillspector.framework`` as well as by this package. Detection and
# Analyzer applicability stay separate predicates; the *spelling* of a package
# name is one fact, not two.
#
# Upstream: the ``<groupId>`` of every dependency block under "Creating skills",
# and the imports of every example on that page. Unlike the entries above these
# are not class identifiers, so the class-listing sweep across the 17 releases
# did not observe them; they were read from the captured documentation and from
# the published Maven coordinates of both artifacts, which have carried this
# group id since their first release.

# The Maven group id, as it appears in a build file's dependency block.
GROUP_COORDINATE: Final[str] = "dev.langchain4j"
# The prefix of a Java or Kotlin import of the library. Trailing dot included:
# it is what separates the package from a differently-named sibling.
IMPORT_PREFIX: Final[str] = "dev.langchain4j."
