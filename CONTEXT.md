# SkillSpector

Security analysis of AI agent skills. This context holds the vocabulary for deciding whether a
published skill is safe to install.

## Language

### Subject of analysis

**Skill**:
A distributable unit of agent capability, published as a directory that an agent loads and trusts.
The thing SkillSpector scans.
_Avoid_: plugin, extension, package, tool

**Component**:
One file inside a Skill. Carries its own type, size, and executable status.
_Avoid_: asset, resource, artifact

**Manifest**:
The declared metadata of a Skill — its name, description, and the tools it claims it may use.
_Avoid_: frontmatter, header, config

**Framework**:
The convention a Skill is written against, which determines how its definition is located and
parsed. Agent Skills, LangChain4j, and Deep Agents are different Frameworks.
_Avoid_: format, flavour, dialect

**Scan**:
One complete pass over a Skill, from resolving the input to emitting a Recommendation.
_Avoid_: run, check, inspection

### Detection

**Analyzer**:
A unit that inspects Components and emits Findings. Every Analyzer runs on every Scan; one that
should only apply to some inputs declines on its own gate.
_Avoid_: checker, detector, scanner, plugin

**Rule**:
The named check an Analyzer applies, and the identity a Finding is attributed to.
_Avoid_: pattern, signature, check

**Finding**:
One instance of a Rule matching at a location in a Component. The atomic claim SkillSpector makes.
_Avoid_: vulnerability, issue, alert, detection

**Analyzer Finding**:
The shape an Analyzer emits, before it is converted into a Finding for graph state and reporting.
Distinct from Finding on purpose — only the latter has a stable identity.

**Severity**:
How damaging a Finding would be if real — LOW, MEDIUM, HIGH, or CRITICAL. Independent of how
certain the Finding is.
_Avoid_: priority, criticality, impact

### Verdict

**Risk Score**:
A 0–100 aggregate over the surviving Findings of a Scan. Suppressed Findings never contribute.
_Avoid_: rating, grade, risk level

**Recommendation**:
The installable verdict a Scan produces — SAFE, CAUTION, or DO_NOT_INSTALL.
_Avoid_: result, outcome, decision

### Accepting known findings

**Baseline**:
A file of Findings that have been reviewed and accepted, so re-scans surface only new ones.
_Avoid_: allowlist, ignore file, exceptions

**Suppression Rule**:
A glob-based Baseline entry that suppresses any Finding matching its rule, path, or message.
_Avoid_: filter, exclusion, mute

**Fingerprint**:
A Baseline entry bound to the exact evidence of one Finding, so any change to the source or the
scanner invalidates it. The precise alternative to a Suppression Rule.
_Avoid_: hash, checksum, signature

**Suppressed Finding**:
A Finding matched by a Baseline. Excluded from the Risk Score and from the report, but never
silently discarded — it is retained with the reason it was accepted.

### Accountability

**Inspection Ledger**:
The record of what a Scan actually inspected and what it did not, with a reason for every gap. It
is what makes an absence of Findings distinguishable from an absence of inspection.
_Avoid_: log, audit trail, trace

**Work Item**:
One planned unit of inspection in the Inspection Ledger. Every Work Item must reach exactly one
terminal outcome; unaccounted work is itself a reportable defect.
_Avoid_: task, job, unit
