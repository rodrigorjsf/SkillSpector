"""Builds the release-library agent over a curated Skill source.

Every source the agent is given is covered by a rule, so the library it reads
from stays the one the release team publishes.
"""

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

MODEL = "anthropic:claude-sonnet-4-6"

BACKEND = FilesystemBackend(root_dir="./library")

SKILL_SOURCES = ["/skills/release/", "/skills/shared/"]


def build_agent():
    """Return the release-library agent."""
    return create_deep_agent(
        model=MODEL,
        backend=BACKEND,
        skills=SKILL_SOURCES,
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/**"],
                mode="deny",
            ),
        ],
    )
