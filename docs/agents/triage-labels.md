# Triage Labels

SkillSpector uses the five canonical triage roles. They are **state** labels, and a triaged issue
carries exactly one of them:

| Label | Role | Meaning |
|-------|------|---------|
| `needs-triage` | Triage | Issue was just created; untriaged |
| `needs-info` | Triage | Issue needs clarification from the author or external source |
| `ready-for-agent` | Agent | Ready for Claude to pick up and work on |
| `ready-for-human` | Human | Ready for a human to review, merge, deploy, or make a judgment call |
| `wontfix` | Disposition | Issue is out of scope or will not be fixed |

## State labels coexist with a category label

A state label is not the only label an issue carries. Alongside it sits one **category** label
saying what kind of work the issue is:

| Label | Meaning |
|-------|---------|
| `bug` | Something is broken |
| `enhancement` | New feature or improvement |
| `documentation` | The change is to prose, not to behavior |

`bug` and `enhancement` are the two canonical categories. `documentation` is a third that this
repository uses in practice for issues whose whole deliverable is prose — it is a category, not a
state, and it is chosen instead of `bug`/`enhancement`, never alongside one.

So a fully triaged issue reads `enhancement` + `ready-for-agent`, or `bug` + `ready-for-agent`, or
`documentation` + `ready-for-human`. An untriaged issue may carry `needs-triage` alone, with its
category assigned during triage.

## Consumer rules

The `triage` skill reads and writes these labels. Do not invent new labels or deviate from this set — the triage workflow depends on a stable vocabulary.

When an issue transitions state (e.g. from `needs-triage` to `ready-for-agent`), remove the old state label and add the new one. An issue should have exactly one **state** label at all times.

**A state transition does not touch the category label.** Moving an issue from `needs-triage` to
`ready-for-agent` leaves its `bug` or `enhancement` untouched — the category says what the work is
and does not change as the work moves through triage. Stripping it is a mistake, not a cleanup.
