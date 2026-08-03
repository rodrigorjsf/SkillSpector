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

"""``skillspector.deepagents.vocabulary`` is the only home for a Deep Agents spelling.

Why the inventory exists is
``docs/adr/0008-deepagents-analyzer-resolves-one-module-deep.md``, which copies
``docs/adr/0005-langchain4j-upstream-vocabulary.md``'s argument for the Python
track. Why it needs a test of its own is that the property -- "this literal
exists nowhere else" -- has no behavioral manifestation, so no existing seam can
observe it.

Read as source text rather than as imported values for the same reason: a
contributor writing ``"create_deep_agent"`` inline produces working code, and
nothing about the running system looks different.

**Scope of the sweep.** The whole of ``src/skillspector``, minus two files. The
inventory module itself is the home rather than a leak site. ``framework.py`` is
excluded *by decision*, not by oversight: ADR 0008 rejected sharing one
inventory between detection and the Rules, so detection's copy of these
spellings is a second copy on purpose, and it is the file that holds
``Framework.DEEPAGENTS``'s own value. Sweeping the rest of the tree rather than a
hand-maintained list is stricter than the LangChain4j guard, which has to be
edited whenever a coupled module appears elsewhere.

**Scope of the assertion.** A spelling is caught when it is written as a literal
of its own -- the shape a matcher takes. A spelling embedded in a longer literal
is not caught, because a Finding message legitimately quotes an upstream name in
prose and containment cannot tell the two apart. Regex-escaped forms *are*
caught, so recomposing ``re.compile(r"create_deep_agent")`` inline fails the
same way the plain spelling does.

**Homonyms are exempt from the sweep, on evidence.** Two of the inventory's
spellings are ordinary English words this repository already writes inline for
reasons that have nothing to do with Deep Agents -- an Agent Skills manifest
field, a discovery directory name, a CLI report key. Demanding those call sites
import a Deep Agents constant would be wrong rather than strict, so the
inventory still owns them and the sweep skips them. What keeps that from being a
hole is ``TestHomonyms``: each exempted spelling must really occur inline
somewhere the sweep covers, so an exemption that stops being a homonym stops
being allowed.

``_own_literals`` is imported from the LangChain4j guard rather than copied.
"A literal of its own" is one definition, and two AST readers of it would drift
into two guards that disagree about what a leak looks like. What comes with it
is that reader's tree-sitter exemption, which no Deep Agents module can trip.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType

import pytest

from skillspector.deepagents import vocabulary
from tests.unit.test_langchain4j_vocabulary import _own_literals

_SRC = Path(__file__).resolve().parents[2] / "src" / "skillspector"

# The module under guard is excluded: it is the home, not a leak site.
_VOCABULARY = _SRC / "deepagents" / "vocabulary.py"

# Detection keeps its own copy, by ADR 0008. See the module docstring.
_DETECTION = _SRC / "framework.py"

_GUARDED_FILES: tuple[Path, ...] = tuple(
    sorted(path for path in _SRC.rglob("*.py") if path not in (_VOCABULARY, _DETECTION))
)

# Every spelling this inventory holds today, as an exact set. Asserted rather
# than counted loosely: a loop over a silently emptied inventory would pass
# every assertion below while guarding nothing.
_EXPECTED_SPELLINGS = {
    "create_deep_agent",
    "deepagents",
    "FilesystemPermission",
    "backend",
    "CompositeBackend",
    "StoreBackend",
    "StateBackend",
    "FilesystemBackend",
    "routes",
    "skills",
    "permissions",
}

# The two homonyms. Owned by the inventory, skipped by the sweep, and required
# by ``TestHomonyms`` below to really be homonyms. See the module docstring.
_HOMONYMS = {"skills", "permissions"}


def _read_inventory(module: ModuleType = vocabulary) -> tuple[dict[str, str], list[str]]:
    """Every inventoried spelling by declaring constant, and what could not be read.

    The second return value is the point. A constant holding something this
    reader does not understand contributes no spelling, so nothing guards it --
    and a guard that quietly covers less than it claims is worse than none.

    Keyed off ``__annotations__`` rather than a leading-underscore convention, so
    imported names such as ``Final`` are not mistaken for inventory entries.
    """
    spellings: dict[str, str] = {}
    unreadable: list[str] = []
    for constant, value in vars(module).items():
        if constant not in module.__annotations__:
            continue
        if isinstance(value, str):
            members: tuple[object, ...] = (value,)
        elif isinstance(value, frozenset | tuple | set | list):
            members = tuple(value)
        else:
            unreadable.append(constant)
            continue
        held = [member for member in members if isinstance(member, str)]
        if not held:
            unreadable.append(constant)
        # First declaration wins, so a spelling that also appears in a
        # collection is reported against the constant that names it alone.
        for member in held:
            spellings.setdefault(member, constant)
    return spellings, unreadable


def _spellings() -> dict[str, str]:
    """Every inventoried spelling, mapped to the constant that declares it."""
    return _read_inventory()[0]


def _swept_spellings() -> dict[str, str]:
    """The inventory the sweep enforces: everything but the homonyms."""
    return {
        spelling: constant
        for spelling, constant in _spellings().items()
        if spelling not in _HOMONYMS
    }


def leaks(path: Path, spellings: dict[str, str] | None = None) -> list[str]:
    """Every inventoried spelling *path* writes out instead of importing.

    *spellings* is injectable so the mutation proofs below can run the real
    reader against a planted inventory, rather than trusting that a guard which
    reports nothing is a guard that looked. It defaults to the swept inventory
    rather than the whole one: a homonym is not a leak.
    """
    spellings = _swept_spellings() if spellings is None else spellings
    escaped = {re.escape(spelling): spelling for spelling in spellings}
    reported = []
    for line, literal in _own_literals(path):
        spelling = literal if literal in spellings else escaped.get(literal)
        if spelling is None:
            continue
        reported.append(
            f"{path.name}:{line} writes {literal!r} inline; it belongs to "
            f"skillspector.deepagents.vocabulary.{spellings[spelling]} -- import it from there"
        )
    return reported


class TestScope:
    """The guard covers what it claims to, so a pass is not vacuous."""

    def test_the_inventory_holds_exactly_the_spellings_it_claims(self) -> None:
        assert set(_spellings()) == _EXPECTED_SPELLINGS

    def test_every_declared_constant_is_readable(self) -> None:
        _found, unreadable = _read_inventory()
        assert unreadable == [], (
            f"{unreadable} hold no spelling this guard can read, so nothing guards them. "
            "The reader understands a string, or a tuple, set, list or frozenset of them "
            "-- teach _read_inventory to read the new shape."
        )

    def test_an_unreadable_constant_is_reported(self) -> None:
        # The control for the assertion above: without it, a reader that
        # returned an empty list unconditionally would look just as green.
        stub = ModuleType("stub_vocabulary")
        stub.__annotations__ = {"CALL": "Final[str]", "RETRY_LIMIT": "Final[int]"}
        stub.CALL = "create_deep_agent"
        stub.RETRY_LIMIT = 3

        spellings, unreadable = _read_inventory(stub)
        assert unreadable == ["RETRY_LIMIT"]
        assert spellings == {"create_deep_agent": "CALL"}

    def test_the_swept_set_names_the_analyzer_and_the_package(self) -> None:
        # Named by full path rather than by basename: `signals.py` and
        # `__init__.py` exist under `langchain4j/` too, so a basename check
        # would pass on a sweep that never reached this package.
        assert {
            _SRC / "nodes" / "analyzers" / "framework_deepagents.py",
            _SRC / "deepagents" / "signals.py",
            _SRC / "deepagents" / "__init__.py",
        } <= set(_GUARDED_FILES)

    def test_the_sweep_excludes_only_the_home_and_detection(self) -> None:
        every = set(_SRC.rglob("*.py"))
        assert every - set(_GUARDED_FILES) == {_VOCABULARY, _DETECTION}


class TestHomonyms:
    """An exemption is allowed only while the word really is a homonym."""

    def test_every_homonym_is_inventoried(self) -> None:
        assert _HOMONYMS <= set(_spellings())

    def test_the_sweep_enforces_everything_that_is_not_a_homonym(self) -> None:
        assert set(_swept_spellings()) == set(_spellings()) - _HOMONYMS

    @pytest.mark.parametrize("spelling", sorted(_HOMONYMS))
    def test_a_homonym_really_occurs_inline_elsewhere(self, spelling: str) -> None:
        """The evidence, rather than the claim.

        A spelling is exempt because unrelated modules legitimately write it --
        an Agent Skills manifest field, a discovery directory name, a CLI report
        key. If none of them does any more, the exemption is a hole rather than
        a homonym, and this is where that is noticed.
        """
        writers = [
            path
            for path in _GUARDED_FILES
            if not path.is_relative_to(_SRC / "deepagents")
            and any(literal == spelling for _line, literal in _own_literals(path))
        ]
        assert writers, (
            f"{spelling!r} is exempted from the sweep as a homonym, but no module outside "
            "skillspector.deepagents writes it inline any more. Drop it from _HOMONYMS so the "
            "guard enforces it like every other spelling."
        )


class TestTheGuardFails:
    """Mutation proofs, in both directions.

    A guard is only evidence if it can be made to fail. One proof plants a
    forbidden spelling and requires a report; the other empties the inventory
    and requires the assertions above to stop passing.
    """

    def test_a_spelling_written_inline_is_reported(self, tmp_path: Path) -> None:
        leaked = tmp_path / "leaked.py"
        leaked.write_text(
            '"""A module whose docstring names create_deep_agent harmlessly."""\n'
            "CALL = 'create_deep_agent'\n",
            encoding="utf-8",
        )
        reported = leaks(leaked)
        assert len(reported) == 1
        assert "CREATE_DEEP_AGENT" in reported[0]
        assert "leaked.py:2" in reported[0]

    def test_a_regex_escaped_spelling_is_reported(self, tmp_path: Path) -> None:
        leaked = tmp_path / "escaped.py"
        leaked.write_text('CALL = re.compile(r"create_deep_agent")\n', encoding="utf-8")
        assert "CREATE_DEEP_AGENT" in "".join(leaks(leaked))

    def test_an_emptied_inventory_reports_nothing_and_fails_the_scope_test(
        self, tmp_path: Path
    ) -> None:
        """The direction a count assertion alone would miss.

        With no spellings, every ``leaks()`` call returns an empty list and
        ``TestSingleHome`` below would pass over a guard that looked at nothing.
        ``test_the_inventory_holds_exactly_the_spellings_it_claims`` is what
        fails instead -- proved here rather than assumed.
        """
        leaked = tmp_path / "leaked.py"
        leaked.write_text("CALL = 'create_deep_agent'\n", encoding="utf-8")

        assert leaks(leaked, spellings={}) == []

        empty = ModuleType("empty_vocabulary")
        empty.__annotations__ = {}
        assert set(_read_inventory(empty)[0]) != _EXPECTED_SPELLINGS


class TestSingleHome:
    """No module outside the inventory writes a Deep Agents spelling."""

    @pytest.mark.parametrize("path", _GUARDED_FILES, ids=lambda path: str(path))
    def test_no_module_writes_a_spelling_inline(self, path: Path) -> None:
        assert leaks(path) == []
