# Execute LangChain4j before Deep Agents

Status: accepted

`docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` §5 orders the phasing **by value-to-risk** and puts the
Deep Agents Analyzer first (phase 2) because it is the cheapest — it reuses the Python `ast`
infrastructure and adds no runtime dependency — while the LangChain4j Analyzer is the most expensive,
gated behind a tree-sitter dependency decision (phase 4) and a new parser.

We override that order for **execution**: the LangChain4j Analyzer ships first, paired with
repository-level discovery, as a single "LangChain4j in CI" increment. Deep Agents (phase 2) and
spec conformance (phase 3) follow it. §5 stands unchanged as the value-to-risk analysis of record;
this ADR records that execution is sequenced on a different axis and why.

## Considered Options

**Order: value-to-risk (§5) vs risk-first.** §5's order minimises effort-to-first-value. We chose
risk-first instead: `ShellSkills` — unsandboxed arbitrary command execution, which LangChain4j's own
documentation flags as unsafe — is the highest-severity signal in the whole design, above the Deep
Agents worst case (writable skill files / self-modification). Covering the gravest risk first is the
priority a security scanner is built to serve. This is a deliberate trade of effort for risk
coverage, not a claim that Java is cheaper.

**Scope of the first LangChain4j increment: thin slice vs full §3.6.** A thin slice — detect only
`ShellSkills` / the `langchain4j-experimental-skills-shell` dependency by string and dependency
scanning, with **no tree-sitter** — would deliver the exact risk that motivates going Java-first, in
the cheapest possible increment, and would leave the tree-sitter dependency decision (ADR 0001)
deferred. We rejected it in favour of the full §3.6 Analyzer (tree-sitter over `.java`, every
definition path, `.content(...)` text-block resolution, `@Tool` poisoning, `McpToolProvider`
filtering, `L4J-UNRESOLVED`). The reason: a `ShellSkills`-only report reads as "clean" on a skill
whose instruction surface — the `@Tool` descriptions and `.content(...)` text the model actually
reads — was never examined, which is the failure §3.6 calls out as worse than a finding. The full
Analyzer is accepted as the first increment with that cost visible.

**Discovery of the host code.** The security-relevant LangChain4j configuration lives in the Java
host, not in `SKILL.md` (§1). Shipping the Analyzer without repository discovery would make it fire
only in the degenerate "one giant anonymous skill" mode §3.7 describes. So the Analyzer is paired
with `--repo-scan` (deep `SKILL.md` discovery plus JVM build-directory exclusion) in the same
increment, rather than left to a later phase.

**Input shape: source tree vs built artifact.** In CI the scan target is the checked-out source
tree, where `.java` and `src/main/resources/skills/` are present as source. A `.jar` normally holds
compiled `.class` files, which carry no parseable Java source. `.jar` ingest stays deferred (§8, open
question 1 resolved: source tree only).

**Discovery roots: fixed vs configurable vs inferred.** Fixed conventional path patterns
(`skills/`, `src/main/resources/skills/`, `.deepagents/skills/`, `.agents/skills/`) matched as a
suffix at any depth find monorepo modules without configuration. Inferring roots from `pom.xml` /
`pyproject.toml` locations was rejected as machinery ahead of need. We take the fixed patterns plus a
`--repo-scan-root` override flag as a cheap escape hatch for non-conventional layouts (§8, open
question 2 resolved).

## Consequences

- **tree-sitter is accepted now.** ADR 0001 moves `proposed → accepted`; the dependency it gated is
  scheduled as part of this increment.
- **Deep Agents and spec conformance are deprioritised**, not dropped. They keep their §5 design and
  follow the LangChain4j increment.
- **The behavior gate (§4) still holds.** The Analyzer is gated on `framework == "langchain4j"` and
  returns `{"findings": []}` on every existing input; `--repo-scan` is off by default; the new
  fixture adds a snapshot entry rather than changing one. No pre-existing Behavior Snapshot changes.
- **Two implementation constraints** the increment must honour, recorded so they are not missed:
  the tree-sitter import is guarded inside the Analyzer, never at module top, so an absent dependency
  cannot be swallowed into `{"findings": []}` + a `"failed"` ledger status (the silent-failure trap
  §4 warns of); and the Analyzer reads `file_cache` directly, as detection does, so a large `.java`
  file is not truncated by the `static_runner` `MAX_FILE_CHARS` cap. `file_cache` holds full,
  untruncated source for `"other"`-typed files (`build_context.py:227`), which is why the §3.4
  `_FILE_TYPES` change stays deferred and is not required for the Analyzer to read Java.
- **Reopen trigger.** If the tree-sitter dependency proves unacceptable, the thin `ShellSkills`-only
  slice above remains a valid fallback that still covers the risk driver without it.

Full analysis: `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` §2.2, §3.6, §3.7, §5.
