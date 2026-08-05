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

"""Which Components of a Scan the Deep Agents Analyzer opens.

One predicate, :func:`applicable_files`, and the narrowings taken from *its*
result. ``docs/adr/0006-langchain4j-applicability-is-what-it-opens.md`` is why
there is one rather than two: the gate tests this result for emptiness and the
planned work derives from the same result, so a Component the Analyzer opens is
always a Component it reports.

The file predicates mirror :mod:`skillspector.framework`'s rather than importing
them. Detection asks "is this tree Deep Agents at all"; this module asks "which
of its files do I open". The two questions drift apart as later Rules land -- the
``SKILL.md`` set below is already a difference -- and this repository merges
upstream, so coupling to a private helper of a phase-1 module is the wrong thing
to do.

None of the three file kinds is Deep Agents vocabulary, so none of them is
inventoried in :mod:`skillspector.deepagents.vocabulary`. ``.py`` and
``pyproject.toml`` move on Python packaging's clock, ``SKILL.md`` on the Agent
Skills specification's; ADR 0005 drew the same line for the Java suffix and the
Maven build file names.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

PYTHON_SUFFIX: Final[str] = ".py"

# Matched on basename at any depth: a Python monorepo declares its dependencies
# in a package's own ``pyproject.toml``, not only at the scan root.
_PYTHON_REQUIREMENT_FILES: Final[tuple[str, ...]] = ("pyproject.toml",)
_PYTHON_REQUIREMENT_PREFIX: Final[str] = "requirements"
_PYTHON_REQUIREMENT_SUFFIX: Final[str] = ".txt"

# The Agent Skills manifest. A Deep Agents Skill directory *is* an Agent Skills
# directory, and the ``name`` this Analyzer will read for the shadowing Rule
# lives in its frontmatter.
_SKILL_MANIFEST: Final[str] = "SKILL.md"


def _basename(path: str) -> str:
    """Return the final segment of a component path.

    ``file_cache`` keys always use forward slashes -- ``build_context``
    normalizes them so they stay portable as dict keys and SARIF locations.
    """
    return path.rsplit("/", 1)[-1]


def is_python_source(path: str) -> bool:
    """Whether *path* names a Python module."""
    return path.endswith(PYTHON_SUFFIX)


def is_python_requirement_file(path: str) -> bool:
    """Whether *path* names a file that can declare a Python dependency."""
    name = _basename(path)
    return name in _PYTHON_REQUIREMENT_FILES or (
        name.startswith(_PYTHON_REQUIREMENT_PREFIX) and name.endswith(_PYTHON_REQUIREMENT_SUFFIX)
    )


def is_skill_manifest(path: str) -> bool:
    """Whether *path* names an Agent Skills manifest."""
    return _basename(path) == _SKILL_MANIFEST


def applicable_files(file_cache: Mapping[str, str]) -> dict[str, str]:
    """The Components the Deep Agents Analyzer opens, by path.

    Applicability is this one predicate: a Python module, a Python requirement
    file, or an Agent Skills manifest.

    ``SKILL.md`` is in the set because the shadowing Rule confirms a duplicate
    Skill ``name`` across the sources of one ``skills=[...]`` list, and that name
    is in the manifest's frontmatter. ADR 0008 §3 decided it, and states the
    price: on a Scan whose Skill source paths cannot be mapped to disk -- the
    default backend being the likeliest case -- every ``SKILL.md`` is still
    opened, still reported, and still yields no verdict. Under ADR 0006 the
    alternative would be opening those files without reporting them.

    Reads ``file_cache`` rather than ``components`` on purpose: a component
    listed but unreadable has nothing to open. The content is whatever
    ``build_context`` cached, which is the full file -- the static runner's
    per-file character cap lives in the static runner and is not inherited here.

    Named for the word the Ledger already uses: an Analyzer with none of these
    reports ``no_applicable_files``, so the code and the report describe
    applicability in one vocabulary rather than two.
    """
    return {
        path: content
        for path, content in file_cache.items()
        if is_python_source(path) or is_python_requirement_file(path) or is_skill_manifest(path)
    }
