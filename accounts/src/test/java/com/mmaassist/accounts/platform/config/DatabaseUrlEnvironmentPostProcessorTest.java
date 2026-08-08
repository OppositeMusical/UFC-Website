package com.mmaassist.accounts.platform.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class DatabaseUrlEnvironmentPostProcessorTest {

    @Test
    void translatesRailwayStyleUrl() {
        Map<String, Object> translated = DatabaseUrlEnvironmentPostProcessor
                .translate("postgres://appuser:s3cret@db.internal:5432/mmaassist");

        assertThat(translated)
                .containsEntry("spring.datasource.url", "jdbc:postgresql://db.internal:5432/mmaassist")
                .containsEntry("spring.datasource.username", "appuser")
                .containsEntry("spring.datasource.password", "s3cret");
    }

    @Test
    @DisplayName("a percent-encoded password survives, rather than being silently truncated")
    void decodesEncodedCredentials() {
        Map<String, Object> translated = DatabaseUrlEnvironmentPostProcessor
                .translate("postgresql://user%40corp:p%40ss%2Fword@host/db");

        assertThat(translated)
                .containsEntry("spring.datasource.username", "user@corp")
                .containsEntry("spring.datasource.password", "p@ss/word");
    }

    @Test
    void keepsQueryParameters() {
        Map<String, Object> translated = DatabaseUrlEnvironmentPostProcessor
                .translate("postgres://u:p@host:5432/db?sslmode=require");

        assertThat(translated).containsEntry("spring.datasource.url",
                "jdbc:postgresql://host:5432/db?sslmode=require");
    }

    @Test
    void ignoresNonPostgresUrls() {
        assertThat(DatabaseUrlEnvironmentPostProcessor.translate("mysql://u:p@host/db")).isEmpty();
        assertThat(DatabaseUrlEnvironmentPostProcessor.translate("not a url at all")).isEmpty();
    }
}
