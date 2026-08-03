# LangChain4j Skills

> **Source:** <https://docs.langchain4j.dev/tutorials/skills/>
> **Captured:** 2026-08-01
>
> **Verified:** 2026-08-02 — re-fetched from `Source:` to confirm the two specification
> citations under [Modes](#modes) are upstream's own wording, and they are; this capture
> does not misquote LangChain4j. Scope: that check only, not a re-comparison of the whole
> capture. See
> [The two "integration approaches" are not specification vocabulary](#the-two-integration-approaches-are-not-specification-vocabulary).
>
> **Upstream status:** *The Skills API is experimental. APIs and behavior may still change
> in future releases.* Artifact versions below are `1.18.1-beta28` as published at capture
> time; the identifiers this capture documents were published unchanged across
> `1.12.1-beta21` — `1.18.1-beta28`, 17 releases with the two artifacts released in lockstep,
> the sole exception being `ClassPathSkillLoader`, which first appears at `1.13.0-beta23`.

Skills is a mechanism for equipping an LLM with reusable, self-contained behavioral
instructions. A skill bundles a name, a short description, and a body of instructions (its
content), together with optional resources (references, assets, templates). The LLM loads
a skill on demand, keeping the initial context small and pulling in detailed instructions
only when needed.

> Skills are designed according to the
> [Agent Skills specification](agent-skills-specification.md).

---

## Creating skills

### From the file system

Each skill lives in its own directory containing a `SKILL.md` file. The file must start
with a YAML front matter block declaring the skill's `name` and `description`. Everything
below the front matter becomes the skill's content.

```
skills/
├── docx/
│   ├── SKILL.md
│   └── references/
│       └── tracked-changes.md   ← loaded as a resource
└── data-analysis/
    └── SKILL.md
```

```markdown
---
name: docx
description: Edit and review Word documents using tracked changes
---
When the user asks you to edit a Word document:
1. Always use tracked changes so edits can be reviewed.
...
```

Any file in the skill directory **other than `SKILL.md` itself and files under a
`scripts/` subdirectory** is automatically loaded as a `SkillResource` that the LLM can
read on demand.

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-skills</artifactId>
    <version>1.18.1-beta28</version>
</dependency>
```

```java
// Load all skills found in immediate subdirectories:
List<FileSystemSkill> skills = FileSystemSkillLoader.loadSkills(Path.of("skills/"));

// Or load a single skill by its directory:
FileSystemSkill skill = FileSystemSkillLoader.loadSkill(Path.of("skills/docx"));
```

### From the classpath

`ClassPathSkillLoader` works like `FileSystemSkillLoader` but resolves skill directories
from the classpath. This is useful when skills are bundled inside a JAR or located under
`src/main/resources`:

```
src/main/resources/
└── skills/
    ├── docx/
    │   ├── SKILL.md
    │   └── references/
    │       └── tracked-changes.md
    └── data-analysis/
        └── SKILL.md
```

```java
List<FileSystemSkill> skills = ClassPathSkillLoader.loadSkills("skills");
FileSystemSkill skill = ClassPathSkillLoader.loadSkill("skills/docx");

// By default the thread's context class loader is used; a custom one can be passed:
FileSystemSkill skill = ClassPathSkillLoader.loadSkill("skills/docx", myClassLoader);
```

The same `SKILL.md` format, resource-loading rules, and `scripts/` exclusion apply.

### Programmatically

Skills do not have to be file-system based. They can be created from any source — a
database, a remote API, generated at runtime — using the builder API:

```java
Skill skill = Skill.builder()
    .name("incident-response")
    .description("Step-by-step runbook for diagnosing and resolving production incidents")
    .content("""
        When a production alert fires:
        1. Call `fetchRecentLogs(serviceName)` to retrieve the last 5 minutes of logs.
        2. Call `checkServiceHealth(serviceName)` to get current health metrics.
        3. Based on the findings, call `createIncidentTicket(summary, severity)`.
        4. If severity is CRITICAL, also call `pageOnCall(incidentId)`.
        """)
    .build();
```

Resources can be attached programmatically:

```java
SkillResource reference = SkillResource.builder()
    .relativePath("references/tone-guide.md")
    .content("Use warm, concise language. Avoid jargon.")
    .build();

Skill skill = Skill.builder()
    .name("customer-support")
    .description("Handles customer support inquiries")
    .content("Follow the tone guide in references/tone-guide.md ...")
    .resources(List.of(reference))
    .build();
```

---

## Modes

Skills integrate with an AI Service in two distinct modes, depending on how much control
and trust is needed.

### Tool mode (recommended)

Class: `Skills` (from `langchain4j-skills`). Corresponds to the *tool-based agents*
integration approach in the Agent Skills specification.[^approach]

The LLM activates a skill to receive step-by-step instructions, then carries them out by
calling tools registered explicitly. **The LLM has no access to the file system at
inference time** — all skill content and resources are loaded into memory upfront, and the
`activate_skill` / `read_skill_resource` tools return that preloaded content rather than
reading from disk. Because only pre-defined tools can be invoked, there is no risk of
arbitrary code execution.

#### Registered tools

| Tool | When registered |
|------|-----------------|
| `activate_skill` | Always. Loads a skill's full instructions into the context. |
| `read_skill_resource` | When at least one skill has resources. Reads individual reference files. |
| Skill-scoped tools | After the skill is activated. |

#### How it works

1. The system message lists the available skills (names and descriptions).
2. The user asks a question that requires a specific skill.
3. The LLM calls `activate_skill("my-skill")` to receive its instructions.
4. The LLM follows those instructions, optionally reading resource files along the way.

#### Wiring it up

```java
Skills skills = Skills.from(FileSystemSkillLoader.loadSkills(Path.of("skills/")));

MyAiService service = AiServices.builder(MyAiService.class)
    .chatModel(chatModel)
    .tools(new OrderTools())              // your tools
    .toolProvider(skills.toolProvider())  // or .toolProviders(myToolProvider, skills.toolProvider())
    .systemMessage("You have access to the following skills:\n" + skills.formatAvailableSkills()
        + "\nWhen the user's request relates to one of these skills, activate it first using the "
        + "`activate_skill` tool before proceeding.")
    .build();
```

`formatAvailableSkills()` returns an XML-formatted block:

```xml
<available_skills>
  <skill>
    <name>process-order</name>
    <description>Processes a customer order end-to-end</description>
  </skill>
  <skill>
    <name>data-analysis</name>
    <description>Analyse tabular data and produce charts</description>
  </skill>
</available_skills>
```

#### Customisation

```java
Skills skills = Skills.builder()
    .skills(mySkills)
    .activateSkillToolConfig(ActivateSkillToolConfig.builder()
        .name(...)                          // default: "activate_skill"
        .description(...)
        .parameterName(...)                 // default: "skill_name"
        .parameterDescription(...)
        .throwToolArgumentsExceptions(...)  // default: false
        .build())
    .readResourceToolConfig(ReadResourceToolConfig.builder()
        .name(...)                                     // default: "read_skill_resource"
        .description(...)
        .skillNameParameterName(...)                   // default: "skill_name"
        .skillNameParameterDescription(...)
        .relativePathParameterName(...)                // default: "relative_path"
        .relativePathParameterDescription(...)         // static (takes precedence over provider)
        .relativePathParameterDescriptionProvider(...) // dynamic, based on available resources
        .throwToolArgumentsExceptions(...)             // default: false
        .build())
    .build();
```

### Skill-scoped tools

Tools can be attached directly to a skill. They are exposed to the LLM only **after** the
skill has been activated via `activate_skill`.

Using `@Tool`-annotated methods:

```java
class OrderTools {
    @Tool("Validates a customer order by ID")
    String validateOrder(String orderId) { return "valid"; }

    @Tool("Charges payment for a customer order")
    String chargePayment(String orderId) { return "charged"; }
}

Skill skill = Skill.builder()
    .name("process-order")
    .description("Processes a customer order end-to-end")
    .content("""
        To process an order:
        1. Call `validateOrder(orderId)` to check the order is valid.
        2. Call `chargePayment(orderId)`.
        """)
    .tools(new OrderTools())
    .build();
```

Attaching tools to an already-built skill via `toBuilder()`:

```java
FileSystemSkill skill = FileSystemSkillLoader.loadSkill(Path.of("skills/process-order"));
Skill skillWithTools = skill.toBuilder()
    .tools(new OrderTools())
    .build();
```

Using tool providers — for example, exposing MCP server tools only after activation:

```java
ToolProvider mcpToolProvider = McpToolProvider.builder()
    .mcpClients(mcpClient)
    .toolFilter((tool, mcpClient) -> tool.name().startsWith("inventory_"))
    .build();

Skill skill = Skill.builder()
    .name("inventory-management")
    .description("Manages warehouse inventory")
    .content("Use inventory tools to check stock levels and update quantities.")
    .toolProviders(mcpToolProvider)
    .build();
```

Using a `Map<ToolSpecification, ToolExecutor>` for full control:

```java
ToolSpecification validateOrder = ToolSpecification.builder()
    .name("validateOrder")
    .description("Validates a customer order by ID")
    .addParameter("orderId", JsonSchemaProperty.STRING, JsonSchemaProperty.description("The order ID"))
    .build();

ToolExecutor validateOrderExecutor = (request, memoryId) -> {
    String orderId = parseOrderId(request.arguments());
    return validate(orderId);
};

Skill skill = Skill.builder()
    .name("process-order")
    .description("Processes a customer order end-to-end")
    .content("To process an order:\n1. Call `validateOrder(orderId)` ...")
    .tools(Map.of(validateOrder, validateOrderExecutor))
    .build();
```

All three approaches can be combined; `@Tool` methods, `ToolProvider`s, and `Map` entries
merge into a single set of skill-scoped tools.

#### How skill-scoped tools work

1. Before activation, the LLM only sees `activate_skill` (and `read_skill_resource`).
   Skill-scoped tools are not in the tool list.
2. When the LLM calls `activate_skill("process-order")`, the activation is recorded in the
   `ToolExecutionResultMessage`.
3. Before the next LLM call within the same AI Service invocation, dynamic tool providers
   are re-evaluated against the current messages. Skill-scoped tools become visible and can
   be called immediately. They stay visible in subsequent invocations until the skill is
   deactivated.

#### With Tool Search

- **Skill-scoped tools are never searchable.** They do not appear in the searchable tool
  pool and cannot be found via `tool_search_tool`.
- **Regular tools remain searchable.** Tools registered via `.tools(...)` on the AI Service
  continue to be searchable.
- **`activate_skill` is always visible.** It is marked `ALWAYS_VISIBLE`.

### Shell mode (experimental)

Class: `ShellSkills` (from `langchain4j-experimental-skills-shell`). Corresponds to the
*filesystem-based agents* integration approach in the Agent Skills specification.[^approach]

> **Upstream warning.** Shell execution is inherently unsafe. Commands run directly in the
> host process environment **without any sandboxing, containerization, or privilege
> restriction**. A misbehaving or prompt-injected LLM can execute arbitrary commands on the
> machine running the application. Only use this in controlled environments where the input
> is fully trusted and the associated risks are accepted.

The LLM is given a single `run_shell_command` tool and reads skill instructions directly
from the file system using shell commands. There is no `activate_skill` or
`read_skill_resource` tool — the LLM navigates skill files like a human developer would.

| Tool | When registered |
|------|-----------------|
| `run_shell_command` | Always. Runs shell commands to read `SKILL.md` files, resource files, and execute scripts. |

How it works:

1. The system message lists available skills with their **absolute filesystem paths**.
2. The user asks a question that requires a specific skill.
3. The LLM runs `cat /path/to/skills/docx/SKILL.md` to read the instructions.
4. The LLM follows those instructions by running further shell commands.

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-experimental-skills-shell</artifactId>
    <version>1.18.1-beta28</version>
</dependency>
```

All skills must be filesystem-based (loaded via `FileSystemSkillLoader`):

```java
ShellSkills skills = ShellSkills.from(FileSystemSkillLoader.loadSkills(Path.of("skills/")));

MyAiService service = AiServices.builder(MyAiService.class)
    .chatModel(chatModel)
    .toolProvider(skills.toolProvider())
    .systemMessage("You have access to the following skills:\n" + skills.formatAvailableSkills()
        + "\nWhen the user's request relates to one of these skills, read its SKILL.md before proceeding.")
    .build();
```

Here `formatAvailableSkills()` includes a `<location>` field:

```xml
<available_skills>
  <skill>
    <name>docx</name>
    <description>Edit and review Word documents using tracked changes</description>
    <location>/path/to/skills/docx/SKILL.md</location>
  </skill>
</available_skills>
```

Upstream guidance on when to use shell mode: experimentation and prototyping, or using
third-party community skills (e.g. from the agentskills.io ecosystem) without first
porting them to Java. Wire up a working workflow quickly, then migrate individual actions
to tools as the solution matures.

```java
ShellSkills skills = ShellSkills.builder()
    .skills(mySkills)
    .runShellCommandToolConfig(RunShellCommandToolConfig.builder()
        .name(...)                               // default: "run_shell_command"
        .description(...)                        // default: includes OS name
        .commandParameterName(...)               // default: "command"
        .commandParameterDescription(...)
        .timeoutSecondsParameterName(...)        // default: "timeout_seconds"
        .timeoutSecondsParameterDescription(...)
        .workingDirectory(...)                   // default: JVM's user.dir
        .maxStdOutChars(...)                     // default: 10_000
        .maxStdErrChars(...)                     // default: 10_000
        .executorService(...)                    // for reading stdout/stderr streams
        .throwToolArgumentsExceptions(...)       // default: false
        .build())
    .build();
```

---

## Relevance to SkillSpector

*This section is SkillSpector's analysis, not upstream content.*

### How far the spellings above have been checked

The release range in the front-matter block is the one recorded as `OBSERVED_VERSION_RANGE`
in [`vocabulary.py`](../../src/skillspector/langchain4j/vocabulary.py) and reasoned about in
[ADR 0005](../adr/0005-langchain4j-upstream-vocabulary.md). It is stated here rather than
re-measured, so a reader can tell how far this capture's identifiers have been checked and
not only when they were captured — a capture date says the page was read on a day, and the
range says the type and method names on it held still for 17 releases. Re-measuring that
claim is issue #46; what the report should say when the shell artifact drops its
`experimental` prefix is issue #45.

### What already works unchanged

A LangChain4j skill directory is an Agent Skills directory. `SKILL.md`, `references/`, and
`scripts/` are laid out exactly as SkillSpector's `build_context` node already walks them,
and the frontmatter keys are the ones `_parse_manifest` already reads. **Every
markdown-content analyzer — the 14 `static_patterns_*` modules, `static_yara`, and the
three `semantic_*` analyzers — already fires correctly on a LangChain4j skill today.** No
change is required for SkillSpector to scan the skill payload itself.

Two adjustments follow from `ClassPathSkillLoader`: skills may live under
`src/main/resources/skills/`, and they may be shipped inside a JAR. The first is just a
path; the second is an ingest format SkillSpector does not open (a JAR is a zip, but
`InputHandler` only treats `.zip` suffixes as archives — `input_handler.py:148`).

### What is not covered

The security-relevant configuration lives in **Java host code**, which SkillSpector does
not parse. `_FILE_TYPES` (`build_context.py:50`) has no `.java`, `.kt`, `.gradle`, or
`.xml` entry, so `pom.xml` and every `.java` file classify as `"other"`; and
`_EXECUTABLE_EXTENSIONS` (`build_context.py:68`) has no JVM entry, so
`has_executable_scripts` stays `False` for a Java-only skill and the risk multiplier that
depends on it never applies.

Detection opportunities, ordered by severity of what they catch:

| Signal in Java host code | Risk | Nearest existing analyzer |
|--------------------------|------|---------------------------|
| `ShellSkills` / `langchain4j-experimental-skills-shell` on the classpath | Unsandboxed arbitrary command execution, flagged unsafe by upstream itself | `static_patterns_excessive_agency`, `static_patterns_privilege_escalation` |
| `RunShellCommandToolConfig.workingDirectory` unset | Commands default to the JVM's `user.dir` — usually the app root | `static_patterns_excessive_agency` |
| `@Tool("...")` description text | Instruction-carrying string the model reads; the tool-poisoning surface, in Java rather than an MCP manifest | `mcp_tool_poisoning` (TP1–TP4) |
| `McpToolProvider` without `.toolFilter(...)` | Every MCP tool exposed post-activation rather than a scoped subset | `mcp_least_privilege` (LP1–LP4) |
| Skill `content(...)` built by string concatenation or from a remote source | Instruction text outside any scanned file | `static_patterns_prompt_injection` |
| `pom.xml` / `build.gradle` dependencies | No Maven ecosystem support in `osv_client.py:56` (PyPI and npm only) | `static_patterns_supply_chain` (SC4) |

Attaching a `ToolProvider` to a skill inverts SkillSpector's usual least-privilege model:
the declared capability set is not in `SKILL.md` frontmatter at all but in the Java builder
chain, so a manifest-only reading of a LangChain4j skill understates its true privilege.

See [MULTI_FRAMEWORK_SKILL_ANALYSIS.md](../MULTI_FRAMEWORK_SKILL_ANALYSIS.md) for how these
are proposed to be wired without altering existing scan behavior.

### The two "integration approaches" are not specification vocabulary

Upstream introduces each mode above by saying it "corresponds to the *tool-based agents*" or
"*filesystem-based agents* integration approach in the Agent Skills specification". **The
specification defines no such approaches, and has not in any published revision of the page
at its source.** Treat the correspondence as
upstream LangChain4j's own framing, not as a normative mapping that can be cited back to the
specification.

Checked 2026-08-02 against the published sources:

| Checked | Result |
|---------|--------|
| `https://agentskills.io/specification.md`, fetched fresh | Neither phrase, nor "integration approach", appears |
| All 15 commits of `docs/specification.mdx` in `agentskills/agentskills`, from the first (2025-12-18) to current head (2026-05-16) | Zero occurrences in every revision |
| All 9 pages listed in `https://agentskills.io/llms.txt` | Zero occurrences site-wide |
| Anthropic's own Agent Skills overview (`platform.claude.com`) | Names no pair of integration approaches |

So [agent-skills-specification.md](agent-skills-specification.md) is **not** a partial
capture — the vocabulary is absent upstream too, which was the open question in
[issue #49](https://github.com/rodrigorjsf/SkillSpector/issues/49).

**Where the axis actually lives upstream.** The distinction itself is real; it is documented
outside the specification, in the client-implementation guide
(`https://agentskills.io/client-implementation/adding-skills-support`), § *Step 4: Activate
skills* → *Model-driven activation*, which names "two implementation patterns":

- **Dedicated tool activation** — a registered tool takes a skill name and returns the
  content. This is Tool mode. The guide's own example tool is named `activate_skill`, which
  is the tool LangChain4j registers, so the two descriptions line up on the detail that
  matters.
- **File-read activation** — the model calls its standard file-read tool with the `SKILL.md`
  path from the catalog. This is the nearest counterpart to Shell mode, though not a precise
  one: LangChain4j hands the model a general `run_shell_command` rather than a file-read
  tool, so reading `SKILL.md` is one use of a broader capability. That gap is the whole
  security story — see the upstream warning quoted above.

That guide is the citable source for this axis. Note that it is a guide, not normative
specification text, so a rule keyed to the distinction cannot claim specification backing.
A search for that section vocabulary does surface it, but on third-party renderings rather
than on upstream's own pages — DeepWiki's auto-generated wiki of the
`agentskills/agentskills` repository carries sections named "Tool-Based Integration" and
"Filesystem-Based Integration". No claim is made here about where LangChain4j drew the
wording from; the checks above establish only that the specification is not its source.

For SkillSpector the axis is still the security-relevant one, and it is already captured
under names that do not borrow the disputed vocabulary: the `ShellSkills` row in the
detection table above is exactly the filesystem/shell side, and it is flagged on the
strength of upstream's own unsandboxed-execution warning rather than on any specification
mapping.

[^approach]: This correspondence is upstream LangChain4j's own claim, not a mapping the
    Agent Skills specification defines — see
    [The two "integration approaches" are not specification vocabulary](#the-two-integration-approaches-are-not-specification-vocabulary)
    for the verification.
