---
paths:
  - "src/skillspector/nodes/build_context.py"
  - "src/skillspector/nodes/analyzers/mcp_least_privilege.py"
---

# `allowed-tools` separator — known deviation, do not fix in passing

- Both files split the Agent Skills `allowed-tools` frontmatter field on **commas** (`build_context.py:304`, `mcp_least_privilege.py:143`). The specification defines it as **space**-separated. This is a known, deliberate deviation — not an oversight.
- **Do not change it as part of unrelated work.** Correcting the separator changes findings on inputs scanned today, which violates the repo's behavior-preservation constraint. It needs its own decision, changelog entry, and version bump.
- Neither call site has direct test coverage, so a change here fails silently in the suite. Downstream consumers are `_map_allowed_tools_to_categories` and the `has_declaration` branch (`mcp_least_privilege.py:190`, `:334`), which drive LP1, LP3, and LP4.
- Reopen conditions, blast radius, and the migration checklist: `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` § Known deviation.
- A second, independent defect lives here: scoped syntax (`Bash(git:*)`) does not match `_TOOL_TO_CAPABILITY` even with correct whitespace splitting. Fixing one does not fix the other.
