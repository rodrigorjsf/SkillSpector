# Gated Analyzers decline silently

Status: accepted

An Analyzer that only applies to one Framework must decline when the Scan is of another Framework.
We decided it declines by returning no Findings and emitting **nothing** to the Inspection Ledger —
no ledger event, no analyzer status event — so a Scan of an Agent Skills Skill is byte-for-byte
unchanged by the existence of a LangChain4j or Deep Agents Analyzer.

This reads like a violation of the Inspection Ledger's purpose, which is why it is recorded here.
The Ledger exists so that an absence of Findings is distinguishable from an absence of inspection,
and a silent decline looks exactly like the thing it guards against. The reconciliation is in the
definition of Work Item: it is a *planned* unit of inspection, and an Analyzer whose Framework gate
does not open plans none. There is no unaccounted work, because there was no work. A gap presupposes
something that was meant to be inspected and was not.

## Considered Options

Emitting a `not_applicable` analyzer status was the faithful-to-the-Ledger alternative, and it was
rejected on cost. `finalize_ledger` builds `analyzer_statuses` from every status event
(`src/skillspector/inspection_ledger.py:765`), so a `not_applicable` row would appear in
`analysis_completeness` for **every existing Scan** the moment any Framework Analyzer is registered.
That churns the report and the behavior snapshot on every input, for every Analyzer added, forever —
and it would mean no phase of the multi-framework work could claim to preserve behavior.

A third option — decline silently on the wrong Framework, but emit `not_applicable` when the
Framework matches and there was still nothing applicable — was considered and deferred rather than
rejected. It is the right shape for reporting a LangChain4j repository with no readable Java, and it
does not conflict with this decision: that case has planned work.

## Consequences

`docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` §3.1 asserts the opposite — that gated Analyzers "still run
through `guard_analyzer_node` and emit ledger status events". That is incorrect as written:
`guard_analyzer_node` only synthesizes events when the Analyzer *raises*. §3.1 needs correcting.

The gate is now a convention with no enforcement. A Framework Analyzer that returns a status event by
habit silently breaks the behavior snapshot for every fixture, and the failure surfaces as an
unrelated-looking snapshot diff. The snapshot test is what catches it.
