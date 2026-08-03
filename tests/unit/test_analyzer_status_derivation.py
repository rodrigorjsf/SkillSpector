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

"""``analyzer_status_for_events`` is the only place the status cascade is written.

Where ``tests/unit/test_analyzer_status.py`` closes the *vocabulary* a status is
drawn from (#47), this closes the *derivation* that picks from it (#60): empty
work means ``not_applicable``, otherwise ``failed`` beats ``degraded`` beats
``completed``. Three Analyzers used to re-inline that cascade, and a drift
between the copies would have produced a *valid* status either way -- nothing
would have failed.

**How the cascade is recognised.** By its one distinctive term rather than by
its shape. ``degraded`` is the branch only this derivation has: the two-way
``failed``/``completed`` derivations in ``llm_analyzer_base`` and
``nodes/meta_analyzer`` never name it, and every other status is written by
modules that legitimately report one directly. So a fourth copy of the cascade
cannot be written without naming ``AnalyzerStatus.DEGRADED`` outside the ledger,
and that is what this reads.

Matching the shape instead -- a nested conditional expression over a set of
outcomes -- was considered and rejected: it is a fuzzy match that a
rearrangement into ``if``/``elif`` would slip past, while the term is exact.

**What it therefore misses**, stated rather than left to be discovered: a
re-inlined cascade that reaches ``degraded`` through an alias or a lookup table
rather than the attribute, and a copy living outside ``src/skillspector``. Both
are contrivances next to the copy-paste this exists to catch.

**What it over-reaches on**, equally stated: ``degraded`` is the one status a
module may no longer report *directly*. An Analyzer that legitimately wanted to
report a degraded result without summarizing ledger events would fail this
guard, and the fix would be to widen ``analyzer_status_for_events`` rather than
to write the status inline. Nothing in the package wants that today; the other
five statuses are unaffected and are still written directly wherever a gate or
an ``unavailable`` result calls for one.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "skillspector"

# The module that owns the derivation, relative to the package root.
_DERIVATION_HOME = "inspection_ledger.py"

_ENUM = "AnalyzerStatus"
_DEGRADED = "DEGRADED"


def _modules_naming_degraded(root: Path = _SRC) -> set[str]:
    """Every module under *root* that writes ``AnalyzerStatus.DEGRADED``, by relative path.

    Parameterized by root so the control below can point it at a synthetic
    module rather than at the tree it is guarding.
    """
    naming: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == _DEGRADED
                and isinstance(node.value, ast.Name)
                and node.value.id == _ENUM
            ):
                naming.add(path.relative_to(root).as_posix())
    return naming


class TestTheCascadeHasOneHome:
    def test_only_the_ledger_derives_a_degraded_status(self) -> None:
        """A module naming ``DEGRADED`` is deriving a status, not reporting one."""
        assert _modules_naming_degraded() == {_DERIVATION_HOME}, (
            "A module outside the inspection ledger names AnalyzerStatus.DEGRADED. "
            "The only reason to is re-inlining the cascade -- call "
            "analyzer_status_for_events instead."
        )

    def test_a_fourth_copy_is_noticed(self, tmp_path: Path) -> None:
        """The control: a re-inlined cascade in a module the guard has never seen.

        Asserting the ledger is in its own result would prove nothing the
        equality above does not already entail. This drives the reader with a
        module written to fail it, so a pass means the reader looks rather than
        that the tree happens to be clean.
        """
        (tmp_path / "fourth_analyzer.py").write_text(
            "from skillspector.inspection_ledger import AnalyzerStatus\n"
            "\n"
            "def status(outcomes):\n"
            "    return (\n"
            "        AnalyzerStatus.FAILED\n"
            "        if 'failed' in outcomes\n"
            "        else AnalyzerStatus.DEGRADED\n"
            "        if 'skipped' in outcomes\n"
            "        else AnalyzerStatus.COMPLETED\n"
            "    )\n",
            encoding="utf-8",
        )
        (tmp_path / "innocent.py").write_text("STATUS = 'degraded'\n", encoding="utf-8")

        assert _modules_naming_degraded(tmp_path) == {"fourth_analyzer.py"}
