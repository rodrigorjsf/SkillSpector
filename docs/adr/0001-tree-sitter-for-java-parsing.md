# Parse Java with tree-sitter

Status: accepted

Supporting LangChain4j Skills means reading Java to resolve where Skills are defined and what their
content is. We chose tree-sitter (`tree-sitter` + `tree-sitter-java`) over `javalang`, accepting two
new runtime dependencies on a deliberately tight list.

Accepted because the LangChain4j Analyzer is now the next increment rather than a later one:
[ADR 0004](0004-langchain4j-before-deepagents.md) schedules the Java track ahead of Deep Agents on
risk grounds, which closes the dependency gate this ADR held open.

## Considered Options

`javalang` 0.13.0 was rejected: last released 2020-03-28 against a Java 8 grammar, so it predates
text blocks (Java 15). LangChain4j's own documentation defines Skill content with `.content("""…""")`,
which means the single most important construct fails to parse.

tree-sitter also parses error-tolerantly — a partially invalid file still yields a usable tree, which
is what lets the analyzer report an unresolved definition instead of failing the whole Scan.

## Consequences

Java definition paths that are not statically resolvable — content from a database, a remote API, or
runtime generation — stay unresolvable. tree-sitter does not move that boundary; it only makes the
resolvable cases correct.

Full analysis: `docs/MULTI_FRAMEWORK_SKILL_ANALYSIS.md` §3.6.
