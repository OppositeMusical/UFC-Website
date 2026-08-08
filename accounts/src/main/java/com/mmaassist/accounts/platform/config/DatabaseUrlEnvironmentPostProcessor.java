package com.mmaassist.accounts.platform.config;

import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.net.URLDecoder;
import java.util.HashMap;
import java.util.Map;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

/**
 * Translates a libpq-style {@code DATABASE_URL} into the three properties Spring
 * actually wants.
 *
 * <p>Railway (like Heroku before it) injects
 * {@code postgres://user:pass@host:5432/dbname}. Spring's datasource needs a
 * JDBC URL, and it does not parse credentials out of one, so handing it the raw
 * value fails at startup with a driver error that says nothing about the real
 * cause. Converting here means the deployment needs no hand-maintained copy of
 * the credentials, which would otherwise drift the moment the database is
 * rotated.
 *
 * <p>An explicit {@code SPRING_DATASOURCE_URL} always wins, so this can be
 * bypassed entirely.
 */
public class DatabaseUrlEnvironmentPostProcessor implements EnvironmentPostProcessor {

    private static final String SOURCE_NAME = "databaseUrlTranslation";

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        if (environment.getProperty("spring.datasource.url") != null) {
            return; // explicitly configured; leave it alone
        }

        String raw = environment.getProperty("DATABASE_URL");
        if (raw == null || raw.isBlank() || raw.startsWith("jdbc:")) {
            return;
        }

        Map<String, Object> translated = translate(raw);
        if (!translated.isEmpty()) {
            environment.getPropertySources().addFirst(new MapPropertySource(SOURCE_NAME, translated));
        }
    }

    /** Package-private so the parsing can be unit tested without a Spring context. */
    static Map<String, Object> translate(String raw) {
        Map<String, Object> properties = new HashMap<>();
        URI uri;
        try {
            uri = new URI(raw);
        } catch (URISyntaxException e) {
            return properties;
        }

        String scheme = uri.getScheme();
        if (scheme == null || !(scheme.equals("postgres") || scheme.equals("postgresql"))) {
            return properties;
        }

        StringBuilder jdbc = new StringBuilder("jdbc:postgresql://").append(uri.getHost());
        if (uri.getPort() > 0) {
            jdbc.append(':').append(uri.getPort());
        }
        jdbc.append(uri.getPath() == null || uri.getPath().isEmpty() ? "/" : uri.getPath());
        if (uri.getQuery() != null && !uri.getQuery().isBlank()) {
            jdbc.append('?').append(uri.getQuery());
        }
        properties.put("spring.datasource.url", jdbc.toString());

        String userInfo = uri.getUserInfo();
        if (userInfo != null && !userInfo.isBlank()) {
            int split = userInfo.indexOf(':');
            // Credentials arrive percent-encoded; a password containing '@' or
            // '/' is otherwise silently truncated, which reads as a wrong
            // password rather than a parsing bug.
            String user = split >= 0 ? userInfo.substring(0, split) : userInfo;
            String password = split >= 0 ? userInfo.substring(split + 1) : "";
            properties.put("spring.datasource.username", decode(user));
            properties.put("spring.datasource.password", decode(password));
        }

        return properties;
    }

    private static String decode(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }
}
