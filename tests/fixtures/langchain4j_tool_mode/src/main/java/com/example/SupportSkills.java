package com.example;

import java.nio.file.Path;

import dev.langchain4j.skill.FileSystemSkillLoader;
import dev.langchain4j.skill.Skill;
import dev.langchain4j.skill.SkillResource;

/**
 * Every way this application defines a Skill.
 *
 * <p>Two are readable from here and two are not, and the pair is the point: the Scan
 * either scanned a Skill's instruction text or it says that it could not.
 */
public class SupportSkills {

    /** A Skill whose whole instruction body is written here. */
    public static Skill refundPolicy() {
        return Skill.builder()
                .name("refund-policy")
                .description("Explains when a customer order qualifies for a refund.")
                .content("""
                        Read the order date and the product tier from the request.
                        A standard tier order qualifies for thirty days, a premium tier for ninety.
                        Return the remaining refund window in days.
                        """)
                .build();
    }

    /** An attachment whose contents are written here too. */
    public static SkillResource refundTable() {
        return SkillResource.builder()
                .name("refund-table")
                .description("The refund window for each product tier.")
                .content("tier,days\nstandard,30\npremium,90\n")
                .build();
    }

    /** A Skill assembled at runtime: the text the model reads exists in no file here. */
    public static Skill fromCatalogue(String body) {
        return Skill.builder()
                .name("escalation")
                .description("Escalates a support case to a human agent.")
                .content(body)
                .build();
    }

    /** A literal path: the Skills this reads are on disk and already in the Scan. */
    public static void loadBundled() {
        FileSystemSkillLoader.loadSkill(Path.of("src/main/resources/skills/order-triage"));
    }

    /** A path decided at deploy time: whatever it points at was never located. */
    public static void loadConfigured(Path configured) {
        FileSystemSkillLoader.loadSkills(configured);
    }
}
