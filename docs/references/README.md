# Vendored framework references

Captured upstream documentation for the agent frameworks SkillSpector analyzes.
These files are **reference material, not SkillSpector documentation**: they exist so
analyzer authors can cite a normative rule when writing a detection, without
re-fetching a live site during development or review.

| File | Upstream source | Captured |
|------|-----------------|----------|
| [agent-skills-specification.md](agent-skills-specification.md) | <https://agentskills.io/specification> | 2026-08-01 |
| [langchain4j-skills.md](langchain4j-skills.md) | <https://docs.langchain4j.dev/tutorials/skills/> | 2026-08-01 |
| [langchain-deepagents-skills.md](langchain-deepagents-skills.md) | <https://docs.langchain.com/oss/python/deepagents/skills> | 2026-08-01 |

## Why these three

The Agent Skills specification is the **shared normative anchor**. Both LangChain4j
Skills and LangChain Deep Agents state explicitly that their skills follow it, and both
consume the same `SKILL.md` layout SkillSpector already scans. The framework-specific
files cover only what the specification does not: the host-side wiring (Java classes,
Python `create_deep_agent` arguments) where the security-relevant configuration lives.

## Conventions

- Each file records its source URL and capture date in a front-matter block.
- Content is a faithful capture of the upstream normative material, reorganized for
  reference use. Code samples are reproduced as published.
- A **"Relevance to SkillSpector"** section at the end of each file maps upstream rules
  to concrete detection opportunities. That section is SkillSpector's own analysis, not
  upstream content.
- An optional **`Verified:`** line in the front-matter block records a date on which the
  capture was re-checked against upstream and found still accurate. It is deliberately
  distinct from `Captured:`, which changes only on an actual re-capture — a `Verified:`
  date means the content was confirmed unchanged, not refreshed. Bumping `Captured:`
  without re-capturing would misreport when this text was taken.
- **A `Verified:` line must state what was checked.** Re-verification is nearly always
  partial — a heading comparison, one field, a single disputed sentence — and a bare
  "verified" reads as a full re-audit nobody performed. Name the scope and the limit, so a
  later reader can tell what still rests on the original capture. These files are cited as
  primary sources when analyzers are written; an overstated line here is exactly the drift
  this directory exists to prevent.

## Upstream cross-citations are claims, not facts

These files quote Frameworks that cite *each other* — most often the Agent Skills
specification, which both LangChain4j and Deep Agents name as the convention they follow.
Such a citation is upstream's assertion and can be wrong. Before relying on one, check it
against the cited capture. When it does not hold, annotate the citing file rather than
silently rewriting upstream's words, so the capture stays faithful and the correction stays
visible.

One such citation has been checked and does not hold; the finding is recorded once, in
[langchain4j-skills.md § The two "integration approaches" are not specification vocabulary](langchain4j-skills.md#the-two-integration-approaches-are-not-specification-vocabulary).

## Refreshing

Upstream docs move. Re-capture with:

```bash
# Mintlify-backed sites (agentskills.io, docs.langchain.com) serve raw markdown
curl -sSL https://agentskills.io/specification.md
curl -sSL https://docs.langchain.com/oss/python/deepagents/skills.md

# Docusaurus (docs.langchain4j.dev) serves HTML only
curl -sSL https://docs.langchain4j.dev/tutorials/skills/ | lynx -dump -nolist -stdin
```

Update the capture date in the file's front-matter block and in the table above. Drop any
stale `Verified:` line at the same time — it describes the text being replaced.
LangChain4j's Skills API is marked experimental upstream — expect it to drift.

**A re-capture overwrites annotations. Re-apply them.** These commands emit upstream
content only, so they discard the "Relevance to SkillSpector" section and every editorial
marker attached to the body — today that means the `[^approach]` footnote markers in
`langchain4j-skills.md` and their definition. Diff the fresh capture against the committed
file rather than replacing it wholesale, and carry the annotations across. An annotation
silently lost in a refresh restores the very citation it was written to correct.
