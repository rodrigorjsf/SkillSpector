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
experimental one: both are still releasing, in lockstep, at `1.18.1-beta28`. `langchain4j-sql` does
not exist at all. `langchain4j-agentic` exists and `langchain4j-experimental-agentic` never did, so
it is not a rename either.

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

**The over-match is bounded and points the right way.** A future `langchain4j-something-shell` fires
`L4J-SHELL` at HIGH before anyone has assessed it. For a security scanner that is the conservative
direction, and the Finding names the artifact it actually read, so a reader can see it is not the
module the Rule was written for and judge. The alternative — a Rule that stays quiet about a shell
dependency it does not recognise — is the failure this record exists to prevent.

**The one over-match that would matter is excluded by construction.** `langchain4j-skills`, the safe
sibling, is in every build file that uses the Skills API at all, and its id is a prefix of the shell
module's. A pattern loose enough to take it would fire HIGH on every clean LangChain4j Scan and make
the Rule useless. It cannot satisfy this one: "skills" does not contain "shell". A test asserts it
directly, with `langchain4j` alone as the control.

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

**Gradle version catalogs are still not read.** `signals.shell_artifact_declarations` explains its
textual match by noting a catalog declares the coordinate as TOML — but `is_jvm_build_file` matches
only `pom.xml` and `build.gradle*`, so `gradle/libs.versions.toml` is never opened. A project
declaring the shell module only there is missed by both halves of the Rule. Pre-existing, untouched
here, and unrelated to the rename.

**Kotlin sources are still not read either.** `signals.is_java_source` matches `.java` only, while
Framework detection accepts a `.kt` import as a LangChain4j signal. On a Kotlin project the
dependency half is the *only* half of `L4J-SHELL` that can fire, which is what makes it worth
keeping alive across a rename rather than leaning on the wiring signal. Also pre-existing.

**The pattern is meant to be copied, with its limit.** A Deep Agents Rule matching a beta-era
distribution name faces the same question. Match the capability rather than the release's current
spelling *where the capability has a word of its own*. Where it does not, an enumeration is a guess
and this record is not a licence to write one.
