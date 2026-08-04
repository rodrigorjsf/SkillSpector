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

> **Corrected by the 2026-08-03 re-measurement.** `ClassPathSkillLoader` was not the only change:
> the `tools` builder argument was added in the same release, on `AbstractSkill$BaseBuilder`. The
> measurement above compared **class listings**, and a builder argument added to a class that
> already exists changes no listing — so the claim was not wrong about what it measured, it was
> measuring something narrower than the sentence said. The range itself was confirmed unchanged.
> The same re-measurement found that `toolFilter` has never been published in any release of
> `langchain4j-mcp`; see [the procedure](../VOCABULARY_REMEASUREMENT.md#worked-example-the-2026-08-03-re-measurement).

That measurement was made by reading the published Maven metadata for both artifacts and comparing
the class listings of the first and latest releases, then sweeping every release for the matched
identifiers — not read off documentation. It is recorded in the module as `OBSERVED_VERSION_RANGE`
so the stability claim is evidence rather than assertion, and so a reader can tell how stale it is.

> **Re-measuring it now has both.** `docs/VOCABULARY_REMEASUREMENT.md` is the procedure — what to
> run, what it reads, what output constitutes the new claim — and the trigger that obliges someone
> to re-run it. It covers both Frameworks and is executable as
> `python -m contrib.vocabulary_sweep langchain4j`. That closes issue #46, which this record opened
> by naming the gap.
>
> Issue #46 asked whether that should be a script, a documented manual procedure, or a scheduled
> check. It is **a script plus a written procedure, and deliberately not a scheduled check.** A
> documented manual procedure was rejected for the reason #46 gave against it — it costs nothing and
> is skipped — and because the measurement it replaces was skipped for a year. A scheduled check was
> rejected because a sweep downloads roughly a hundred archives from two public indexes, and CI is
> the wrong place to depend on them being up; the script exits non-zero on a blocking result
> precisely so a schedule can be added later without re-deciding what counts as a failure. The
> network dependency #46 worried about is real, so the tool lives in `contrib/` beside the batch
> scanner, outside `testpaths` and outside the package — a sweep is a maintainer's deliberate act,
> not a per-commit check. Where the result lives is settled the same way: in the vocabulary module,
> so this record stays a decision rather than becoming a changelog.

So the exposure to date is nil. It is not nil going forward: the artifact carrying the
highest-severity Rule is still named `langchain4j-experimental-skills-shell`, and the day it
graduates and drops that prefix, the dependency signal behind `L4J-SHELL` dies without a sound. What
the report should say when that happens, and how to detect that it has, is issue #45. This decision
only makes the rename a one-line edit.

> **Superseded in part by [ADR 0007](0007-l4j-shell-survives-the-graduation-rename.md).** Issue #45
> was decided: `L4J-SHELL`'s dependency half no longer matches `SHELL_ARTIFACT_ID` at all, but a
> pattern over any `langchain4j-` artifact id containing `shell`. The rename is therefore no longer
> a one-line edit the Rule depends on — it is an accuracy update. Everything else in this record
> stands, including the failure shape described above, which still applies to every *other* spelling
> in the inventory.

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
one of the two would leave the other matching nothing in silence.

`signals.py`'s docstring — the one that recorded the decoupling — now says so; `framework.py`
carries the same note at the import itself, where a reader meets the coupling. The consolidation is
therefore not later mistaken for a reversal.

`vocabulary` is import-free and parser-free, which is what makes this safe: detection runs on every
Scan, and the Analyzer decides applicability before reaching for tree-sitter. An import in
`vocabulary` would move tree-sitter to the top of both paths and undo that ordering. Three tests
assert it directly, in a subprocess, with importing a Rule module as the control.

## Consequences

**`repository_scan.py` is a known gap.** `DISCOVERY_ROOTS` names `src/main/resources/skills`
alongside the Agent Skills and Deep Agents layouts, so a LangChain4j layout rename would silently
stop Repository Scan discovering Skills there.

It is not inventoried, and the reason is the literal rather than the dependency direction —
`framework.py` is a three-Framework module too, and it imports from `vocabulary` without trouble.
Repository Scan's entry has **no trailing slash**: it is matched as a path suffix at any depth,
where detection matches `src/main/resources/skills/` as a substring. They are two shapes of one
convention, not one spelling in two files. Consolidating them means either editing a literal —
which this change cannot do, since its entire proof is that no Behavior Snapshot moved — or
inventorying a second spelling for the same convention and explaining why there are two.

The enforcement test's file set therefore stops at the LangChain4j-coupled modules, and the honest
consequence is that adding `repository_scan.py` to it today would **not** flag the existing copy:
the guard matches literals exactly, and the two literals differ. Revisit when the Deep Agents
Analyzer lands and the same question arises for its layout — that is the point at which one
inventory per Framework, and a discovery table composed from all of them, becomes worth the churn.

**The enforcement test catches a spelling written as a literal of its own, not one embedded in a
longer string.** That is the shape a matcher takes, and the shape every leak this change relocated
had. Containment was measured and rejected: the Finding messages in `framework_langchain4j`
legitimately quote type names in prose — *"McpToolProvider is built without a filter or
filterToolNames"* — and
containment cannot tell a quoted name from a matcher. Regex-escaped forms *are* caught, so
recomposing `re.compile(r"dev\.langchain4j")` inline fails the same way the plain spelling does.

**A leak fails the build; a stale identifier still does not.** The guard fires when a spelling is
written inline, which is what keeps the inventory whole. It cannot fire when upstream renames
`ShellSkills` and the inventory still says `ShellSkills` — every test passes, `L4J-SHELL` stops
matching, and the report reads as clean. That is the failure this record opened with, and this
decision does not close it: it reduces the fix to one line and gives a maintainer one file to read
against a release. Detecting that the rename happened is issue #45; re-measuring the stability claim
on a schedule is issue #46. Neither should be read as delivered here.

> **Both have since been delivered, and the second one immediately earned itself.** #45 landed as
> [ADR 0007](0007-l4j-shell-survives-the-graduation-rename.md). #46 landed as
> [the re-measurement procedure](../VOCABULARY_REMEASUREMENT.md), and its first run found exactly the
> failure this paragraph describes, in the inventory this record created: `toolFilter` is a spelling
> no published release has ever declared, so `L4J-MCP-FILTER` reports every builder chain compiled
> against a real release as unfiltered. Nothing in the test suite could have said so — the guard
> here fires on a spelling written in the wrong *place*, never on one that is wrong. Tracked as
> issue #82; correcting it changes what a Scan reports, which the measurement that found it did not.
>
> **Issue #82 has since reversed that.** The inventory no longer holds `toolFilter`. It holds
> `TOOL_FILTER_SETTERS`, the two spellings `McpToolProvider.Builder` actually declares — `filter`
> and `filterToolNames` — and `L4J-MCP-FILTER` reports a chain only when it called neither. The
> deferral above was the right call for a *measurement*, which must not move behavior, and the wrong
> thing to leave standing: the Rule could not be satisfied by any code that compiles. What changed
> is a Rule and its Finding text, so the two LangChain4j Behavior Snapshots changed with it;
> `L4J-WORKDIR`, which shares the unset-setter machinery, did not. `toolFilter` survives in this
> record and in the module's comments as history, and nowhere as a setter to call.

**This change altered no behavior, and that is its proof.** No Rule logic changed, no Rule was added
or removed, no Finding changed. Regenerating the Behavior Snapshot corpus left the working tree
clean, and the 107 existing assertions over the Analyzer node and Framework detection pass without a
single test edit. Any observable change would have been a defect.

**The pattern is meant to be copied.** The Deep Agents Analyzer will match on an upstream vocabulary
with the same beta-era volatility, and this is the shape to reuse rather than reinvent.
