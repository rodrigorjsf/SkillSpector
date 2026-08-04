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

"""How far a Deep Agents host configuration resolves, and where it stops.

``create_deep_agent(...)`` is where a Deep Agents application says which Skill
sources the agent is given, what it may do to them, and whether they are on disk
at all. This module reads that call, and
``FilesystemPermission(...)`` inside it, and resolves **a literal and a constant
declared in the same module. Nothing else.**

That boundary is not new and is not this module's invention.
``docs/adr/0008-deepagents-analyzer-resolves-one-module-deep.md`` §1 copies it
from the Java track, where ``langchain4j/skill_definitions.py`` resolves same-unit
``String`` constants and returns nothing for everything else, citing §3.6 of
``docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md``: following a value anywhere else is the
arbitrary dataflow that is out of scope. Copying it keeps that one line in the
project rather than one line per Framework.

So a value assembled at runtime resolves to nothing, and nothing is the answer
this module returns -- never a guess. The Analyzer turns each of those into a
``DA-UNRESOLVED`` Finding that names *which* thing was unresolvable, which is the
whole point: a report that says nothing about the surface it never examined
reads as a clean report.

**What this module deliberately does not decide.** It says whether the backend
was readable and which literal Skill source paths are routed somewhere whose
contents are computed per request. It does **not** say whether any path is
writable, whether a permission rule covers it, or which rule wins -- that verdict
is issue #72, and the rule-order semantics it needs are stated in the captured
reference rather than here. This module resolves; it does not judge.

Known limits, stated rather than discovered:

* An aliased import -- ``from deepagents import create_deep_agent as make_agent``
  -- is not matched. Recognizing it means tracking import bindings, which is the
  same interprocedural reach §3.6 declined.
* A backend nested inside another backend's route is recognized by name and not
  walked further. One level is what the captured reference documents.
* A name assigned more than once at module level resolves to nothing, because
  which assignment reaches the call is control flow this module does not model.
* Only keyword arguments are read. A configuration passed positionally --
  ``create_deep_agent(model, build_skills())`` -- is not seen at all, so it
  raises no boundary either. Every ``create_deep_agent(`` on the captured page
  names its arguments, and reading by position would mean pinning an upstream
  signature order that no rename would announce; ``_permission_rules`` refuses
  positional arguments for the same reason.

Provenance
----------

Captured from ``docs/references/langchain-deepagents-skills.md`` (upstream
<https://docs.langchain.com/labs/deep-agents/skills>).
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from skillspector.deepagents import vocabulary

# `None` is a value a literal can legitimately resolve to -- `mode=None` is
# written by nobody, but nothing stops it -- so "did not resolve" needs a marker
# of its own rather than borrowing it.
_UNRESOLVED: Final[object] = object()

_BACKENDS: Final[frozenset[str]] = frozenset(
    {
        vocabulary.COMPOSITE_BACKEND,
        vocabulary.STORE_BACKEND,
        vocabulary.STATE_BACKEND,
        vocabulary.FILESYSTEM_BACKEND,
    }
)


@dataclass(frozen=True)
class Resolution:
    """One keyword argument of ``create_deep_agent(...)``, as far as it resolved.

    *line* is where the argument's expression is written, so a Finding sends a
    reviewer to the argument rather than to the top of a multi-line call.
    *value* is ``None`` when the expression is one this module refuses to guess
    at -- the boundary, not an empty configuration. An argument that is simply
    absent is represented by the absence of a ``Resolution`` at all.
    """

    line: int
    value: object | None

    @property
    def unresolved(self) -> bool:
        """Whether the expression fell on the boundary side."""
        return self.value is None


@dataclass(frozen=True)
class PermissionRule:
    """One ``FilesystemPermission(...)`` whose every keyword argument resolved.

    *settings* is keyed by the keyword as written. The keywords are not
    inventoried in :mod:`skillspector.deepagents.vocabulary` on purpose: this
    module requires all of them to resolve without caring which they are, so it
    never matches on their spellings. The Rule that reads them by name is #72.
    """

    line: int
    settings: Mapping[str, object]


@dataclass(frozen=True)
class OpaqueRoute:
    """A resolved Skill source path routed somewhere the Scan cannot look into.

    Upstream's own namespaced-skills example is the shape: a literal ``routes``
    key mapping a Skill path onto a ``StoreBackend`` whose namespace is computed
    from the request. The *path* resolves; what lives at it does not, so the
    writability verdict has nowhere to land. ADR 0008 §1 requires this case to
    reach the boundary rather than be treated as resolved because the route key
    happened to be a string.
    """

    path: str
    line: int


@dataclass(frozen=True)
class AgentConfiguration:
    """One ``create_deep_agent(...)`` call, read as far as this module resolves.

    Each of the three arguments is ``None`` when it is not written at all, which
    is a different statement from a ``Resolution`` that did not resolve. Absent
    is a configuration -- no Skills, no permission rules, the default backend --
    and the Analyzer says nothing about it. Unresolved is a boundary.
    """

    line: int
    skill_paths: Resolution | None
    permission_rules: Resolution | None
    backend: Resolution | None
    opaque_routes: tuple[OpaqueRoute, ...]


def find_agent_configurations(tree: ast.Module) -> list[AgentConfiguration]:
    """Every ``create_deep_agent(...)`` in one module, read one module deep.

    Walks the whole tree rather than its top level: upstream's own dynamic
    example builds the agent inside ``create_agent_for_user(user_role)``, and a
    call this module could not see is a configuration nobody would be told
    about.

    Constants are collected from the module's top level only. A name bound
    inside a function or a class body resolves to nothing, and so does a
    function parameter -- which is the right answer for ``user_role``, not a
    limitation to work around.
    """
    constants = _module_constants(tree)
    return [
        _configuration(node, constants)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _called_name(node) == vocabulary.CREATE_DEEP_AGENT
    ]


def _configuration(call: ast.Call, constants: Mapping[str, ast.expr]) -> AgentConfiguration:
    """Read one call's three arguments, and the routes that cover its Skill paths."""
    arguments = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None}

    skills = arguments.get(vocabulary.SKILLS)
    skill_paths = (
        None if skills is None else Resolution(skills.lineno, _string_sequence(skills, constants))
    )

    permissions = arguments.get(vocabulary.PERMISSIONS)
    permission_rules = (
        None
        if permissions is None
        else Resolution(permissions.lineno, _permission_rules(permissions, constants))
    )

    backend_argument = arguments.get(vocabulary.BACKEND)
    backend, routes = (
        (None, ()) if backend_argument is None else _backend(backend_argument, constants)
    )

    # A route is only a boundary for a Skill path that resolved. Where the Skill
    # list itself did not resolve, that is already reported and saying it twice
    # in two vocabularies would describe one silence as two.
    resolved_paths = skill_paths.value if skill_paths is not None else None
    covered = (
        ()
        if not isinstance(resolved_paths, tuple)
        else tuple(route for route in routes if _covers_any(route.path, resolved_paths))
    )

    return AgentConfiguration(
        line=call.lineno,
        skill_paths=skill_paths,
        permission_rules=permission_rules,
        backend=backend,
        opaque_routes=covered,
    )


def _covers_any(prefix: str, paths: tuple[object, ...]) -> bool:
    """Whether a route prefix routes any of *paths*.

    ``routes`` maps path *prefixes* onto backends, so a route covers a Skill
    source path when the path starts with it. The equal case -- upstream's own
    example routes exactly the path it passes -- is covered by the same test.
    """
    return any(isinstance(path, str) and path.startswith(prefix) for path in paths)


def _module_constants(tree: ast.Module) -> dict[str, ast.expr]:
    """The module's top-level names, mapped to the expression each was assigned.

    A name assigned more than once is dropped rather than resolved to its last
    assignment: which one reaches the call is control flow, and guessing is the
    thing this module exists not to do.
    """
    assigned: dict[str, ast.expr] = {}
    reassigned: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets: list[ast.expr] = list(statement.targets)
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            targets = [statement.target]
            value = statement.value
        else:
            continue
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id in assigned:
                reassigned.add(target.id)
            assigned[target.id] = value
    return {name: value for name, value in assigned.items() if name not in reassigned}


def _effective(node: ast.expr, constants: Mapping[str, ast.expr]) -> ast.expr | None:
    """Follow a name to the expression it was assigned, or return the node itself.

    Names chain -- ``BACKEND = _BACKEND`` -- so this follows them until it
    reaches something that is not a name. A name it cannot resolve, and a cycle,
    both return ``None``: the boundary.
    """
    seen: set[str] = set()
    current = node
    while isinstance(current, ast.Name):
        if current.id in seen:
            return None
        seen.add(current.id)
        assigned = constants.get(current.id)
        if assigned is None:
            return None
        current = assigned
    return current


def _called_name(call: ast.Call) -> str | None:
    """The name a call is written with, whether bare or attribute-qualified."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _literal(node: ast.expr, constants: Mapping[str, ast.expr]) -> object:
    """The literal value of an expression, or ``_UNRESOLVED``."""
    effective = _effective(node, constants)
    if effective is None:
        return _UNRESOLVED
    try:
        return ast.literal_eval(effective)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return _UNRESOLVED


def _string_sequence(node: ast.expr, constants: Mapping[str, ast.expr]) -> tuple[str, ...] | None:
    """The Skill source paths a ``skills=`` argument names, or ``None``.

    Each element is resolved on its own rather than the whole list at once, so a
    list literal holding a same-module constant still resolves. One element that
    does not resolve makes the whole list unresolved: a partially known Skill
    list would be reported as a complete one.
    """
    effective = _effective(node, constants)
    if not isinstance(effective, ast.List | ast.Tuple):
        return None
    paths: list[str] = []
    for element in effective.elts:
        value = _literal(element, constants)
        if not isinstance(value, str):
            return None
        paths.append(value)
    return tuple(paths)


def _permission_rules(
    node: ast.expr, constants: Mapping[str, ast.expr]
) -> tuple[PermissionRule, ...] | None:
    """The permission rules a ``permissions=`` argument declares, or ``None``.

    Every element must be a ``FilesystemPermission(...)`` written with keyword
    arguments that all resolve. A positional argument is refused rather than
    read by position: rule order is semantics here, and so is which setting a
    value belongs to.
    """
    effective = _effective(node, constants)
    if not isinstance(effective, ast.List | ast.Tuple):
        return None
    rules: list[PermissionRule] = []
    for element in effective.elts:
        call = _effective(element, constants)
        if not isinstance(call, ast.Call):
            return None
        if _called_name(call) != vocabulary.FILESYSTEM_PERMISSION or call.args:
            return None
        settings: dict[str, object] = {}
        for keyword in call.keywords:
            if keyword.arg is None:
                return None
            value = _literal(keyword.value, constants)
            if value is _UNRESOLVED:
                return None
            settings[keyword.arg] = value
        rules.append(PermissionRule(line=call.lineno, settings=settings))
    return tuple(rules)


def _backend(
    node: ast.expr, constants: Mapping[str, ast.expr]
) -> tuple[Resolution, tuple[OpaqueRoute, ...]]:
    """Which backend a ``backend=`` argument names, and which routes stay opaque.

    Recognizing the backend is naming it: the four upstream backends resolve to
    their own spelling, and anything else -- a helper call, a name bound
    elsewhere -- resolves to nothing. Only a ``CompositeBackend`` is walked into,
    because it is the only one that maps paths onto other backends; a backend
    nested inside one of its routes is recognized by name and not walked again.
    """
    resolution = Resolution(node.lineno, None)
    call = _effective(node, constants)
    if not isinstance(call, ast.Call):
        return resolution, ()
    name = _called_name(call)
    if name not in _BACKENDS:
        return resolution, ()
    if name != vocabulary.COMPOSITE_BACKEND:
        return Resolution(node.lineno, name), ()

    routes = next(
        (keyword.value for keyword in call.keywords if keyword.arg == vocabulary.ROUTES), None
    )
    if routes is None:
        return Resolution(node.lineno, name), ()
    mapping = _effective(routes, constants)
    if not isinstance(mapping, ast.Dict):
        return resolution, ()

    opaque: list[OpaqueRoute] = []
    for key, target in zip(mapping.keys, mapping.values, strict=True):
        # A `**other` spread inside the mapping leaves a `None` key, and what it
        # contributes is exactly what this module will not guess at.
        if key is None:
            return resolution, ()
        path = _literal(key, constants)
        if not isinstance(path, str):
            return resolution, ()
        routed = _effective(target, constants)
        if not isinstance(routed, ast.Call) or _called_name(routed) not in _BACKENDS:
            return resolution, ()
        if _called_name(routed) == vocabulary.STORE_BACKEND and _is_computed(routed, constants):
            opaque.append(OpaqueRoute(path=path, line=key.lineno))
    return Resolution(node.lineno, name), tuple(opaque)


def _is_computed(call: ast.Call, constants: Mapping[str, ast.expr]) -> bool:
    """Whether a store is configured with something evaluated per request.

    Upstream's example is a namespace lambda over the request context, and its
    consequence is that what lives at the routed path differs per caller. Asked
    of the arguments as a whole rather than of the namespace by name: any
    argument this module cannot resolve leaves the store's contents unknowable
    in the same way, and asking generally means no keyword spelling is matched
    on here.
    """
    return any(_literal(argument, constants) is _UNRESOLVED for argument in call.args) or any(
        keyword.arg is None or _literal(keyword.value, constants) is _UNRESOLVED
        for keyword in call.keywords
    )
