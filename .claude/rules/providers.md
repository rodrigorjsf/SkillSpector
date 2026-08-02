---
paths:
  - "src/skillspector/providers/**/*.py"
---

# LLM providers

- Each provider is a subpackage: `__init__.py` + `provider.py` + a bundled `model_registry.yaml`. CLI providers omit the YAML.
- Implement the Protocols in `providers/base.py`. `ModelMetadataProvider` requires `DEFAULT_MODEL`, `SLOT_DEFAULTS`, and `resolve_model`; `CredentialsProvider`, `ChatModelProvider`, and `AgentCLICapable` are optional.
- Registering a new provider touches **three** places in `providers/__init__.py`: the module docstring's provider table, the `if name == "..."` chain in `_select_active_provider()`, and the `ValueError` message listing valid names.
- CLI providers must route every subprocess call through `providers/_agent_cli.py`, never raw `subprocess`. It enforces `shell=False`, untrusted content via stdin only, capability stripping, environment scrubbing, and a per-call timeout.
- `model_registry.yaml` is read by `registry.py`'s `lookup_context_length` / `lookup_max_output_tokens`. Adding one means `tests/unit/test_wheel_contents.py` must assert it ships in the wheel.
- The `provider` `StringEnum` in `extensions/skillspector.ts` mirrors the valid `SKILLSPECTOR_PROVIDER` values and is already stale. Update it when adding a provider — the current gap is enumerated in `.claude/rules/pi-extension.md`, so it is tracked in one place rather than drifting between two.
