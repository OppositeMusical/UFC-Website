package com.mmaassist.accounts.platform.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * Opaque bearer credentials: session cookies, refresh tokens, authorization
 * codes.
 *
 * <p>Only the SHA-256 of a token is ever persisted. A plain hash (rather than a
 * password KDF) is right here and wrong for passwords: these are 256 bits of
 * output from a CSPRNG, so there is no dictionary to attack and no work factor
 * worth paying on every request.
 */
public final class Tokens {

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final Base64.Encoder ENCODER = Base64.getUrlEncoder().withoutPadding();

    private Tokens() {
    }

    /** A fresh 256-bit token, base64url encoded. */
    public static String generate() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return ENCODER.encodeToString(bytes);
    }

    public static byte[] hash(String token) {
        try {
            return MessageDigest.getInstance("SHA-256")
                    .digest(token.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is required by the JLS and must exist", e);
        }
    }
}
