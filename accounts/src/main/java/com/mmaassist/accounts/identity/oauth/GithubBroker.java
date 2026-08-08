package com.mmaassist.accounts.identity.oauth;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

/**
 * GitHub sign-in.
 *
 * <p>GitHub is OAuth2, not OIDC, and this is where that bites: there is no
 * {@code email} claim anywhere in the token response, and {@code GET /user}
 * returns the <em>public</em> profile email, which is frequently null and is
 * never guaranteed to be verified. The address has to come from
 * {@code GET /user/emails} — the entry that is both primary and verified — and
 * a login with no such entry is refused outright.
 *
 * <p>That refusal is deliberate. Linking on an unverified address is account
 * takeover: anyone who can add {@code victim@example.com} to their GitHub
 * account without confirming it would inherit the victim's licence and payment
 * history.
 */
@Component
public class GithubBroker implements OAuthBroker {

    private static final Logger log = LoggerFactory.getLogger(GithubBroker.class);

    private final AppProperties.OAuth.Provider config;
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public GithubBroker(AppProperties properties, RestClient.Builder restClientBuilder,
                        ObjectMapper objectMapper) {
        this.config = properties.getOauth().getGithub();
        this.restClient = restClientBuilder.build();
        this.objectMapper = objectMapper;
    }

    @Override
    public String provider() {
        return "github";
    }

    @Override
    public boolean isConfigured() {
        return config.isConfigured();
    }

    @Override
    public String authorizationUri(String state, String redirectUri) {
        return config.getAuthorizationUri()
                + "?client_id=" + encode(config.getClientId())
                + "&redirect_uri=" + encode(redirectUri)
                // user:email is not optional: without it /user/emails 403s and
                // every login fails the verified-email check.
                + "&scope=" + encode("read:user user:email")
                + "&state=" + encode(state);
    }

    @Override
    public OAuthProfile exchangeCode(String code, String redirectUri) {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("code", code);
        form.add("client_id", config.getClientId());
        form.add("client_secret", config.getClientSecret());
        form.add("redirect_uri", redirectUri);

        JsonNode tokenResponse;
        try {
            String body = restClient.post()
                    .uri(config.getTokenUri())
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    // GitHub defaults to a form-encoded response body and only
                    // returns JSON when asked. Without this header the parse
                    // below silently yields nothing.
                    .accept(MediaType.APPLICATION_JSON)
                    .body(form)
                    .retrieve()
                    .body(String.class);
            tokenResponse = objectMapper.readTree(body == null ? "{}" : body);
        } catch (Exception e) {
            log.warn("github token exchange failed", e);
            throw ApiException.badRequest("oauth_failed", "GitHub rejected the sign-in. Try again.");
        }

        String accessToken = text(tokenResponse, "access_token");
        if (accessToken == null) {
            throw ApiException.badRequest("oauth_failed", "GitHub did not return an access token.");
        }

        JsonNode user = get(accessToken, config.getUserInfoUri());
        JsonNode emails = get(accessToken, config.getUserEmailsUri());

        String subject = text(user, "id");
        if (subject == null) {
            throw ApiException.badRequest("oauth_failed", "GitHub returned an incomplete profile.");
        }

        String email = primaryVerifiedEmail(emails);
        if (email == null) {
            throw ApiException.badRequest("email_unverified",
                    "Your GitHub account has no verified primary email address. "
                            + "Verify one with GitHub, or sign in with Google instead.");
        }

        String displayName = text(user, "name");
        if (displayName == null || displayName.isBlank()) {
            displayName = text(user, "login");
        }

        return new OAuthProfile("github", subject, email, true, displayName, text(user, "avatar_url"));
    }

    /** Visible for testing: picks the one address GitHub says is both primary and verified. */
    static String primaryVerifiedEmail(JsonNode emails) {
        if (emails == null || !emails.isArray()) {
            return null;
        }
        for (JsonNode entry : emails) {
            boolean primary = entry.path("primary").asBoolean(false);
            boolean verified = entry.path("verified").asBoolean(false);
            JsonNode address = entry.get("email");
            if (primary && verified && address != null && !address.isNull()) {
                return address.asText().toLowerCase(Locale.ROOT);
            }
        }
        return null;
    }

    private JsonNode get(String accessToken, String uri) {
        try {
            String body = restClient.get()
                    .uri(uri)
                    .header("Authorization", "Bearer " + accessToken)
                    .header("Accept", "application/vnd.github+json")
                    .retrieve()
                    .body(String.class);
            return objectMapper.readTree(body == null ? "{}" : body);
        } catch (Exception e) {
            log.warn("github api call failed for {}", uri, e);
            throw ApiException.unavailable("oauth_unavailable", "Could not reach GitHub. Try again.");
        }
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
