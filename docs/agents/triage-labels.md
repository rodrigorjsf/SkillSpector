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

## `blocked` is a modifier, not a state

One further label sits alongside both of the above:

| Label | Meaning |
|-------|---------|
| `blocked` | The issue cannot be worked until something else lands, and that something is named in its body |

It is deliberately **not** a sixth state. A state answers "where is this in triage"; `blocked`
answers "may work start", and the two are independent — an issue can be fully specified and still
unworkable. Keeping it orthogonal means the one-state-at-a-time rule is untouched, and the `triage`
skill's five-state machine keeps working without knowing this label exists. Made a state instead, it
would collide with `ready-for-agent` and lose the distinction between *not yet specified* and
*specified but waiting*.

So a blocked-but-specified issue reads `bug` + `ready-for-agent` + `blocked`. `blocked` overrides
`ready-for-agent` in practice: an agent picking work up skips a blocked issue regardless of its
state.

`blocked` is removed by whoever closes the blocker — it is not a state transition, so removing it
touches neither the state nor the category label. An issue carrying `blocked` whose body names no
blocker is a defect in the labelling, not a blocked issue.

## Consumer rules

The `triage` skill reads and writes the state and category labels. Do not invent new labels or deviate from this set — the triage workflow depends on a stable vocabulary. `blocked` is outside that vocabulary by design: the skill neither sets nor clears it, so a human or an agent working from an issue applies and removes it directly.

When an issue transitions state (e.g. from `needs-triage` to `ready-for-agent`), remove the old state label and add the new one. An issue should have exactly one **state** label at all times.

**A state transition does not touch the category label.** Moving an issue from `needs-triage` to
`ready-for-agent` leaves its `bug` or `enhancement` untouched — the category says what the work is
and does not change as the work moves through triage. Stripping it is a mistake, not a cleanup.
