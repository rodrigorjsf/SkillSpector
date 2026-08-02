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

"""The tool surface a LangChain4j application hands its agent.

Three ways the wiring gives an agent more capability than the author meant:

* an ``@Tool`` description that carries instructions rather than describing a
  tool -- the tool-poisoning surface written in Java instead of in an MCP
  manifest, sitting in an annotation nobody reviews as prose;
* an ``McpToolProvider`` built without a tool filter, so every tool the server
  exposes reaches the agent instead of a scoped subset;
* a ``RunShellCommandToolConfig`` with no working directory, so commands run
  wherever the JVM happened to start -- usually the application root.

Each is a fact about the shape of a builder chain or an annotation, which is why
all three are statically visible.

Importing this module imports the tree-sitter parser -- see
:mod:`skillspector.langchain4j.java_parser`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tree_sitter import Node

from skillspector.langchain4j import builder_chains, java_parser

# The upstream spelling this module matches on. The types and setters the
# Analyzer passes to :func:`find_unset_setter` are spelled there too -- this
# module takes a receiver and a setter as arguments and does not name them.
from skillspector.langchain4j.vocabulary import TOOL_ANNOTATION

_ANNOTATION_TYPES: Final[frozenset[str]] = frozenset({"annotation", "marker_annotation"})


@dataclass(frozen=True)
class ToolAnnotation:
    """One ``@Tool`` annotation and the text it hands the model."""

    line: int
    description: str


@dataclass(frozen=True)
class UnsetSetter:
    """A builder chain that never called a setter it should have."""

    receiver: str
    setter: str
    line: int


def _annotation_strings(annotation: Node) -> list[str]:
    """Every string literal an annotation passes, in source order.

    ``@Tool("text")`` and ``@Tool(name = "x", value = "text")`` are both real
    spellings, and an array form passes several. Collecting the literals rather
    than reading one named element keeps all three readable without deciding
    which element is the description -- every literal in a ``@Tool`` is text the
    model may be shown.
    """
    arguments = annotation.child_by_field_name("arguments")
    if arguments is None:
        return []
    return [
        java_parser.text(node)[1:-1]
        for node in java_parser.walk(arguments)
        if node.type == "string_literal" and not java_parser.text(node).startswith('"""')
    ]


def find_tool_annotations(source: str) -> list[ToolAnnotation]:
    """Every ``@Tool`` annotation in *source* that carries text.

    A bare ``@Tool`` with no arguments carries none and is skipped: there is no
    prose to examine, and the tool's risk is then a question about its body
    rather than about its description.
    """
    root = java_parser.parse(source).root_node

    annotations: list[ToolAnnotation] = []
    for node in java_parser.walk(root):
        if node.type not in _ANNOTATION_TYPES:
            continue
        name = node.child_by_field_name("name")
        if name is None or java_parser.text(name) != TOOL_ANNOTATION:
            continue
        strings = _annotation_strings(node)
        if not strings:
            continue
        annotations.append(
            ToolAnnotation(line=java_parser.line(node), description="\n".join(strings))
        )
    return annotations


def find_unset_setter(source: str, receiver: str, setter: str) -> list[UnsetSetter]:
    """Every ``<receiver>.builder()`` chain in *source* that never called *setter*.

    The absence is the finding, so the whole chain has to be in view before it
    can be judged -- a chain is reported once, at its first line, however many
    other setters it called.
    """
    return [
        UnsetSetter(receiver=receiver, setter=setter, line=chain.line)
        for chain in builder_chains.find_builder_chains(source, receiver)
        if not chain.called(setter)
    ]
