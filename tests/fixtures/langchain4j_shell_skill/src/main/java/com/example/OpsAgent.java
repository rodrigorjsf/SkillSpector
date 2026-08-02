package com.example;

import java.nio.file.Path;

import dev.langchain4j.service.AiServices;
import dev.langchain4j.skill.FileSystemSkillLoader;
import dev.langchain4j.skill.shell.ShellSkills;

/**
 * Wires the operations agent in shell mode.
 *
 * <p>Shell mode hands the model a single {@code run_shell_command} tool and lets it read
 * the Skill instructions off the filesystem itself. Nothing here sandboxes it.
 */
public class OpsAgent {

    public static OpsAssistant create(ChatModel chatModel) {
        ShellSkills skills =
                ShellSkills.from(FileSystemSkillLoader.loadSkills(Path.of("src/main/resources/skills/")));

        return AiServices.builder(OpsAssistant.class)
                .chatModel(chatModel)
                .toolProvider(skills.toolProvider())
                .systemMessage("You have access to the following skills:\n" + skills.formatAvailableSkills())
                .build();
    }
}
