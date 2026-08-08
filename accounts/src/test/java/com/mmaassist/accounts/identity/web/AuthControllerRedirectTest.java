package com.mmaassist.accounts.identity.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.mmaassist.accounts.identity.service.DesktopAuthService;
import com.mmaassist.accounts.platform.error.ApiException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * An open redirect on a sign-in endpoint is a phishing primitive: the link is
 * genuinely our domain right up to the moment it bounces somewhere else.
 */
class AuthControllerRedirectTest {

    @ParameterizedTest
    @ValueSource(strings = {
            "https://evil.example/steal",   // absolute
            "//evil.example/steal",         // protocol-relative
            "/\\evil.example",              // backslash, which some browsers normalise to /
            "\\\\evil.example",
            "http://127.0.0.1/account",     // absolute, even to loopback
    })
    @DisplayName("off-site return paths fall back to /account")
    void rejectsOffsiteRedirects(String candidate) {
        assertThat(AuthController.safeReturnPath(candidate)).isEqualTo("/account");
    }

    @ParameterizedTest
    @ValueSource(strings = {"/account", "/pricing", "/checkout/success?session_id=cs_1"})
    void keepsRelativePaths(String candidate) {
        assertThat(AuthController.safeReturnPath(candidate)).isEqualTo(candidate);
    }

    @Test
    void defaultsWhenAbsent() {
        assertThat(AuthController.safeReturnPath(null)).isEqualTo("/account");
        assertThat(AuthController.safeReturnPath("  ")).isEqualTo("/account");
    }

    @Test
    @DisplayName("the desktop callback must be loopback on the exact expected path")
    void acceptsOnlyLoopbackCallback() {
        assertThat(DesktopAuthService.requireLoopbackRedirect("http://127.0.0.1:49731/account/callback"))
                .isEqualTo("http://127.0.0.1:49731/account/callback");
    }

    @ParameterizedTest
    @ValueSource(strings = {
            // `localhost` is a name, and on a machine with a doctored hosts file
            // it need not be this machine - at which point the code leaves.
            "http://localhost:49731/account/callback",
            "https://evil.example/account/callback",
            "http://127.0.0.1:49731/other/path",
            "http://127.0.0.1:49731/account/callback/../../evil",
            "http://127.0.0.2:49731/account/callback",
            "http://[::1]:49731/account/callback",
    })
    void rejectsEverythingElse(String candidate) {
        assertThatThrownBy(() -> DesktopAuthService.requireLoopbackRedirect(candidate))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode())
                        .isEqualTo("invalid_redirect_uri"));
    }
}
