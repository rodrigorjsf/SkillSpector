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

"""Throwaway: which candidate Deep Agents application should be committed as a fixture.

Issue #72 requires the fixtures of ``DA-SKILL-WRITABLE`` to be **chosen** rather
than authored -- the scenario matrix is driven through the real Scan first, what
fires per case is read, and only then is a fixture picked. This script is that
drive. It is captured on ``proto/da-skill-writable`` and is never merged.

Run from the repository root::

    .venv/bin/python prototype/da_skill_writable_matrix.py

Each candidate is materialized as a complete application tree in a temporary
directory -- ``pyproject.toml``, a package, a Skill directory with its
``SKILL.md`` -- and scanned through ``tests.behavior.projection.scan_state``,
which is the same entry point the Behavior Snapshot gate uses. So what is printed
is what a committed snapshot would carry, not what a unit test asserts.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.behavior.projection import scan_state  # noqa: E402

PYPROJECT = """[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "deepagents>=0.6.8",
]

[tool.setuptools.packages.find]
where = ["src"]
"""

SKILL_MD = """---
name: {name}
description: {description}
---

# {title}

1. Read the record the request names.
2. Match it against the table for its tier.
3. Write the decision back onto the record.
"""

# The scenario matrix. Each entry is the body of one `agent.py`, written the way
# the captured upstream page writes the shape it stands for.
CANDIDATES: Mapping[str, str] = {
    "tutorial-default": '''"""Builds the agent the way the tutorial builds one."""

from deepagents import create_deep_agent

MODEL = "anthropic:claude-sonnet-4-6"


def build_agent():
    return create_deep_agent(
        model=MODEL,
        skills=["/skills/shared/", "/skills/personal/"],
    )
''',
    "shared-denied-personal-open": '''"""Shared sources are closed; the personal one is left open."""

from deepagents import FilesystemPermission, create_deep_agent

MODEL = "anthropic:claude-sonnet-4-6"


def build_agent():
    return create_deep_agent(
        model=MODEL,
        skills=["/skills/shared/", "/skills/personal/"],
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/shared/**"],
                mode="deny",
            ),
        ],
    )
''',
    "every-source-denied": '''"""Every source the agent is given is closed to it."""

from deepagents import FilesystemPermission, create_deep_agent

MODEL = "anthropic:claude-sonnet-4-6"


def build_agent():
    return create_deep_agent(
        model=MODEL,
        skills=["/skills/shared/", "/skills/personal/"],
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/**"],
                mode="deny",
            ),
        ],
    )
''',
    "approval-by-mode": '''"""Every write to a source is put in front of a person."""

from deepagents import FilesystemPermission, create_deep_agent

MODEL = "anthropic:claude-sonnet-4-6"


def build_agent():
    return create_deep_agent(
        model=MODEL,
        skills=["/skills/shared/", "/skills/personal/"],
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/**"],
                mode="interrupt",
            ),
        ],
    )
''',
    "approval-by-gate": '''"""Every filesystem write is put in front of a person."""

from deepagents import create_deep_agent

MODEL = "anthropic:claude-sonnet-4-6"


def build_agent():
    return create_deep_agent(
        model=MODEL,
        skills=["/skills/shared/", "/skills/personal/"],
        interrupt_on={"write_file": True, "edit_file": True},
    )
''',
    "specific-before-broad": '''"""The ordering upstream tells people to write."""

from deepagents import FilesystemPermission, create_deep_agent

MODEL = "anthropic:claude-sonnet-4-6"


def build_agent():
    return create_deep_agent(
        model=MODEL,
        skills=["/skills/shared/", "/skills/personal/"],
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/personal/**"],
                mode="interrupt",
            ),
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/**"],
                mode="deny",
            ),
        ],
    )
''',
    "on-disk-and-denied": '''"""The sources are files on disk, and closed to the agent."""

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

MODEL = "anthropic:claude-sonnet-4-6"
BACKEND = FilesystemBackend(root_dir="./app")


def build_agent():
    return create_deep_agent(
        model=MODEL,
        backend=BACKEND,
        skills=["/skills/shared/"],
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/**"],
                mode="deny",
            ),
        ],
    )
''',
}


def materialize(root: Path, name: str, agent: str) -> Path:
    """Write one candidate application tree under *root* and return its path."""
    tree = root / name.replace("-", "_")
    package = tree / "src" / "support_agent"
    package.mkdir(parents=True)
    (tree / "pyproject.toml").write_text(PYPROJECT.format(name=name), encoding="utf-8")
    (package / "__init__.py").write_text('"""An agent built for one caller."""\n', encoding="utf-8")
    (package / "agent.py").write_text(agent, encoding="utf-8")
    skill = tree / "skills" / "ticket-triage"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        SKILL_MD.format(
            name="ticket-triage",
            description="Walks an agent through triaging an incoming customer ticket.",
            title="Ticket triage",
        ),
        encoding="utf-8",
    )
    return tree


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="da-writable-matrix-"))
    try:
        for name, agent in CANDIDATES.items():
            state = scan_state(materialize(root, name, agent))
            findings = [
                finding
                for finding in state.get("findings", [])
                if str(finding.rule_id).startswith("DA-")
            ]
            print(f"\n=== {name}: {len(findings)} Deep Agents Finding(s)")
            print(f"    risk score {state.get('risk_score')}")
            for finding in findings:
                print(
                    f"    {finding.rule_id:<18} {finding.severity:<7} "
                    f"conf={finding.confidence} {finding.file}:{finding.start_line}"
                )
                print(f"        {finding.message}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
