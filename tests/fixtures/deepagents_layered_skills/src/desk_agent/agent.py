"""Builds the desk agent from a shared library and a per-user directory.

The per-user directory is written after the shared one, which is the order the
upstream documentation recommends for letting a desk add Skills of its own on
top of the library the release team publishes. Both sources sit under the backend
root below, and both are covered by the rule.
"""

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

MODEL = "anthropic:claude-sonnet-4-6"

BACKEND = FilesystemBackend(root_dir="./library")

SKILL_SOURCES = ["/skills/shared/", "/skills/personal/"]


def build_agent():
    """Return the desk agent, carrying both Skill sources."""
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
