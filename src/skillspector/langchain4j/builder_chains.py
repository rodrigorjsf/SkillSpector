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

"""Reading a Java builder chain.

LangChain4j configures nearly everything through ``X.builder().a(...).b(...)``,
so most of what a Rule wants to know is a question about a chain: which type it
builds, which setters it called, and what it passed to one of them. Two Rule
families ask it -- Skill definitions and the tool surface -- and they ask it the
same way, so the walk lives here rather than twice.

Chains nest left. ``Skill.builder().name(x).content(y)`` parses as an invocation
of ``content`` whose object is an invocation of ``name`` whose object is an
invocation of ``builder``. Every function here follows that spine down.

Importing this module imports the tree-sitter parser -- see
:mod:`skillspector.langchain4j.java_parser`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tree_sitter import Node

from skillspector.langchain4j import java_parser

_ARGUMENT_PUNCTUATION: Final[frozenset[str]] = frozenset({"(", ")", ","})
_ENTRY_METHODS: Final[frozenset[str]] = frozenset({"builder", "toBuilder"})


@dataclass(frozen=True)
class BuilderChain:
    """One ``X.builder()...`` chain, as a whole.

    ``receiver`` is the text the chain starts from: a type name for
    ``X.builder()``, and the variable's name for ``value.toBuilder()`` -- the
    walk cannot know what type a value has, so callers that care apply their own
    rule. ``setters`` maps each setter called anywhere in the chain to the line
    it was called on; a setter called twice keeps the first.
    """

    receiver: str
    entry: str
    line: int
    setters: dict[str, int]

    def called(self, setter: str) -> bool:
        """Whether the chain called *setter* at any point."""
        return setter in self.setters


def argument_list(invocation: Node) -> list[Node]:
    """Every argument of *invocation*, in source order, punctuation removed."""
    arguments = invocation.child_by_field_name("arguments")
    if arguments is None:
        return []
    return [child for child in arguments.children if child.type not in _ARGUMENT_PUNCTUATION]


def sole_argument(invocation: Node) -> Node | None:
    """The single argument of *invocation*, or ``None`` if it takes another count."""
    values = argument_list(invocation)
    return values[0] if len(values) == 1 else None


def chain_entry(invocation: Node) -> tuple[str, str] | None:
    """The ``(receiver, entry method)`` the chain holding *invocation* starts from.

    Returns ``None`` when the spine bottoms out on something other than a
    ``builder()`` or ``toBuilder()`` call -- an ordinary method chain is not a
    builder chain.
    """
    current: Node | None = invocation
    while current is not None and current.type == "method_invocation":
        name = current.child_by_field_name("name")
        target = current.child_by_field_name("object")
        if name is None or target is None:
            return None
        if java_parser.text(name) in _ENTRY_METHODS:
            return java_parser.text(target), java_parser.text(name)
        current = target
    return None


def chain_start(invocation: Node) -> int:
    """The start byte of the chain *invocation* belongs to.

    Two chains on one line are told apart by where each begins, which is where
    the spine bottoms out. Used as an identity, never as a location.
    """
    current: Node | None = invocation
    while (
        current is not None
        and current.type == "method_invocation"
        and current.child_by_field_name("object") is not None
    ):
        current = current.child_by_field_name("object")
    return int(current.start_byte) if current is not None else 0


def find_builder_chains(source: str, receiver: str) -> list[BuilderChain]:
    """Every ``<receiver>.builder()`` chain in *source*, collected whole.

    A chain is reported once, however many setters it called, so a Rule that
    asks "was this setter ever called" gets one answer per chain rather than one
    per link.
    """
    root = java_parser.parse(source).root_node

    setters_by_chain: dict[int, dict[str, int]] = {}
    entries: dict[int, tuple[str, str, int]] = {}
    for node in java_parser.walk(root):
        if node.type != "method_invocation":
            continue
        name = node.child_by_field_name("name")
        if name is None:
            continue
        entry = chain_entry(node)
        if entry is None or entry[0] != receiver:
            continue
        key = chain_start(node)
        entries.setdefault(key, (entry[0], entry[1], java_parser.line(node)))
        setters_by_chain.setdefault(key, {}).setdefault(
            java_parser.text(name), java_parser.line(node)
        )

    return [
        BuilderChain(
            receiver=entries[key][0],
            entry=entries[key][1],
            line=min(entries[key][2], *setters_by_chain[key].values()),
            setters=setters_by_chain[key],
        )
        for key in sorted(setters_by_chain)
    ]
