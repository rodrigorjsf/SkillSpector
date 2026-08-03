package com.example;

import dev.langchain4j.mcp.McpToolProvider;
import dev.langchain4j.mcp.client.McpClient;
import dev.langchain4j.service.tool.ToolProvider;

/** The MCP servers this application borrows tools from. */
public class McpWiring {

    /** Scoped: only the inventory tools reach the agent. */
    public static ToolProvider inventoryTools(McpClient mcpClient) {
        return McpToolProvider.builder()
                .mcpClients(mcpClient)
                .toolFilter((tool, client) -> tool.name().startsWith("inventory_"))
                .build();
    }

    /** Unscoped: every tool the shipping server exposes, with nothing narrowing the set. */
    public static ToolProvider shippingTools(McpClient mcpClient) {
        return McpToolProvider.builder()
                .mcpClients(mcpClient)
                .build();
    }
}
