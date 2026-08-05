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

"""Discovery for a Repository Scan, driven by constructed directory trees.

Every test here builds a tree and asserts the *set of Skills found*, which is
the external behavior. Nothing asserts how the walk got there.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from skillspector.cli import FormatChoice, _merge_repository_sarif, _scan_repository
from skillspector.repository_scan import (
    DISCOVERY_ROOTS,
    JVM_BUILD_DIRECTORIES,
    DiscoveredSkill,
    discover_skills,
)


def make_skill(root: Path, relative: str, name: str | None = None) -> Path:
    """Create a Skill directory declaring *name* at *relative* under *root*."""
    directory = root / relative
    directory.mkdir(parents=True, exist_ok=True)
    declared = name or relative.rsplit("/", 1)[-1]
    (directory / "SKILL.md").write_text(
        f"---\nname: {declared}\ndescription: A test Skill.\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return directory


def found(root: Path, **kwargs: Any) -> list[str]:
    return [skill.relative_path for skill in discover_skills(root, **kwargs)]


class TestDiscovery:
    """Which Skills a Repository Scan finds inside a repository."""

    def test_a_skill_under_each_conventional_root_is_found(self, tmp_path: Path) -> None:
        for root in DISCOVERY_ROOTS:
            make_skill(tmp_path, f"{root}/alpha-{root.replace('/', '-')}")

        assert len(found(tmp_path)) == len(DISCOVERY_ROOTS)

    def test_a_root_pattern_matches_as_a_path_suffix_in_two_modules(self, tmp_path: Path) -> None:
        """A repository holding many modules needs no configuration."""
        make_skill(tmp_path, "modules/billing/src/main/resources/skills/invoice")
        make_skill(tmp_path, "modules/orders/src/main/resources/skills/refund")

        assert found(tmp_path) == [
            "modules/billing/src/main/resources/skills/invoice",
            "modules/orders/src/main/resources/skills/refund",
        ]

    def test_a_skill_nested_below_a_root_is_found(self, tmp_path: Path) -> None:
        make_skill(tmp_path, "skills/team/billing/escalation")

        assert found(tmp_path) == ["skills/team/billing/escalation"]

    def test_a_declaring_directory_outside_every_root_is_not_a_skill(self, tmp_path: Path) -> None:
        """Otherwise a SKILL.md shipped as documentation or test data is Scanned."""
        make_skill(tmp_path, "docs/examples/sample")

        assert found(tmp_path) == []

    def test_a_root_pattern_matches_whole_segments_only(self, tmp_path: Path) -> None:
        """``my-skills`` ends with the letters of ``skills`` and is not that root."""
        make_skill(tmp_path, "my-skills/decoy")

        assert found(tmp_path) == []

    def test_a_directory_under_a_root_that_declares_nothing_is_not_a_skill(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "skills" / "empty").mkdir(parents=True)

        assert found(tmp_path) == []

    def test_the_depth_bound_is_respected(self, tmp_path: Path) -> None:
        make_skill(tmp_path, "skills/shallow")
        make_skill(tmp_path, "skills/a/b/c/d/deep")

        assert found(tmp_path, max_depth=3) == ["skills/shallow"]
        assert "skills/a/b/c/d/deep" in found(tmp_path)

    def test_an_input_that_is_not_a_directory_finds_nothing(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_text("not a directory", encoding="utf-8")

        assert found(target) == []


class TestJvmBuildDirectories:
    """Skipped here, and *only* here -- both halves asserted."""

    @pytest.mark.parametrize("build_directory", sorted(JVM_BUILD_DIRECTORIES))
    def test_a_skill_inside_compiled_output_is_not_found(
        self, tmp_path: Path, build_directory: str
    ) -> None:
        make_skill(tmp_path, f"{build_directory}/classes/skills/ghost")

        assert found(tmp_path) == []

    def test_the_ordinary_walk_still_reads_them(self, tmp_path: Path) -> None:
        """The other half. Adding these to the ordinary skip set would change
        ``components`` and the ledger's excluded-directory events for every
        existing Scan of a tree holding one, which the behavior gate forbids.
        """
        from skillspector.nodes.build_context import build_context

        (tmp_path / "target").mkdir()
        (tmp_path / "target" / "Compiled.txt").write_text("output", encoding="utf-8")
        (tmp_path / "SKILL.md").write_text("---\nname: t\n---\n", encoding="utf-8")

        components = build_context({"skill_path": str(tmp_path)})["components"]

        assert "target/Compiled.txt" in components


class TestOverridingTheRoots:
    """``--repo-scan-root`` replaces the conventional list."""

    def test_an_override_finds_a_layout_the_defaults_miss(self, tmp_path: Path) -> None:
        make_skill(tmp_path, "playbooks/onboarding")

        assert found(tmp_path) == []
        assert found(tmp_path, roots=("playbooks",)) == ["playbooks/onboarding"]

    def test_an_override_replaces_rather_than_extends(self, tmp_path: Path) -> None:
        make_skill(tmp_path, "skills/alpha")
        make_skill(tmp_path, "playbooks/onboarding")

        assert found(tmp_path, roots=("playbooks",)) == ["playbooks/onboarding"]


class TestEachSkillCarriesItsOwnManifest:
    """The defect this replaces is one anonymous Skill with an empty Manifest."""

    def test_the_declared_name_is_read_from_each_skill(self, tmp_path: Path) -> None:
        make_skill(tmp_path, "skills/one", name="invoice-triage")
        make_skill(tmp_path, "skills/two", name="refund-approval")

        assert [skill.name for skill in discover_skills(tmp_path)] == [
            "invoice-triage",
            "refund-approval",
        ]

    def test_each_skill_is_scanned_at_its_own_path(self, tmp_path: Path, monkeypatch) -> None:
        make_skill(tmp_path, "skills/one")
        make_skill(tmp_path, "skills/two")
        scanned: list[str] = []

        def fake_invoke(state: dict, config: object = None) -> dict:
            scanned.append(str(state["input_path"]))
            return {"risk_score": 0, "report_body": "{}", "sarif_report": {"runs": []}}

        monkeypatch.setattr("skillspector.cli.graph", SimpleNamespace(invoke=fake_invoke))

        _scan_repository(
            tmp_path,
            DISCOVERY_ROOTS,
            FormatChoice.json,
            tmp_path / "out.json",
            no_llm=True,
            yara_rules_dir=None,
            baseline=None,
            show_suppressed=False,
            verbose=False,
        )

        assert scanned == [str(tmp_path / "skills" / "one"), str(tmp_path / "skills" / "two")]


class TestTheOutputsCiNeeds:
    """SARIF, the exit code, and the baseline all work on a Repository Scan."""

    def test_sarif_locations_are_relative_to_the_repository(self) -> None:
        merged = _merge_repository_sarif(
            [
                (
                    DiscoveredSkill(Path("/x"), "skills/one", "one"),
                    {
                        "sarif_report": {
                            "version": "2.1.0",
                            "runs": [
                                {
                                    "results": [
                                        {
                                            "ruleId": "P1",
                                            "locations": [
                                                {
                                                    "physicalLocation": {
                                                        "artifactLocation": {"uri": "SKILL.md"}
                                                    }
                                                }
                                            ],
                                        }
                                    ]
                                }
                            ],
                        }
                    },
                )
            ]
        )

        uri = merged["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "artifactLocation"
        ]["uri"]
        assert uri == "skills/one/SKILL.md"

    def test_one_run_is_carried_per_skill(self) -> None:
        entries = [
            (
                DiscoveredSkill(Path("/x"), f"skills/{name}", name),
                {"sarif_report": {"version": "2.1.0", "runs": [{"results": []}]}},
            )
            for name in ("one", "two")
        ]

        assert len(_merge_repository_sarif(entries)["runs"]) == 2

    def test_a_score_above_the_threshold_exits_one(self, tmp_path: Path, monkeypatch) -> None:
        make_skill(tmp_path, "skills/one")
        monkeypatch.setattr(
            "skillspector.cli.graph",
            SimpleNamespace(
                invoke=lambda state, config=None: {"risk_score": 99, "report_body": "{}"}
            ),
        )

        with pytest.raises(typer.Exit) as exit_info:
            _scan_repository(
                tmp_path,
                DISCOVERY_ROOTS,
                FormatChoice.json,
                tmp_path / "out.json",
                no_llm=True,
                yara_rules_dir=None,
                baseline=None,
                show_suppressed=False,
                verbose=False,
            )

        assert exit_info.value.exit_code == 1

    def test_a_failed_execution_exits_two_after_writing_the_report(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        make_skill(tmp_path, "skills/one")
        output = tmp_path / "out.json"
        monkeypatch.setattr(
            "skillspector.cli.graph",
            SimpleNamespace(
                invoke=lambda state, config=None: {
                    "risk_score": 0,
                    "report_body": "{}",
                    "execution_successful": False,
                }
            ),
        )

        with pytest.raises(typer.Exit) as exit_info:
            _scan_repository(
                tmp_path,
                DISCOVERY_ROOTS,
                FormatChoice.json,
                output,
                no_llm=True,
                yara_rules_dir=None,
                baseline=None,
                show_suppressed=False,
                verbose=False,
            )

        assert exit_info.value.exit_code == 2
        assert output.exists()

    def test_a_baseline_reaches_every_skill(self, tmp_path: Path, monkeypatch) -> None:
        """Unlike ``--recursive``, which rejects a shared baseline outright."""
        make_skill(tmp_path, "skills/one")
        make_skill(tmp_path, "skills/two")
        baseline = tmp_path / "baseline.yaml"
        baseline.write_text(json.dumps({"version": 1, "rules": []}), encoding="utf-8")
        seen: list[bool] = []

        def fake_invoke(state: dict, config: object = None) -> dict:
            seen.append("baseline" in state)
            return {"risk_score": 0, "report_body": "{}"}

        monkeypatch.setattr("skillspector.cli.graph", SimpleNamespace(invoke=fake_invoke))

        _scan_repository(
            tmp_path,
            DISCOVERY_ROOTS,
            FormatChoice.json,
            tmp_path / "out.json",
            no_llm=True,
            yara_rules_dir=None,
            baseline=baseline,
            show_suppressed=False,
            verbose=False,
        )

        assert seen == [True, True]


class TestNothingHappensWithoutTheFlag:
    """The flag is off by default, and a Scan of a Skill never reaches discovery.

    Issue #39 narrowed this from "an ordinary Scan never reaches discovery". A
    directory that declares no ``SKILL.md`` is about to be reported as one
    anonymous Skill spanning the whole tree, and ``cli`` now runs discovery there
    so its warning can say how many Skills ``--repo-scan`` would find rather than
    naming both flags and leaving the reader to guess.

    The contract that matters is unchanged, and it is narrower than the old test
    asserted: discovery must not influence a Scan's *result*. It reads the tree
    and returns a list -- ``components``, the Inspection Ledger, the Manifest,
    the Findings and the Risk Score are all untouched, which is what the
    ``repository_scan`` module docstring is protecting. Both halves are below.
    """

    def _record_discovery(self, monkeypatch) -> list[Path]:
        called: list[Path] = []
        monkeypatch.setattr(
            "skillspector.cli.discover_skills", lambda *args, **kwargs: called.append(args[0]) or []
        )
        monkeypatch.setattr(
            "skillspector.cli.graph",
            SimpleNamespace(
                invoke=lambda state, config=None: {"risk_score": 0, "report_body": "{}"}
            ),
        )
        return called

    def test_a_scan_of_a_declared_skill_does_not_discover(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The common input, and the half of the old contract that still holds."""
        from typer.testing import CliRunner

        from skillspector.cli import app

        make_skill(tmp_path, ".")
        called = self._record_discovery(monkeypatch)

        CliRunner().invoke(app, ["scan", str(tmp_path), "--no-llm"])

        assert called == []

    def test_a_scan_of_a_directory_declaring_nothing_discovers_only_to_advise(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The exception, and the bound on it: discovery runs, the result does not move."""
        from typer.testing import CliRunner

        from skillspector.cli import app

        make_skill(tmp_path, "skills/one")
        called = self._record_discovery(monkeypatch)

        result = CliRunner().invoke(app, ["scan", str(tmp_path), "--no-llm"])

        assert called == [tmp_path.resolve()]
        # Discovery advised and nothing else: the Scan still ran on the tree it
        # was given, not on the Skill discovery found.
        assert result.exit_code == 0, result.output
