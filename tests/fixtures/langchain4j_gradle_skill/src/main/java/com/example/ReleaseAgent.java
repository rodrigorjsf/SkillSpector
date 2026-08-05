package com.example;

import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.service.AiServices;
import dev.langchain4j.skill.ClassPathSkillLoader;
import dev.langchain4j.skill.Skills;

/**
 * Wires the release agent in Tool mode.
 *
 * <p>The host code is upstream's ordinary wiring, so what this fixture measures stays
 * in the build file: the Gradle declaration is the whole of its shell signal.
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
