package com.mmaassist.accounts.licensing;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mmaassist.accounts.platform.config.AppProperties;
import java.nio.charset.StandardCharsets;
import java.security.Signature;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class LicenceTokenSignerTest {

    private static final Instant NOW = Instant.parse("2026-08-08T12:00:00Z");

    private AppProperties properties;
    private ObjectMapper objectMapper;
    private String signingKey;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        signingKey = Ed25519Keys.encode(Ed25519Keys.generate());

        properties = new AppProperties();
        properties.getLicence().setSigningKey(signingKey);
        properties.getLicence().setKid("test-kid");
        properties.getLicence().setIssuer("https://api.example.test");
        properties.getLicence().setAudience("mma-assist-desktop");
        properties.getLicence().setGraceDays(7);
    }

    @Test
    @DisplayName("the token verifies against the published public key")
    void tokenVerifiesAgainstPublishedKey() throws Exception {
        LicenceTokenSigner signer = new LicenceTokenSigner(properties, objectMapper);
        UUID account = UUID.randomUUID();
        UUID device = UUID.randomUUID();
        UUID jti = UUID.randomUUID();

        String token = signer.sign(account, device, jti, "pro",
                Map.of("cloud_providers", true), "user@example.test",
                NOW, NOW.plus(Duration.ofDays(14)));

        String[] parts = token.split("\\.");
        assertThat(parts).as("compact JWS has three parts").hasSize(3);

        // Verify exactly the way the desktop app will: rebuild the signing
        // input, check it against the key from the JWKS document.
        byte[] rawPublic = Base64.getUrlDecoder().decode((String) signer.publicJwk().get("x"));
        Signature verifier = Signature.getInstance("Ed25519");
        verifier.initVerify(Ed25519Keys.publicKeyFromRaw(rawPublic));
        verifier.update((parts[0] + "." + parts[1]).getBytes(StandardCharsets.US_ASCII));

        assertThat(verifier.verify(Base64.getUrlDecoder().decode(parts[2]))).isTrue();
    }

    @Test
    @DisplayName("a tampered payload fails verification")
    void tamperedPayloadFails() throws Exception {
        LicenceTokenSigner signer = new LicenceTokenSigner(properties, objectMapper);
        String token = signer.sign(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                "free", Map.of(), null, NOW, NOW.plus(Duration.ofDays(1)));

        String[] parts = token.split("\\.");
        // Promote the holder to pro, exactly as an attacker with a text editor would.
        String forged = new String(Base64.getUrlDecoder().decode(parts[1]), StandardCharsets.UTF_8)
                .replace("\"tier\":\"free\"", "\"tier\":\"pro\"");
        String forgedPayload = Base64.getUrlEncoder().withoutPadding()
                .encodeToString(forged.getBytes(StandardCharsets.UTF_8));

        byte[] rawPublic = Base64.getUrlDecoder().decode((String) signer.publicJwk().get("x"));
        Signature verifier = Signature.getInstance("Ed25519");
        verifier.initVerify(Ed25519Keys.publicKeyFromRaw(rawPublic));
        verifier.update((parts[0] + "." + forgedPayload).getBytes(StandardCharsets.US_ASCII));

        assertThat(verifier.verify(Base64.getUrlDecoder().decode(parts[2]))).isFalse();
    }

    @Test
    void headerNamesEdDsaAndTheKeyId() throws Exception {
        LicenceTokenSigner signer = new LicenceTokenSigner(properties, objectMapper);
        String token = signer.sign(UUID.randomUUID(), null, UUID.randomUUID(), "pro",
                Map.of(), null, NOW, NOW.plus(Duration.ofDays(14)));

        JsonNode header = objectMapper.readTree(
                Base64.getUrlDecoder().decode(token.split("\\.")[0]));

        assertThat(header.get("alg").asText()).isEqualTo("EdDSA");
        assertThat(header.get("typ").asText()).isEqualTo("JWT");
        assertThat(header.get("kid").asText()).isEqualTo("test-kid");
    }

    @Test
    @DisplayName("claims carry everything the app gates on")
    void claimsCarryEntitlement() throws Exception {
        LicenceTokenSigner signer = new LicenceTokenSigner(properties, objectMapper);
        UUID account = UUID.randomUUID();
        UUID device = UUID.randomUUID();
        Instant expiry = NOW.plus(Duration.ofDays(14));

        String token = signer.sign(account, device, UUID.randomUUID(), "pro",
                Map.of("cloud_providers", true, "kalshi_market", false), "user@example.test",
                NOW, expiry);

        JsonNode claims = objectMapper.readTree(
                Base64.getUrlDecoder().decode(token.split("\\.")[1]));

        assertThat(claims.get("iss").asText()).isEqualTo("https://api.example.test");
        assertThat(claims.get("sub").asText()).isEqualTo(account.toString());
        assertThat(claims.get("aud").asText()).isEqualTo("mma-assist-desktop");
        assertThat(claims.get("device").asText()).isEqualTo(device.toString());
        assertThat(claims.get("tier").asText()).isEqualTo("pro");
        assertThat(claims.get("exp").asLong()).isEqualTo(expiry.getEpochSecond());
        assertThat(claims.get("iat").asLong()).isEqualTo(NOW.getEpochSecond());
        assertThat(claims.get("grace_days").asInt()).isEqualTo(7);
        assertThat(claims.get("features").get("cloud_providers").asBoolean()).isTrue();
        assertThat(claims.get("features").get("kalshi_market").asBoolean()).isFalse();
    }

    @Test
    @DisplayName("no configured key still boots, on an ephemeral one")
    void ephemeralKeyWhenUnconfigured() {
        AppProperties blank = new AppProperties();
        blank.getLicence().setSigningKey("");

        LicenceTokenSigner signer = new LicenceTokenSigner(blank, objectMapper);

        assertThat(signer.publicJwk().get("x")).isNotNull();
    }

    @Test
    @DisplayName("a seed that does not match its public key is rejected at startup")
    void mismatchedKeyPairRejected() {
        byte[] seedOfOne = Base64.getDecoder().decode(Ed25519Keys.encode(Ed25519Keys.generate()));
        byte[] publicOfAnother = Base64.getDecoder().decode(Ed25519Keys.encode(Ed25519Keys.generate()));

        byte[] frankenstein = new byte[64];
        System.arraycopy(seedOfOne, 0, frankenstein, 0, 32);
        System.arraycopy(publicOfAnother, 32, frankenstein, 32, 32);

        AppProperties broken = new AppProperties();
        broken.getLicence().setSigningKey(Base64.getEncoder().encodeToString(frankenstein));

        assertThatThrownBy(() -> new LicenceTokenSigner(broken, objectMapper))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("do not match");
    }

    @Test
    void keyBlobRoundTrips() {
        Ed25519Keys.Keys generated = Ed25519Keys.generate();
        Ed25519Keys.Keys reloaded = Ed25519Keys.fromEncoded(Ed25519Keys.encode(generated));

        assertThat(reloaded.publicKeyBase64Url()).isEqualTo(generated.publicKeyBase64Url());
    }

    @Test
    void wrongLengthKeyIsRejected() {
        assertThatThrownBy(() -> Ed25519Keys.fromEncoded(
                Base64.getEncoder().encodeToString(new byte[32])))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("64 bytes");
    }
}
