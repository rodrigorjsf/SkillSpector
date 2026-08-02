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

"""The tree-sitter binding for Java, and nothing else.

Importing this module imports tree-sitter. That is the point: it is the single
place the dependency enters, so a Rule module can depend on a parser by
importing one name, and the Analyzer can stay parser-free until its gates open.
See :mod:`skillspector.langchain4j` for why that ordering matters.

tree-sitter was chosen over ``javalang`` in
``docs/adr/0001-tree-sitter-for-java-parsing.md``. Two of its properties are
load-bearing rather than incidental, and both are relied on below: it knows
Java text blocks, which LangChain4j's own documentation uses to define Skill
content, and it is error tolerant, so a compilation unit with a syntax error
still yields a tree covering the parts that parsed.
"""

from __future__ import annotations

from collections.abc import Iterator

import tree_sitter_java
from tree_sitter import Language, Node, Parser, Tree

_LANGUAGE: Language | None = None


def _language() -> Language:
    """The Java grammar, built once per process.

    ``Language`` compiles the grammar pointer into a lookup table, so building
    one per file would repeat that work on every Java source of every Scan.
    """
    global _LANGUAGE
    if _LANGUAGE is None:
        _LANGUAGE = Language(tree_sitter_java.language())
    return _LANGUAGE


def parse(source: str) -> Tree:
    """Parse Java *source* into a syntax tree.

    Never raises on malformed input: an unparseable region becomes an ``ERROR``
    node and its siblings still parse. A Rule reading the result therefore sees
    the parts of a broken file that were valid, which is what keeps one typo
    from blinding a whole Scan.
    """
    return Parser(_language()).parse(source.encode("utf-8"))


def walk(node: Node) -> Iterator[Node]:
    """Yield *node* and every node beneath it, in source order.

    Pre-order and left to right, so the first match a caller accepts is also the
    earliest one in the file.
    """
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def text(node: Node) -> str:
    """The source text *node* spans."""
    raw = node.text
    return "" if raw is None else raw.decode("utf-8", errors="replace")


def line(node: Node) -> int:
    """The 1-based line *node* starts on.

    tree-sitter counts rows from zero; Findings, SARIF and every human reading
    the report count from one.
    """
    return node.start_point[0] + 1


def has_ancestor(node: Node, node_type: str) -> bool:
    """Whether *node* sits anywhere inside a *node_type* node."""
    current = node.parent
    while current is not None:
        if current.type == node_type:
            return True
        current = current.parent
    return False
