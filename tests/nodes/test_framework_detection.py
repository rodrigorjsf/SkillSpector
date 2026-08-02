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

"""Which Framework a scanned tree is written against.

Issue #21, phase 1. Detection is a pure function over ``components`` and
``file_cache``, so the whole signal matrix is driven in memory -- no directory,
no graph. Only the two seam tests at the bottom touch the disk: they prove
``build_context`` sets the key to what the pure function returned.

Every existing fixture is asserted to detect ``agent_skills``, which is the
evidence behind the phase's behavior-preservation claim. The fixtures listed in
``DETECTION_FIXTURES`` are the deliberate exception.
"""

from __future__ import annotations

import pytest

from skillspector.framework import Framework, detect_framework
from skillspector.nodes.build_context import build_context
from skillspector.state import SkillspectorState
from tests.behavior import projection as proj

# The behavior corpus is the declared list of leaf scan targets, and
# ``test_the_corpus_is_exactly_the_leaf_fixture_directories`` already holds it
# equal to what is on disk. Deriving from it rather than re-walking the tree
# keeps one leaf rule in the suite: a second one could drift silently, dropping
# a fixture from the assertion below without turning anything red.
FIXTURES_DIR = proj.FIXTURES_DIR

# Every fixture whose Framework is not the default, and what it must detect as.
# Two carry a bare detection signal and nothing else (issue #21); the third is a
# LangChain4j application the ``framework_langchain4j`` Analyzer reads. Every
# fixture outside this mapping predates Framework detection and must keep
# detecting ``agent_skills`` -- a fixture arriving here by accident rather than
# by this edit is the drift the assertion below exists to catch.
DETECTION_FIXTURES: dict[str, Framework] = {
    "deepagents_detection": Framework.DEEPAGENTS,
    "langchain4j_detection": Framework.LANGCHAIN4J,
    "langchain4j_shell_skill": Framework.LANGCHAIN4J,
}

# One row per signal, positive and negative: the in-memory ``file_cache`` and
# the Framework a Scan of it must detect. ``components`` is the cache's keys,
# which is what ``build_context`` produces for every readable file.
SIGNALS: tuple[tuple[str, dict[str, str], Framework], ...] = (
    # -- LangChain4j, positive --------------------------------------------- #
    (
        "pom_names_the_coordinate",
        {"pom.xml": "<dependency><groupId>dev.langchain4j</groupId></dependency>"},
        Framework.LANGCHAIN4J,
    ),
    (
        "nested_module_pom",
        {"agent/pom.xml": "<groupId>dev.langchain4j</groupId>"},
        Framework.LANGCHAIN4J,
    ),
    (
        "gradle_groovy_names_the_coordinate",
        {"build.gradle": "implementation 'dev.langchain4j:langchain4j:0.36.0'"},
        Framework.LANGCHAIN4J,
    ),
    (
        "gradle_kotlin_names_the_coordinate",
        {"build.gradle.kts": 'implementation("dev.langchain4j:langchain4j:0.36.0")'},
        Framework.LANGCHAIN4J,
    ),
    (
        "java_imports_the_package",
        {"Agent.java": "package a;\n\nimport dev.langchain4j.service.AiServices;\n"},
        Framework.LANGCHAIN4J,
    ),
    (
        "java_static_import",
        {"Agent.java": "import static dev.langchain4j.internal.Utils.randomUUID;\n"},
        Framework.LANGCHAIN4J,
    ),
    (
        "kotlin_imports_the_package",
        {"Agent.kt": "import dev.langchain4j.service.AiServices\n"},
        Framework.LANGCHAIN4J,
    ),
    (
        "maven_skill_resource_layout",
        {"src/main/resources/skills/review/SKILL.md": "# review\n"},
        Framework.LANGCHAIN4J,
    ),
    # -- LangChain4j, negative --------------------------------------------- #
    (
        "pom_without_the_coordinate",
        {"pom.xml": "<dependency><groupId>org.junit</groupId></dependency>"},
        Framework.AGENT_SKILLS,
    ),
    (
        "gradle_without_the_coordinate",
        {"build.gradle.kts": 'implementation("org.junit.jupiter:junit-jupiter:5.10.0")'},
        Framework.AGENT_SKILLS,
    ),
    (
        "java_without_the_import",
        {"Agent.java": "package a;\n\nimport java.util.List;\n"},
        Framework.AGENT_SKILLS,
    ),
    (
        "kotlin_without_the_import",
        {"Agent.kt": "import kotlin.collections.List\n"},
        Framework.AGENT_SKILLS,
    ),
    (
        "coordinate_only_in_prose",
        {"README.md": "This Skill is meant for dev.langchain4j users.\n"},
        Framework.AGENT_SKILLS,
    ),
    (
        "java_names_the_package_mid_line",
        {"Agent.java": "int n = 1; // see import dev.langchain4j.service.AiServices\n"},
        Framework.AGENT_SKILLS,
    ),
    (
        "coordinate_in_an_xml_that_is_not_a_build_file",
        {"logback.xml": "<logger name='dev.langchain4j' level='DEBUG'/>"},
        Framework.AGENT_SKILLS,
    ),
    (
        "skills_directory_outside_the_maven_layout",
        {"skills/review/SKILL.md": "# review\n"},
        Framework.AGENT_SKILLS,
    ),
    # -- Deep Agents, positive --------------------------------------------- #
    (
        "pyproject_names_the_distribution",
        {"pyproject.toml": 'dependencies = ["deepagents>=0.1"]\n'},
        Framework.DEEPAGENTS,
    ),
    (
        "requirements_names_the_distribution",
        {"requirements.txt": "deepagents==0.1.0\n"},
        Framework.DEEPAGENTS,
    ),
    (
        "requirements_variant_names_the_distribution",
        {"requirements-dev.txt": "deepagents\n"},
        Framework.DEEPAGENTS,
    ),
    (
        "python_imports_the_package",
        {"agent.py": "import deepagents\n"},
        Framework.DEEPAGENTS,
    ),
    (
        "python_imports_from_the_package",
        {"agent.py": "from deepagents import create_deep_agent\n"},
        Framework.DEEPAGENTS,
    ),
    (
        "python_calls_the_constructor",
        {"agent.py": "agent = create_deep_agent(tools=[], instructions='')\n"},
        Framework.DEEPAGENTS,
    ),
    # -- Deep Agents, negative --------------------------------------------- #
    (
        "pyproject_without_the_distribution",
        {"pyproject.toml": 'dependencies = ["pydantic"]\n'},
        Framework.AGENT_SKILLS,
    ),
    (
        "python_without_the_import",
        {"agent.py": "import os\n"},
        Framework.AGENT_SKILLS,
    ),
    (
        "distribution_only_in_prose",
        {"README.md": "Works well with deepagents and create_deep_agent().\n"},
        Framework.AGENT_SKILLS,
    ),
    (
        "substring_of_a_longer_distribution",
        {"requirements.txt": "deepagents-contrib==2.0\n"},
        Framework.AGENT_SKILLS,
    ),
    (
        "package_named_inside_a_dotted_path",
        {"agent.py": "import vendor.deepagents\n"},
        Framework.AGENT_SKILLS,
    ),
    (
        "distribution_in_a_txt_that_is_not_a_requirement_file",
        {"notes.txt": "deepagents\n"},
        Framework.AGENT_SKILLS,
    ),
    # -- Neither ------------------------------------------------------------ #
    ("nothing_at_all", {}, Framework.AGENT_SKILLS),
    (
        "an_ordinary_agent_skill",
        {"SKILL.md": "---\nname: review\ndescription: d\n---\n"},
        Framework.AGENT_SKILLS,
    ),
)

EVERY_SIGNAL = pytest.mark.parametrize(
    ("file_cache", "expected"),
    [(cache, expected) for _name, cache, expected in SIGNALS],
    ids=[name for name, _cache, _expected in SIGNALS],
)


@EVERY_SIGNAL
def test_every_signal_detects_its_framework(
    file_cache: dict[str, str], expected: Framework
) -> None:
    """One row per signal: each positive fires, each negative does not."""
    assert detect_framework(sorted(file_cache), file_cache) == expected


def test_both_frameworks_signalled_is_doubt_and_resolves_to_agent_skills() -> None:
    """A polyglot tree detects neither Framework -- §3.2's conservative rule.

    The consequence is stated in ``skillspector.framework``: such a tree loses
    Framework analysis, and loses it silently. Nothing reads the key yet.
    """
    file_cache = {
        "pom.xml": "<groupId>dev.langchain4j</groupId>",
        "pyproject.toml": 'dependencies = ["deepagents"]\n',
    }

    assert detect_framework(sorted(file_cache), file_cache) == Framework.AGENT_SKILLS


def test_the_ambiguous_case_is_not_vacuous() -> None:
    """Each half of the ambiguous tree detects its own Framework alone.

    Without this control the test above would pass on a pure function that
    simply never fires.
    """
    pom = {"pom.xml": "<groupId>dev.langchain4j</groupId>"}
    pyproject = {"pyproject.toml": 'dependencies = ["deepagents"]\n'}

    assert detect_framework(sorted(pom), pom) == Framework.LANGCHAIN4J
    assert detect_framework(sorted(pyproject), pyproject) == Framework.DEEPAGENTS


def test_a_component_missing_from_the_cache_carries_no_signal() -> None:
    """An unreadable signal file cannot detect: there is no content to read.

    ``build_context`` lists a file in ``components`` and omits it from
    ``file_cache`` when the read failed, so the two are not interchangeable.
    """
    assert detect_framework(["pom.xml", "pyproject.toml"], {}) == Framework.AGENT_SKILLS


def test_the_enum_serializes_to_the_specified_wire_values() -> None:
    """§3.1's values are the contract; the enum is only how they are spelled."""
    assert Framework.AGENT_SKILLS == "agent_skills"
    assert Framework.LANGCHAIN4J == "langchain4j"
    assert Framework.DEEPAGENTS == "deepagents"


# --------------------------------------------------------------------------- #
# The seam: build_context sets what the pure function returned
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    [name for name in proj.CORPUS_NAMES if name not in DETECTION_FIXTURES],
    ids=lambda name: name,
)
def test_every_pre_existing_fixture_detects_agent_skills(name: str) -> None:
    """The evidence behind the phase's behavior-preservation claim.

    Detection returns the default on every input scanned today, so ``framework``
    is omitted from every pre-existing snapshot and none of them changes.
    """
    state: SkillspectorState = {"skill_path": str(FIXTURES_DIR / name)}

    assert build_context(state)["framework"] == Framework.AGENT_SKILLS


@pytest.mark.parametrize(("name", "expected"), sorted(DETECTION_FIXTURES.items()))
def test_the_detection_fixtures_detect_through_build_context(
    name: str, expected: Framework
) -> None:
    """The node sets the key, and it sets it to what the pure function says."""
    state: SkillspectorState = {"skill_path": str(FIXTURES_DIR / name)}

    result = build_context(state)

    assert result["framework"] == expected
    assert result["framework"] == detect_framework(
        result["components"],  # type: ignore[arg-type]
        result["file_cache"],  # type: ignore[arg-type]
    )
