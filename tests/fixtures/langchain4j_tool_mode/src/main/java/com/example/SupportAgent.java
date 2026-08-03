package com.example;

import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.service.AiServices;
import dev.langchain4j.skill.ClassPathSkillLoader;
import dev.langchain4j.skill.Skills;

/**
 * Wires the customer support agent in Tool mode.
 *
 * <p>The agent reaches its Skills through registered tools, with each Skill's content
 * preloaded. This is upstream's ordinary, recommended wiring, and the Analyzer is expected
 * to say nothing about any of it.
 */
public class SupportAgent {

    public static SupportAssistant create(ChatModel chatModel) {
        Skills skills = Skills.from(ClassPathSkillLoader.loadSkills("skills"));

        return AiServices.builder(SupportAssistant.class)
                .chatModel(chatModel)
                .toolProvider(skills.toolProvider())
                .build();
    }
}
