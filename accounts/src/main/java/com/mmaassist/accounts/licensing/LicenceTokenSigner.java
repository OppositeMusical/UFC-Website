package com.mmaassist.accounts.licensing;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mmaassist.accounts.platform.config.AppProperties;
import java.nio.charset.StandardCharsets;
import java.security.Signature;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Builds and signs the licence token the desktop app verifies offline.
 *
 * <p>A compact JWS, assembled directly rather than through a JOSE library. That
 * is a defensible choice specifically because this class only signs: the
 * classic hand-rolled-JWT disaster is algorithm confusion, and that is a
 * <em>verifier</em> bug. The verifier here is
 * {@code backend/app/services/licensing/token.py}, which pins EdDSA and refuses
 * everything else, and the two are held together by a cross-language contract
 * test.
 */
@Component
public class LicenceTokenSigner {

    private static final Logger log = LoggerFactory.getLogger(LicenceTokenSigner.class);
    private static final Base64.Encoder BASE64URL = Base64.getUrlEncoder().withoutPadding();

    private final AppProperties.Licence config;
    private final ObjectMapper objectMapper;
    private final Ed25519Keys.Keys keys;

    public LicenceTokenSigner(AppProperties properties, ObjectMapper objectMapper) {
        this.config = properties.getLicence();
        this.objectMapper = objectMapper;

        if (config.getSigningKey() == null || config.getSigningKey().isBlank()) {
            // Development convenience. Tokens signed with an ephemeral key stop
            // verifying at the next restart, which is fine locally and would be
            // a disaster in production - hence the noise.
            this.keys = Ed25519Keys.generate();
            log.warn("No LICENCE_SIGNING_KEY configured - generated an ephemeral key. "
                    + "Licence tokens will stop verifying when this process restarts.");
            log.warn("Ephemeral public key (base64url): {}", keys.publicKeyBase64Url());
        } else {
            this.keys = Ed25519Keys.fromEncoded(config.getSigningKey());
            log.info("Licence signing key loaded, kid={}", config.getKid());
        }
    }

    /**
     * @param jti      the token id, so a single device can be cut off before expiry
     * @param features what the app should unlock
     */
    public String sign(UUID accountId, UUID deviceId, UUID jti, String tier,
                       Map<String, Object> features, String email, Instant issuedAt,
                       Instant expiresAt) {

        Map<String, Object> header = new LinkedHashMap<>();
        header.put("alg", "EdDSA");
        header.put("typ", "JWT");
        header.put("kid", config.getKid());

        Map<String, Object> claims = new LinkedHashMap<>();
        claims.put("iss", config.getIssuer());
        claims.put("sub", accountId.toString());
        claims.put("aud", config.getAudience());
        claims.put("jti", jti.toString());
        claims.put("iat", issuedAt.getEpochSecond());
        claims.put("exp", expiresAt.getEpochSecond());
        claims.put("tier", tier);
        claims.put("features", features);
        if (deviceId != null) {
            claims.put("device", deviceId.toString());
        }
        // How long past expiry the app may keep working while it cannot reach
        // us. Carried in the token so the policy can change without shipping a
        // new build.
        claims.put("grace_days", config.getGraceDays());
        if (email != null) {
            // Display only. The app must never treat this as proof of anything.
            claims.put("email", email);
        }

        String signingInput = encode(header) + "." + encode(claims);
        return signingInput + "." + BASE64URL.encodeToString(signature(signingInput));
    }

    /** The public half, in JWK form, for {@code /.well-known/jwks.json}. */
    public Map<String, Object> publicJwk() {
        Map<String, Object> jwk = new LinkedHashMap<>();
        jwk.put("kty", "OKP");
        jwk.put("crv", "Ed25519");
        jwk.put("x", keys.publicKeyBase64Url());
        jwk.put("use", "sig");
        jwk.put("alg", "EdDSA");
        jwk.put("kid", config.getKid());
        return jwk;
    }

    private byte[] signature(String signingInput) {
        try {
            Signature signature = Signature.getInstance("Ed25519");
            signature.initSign(keys.privateKey());
            signature.update(signingInput.getBytes(StandardCharsets.US_ASCII));
            return signature.sign();
        } catch (Exception e) {
            throw new IllegalStateException("could not sign licence token", e);
        }
    }

    private String encode(Map<String, Object> value) {
        try {
            return BASE64URL.encodeToString(objectMapper.writeValueAsBytes(value));
        } catch (Exception e) {
            throw new IllegalStateException("could not serialise licence token", e);
        }
    }
}
