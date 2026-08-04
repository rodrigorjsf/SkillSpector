# Vocabulary sweep — re-measures what a Framework inventory claims, by reading published releases.

The procedure this tool belongs to is `docs/VOCABULARY_REMEASUREMENT.md`. Read it first: it owns
what counts as in scope, how to read the output, what to record, and the trigger that obliges a
re-run. This file is only how to work on the tool.

## Tooling

- **Excluded from `make test`** — the root `pyproject.toml` sets `testpaths = ["tests"]`, so nothing
  here runs in the default suite. That is deliberate: a sweep is network-dependent and is a
  maintainer's act, not a per-commit check.
- Run a sweep with `python -m contrib.vocabulary_sweep deepagents` or `... langchain4j`.
- Tests are a standalone script, not pytest: `python contrib/vocabulary_sweep/tests/test_readers.py`.
  They are offline — the discrimination they prove lives in the AST and class-file readers, not in
  the download.
- **Standard library only.** No third-party HTTP or parsing dependency, so the tool works from a
  bare checkout.

## Conventions

- **Never write an inventoried spelling here.** Both vocabularies are guarded by a test that fails
  the build on a spelling written outside them, and that guard sweeps `src/skillspector` — it cannot
  see this package. A hardcoded spelling would be a second inventory drifting away from the one it
  measures. Import the constant, or key a role map by the *constant name*.
- **Fail closed on an unmapped constant.** `roles.assign` raises when an inventoried constant has no
  role and when a role names a constant that no longer exists. A new spelling nobody measured is
  exactly what a re-measurement is supposed to notice.
- **Measure in role, never by containment.** `skills`, `mode`, `write`, `name`, `content` and `tools`
  are ordinary words; a substring search reports them present in every release ever published and
  measures nothing. Prove any new reader discriminates before trusting a green sweep — that is what
  `tests/test_readers.py` exists for.
- **Parse, do not execute.** Python releases are read with `ast`, Java releases as class files.
  Importing a published release would run arbitrary code and need its dependency tree resolved at
  the version it expected, across the whole history.
- **Exit code 1 is a blocking result** — a spelling removed after appearing, or one never published
  in role. Keep it that way: a trigger that says "run this and read the output" is only as good as
  the reader.
