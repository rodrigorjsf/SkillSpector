"""Builds the support agent for one caller.

The Skill sources are looked up from the caller's role, so which directories the
agent ends up with is decided while the request is being served rather than in
this file.
"""

from deepagents import create_deep_agent

MODEL = "anthropic:claude-sonnet-4-6"

SKILLS_BY_ROLE = {
    "support": ["skills/ticket-triage/"],
    "engineering": ["skills/ticket-triage/", "skills/deployment/"],
}


def build_agent(user_role: str):
    """Return an agent carrying the Skill sources that go with *user_role*."""
    return create_deep_agent(
        model=MODEL,
        skills=SKILLS_BY_ROLE.get(user_role, []),
    )
