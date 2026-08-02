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

"""Tests for the gated ``framework_langchain4j`` Analyzer and its ``L4J-SHELL`` Rule.

Every assertion here reads the Findings the node returns. A green suite is not
evidence the Analyzer ran: ``guard_analyzer_node`` turns any exception into an
empty Finding list plus a ``"failed"`` status, so a test that only checked the
node returned successfully would pass on a completely broken Analyzer.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from skillspector.framework import Framework
from skillspector.inspection_ledger import LedgerOutcome, guard_analyzer_node
from skillspector.nodes.analyzers import framework_langchain4j as analyzer

SHELL_WIRING_JAVA = """package com.example;

import dev.langchain4j.skill.FileSystemSkillLoader;
import dev.langchain4j.skill.shell.ShellSkills;

public class OpsAgent {
    void wire() {
        ShellSkills skills = ShellSkills.from(FileSystemSkillLoader.loadSkills(Path.of("skills/")));
    }
}
"""
# The wiring sits on line 8; the import that makes it available on line 4.
SHELL_WIRING_LINE = 8

TOOL_MODE_JAVA = """package com.example;

import dev.langchain4j.skill.Skill;
import dev.langchain4j.skill.FileSystemSkillLoader;

public class OrderAgent {
    void wire() {
        Skill skill = Skill.builder().name("process-order").build();
    }
}
"""

SHELL_POM = """<project>
  <dependencies>
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j-experimental-skills-shell</artifactId>
    </dependency>
  </dependencies>
</project>
"""
# The artifactId naming the shell module sits on line 5.
SHELL_POM_LINE = 5

PLAIN_POM = """<project>
  <dependencies>
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j</artifactId>
    </dependency>
  </dependencies>
</project>
"""

COMMENTED_POM = """<project>
  <!--
    We removed langchain4j-experimental-skills-shell when we left the prototype
    behind; do not put it back.
  -->
  <dependencies>
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j</artifactId>
    </dependency>
  </dependencies>
</project>
"""

SHELL_COORDINATE = "dev.langchain4j:langchain4j-experimental-skills-shell:1.18.1-beta28"


def make_state(
    file_cache: dict[str, str],
    framework: Framework = Framework.LANGCHAIN4J,
) -> dict[str, Any]:
    """Build the slice of Scan state the Analyzer reads."""
    return {
        "framework": framework,
        "file_cache": dict(file_cache),
        "components": sorted(file_cache),
    }


def shell_findings(result: dict[str, Any]) -> list[Any]:
    return [finding for finding in result["findings"] if finding.rule_id == "L4J-SHELL"]


class TestShellSkillsWiring:
    """``L4J-SHELL`` on the Java that grants unsandboxed command execution."""

    def test_wiring_is_reported_at_its_file_and_line(self) -> None:
        result = analyzer.node(make_state({"src/main/java/OpsAgent.java": SHELL_WIRING_JAVA}))

        findings = shell_findings(result)
        assert len(findings) == 1, [finding.rule_id for finding in result["findings"]]
        finding = findings[0]
        assert finding.severity == "HIGH"
        assert finding.file == "src/main/java/OpsAgent.java"
        assert finding.start_line == SHELL_WIRING_LINE
        assert "ASI02" in finding.tags

    def test_an_import_with_no_wiring_is_reported_at_the_import(self) -> None:
        source = "package com.example;\n\nimport dev.langchain4j.skill.shell.ShellSkills;\n"

        findings = shell_findings(analyzer.node(make_state({"A.java": source})))

        assert len(findings) == 1
        assert findings[0].start_line == 3

    def test_tool_mode_java_yields_no_shell_finding(self) -> None:
        """The negative control: LangChain4j Java that never reaches shell mode."""
        result = analyzer.node(make_state({"src/main/java/OrderAgent.java": TOOL_MODE_JAVA}))

        assert shell_findings(result) == []

    def test_a_partially_invalid_file_still_yields_the_finding(self) -> None:
        """Error-tolerant parsing is load-bearing, not incidental."""
        broken = SHELL_WIRING_JAVA + "\nclass Broken { void oops( { } }\n"

        findings = shell_findings(analyzer.node(make_state({"A.java": broken})))

        assert len(findings) == 1
        assert findings[0].start_line == SHELL_WIRING_LINE


class TestShellDependencyDeclaration:
    """``L4J-SHELL`` on the build file that puts the shell module on the classpath."""

    def test_the_declaration_is_reported_at_its_line(self) -> None:
        result = analyzer.node(make_state({"pom.xml": SHELL_POM, "A.java": TOOL_MODE_JAVA}))

        findings = shell_findings(result)
        assert len(findings) == 1
        assert findings[0].file == "pom.xml"
        assert findings[0].start_line == SHELL_POM_LINE
        assert findings[0].severity == "HIGH"

    def test_a_build_file_without_the_shell_module_yields_nothing(self) -> None:
        result = analyzer.node(make_state({"pom.xml": PLAIN_POM, "A.java": TOOL_MODE_JAVA}))

        assert shell_findings(result) == []

    def test_a_commented_out_declaration_is_not_a_declaration(self) -> None:
        """An XML comment naming the artifact is prose, not a dependency.

        A plain substring scan reads the two the same way and reports the
        comment's line, which is both a false positive and a wrong location.
        """
        commented = COMMENTED_POM
        assert analyzer.signals.SHELL_ARTIFACT_ID in commented

        findings = shell_findings(analyzer.node(make_state({"pom.xml": commented})))

        assert findings == []

    def test_a_gradle_line_comment_is_not_a_declaration(self) -> None:
        gradle = f"dependencies {{\n    // implementation '{SHELL_COORDINATE}'\n}}\n"

        assert shell_findings(analyzer.node(make_state({"build.gradle": gradle}))) == []

    def test_a_live_gradle_declaration_below_a_comment_is_found_at_its_own_line(self) -> None:
        gradle = (
            "dependencies {\n"
            f"    // was: implementation '{SHELL_COORDINATE}'\n"
            f"    implementation '{SHELL_COORDINATE}'\n"
            "}\n"
        )

        findings = shell_findings(analyzer.node(make_state({"build.gradle": gradle})))

        assert len(findings) == 1
        assert findings[0].start_line == 3

    def test_the_declaration_fires_with_no_java_in_the_scan(self) -> None:
        """The Rule fires on the dependency *or* the wiring -- neither implies the other."""
        findings = shell_findings(analyzer.node(make_state({"build.gradle": SHELL_POM})))

        assert len(findings) == 1
        assert findings[0].file == "build.gradle"


class TestTheFrameworkGate:
    """The gate is the first statement, and a declining Analyzer emits nothing."""

    @pytest.mark.parametrize("framework", [Framework.AGENT_SKILLS, Framework.DEEPAGENTS])
    def test_another_framework_produces_no_findings_and_no_ledger(
        self, framework: Framework
    ) -> None:
        result = analyzer.node(
            make_state(
                {"src/main/java/OpsAgent.java": SHELL_WIRING_JAVA, "pom.xml": SHELL_POM},
                framework=framework,
            )
        )

        assert result["findings"] == []
        assert result.get("inspection_ledger", []) == []
        assert result.get("analyzer_status_events", []) == []

    def test_a_missing_framework_key_declines(self) -> None:
        result = analyzer.node({"file_cache": {"A.java": SHELL_WIRING_JAVA}})

        assert result["findings"] == []
        assert result.get("analyzer_status_events", []) == []

    def test_a_matching_framework_with_nothing_to_inspect_declines_silently(self) -> None:
        """The shape of ``tests/fixtures/langchain4j_detection``: a pom and no Java.

        ADR 0002 defers the ``not_applicable`` status for this case rather than
        approving silence, so the decline is an interim owed a revisit -- but it
        is what keeps that fixture's committed Behavior Snapshot byte-identical.
        """
        result = analyzer.node(make_state({"pom.xml": PLAIN_POM, "README.md": "# hi\n"}))

        assert result["findings"] == []
        assert result.get("inspection_ledger", []) == []
        assert result.get("analyzer_status_events", []) == []


class TestTheLedgerContract:
    """Every Finding is accounted for by exactly one completed producer row."""

    def test_each_finding_has_exactly_one_completed_producer(self) -> None:
        result = analyzer.node(
            make_state({"pom.xml": SHELL_POM, "src/main/java/OpsAgent.java": SHELL_WIRING_JAVA})
        )

        emitted = [
            finding_id
            for event in result["inspection_ledger"]
            for finding_id in event["emitted_finding_ids"]
        ]
        assert sorted(emitted) == sorted(finding.finding_id for finding in result["findings"])
        assert len(emitted) == len(set(emitted))
        assert all(
            event["outcome"] is LedgerOutcome.COMPLETED for event in result["inspection_ledger"]
        )

    def test_every_inspected_file_gets_a_row_even_with_no_finding(self) -> None:
        result = analyzer.node(
            make_state({"pom.xml": PLAIN_POM, "src/main/java/OpsAgent.java": SHELL_WIRING_JAVA})
        )

        assert {event["path"] for event in result["inspection_ledger"]} == {
            "pom.xml",
            "src/main/java/OpsAgent.java",
        }

    def test_planned_work_matches_the_emitted_rows(self) -> None:
        result = analyzer.node(
            make_state({"pom.xml": SHELL_POM, "src/main/java/OpsAgent.java": SHELL_WIRING_JAVA})
        )

        status = result["analyzer_status_events"][0]
        assert status["status"] == "completed"
        assert [target["work_id"] for target in status["planned_work"]] == [
            event["work_id"] for event in result["inspection_ledger"]
        ]


class TestTheParserIsRequiredLoudly:
    """An absent tree-sitter is a failed Analyzer, never an empty Finding list."""

    @staticmethod
    def _without_tree_sitter(monkeypatch: pytest.MonkeyPatch) -> None:
        """Make the parser genuinely unimportable, as an install missing it would.

        Dropping the submodules from ``sys.modules`` is not enough on its own:
        ``from package import submodule`` reads the attribute the first import
        left on the package object and never reaches the import system, so the
        already-loaded parser would answer anyway.
        """
        import skillspector.langchain4j as package

        for name in ("shell_skills", "java_parser"):
            monkeypatch.delitem(sys.modules, f"skillspector.langchain4j.{name}", raising=False)
            monkeypatch.delattr(package, name, raising=False)
        monkeypatch.setitem(sys.modules, "tree_sitter_java", None)
        monkeypatch.setitem(sys.modules, "tree_sitter", None)

    def test_the_node_raises_rather_than_returning_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._without_tree_sitter(monkeypatch)

        with pytest.raises(ImportError):
            analyzer.node(make_state({"A.java": SHELL_WIRING_JAVA}))

    def test_the_guard_turns_that_into_a_failed_analyzer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._without_tree_sitter(monkeypatch)
        guarded = guard_analyzer_node(analyzer.ANALYZER_ID, analyzer.node)

        result = guarded(make_state({"A.java": SHELL_WIRING_JAVA}))

        assert result["findings"] == []
        assert result["analyzer_status_events"][0]["status"] == "failed"
        assert result["inspection_ledger"][0]["outcome"] is LedgerOutcome.FAILED

    def test_the_gate_still_declines_without_a_parser(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing parser must not turn every existing Scan into a failure."""
        self._without_tree_sitter(monkeypatch)

        result = analyzer.node(
            make_state({"A.java": SHELL_WIRING_JAVA}, framework=Framework.AGENT_SKILLS)
        )

        assert result["findings"] == []


class TestTheFindingReachesTheReport:
    """A Finding the node returns is not yet a Finding the user sees.

    Between the two sit the meta analyzer's filtering, deduplication, baseline
    suppression and SARIF assembly. Asserting on ``node()`` alone cannot see any
    of them, so this drives the whole graph over the committed fixture.
    """

    @staticmethod
    def _scan() -> dict[str, Any]:
        from tests.behavior.projection import FIXTURES_DIR, scan_state

        return dict(scan_state(FIXTURES_DIR / "langchain4j_shell_skill"))

    def test_it_survives_to_the_filtered_findings(self) -> None:
        result = self._scan()

        reported = [
            finding
            for finding in result["filtered_findings"]
            if finding.rule_id == "L4J-SHELL"  # type: ignore[union-attr]
        ]
        assert {finding.severity for finding in reported} == {"HIGH"}  # type: ignore[union-attr]
        assert {finding.file for finding in reported} == {  # type: ignore[union-attr]
            "pom.xml",
            "src/main/java/com/example/OpsAgent.java",
        }

    def test_it_reaches_the_sarif_output(self) -> None:
        run = self._scan()["sarif_report"]["runs"][0]

        assert "L4J-SHELL" in {rule["id"] for rule in run["tool"]["driver"]["rules"]}
        assert "L4J-SHELL" in {result["ruleId"] for result in run["results"]}

    def test_the_scan_stays_accounted_for(self) -> None:
        """A Finding with no producer row is a fatal accounting error, not a Finding."""
        completeness = self._scan()["analysis_completeness"]

        assert completeness["ledger_exceptions"] == []
        assert completeness["execution_successful"] is True


class TestFullFileContent:
    """The Analyzer reads ``file_cache`` directly, so no per-file cap applies."""

    def test_a_file_past_the_static_runner_cap_is_still_analyzed(self) -> None:
        from skillspector.nodes.analyzers.static_runner import MAX_FILE_CHARS

        padding = "// filler comment line\n" * ((MAX_FILE_CHARS // 23) + 1)
        oversized = padding + SHELL_WIRING_JAVA
        assert len(oversized) > MAX_FILE_CHARS

        findings = shell_findings(analyzer.node(make_state({"Big.java": oversized})))

        assert len(findings) == 1
