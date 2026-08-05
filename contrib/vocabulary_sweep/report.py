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

"""Turn a release-by-release sweep into the claim a vocabulary module records.

The output is what a maintainer copies into the inventory: the range swept, and
for each spelling either "observed across the whole range" or the release it
first appears in. The verdict line is the part that decides whether the sweep
changes anything -- a spelling that was **removed** after appearing is the event
ADR 0005 named as the one that reopens per-version API profiles, so it is
reported as its own category rather than folded into "changed".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class History:
    """One spelling's presence across the swept range."""

    spelling: str
    first: str | None
    last_absent: str | None
    removed_at: str | None

    @property
    def summary(self) -> str:
        if self.first is None:
            return "never observed"
        if self.removed_at is not None:
            return f"observed from {self.first}, REMOVED at {self.removed_at}"
        if self.last_absent is not None:
            return f"added at {self.first}"
        return "observed across the whole range"


def history(spelling: str, observed: dict[str, bool]) -> History:
    """When *spelling* appeared, and whether it ever went away again.

    ``removed_at`` is the first release after its introduction that no longer
    carries it. A spelling absent from early releases and present ever after was
    added; one that disappears again is the event that reopens a rejected option.
    """
    versions = list(observed)
    present = [version for version in versions if observed[version]]
    if not present:
        return History(spelling, None, versions[-1] if versions else None, None)
    first = present[0]
    after = versions[versions.index(first) :]
    gone = [version for version in after if not observed[version]]
    before = versions[: versions.index(first)]
    return History(
        spelling=spelling,
        first=first,
        last_absent=before[-1] if before else None,
        removed_at=gone[0] if gone else None,
    )


def render(swept: dict[str, dict[str, dict[str, bool]]], *, framework: str) -> str:
    """The whole sweep as the text a maintainer reads and records.

    One section per published unit -- a distribution, or one of LangChain4j's
    four artifacts -- because a range only means anything within the history it
    was measured over, and those four are not on one version line. The verdict is
    computed across all of them: a spelling removed from any is the event.
    """
    lines: list[str] = [f"{framework}"]
    every: list[History] = []
    for unit in sorted(swept):
        ordered = list(next(iter(swept[unit].values()), {}))
        lines += [
            "",
            f"{unit}: {len(ordered)} releases swept"
            + (f", {ordered[0]} through {ordered[-1]}" if ordered else ""),
        ]
        histories = [history(spelling, swept[unit][spelling]) for spelling in sorted(swept[unit])]
        every += histories
        width = max((len(entry.spelling) for entry in histories), default=0)
        lines += [f"  {entry.spelling.ljust(width)}  {entry.summary}" for entry in histories]
    lines += ["", verdict(every)]
    return "\n".join(lines)


def histories(swept: dict[str, dict[str, dict[str, bool]]]) -> list[History]:
    """Every spelling's history across every published unit in *swept*."""
    return [
        history(spelling, observed)
        for unit in sorted(swept)
        for spelling, observed in sorted(swept[unit].items())
    ]


def blocking(histories: list[History]) -> bool:
    """Whether this sweep found something a maintainer must settle before recording.

    Two shapes qualify, and both mean the inventory and the published releases
    disagree: a spelling that went away after appearing, and one that was never
    published in role at all. Separated from :func:`verdict` so a caller can exit
    non-zero on them -- a trigger that says "run this and read the output" is
    only as good as the reader, and this is the half a reader can skim past.
    """
    return any(entry.removed_at or entry.first is None for entry in histories)


def verdict(histories: list[History]) -> str:
    """The one line that says whether this sweep changes the stability claim."""
    removed = [entry.spelling for entry in histories if entry.removed_at]
    never = [entry.spelling for entry in histories if entry.first is None]
    added = [entry.spelling for entry in histories if entry.last_absent and not entry.removed_at]
    if removed:
        return (
            f"VERDICT: {removed} were REMOVED after appearing. This is the event ADR 0005 "
            "named as reopening per-version API profiles -- do not record a range without "
            "deciding that question."
        )
    if never:
        return (
            f"VERDICT: {never} were never observed in role across the swept range. Either the "
            "inventory is stale or the role assigned to them is wrong; settle which before "
            "recording anything."
        )
    if added:
        return (
            f"VERDICT: no spelling was ever removed. {added} were added mid-range; annotate each "
            "with the release it first appears in, and record the range."
        )
    return "VERDICT: no spelling was ever added or removed across the swept range."
