package com.mmaassist.accounts.identity.oauth;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class PkceTest {

    /** RFC 7636 appendix B's worked example, which pins our encoding to the spec's. */
    private static final String RFC_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
    private static final String RFC_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM";

    @Test
    @DisplayName("matches the challenge from RFC 7636")
    void matchesRfcExample() {
        assertThat(Pkce.challengeFor(RFC_VERIFIER)).isEqualTo(RFC_CHALLENGE);
        assertThat(Pkce.verify(RFC_VERIFIER, RFC_CHALLENGE)).isTrue();
    }

    @Test
    void rejectsTheWrongVerifier() {
        assertThat(Pkce.verify("a".repeat(43), RFC_CHALLENGE)).isFalse();
    }

    @Test
    @DisplayName("a verifier shorter than the spec's minimum is refused, not merely mismatched")
    void rejectsShortVerifier() {
        String tooShort = "short";
        assertThat(Pkce.verify(tooShort, Pkce.challengeFor(tooShort))).isFalse();
    }

    @Test
    void rejectsOverlongVerifier() {
        String tooLong = "a".repeat(129);
        assertThat(Pkce.verify(tooLong, Pkce.challengeFor(tooLong))).isFalse();
    }

    @Test
    void rejectsNulls() {
        assertThat(Pkce.verify(null, RFC_CHALLENGE)).isFalse();
        assertThat(Pkce.verify(RFC_VERIFIER, null)).isFalse();
    }

    @Test
    @DisplayName("the plain method is not accepted: passing the verifier as the challenge fails")
    void plainDowngradeIsRefused() {
        assertThat(Pkce.verify(RFC_VERIFIER, RFC_VERIFIER)).isFalse();
    }
}
