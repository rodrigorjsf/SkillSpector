package com.example;

import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.service.AiServices;
import dev.langchain4j.skill.ClassPathSkillLoader;
import dev.langchain4j.skill.Skills;

/**
 * Wires the release agent through registered tools, with each Skill's content preloaded.
 *
 * <p>Upstream's ordinary wiring, chosen so that what this fixture measures stays in the
 * build file: the Gradle coordinate is the whole of its L4J-SHELL signal, and the Finding
 * its snapshot pins is the build file's, at the build file's line.
 */
public class ReleaseAgent {

    public static ReleaseAssistant create(ChatModel chatModel) {
        Skills skills = Skills.from(ClassPathSkillLoader.loadSkills("skills"));

        return AiServices.builder(ReleaseAssistant.class)
                .chatModel(chatModel)
                .toolProvider(skills.toolProvider())
                .build();
    }
}
