package com.example;

import dev.langchain4j.mcp.client.McpClient;
import dev.langchain4j.mcp.McpToolProvider;
import dev.langchain4j.service.tool.ToolProvider;
import dev.langchain4j.skill.Skill;
import dev.langchain4j.skill.shell.RunShellCommandToolConfig;
import dev.langchain4j.skill.shell.ShellSkills;

/** How this application hands its agent a tool surface. */
public class ToolWiring {

    /** Every tool the MCP server exposes, with nothing scoping the set. */
    public static ToolProvider inventoryTools(McpClient mcpClient) {
        return McpToolProvider.builder()
                .mcpClients(mcpClient)
                .build();
    }

    /** A shell tool that inherits wherever the JVM happened to start. */
    public static ShellSkills shell(Skill skill) {
        return ShellSkills.builder()
                .skills(skill)
                .runShellCommandToolConfig(RunShellCommandToolConfig.builder()
                        .name("run_shell_command")
                        .maxStdOutChars(10_000)
                        .build())
                .build();
    }

    /** Tools attached to a Skill after it was built. */
    public static Skill withTools(Skill skill) {
        return skill.toBuilder().tools(new OrderTools()).build();
    }
}
