# Triage Labels

SkillSpector uses the five canonical triage roles. Each issue receives exactly one label from this set:

| Label | Role | Meaning |
|-------|------|---------|
| `needs-triage` | Triage | Issue was just created; untriaged |
| `needs-info` | Triage | Issue needs clarification from the author or external source |
| `ready-for-agent` | Agent | Ready for Claude to pick up and work on |
| `ready-for-human` | Human | Ready for a human to review, merge, deploy, or make a judgment call |
| `wontfix` | Disposition | Issue is out of scope or will not be fixed |

## Consumer rules

The `triage` skill reads and writes these labels. Do not invent new labels or deviate from this set — the triage workflow depends on a stable vocabulary.

When an issue transitions state (e.g. from `needs-triage` to `ready-for-agent`), remove the old label and add the new one. An issue should have exactly one label at all times.
