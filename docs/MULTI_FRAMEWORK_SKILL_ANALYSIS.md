# Multi-framework skill analysis — design

**Status:** design proposal. Nothing described here is implemented.
**Goal:** extend SkillSpector to evaluate skills hosted by **LangChain4j** (Java) and
**LangChain Deep Agents** (Python), covering both structural/best-practice conformance and
the security analysis SkillSpector already performs.
**Hard constraint:** current behavior on current inputs must not change. This document
treats that as a testable gate, not a promise — see [§4](#4-the-unchanged-behavior-gate).

Framework references live in [`docs/references/`](references/README.md).

---

## 1. The finding that shapes everything

**All three skill ecosystems share one on-disk format.** LangChain4j Skills and Deep Agents
both state upstream that they implement the
[Agent Skills specification](references/agent-skills-specification.md) — the same
`SKILL.md` + `scripts/` + `references/` + `assets/` layout SkillSpector already scans, with
the same frontmatter keys `_parse_manifest` already reads
(`src/skillspector/nodes/build_context.py:253`).

The practical consequence is large and worth stating plainly before any design follows:

> **SkillSpector already analyzes LangChain4j and Deep Agents skill payloads correctly
> today.** Point `skillspector scan` at a `skills/docx/` directory from either framework and
> all 14 `static_patterns_*` analyzers, `static_yara`, and the three `semantic_*` analyzers
> run exactly as they do on a Claude Code skill. For Deep Agents, `behavioral_ast` and
> `behavioral_taint_tracking` also cover `scripts/` unchanged, because the scripts are
> Python.

So this is not a port. The gap is narrower and sits in two places:

1. **Spec conformance is parsed but never validated.** SkillSpector extracts frontmatter
   and never checks it against the specification's constraints.
2. **Host code is invisible.** The code that *wires* skills into an application —
   `ShellSkills` in Java, `create_deep_agent(permissions=...)` in Python — carries the
   security-relevant configuration, and none of it lives in `SKILL.md`.

## 2. Gap analysis

### 2.1 Spec conformance (framework-independent)

The specification defines machine-checkable constraints for every field. None are enforced.

| Constraint | Currently |
|------------|-----------|
| `name` matches parent directory name | Not checked |
| `name` charset, 1–64 chars, no leading/trailing/consecutive hyphens | Not checked |
| `description` present, ≤ 1024 chars | Not checked |
| `compatibility` ≤ 500 chars | Field not parsed at all |
| `SKILL.md` body ≤ 500 lines / ~5000 tokens | Not checked |
| File references one level deep, targets exist | Not checked |
| `allowed-tools` is **space**-separated | **Parsed as comma-separated** |

The last row is a live defect rather than a missing feature. `_parse_manifest`
(`build_context.py:297`) and `_normalize_allowed_tools`
(`src/skillspector/nodes/analyzers/mcp_least_privilege.py:143`) both split on `,`. A
spec-canonical value collapses to one token:

```
input:      "Bash(git:*) Bash(jq:*) Read"
parsed:     ['Bash(git:*) Bash(jq:*) Read']
categories: set()
```

`_map_allowed_tools_to_categories` (`mcp_least_privilege.py:190`) does an exact lowercase
lookup against `_TOOL_TO_CAPABILITY` (`mcp_least_privilege.py:172`), so the single token
matches nothing. `has_declaration` is `True` at `mcp_least_privilege.py:334` while the
derived capability set is empty — LP1/LP4 reason over a skill that appears to declare tools
while granting no capabilities. Scoped syntax (`Bash(git:*)`) also fails to match even after
correct whitespace splitting; the base tool name needs extracting first.

**Decision: current behavior is retained.** Fixing this changes findings on existing
inputs, which the non-negotiable constraint forbids. It is recorded as a known deviation
with an explicit trigger rather than scheduled as work — see
[§5, Known deviation](#known-deviation-allowed-tools-separator).

### 2.2 LangChain4j (Java host)

| Signal | Risk | Nearest existing analyzer |
|--------|------|---------------------------|
| `ShellSkills` / `langchain4j-experimental-skills-shell` present | Unsandboxed arbitrary command execution — upstream itself documents this as unsafe | `static_patterns_excessive_agency`, `static_patterns_privilege_escalation` |
| `RunShellCommandToolConfig.workingDirectory` unset | Commands default to the JVM's `user.dir` | `static_patterns_excessive_agency` |
| `@Tool("...")` description text | Instruction-carrying string the model reads — the tool-poisoning surface, in Java rather than an MCP manifest | `mcp_tool_poisoning` (TP1–TP4) |
| `McpToolProvider` without `.toolFilter(...)` | Every MCP tool exposed post-activation instead of a scoped subset | `mcp_least_privilege` (LP1–LP4) |
| Skill `content(...)` built by concatenation or fetched remotely | Instruction text that exists in no scanned file | `static_patterns_prompt_injection` |
| `pom.xml` / `build.gradle` dependencies | Maven ecosystem unsupported in `osv_client.py:56` (PyPI and npm only) | `static_patterns_supply_chain` (SC4) |

Two structural facts make Java harder than Python:

- **No `.java` file type.** `_FILE_TYPES` (`build_context.py:50`) has no `.java`, `.kt`,
  `.gradle`, or `.xml` entry, so `pom.xml` and every Java source file classify as `"other"`.
  `_EXECUTABLE_EXTENSIONS` (`build_context.py:68`) has no JVM entry, so
  `has_executable_scripts` stays `False` for a Java-only skill and the risk multiplier that
  depends on it never applies.
- **No Java parser in the dependency set.** `behavioral_ast` and `behavioral_taint_tracking`
  are built on Python's stdlib `ast`. Java needs one added — see
  [§3.6](#36-java-parsing-and-definition-path-coverage) for the choice and its cost.

`ClassPathSkillLoader` also allows skills under `src/main/resources/skills/` or bundled
inside a JAR. The path is trivially handled; the JAR is not — `InputHandler` keys archive
handling off the `.zip` suffix (`src/skillspector/input_handler.py:148`), so a `.jar` is
never opened.

### 2.3 Deep Agents (Python host)

| Signal | Risk | Nearest existing analyzer |
|--------|------|---------------------------|
| `create_deep_agent(skills=[...])` with no `permissions=[...]` | Agents can write to skill files by default when the backend permits — self-modifying skills | `mcp_rug_pull` (RP1–RP3), `static_patterns_memory_poisoning` |
| No `FilesystemPermission(..., mode="deny")` on a `/skills/**` path also passed in `skills` | Writable shared skill library | `mcp_least_privilege` |
| `interrupt_on` absent for `write_file` / `edit_file` | No human in the loop for skill mutation | `static_patterns_excessive_agency` |
| Duplicate skill `name` across sources | Silent last-one-wins override | New |
| Custom subagent without its own `skills` | Capability silently unavailable — a correctness bug upstream calls out | New |

The duplicate-name case is the most interesting new primitive. `skills=[shared, personal]`
means a user-writable `personal/` skill can shadow a curated `shared/` skill of the same
name. That is supply-chain substitution expressible purely in configuration and invisible to
any single-directory scan. Detecting it requires reasoning across the whole list of skill
sources — architecturally closer to `multi_skill.detect_skills`
(`src/skillspector/multi_skill.py:51`) than to any per-file analyzer.

Deep Agents is substantially cheaper to support than LangChain4j: its host language is the
one SkillSpector already parses, so host-code detection reuses the existing Python AST
infrastructure rather than requiring new machinery.

## 3. Architecture

### 3.1 Principle: detect, then gate

`graph.py:53` fans out **every** id in `ANALYZER_NODE_IDS` from `build_context`
unconditionally. Appending framework analyzers therefore executes them on every existing
scan. Even when they produce no findings they still run through `guard_analyzer_node`
(`src/skillspector/inspection_ledger.py:773`) and emit ledger status events that
`finalize_inspection_ledger` can surface as `ledger_exceptions` in terminal and markdown
output (`src/skillspector/nodes/report.py:441`, `:741`).

So the rule is **additive *and* gated**, never unconditionally wired:

```
build_context
  └─ detect_framework(components, file_cache, manifest) → framework: str
       "agent_skills" (default) | "langchain4j" | "deepagents"

framework_* analyzers
  └─ first statement: if state.get("framework") not in (...): return {"findings": []}
```

A new `framework` key on `SkillspectorState` is set by `build_context` and read by the new
analyzers. Existing analyzers never read it and are untouched.

### 3.2 Detection signals

Detection must be conservative: **when in doubt, return `"agent_skills"`** and behave
exactly as today.

| Framework | Positive signals |
|-----------|------------------|
| `langchain4j` | `pom.xml` / `build.gradle*` containing `dev.langchain4j`; any `.java`/`.kt` file importing `dev.langchain4j.*`; `src/main/resources/skills/` layout |
| `deepagents` | `pyproject.toml` / `requirements*.txt` naming `deepagents`; any `.py` importing `deepagents` or calling `create_deep_agent` |

Detection is a pure function over `components` and `file_cache`, both already built. It adds
no I/O and cannot fail a scan.

### 3.3 Proposed analyzer nodes

Four new nodes, appended to `ANALYZER_NODE_IDS` after `semantic_quality_policy` so existing
ordering is preserved:

| Node id | Gate | Rules |
|---------|------|-------|
| `structure_agent_skills_spec` | `--spec-checks` (opt-in, default `off`) | Frontmatter conformance: name↔directory, charset, length, description bounds, body size, dangling file references. Rule catalogue and scoring split in [§3.5](#35-spec-conformance-rules-and-scoring) |
| `framework_langchain4j` | `framework == "langchain4j"` | `ShellSkills` usage, unset `workingDirectory`, `@Tool` description poisoning, unfiltered `McpToolProvider` |
| `framework_deepagents` | `framework == "deepagents"` | Missing `permissions` / `interrupt_on`, writable `/skills/**`, subagent skill inheritance, duplicate skill `name` across the `skills=[...]` list |

> **Note on `structure_agent_skills_spec`.** This one is framework-independent and would fire
> on existing inputs, which is exactly what the gate forbids. Hence the opt-in flag rather
> than a detection gate: it stays off until a major version, then flips to on-by-default with
> a changelog entry. This is the honest cost of the constraint — valuable checks that apply
> to today's inputs cannot be silently enabled.

> **Note on duplicate skill names.** There are two distinct cases and they live in different
> nodes. Shadowing across the Deep Agents `skills=[...]` list — where last-one-wins is
> documented upstream — belongs to `framework_deepagents`. Duplicate names across sibling
> skill *directories* have no override semantics of their own and are covered by SPEC-17 in
> [§3.5](#35-spec-conformance-rules-and-scoring).

`framework_langchain4j` parses Java with tree-sitter rather than matching patterns — see
[§3.6](#36-java-parsing-and-definition-path-coverage). Deep Agents detection reuses the
existing Python `ast` infrastructure to inspect `create_deep_agent` call keywords directly.

### 3.4 Supporting changes

| Change | File | Risk |
|--------|------|------|
| Add `.java`, `.kt`, `.gradle`, `.xml` to `_FILE_TYPES` | `build_context.py:50` | **Behavior-affecting** — flips `component_metadata[].type` from `"other"` for any current scan containing such a file |
| Add JVM extensions to `_EXECUTABLE_EXTENSIONS` | `build_context.py:68` | **Behavior-affecting** — flips `has_executable_scripts`, which feeds the risk multiplier |
| Maven ecosystem in OSV queries | `osv_client.py:56` | Additive — new ecosystem constant, new lockfile parser |
| `.jar` treated as an archive | `input_handler.py:148` | Additive — new input type, must inherit the existing zip-slip and size caps |

The first two rows are the ones to be careful with. Neither is required for the framework
analyzers to work — `framework_langchain4j` selects its inputs by path suffix and reads
`file_cache` directly, regardless of the inferred type — so **both should be deferred**
rather than bundled into the first phase.

### 3.5 Spec-conformance rules and scoring

#### The rule catalogue

Sixteen deterministic checks — string comparison and path existence, no LLM. None is covered
today; the nearest analyzer, `semantic_quality_policy` (SQP-1/2/3), judges trigger vagueness,
missing user warnings, and natural-language policy violations, all by LLM. It checks nothing
mechanical.

| Rule | Check | Spec | Scored by default |
|------|-------|------|-------------------|
| SPEC-1 | `SKILL.md` has no frontmatter, or the YAML fails to parse | — | No |
| SPEC-2 | `name` missing | required | No |
| SPEC-3 | `description` missing | required | No |
| SPEC-4 | `name` ≠ parent directory name | `name` | **Yes** |
| SPEC-5 | `name` contains characters outside `a-z0-9-` | `name` | No |
| SPEC-6 | `name` starts/ends with `-`, or contains `--` | `name` | No |
| SPEC-7 | `name` longer than 64 characters | `name` | No |
| SPEC-8 | `description` empty | `description` | No |
| SPEC-9 | `description` longer than 1024 characters | `description` | **Yes** |
| SPEC-10 | `compatibility` longer than 500 characters | `compatibility` | No |
| SPEC-11 | `metadata` is not a string→string mapping | `metadata` | No |
| SPEC-12 | `SKILL.md` body over 500 lines | progressive disclosure (SHOULD) | No |
| SPEC-13 | `SKILL.md` body over ~5000 tokens | progressive disclosure (SHOULD) | No |
| SPEC-14 | `SKILL.md` over 10 MB — Deep Agents skips the file silently | Deep Agents | **Yes** |
| SPEC-15 | `SKILL.md` references a relative path that does not exist | file references | **Yes** |
| SPEC-16 | File reference more than one level deep | file references (SHOULD) | No |
| SPEC-17 | Two skill directories in the same scan declare the same `name` | `name` uniqueness | **Yes** |

Five rules are scored by default because each has a runtime consequence, not merely a style
one:

- **SPEC-4** — Deep Agents resolves same-name overrides across the `skills=[...]` list by
  `name`, not by path. A `name` that disagrees with its directory is a shadowing primitive.
- **SPEC-9** — the description goes into the system prompt in both frameworks; content past
  the 1024-character cut is silently dropped.
- **SPEC-14** — the skill looks installed and never loads.
- **SPEC-15** — `SKILL.md` instructs the agent to run a script that is not there, so the
  agent improvises.
- **SPEC-17** — a duplicate `name` across sibling skill directories. `multi_skill.detect_skills`
  has no override semantics of its own, so this is not a substitution primitive the way the
  Deep Agents `skills=[...]` list is. It is scored anyway because whichever loader consumes
  those directories will have to pick one, and the choice is not visible from the tree.

The remaining twelve are conformance and hygiene. They are reported, not scored.

#### The `--spec-checks` flag

One new CLI option, a `StrEnum` following the existing `FormatChoice` / `TransportChoice`
pattern (`src/skillspector/cli.py:76`, `:85`):

| Value | Behavior |
|-------|----------|
| `off` (default) | Analyzer returns `{"findings": []}`. Today's behavior exactly. |
| `advisory` | All 16 rules run. The four above score normally; the other twelve are reported but contribute zero. |
| `strict` | All 16 rules run and **all** contribute to the risk score. |

#### The mechanism — no scorer change required

`_compute_risk_score` already has the exact semantics needed, and its docstring states them
(`src/skillspector/nodes/report.py:171-173`):

> Each finding's contribution is also scaled by its confidence value (clamped to [0, 1]).
> Findings with confidence <= 0 are skipped entirely — **they do not contribute to the score
> but remain in the reported findings list.**

So advisory findings are emitted with `confidence = 0.0`. They flow into `findings`, SARIF,
terminal, and markdown output unchanged, and `_compute_risk_score` skips them at
`report.py:199`. **`report.py` is not modified at all.** The mode gate lives entirely inside
the new analyzer, which decides each finding's confidence:

```python
# structure_agent_skills_spec
scored = mode == "strict" or rule_id in _SCORED_BY_DEFAULT
confidence = _RULE_CONFIDENCE[rule_id] if scored else 0.0
```

This is why the enum lives on the flag rather than in `models.py`: **do not add a `NOTE` or
`INFO` member to `Severity`.** `_SEVERITY_POINTS.get(sev, 5)` (`report.py:203`) falls back to
5 points for any unrecognized severity, so a new member would silently score as `LOW` unless
every scoring table were updated in lockstep. The confidence channel needs none of that.

#### Visual treatment

`confidence` is already rendered — `report.py:543` (terminal) and `:815` (markdown) — but as
`Confidence: 0%`, which reads as "we are unsure" rather than "advisory, not scored". That is
misleading enough to fix, and it is the one report-side change this design needs:

- Render advisory findings under a separate `Spec conformance (advisory — not scored)`
  heading rather than inline with security findings.
- Replace the `0%` confidence line with an explicit `Not scored — run with
  --spec-checks=strict to include` note.
- Print a one-line summary when advisory findings exist and the mode is `advisory`, so the
  count is visible without reading the whole report.

Both changes are additive and reachable only when `--spec-checks` is not `off`, so the
[§4 gate](#4-the-unchanged-behavior-gate) still holds: with the flag absent, the diff is
empty.

#### Baseline interaction — decided

Baseline suppression (`suppression.py`) fingerprints findings by rule and location. Advisory
findings enter the findings list, so they are baseline-eligible like any other, **by design**.

The consequence is accepted: a baseline captured under `--spec-checks=advisory` will suppress
those same rules in a later `--spec-checks=strict` run. Escalating the flag does not
resurrect findings a maintainer already accepted. If a strict run should re-surface them, the
baseline is regenerated — the same workflow as any other accepted finding. No special-casing
of zero-confidence findings in `suppression.py`.

### 3.6 Java parsing and definition-path coverage

The goal is production LangChain4j applications, so this section covers **every way
LangChain4j lets a skill be defined**, and says plainly where static analysis stops.

#### Parser choice: tree-sitter

| Candidate | Verdict |
|-----------|---------|
| `javalang` 0.13.0 | **Rejected.** Last released 2020-03-28, Java 8 era grammar — predates text blocks (Java 15). LangChain4j's own docs define skill content with `.content("""…""")`, so the single most important construct fails to parse. |
| `tree-sitter` 0.26.0 + `tree-sitter-java` 0.23.5 | **Chosen.** Current, `requires_python >=3.10` against this project's `>=3.12`, error-tolerant parsing (a partially-invalid file still yields a usable tree). |

This adds a runtime dependency to a deliberately tight dependency list, so it lands in its
own phase with its own decision — see [§5](#5-phasing). Until it is accepted,
`framework_langchain4j` is not implementable to the standard this section describes.

#### Definition-path coverage

| Definition path | Statically resolvable | Notes |
|-----------------|----------------------|-------|
| `FileSystemSkillLoader.loadSkills(Path.of("skills/"))` | Yes | Literal path argument |
| `FileSystemSkillLoader.loadSkill(Path.of("skills/docx"))` | Yes | Single-skill form |
| `ClassPathSkillLoader.loadSkills("skills")` | Yes | Resolves to `src/main/resources/skills/` |
| `Skill.builder().content("""…""")` | Yes | Text block or string literal |
| `Skill.builder().content(CONSTANT)` | Usually | Resolvable when the constant is a literal in the same compilation unit |
| `Skill.builder().content(someVar)` — DB, remote API, runtime-generated | **No** | See below |
| `SkillResource.builder().relativePath(…).content(…)` | Same rules as `Skill.builder()` | |
| `skill.toBuilder().tools(new OrderTools())` | Yes | Resolve the class, read its `@Tool` annotations |
| `.toolProviders(McpToolProvider.builder()…)` | Yes | Presence and `.toolFilter(…)` absence are both visible |
| `.tools(Map.of(spec, executor))` | Partially | The `ToolSpecification` literal is readable; the `ToolExecutor` lambda body is not analyzed |
| `Skills.from(…)` vs `ShellSkills.from(…)` | Yes | Mode selection is a type reference |

#### The coverage limit, stated as a finding

"State of the art" cannot mean resolving arbitrary Java dataflow. A skill whose `content(…)`
comes from a variable, a database, or a remote call has **instruction text that exists in no
scanned file** — invisible to every content analyzer SkillSpector has.

Silence there would be worse than a finding, because the report would read as "clean" when
the primary attack surface was never examined. So this emits its own rule:

> **L4J-UNRESOLVED** — *Skill content is not statically resolvable; the instruction surface
> was not scanned.* Severity `MEDIUM`, reported whenever a `Skill.builder()` chain reaches
> `.content(…)` with a non-literal argument. Names the file and line of the builder chain.

The same applies to `.name(…)` and `.description(…)` built dynamically, and to
`ClassPathSkillLoader.loadSkill(path, myClassLoader)` with a custom loader whose resolution
cannot be followed.

### 3.7 Repository-level discovery (CI/CD)

The stated target is running the CLI in the CI/CD pipeline of a Java or Python application —
i.e. against a **whole repository**, not a skill directory. Three verified facts block that
today:

| Fact | Evidence | Consequence |
|------|----------|-------------|
| `detect_skills` iterates immediate children only | `multi_skill.py:71` (`iterdir()`) | `src/main/resources/skills/*/SKILL.md` sits at depth 4 and is never found. **A production Java repo scans as zero skills.** |
| `_SKIP_DIRS` has no JVM build directories | `build_context.py:46` — `{.git, __pycache__, node_modules, .venv, venv, .tox, .pytest_cache}` | A post-`mvn package` tree walks all of `target/`, including compiled classes and any fat JAR |
| A local directory input has no ingest cap | `input_handler.py:152` returns the path directly; only `MAX_FILE_CHARS = 1_000_000` per file applies (`static_runner.py:60`) | Repo size is unbounded at ingest; the per-file cap does not bound the walk |

Required work:

1. **Deep skill discovery** — find `SKILL.md` at any depth under conventional roots
   (`skills/`, `src/main/resources/skills/`, `.deepagents/skills/`, `.agents/skills/`),
   bounded by a maximum depth and by the skip list.
2. **JVM build-directory exclusion** — add `target`, `build`, `.gradle`, `.mvn`, `out` to the
   walk's skip set.

**Neither is free, and neither may be applied unconditionally.** Adding entries to
`_SKIP_DIRS` changes `components` and the ledger's `EXCLUDED_DIRECTORY` events for any
existing scan that contains a `build/` or `target/` directory — the same class of change as
the `_FILE_TYPES` edit already deferred in [§3.4](#34-supporting-changes). Deepening
discovery likewise changes what `detect_skills` returns for existing inputs.

Both therefore go behind the framework gate or an explicit `--repo-scan` flag. CI/CD is not
an exception to the [§4 gate](#4-the-unchanged-behavior-gate).

What already works for CI/CD and needs nothing: SARIF output (GitHub code scanning ingests
it directly), exit code 1 above the risk threshold and 2 on error, and `--baseline` for
accepting known findings.

## 4. The unchanged-behavior gate

"Current behavior must not change" becomes a command that either passes or fails.

**Before any change**, capture a baseline across the existing fixture corpus:

```bash
for f in tests/fixtures/*/; do
  skillspector scan "$f" --format json --no-llm \
    -o "/tmp/ss-before/$(basename "$f").json"
done
```

**After each phase**, re-capture into `/tmp/ss-after/` and diff:

```bash
diff -ru /tmp/ss-before /tmp/ss-after
```

`--no-llm` is load-bearing: the semantic analyzers are non-deterministic, so a diff that
includes them proves nothing.

Acceptance for any phase claiming to be behavior-preserving:

1. `diff -ru /tmp/ss-before /tmp/ss-after` is **empty**.
2. `make test-unit` green.
3. `make lint` and `make format-check` green.
4. `ruff` is the only linter CI runs — `mypy` is configured (`pyproject.toml:94`) but
   invoked nowhere, so type errors will not be caught for you.

Two traps worth stating explicitly:

- **`tests/nodes/analyzers/test_registry.py:24` hardcodes `EXPECTED_ANALYZER_NODE_IDS`** as
  an exact, order-sensitive list and asserts equality. Every new analyzer must be added
  there, in position, or the suite fails.
- **`guard_analyzer_node` swallows exceptions** (`inspection_ledger.py:773`). A new analyzer
  that throws on every file is converted to `{"findings": []}` plus a `"failed"` ledger
  status and will *not* fail the run. A green test suite is not evidence a new analyzer
  works — assert on its findings directly.

Fixtures for the new frameworks go in new directories (`tests/fixtures/langchain4j_skill/`,
`tests/fixtures/deepagents_skill/`) so the before/after diff over existing fixtures stays
meaningful.

## 5. Phasing

Ordered by value-to-risk. Each phase is independently shippable and independently revertible.

| Phase | Content | Behavior-preserving? |
|-------|---------|----------------------|
| **0** | This document + [`docs/references/`](references/README.md) | Yes — docs only |
| **1** | `detect_framework` + `framework` state key. No analyzer reads it yet. Unit tests assert correct detection on new fixtures and `"agent_skills"` on every existing fixture | Yes |
| **2** | `framework_deepagents` analyzer, gated. Cheapest — reuses Python AST | Yes, via gate |
| **3** | `structure_agent_skills_spec` behind `--spec-checks` (default `off`), plus the advisory-section rendering in [§3.5](#35-spec-conformance-rules-and-scoring) | Yes, via opt-in |
| **4** | **Dependency decision:** accept `tree-sitter` + `tree-sitter-java` ([§3.6](#36-java-parsing-and-definition-path-coverage)). Nothing ships — this is a gate on phases 5–6 | N/A |
| **5** | LangChain4j fixture: minimal `pom.xml` + `src/main/resources/skills/` + a `Skill.builder()` class under `tests/fixtures/langchain4j_skill/`. Prerequisite for any phase-6 assertion | Yes — test data only |
| **6** | `framework_langchain4j` analyzer, gated. Tree-sitter over `.java`, full definition-path coverage per [§3.6](#36-java-parsing-and-definition-path-coverage), including `L4J-UNRESOLVED` | Yes, via gate |
| **7** | Repository-level discovery for CI/CD ([§3.7](#37-repository-level-discovery-cicd)): deep `SKILL.md` search + JVM build-dir exclusion, behind `--repo-scan` | Yes, via flag — **not** if applied unconditionally |
| **8** | Maven/OSV, `.jar` ingest, `_FILE_TYPES` / `_EXECUTABLE_EXTENSIONS` additions | Mixed — the last two are behavior-affecting; ship separately |

Phases 1–3 deliver Deep Agents support and spec conformance without touching a single
existing code path. Phase 4 is a decision, not code: tree-sitter adds a runtime dependency to
a deliberately tight list, and phases 5–6 cannot proceed to the standard §3.6 describes until
it is accepted. Phase 8's last two items are the only scheduled work that trades the
constraint for correctness.

### Known deviation: `allowed-tools` separator

SkillSpector splits the Agent Skills `allowed-tools` frontmatter field on commas; the
specification defines it as **space**-separated. Full analysis in [§2.1](#21-spec-conformance-framework-independent).

**Status: observed, deliberately unfixed.** Correcting the separator changes findings on
inputs that are scanned today, and preserving current behavior outranks spec fidelity here.
This is a recorded deviation, not a backlog item — no work is scheduled against it.

**Blast radius if it were changed** (both call sites lack direct test coverage):

| Site | Current |
|------|---------|
| `src/skillspector/nodes/build_context.py:297` | `allowed_tools.split(",")` → `manifest["allowed-tools"]` |
| `src/skillspector/nodes/analyzers/mcp_least_privilege.py:143` | `value.split(",")` in `_normalize_allowed_tools` |

Downstream: `_map_allowed_tools_to_categories` (`mcp_least_privilege.py:190`) and the
`has_declaration` branch (`mcp_least_privilege.py:334`), which drive LP1, LP3, and LP4.

**Reopen this decision when any of these is observed:**

1. A real scan of a skill whose `allowed-tools` uses the spec-canonical space separator
   produces a wrong LP1/LP3/LP4 verdict — most likely LP3 suppressed (a declaration is
   present, so `has_declaration` is `True`) while no capability category was actually
   derived, so declared-vs-detected reconciliation silently passes.
2. A user reports a false negative or false positive traceable to `allowed-tools` parsing.
3. Upstream NVIDIA/SkillSpector changes the separator — then take theirs and drop this note.
4. Scoped tool syntax (`Bash(git:*)`) needs to map to a capability. That requires extracting
   the base tool name before the `_TOOL_TO_CAPABILITY` lookup, and is a second, independent
   defect from the separator: it fails even with correct whitespace splitting.

**If reopened**, the change is not behavior-preserving. It needs a changelog entry, a minor
version bump, and — because `.skillspector-baseline.example.yaml` shows baselines are in
use — a note that existing baselines may need regenerating.

A regression test asserting the *current* comma behavior would lock in the deviation and make
a future fix look like a break. Prefer a test that documents the deviation explicitly (named
for it, with a comment pointing here) over one that silently ratifies it.

## 6. Fork considerations

This repository is a fork of [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector).
Assuming upstream merges continue:

- **New files in new paths.** `docs/references/`, `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md`,
  `src/skillspector/nodes/analyzers/framework_*.py`, `tests/fixtures/langchain4j_skill/`.
  These never conflict.
- **Where an existing file must change, keep the diff append-only.** Appending to
  `ANALYZER_NODE_IDS`, `ANALYZER_NODES`, `_FILE_TYPES`, and `EXPECTED_ANALYZER_NODE_IDS`
  produces conflicts that resolve by taking both sides. Reordering or reformatting those
  lists does not.
- **`test_registry.py` will conflict on every upstream analyzer addition.** Unavoidable —
  the list is order-sensitive by design. Keep fork-added ids strictly at the end.
- Upstream commit `e8e08c5` ("read exact versions from Python lockfiles for OSV") is the
  closest precedent for the phase-8 supply-chain work; follow its shape.

## 7. Decisions taken

Recorded so the reasoning is not relitigated. Each links to where it is implemented in the design.

| Question | Decision |
|----------|----------|
| Should an `advisory` run write spec findings into a baseline? | **Yes.** Advisory findings are baseline-eligible by design; an `advisory` baseline suppressing a later `strict` run is accepted, not special-cased ([§3.5](#baseline-interaction--decided)) |
| How far into Java? | **As far as static analysis allows.** Target is production LangChain4j applications, so tree-sitter replaces regex and every definition path is covered, with unresolvable content reported as `L4J-UNRESOLVED` rather than passed over ([§3.6](#36-java-parsing-and-definition-path-coverage)) |
| Directory-level shadowing check? | **Yes**, as SPEC-17, scored by default ([§3.5](#35-spec-conformance-rules-and-scoring)) |
| Where does the CLI run? | Primary usage is repository-level with codebase access; CI/CD of a Java or Python application is the production target ([§3.7](#37-repository-level-discovery-cicd)) |
| `allowed-tools` separator | **Keep current behavior.** Recorded as a known deviation with reopen triggers ([§5](#known-deviation-allowed-tools-separator)) |

## 8. Open questions

1. **`.jar` ingest scope.** A JAR is a zip, but usually holds compiled classes, not source.
   Reading `src/main/resources/skills/` out of one is useful; reading `.class` files is not.
   Worth confirming the deployment shape — is the CLI ever pointed at a built artifact rather
   than a source tree? — before building it (phase 8).
2. **`--repo-scan` discovery roots.** [§3.7](#37-repository-level-discovery-cicd) proposes
   `skills/`, `src/main/resources/skills/`, `.deepagents/skills/`, `.agents/skills/`. A
   monorepo with several modules would need per-module roots. Whether to make the root list
   configurable or infer it from `pom.xml` / `pyproject.toml` locations is unresolved.

## 9. Recommended next step

Phase 5 as a standalone prototype, before any analyzer work: build
`tests/fixtures/langchain4j_skill/` with a minimal `pom.xml` declaring
`dev.langchain4j:langchain4j-skills`, a `src/main/resources/skills/<name>/SKILL.md`, and one
Java class exercising `Skill.builder()`, `@Tool`, and a non-literal `.content(…)`.

It is cheap, it is pure test data so it cannot affect behavior, and it makes the rest
falsifiable: run today's `skillspector scan` against it and the §3.7 claim that a production
Java repo scans as zero skills either reproduces or does not. Every later phase then has
something to assert against.
