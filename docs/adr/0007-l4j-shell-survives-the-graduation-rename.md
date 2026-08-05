# `L4J-SHELL` matches the capability word, not the published artifact id

Status: accepted

The dependency half of `L4J-SHELL` matches `SHELL_ARTIFACT_PATTERN` —
`langchain4j-[a-z0-9-]*shell[a-z0-9-]*`, any `langchain4j-` artifact id whose own name contains
`shell` — rather than the literal `langchain4j-experimental-skills-shell`. The Finding names the
spelling the scanned build file used.

Nothing new is reported when a Rule stops matching because an identifier moved. That is a decision,
recorded below, not an omission.

## Why this needed a decision at all

`L4J-SHELL` is the highest-severity Rule in the Java track: LangChain4j's shell mode runs commands
in the host process with no sandboxing, containerization or privilege restriction, which upstream
documents as unsafe. Half its signal is the Maven artifact id.

That artifact is named *experimental*. The day it graduates and drops the prefix, a literal match
stops firing — and nothing says so. The Framework still detects, the Analyzer still opens the build
file, the Scan still reports `completed`, every opened Component still gets a ledger row, and the
report reads clean on a repository that just put an unsandboxed shell tool on its classpath. This is
the failure shape [ADR 0005](0005-langchain4j-upstream-vocabulary.md) opened with, except it happens
*inside* an open gate with a Work Item recorded, so the Inspection Ledger cannot catch it either:
the Ledger can say *this file was inspected*, never *the Rule that inspected it still recognises
anything*.

ADR 0005 reduced the fix to a one-line edit. It deliberately did not decide what the Rule should
match, or what the report should say. That is this record.

## What was measured

The rename has not happened. `dev.langchain4j:langchain4j-experimental-skills-shell` still publishes
under that name, latest `1.18.1-beta28`, `lastUpdated` 2026-07-29, read from
`repo1.maven.org/maven2/dev/langchain4j/langchain4j-experimental-skills-shell/maven-metadata.xml`.
So this is a forward risk, not a present defect.

**The graduated spelling cannot be derived.** Every `experimental`-named artifact under
`dev.langchain4j` — `langchain4j-experimental-hibernate`, `langchain4j-experimental-skills-shell`,
`langchain4j-experimental-sql` — still carries the prefix, and none has a graduated counterpart that
replaced it. `langchain4j-hibernate` exists, but it is a *different module published alongside* the
experimental one rather than its successor: it starts at `1.12.1-beta21` and the experimental one at
`1.13.0-beta23`, so the experimental artifact appeared **after** the unprefixed one, and both are
still publishing at the current `1.18.1-beta28`. A rename would have retired one of them.
`langchain4j-sql` does not exist at all. `langchain4j-agentic` exists and
`langchain4j-experimental-agentic` never did, so it is not a rename either.

The group id has therefore never renamed an artifact out of `experimental`. There is no observed
shape to copy, which means any specific graduated spelling is a guess.

**The failure was reproduced before it was fixed.** A throwaway Maven project declaring
`dev.langchain4j:langchain4j-skills` and `dev.langchain4j:langchain4j-skills-shell`, with a Java
Skill definition and a `SKILL.md` under the classpath layout, scans clean of `L4J-SHELL` under the
literal match — zero Findings on a repository that just put an unsandboxed shell tool on its
classpath, with the Analyzer reporting `completed` throughout. The same tree under the shipped
pattern yields one HIGH Finding at the `langchain4j-skills-shell` line and none at the
`langchain4j-skills` line.

## The decision, and the option it displaced

Issue #45 proposed *"a pattern covering both the experimental and graduated spellings"* — an
enumeration: `langchain4j-experimental-skills-shell` plus `langchain4j-skills-shell`. That was the
option this record set out to accept, and the measurement above is why it did not.

An enumeration is only as good as the guess inside it. `langchain4j-skills-shell` is what the word
"graduation" implies textually, not what upstream has demonstrated, and if the release picks
`langchain4j-shell` or `langchain4j-skills-shell-api` the enumeration fails **exactly the way the
literal it replaced fails**: silently, on the highest-severity Rule, with a clean report. Paying the
cost of matching a nonexistent artifact and still keeping the failure mode is the worst of both.

Matching the capability word needs no guess. The invariant across every plausible rename is that a
LangChain4j artifact providing shell execution has `shell` in its name; that is what the artifact is
*for*. The pattern is confined to one hyphenated token beginning `langchain4j-`, because the
character class is the artifact-id alphabet — so the match cannot span from a group id on one part
of a line to an unrelated word later on it.

**The over-match is real, and it points the right way.** Two kinds of it, measured rather than
assumed.

*A future artifact.* `langchain4j-something-shell` fires `L4J-SHELL` at HIGH before anyone has
assessed it. For a security scanner that is the conservative direction, and the Finding names the
artifact it actually read, so a reader sees it is not the module the Rule was written for and
judges.

*A project named after shell mode.* This one is new with the widening and was not obvious. The
pattern matches an artifact id wherever it appears on a live line, so a build file whose **own**
`<artifactId>`, `<module>`, `<name>` or `<url>` contains `langchain4j-…shell…` — a demo repository,
an aggregator listing the module, a fork — now fires HIGH without depending on anything. The literal
did not, because no project is called `langchain4j-experimental-skills-shell`.

Accepted rather than fixed. Separating "this element declares a dependency" from "this element names
the project" means reading Maven's element names and Gradle's coordinate syntax separately, which is
the per-format structure `signals` avoids on purpose and which would add new ways to *miss* a real
declaration. Missing one is the failure this record exists to prevent; over-reporting a repository
whose own name says shell mode is noise a reader resolves by reading the Finding, which names the id
it matched. `TestWhatTheWideningAlsoMatches` pins all four cases so the behaviour is a decision, with
prose naming the capability as the control that bounds the claim — the pattern takes an artifact id,
not the word "shell".

**The one over-match that would matter is excluded by construction.** `langchain4j-skills`, the safe
sibling, is in every build file that uses the Skills API at all, and its id is a prefix of the shell
module's. A pattern loose enough to take it would fire HIGH on every clean LangChain4j Scan and make
the Rule useless. It cannot satisfy this one: "skills" does not contain "shell". A test asserts it
directly, with `langchain4j` alone as the control.

**A pre-existing inversion this work surfaced and did not cause.** A pom that *excludes* the shell
module — `<exclusion>` under a `langchain4j-skills` dependency, or a Maven Enforcer `<exclude>` —
is flagged HIGH for the one action that removes the risk. `shell_artifact_declarations` already
blanks comments so a build file naming the artifact only to say it was removed is not read as
declaring it; an `<exclusion>` says the same thing in XML rather than in a comment, and is not
blanked. Measured against the literal match this pattern replaced: it reports the exclusion
identically, so the widening neither caused nor worsened it. Left as a strict `xfail` naming the
desired behaviour, so the suite carries the defect rather than the repository forgetting it, and
filed as issue #64.

**Fixed for Maven, by issue #64.** `shell_artifact_declarations` now blanks two subtrees alongside
the comments it already blanked: a dependency's `<exclusions>` and Enforcer's
`<bannedDependencies>`. The strict `xfail` above is gone and the test asserts the behaviour directly.
The patterns are *tempered twice*, and the second temper is the one that matters. A plain
`<exclusions>.*?</exclusions>` pairs an unclosed opening tag with the next close anywhere later in
the file and blanks every declaration between them — trading this false positive for the false
negative issue #45 existed to fix. Refusing to cross a second `<exclusions` opening is not enough on
its own: when nothing re-opens the tag, the stray close still pairs. So the region also refuses to
cross `</dependency>`, the element an `<exclusions>` subtree always lives inside — and
`</rules>` for `<bannedDependencies>`. Measured on the malformed pom the test drives: the shipped
pattern reports the declaration at its line, while both the naive and the opening-only-tempered
patterns report nothing.

What survives both tempers is an unclosed tag and an orphan close inside *one* `<dependency>`, with a
declaration between them. A textual scan cannot tell that apart from a well-formed subtree containing
the same line, and neither can a reader; it is accepted rather than fixed.

**Fixed for Gradle, by issue #68.** Gradle says the same Refusal as an `exclude` call rather than as
a subtree, and says it in ten spellings — two DSLs, an optional group, named or positional
arguments, wrapped across lines or not, plus Shadow's `exclude(dependency(…))`. Issue #88's survey of
262 real build files observed eight of them; the two wrapped forms are predicted rather than
observed, measured against this function rather than found in the population. One recognizer
collapses all of them because it is anchored to the *call and its argument list*, not to the
arguments it was given and not to the line holding it. The line would be the wrong anchor: in Gradle
a real declaration and an exclusion of something else fit on one line, a shape Maven cannot produce,
and a line-anchored suppression turns it into a false negative.

The recognizer is context-free — any `exclude` in a `build.gradle*`, with no tracking of the closure
around it. That buys `configurations.all` at no cost and also blanks Gradle's file-filter `exclude`,
which is harmless unless such a call's own arguments name a shell coordinate. Requiring a dependency
closure would take the brace-nesting this module exists without.

It carries the same temper as the Maven side, spelled for parentheses: a parenthesised argument list
may cross neither `{` nor `}`, which no legitimate `exclude` argument contains, so an unclosed
`exclude(` inside a closure stops at that closure's brace rather than pairing with a `)` further down
the file and blanking a real declaration between them. Measured on the malformed build file the test
drives: the shipped pattern reports the declaration at its line, while the untempered one reports
nothing.

And it keeps a residual hole, the way the Maven patterns do. An unclosed `exclude(` and an orphan `)`
with *no* brace between them still pair, and a Groovy `exclude` line whose trailing comma is followed
by a declaration rather than by the rest of its own argument list still eats it. Both need malformed
or unformattable input, and closing either needs brace-nesting — so, like the Maven residue above,
they are accepted rather than fixed. Issue #91 carries the analysis and the options.

## What the report says when a Rule stops matching

Nothing, and deliberately.

Issue #45 asked what a Scan should report when the Framework matched, Components were opened, and no
Rule fired because an identifier moved. Today that is indistinguishable from a genuinely clean Scan.
It stays that way.

A scanner cannot know what it failed to recognise. The only thing it could emit without that
knowledge is a blanket note — *this Analyzer's vocabulary may be stale* — on every clean LangChain4j
Scan. That fires on every clean Scan by definition, which makes it noise, and noise on every clean
result trains a reader to skip the line that would have mattered. It is the opposite of what the
Inspection Ledger does: the Ledger earns its place by making a *specific* absence explainable, one
Component at a time.

What the Scan already says is the honest maximum: the Analyzer reports `completed`, and every
Component it opened carries a ledger row. A reader can see the build file was read. Whether the Rule
that read it still recognises anything is a property of the Analyzer's vocabulary against upstream,
not of the repository being scanned, and it is measurable only out of band. That measurement is
issue #46.

### The option considered and rejected here

**Report when the scanned repository's LangChain4j version is outside `OBSERVED_VERSION_RANGE`.**
This is the one signal that is specific rather than blanket: it fires only on a repository newer
than the sweep the inventory was measured against, and it says something true — *SkillSpector's
identifier inventory was never checked against the release this build file declares*.

Rejected because it requires the Analyzer to resolve a dependency version out of Maven or Gradle
syntax, which is the parsing problem ADR 0005 refused when it rejected per-version API profiles.
Buying the same machinery for a weaker payoff would reverse that decision by the back door.
`OBSERVED_VERSION_RANGE` stays what it is — a staleness marker a *maintainer* reads — and comparing
it against upstream belongs to #46's re-measurement, where it costs no parser.

## How anyone learns the rename happened

Nothing in this repository watches upstream, and this decision does not change that. The pattern
buys time rather than notice: it keeps the Rule alive across the transition so that *not* noticing
promptly stops being a security regression.

Detection remains issue #46 — the LangChain4j version-stability measurement has no re-measurement
procedure and no trigger. This record narrows what #46 has to catch, because a graduation rename is
no longer the case that silently breaks a Rule; it is now a case where a maintainer wants to update
`SHELL_ARTIFACT_ID` for accuracy.

> **#46 closed.** [`docs/VOCABULARY_REMEASUREMENT.md`](../VOCABULARY_REMEASUREMENT.md) is the
> procedure and the trigger, and `python -m contrib.vocabulary_sweep langchain4j` is what runs it.
> The shell artifact's id is swept as a published coordinate, so the graduation this record
> describes shows up as that spelling ceasing to be served — the accuracy update a maintainer wants,
> arriving as an output line rather than as a thing nobody watches. As of 2026-08-03 it has not
> happened: the artifact is still published under its `experimental` name across all 17 releases.

## Consequences

**`SHELL_ARTIFACT_ID` is no longer what the Rule matches.** It stays inventoried as the only
spelling ever published, because it is what a build file says today and because the tests that prove
the pattern still recognises the real artifact need a name for it. A reader who assumes the Rule
matches it will be wrong; the constant's comment says so.

**The Finding message is now built rather than constant.** `shell_artifact_declarations` returns the
matched spelling alongside the line, and `_declaration_message` interpolates it. This is what keeps
the change behaviour-preserving: on the published spelling the message is byte-identical to the one
`_DECLARATION_MESSAGE` produced, so no Behavior Snapshot moved. A test asserts the historical
sentence literally rather than deriving it, so a future edit that keeps the helper self-consistent
still fails.

**A fixture guard had to widen with the Rule.** `TestTheToolModeFixtureCarriesNoShellSpelling`
asserted three literals were absent from the Tool mode fixture. Since the Rule now matches a
pattern, absent literals no longer imply a silent Rule, so the guard checks the pattern too.

**Gradle version catalogs are still not read, and the gap has two halves.**
`signals.shell_artifact_declarations` explains its textual match by noting a catalog declares the
coordinate as TOML — but `is_jvm_build_file` matches only `pom.xml` and `build.gradle*`, so
`gradle/libs.versions.toml` is never opened. Worse, the *opened* file cannot help either: a
`build.gradle.kts` using the catalog writes `implementation(libs.langchain4j.skills.shell)`, which
carries no `langchain4j-` token at all and cannot match any artifact-id pattern. A project on a
version catalog is missed by the dependency half however wide the pattern gets. Pre-existing,
untouched here, and unrelated to the rename — but it bounds what this record bought.

**Kotlin sources are still not read either.** `signals.is_java_source` matches `.java` only, while
Framework detection accepts a `.kt` import as a LangChain4j signal. On a Kotlin project the
dependency half is the *only* half of `L4J-SHELL` that can fire, which is what makes it worth
keeping alive across a rename rather than leaning on the wiring signal. Also pre-existing.

**The pattern is meant to be copied, with its limit.** A Deep Agents Rule matching a beta-era
distribution name faces the same question. Match the capability rather than the release's current
spelling *where the capability has a word of its own*. Where it does not, an enumeration is a guess
and this record is not a licence to write one.
