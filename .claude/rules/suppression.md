---
paths:
  - "src/skillspector/suppression.py"
---

# Baseline suppression

Suppressed findings are dropped from the risk score **and** from the SARIF results
(`partition_findings`). A matching bug here silently hides real vulnerabilities — treat every change
as security-relevant, not as reporting cosmetics.

- `_match_glob` is `fnmatch`, not substring. `message: "hardcoded"` does **not** match
  `"found hardcoded secret"` — a rule needs `*hardcoded*`. Matching is case-insensitive, and `**` is
  rewritten to `*`, so there is no recursive-glob semantics despite the syntax suggesting it.
- A `message` rule is tested against three fields — `finding.message`, `finding.finding`,
  `finding.matched_text`. Matching any one of them suppresses.
- `SuppressionRule.matches` returns False when `rule_id`, `path` and `message` are all unset. That
  guard is what stops an empty rule from suppressing everything; `baseline_from_dict` rejects the
  same shape at load time. Keep both.
- v1 fingerprints are rejected outright — they did not bind to finding evidence. Only a v1
  *rule-only* baseline still loads, with a warning.
- v2 fingerprints suppress only when `baseline.scanner_version` equals the running
  `scanner_version`. A mismatch logs a warning and skips them — it is **not** an error. Bumping the
  scanner version therefore disables every fingerprint suppression silently.
- `_match_glob` has no direct test coverage. `tests/unit/test_suppression.py` exercises the layers
  above it, so a change to its semantics can pass the suite — add a direct test when you touch it.
- Prose reference for baseline authors: `docs/SUPPRESSION.md`.
