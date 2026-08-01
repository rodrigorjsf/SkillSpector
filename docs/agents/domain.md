# Domain Docs

SkillSpector uses a **single-context** layout for domain documentation and architectural decisions.

## Layout

- **`CONTEXT.md`** (repo root) — overview, architecture, tech stack, critical constraints, and pointers to deeper docs
- **`docs/adr/`** (repo root) — architecture decision records, one file per decision

## Consumer rules

The engineering skills (`to-spec`, `to-tickets`) read from `CONTEXT.md` to understand the project's scope, goals, and constraints before generating specs or breaking down work.

When a significant architectural decision is made, record it in `docs/adr/NNNN-decision-title.md` (use a 4-digit zero-padded number; e.g. `0001-langchain4j-support.md`). Include:
- **Status** — Proposed, Accepted, Deprecated, Superseded
- **Context** — why this decision was needed
- **Decision** — what was chosen and why
- **Consequences** — what changes as a result

The ADR directory acts as a searchable history of major choices. Skills may reference ADRs when generating work; humans use them to understand the reasoning behind the codebase.

## Next steps

- Create `CONTEXT.md` at the repo root with a high-level overview of SkillSpector
- Create `docs/adr/` directory (if it doesn't already exist)
- Document existing decisions as ADRs
