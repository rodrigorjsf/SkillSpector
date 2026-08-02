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

"""Which Framework a scanned tree is written against.

Phase 1 of ``docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md``. Detection is pure over
``components`` and ``file_cache`` (§3.2): it does no I/O, cannot fail a Scan,
and is read by nothing today. The key exists so the gated Analyzers of later
phases have something to gate on, and so the Behavior Snapshot can prove
detection never drifts on an input scanned today.

Enum rather than the bare ``str`` the design document writes, mirroring
``skillspector.manifest_status``: a misspelled literal in a later Analyzer's
gate would fail by never opening the gate, and ADR 0002 has that gate decline
without a ledger event -- so the failure would be silent. The serialized values
are §3.1's, unchanged.

**Ambiguity resolves to** ``AGENT_SKILLS``. When the signals of two Frameworks
are both present -- a polyglot repository whose ``pom.xml`` names
``dev.langchain4j`` and whose ``pyproject.toml`` names ``deepagents`` -- two
matches is doubt, and §3.2's conservative rule ("when in doubt,
``agent_skills``") applies literally.

The bad consequence is known rather than discovered later: a genuinely
LangChain4j repository that happens to carry ``deepagents`` in a test dependency
loses Framework analysis entirely, and loses it *in silence*, because the gate
declines without a ledger event. This is accepted while no Analyzer reads the
key, so nothing is lost today. **Reopen trigger:** the first real repository
observed to detect ambiguously. Two alternatives were rejected and should not be
relitigated without that trigger -- a fixed precedence between the two
Frameworks (deterministic, but an arbitrary order becomes silent law) and
returning a set of Frameworks (the right answer for a real polyglot world, and
speculative generality before the first Analyzer exists).

Detection is textual and reads only the files a signal names. It therefore does
not distinguish code from comments inside a ``.py`` or ``.java`` file, while a
mention in prose -- a ``README.md`` naming ``deepagents`` -- is not a signal at
all, because no signal names markdown.

Two signals are read more narrowly than §3.2's table spells them, both in the
conservative direction the same section mandates. A requirement naming
``deepagents-contrib`` is a *different* distribution and is not a Deep Agents
signal; and an import is matched at the start of a line, so ``vendor.deepagents``
and a package named inside a string are not signals either. Both narrowings can
only ever return ``AGENT_SKILLS`` where a looser reading would return a
Framework, so they cannot make an existing Scan detect as something new.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Final


class Framework(StrEnum):
    """The Framework a scanned tree is written against.

    ``AGENT_SKILLS`` is both a real answer and the conservative default: it is
    what every input scanned before this module existed detects as.
    """

    AGENT_SKILLS = "agent_skills"
    LANGCHAIN4J = "langchain4j"
    DEEPAGENTS = "deepagents"


# -- LangChain4j signals ---------------------------------------------------- #

# Matched on basename at any depth: a multi-module Maven build declares the
# dependency in a child module's ``pom.xml``, not only at the scan root.
_JVM_BUILD_FILES: Final[tuple[str, ...]] = ("pom.xml",)
_JVM_BUILD_PREFIX: Final[str] = "build.gradle"
_JVM_SOURCE_SUFFIXES: Final[tuple[str, ...]] = (".java", ".kt")

# The Maven group id, as it appears in a build file's dependency block.
_LANGCHAIN4J_COORDINATE: Final[re.Pattern[str]] = re.compile(r"dev\.langchain4j")
# An import of the package, Java (optionally static) or Kotlin. Anchored to the
# start of a line so a mention inside a string or a comment tail is not a
# signal.
_LANGCHAIN4J_IMPORT: Final[re.Pattern[str]] = re.compile(
    r"^\s*import\s+(?:static\s+)?dev\.langchain4j\.", re.MULTILINE
)
# The layout a LangChain4j project keeps its Skills in.
_LANGCHAIN4J_SKILL_LAYOUT: Final[str] = "src/main/resources/skills/"


# -- Deep Agents signals ---------------------------------------------------- #

_PYTHON_REQUIREMENT_FILES: Final[tuple[str, ...]] = ("pyproject.toml",)
_PYTHON_REQUIREMENT_PREFIX: Final[str] = "requirements"
_PYTHON_REQUIREMENT_SUFFIX: Final[str] = ".txt"
_PYTHON_SOURCE_SUFFIX: Final[str] = ".py"

# The distribution name, bounded so ``deepagents-contrib`` is not a match: a
# different distribution is a different Framework question.
_DEEPAGENTS_DISTRIBUTION: Final[re.Pattern[str]] = re.compile(r"(?<![\w.-])deepagents(?![\w-])")
# A top-level import of the package. ``import vendor.deepagents`` is not one.
_DEEPAGENTS_IMPORT: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:from|import)\s+deepagents\b", re.MULTILINE
)
# The constructor the framework is used through.
_DEEPAGENTS_CALL: Final[re.Pattern[str]] = re.compile(r"\bcreate_deep_agent\s*\(")


def _basename(path: str) -> str:
    """Return the final segment of a component path.

    ``components`` always uses forward slashes -- ``build_context`` normalizes
    them so the paths stay portable as dict keys and SARIF locations.
    """
    return path.rsplit("/", 1)[-1]


def _is_jvm_build_file(path: str) -> bool:
    name = _basename(path)
    return name in _JVM_BUILD_FILES or name.startswith(_JVM_BUILD_PREFIX)


def _is_python_requirement_file(path: str) -> bool:
    name = _basename(path)
    return name in _PYTHON_REQUIREMENT_FILES or (
        name.startswith(_PYTHON_REQUIREMENT_PREFIX) and name.endswith(_PYTHON_REQUIREMENT_SUFFIX)
    )


def _signals_langchain4j(components: Iterable[str], file_cache: Mapping[str, str]) -> bool:
    """Whether any §3.2 LangChain4j signal is present."""
    for path in components:
        if _LANGCHAIN4J_SKILL_LAYOUT in path:
            return True
    for path, content in file_cache.items():
        if _is_jvm_build_file(path) and _LANGCHAIN4J_COORDINATE.search(content):
            return True
        if path.endswith(_JVM_SOURCE_SUFFIXES) and _LANGCHAIN4J_IMPORT.search(content):
            return True
    return False


def _signals_deepagents(file_cache: Mapping[str, str]) -> bool:
    """Whether any §3.2 Deep Agents signal is present.

    Takes no ``components``: every Deep Agents signal is a content one, unlike
    LangChain4j's Maven resource layout, which is a path.
    """
    for path, content in file_cache.items():
        if _is_python_requirement_file(path) and _DEEPAGENTS_DISTRIBUTION.search(content):
            return True
        if path.endswith(_PYTHON_SOURCE_SUFFIX) and (
            _DEEPAGENTS_IMPORT.search(content) or _DEEPAGENTS_CALL.search(content)
        ):
            return True
    return False


def detect_framework(components: Iterable[str], file_cache: Mapping[str, str]) -> Framework:
    """Detect the Framework of one scanned tree.

    ``components`` carries every discovered path; ``file_cache`` carries the
    content of the ones that could be read. The two are not interchangeable -- a
    signal file listed but unreadable carries no signal, because there is
    nothing to read.

    Returns ``AGENT_SKILLS`` when no signal fires *and* when both fire; the
    module docstring records why the second case is not a precedence rule.
    """
    langchain4j = _signals_langchain4j(components, file_cache)
    deepagents = _signals_deepagents(file_cache)
    if langchain4j and not deepagents:
        return Framework.LANGCHAIN4J
    if deepagents and not langchain4j:
        return Framework.DEEPAGENTS
    return Framework.AGENT_SKILLS
