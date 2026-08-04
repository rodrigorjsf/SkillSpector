"""Builds the support agent from a shared library and a per-user directory.

Both sources sit under the backend root below, and both are covered by the rule,
so the library the agent reads from stays the one the support team publishes.
"""

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

MODEL = "anthropic:claude-sonnet-4-6"

BACKEND = FilesystemBackend(root_dir="./library")

SKILL_SOURCES = ["/skills/shared/", "/skills/personal/"]


def build_agent():
    """Return the support agent, carrying both Skill sources."""
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
