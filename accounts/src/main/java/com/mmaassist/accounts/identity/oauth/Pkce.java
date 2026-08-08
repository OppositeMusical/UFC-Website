package com.mmaassist.accounts.identity.oauth;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

/**
 * PKCE (RFC 7636), S256 only.
 *
 * <p>The desktop app is a public client: it ships its client id to every user
 * and can keep no secret. PKCE is what stops another local process that manages
 * to intercept the loopback redirect from redeeming the authorization code —
 * it would also need the verifier, which never leaves the app's memory.
 *
 * <p>The {@code plain} method is deliberately unsupported. It provides no
 * protection at all, and accepting it would let a downgrade undo the whole
 * mechanism.
 */
public final class Pkce {

    private static final int MIN_VERIFIER_LENGTH = 43;
    private static final int MAX_VERIFIER_LENGTH = 128;

    private Pkce() {
    }

    public static boolean verify(String verifier, String expectedChallenge) {
        if (verifier == null || expectedChallenge == null) {
            return false;
        }
        if (verifier.length() < MIN_VERIFIER_LENGTH || verifier.length() > MAX_VERIFIER_LENGTH) {
            return false;
        }
        String actual = challengeFor(verifier);
        // Constant-time: the challenge is not secret, but comparing it in
        // variable time is free to avoid and costs nothing to get right.
        return MessageDigest.isEqual(
                actual.getBytes(StandardCharsets.US_ASCII),
                expectedChallenge.getBytes(StandardCharsets.US_ASCII));
    }

    public static String challengeFor(String verifier) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(verifier.getBytes(StandardCharsets.US_ASCII));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is required by the JLS and must exist", e);
        }
    }
}
