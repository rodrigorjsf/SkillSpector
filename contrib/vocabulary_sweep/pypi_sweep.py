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

"""Sweep every published ``deepagents`` release for the spellings the Rules match.

Reads the wheels PyPI serves, not the documentation. Each wheel's Python sources
are parsed with :mod:`ast`, and a spelling counts as observed in a release only
when it occurs in the role :mod:`contrib.vocabulary_sweep.roles` assigns it --
defined as a name, bound as a parameter or field, or written as a string value.

**What "in scope" means, so the next sweep is comparable.** Final releases only:
every version whose identifier is three dotted integers with nothing appended.
The pre-releases PyPI also serves for this project -- ``0.7.0b1``, ``0.0.11rc1``
and their kind -- are excluded, because a spelling that appeared in one and was
gone by the final release was never published as upstream's API. This is the one
place the rule differs from the LangChain4j sweep, where ``-betaNN`` is not a
pre-release marker but part of how every release of that artifact is named.
"""

from __future__ import annotations

import ast
import io
import json
import re
import urllib.request
import warnings
import zipfile
from dataclasses import dataclass
from typing import Final

from contrib.vocabulary_sweep.roles import DEEPAGENTS_ROLES, Role, assign
from skillspector.deepagents import vocabulary

_INDEX: Final[str] = "https://pypi.org/pypi/{distribution}/json"

# A final release: three dotted integers and nothing else. `0.7.0b1` and
# `0.0.11rc1` are the shapes this excludes. See the module docstring.
_FINAL_RELEASE: Final[re.Pattern[str]] = re.compile(r"\d+\.\d+\.\d+")


@dataclass(frozen=True)
class Occurrences:
    """Every name and value one release's sources write, grouped by role."""

    defined: frozenset[str]
    bound: frozenset[str]
    literal: frozenset[str]

    def carries(self, spelling: str, role: Role) -> bool:
        """Whether the release writes *spelling* in *role*."""
        if role is Role.DEFINED_NAME:
            return spelling in self.defined
        if role is Role.BOUND_NAME:
            return spelling in self.bound
        if role is Role.LITERAL_VALUE:
            return spelling in self.literal
        # DISTRIBUTION is observed from the index, NOT_MEASURED from nowhere.
        # Neither is a question about this archive's contents.
        return False


class _Reader(ast.NodeVisitor):
    """Collects the three role shapes out of one module's syntax tree.

    Deliberately syntactic. Importing a release to introspect it would run
    arbitrary published code and would need every one of its dependencies
    installed at the version it expected -- for 78 releases spanning a year.
    """

    def __init__(self) -> None:
        self.defined: set[str] = set()
        self.bound: set[str] = set()
        self.literal: set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802 -- ast API
        self.defined.add(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 -- ast API
        self.defined.add(node.name)
        self._parameters(node.args)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802 -- ast API
        self.defined.add(node.name)
        self._parameters(node.args)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802 -- ast API
        # An alias -- `create_deep_agent = _create` -- defines the name just as
        # a `def` does, and re-exports are how a package moves an entry point.
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined.add(target.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802 -- ast API
        # A declared field: how a dataclass, a TypedDict and a Pydantic model all
        # spell the arguments they are constructed with.
        if isinstance(node.target, ast.Name):
            self.bound.add(node.target.id)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802 -- ast API
        # A name re-exported from a submodule is still a name this distribution
        # publishes, and `deepagents/__init__.py` is written that way.
        for alias in node.names:
            self.defined.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        # A keyword argument at a call site inside the distribution: how the
        # package's own code passes what upstream documents as an argument.
        if node.arg is not None:
            self.bound.add(node.arg)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802 -- ast API
        if isinstance(node.value, str):
            self.literal.add(node.value)
        self.generic_visit(node)

    def _parameters(self, args: ast.arguments) -> None:
        every = (
            *args.posonlyargs,
            *args.args,
            *args.kwonlyargs,
            *([args.vararg] if args.vararg else []),
            *([args.kwarg] if args.kwarg else []),
        )
        self.bound.update(argument.arg for argument in every)


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 -- https, fixed index
        return bytes(response.read())


def releases_in_scope(distribution: str) -> dict[str, str]:
    """Every final release of *distribution*, oldest first, mapped to its wheel URL."""
    index = json.loads(_fetch(_INDEX.format(distribution=distribution)))
    published: dict[str, str] = {}
    for version, files in index["releases"].items():
        if not _FINAL_RELEASE.fullmatch(version):
            continue
        wheels = [entry["url"] for entry in files if entry["filename"].endswith(".whl")]
        if wheels:
            published[version] = wheels[0]
    return {
        version: published[version]
        for version in sorted(published, key=lambda text: tuple(int(p) for p in text.split(".")))
    }


def read_release(wheel_url: str) -> Occurrences:
    """Every role shape one release's wheel writes, across all its Python sources."""
    reader = _Reader()
    with zipfile.ZipFile(io.BytesIO(_fetch(wheel_url))) as archive:
        for name in archive.namelist():
            if not name.endswith(".py"):
                continue
            source = archive.read(name).decode("utf-8", errors="replace")
            try:
                # Early releases contain regex literals written without a raw
                # prefix. That is upstream's warning to answer, not this sweep's
                # output to carry.
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", SyntaxWarning)
                    tree = ast.parse(source)
            except SyntaxError:
                # A release built for a newer Python than this interpreter
                # parses. Skipping the file is honest -- and the caller sees it
                # as an absence to explain rather than as silence, because the
                # spellings it held will read as absent for that release only.
                continue
            reader.visit(tree)
    return Occurrences(
        defined=frozenset(reader.defined),
        bound=frozenset(reader.bound),
        literal=frozenset(reader.literal),
    )


def sweep() -> dict[str, dict[str, dict[str, bool]]]:
    """The distribution's own history, spelling by spelling. Name -> spelling -> version.

    One distribution publishes every Deep Agents spelling, so the outer mapping
    has a single key. It is the same shape the Maven sweep returns over four
    artifacts, so one report reads both.
    """
    assigned = assign(vocabulary, DEEPAGENTS_ROLES)
    distribution = releases_in_scope(vocabulary.DISTRIBUTION)
    observed: dict[str, dict[str, bool]] = {spelling: {} for spelling in assigned}
    for version, wheel_url in distribution.items():
        release = read_release(wheel_url)
        for spelling, (role, _constant) in assigned.items():
            carried = (
                # The distribution name is the index entry that served the
                # wheel, so a release existing at all is the observation.
                True if role is Role.DISTRIBUTION else release.carries(spelling, role)
            )
            observed[spelling][version] = carried
    return {vocabulary.DISTRIBUTION: observed}
