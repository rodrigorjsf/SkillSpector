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

"""Where a LangChain4j Skill is defined in Java, and what its text actually says.

A LangChain4j Skill does not have to be a directory on disk. It can be built in
Java -- ``Skill.builder().content(...)`` -- from a string literal, a text block,
a constant, or from a database, a remote call, or anything else the application
does at runtime. The instruction text a model reads is whatever that argument
evaluates to.

This module resolves the arguments it can and, just as importantly, says which
ones it cannot. Resolving arbitrary Java dataflow is explicitly out of scope
(``docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md`` §3.6); the boundary is the product.
A Skill whose content is assembled at runtime has instruction text that exists
in no scanned file, and reporting nothing there would let a Scan read as clean
on the one surface it never examined.

Importing this module imports the tree-sitter parser -- see
:mod:`skillspector.langchain4j.java_parser`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tree_sitter import Node

from skillspector.langchain4j import java_parser

# The builders that define a Skill, and the argument of each that carries text a
# model reads. ``relativePath`` is not one: it names a file, not instructions.
_SKILL_BUILDERS: Final[frozenset[str]] = frozenset({"Skill", "SkillResource"})
_BUILDER_ENTRY_METHODS: Final[frozenset[str]] = frozenset({"builder", "toBuilder"})
_TEXT_SETTERS: Final[tuple[str, ...]] = ("content", "name", "description")

# The loaders that find a Skill on disk or on the classpath, per §3.6's table.
_SKILL_LOADERS: Final[frozenset[str]] = frozenset({"FileSystemSkillLoader", "ClassPathSkillLoader"})
_LOADER_METHODS: Final[frozenset[str]] = frozenset({"loadSkills", "loadSkill"})

# ``ClassPathSkillLoader.loadSkills("skills")`` resolves against the Maven
# resource root, so the same literal names a different directory than the
# filesystem loader's would.
_CLASSPATH_ROOT: Final[str] = "src/main/resources/"

_TEXT_BLOCK_DELIMITER: Final[str] = '"""'
_ESCAPES: Final[tuple[tuple[str, str], ...]] = (
    ("\\\\", "\x00"),
    ("\\n", "\n"),
    ("\\t", "\t"),
    ('\\"', '"'),
    ("\\'", "'"),
)


@dataclass(frozen=True)
class BuilderArgument:
    """One ``.name(...)`` / ``.description(...)`` / ``.content(...)`` argument.

    ``value`` is the resolved text, or ``None`` when the argument is not
    statically resolvable. ``None`` is the reportable case, not a failure to
    record: it is what ``L4J-UNRESOLVED`` exists to name.

    ``value_start_line`` is where the *first line of the value* sits in the Java
    file, which is not always where the argument starts: a text block's content
    begins on the line after its opening delimiter. A content Rule matching line
    3 of a resolved body has to be reported against the right Java line, and the
    two differ by exactly this.
    """

    setter: str
    line: int
    value: str | None
    value_start_line: int


@dataclass(frozen=True)
class SkillDefinition:
    """One ``Skill.builder()`` or ``SkillResource.builder()`` chain."""

    builder: str
    line: int
    arguments: tuple[BuilderArgument, ...]

    def argument(self, setter: str) -> BuilderArgument | None:
        """The argument passed to *setter*, if the chain set it."""
        for argument in self.arguments:
            if argument.setter == setter:
                return argument
        return None


@dataclass(frozen=True)
class SkillLoaderCall:
    """One ``FileSystemSkillLoader`` or ``ClassPathSkillLoader`` call.

    ``directory`` is the Scan-relative directory the call reads, or ``None``
    when the argument was not a literal path -- a custom class loader, or a path
    built at runtime, is a definition site whose Skills were never examined.
    """

    loader: str
    method: str
    line: int
    directory: str | None


@dataclass(frozen=True)
class AttachedTools:
    """One ``.tools(...)`` call on a builder chain.

    ``type_name`` is the class whose ``@Tool`` methods the Skill gains, when the
    argument is a plain ``new X()``. Tools attached any other way -- a map, a
    variable -- leave it ``None``.
    """

    line: int
    type_name: str | None


def _unescape(text: str) -> str:
    for escaped, plain in _ESCAPES:
        text = text.replace(escaped, plain)
    return text.replace("\x00", "\\")


def _text_block_value(raw: str) -> str:
    """The value of a Java text block, with incidental indentation removed.

    Follows JLS 3.10.6: the line holding the opening delimiter contributes
    nothing, and the common indentation of the content lines *and the closing
    delimiter's line* is stripped from all of them. Getting this wrong would
    shift every line of a resolved Skill body by a few spaces, which changes
    what a content Rule matches.
    """
    body = raw[len(_TEXT_BLOCK_DELIMITER) : -len(_TEXT_BLOCK_DELIMITER)]
    first_newline = body.find("\n")
    body = body[first_newline + 1 :] if first_newline >= 0 else body

    lines = body.split("\n")
    # The closing delimiter's line is always significant, blank or not; content
    # lines are significant only when they hold something.
    measured = [line for line in lines[:-1] if line.strip()]
    measured.append(lines[-1])
    indent = min((len(line) - len(line.lstrip()) for line in measured), default=0)

    stripped = [line[indent:] if line[:indent].strip() == "" else line.lstrip() for line in lines]
    if stripped and not stripped[-1].strip():
        stripped = stripped[:-1]
        return "\n".join(stripped) + "\n" if stripped else ""
    return "\n".join(stripped)


def _string_value(node: Node) -> str | None:
    """The text a string-literal node holds, or ``None`` if it is not one."""
    if node.type != "string_literal":
        return None
    raw = java_parser.text(node)
    if raw.startswith(_TEXT_BLOCK_DELIMITER):
        return _text_block_value(raw)
    return _unescape(raw[1:-1])


def _string_constants(root: Node) -> dict[str, str]:
    """Every ``String NAME = "literal"`` in the compilation unit, by name.

    Same-unit constants only. §3.6 calls a constant "usually" resolvable and
    means exactly this: the declaration has to be in the file being read, since
    following it anywhere else is the arbitrary dataflow that is out of scope.
    """
    constants: dict[str, str] = {}
    for node in java_parser.walk(root):
        if node.type not in ("field_declaration", "local_variable_declaration"):
            continue
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue
            name = declarator.child_by_field_name("name")
            value = declarator.child_by_field_name("value")
            if name is None or value is None:
                continue
            resolved = _string_value(value)
            if resolved is not None:
                constants[java_parser.text(name)] = resolved
    return constants


def _resolve(argument: Node, constants: dict[str, str]) -> str | None:
    """The text an argument evaluates to, or ``None`` when that is not knowable."""
    literal = _string_value(argument)
    if literal is not None:
        return literal
    if argument.type == "identifier":
        return constants.get(java_parser.text(argument))
    return None


def _sole_argument(invocation: Node) -> Node | None:
    """The single argument of an invocation, or ``None`` if it takes another count."""
    arguments = invocation.child_by_field_name("arguments")
    if arguments is None:
        return None
    values = [child for child in arguments.children if child.type not in ("(", ")", ",")]
    return values[0] if len(values) == 1 else None


def _chain_root(invocation: Node) -> tuple[str, str] | None:
    """The ``(type, entry method)`` a builder chain starts from.

    ``Skill.builder().name(...).content(...)`` nests left, so the chain is walked
    by following each invocation's object down to the ``Skill.builder()`` at the
    bottom. Returns ``None`` for a chain that is not a Skill builder.
    """
    current: Node | None = invocation
    while current is not None and current.type == "method_invocation":
        name = current.child_by_field_name("name")
        target = current.child_by_field_name("object")
        if (
            name is not None
            and java_parser.text(name) in _BUILDER_ENTRY_METHODS
            and target is not None
        ):
            entry = java_parser.text(name)
            if entry == "toBuilder":
                # ``skill.toBuilder()`` -- the receiver is an already-built Skill,
                # so the builder's type comes from the value, not from the name
                # the variable happens to be spelled with.
                return "Skill", entry
            if target.type == "identifier":
                return java_parser.text(target), entry
            return None
        current = target
    return None


def find_skill_definitions(source: str) -> list[SkillDefinition]:
    """Every Skill-builder chain in *source*, with each text argument resolved."""
    root = java_parser.parse(source).root_node
    constants = _string_constants(root)

    by_root: dict[tuple[int, int], list[BuilderArgument]] = {}
    builders: dict[tuple[int, int], str] = {}
    for node in java_parser.walk(root):
        if node.type != "method_invocation":
            continue
        name_node = node.child_by_field_name("name")
        if name_node is None or java_parser.text(name_node) not in _TEXT_SETTERS:
            continue
        chain = _chain_root(node)
        if chain is None or chain[0] not in _SKILL_BUILDERS:
            continue
        argument = _sole_argument(node)
        if argument is None:
            continue
        # Chains are keyed by their own start position, so two Skills built in
        # one statement stay two Skills.
        key = (node.start_point[0], _chain_start_column(node))
        builders[key] = chain[0]
        argument_line = java_parser.line(argument)
        is_text_block = java_parser.text(argument).startswith(_TEXT_BLOCK_DELIMITER)
        by_root.setdefault(key, []).append(
            BuilderArgument(
                setter=java_parser.text(name_node),
                line=argument_line,
                value=_resolve(argument, constants),
                value_start_line=argument_line + 1 if is_text_block else argument_line,
            )
        )

    return [
        SkillDefinition(
            builder=builders[key],
            line=min(argument.line for argument in arguments),
            arguments=tuple(sorted(arguments, key=lambda item: (item.line, item.setter))),
        )
        for key, arguments in sorted(by_root.items())
    ]


def _chain_start_column(invocation: Node) -> int:
    """The start byte of the chain *invocation* belongs to.

    Two chains on the same line are distinguished by where each begins, which is
    the position of the outermost object once the chain has been walked down.
    """
    current: Node | None = invocation
    while (
        current is not None
        and current.type == "method_invocation"
        and current.child_by_field_name("object") is not None
    ):
        current = current.child_by_field_name("object")
    return int(current.start_byte) if current is not None else 0


def find_skill_loader_calls(source: str) -> list[SkillLoaderCall]:
    """Every filesystem or classpath Skill-loader call in *source*."""
    root = java_parser.parse(source).root_node
    constants = _string_constants(root)

    calls: list[SkillLoaderCall] = []
    for node in java_parser.walk(root):
        if node.type != "method_invocation":
            continue
        name_node = node.child_by_field_name("name")
        target = node.child_by_field_name("object")
        if name_node is None or target is None:
            continue
        method = java_parser.text(name_node)
        loader = java_parser.text(target)
        if method not in _LOADER_METHODS or loader not in _SKILL_LOADERS:
            continue
        calls.append(
            SkillLoaderCall(
                loader=loader,
                method=method,
                line=java_parser.line(node),
                directory=_loader_directory(loader, node, constants),
            )
        )
    return calls


def _loader_directory(loader: str, invocation: Node, constants: dict[str, str]) -> str | None:
    """The Scan-relative directory a loader call reads, when it is a literal.

    ``Path.of("skills/")`` is unwrapped: the filesystem loader takes a ``Path``,
    so the literal is one call deeper than the classpath loader's.
    """
    argument = _sole_argument(invocation)
    if argument is None:
        return None
    if argument.type == "method_invocation":
        argument = _sole_argument(argument)
        if argument is None:
            return None
    literal = _resolve(argument, constants)
    if literal is None:
        return None
    directory = literal.rstrip("/")
    if loader == "ClassPathSkillLoader":
        return f"{_CLASSPATH_ROOT}{directory}"
    return directory


def find_attached_tools(source: str) -> list[AttachedTools]:
    """Every ``.tools(...)`` call on a Skill-builder chain in *source*."""
    root = java_parser.parse(source).root_node

    attached: list[AttachedTools] = []
    for node in java_parser.walk(root):
        if node.type != "method_invocation":
            continue
        name_node = node.child_by_field_name("name")
        if name_node is None or java_parser.text(name_node) != "tools":
            continue
        chain = _chain_root(node)
        if chain is None or chain[0] not in _SKILL_BUILDERS:
            continue
        attached.append(
            AttachedTools(line=java_parser.line(node), type_name=_constructed_type(node))
        )
    return attached


def _constructed_type(invocation: Node) -> str | None:
    """The class name of a sole ``new X()`` argument, or ``None``."""
    argument = _sole_argument(invocation)
    if argument is None or argument.type != "object_creation_expression":
        return None
    for child in argument.children:
        if child.type == "type_identifier":
            return java_parser.text(child)
    return None
