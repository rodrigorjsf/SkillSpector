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

"""Finding LangChain4j's shell mode in Java source.

Shell mode replaces the ``activate_skill`` tool surface with a single
``run_shell_command`` tool and lets the model read Skill files off the disk
itself. LangChain4j's own documentation calls it unsafe: commands run in the
host process environment with no sandboxing, containerization or privilege
restriction, so a prompt-injected model executes arbitrary commands on the
machine running the application.

Importing this module imports the tree-sitter parser -- see
:mod:`skillspector.langchain4j.java_parser`.
"""

from __future__ import annotations

from typing import Final

from skillspector.langchain4j import java_parser

# The type that selects shell mode. ``Skills`` is the safe sibling; the choice
# between them is a plain type reference, which is why it is statically visible.
from skillspector.langchain4j.vocabulary import SHELL_SKILLS_TYPE

# A bare name in Java source is one of these two node types, depending on
# whether it appears in type position (``ShellSkills skills = ...``) or in
# expression position (``ShellSkills.from(...)``).
_NAME_NODE_TYPES: Final[frozenset[str]] = frozenset({"identifier", "type_identifier"})
_IMPORT_DECLARATION: Final[str] = "import_declaration"


def find_shell_skills_usage(source: str) -> int | None:
    """The line where *source* reaches for shell mode, or ``None``.

    Reports the wiring in preference to the import that made it reachable: the
    import says the type is on the classpath, the wiring says the application
    uses it, and a reviewer sent to the wiring is standing where the decision
    was made. A file that only imports the type is still reported, at the
    import, because an unused import of it is a stronger signal than none.

    Only the first reference is returned. One Finding is enough to send a
    reviewer to the file; a second on the same type in the same file would add
    noise, not information.
    """
    root = java_parser.parse(source).root_node
    import_line: int | None = None
    for node in java_parser.walk(root):
        if node.type not in _NAME_NODE_TYPES:
            continue
        if java_parser.text(node) != SHELL_SKILLS_TYPE:
            continue
        if java_parser.has_ancestor(node, _IMPORT_DECLARATION):
            if import_line is None:
                import_line = java_parser.line(node)
            continue
        return java_parser.line(node)
    return import_line
