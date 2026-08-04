"""Builds the support agent from a shared source and a per-user source.

The shared source is under a rule; the per-user one is left as the framework
leaves it, which is the arrangement the upstream documentation recommends for
letting an agent refine its own notes without touching the shared library.
"""

from deepagents import FilesystemPermission, create_deep_agent

MODEL = "anthropic:claude-sonnet-4-6"

SKILL_SOURCES = ["/skills/shared/", "/skills/personal/"]


def build_agent():
    """Return the support agent, carrying both Skill sources."""
    return create_deep_agent(
        model=MODEL,
        skills=SKILL_SOURCES,
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/shared/**"],
                mode="deny",
            ),
        ],
    )
