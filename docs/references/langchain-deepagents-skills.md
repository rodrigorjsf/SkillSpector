# LangChain Deep Agents — Skills

> **Source:** <https://docs.langchain.com/oss/python/deepagents/skills>
> **Captured:** 2026-08-01
>
> **Upstream releases swept:** 2026-08-03 — the spellings this capture documents were read out of
> every published `deepagents` wheel, `0.0.1` through `0.7.3`, 78 final releases. None has ever
> been removed; the permission vocabulary arrives together at `0.5.2`, below the
> `deepagents>=0.6.8` floor quoted under [Usage](#usage). The range is recorded as
> `OBSERVED_VERSION_RANGE` in
> [`vocabulary.py`](../../src/skillspector/deepagents/vocabulary.py); re-measuring it is
> [`docs/VOCABULARY_REMEASUREMENT.md`](../VOCABULARY_REMEASUREMENT.md). Stated here rather than
> re-measured, so a reader can tell how far this capture's spellings have been checked and not
> only when they were captured.
> **Scope note:** Deep Agents is the LangChain Python framework that consumes `SKILL.md`
> directories. The general LangChain OSS docs (`/oss/python/langchain/overview`) describe
> agents, tools, and middleware but have no on-disk skill format, so Deep Agents is the
> correct anchor for SkillSpector.

Skills package domain expertise — workflows, best practices, scripts, reference docs, and
templates — into reusable directories. The agent gets a summary of the contents on startup
and discovers and reads the contained files only when relevant.

> Deep agent skills follow the
> [Agent Skills specification](agent-skills-specification.md).

---

## Usage

1. **Create a top-level skills directory**, such as `skills/` under the backend root.

2. **Create a subdirectory per skill.** Each skill is a directory containing a `SKILL.md`
   file: markdown with YAML frontmatter (`name` and `description`) followed by
   instructions. It may also include scripts, reference docs, and templates.

   ```
   skills/
   └── langgraph-docs/
       ├── SKILL.md
       ├── scripts/
       │   └── fetch_docs.py
       ├── references/
       │   ├── api-patterns.md
       │   └── style-guide.md
       └── assets/
           ├── report-template.md
           └── schema.json
   ```

3. **Add a `SKILL.md` with YAML frontmatter and instructions:**

   ```markdown
   ---
   name: langgraph-docs
   description: Use this skill for requests related to LangGraph in order to fetch relevant documentation to provide accurate, up-to-date guidance.
   ---

   # langgraph-docs

   ## Instructions

   ### 1. Fetch the documentation index
   Use the fetch_url tool to read the following URL:
   https://docs.langchain.com/llms.txt

   ### 2. Select relevant documentation
   Based on the question, identify 2-4 most relevant documentation URLs from the index.

   ### 3. Fetch and synthesize
   Use the fetch_url tool to read the selected documentation URLs, then answer.
   ```

4. **Pass the skills path when creating the agent:**

   ```python
   from deepagents import create_deep_agent
   from deepagents.backends.filesystem import FilesystemBackend

   backend = FilesystemBackend(root_dir="./my-project")

   agent = create_deep_agent(
       model="anthropic:claude-sonnet-4-6",
       backend=backend,
       skills=["./my-project/skills/"],
   )
   ```

   `skills: list[str]` — list of skill source paths, specified with forward slashes and
   relative to the backend's root. If omitted, no skills are loaded. **Later sources
   override earlier ones for skills with the same name (last one wins)**, which lets base
   skills be overridden by project-specific versions.

5. **Invoke the agent.** At startup the agent loads each skill's `name` and `description`
   from frontmatter into the system prompt. When a task matches a skill's description, the
   agent reads that skill's `SKILL.md` and follows its instructions.

## How skills work

Skills use **progressive disclosure**: the agent loads skill information in layers instead
of all at once.

| Level | What loads | When |
|-------|------------|------|
| 1. Metadata | `name` and `description` from `SKILL.md` frontmatter | Agent startup, for every configured skill |
| 2. Instructions | Full `SKILL.md` body | When the skill is invoked |
| 3. Resources | Supporting files under `scripts/`, `references/`, `assets/` | As needed after invocation, when the instructions reference them |

`SkillsMiddleware` — part of the default middleware stack when `skills` is passed —
handles the first two levels; the third is handled by the LLM:

1. **Discovery** (level 1): at agent start, the middleware scans the configured skill
   paths, parses each `SKILL.md` frontmatter, and injects `name` and `description` into the
   system prompt.
2. **Read** (level 2): when the agent invokes a skill, it reads the full `SKILL.md` content
   via `read_file`.
3. **Execute** (level 3): after invocation, the agent follows the instructions and reads
   supporting files only as required.

## Writing effective skills

- **Keep frontmatter concise** and the `SKILL.md` body under **5,000 tokens**. Frontmatter
  is added to the system prompt at discovery for every skill.
- **Write specific descriptions.** During discovery, `description` is the only information
  the agent sees. It should state both what the skill does and when to activate it, with
  specific keywords.

  ```yaml
  # Good: specific about what and when
  description: >-
    Extract text and tables from PDF files, fill PDF forms, and merge
    multiple PDFs. Use when working with PDF documents or when the user
    mentions PDFs, forms, or document extraction.

  # Poor: too vague for reliable matching
  description: Helps with PDFs.
  ```

  Differentiate descriptions across related skills. Overlapping descriptions cause the
  agent to activate the wrong skill or hesitate. If two skills serve similar purposes,
  consolidate them.
- **Keep instructions focused.** The specification recommends keeping `SKILL.md` under
  **500 lines**. Move detailed reference material into supporting files and reference them
  from the main `SKILL.md`. Keep file references **one level deep**; avoid deeply nested
  reference chains.
- **Structure instructions for the agent** — step-by-step procedures, decision criteria,
  examples of expected inputs and outputs, edge cases to handle or flag.
- **Manage skill count.** Fewer well-scoped skills outperform many overlapping ones.

## Supporting resources

Deep Agents does **not** load these files at discovery or activation. The agent reads or
executes them only when the `SKILL.md` instructions say to.

- **`scripts/`** — executable code the agent can run: API clients, data transforms,
  validation checks. Should be self-contained or clearly document dependencies, include
  helpful error messages, and handle edge cases. Supported languages depend on the agent
  setup; commonly Python, Bash, and JavaScript/TypeScript.
- **`references/`** — supplementary documentation read on demand, too detailed for
  `SKILL.md` but still task-specific.
- **`assets/`** — static resources the agent uses but does not read as instructions:
  templates, images, data files.

Reference supporting files with paths relative to the skill root:

```markdown
For API details, see the [reference guide](references/api-patterns.md).

To extract tables from a PDF, run:
scripts/extract.py
```

## Backends and remote skill loading

- **`StateBackend`** (default) — stores files in LangGraph agent state for the current
  thread. Skill files are supplied via `invoke(files={...})`, formatted with
  `create_file_data()` from `deepagents.backends.utils`; raw strings are not supported.
- **`StoreBackend`** — stores files in a LangGraph store for durable, cross-thread storage.
- **`FilesystemBackend`** — loads skills from disk relative to `root_dir`.
- **`CompositeBackend`** — routes path prefixes to different backends.

## Loading skills at runtime

### Dynamic skill lists

```python
from deepagents import create_deep_agent

SKILLS_BY_ROLE = {
    "engineering": ["/skills/code-review/", "/skills/testing/", "/skills/deployment/"],
    "data": ["/skills/sql-analysis/", "/skills/visualization/", "/skills/data-pipeline/"],
    "support": ["/skills/ticket-triage/", "/skills/runbook/"],
}


def create_agent_for_user(user_role: str):
    return create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        skills=SKILLS_BY_ROLE.get(user_role, []),
    )
```

> The SDK only loads the sources passed in `skills`. It does **not** automatically scan CLI
> directories such as `~/.deepagents/...` or `~/.agents/...`. CLI-style layering must be
> emulated by passing all sources explicitly in lowest-to-highest precedence order:
>
> ```text
> [
>   "<user-home>/.deepagents/{agent}/skills/",
>   "<user-home>/.agents/skills/",
>   "<project-root>/.deepagents/skills/",
>   "<project-root>/.agents/skills/",
> ]
> ```

### Namespaced skills

```python
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    skills=["/skills/"],
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": StoreBackend(
                namespace=lambda rt: (
                    rt.server_info.assistant_id,
                    rt.server_info.user.identity,
                ),
            ),
        },
    ),
)
```

## Skills for subagents

- **General-purpose subagent** — automatically inherits skills from the main agent when
  `skills` is passed to `create_deep_agent`.
- **Custom subagents** — do **not** inherit the main agent's skills. Each subagent
  definition needs its own `skills` parameter.

## Skill permissions

Production deployments usually need to control three things: which skills each user can
see, whether the agent can modify skill files, and whether writes require human approval.
Visibility is controlled by the `skills` argument and backend routing, access by filesystem
permissions, approval by `interrupt_on` or permission rules with `mode="interrupt"`.

### Enforce read-only skills

```python
from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": StoreBackend(
                namespace=lambda rt: ("curated-skills", rt.context.org_id),
            ),
        },
    ),
    skills=["/skills/"],
    permissions=[
        FilesystemPermission(
            operations=["write"],
            paths=["/skills/**"],
            mode="deny",
        ),
    ],
    store=InMemoryStore(),
)
```

### Require approval for skill writes

```python
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    skills=["/skills/personal/"],
    permissions=[
        FilesystemPermission(
            operations=["write"],
            paths=["/skills/**"],
            mode="interrupt",
        ),
    ],
    checkpointer=MemorySaver(),  # Required to pause and resume
)
```

Alternatively, `interrupt_on={"write_file": True, "edit_file": True}` requires approval for
all filesystem writes, not only skills paths. Filesystem permission interrupts require
`deepagents>=0.6.8`.

### Allow agents to edit personal skills

**By default, agents can write to skill files if the backend permits it and no permission
rule blocks the path.** To let agents create or refine skills without touching shared
libraries: route a writable path such as `/skills/personal/` to a user-scoped
`StoreBackend`, pass that path along with any shared paths in `skills`, and do not add a
`deny` rule for the writable path. Place more specific rules before broader deny rules.

## Executing code with skills

Without code execution, skills are passive: the agent reads instructions and follows them
using available tools. Code execution turns skills into active capabilities — a skill can
ship a tested script that calls an API, transforms data, validates output, or runs a
pipeline, executed deterministically rather than regenerated from instructions.

Skills execute code through **sandbox scripts**: the agent runs a bundled script when it
needs to install dependencies, run tests, call CLIs, or work with an operating-system
filesystem.

```
skills/
└── arxiv-search/
    ├── SKILL.md
    └── scripts/
        └── search.py
```

## Frontmatter reference

The Agent Skills specification defines the following fields:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Lowercase alphanumeric with hyphens, 1–64 characters. Must match the parent directory name. |
| `description` | Yes | What the skill does and when to use it. Max 1,024 characters. |
| `license` | No | License name or reference to a bundled license file. |
| `compatibility` | No | Environment requirements (system packages, network access). Max 500 characters. |
| `metadata` | No | Arbitrary key-value pairs for additional properties. |
| `allowed-tools` | No | Space-separated list of pre-approved tools the skill can use. Experimental. |

> In Deep Agents, `SKILL.md` files must be **under 10 MB**. Files exceeding this limit are
> **skipped** during skill loading.

## Skills vs. memory vs. tools

| | Skills | Memory | Tools |
|---|--------|--------|-------|
| **Purpose** | On-demand capabilities via progressive disclosure | Persistent context loaded at startup | Programmatic actions the agent can call |
| **Loading** | Read only when the agent determines relevance | Loaded at agent start | Available every turn |
| **Format** | `SKILL.md` in named directories | `AGENTS.md` files | Functions bound to the agent |
| **Layering** | User, then project (last wins) | User, then project (combined) | Defined at agent creation |

---

## Relevance to SkillSpector

*This section is SkillSpector's analysis, not upstream content.*

### What already works unchanged

A Deep Agents skill directory is an Agent Skills directory with the same three optional
subdirectories. `build_context` already walks it, `_parse_manifest` already reads the
frontmatter, and `scripts/` contents are already `.py`/`.sh` files that
`behavioral_ast`, `behavioral_taint_tracking`, and every `static_patterns_*` analyzer
handle today. Deep Agents is the **cheapest of the two frameworks to support**, because its
host language is the language SkillSpector already parses.

### What is not covered

| Signal | Risk | Nearest existing analyzer |
|--------|------|---------------------------|
| `create_deep_agent(...)` with `skills=[...]` and **no** `permissions=[...]` | Agents can write to skill files by default when the backend permits — self-modifying skills | `mcp_rug_pull` (RP1–RP3, manifest drift), `static_patterns_memory_poisoning` |
| `FilesystemPermission(..., mode="deny")` absent on a `/skills/**` path that is also passed in `skills` | Writable shared skill library | `mcp_least_privilege` |
| `interrupt_on` absent on `write_file` / `edit_file` | No human in the loop for skill mutation | `static_patterns_excessive_agency` |
| Duplicate skill `name` across sources in the `skills` list | Silent last-one-wins override; a later source can shadow a vetted skill | New — no equivalent today |
| Skill referenced under `scripts/` but never invoked from `SKILL.md`, or referenced but missing | Dead or dangling executable payload | `semantic_quality_policy` |
| `SKILL.md` body over 500 lines / ~5000 tokens | Spec-conformance and context-bloat defect, not a security one | `semantic_quality_policy` |
| Custom subagent definitions without their own `skills` | Capability silently unavailable at runtime — a correctness bug the docs call out explicitly | New — no equivalent today |

The duplicate-name override deserves emphasis: `skills=[shared, personal]` means a
user-writable `personal/` skill can shadow a curated `shared/` skill of the same name. That
is a supply-chain substitution primitive expressible entirely in configuration, invisible to
any single-directory scan. Detecting it requires reasoning across the **whole list of skill
sources**, which is closer to SkillSpector's existing `multi_skill.detect_skills`
(`src/skillspector/multi_skill.py:51`) than to any per-file analyzer.

See [MULTI_FRAMEWORK_SKILL_ANALYSIS.md](../MULTI_FRAMEWORK_SKILL_ANALYSIS.md) for how these
are proposed to be wired without altering existing scan behavior.
