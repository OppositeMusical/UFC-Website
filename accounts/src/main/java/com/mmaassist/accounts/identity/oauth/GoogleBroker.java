package com.mmaassist.accounts.identity.oauth;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

@Component
public class GoogleBroker implements OAuthBroker {

    private static final Logger log = LoggerFactory.getLogger(GoogleBroker.class);

    private final AppProperties.OAuth.Provider config;
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public GoogleBroker(AppProperties properties, RestClient.Builder restClientBuilder,
                        ObjectMapper objectMapper) {
        this.config = properties.getOauth().getGoogle();
        this.restClient = restClientBuilder.build();
        this.objectMapper = objectMapper;
    }

    @Override
    public String provider() {
        return "google";
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
                + "&response_type=code"
                + "&scope=" + encode("openid email profile")
                + "&state=" + encode(state)
                // Without this, a user signed into several Google accounts is
                // silently logged in as whichever one Google picks, with no way
                // to choose. That reads as a bug in our app, not Google's.
                + "&prompt=select_account";
    }

    @Override
    public OAuthProfile exchangeCode(String code, String redirectUri) {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("code", code);
        form.add("client_id", config.getClientId());
        form.add("client_secret", config.getClientSecret());
        form.add("redirect_uri", redirectUri);
        form.add("grant_type", "authorization_code");

        JsonNode tokenResponse = postForm(config.getTokenUri(), form);
        String accessToken = text(tokenResponse, "access_token");
        if (accessToken == null) {
            throw ApiException.badRequest("oauth_failed", "Google did not return an access token.");
        }

        // The userinfo endpoint is used instead of validating the id_token's
        // signature. The claims arrive over TLS straight from Google's token
        // endpoint in response to our authenticated request, so there is no
        // untrusted intermediary whose tampering a signature check would catch
        // (OIDC Core 3.1.3.7 makes this allowance explicitly).
        JsonNode profile;
        try {
            String body = restClient.get()
                    .uri(config.getUserInfoUri())
                    .header("Authorization", "Bearer " + accessToken)
                    .retrieve()
                    .body(String.class);
            profile = objectMapper.readTree(body == null ? "{}" : body);
        } catch (Exception e) {
            log.warn("google userinfo call failed", e);
            throw ApiException.unavailable("oauth_unavailable", "Could not reach Google. Try again.");
        }

        String subject = text(profile, "sub");
        String email = text(profile, "email");
        if (subject == null || email == null) {
            throw ApiException.badRequest("oauth_failed", "Google returned an incomplete profile.");
        }

        // Workspace domains can be configured such that this is false. Passing
        // it through rather than assuming true is what stops an unverified
        // address from linking to somebody else's account.
        boolean verified = profile.path("email_verified").asBoolean(false);

        return new OAuthProfile("google", subject, email.toLowerCase(java.util.Locale.ROOT),
                verified, text(profile, "name"), text(profile, "picture"));
    }

    private JsonNode postForm(String uri, MultiValueMap<String, String> form) {
        try {
            String body = restClient.post()
                    .uri(uri)
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(form)
                    .retrieve()
                    .body(String.class);
            return objectMapper.readTree(body == null ? "{}" : body);
        } catch (Exception e) {
            // Never log `form`: it carries the client secret and the code.
            log.warn("google token exchange failed", e);
            throw ApiException.badRequest("oauth_failed", "Google rejected the sign-in. Try again.");
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
