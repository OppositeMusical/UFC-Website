package com.mmaassist.accounts.licensing;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.mmaassist.accounts.platform.config.AppProperties;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * The Java half of the licence-token contract.
 *
 * <p>Java signs these tokens and Python verifies them, and neither language's
 * own test suite can see the other side. A change to the claim set, the header,
 * or the base64 variant would leave both suites green and every paying customer
 * locked out of the app they bought — which is exactly the kind of break that
 * only a shared fixture catches.
 *
 * <p>The fixture at {@code backend/tests/fixtures/licence_contract.json} is that
 * shared artefact. This test asserts the signer still reproduces it byte for
 * byte; {@code backend/tests/test_licensing_contract.py} asserts the verifier
 * still accepts it. Ed25519 signatures are deterministic (RFC 8032), so with a
 * fixed key and fixed claims the token is a fixed string.
 *
 * <p><b>Regenerating.</b> Delete the fixture and re-run: it is written back and
 * this test fails once, telling you to commit it. Do that only when the token
 * format is meant to change — and re-run the Python contract test afterwards,
 * because a fixture regenerated to match a broken signer proves nothing.
 *
 * <p>The signing key in that file is generated for this test and used nowhere
 * else. It is not a leaked secret.
 */
class LicenceContractTest {

    private static final Path FIXTURE =
            Path.of("..", "backend", "tests", "fixtures", "licence_contract.json");

    private static final String KID = "contract-test";
    private static final String ISSUER = "https://api.mmaassist.test";
    private static final String AUDIENCE = "mma-assist-desktop";

    // Fixed so the token is reproducible.
    private static final UUID ACCOUNT = UUID.fromString("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0");
    private static final UUID DEVICE = UUID.fromString("11112222-3333-4444-5555-666677778888");
    private static final UUID JTI = UUID.fromString("99998888-7777-6666-5555-444433332222");
    private static final Instant ISSUED_AT = Instant.parse("2026-08-08T12:00:00Z");
    private static final Instant EXPIRES_AT = Instant.parse("2026-08-22T12:00:00Z");

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    @DisplayName("the signer still reproduces the committed contract fixture")
    void signerMatchesFixture() throws Exception {
        if (!Files.exists(FIXTURE)) {
            writeFixture();
            throw new AssertionError(
                    "No contract fixture existed, so one was written to " + FIXTURE.toAbsolutePath()
                            + ". Commit it, then run the Python contract test "
                            + "(backend/tests/test_licensing_contract.py) to confirm the "
                            + "verifier accepts it.");
        }

        JsonNode fixture = objectMapper.readTree(Files.readString(FIXTURE));
        String token = signWith(fixture.get("signingKey").asText());

        assertThat(token)
                .as("the licence token format changed - see this class's javadoc before "
                        + "regenerating the fixture")
                .isEqualTo(fixture.get("token").asText());
    }

    @Test
    @DisplayName("the fixture's published public key is the one that verifies it")
    void fixturePublicKeyMatches() throws Exception {
        if (!Files.exists(FIXTURE)) {
            return; // the test above owns that failure
        }
        JsonNode fixture = objectMapper.readTree(Files.readString(FIXTURE));

        Ed25519Keys.Keys keys = Ed25519Keys.fromEncoded(fixture.get("signingKey").asText());

        assertThat(keys.publicKeyBase64Url())
                .isEqualTo(fixture.get("publicKeyBase64Url").asText());
    }

    private String signWith(String signingKey) {
        AppProperties properties = new AppProperties();
        properties.getLicence().setSigningKey(signingKey);
        properties.getLicence().setKid(KID);
        properties.getLicence().setIssuer(ISSUER);
        properties.getLicence().setAudience(AUDIENCE);
        properties.getLicence().setGraceDays(7);

        return new LicenceTokenSigner(properties, objectMapper)
                .sign(ACCOUNT, DEVICE, JTI, "pro", features(), "contract@example.test",
                        ISSUED_AT, EXPIRES_AT);
    }

    /** Insertion-ordered, because the signature covers the serialised bytes. */
    private static Map<String, Object> features() {
        Map<String, Object> features = new LinkedHashMap<>();
        features.put("cloud_providers", true);
        features.put("all_platforms", true);
        features.put("kalshi_market", true);
        features.put("unlimited_history", true);
        return features;
    }

    private void writeFixture() throws Exception {
        Ed25519Keys.Keys keys = Ed25519Keys.generate();
        String signingKey = Ed25519Keys.encode(keys);

        ObjectNode fixture = objectMapper.createObjectNode();
        fixture.put("_note", "Shared Java/Python contract for the licence token. "
                + "The signing key is generated for this fixture and used nowhere else. "
                + "See LicenceContractTest for how to regenerate.");
        fixture.put("signingKey", signingKey);
        fixture.put("publicKeyBase64Url", keys.publicKeyBase64Url());
        fixture.put("kid", KID);
        fixture.put("issuer", ISSUER);
        fixture.put("audience", AUDIENCE);

        ObjectNode claims = fixture.putObject("expectedClaims");
        claims.put("sub", ACCOUNT.toString());
        claims.put("device", DEVICE.toString());
        claims.put("jti", JTI.toString());
        claims.put("tier", "pro");
        claims.put("email", "contract@example.test");
        claims.put("iat", ISSUED_AT.getEpochSecond());
        claims.put("exp", EXPIRES_AT.getEpochSecond());
        claims.put("grace_days", 7);
        ObjectNode featureNode = claims.putObject("features");
        features().forEach((key, value) -> featureNode.put(key, (Boolean) value));

        fixture.put("token", signWith(signingKey));

        Files.createDirectories(FIXTURE.getParent());
        Files.writeString(FIXTURE, objectMapper.writerWithDefaultPrettyPrinter()
                .writeValueAsString(fixture) + "\n");
    }
}
