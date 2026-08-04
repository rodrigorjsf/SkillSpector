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

"""Whether a Deep Agents agent can rewrite the Skill files it was given.

One question, asked once per resolved Skill source path, over the three keyword
arguments upstream says decide it: *"By default, agents can write to skill files
if the backend permits it and no permission rule blocks the path"*
(``docs/references/langchain-deepagents-skills.md:292-293``). So the unsafe
configuration is the one a developer gets by following the tutorial, and
``docs/adr/0008-deepagents-analyzer-resolves-one-module-deep.md`` §2 is why that
is one composed Rule rather than three: "no ``permissions`` at all" and
"``permissions`` present but silent about this path" are two spellings of the
same question, and shipped apart they would both fire on one configuration.

**Rule order is semantics, so the verdict is computed rather than matched.**
Upstream: *"Place more specific rules before broader deny rules"* (``:296``).
Each path therefore walks the rules in the order they were written and the
**first** rule that governs writing *and* covers the path decides it -- which is
what makes a specific rule placed before a broad ``deny`` mean anything. A
predicate asking "is there any ``deny`` anywhere in the list" would read the same
in a test and be wrong on exactly the configuration upstream tells people to
write.

**A rule that does not govern writing does not end the walk.** A ``read`` rule
covering the path says nothing about whether the path can be rewritten, so the
walk continues past it to whatever does.

**The backend contributes unknowability, never a verdict.** Issue #72 was written
expecting a "read-only backend" to clear a path, and the captured reference
documents no such thing: all four backends it lists (``:167-171``) are stores
that hold files, and the only read-only-ness upstream describes is the ``deny``
rule of its own "Enforce read-only skills" example (``:240-266``). Inventing a
spelling for a backend that does not exist upstream is what
``docs/adr/0005-langchain4j-upstream-vocabulary.md`` exists to prevent. What the
backend really contributes is whether the Scan can see what a path holds at all,
and that is already answered one layer down: a Skill path routed into a store
whose contents are computed per request is an
:class:`~skillspector.deepagents.host_config.OpaqueRoute`, reported as
``DA-UNRESOLVED``, and it reaches no verdict here.

**Files that are not on disk are still writable.** ADR 0008 §3's other boundary
-- Skill paths under a ``StoreBackend`` or the default ``StateBackend`` are not
on disk, so no Scan will map them to a directory -- is about the shadowing Rule
of issue #73, which has to open the files. It must not be borrowed here: agent
state is exactly what a self-modifying agent rewrites, and letting "not on disk"
clear the verdict would silence this Rule on
``create_deep_agent(model=..., skills=[...])`` -- the configuration the tutorial
teaches, and the one the whole Spec exists to report.

Provenance
----------

Captured from ``docs/references/langchain-deepagents-skills.md`` (upstream
<https://docs.langchain.com/labs/deep-agents/skills>).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase

from skillspector.deepagents import vocabulary
from skillspector.deepagents.host_config import AgentConfiguration, PermissionRule

# Both write tools, because upstream's gate is written over both --
# ``interrupt_on={"write_file": True, "edit_file": True}`` -- and half of it is
# an agent that still edits a Skill file without anyone being asked.
_WRITE_TOOLS: frozenset[str] = frozenset({vocabulary.WRITE_FILE, vocabulary.EDIT_FILE})

_MODES: frozenset[str] = frozenset({vocabulary.DENY, vocabulary.INTERRUPT})


@dataclass(frozen=True)
class WritablePath:
    """One resolved Skill source path nothing denies the agent write access to.

    *mitigated* says a human is put in front of the write -- by the deciding
    rule's ``mode="interrupt"``, or by an ``interrupt_on`` gate over both write
    tools. ADR 0008 §2 makes that a severity of this verdict rather than a Rule
    of its own: an approval prompt is not the same as a denial, and a
    configuration carrying one has still handed the agent its own instructions
    to rewrite.
    """

    path: str
    line: int
    mitigated: bool


@dataclass(frozen=True)
class Assessment:
    """What one ``create_deep_agent(...)`` call's Skill paths came to.

    The two lists are exclusive by construction. *unreadable_rule_lines* being
    non-empty empties *writable*: a permission rule written in a shape this Scan
    cannot read leaves the whole ordered walk undecided, because the part it
    could not read may be the ``paths`` that would have decided every one of
    them.
    """

    writable: tuple[WritablePath, ...]
    unreadable_rule_lines: tuple[int, ...]


def assess(configuration: AgentConfiguration) -> Assessment:
    """Judge one call's Skill source paths, or decline where a boundary was reported.

    Declines -- returns nothing at all -- when the Skill list, the permission
    rules or the backend did not resolve. Each of those is already a
    ``DA-UNRESOLVED`` Finding, and a writability verdict computed over a
    configuration the Scan admits it could not read would be a guess wearing the
    same severity as a measurement.

    An *absent* argument is not a boundary and does not decline: no
    ``permissions`` is no rules, and no ``backend`` is the default one. Those are
    configurations, and they are the ones this Rule most exists to judge.
    """
    skills = configuration.skill_paths
    if skills is None or skills.unresolved:
        return Assessment(writable=(), unreadable_rule_lines=())
    if configuration.backend is not None and configuration.backend.unresolved:
        return Assessment(writable=(), unreadable_rule_lines=())
    if configuration.permission_rules is not None and configuration.permission_rules.unresolved:
        return Assessment(writable=(), unreadable_rule_lines=())

    rules = _rules(configuration)
    unreadable = tuple(rule.line for rule in rules if not _readable(rule))
    if unreadable:
        return Assessment(writable=(), unreadable_rule_lines=unreadable)

    # A path routed into a store whose contents are computed per request is
    # already reported as `DA-UNRESOLVED`, and this is where that boundary is
    # honoured rather than talked about: it reaches no verdict.
    opaque = {route.path for route in configuration.opaque_routes}
    gated = _interrupts_every_write(configuration)

    writable: list[WritablePath] = []
    for path in _paths(skills.value):
        if any(path.startswith(prefix) for prefix in opaque):
            continue
        deciding = _deciding_rule(rules, path)
        if deciding is not None and deciding.settings[vocabulary.MODE] == vocabulary.DENY:
            continue
        mitigated = gated or (
            deciding is not None and deciding.settings[vocabulary.MODE] == vocabulary.INTERRUPT
        )
        writable.append(WritablePath(path=path, line=skills.line, mitigated=mitigated))
    return Assessment(writable=tuple(writable), unreadable_rule_lines=())


def _paths(value: object) -> tuple[str, ...]:
    """The resolved Skill source paths, however the resolver spelled its result."""
    if not isinstance(value, tuple):
        return ()
    return tuple(path for path in value if isinstance(path, str))


def _rules(configuration: AgentConfiguration) -> tuple[PermissionRule, ...]:
    """The permission rules the call declared, in the order they were written."""
    rules = configuration.permission_rules
    if rules is None or not isinstance(rules.value, tuple):
        return ()
    return tuple(rule for rule in rules.value if isinstance(rule, PermissionRule))


def _readable(rule: PermissionRule) -> bool:
    """Whether a rule is written in the shape upstream documents.

    All three keyword arguments present, ``operations`` and ``paths`` sequences
    of strings, and a ``mode`` this Scan knows the meaning of. A rule failing any
    of that is not a rule this module guesses at: an unrecognized ``mode`` could
    be a denial or a permission, and reading it either way would be wrong in the
    direction nobody would notice.
    """
    settings = rule.settings
    return (
        _string_sequence(settings.get(vocabulary.OPERATIONS)) is not None
        and _string_sequence(settings.get(vocabulary.PATHS)) is not None
        and settings.get(vocabulary.MODE) in _MODES
    )


def _string_sequence(value: object) -> tuple[str, ...] | None:
    """*value* as a sequence of strings, or ``None`` if it is not one.

    A bare string is refused rather than read as a one-element sequence: it
    would iterate into characters, and upstream writes both arguments as lists.
    """
    if isinstance(value, str) or not isinstance(value, Sequence):
        return None
    if not all(isinstance(member, str) for member in value):
        return None
    return tuple(str(member) for member in value)


def _deciding_rule(rules: Sequence[PermissionRule], path: str) -> PermissionRule | None:
    """The first rule that governs writing and covers *path*, if any."""
    return next(
        (
            rule
            for rule in rules
            if vocabulary.WRITE in (_string_sequence(rule.settings[vocabulary.OPERATIONS]) or ())
            and _covers(rule, path)
        ),
        None,
    )


def _covers(rule: PermissionRule, path: str) -> bool:
    """Whether any of a rule's path patterns matches *path*.

    Glob matching, case-sensitively on every platform: these are agent-visible
    backend paths rather than paths on the machine running the Scan, so folding
    case where the host happens to would make one configuration read two ways.

    The match is deliberately literal. ``paths=["/skills/shared"]`` does not
    cover the Skill source ``/skills/shared/``, and a rule written ``/skills/**``
    does not cover a Skill source written ``skills/`` -- upstream's paths are
    absolute and its own examples pair the two spellings exactly. Treating a
    near-miss as a match would clear a Finding on a rule that does not apply,
    which is the failure direction nothing downstream can recover from.
    """
    patterns = _string_sequence(rule.settings[vocabulary.PATHS]) or ()
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def _interrupts_every_write(configuration: AgentConfiguration) -> bool:
    """Whether ``interrupt_on`` puts a human in front of both write tools.

    Wider than ``mode="interrupt"`` on purpose, because upstream is: it
    *"requires approval for all filesystem writes, not only skills paths"*
    (``:286``), so where it is present it mitigates every path this call was
    given rather than one rule's.

    An ``interrupt_on`` this Scan could not read is **no** mitigation, and that
    asymmetry is deliberate. An unconfirmed mitigation left in place would lower
    the severity of a real Finding on evidence nobody has; refused, it leaves the
    Finding at full severity, which is the direction a reviewer can correct.
    """
    gate = configuration.interrupt_on
    if gate is None or gate.unresolved or not isinstance(gate.value, frozenset):
        return False
    return _WRITE_TOOLS <= gate.value
