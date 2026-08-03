---
paths:
  - "src/skillspector/*.py"
  - "src/skillspector/**/*.py"
---

# Analyzer Status

Thirteen modules call `analyzer_status_event`, and only ten of them are Analyzer nodes — the ledger
itself, `llm_analyzer_base.py` and `nodes/meta_analyzer.py` emit statuses too. This rule is scoped to
the whole source tree for that reason, matching the scope its guard test already chose.

- Statuses come from `AnalyzerStatus` in `inspection_ledger.py`, never from a bare string. Import the
  member: `analyzer_status_event` raises on an undeclared spelling, and
  `tests/unit/test_analyzer_status.py` fails a status written inline.
- That guard reads three usage shapes — the `status=` argument, an assignment to a name called
  `status`, and a dict entry keyed `"status"`. Its docstring states what it therefore misses: a
  *valid* spelling reaching the ledger through a differently named variable is a style leak nothing
  catches. Import the member there too.
- `LedgerOutcome` shares the spellings `completed` and `failed`, and `inspection_ledger.py` writes
  the outcome vocabulary as bare strings on purpose. Those are correct code — do not "fix" them to
  enum members.
