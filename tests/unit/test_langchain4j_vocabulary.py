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

"""``skillspector.langchain4j.vocabulary`` is the only home for an upstream spelling.

The property asserted here -- "this literal exists nowhere else" -- has no
behavioral manifestation, so no existing seam can observe it. A LangChain4j
release that renames a type breaks a Rule *silently*: the Scan succeeds, the
Analyzer reports itself as having run, and the report reads as clean. Keeping
the spellings in one file is what makes that rename a one-file edit, and this
module is what keeps them there.

Read as source text rather than as imported values because the leak being
guarded against is a source-level one: a contributor writing ``"ShellSkills"``
inline is not observable from the outside.

**Scope of the assertion.** A spelling is caught when it is written as a literal
of its own -- the shape a matcher takes, and the shape every leak this Spec
relocated had. A spelling embedded in a longer literal is not caught, because
the Finding messages in ``framework_langchain4j`` legitimately quote type names
in prose (*"McpToolProvider is built without a toolFilter"*) and containment
cannot tell the two apart. Regex-escaped forms *are* caught, so recomposing
``re.compile(r"dev\\.langchain4j")`` inline fails the same way the plain
spelling does.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

from skillspector.langchain4j import vocabulary

_SRC = Path(__file__).resolve().parents[2] / "src" / "skillspector"

# The module under guard is excluded: it is the home, not a leak site.
_VOCABULARY = _SRC / "langchain4j" / "vocabulary.py"

# Every module that matches on a LangChain4j spelling. ``framework.py`` is here
# because detection reads the same inventory; ``repository_scan.py`` is not,
# and ``TestScope`` records why.
_GUARDED_FILES: tuple[Path, ...] = (
    *sorted(path for path in (_SRC / "langchain4j").glob("*.py") if path != _VOCABULARY),
    _SRC / "framework.py",
    _SRC / "nodes" / "analyzers" / "framework_langchain4j.py",
)

# Released versions, not spellings a Rule matches on. Left out so the inventory
# stays derived from the module rather than restated here.
_NOT_A_SPELLING = frozenset({"OBSERVED_VERSION_RANGE"})

# tree-sitter's Java grammar names its own fields, and two of them collide with
# LangChain4j setter names by coincidence: ``child_by_field_name("name")`` asks
# the parser for a node's name field, not for ``Skill.builder().name(...)``.
# Excluded by call site rather than by spelling, so a genuine ``"name"`` leak
# anywhere else still fails.
_GRAMMAR_ACCESSOR = "child_by_field_name"


def _spellings() -> dict[str, str]:
    """Every inventoried spelling, mapped to the constant that declares it."""
    found: dict[str, str] = {}
    for constant, value in vars(vocabulary).items():
        if constant.startswith("_") or constant in _NOT_A_SPELLING:
            continue
        if isinstance(value, str):
            members: tuple[object, ...] = (value,)
        elif isinstance(value, frozenset | tuple):
            members = tuple(value)
        else:
            continue
        # First declaration wins, so a spelling that also appears in a
        # collection is reported against the constant that names it alone.
        for member in members:
            if isinstance(member, str):
                found.setdefault(member, constant)
    return found


def _exempt(tree: ast.Module) -> set[int]:
    """String nodes that are documentation or tree-sitter grammar vocabulary."""
    exempt: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                exempt.add(id(body[0].value))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == _GRAMMAR_ACCESSOR
        ):
            exempt.update(id(argument) for argument in node.args)
    return exempt


def _own_literals(path: Path) -> list[tuple[int, str]]:
    """Every ``(line, text)`` string literal in *path* that is not exempt."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    exempt = _exempt(tree)
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in exempt
    ]


def leaks(path: Path) -> list[str]:
    """Every inventoried spelling *path* writes out instead of importing."""
    spellings = _spellings()
    escaped = {re.escape(spelling): spelling for spelling in spellings}
    reported = []
    for line, literal in _own_literals(path):
        spelling = literal if literal in spellings else escaped.get(literal)
        if spelling is None:
            continue
        reported.append(
            f"{path.name}:{line} writes {literal!r} inline; it belongs to "
            f"skillspector.langchain4j.vocabulary.{spellings[spelling]} -- import it from there"
        )
    return reported


class TestScope:
    """The guard covers what it claims to, so a pass is not vacuous."""

    def test_every_guarded_file_exists(self) -> None:
        missing = [str(path) for path in _GUARDED_FILES if not path.is_file()]
        assert not missing, f"guarded files no longer exist: {missing}"

    def test_the_guarded_set_names_the_analyzer_and_detection(self) -> None:
        names = {path.name for path in _GUARDED_FILES}
        assert {"framework.py", "framework_langchain4j.py", "signals.py"} <= names

    def test_the_inventory_is_not_empty(self) -> None:
        # Twenty distinct spellings at the time #44 landed. A collapse to
        # near-zero would make every assertion below pass while guarding
        # nothing, so the floor is asserted rather than the exact count.
        assert len(_spellings()) >= 16

    def test_a_spelling_written_inline_is_reported(self, tmp_path: Path) -> None:
        leaked = tmp_path / "leaked.py"
        leaked.write_text(
            '"""A module whose docstring names ShellSkills harmlessly."""\n'
            "SHELL = 'ShellSkills'\n",
            encoding="utf-8",
        )
        reported = leaks(leaked)
        assert len(reported) == 1
        assert "ShellSkills" in reported[0]
        assert "SHELL_SKILLS_TYPE" in reported[0]
        assert "leaked.py:2" in reported[0]

    def test_a_regex_escaped_spelling_is_reported(self, tmp_path: Path) -> None:
        leaked = tmp_path / "escaped.py"
        leaked.write_text('COORDINATE = r"dev\\.langchain4j"\n', encoding="utf-8")
        assert "GROUP_COORDINATE" in "".join(leaks(leaked))

    def test_a_grammar_field_name_is_not_reported(self, tmp_path: Path) -> None:
        # The control for the exemption: the same literal outside the accessor
        # is a leak, inside it is not.
        allowed = tmp_path / "grammar.py"
        allowed.write_text("x = node.child_by_field_name('name')\n", encoding="utf-8")
        assert leaks(allowed) == []

        forbidden = tmp_path / "setter.py"
        forbidden.write_text("x = definition.argument('name')\n", encoding="utf-8")
        assert "NAME_SETTER" in "".join(leaks(forbidden))


class TestSingleHome:
    """No module outside the inventory writes an upstream spelling."""

    @pytest.mark.parametrize("path", _GUARDED_FILES, ids=lambda path: path.name)
    def test_no_module_writes_a_spelling_inline(self, path: Path) -> None:
        assert leaks(path) == []

    def test_the_inventory_declares_every_spelling_it_claims(self) -> None:
        declared = _spellings()
        for spelling in ("ShellSkills", "langchain4j-experimental-skills-shell", "dev.langchain4j"):
            assert spelling in declared


class TestParserFree:
    """Importing the inventory must not pull tree-sitter in.

    The Analyzer decides applicability before reaching for a parser, and
    detection reads this inventory on *every* Scan. An import here would move
    tree-sitter to the top of both paths and undo that ordering.
    """

    @staticmethod
    def _imports_tree_sitter(module: str) -> bool:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import importlib, sys; importlib.import_module('{module}'); "
                "print('tree_sitter' in sys.modules)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() == "True"

    def test_importing_the_inventory_does_not_import_the_parser(self) -> None:
        assert not self._imports_tree_sitter("skillspector.langchain4j.vocabulary")

    def test_importing_detection_does_not_import_the_parser(self) -> None:
        assert not self._imports_tree_sitter("skillspector.framework")

    def test_a_rule_module_does_import_the_parser(self) -> None:
        # The control. Without it the two assertions above would also pass if
        # the subprocess never imported anything at all.
        assert self._imports_tree_sitter("skillspector.langchain4j.skill_definitions")
