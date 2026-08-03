# Applicability is what the Analyzer opens, and a matching Framework always reports

Status: accepted

The LangChain4j Analyzer's applicability is one predicate — `signals.applicable_files`, the Java
compilation units and JVM build files of a Scan, whether or not a build file declares the shell
module. The second gate tests that result's emptiness and the planned work is derived from the same
result, so the Analyzer cannot open a Component it does not report.

Under that definition a Scan whose Framework is LangChain4j **always reports exactly one Analyzer
Status**. A repository holding a build file gets `completed` with a Work Item for it and no
Findings. A LangChain4j tree the Analyzer opens nothing in — Skills reached through the classpath
layout, or a Kotlin-only import — gets `not_applicable` with `no_applicable_files`, the reason this
codebase already emits wherever an Analyzer finds no file it can open. (The Analyzers that report
`not_applicable` for an *absent Manifest* use `manifest_absent`; that is a different shape and keeps
its own reason.)

The Framework gate is untouched. A Scan of another Framework stays byte-for-byte unchanged by this
Analyzer's existence, which is [ADR 0002](0002-gated-analyzers-decline-silently.md)'s decision and
remains correct.

## Why this needed a decision at all

The Analyzer held two definitions of "applicable", eight lines apart, and they disagreed. The gate
asked whether there was Java **or a build file that already declared the shell module**; the
planned-work construction asked whether there was Java **or any JVM build file**. They differ on
exactly one shape — a build file with no shell declaration — which is the shape of
`tests/fixtures/langchain4j_detection`, the one committed fixture that reached the gate.

So the same Component was accounted for in one Scan and invisible in another, and what decided the
difference was whether some *other* Component had produced a Finding. On the fixture the gate closed
and the Scan emitted no Finding, no Work Item and no status at all — a reader could not tell whether
the Analyzer ran and approved the repository or never engaged with it. That is exactly the confusion
the Inspection Ledger exists to eliminate, occurring on the one input it was built to disambiguate.

## The build file really is opened

This is the fact the decision rests on, so it is stated rather than assumed. `L4J-SHELL` fires on a
build file alone: `signals.shell_artifact_declaration_lines` blanks each build file's comments —
XML for Maven, block and line for Gradle — and scans every remaining line for the shell artifact id,
reporting the first live declaration. A build file that names the artifact only inside a comment is
correctly *not* a declaration.

On `tests/fixtures/langchain4j_detection` that read happens and finds nothing. `completed` with a
Work Item for `pom.xml` and no Findings says what the Analyzer did: *we opened your build file and
there was nothing in it*. A file that was read is a file that was inspected, whatever the reason the
gate happened to be written in.

## Considered Options

**Emit `not_applicable` for the bare build file too** — the shape issue #38's original body
recommended, and the one that keeps the gate's old wording. Rejected because it records a false
reason about a Component that *was* opened. `no_applicable_files` means "no files matched this
analyzer's applicability contract"; a build file the Analyzer read line by line, looking for the
identifier behind its highest-severity Rule, matched that contract. Reporting otherwise would make
the Ledger's most load-bearing reason code the one place the Ledger lies.

**Leave the silence and document it** — no code change, a note in the design document explaining
that the second gate declines. Rejected because the Deep Agents Framework Analyzer is the next
increment and would copy the pattern into Python trees before anyone re-read the note. A documented
defect in the one Analyzer that has the shape is a defect in every Analyzer that inherits it. It was
also already documented, in that design document and in a comment block in the node, and the
documentation is what this record replaces.

## Consequences

**[ADR 0002](0002-gated-analyzers-decline-silently.md)'s third option closes here.** That record
deferred rather than rejected "decline silently on the wrong Framework, but emit `not_applicable`
when the Framework matches and there was still nothing applicable". It closes to something narrower
than it was framed as: the case it described as needing `not_applicable` turned out to be two cases,
and only the one where nothing is opened gets that status. The other gets `completed`. ADR 0002's
own decision — silence on a Framework mismatch — is untouched and stays accepted.

**The Deep Agents Framework Analyzer inherits this, and the answer is decided rather than left
open.** A matching Framework with nothing applicable reports `not_applicable`; a matching Framework
that opens something reports `completed`, even when nothing was found; only a Framework mismatch is
silent. Applicability there is likewise one predicate over the Components that Analyzer opens —
Python sources and Python requirement files — with the gate and the accounting derived from it. The
pattern is meant to be copied, not re-decided.

> **The predicate named in that last sentence is revised by
> [ADR 0008](0008-deepagents-analyzer-resolves-one-module-deep.md).** Scoping duplicate-name
> shadowing into that Analyzer means it opens each source directory's `SKILL.md` to read the `name`,
> so its Applicability is Python sources, Python requirement files **and every `SKILL.md` in the
> Scan**. That widening is forced by *this* record — a Component the Analyzer opens is a Component it
> reports — so the decision here stands unchanged; only the file set anticipated for Deep Agents
> was written before the Rule that widens it.

**The behavioral cost was measured, and it is one status row.** Regenerating the corpus changed
exactly one snapshot: `tests/behavior/snapshots/langchain4j_detection.json` gained a
`framework_langchain4j` row reading `completed` with `planned_work: 1`. Every other snapshot stayed
byte-identical, `langchain4j_shell_skill` included — its applicable set is the same five files under
both definitions. That fixture's `is_complete` (`false`, from three semantic Analyzers disabled
without credentials), `execution_successful` (`true`) and `coverage_percent` (`100.0`) are unchanged,
and `test_langchain4j_detection_reports_its_analyzer_and_costs_only_that_row` asserts all three
rather than leaving them to inspection.

**A `not_applicable` status does not make a Scan incomplete.** The completeness projection treats
`completed` and `not_applicable` as non-limiting and turns every other status into a stated
limitation (`src/skillspector/inspection_ledger.py:744`). That is relied upon here, so it is
asserted through the projection rather than assumed from the reason code.

**No committed fixture reaches the `not_applicable` branch.** Once applicability is what the
Analyzer opens, a LangChain4j tree with neither Java nor a build file is an unusual shape, and
manufacturing a fixture for it would cost a second corpus entry and another round of prose-count
edits for a branch that is one status with no logic. It is proved by unit test, and the CLI was
driven once over a throwaway tree of that shape — Skills under `src/main/resources/skills/`, no
`.java`, no build file — with the output read: one `not_applicable` row carrying
`no_applicable_files`, no ledger event, no Findings, and no new limitation.

**The two predicates stay two.** Detection asks "is this tree LangChain4j at all" and applicability
asks "which of its files do I open"; they remain separate functions in separate modules, for the
reason `skillspector.langchain4j.signals` records. What this decision unifies is the *second*
question with itself, not the second with the first.
