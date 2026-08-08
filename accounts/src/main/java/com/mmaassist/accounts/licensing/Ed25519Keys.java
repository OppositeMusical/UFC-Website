package com.mmaassist.accounts.licensing;

import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.spec.EdECPrivateKeySpec;
import java.security.spec.NamedParameterSpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Arrays;
import java.util.Base64;

/**
 * Ed25519 key handling, using the JDK's own provider (Ed25519 has been built in
 * since Java 15).
 *
 * <p>No BouncyCastle, no Nimbus, no Tink. The service only ever <em>signs</em>
 * — the desktop app is the verifier, in Python — so the Java side needs exactly
 * one primitive, and pulling a JOSE stack in for it would be more moving parts
 * than the whole feature.
 *
 * <h2>Key format</h2>
 *
 * <p>{@code LICENCE_SIGNING_KEY} is base64 of <b>64 bytes</b>: the 32-byte seed
 * followed by the 32-byte public key, which is the layout libsodium and most
 * Ed25519 tooling use. Both halves are stored because the JDK offers no way to
 * derive a public key from a seed — that needs a scalar multiplication the
 * public API does not expose. Storing the pair sidesteps it entirely, and the
 * pairing is checked at load time so a mismatched blob fails at startup rather
 * than producing tokens nothing can verify.
 *
 * <p>Generate one with:
 * {@snippet : java -cp target/classes com.mmaassist.accounts.licensing.Ed25519Keys }
 */
public final class Ed25519Keys {

    /**
     * The fixed DER prefix of an Ed25519 SubjectPublicKeyInfo. The last 32
     * bytes of such a structure are the raw key, and prefixing raw bytes with
     * this turns them back into something {@code X509EncodedKeySpec} accepts.
     */
    private static final byte[] SPKI_PREFIX = {
            0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00
    };

    public static final int RAW_KEY_LENGTH = 32;

    /**
     * @param privateKey for signing
     * @param publicKey  for the JWKS document
     * @param rawPublic  the 32 raw bytes, which is what a JWK's {@code x} holds
     */
    public record Keys(PrivateKey privateKey, PublicKey publicKey, byte[] rawPublic) {

        public String publicKeyBase64Url() {
            return Base64.getUrlEncoder().withoutPadding().encodeToString(rawPublic);
        }
    }

    private Ed25519Keys() {
    }

    /** Parses the configured 64-byte blob. */
    public static Keys fromEncoded(String base64) {
        byte[] material = decode(base64);
        if (material.length != RAW_KEY_LENGTH * 2) {
            throw new IllegalArgumentException(
                    "LICENCE_SIGNING_KEY must decode to 64 bytes (32-byte seed + 32-byte public key), got "
                            + material.length);
        }
        byte[] seed = Arrays.copyOfRange(material, 0, RAW_KEY_LENGTH);
        byte[] rawPublic = Arrays.copyOfRange(material, RAW_KEY_LENGTH, RAW_KEY_LENGTH * 2);

        try {
            PrivateKey privateKey = KeyFactory.getInstance("Ed25519")
                    .generatePrivate(new EdECPrivateKeySpec(NamedParameterSpec.ED25519, seed));
            PublicKey publicKey = publicKeyFromRaw(rawPublic);
            Keys keys = new Keys(privateKey, publicKey, rawPublic);
            verifyPairing(keys);
            return keys;
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalArgumentException("LICENCE_SIGNING_KEY is not a usable Ed25519 key", e);
        }
    }

    /** A fresh keypair, for development and for the generator below. */
    public static Keys generate() {
        try {
            KeyPair pair = KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
            return new Keys(pair.getPrivate(), pair.getPublic(), rawPublicOf(pair.getPublic()));
        } catch (Exception e) {
            throw new IllegalStateException("Ed25519 is unavailable on this JVM", e);
        }
    }

    /** The 64-byte blob for a keypair, ready to paste into an environment variable. */
    public static String encode(Keys keys) {
        byte[] pkcs8 = keys.privateKey().getEncoded();
        // A PKCS#8-encoded Ed25519 private key ends with the 32-byte seed.
        byte[] seed = Arrays.copyOfRange(pkcs8, pkcs8.length - RAW_KEY_LENGTH, pkcs8.length);
        byte[] combined = new byte[RAW_KEY_LENGTH * 2];
        System.arraycopy(seed, 0, combined, 0, RAW_KEY_LENGTH);
        System.arraycopy(keys.rawPublic(), 0, combined, RAW_KEY_LENGTH, RAW_KEY_LENGTH);
        return Base64.getEncoder().encodeToString(combined);
    }

    static PublicKey publicKeyFromRaw(byte[] rawPublic) throws Exception {
        byte[] spki = new byte[SPKI_PREFIX.length + RAW_KEY_LENGTH];
        System.arraycopy(SPKI_PREFIX, 0, spki, 0, SPKI_PREFIX.length);
        System.arraycopy(rawPublic, 0, spki, SPKI_PREFIX.length, RAW_KEY_LENGTH);
        return KeyFactory.getInstance("Ed25519").generatePublic(new X509EncodedKeySpec(spki));
    }

    static byte[] rawPublicOf(PublicKey publicKey) {
        byte[] encoded = publicKey.getEncoded();
        return Arrays.copyOfRange(encoded, encoded.length - RAW_KEY_LENGTH, encoded.length);
    }

    /**
     * Signs and verifies a probe so a seed and public key that do not belong
     * together are caught at startup, not by every desktop install at once.
     */
    private static void verifyPairing(Keys keys) {
        try {
            byte[] probe = "licence-key-pairing-check".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            java.security.Signature signer = java.security.Signature.getInstance("Ed25519");
            signer.initSign(keys.privateKey());
            signer.update(probe);
            byte[] signature = signer.sign();

            java.security.Signature verifier = java.security.Signature.getInstance("Ed25519");
            verifier.initVerify(keys.publicKey());
            verifier.update(probe);
            if (!verifier.verify(signature)) {
                throw new IllegalArgumentException(
                        "LICENCE_SIGNING_KEY's seed and public key do not match");
            }
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalArgumentException("LICENCE_SIGNING_KEY failed its self-check", e);
        }
    }

    private static byte[] decode(String value) {
        String trimmed = value.trim();
        try {
            return Base64.getDecoder().decode(trimmed);
        } catch (IllegalArgumentException e) {
            // Tolerate the URL-safe alphabet: it is what half of the tooling
            // that produces these emits, and the failure is otherwise cryptic.
            return Base64.getUrlDecoder().decode(trimmed);
        }
    }

    /** Prints a fresh key blob. Handy once per environment, then never again. */
    public static void main(String[] args) {
        Keys keys = generate();
        System.out.println("LICENCE_SIGNING_KEY=" + encode(keys));
        System.out.println("public key (base64url, for the desktop app): " + keys.publicKeyBase64Url());
    }
}
