# The Deep Agents Analyzer resolves one module deep, judges writability once, and opens every `SKILL.md`

Status: accepted

The `framework_deepagents` Analyzer — phase 2 of `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md`, tracked as
issue #58 — reads host-side configuration in `create_deep_agent(...)`. Three things about its shape
were settled before any of it was written, because each of them is expensive to change once Findings
and ledger rows exist in committed snapshots: **how far it resolves a value before reporting a
boundary, how many Findings the absence of a write restriction produces, and which Components its
Applicability opens.**

This record was written as the input to the Spec that would implement it. Issue #70 has since landed
the Analyzer itself — the gate, the Applicability predicate of §3, the status reporting and the
vocabulary module — carrying no Rule at all. The Rules of §1 and §2 are issues #71–#74, and the
stability measurement named under Consequences is #75.

One thing #70 measured that this record did not anticipate: with the Applicability set of §3, the
Analyzer's `not_applicable` branch is **unreachable through the graph**. Every signal
`skillspector.framework` detects Deep Agents by is a Python module or a Python requirement file, and
both are inside the predicate, read from the `file_cache` that `build_context` derived `framework`
from in the same return. The branch is kept — ADR 0006 makes it the shape of an Applicability gate
rather than an observed case — and is exercised from synthetic state.

## What is being judged, and why a token match is wrong

Upstream states the default in as many words: *"By default, agents can write to skill files if the
backend permits it and no permission rule blocks the path"*
(`docs/references/langchain-deepagents-skills.md:294-295`). So the question "can this agent rewrite
its own instructions?" is a joint verdict over three keyword arguments — `skills=[...]`,
`permissions=[FilesystemPermission(operations, paths, mode)]` and `backend=`, which decides whether
the path is writable at all — evaluated with rule order as semantics: *"Place more specific rules
before broader deny rules"* (`:296`).

A Rule that tests for the presence of the token `permissions=` is therefore wrong in both
directions. It fires on a read-only backend, and it stays silent on a broad `deny` that a more
specific earlier rule has already overridden.

## 1. Resolution stops at the module boundary

The Analyzer resolves a literal, and a constant declared in the same module. Anything else is not
resolved and is not guessed: it produces a boundary Finding, the Deep Agents analogue of
`L4J-UNRESOLVED`.

This is the LangChain4j rule, not a new one. `skill_definitions.py:181-212` resolves same-unit
`String` constants and returns `None` for everything else, with a docstring citing §3.6: *"following
it anywhere else is the arbitrary dataflow that is out of scope."* Copying it keeps §3.6 as one line
in the project rather than one line per Framework.

Two cases fall on the boundary side, and both are documented upstream patterns rather than
pathologies:

- **A skill list assembled at runtime.** `SKILLS_BY_ROLE.get(user_role, [])` (`:179-190`) — the skill
  sources exist in no scanned file, so the Scan cannot say what the agent was given.
- **A resolvable path whose writability still is not knowable.** `CompositeBackend` may route a
  literal prefix to `StoreBackend(namespace=lambda rt: ...)` (`:208-223`). The *path* resolves; the
  verdict does not. This case must reach the boundary too, rather than being treated as resolved
  because the route key was a string.

**Rejected: resolving `backend=` across modules.** It is real interprocedural dataflow, it is what
§3.6 declined for Java, and the failure it prevents — a wrong verdict — is already prevented more
cheaply by reporting the boundary.

**Rejected: literal-only, no constant folding.** Stricter than the Java track for no stated reason,
and it puts the upstream documentation's own most common shape — a module-level dict or list above
the call — on the boundary rather than under a verdict.

## 2. One composed Rule, one Finding per Skill source path

The issue named three candidate Rules over absences: no `permissions`, no `deny` covering a
`/skills/**` path that is also passed in `skills`, and no `interrupt_on` on `write_file` /
`edit_file`. They collapse to one.

The first two are the same predicate — *for each resolved Skill source path, is there a rule denying
write to it?* — split by whether `permissions` happens to be absent entirely or merely silent about
that path. Shipped separately, an application with no `permissions` matches both and receives two
Findings for one configuration. That is a duplicate, not a budget question.

The third is a mitigation of the same verdict rather than a parallel one. `interrupt_on` and
`mode="interrupt"` put a human in front of the write; where they are present they lower the
severity, and they never produce a Finding of their own.

So: one Rule, emitting **one Finding per resolved Skill source path** that is neither denied write
nor made read-only by its backend. Per path rather than per application, so a reviewer who
deliberately accepts a writable `/skills/personal/` can baseline exactly that and keep the verdict on
a shared library.

**Why the false-positive budget needed deciding at all.** Unlike `L4J-MCP-FILTER` and `L4J-WORKDIR` —
absence Rules that shipped independently at MEDIUM with confidence 0.9
(`nodes/analyzers/framework_langchain4j.py:107-116`) — this Rule fires on the framework's
**documented default**. An unfiltered `McpToolProvider` is a choice a developer made; a Deep Agents
application without `permissions` is the path the tutorial teaches. Three independent absence Rules
would put two or three MEDIUM Findings on nearly every Deep Agents application in existence.

**Rejected: one Finding per application.** Cheaper report, but Baseline granularity collapses — the
personal-skills case and the shared-library case are suppressed together.

## 3. Applicability opens every `SKILL.md`, and therefore reports every `SKILL.md`

`skills=["/skills/shared/", "/skills/personal/"]` is a supply-chain substitution primitive only when
two sources contain a Skill with the same `name` — *"Later sources override earlier ones for skills
with the same name (last one wins)"* (`:80-82`). That `name` lives in the frontmatter of each source
directory's `SKILL.md`, so confirming the shadowing means opening Components that are not Python.

[ADR 0006](0006-langchain4j-applicability-is-what-it-opens.md) then decides the rest, and it is not
optional: one named predicate, the gate tests its result for emptiness, the planned work derives from
the same result, so *a Component the Analyzer opens is always a Component it reports*. There is no
version of this where the Analyzer peeks at a `SKILL.md` without giving it a ledger row.

Applicability is therefore **Python sources, Python requirement files, and every `SKILL.md` in the
Scan** — one predicate, still pure over `file_cache`.

This **revises the forward-looking paragraph in ADR 0006**, which anticipated "Python sources and
Python requirement files" for this Analyzer. That sentence was written before the shadowing Rule was
scoped into it. ADR 0006's actual decision — one predicate, gate and accounting derived from it — is
what forces the wider set, so the revision follows the record rather than departing from it.

**A second boundary lives here.** Paths in `skills=[...]` are relative to the backend root, not to
the Scan root (`:80-81`). Mapping `/skills/` to a directory on disk requires a resolvable
`FilesystemBackend(root_dir=...)`; under `StoreBackend` or the default `StateBackend` the files are
not on disk at all and no Scan will ever see them. Those fall to the boundary of §1.

**State the cost rather than let a reader discover it in a snapshot.** On a Scan where the mapping
fails for *every* path — the default `StateBackend` being the likeliest case — the Analyzer has
opened every `SKILL.md` in the tree, given each one a Work Item, and produced no shadowing verdict
from any of them. The snapshot reads `completed`, with ledger rows for files that were read only to
fail to be usable. That is correct under ADR 0006 and it is the price of the wider predicate: the
alternative is opening those files without reporting them, which that record forbids.

**Rejected: leaving shadowing to a repository-level pass** near `multi_skill.detect_skills`, which is
where the captured reference points (`:372-374`). It would ship #58 without the Rule that most
justifies it, and the cross-source reasoning it needs is available in one `file_cache` today.

**Rejected: inferring shadowing from the configuration alone** — flagging any `skills=[...]` with
more than one source, without confirming names. That fires on deliberate layering, which is the
pattern upstream documents (`:196-204`).

**Only one of the issue's two "cross-source" Rules actually crosses.** Subagent skill inheritance —
*"Custom subagents do not inherit the main agent's skills"* (`:228-231`) — is decidable in the
configuration alone, in the same file. It forces nothing here.

## Consequences

**The vocabulary module is copied from [ADR 0005](0005-langchain4j-upstream-vocabulary.md); the
stability measurement is not.** The decisions above already oblige matching twenty-one upstream
spellings — `create_deep_agent`, `skills`, `permissions`, `backend`, `interrupt_on`, `subagents`,
`FilesystemPermission`, `operations`, `paths`, `mode`, the values `"deny"` / `"interrupt"` /
`"write"`, `write_file`, `edit_file`, `FilesystemBackend`, `StoreBackend`, `StateBackend`,
`CompositeBackend`, `root_dir`, `routes` — the same order of magnitude as the twenty ADR 0005
collected for Java, and with the same silent failure on a rename. They get one module and an
enforcement test.

What is *not* copied is ADR 0005's second half. That record measured rather than asserted: seventeen
Maven releases swept, no matched identifier ever removed, recorded in `OBSERVED_VERSION_RANGE` "so
the stability claim is evidence rather than assertion". No such measurement exists for Deep Agents —
only a version floor quoted in the capture, `deepagents>=0.6.8` for filesystem-permission interrupts
(`:288`). The measurement is a Ticket of its own inside this work, and that Ticket defines the
*procedure* and applies it to both Frameworks, which closes issue #46 rather than duplicating it.

**The code lives in `src/skillspector/deepagents/`, mirroring `langchain4j/`.** Not for size —
`langchain4j/` is seven modules largely because `java_parser.py` isolates a native dependency that
Deep Agents does not have — but because the vocabulary enforcement test needs a boundary to sweep,
and because the `create_deep_agent` resolver and the `SKILL.md` name reader parse *different
languages*. Folding the spellings into `framework.py` was rejected outright: detection and Rules
would then share an inventory, and one upstream rename would move both at once.

**This Analyzer calls `analyzer_status_for_events`, it does not write the cascade.** Unlike
`framework_langchain4j`, whose events are all `COMPLETED`, this one can emit `SKIPPED` — an
unparseable Python file, for which `behavioral_ast.py:270-279` already fixed the shape
(`LedgerOutcome.SKIPPED` with `LedgerReason.SYNTAX_ERROR`). `DEGRADED` is reserved to the ledger; see
`.claude/rules/analyzer-status.md`.

**Issue #48 closes with no glossary term, and this is the record of why.** #48 was held open waiting
for a second Framework to generalise from. With this shape settled, the two axes turn out to be
orthogonal rather than two instances of one concept. LangChain4j's Tool mode / Shell mode axis varies
**how the model reaches Skill content and what that lets it execute**. Deep Agents does not vary
that at all — `SkillsMiddleware` always reads `SKILL.md` through `read_file` at level 2 of
progressive disclosure (`:99-108`) — it varies **mutability**: whether the agent can rewrite the
Skill. Read-and-execute on one side, write on the other. A cross-Framework term generalised from the
Java axis would describe the Python one badly, which is the risk #48 named when it declined to invent
one from a single data point. Nothing is added to `CONTEXT.md`.

That closure has a plausible reopening that has nothing to do with Deep Agents: issue #49 asks
whether the Agent Skills specification itself defines this axis as *tool-based* versus
*filesystem-based agents*. If it does, it is specification-level vocabulary and belongs in the
glossary regardless of how many Frameworks implement it.

**Issue #47 no longer constrains the ordering.** It has landed — `framework_langchain4j.py:78-86`
imports `AnalyzerStatus` from `inspection_ledger` — so this Analyzer is written against a declared
status value set from its first line.
