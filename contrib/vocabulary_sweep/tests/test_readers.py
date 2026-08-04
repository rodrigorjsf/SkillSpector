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
import struct
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
from contrib.vocabulary_sweep.maven_sweep import declared_methods  # noqa: E402
from contrib.vocabulary_sweep.published import Occurrences  # noqa: E402
from contrib.vocabulary_sweep.pypi_sweep import _Reader  # noqa: E402
from contrib.vocabulary_sweep.roles import (  # noqa: E402
    DEEPAGENTS_ROLES,
    LANGCHAIN4J_ROLES,
    Role,
    assign,
    measurable,
)
from skillspector.deepagents import vocabulary as deepagents_vocabulary  # noqa: E402
from skillspector.langchain4j import vocabulary as langchain4j_vocabulary  # noqa: E402


def _read(source: str) -> Occurrences:
    reader = _Reader()
    reader.visit(ast.parse(source))
    return Occurrences(
        {
            Role.DEFINED_NAME: frozenset(reader.defined),
            Role.BOUND_NAME: frozenset(reader.bound),
            Role.LITERAL_VALUE: frozenset(reader.literal),
        }
    )


def _class_file(*, fields: list[str], methods: list[str]) -> bytes:
    """A minimal class file declaring *fields* and *methods*, built by hand.

    Every shape the reader has to walk past is present, because those are what
    it can silently mis-offset: a `Long` constant, which occupies **two** pool
    slots; a `Methodref`, which is wider than a `Class`; an implemented
    interface; and an attribute on a member, whose four-byte length has to be
    stepped over. Get any of them wrong and the method table is read from the
    wrong offset -- which surfaces as every spelling reading "never observed",
    an alarm pointed at the inventory rather than at the reader.
    """
    utf8 = [*fields, *methods, "()V", "Code"]
    pool = bytearray()
    slot: dict[str, int] = {}
    index = 1
    for text in utf8:
        slot[text] = index
        payload = text.encode("utf-8")
        pool += struct.pack(">BH", 1, len(payload)) + payload
        index += 1
    pool += struct.pack(">Bq", 5, 1)  # Long: two slots, eight bytes
    index += 2
    pool += struct.pack(">BH", 7, 1)  # Class
    index += 1
    pool += struct.pack(">BHH", 10, 1, 1)  # Methodref
    index += 1

    def members(names: list[str]) -> bytes:
        out = struct.pack(">H", len(names))
        for name in names:
            # One attribute each, four bytes of payload, so the reader has to
            # honour the length rather than assume an empty attribute table.
            out += struct.pack(">HHHH", 0, slot[name], slot["()V"], 1)
            out += struct.pack(">HI", slot["Code"], 4) + b"\x00\x00\x00\x00"
        return out

    return (
        struct.pack(">IHHH", 0xCAFEBABE, 0, 65, index)
        + bytes(pool)
        + struct.pack(">HHH", 0, 1, 1)  # access_flags, this_class, super_class
        + struct.pack(">HH", 1, 1)  # one interface
        + members(fields)
        + members(methods)
    )


def test_the_class_reader_returns_methods_and_not_fields() -> None:
    """Reading the wrong section would report field names as published methods."""
    declared = declared_methods(_class_file(fields=["logger"], methods=["filter", "build"]))
    assert sorted(declared) == ["build", "filter"]
    assert "logger" not in declared


def test_the_class_reader_walks_past_the_wide_pool_entries() -> None:
    """The control for the offset arithmetic: an empty method table, read correctly."""
    assert declared_methods(_class_file(fields=["only"], methods=[])) == []


def test_a_python_name_is_read_in_its_own_role() -> None:
    """The whole point: a word in prose is not the word in role."""
    documented = _read('"""A module whose docstring mentions a keyword argument."""\n')
    assert not documented.carries("backing", Role.BOUND_NAME)
    assert not documented.carries("make", Role.DEFINED_NAME)

    declared = _read("def make(*, backing: int) -> None: ...\n")
    assert declared.carries("backing", Role.BOUND_NAME)
    assert declared.carries("make", Role.DEFINED_NAME)
    assert not declared.carries("backing", Role.DEFINED_NAME)


def test_a_string_value_is_not_a_bound_name() -> None:
    """The three role shapes stay apart, or every spelling reads as present."""
    occurrences = _read("CHOICE = 'halt'\ndef run(*, halt: bool) -> None: ...\n")
    assert occurrences.carries("halt", Role.LITERAL_VALUE)
    assert occurrences.carries("halt", Role.BOUND_NAME)
    assert not _read("CHOICE = 'halt'\n").carries("halt", Role.BOUND_NAME)


def test_an_annotated_field_counts_as_bound() -> None:
    """How a dataclass, a TypedDict and a model all spell their arguments."""
    occurrences = _read("class Rule:\n    governs: list[str]\n")
    assert occurrences.carries("governs", Role.BOUND_NAME)
    assert occurrences.carries("Rule", Role.DEFINED_NAME)


def test_a_role_map_covers_its_inventory_exactly() -> None:
    """Fails closed on both a new spelling and a dropped one."""
    for module, roles in (
        (deepagents_vocabulary, DEEPAGENTS_ROLES),
        (langchain4j_vocabulary, LANGCHAIN4J_ROLES),
    ):
        assigned = assign(module, roles)
        assert assigned, f"{module.__name__} assigned nothing"
        assert all(isinstance(role, Role) for role, _constant in assigned.values())


def test_the_version_range_is_not_swept_as_a_spelling() -> None:
    """A regression: sweeping releases for the sweep's own version numbers.

    ``OBSERVED_VERSION_RANGE`` holds two version strings, and they are inventory
    entries like any other. Swept, they read as never observed and raise a
    blocking verdict against the inventory's own bookkeeping.
    """
    for module, roles in (
        (deepagents_vocabulary, DEEPAGENTS_ROLES),
        (langchain4j_vocabulary, LANGCHAIN4J_ROLES),
    ):
        swept = set(measurable(module, roles))
        assert swept, f"{module.__name__} would be swept for nothing"
        assert not swept & set(module.OBSERVED_VERSION_RANGE)
        # The control: without the filter, both versions are in the swept set.
        assert set(module.OBSERVED_VERSION_RANGE) <= set(assign(module, roles))


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
