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

"""Offline proofs that the sweep discriminates, rather than reporting everything present.

The failure mode a sweep has is the same one the vocabulary guard has: it can
report a clean result because it looked at nothing. So each reader is run against
source that *does* write the spelling in role and source that writes it in some
other shape, and the two have to disagree.

Standalone rather than pytest, and outside ``testpaths``, matching
``contrib/batch_scan/tests``::

    python contrib/vocabulary_sweep/tests/test_readers.py

No network: the archive readers are exercised through the AST and class-file
layers they are built on, which is where the discrimination lives.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# The project root, so `contrib.` resolves when this runs as a script from
# anywhere. The same bootstrap `contrib/batch_scan/tests` uses.
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Every import below follows the path bootstrap above, which is what makes them
# resolvable when this file is run as a script.
from contrib.vocabulary_sweep import report  # noqa: E402
from contrib.vocabulary_sweep.pypi_sweep import Occurrences, _Reader  # noqa: E402
from contrib.vocabulary_sweep.roles import (  # noqa: E402
    DEEPAGENTS_ROLES,
    LANGCHAIN4J_ROLES,
    Role,
    assign,
)
from skillspector.deepagents import vocabulary as deepagents_vocabulary  # noqa: E402
from skillspector.langchain4j import vocabulary as langchain4j_vocabulary  # noqa: E402


def _read(source: str) -> Occurrences:
    reader = _Reader()
    reader.visit(ast.parse(source))
    return Occurrences(
        defined=frozenset(reader.defined),
        bound=frozenset(reader.bound),
        literal=frozenset(reader.literal),
    )


def test_a_python_name_is_read_in_its_own_role() -> None:
    """The whole point: a word in prose is not the word in role."""
    documented = _read('"""A module whose docstring mentions a keyword argument."""\n')
    assert not documented.bound
    assert not documented.defined

    declared = _read("def make(*, backing: int) -> None: ...\n")
    assert "backing" in declared.bound
    assert "make" in declared.defined
    assert "backing" not in declared.defined


def test_a_string_value_is_not_a_bound_name() -> None:
    """The three role shapes stay apart, or every spelling reads as present."""
    occurrences = _read("CHOICE = 'halt'\ndef run(*, halt: bool) -> None: ...\n")
    assert "halt" in occurrences.literal
    assert "halt" in occurrences.bound
    assert not _read("CHOICE = 'halt'\n").bound


def test_an_annotated_field_counts_as_bound() -> None:
    """How a dataclass, a TypedDict and a model all spell their arguments."""
    occurrences = _read("class Rule:\n    governs: list[str]\n")
    assert "governs" in occurrences.bound
    assert "Rule" in occurrences.defined


def test_a_role_map_covers_its_inventory_exactly() -> None:
    """Fails closed on both a new spelling and a dropped one."""
    for module, roles in (
        (deepagents_vocabulary, DEEPAGENTS_ROLES),
        (langchain4j_vocabulary, LANGCHAIN4J_ROLES),
    ):
        assigned = assign(module, roles)
        assert assigned, f"{module.__name__} assigned nothing"
        assert all(isinstance(role, Role) for role, _constant in assigned.values())


def test_a_missing_role_stops_the_sweep() -> None:
    """The control for the check above: silence would look identical."""
    incomplete = dict(DEEPAGENTS_ROLES)
    incomplete.pop("CREATE_DEEP_AGENT")
    try:
        assign(deepagents_vocabulary, incomplete)
    except KeyError:
        return
    raise AssertionError("an inventoried constant with no role was swept anyway")


def test_a_removal_is_reported_as_its_own_category() -> None:
    """The event ADR 0005 named as reopening per-version API profiles."""
    added = report.history("late", {"1": False, "2": True, "3": True})
    assert added.first == "2"
    assert added.removed_at is None
    assert "added at 2" == added.summary

    removed = report.history("gone", {"1": True, "2": True, "3": False})
    assert removed.removed_at == "3"
    assert "REMOVED" in removed.summary

    absent = report.history("never", {"1": False, "2": False})
    assert absent.first is None

    assert not report.blocking([added])
    assert report.blocking([removed])
    assert report.blocking([absent])


def main() -> int:
    failures = 0
    for name, case in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            case()
        except AssertionError as failure:  # noqa: PERF203 -- one report per case
            failures += 1
            print(f"FAIL {name}: {failure}")
        else:
            print(f"ok   {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
