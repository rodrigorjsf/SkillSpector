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

"""What each inventoried spelling *is* upstream, so presence can be measured in role.

A sweep that asked "does this release contain the text ``skills``" would answer
yes for every release ever published, including the ones predating the feature,
and the stability claim would be exactly the unmeasured assertion this tooling
exists to replace. Four Deep Agents spellings are ordinary English words -- the
inventory says so itself -- and several LangChain4j ones (``name``, ``content``,
``tools``, ``mode``) are among the commonest identifiers in any Java library.

So every inventoried constant is assigned a **role**: the shape upstream writes
it in. A release counts as carrying the spelling only when the spelling occurs in
that shape. ``skills`` is observed when a published function takes it as a
keyword argument, not when a docstring mentions it.

Roles are keyed by the *constant name* in the inventory module, never by its
value. Writing a value here would put a second copy of the spelling outside the
reach of the guards in ``tests/unit/test_langchain4j_vocabulary.py`` and
``tests/unit/test_deepagents_vocabulary.py`` -- the very drift the single-home
decision exists to prevent.

:func:`assign` fails closed. A constant added to an inventory without a role here
stops the sweep rather than being silently skipped, because a spelling nobody
measured is the thing the measurement is for.
"""

from __future__ import annotations

from enum import Enum
from types import ModuleType
from typing import Final


class Role(Enum):
    """The shape a release has to write a spelling in for the sweep to count it."""

    #: A name the distribution itself defines -- a class, a function, or a
    #: module-level binding. Python: ``class FilesystemBackend``. Java: a type
    #: whose class file the artifact ships.
    DEFINED_NAME = "defined name"

    #: A name something is passed or declared under -- a parameter, a keyword
    #: argument at a call site, an annotated field. Python: ``skills=`` in a
    #: signature. Java: a builder method, which is how LangChain4j spells a
    #: named argument.
    BOUND_NAME = "bound name"

    #: A string value the distribution writes out, rather than a name. The two
    #: documented ``mode`` values and the tools an approval gate is keyed by.
    LITERAL_VALUE = "literal value"

    #: The distribution's own published name, observed from the index rather
    #: than from inside the archive.
    DISTRIBUTION = "distribution name"

    #: Deliberately not measured by a release sweep, with the reason recorded
    #: beside the constant in the inventory. A documented directory convention
    #: is not an identifier: it appears in upstream's prose and example trees,
    #: not in a compiled artifact, so a sweep that reported it absent would be
    #: reporting on its own reach rather than on upstream.
    NOT_MEASURED = "not measured by a release sweep"


#: Every constant in :mod:`skillspector.deepagents.vocabulary`, by role.
DEEPAGENTS_ROLES: dict[str, Role] = {
    "OBSERVED_VERSION_RANGE": Role.NOT_MEASURED,
    "CREATE_DEEP_AGENT": Role.DEFINED_NAME,
    "DISTRIBUTION": Role.DISTRIBUTION,
    "FILESYSTEM_PERMISSION": Role.DEFINED_NAME,
    "COMPOSITE_BACKEND": Role.DEFINED_NAME,
    "STORE_BACKEND": Role.DEFINED_NAME,
    "STATE_BACKEND": Role.DEFINED_NAME,
    "FILESYSTEM_BACKEND": Role.DEFINED_NAME,
    "BACKEND": Role.BOUND_NAME,
    "SUBAGENTS": Role.BOUND_NAME,
    "SKILLS": Role.BOUND_NAME,
    "PERMISSIONS": Role.BOUND_NAME,
    "ROUTES": Role.BOUND_NAME,
    "ROOT_DIR": Role.BOUND_NAME,
    "OPERATIONS": Role.BOUND_NAME,
    "PATHS": Role.BOUND_NAME,
    "MODE": Role.BOUND_NAME,
    "INTERRUPT_ON": Role.BOUND_NAME,
    "DENY": Role.LITERAL_VALUE,
    "INTERRUPT": Role.LITERAL_VALUE,
    "WRITE": Role.LITERAL_VALUE,
    "WRITE_FILE": Role.LITERAL_VALUE,
    "EDIT_FILE": Role.LITERAL_VALUE,
}

#: The four published artifacts a LangChain4j spelling can live in. Symbolic
#: rather than spelled here: three of the four ids are ordinary strings this
#: package may write, but the fourth is inventoried, and resolving all of them in
#: one place keeps the asymmetry from reading as an oversight.
SKILLS_ARTIFACT: Final[str] = "skills"
SHELL_ARTIFACT: Final[str] = "shell"
CORE_ARTIFACT: Final[str] = "core"
MCP_ARTIFACT: Final[str] = "mcp"

#: Every constant in :mod:`skillspector.langchain4j.vocabulary`, by role.
#:
#: The four entries the sweep cannot observe are ``NOT_MEASURED`` here rather
#: than absent, so the completeness check still covers them and the reason
#: travels with the constant. The artifact ids and the group coordinate are
#: measured from the index's own coordinates, which is what
#: :data:`Role.DISTRIBUTION` means for Maven -- and for the shell artifact that
#: observation is precisely the graduation watch ADR 0007 describes.
LANGCHAIN4J_ROLES: dict[str, Role] = {
    "OBSERVED_VERSION_RANGE": Role.NOT_MEASURED,
    "SKILL_BUILDER": Role.DEFINED_NAME,
    "SKILL_RESOURCE_BUILDER": Role.DEFINED_NAME,
    "SKILL_BUILDERS": Role.DEFINED_NAME,
    "CONTENT_SETTER": Role.BOUND_NAME,
    "NAME_SETTER": Role.BOUND_NAME,
    "DESCRIPTION_SETTER": Role.BOUND_NAME,
    "TEXT_SETTERS": Role.BOUND_NAME,
    "TOOLS_SETTER": Role.BOUND_NAME,
    "FILESYSTEM_SKILL_LOADER": Role.DEFINED_NAME,
    "CLASSPATH_SKILL_LOADER": Role.DEFINED_NAME,
    "SKILL_LOADERS": Role.DEFINED_NAME,
    "LOAD_SKILLS_METHOD": Role.BOUND_NAME,
    "LOAD_SKILL_METHOD": Role.BOUND_NAME,
    "LOADER_METHODS": Role.BOUND_NAME,
    "CLASSPATH_SKILL_LAYOUT": Role.NOT_MEASURED,
    "SHELL_SKILLS_TYPE": Role.DEFINED_NAME,
    "SHELL_COMMAND_CONFIG": Role.DEFINED_NAME,
    "WORKING_DIRECTORY_SETTER": Role.BOUND_NAME,
    "SHELL_ARTIFACT_ID": Role.DISTRIBUTION,
    "SHELL_ARTIFACT_PATTERN": Role.NOT_MEASURED,
    "TOOL_ANNOTATION": Role.DEFINED_NAME,
    "MCP_TOOL_PROVIDER": Role.DEFINED_NAME,
    "TOOL_FILTER_SETTER": Role.BOUND_NAME,
    "GROUP_COORDINATE": Role.DISTRIBUTION,
    "IMPORT_PREFIX": Role.NOT_MEASURED,
}

#: Which artifact publishes each measured LangChain4j constant. Four artifacts on
#: three version lines: ``langchain4j-core`` is released without the ``-betaNN``
#: suffix the other three carry, so each is swept over its own published history
#: rather than over one shared spine.
#:
#: Only the constants with a measurable role appear. ``assign_artifacts`` fails
#: closed on the rest, exactly as :func:`assign` does for roles.
LANGCHAIN4J_ARTIFACTS: dict[str, str] = {
    "SKILL_BUILDER": SKILLS_ARTIFACT,
    "SKILL_RESOURCE_BUILDER": SKILLS_ARTIFACT,
    "SKILL_BUILDERS": SKILLS_ARTIFACT,
    "CONTENT_SETTER": SKILLS_ARTIFACT,
    "NAME_SETTER": SKILLS_ARTIFACT,
    "DESCRIPTION_SETTER": SKILLS_ARTIFACT,
    "TEXT_SETTERS": SKILLS_ARTIFACT,
    "TOOLS_SETTER": SKILLS_ARTIFACT,
    "FILESYSTEM_SKILL_LOADER": SKILLS_ARTIFACT,
    "CLASSPATH_SKILL_LOADER": SKILLS_ARTIFACT,
    "SKILL_LOADERS": SKILLS_ARTIFACT,
    "LOAD_SKILLS_METHOD": SKILLS_ARTIFACT,
    "LOAD_SKILL_METHOD": SKILLS_ARTIFACT,
    "LOADER_METHODS": SKILLS_ARTIFACT,
    "GROUP_COORDINATE": SKILLS_ARTIFACT,
    "SHELL_SKILLS_TYPE": SHELL_ARTIFACT,
    "SHELL_COMMAND_CONFIG": SHELL_ARTIFACT,
    "WORKING_DIRECTORY_SETTER": SHELL_ARTIFACT,
    "SHELL_ARTIFACT_ID": SHELL_ARTIFACT,
    "TOOL_ANNOTATION": CORE_ARTIFACT,
    "MCP_TOOL_PROVIDER": MCP_ARTIFACT,
    "TOOL_FILTER_SETTER": MCP_ARTIFACT,
}


def read_inventory(module: ModuleType) -> dict[str, tuple[str, ...]]:
    """Every annotated constant in *module*, mapped to the spellings it holds.

    The same shape the two guard tests read, and for the same reason: a constant
    holding something no reader understands contributes no spelling, so nothing
    would measure it. Here that is an error rather than an omission.
    """
    inventory: dict[str, tuple[str, ...]] = {}
    for constant, value in vars(module).items():
        if constant not in module.__annotations__:
            continue
        if isinstance(value, str):
            held: tuple[str, ...] = (value,)
        elif isinstance(value, frozenset | tuple | set | list):
            held = tuple(sorted(member for member in value if isinstance(member, str)))
        else:
            raise TypeError(
                f"{module.__name__}.{constant} holds {type(value).__name__}, which this sweep "
                "cannot read. Teach read_inventory the new shape rather than leaving the "
                "constant unmeasured."
            )
        if not held:
            raise TypeError(f"{module.__name__}.{constant} holds no spelling to measure.")
        inventory[constant] = held
    return inventory


def assign(module: ModuleType, roles: dict[str, Role]) -> dict[str, tuple[Role, str]]:
    """Each spelling in *module*, mapped to the role it is measured in.

    Fails closed in both directions. A constant with no role stops the sweep --
    a new spelling is exactly what a re-measurement is supposed to notice -- and
    a role for a constant that no longer exists stops it too, because it is the
    trace of an inventory entry that was renamed or dropped without the sweep
    following.
    """
    inventory = read_inventory(module)
    missing = sorted(set(inventory) - set(roles))
    if missing:
        raise KeyError(
            f"{missing} are inventoried in {module.__name__} with no role in this sweep. "
            "Assign one -- an unmeasured spelling is what the measurement exists to find."
        )
    stale = sorted(set(roles) - set(inventory))
    if stale:
        raise KeyError(
            f"{stale} carry a role here but are no longer inventoried in {module.__name__}. "
            "Drop them, so this map does not outlive what it measures."
        )
    assigned: dict[str, tuple[Role, str]] = {}
    for constant, spellings in inventory.items():
        for spelling in spellings:
            assigned.setdefault(spelling, (roles[constant], constant))
    return assigned


def assign_artifacts(
    module: ModuleType, roles: dict[str, Role], artifacts: dict[str, str]
) -> dict[str, str]:
    """Each measurable spelling in *module*, mapped to the artifact publishing it.

    Fails closed the same way :func:`assign` does: a spelling with a measurable
    role and no artifact would be swept over the wrong published history, and
    would come back absent for reasons that say nothing about upstream.
    """
    assigned = assign(module, roles)
    located: dict[str, str] = {}
    unplaced: list[str] = []
    for spelling, (role, constant) in assigned.items():
        if role is Role.NOT_MEASURED:
            continue
        if constant not in artifacts:
            unplaced.append(constant)
            continue
        located[spelling] = artifacts[constant]
    if unplaced:
        raise KeyError(
            f"{sorted(set(unplaced))} are measured but belong to no artifact here. Name the one "
            "that publishes them -- a spelling swept over the wrong release history reads as "
            "absent for a reason that is about this tool rather than about upstream."
        )
    return located
