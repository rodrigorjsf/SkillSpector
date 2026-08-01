---
paths:
  - "src/skillspector/yara_rules/**"
---

# YARA rules

- Rule files are auto-globbed by `static_yara.py` (`*.yar`, `*.yara`, `*.yar.b64`, `*.yara.b64`) and namespaced by filename. There is no registration list — dropping a file in is enough.
- A `.b64` suffix means the YARA source is **base64-encoded** and decoded at load time. Decode before reading or editing; do not treat it as text.
- Every rule needs a `meta:` block with `description`, `category`, `severity`, `confidence`, and `reference`. `category` is mapped to a rule id and severity by `_CATEGORY_MAP` in `static_yara.py`; an unrecognized value silently falls back to `YR4` / `MEDIUM`.
- Files are loaded in sorted order for determinism.
- `tests/unit/test_wheel_contents.py` asserts rule files ship in the wheel — no packaging config needed, but that test will catch a file the build misses.
