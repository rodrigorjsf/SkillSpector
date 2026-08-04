"""Builds the support agent and the two subagents it delegates to.

The main agent's Skill source is covered by the rule below, so nothing here can
rewrite the procedure it runs on. The triager is declared with the same Skill
source the main agent reads; the summarizer is declared with none.
"""

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

MODEL = "anthropic:claude-sonnet-4-6"

BACKEND = FilesystemBackend(root_dir="./library")

SKILL_SOURCES = ["/skills/shared/"]


def build_agent():
    """Return the support agent, carrying both of its subagents."""
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
        subagents=[
            {
                "name": "triager",
                "description": "Routes an incoming customer ticket to a queue.",
                "prompt": "Route the ticket the conversation refers to.",
                "skills": SKILL_SOURCES,
            },
            {
                "name": "summarizer",
                "description": "Writes the closing summary of a resolved ticket.",
                "prompt": "Summarize what was done on the ticket and why.",
            },
        ],
    )
