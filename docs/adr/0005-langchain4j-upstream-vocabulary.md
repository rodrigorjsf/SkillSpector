# One module owns every LangChain4j spelling

Status: accepted

Every upstream spelling the LangChain4j Analyzer matches on — type names, method names, builder
argument names, the Maven group id and artifact id, the conventional Skill layout — lives in
`src/skillspector/langchain4j/vocabulary.py` and nowhere else.
`tests/unit/test_langchain4j_vocabulary.py` fails the build when one is written inline in any other
module, so the single home is enforced rather than conventional.

## Why this needed a decision at all

LangChain4j's Skills API is published as beta. Upstream's own documentation, captured in
`docs/references/langchain4j-skills.md`, says *"The Skills API is experimental. APIs and behavior
may still change in future releases."* The names below are therefore expected to move, and moving
them is not a hypothetical the way an upstream rename usually is.

The failure a rename causes is the worst kind this project has. A Rule whose identifier no longer
matches simply stops producing Findings. The Scan still succeeds, the Analyzer still reports itself
as `completed`, every file it opened still gets a ledger row, and the report reads as clean. An
absence of Findings caused by a stale identifier is indistinguishable from a genuinely clean Scan —
which is precisely the confusion the Inspection Ledger exists to prevent, one layer above where the
Ledger operates. The Ledger can say *this file was inspected*; it cannot say *the Rule that
inspected it still recognises anything*.

Before this decision the twenty spellings were spread across six modules in two packages, about half
declared as private constants, with no inventory, no citation of where each came from, and no record
of which upstream versions each was observed in.

## What bounds the risk

Every published release of `dev.langchain4j:langchain4j-skills` was checked — 17 versions,
`1.12.1-beta21` through `1.18.1-beta28`, released in lockstep with
`langchain4j-experimental-skills-shell`. Across that entire history **no identifier the Analyzer
matches has ever been removed**. The only change is `ClassPathSkillLoader`, added at
`1.13.0-beta23`.

That measurement was made by reading the published Maven metadata for both artifacts and comparing
the class listings of the first and latest releases, then sweeping every release for the matched
identifiers — not read off documentation. It is recorded in the module as `OBSERVED_VERSION_RANGE`
so the stability claim is evidence rather than assertion, and so a reader can tell how stale it is.
Re-measuring it has no procedure and no trigger; that gap is issue #46.

So the exposure to date is nil. It is not nil going forward: the artifact carrying the
highest-severity Rule is still named `langchain4j-experimental-skills-shell`, and the day it
graduates and drops that prefix, the dependency signal behind `L4J-SHELL` dies without a sound. What
the report should say when that happens, and how to detect that it has, is issue #45. This decision
only makes the rename a one-line edit.

## Considered Options

**Per-version API profiles** — a spelling table per upstream version, selected by the version found
in the scanned build file. Rejected as machinery ahead of need. Nothing has been removed in
seventeen releases, so the profiles would all be identical, and the cost is not just the tables: the
Analyzer would have to resolve a dependency version out of Maven or Gradle syntax before it could
choose one, which is a parsing problem this project deliberately does not have. Reopen if a release
ever removes an identifier rather than adding one.

**An inventory that documents the spellings without moving them** — a table in
`docs/references/langchain4j-skills.md` listing each spelling and the module holding it. Rejected
because it tells a maintainer which six files to edit rather than reducing them to one, and because
a document cannot fail a build. It would go stale on the first change that did not think to update
it, and its staleness would itself be silent.

## What is deliberately not in the inventory

Conventions that change on a different clock stay where they are: Maven and Gradle build file names,
the Java source suffix, the generic `builder()` / `toBuilder()` entry methods, and the bare Maven
resource root `src/main/resources/`. None of them is LangChain4j knowledge. The one hybrid — the
conventional Skill layout `src/main/resources/skills/` — *is* inventoried, because the `skills/`
segment is LangChain4j's convention even though the prefix is Maven's.

The inventory covers what the Analyzer matches, not what LangChain4j exposes. Tool mode wiring
types, the activate-skill and read-resource tool configurations, and the available-skills formatting
helper are real upstream surface that no Rule reads today, and they stay out until a Rule needs them.

One spelling was inventoried beyond the enumeration in issue #44: the `.tools(...)` builder
argument, matched by `skill_definitions.find_attached_tools`. It is an upstream builder argument in
exactly the same class as the text setters, and leaving it out would have meant the enforcement test
carrying a documented exemption inside a module whose whole point is completeness.

## Framework detection reads the same inventory

`skillspector.framework` composes its LangChain4j signals from `vocabulary` rather than spelling the
group coordinate, the import prefix and the Skill layout itself.

This does not reopen the deliberate decoupling between detection and Analyzer applicability recorded
in `skillspector.langchain4j.signals`. What that decision defends is the duplication of the
*predicates* — "is this tree LangChain4j at all" versus "which of its files do I open" — and those
stay separate. The spelling of a package name is one fact, not two, and a rename that reached only
one of the two would leave the other matching nothing in silence. Both module docstrings now say so
explicitly, so the consolidation is not later mistaken for a reversal.

`vocabulary` is import-free and parser-free, which is what makes this safe: detection runs on every
Scan, and the Analyzer decides applicability before reaching for tree-sitter. An import in
`vocabulary` would move tree-sitter to the top of both paths and undo that ordering. Three tests
assert it directly, in a subprocess, with importing a Rule module as the control.

## Consequences

**`repository_scan.py` is a known gap.** `DISCOVERY_ROOTS` names `src/main/resources/skills`
alongside the Agent Skills and Deep Agents layouts, so a LangChain4j layout rename would silently
stop Repository Scan discovering Skills there. It is not inventoried and not guarded, because it
sits in a three-Framework table where coupling one row to a LangChain4j module would invert the
dependency and give a cross-cutting module a Framework-specific import. The enforcement test's file
set therefore stops at the LangChain4j-coupled modules. Revisit when the Deep Agents Analyzer lands
and the same question arises for its layout.

**The enforcement test catches a spelling written as a literal of its own, not one embedded in a
longer string.** That is the shape a matcher takes, and the shape every leak this change relocated
had. Containment was measured and rejected: the Finding messages in `framework_langchain4j`
legitimately quote type names in prose — *"McpToolProvider is built without a toolFilter"* — and
containment cannot tell a quoted name from a matcher. Regex-escaped forms *are* caught, so
recomposing `re.compile(r"dev\.langchain4j")` inline fails the same way the plain spelling does.

**This change altered no behavior, and that is its proof.** No Rule logic changed, no Rule was added
or removed, no Finding changed. Regenerating the Behavior Snapshot corpus left the working tree
clean, and the 107 existing assertions over the Analyzer node and Framework detection pass without a
single test edit. Any observable change would have been a defect.

**The pattern is meant to be copied.** The Deep Agents Analyzer will match on an upstream vocabulary
with the same beta-era volatility, and this is the shape to reuse rather than reinvent.
