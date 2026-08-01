# Domain Docs

SkillSpector uses a **single-context** layout. The `domain-modeling` skill is the authority on the
format of both files below — do not restate its templates here, they will drift.

## Layout

- **`CONTEXT.md`** (repo root) — the project's glossary. Domain terms only: what each term *is*, and
  which near-synonyms to avoid. **Not** an overview, architecture note, or spec — implementation
  detail does not belong in it.
- **`docs/adr/`** — architecture decision records, `NNNN-slug.md`, sequentially numbered. An ADR can
  be a single paragraph; sections beyond that are optional and used only when they earn their place.

## Consumer rules

The engineering skills (`to-spec`, `to-tickets`) read `CONTEXT.md` for the project's vocabulary
before generating specs or breaking down work. Using a term inconsistently with the glossary is a
defect — fix the glossary or the usage, not both silently.

Write an ADR only when the decision is hard to reverse, would look surprising without the reasoning,
and came from a real trade-off. If any of the three is missing, skip it.

Prose that is neither vocabulary nor a decision belongs in `docs/` — architecture in
`docs/DEVELOPMENT.md`, project overview in `README.md`.

## Status

Both `CONTEXT.md` and `docs/adr/` exist. Past decisions still living only in design docs have not
all been backfilled as ADRs; write one when a decision gets re-litigated often enough to need a
stable home.
