# Handoff: Multi-framework skill analysis (LangChain4j + Deep Agents)

**Created:** 2026-08-01 13:30 GMT-3
**Branch:** `main` (no commits made — everything untracked)
**Scope of this handoff:** design phase complete; next action is building the LangChain4j prototype fixture

---

## Summary

Extended a fork of NVIDIA/SkillSpector with a **design** (no implementation) for scanning
LangChain4j (Java) and LangChain Deep Agents (Python) skills. Captured the upstream framework
docs into the repo, produced a phased design document, and initialized the CLAUDE.md
hierarchy. **Zero source files were modified** — `git status --short -- src/ tests/` is empty.

The immediate next action, already agreed in principle with the user, is **phase 5**: build
`tests/fixtures/langchain4j_skill/` as a standalone prototype to make the design's central
claim falsifiable.

---

## Work Completed

### Changes Made

- [x] Captured 3 upstream doc sources into `docs/references/`
- [x] Wrote `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` — 9-section design, 8 phases
- [x] Initialized CLAUDE.md hierarchy: root + 1 scoped + 6 path-scoped rules
- [x] Verified the `allowed-tools` separator defect against real source
- [x] Resolved all 4 open questions with the user; recorded as §7 "Decisions taken"
- [ ] **Phase 5 prototype fixture — NOT started. This is the next step.**

### Key Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|-------------------------|
| Keep `allowed-tools` comma parsing as-is | Fixing changes findings on today's inputs; behavior preservation outranks spec fidelity | Fix it (rejected by user); gate behind flag |
| `tree-sitter` + `tree-sitter-java` for Java | `javalang` 0.13.0 last released **2020-03-28**, Java 8 grammar — cannot parse text blocks (Java 15), which langchain4j uses for `.content("""…""")` | `javalang`; regex-only (rejected by user answer #2) |
| Advisory findings via `confidence = 0.0` | `_compute_risk_score` already skips `confidence <= 0` while keeping the finding in the list (`report.py:171-173`). **Zero changes to `report.py` scoring** | Add `NOTE` to `Severity` enum — rejected, see Gotchas |
| Advisory findings are baseline-eligible | User answer #1. An `advisory` baseline suppressing a later `strict` run is accepted, not special-cased | Exclude zero-confidence findings from baseline capture |
| Java analysis goes as far as static analysis allows | User answer #2: production LangChain4j apps are the target | Stop at regex (original design) |
| Unresolvable content emits `L4J-UNRESOLVED` | Silence would make the report read "clean" when the primary attack surface was never examined | Skip silently |

---

## Files Affected

### Created (all untracked)

- `CLAUDE.md` — root config, 28 lines
- `contrib/batch_scan/CLAUDE.md` — scoped config, 15 lines
- `.claude/rules/analyzers.md` — analyzer authoring + registry lockstep
- `.claude/rules/providers.md` — three-touch-point provider registration
- `.claude/rules/tests.md` — pytest marker mechanism
- `.claude/rules/yara-rules.md` — glob loading, `.b64` encoding, `meta:` block
- `.claude/rules/pi-extension.md` — `pi.exec` no-shell, `redactSecrets`
- `.claude/rules/allowed-tools-separator.md` — **guard rule**: prevents a future session from "fixing" the known deviation in passing
- `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` — the design (553 lines)
- `docs/references/README.md` — index + refresh commands
- `docs/references/agent-skills-specification.md` — normative spec
- `docs/references/langchain4j-skills.md` — LangChain4j Skills API
- `docs/references/langchain-deepagents-skills.md` — Deep Agents skills

### Modified

**None.** `git status --short -- src/ tests/ pyproject.toml Makefile` is empty.

### Read (reference)

- `src/skillspector/nodes/build_context.py` — `_FILE_TYPES:50`, `_EXECUTABLE_EXTENSIONS:68`, `_parse_manifest:253`, comma split `:297`
- `src/skillspector/nodes/analyzers/mcp_least_privilege.py` — `_normalize_allowed_tools:134`, `_TOOL_TO_CAPABILITY:172`, `_map_allowed_tools_to_categories:190`, `has_declaration:334`
- `src/skillspector/nodes/report.py` — `_compute_risk_score:158`, confidence skip `:199`, severity fallback `:203`, confidence render `:543`/`:815`
- `src/skillspector/multi_skill.py` — `detect_skills:51`, `iterdir():71`
- `src/skillspector/graph.py` — unconditional fan-out `:46-58`
- `src/skillspector/nodes/analyzers/__init__.py` — `ANALYZER_NODE_IDS:80`, `ANALYZER_NODES:106`
- `tests/nodes/analyzers/test_registry.py` — `EXPECTED_ANALYZER_NODE_IDS:24`
- `src/skillspector/inspection_ledger.py` — `guard_analyzer_node:773`
- `src/skillspector/input_handler.py` — zip suffix `:148`, local dir passthrough `:152`
- `docs/DEVELOPMENT.md` — §9 analyzer registration (already documents most of it)

---

## Technical Context

### The finding that shapes the whole design

**All three ecosystems share one on-disk format.** LangChain4j Skills and Deep Agents both
state upstream that they implement the Agent Skills specification. So SkillSpector **already
analyzes both frameworks' skill payloads correctly today** — every `static_patterns_*`,
`static_yara`, and `semantic_*` analyzer fires unchanged. This is not a port.

The gaps are narrow: (1) spec conformance is parsed but never validated, (2) host code (Java
wiring, `create_deep_agent` config) is invisible.

### Dependencies (proposed, not added)

- `tree-sitter` 0.26.0 + `tree-sitter-java` 0.23.5 — `requires_python >=3.10` vs project `>=3.12`. **Phase 4 is the decision gate; nothing proceeds to §3.6 standard until accepted.**

---

## Things to Know

### Gotchas & Pitfalls

- **`guard_analyzer_node` swallows every analyzer exception** (`inspection_ledger.py:773`) →
  `{"findings": []}` + `"failed"` ledger status. A broken analyzer does **not** fail the run
  or a graph-level test. Assert on findings directly.
- **`test_registry.py:24` hardcodes `EXPECTED_ANALYZER_NODE_IDS`** — exact, order-sensitive,
  asserted for equality. Every new analyzer must be added there in position.
- **Do not add `NOTE`/`INFO` to `Severity`.** `_SEVERITY_POINTS.get(sev, 5)`
  (`report.py:203`) falls back to 5 points, so a new member silently scores as `LOW`.
- **`graph.py:53` fans out unconditionally.** New analyzers run on every scan unless they
  self-gate on the first line.
- **`mypy` is configured but invoked nowhere** — not `make lint`, not CI, not pre-commit.
- **`make lint` could not run in this environment** (`ruff: No such file or directory`, no
  venv). Verified zero source change via `git status --short -- src/ tests/` instead.
- **CI enforces DCO `Signed-off-by:`** on every commit in the PR range.

### Tensions observed (unresolved by design, deliberately)

1. **Behavior preservation vs. correctness.** The `allowed-tools` defect is real and
   verified; the user chose to keep it. Recorded as a known deviation with 4 reopen triggers,
   plus `.claude/rules/allowed-tools-separator.md` so a future session does not "fix" it.
2. **CI/CD vs. the §4 gate.** Repo-level scanning needs `_SKIP_DIRS` additions and deeper
   discovery — both change `components`, the ledger's `EXCLUDED_DIRECTORY` events, and what
   `detect_skills` returns for existing inputs. Put behind `--repo-scan`; **CI/CD is not an
   exception to the gate.**
3. **"State of the art" vs. static-analysis limits.** `.content(someVar)` from a DB or remote
   call cannot be resolved. Handled by emitting `L4J-UNRESOLVED` rather than silence.
4. **Fork vs. upstream merges.** New files in new paths; existing-file diffs kept
   append-only. `test_registry.py` will conflict on every upstream analyzer addition —
   unavoidable; keep fork-added ids strictly at the end.
5. **Advisory baseline.** An `advisory` baseline suppresses a later `strict` run. Accepted by
   the user; regenerate the baseline if strict findings should resurface.

### Verified defect (documented, not fixed)

`allowed-tools` is **space**-separated per spec; SkillSpector splits on commas at
`build_context.py:297` and `mcp_least_privilege.py:143`. Reproduced against real source:

```
input:      "Bash(git:*) Bash(jq:*) Read"
parsed:     ['Bash(git:*) Bash(jq:*) Read']    # one token
categories: EMPTY SET                           # real 14-entry map
```

`has_declaration` stays `True` with an empty capability set → LP1/LP3/LP4 reason over a skill
that appears to declare tools while granting none. Neither call site has direct test coverage.

---

## Current State

### What's Working

- Design document complete and internally consistent — all internal anchors resolve
- Reference docs captured with source URLs, capture dates, and refresh commands
- CLAUDE.md hierarchy within size targets (root 28 lines, scoped 15, rules 12–17)
- Every path and symbol cited in `.claude/rules/*.md` verified against source

### What's Not Working / Not Started

- **Nothing is implemented.** The design doc's first line says so explicitly.
- No LangChain4j or Deep Agents fixture exists.

### Tests

- [ ] Unit tests: none written (nothing to test yet)
- [ ] `make lint` / `make test-unit`: **could not run** — no venv in the environment
- [x] Manual verification: `allowed-tools` repro against real source; parser candidates checked on PyPI; discovery/skip-dir gaps confirmed by reading source

---

## Next Steps

### Immediate — Phase 5: the `/prototype` fixture

Build `tests/fixtures/langchain4j_skill/`. It is pure test data, so it **cannot affect scan
behavior** and needs no gate. Deliverables:

1. **`pom.xml`** — minimal, declaring:
   ```xml
   <dependency>
     <groupId>dev.langchain4j</groupId>
     <artifactId>langchain4j-skills</artifactId>
     <version>1.18.1-beta28</version>
   </dependency>
   ```
   Optionally also `langchain4j-experimental-skills-shell` (same version) to exercise the
   `ShellSkills` detection path.

2. **`src/main/resources/skills/<name>/SKILL.md`** — spec-conformant frontmatter:
   ```markdown
   ---
   name: process-order
   description: Processes a customer order end-to-end
   ---
   ```
   The directory name **must** equal `name` (else SPEC-4 fires — which may be what you want
   for a second, deliberately-invalid fixture).

3. **One Java class** exercising the definition paths that matter:
   - `Skill.builder().name(…).description(…).content("""…""")` — text block, resolvable
   - `.content(someVariable)` — **non-literal, must trigger `L4J-UNRESOLVED`**
   - A `@Tool("…")`-annotated method class passed via `.tools(new OrderTools())`
   - `McpToolProvider.builder()` **without** `.toolFilter(…)`
   - Optionally `ShellSkills.from(…)` for the high-severity path

4. **Run the falsification test:**
   ```bash
   skillspector scan tests/fixtures/langchain4j_skill/ --format json --no-llm
   ```
   The §3.7 claim is that this yields **zero skills**, because `detect_skills` uses
   `iterdir()` (depth 1) and `SKILL.md` sits at depth 4. Confirm or refute — this is the
   whole point of the prototype.

### Subsequent

- Phases 1–3 (detect_framework → `framework_deepagents` → `structure_agent_skills_spec`) are
  independent of the Java work and touch no existing code path. They can proceed in parallel.
- Phase 4 (tree-sitter dependency decision) gates phase 6.

### Blocked On

- **Phase 6** (`framework_langchain4j`) is blocked on the phase-4 dependency decision.
- Nothing blocks phase 5.

---

## Related Resources

### Documentation (in-repo)

- `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` — the design. §3.6 has the definition-path
  coverage table; §3.7 the CI/CD discovery gaps; §5 the phasing; §7 decisions taken
- `docs/references/langchain4j-skills.md` — every Java code sample needed for the fixture
- `docs/references/agent-skills-specification.md` — frontmatter constraints for SPEC-1..17
- `docs/DEVELOPMENT.md` §9 — analyzer registration walkthrough

### Commands

```bash
# Baseline capture, required before ANY behavior-affecting change (§4 gate)
mkdir -p /tmp/ss-before
for f in tests/fixtures/*/; do
  skillspector scan "$f" --format json --no-llm -o "/tmp/ss-before/$(basename "$f").json"
done
# after the change, repeat into /tmp/ss-after/ then:
diff -ru /tmp/ss-before /tmp/ss-after     # MUST be empty

# Environment (no venv exists yet in this checkout)
uv venv .venv && source .venv/bin/activate && make install-dev
make test-unit && make lint && make format-check

# Refresh captured upstream docs
curl -sSL https://agentskills.io/specification.md
curl -sSL https://docs.langchain.com/oss/python/deepagents/skills.md
curl -sSL https://docs.langchain4j.dev/tutorials/skills/ | lynx -dump -nolist -stdin
```

### Search queries

- `grep -n "iterdir" src/skillspector/multi_skill.py` — the depth-1 discovery limit
- `grep -n "_SKIP_DIRS" -A 3 src/skillspector/nodes/build_context.py` — missing JVM build dirs
- `grep -n "confidence <= 0" src/skillspector/nodes/report.py` — the advisory mechanism
- `grep -rn "split(\",\")" src/skillspector/` — both `allowed-tools` call sites

---

## Open Questions

- [ ] **`.jar` ingest scope** — is the CLI ever pointed at a built artifact rather than a
      source tree? Reading `src/main/resources/skills/` out of a JAR is useful; reading
      `.class` files is not.
- [ ] **`--repo-scan` discovery roots** — a monorepo with several modules needs per-module
      roots. Configurable list, or infer from `pom.xml` / `pyproject.toml` locations?

---

## Session Notes

- **Nothing is committed.** All 13 files are untracked on `main`. If the user wants them
  kept, branch first — `main` is the default branch and the repo's convention is PRs.
- `.codegraph/` also appears untracked; it was not created by this work.
- Doc-capture technique worth reusing: Mintlify sites (`docs.langchain.com`,
  `agentskills.io`) serve raw markdown by appending `.md` to the URL. Docusaurus
  (`docs.langchain4j.dev`) serves HTML only — `lynx -dump -nolist` converts it acceptably.
  The chrome-devtools MCP was never needed.
- A memory-consolidation pass ran and correctly saved nothing: every durable fact from this
  session is already in the repo artifacts above, so duplicating into user-local memory would
  create drift.

---

_Generated by `/handoff`. Start a new session with this document as initial context._
