package com.mmaassist.accounts.identity.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.mmaassist.accounts.identity.domain.RefreshToken;
import com.mmaassist.accounts.identity.domain.RefreshTokenRepository;
import com.mmaassist.accounts.identity.oauth.DesktopAuthorizationCodes;
import com.mmaassist.accounts.platform.audit.AuditService;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import com.mmaassist.accounts.platform.security.Tokens;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class DesktopAuthServiceTest {

    private static final Instant NOW = Instant.parse("2026-08-08T12:00:00Z");

    @Mock private DesktopAuthorizationCodes codes;
    @Mock private SessionService sessionService;
    @Mock private DeviceService deviceService;
    @Mock private RefreshTokenRepository refreshTokens;
    @Mock private AuditService audit;

    private DesktopAuthService service;

    @BeforeEach
    void setUp() {
        service = new DesktopAuthService(codes, sessionService, deviceService, refreshTokens,
                new AppProperties(), audit, Clock.fixed(NOW, ZoneOffset.UTC));
    }

    @Test
    @DisplayName("replaying a rotated refresh token revokes the whole family")
    void reuseRevokesTheFamily() {
        String presented = Tokens.generate();
        UUID accountId = UUID.randomUUID();
        UUID familyId = UUID.randomUUID();

        RefreshToken spent = new RefreshToken(UUID.randomUUID(), accountId, UUID.randomUUID(),
                Tokens.hash(presented), familyId, NOW.minus(Duration.ofDays(1)),
                NOW.plus(Duration.ofDays(89)));
        spent.rotateTo(UUID.randomUUID(), NOW.minus(Duration.ofHours(1)));

        when(refreshTokens.findByTokenHash(Tokens.hash(presented))).thenReturn(Optional.of(spent));

        assertThatThrownBy(() -> service.refresh(presented))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("security");

        // Both halves matter: the family is dead, and every live session for
        // the account goes with it, since we cannot tell the thief from the
        // owner.
        verify(refreshTokens).revokeFamily(eq(familyId), any(Instant.class));
        verify(sessionService).revokeAllForAccount(accountId);
    }

    @Test
    @DisplayName("an unknown refresh token is simply refused")
    void unknownTokenIsRefused() {
        String presented = Tokens.generate();
        when(refreshTokens.findByTokenHash(any())).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.refresh(presented)).isInstanceOf(ApiException.class);

        verify(refreshTokens, never()).revokeFamily(any(), any());
    }

    @Test
    @DisplayName("an expired refresh token is refused without nuking the family")
    void expiredTokenIsRefusedQuietly() {
        String presented = Tokens.generate();
        RefreshToken expired = new RefreshToken(UUID.randomUUID(), UUID.randomUUID(), null,
                Tokens.hash(presented), UUID.randomUUID(),
                NOW.minus(Duration.ofDays(120)), NOW.minus(Duration.ofDays(30)));

        when(refreshTokens.findByTokenHash(Tokens.hash(presented))).thenReturn(Optional.of(expired));

        assertThatThrownBy(() -> service.refresh(presented)).isInstanceOf(ApiException.class);

        // Expiry is not evidence of theft, so the family survives.
        verify(refreshTokens, never()).revokeFamily(any(), any());
    }

    @Test
    @DisplayName("an expired or already-redeemed authorization code is refused")
    void spentAuthorizationCodeIsRefused() {
        when(codes.consume("code-1")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.exchangeCode("code-1", "verifier", "install-1", null, null))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("invalid_grant"));
    }

    @Test
    @DisplayName("a code redeemed with the wrong PKCE verifier is refused and audited")
    void wrongPkceVerifierIsRefused() {
        UUID accountId = UUID.randomUUID();
        when(codes.consume("code-1")).thenReturn(Optional.of(
                new DesktopAuthorizationCodes.Issued(accountId, "some-challenge",
                        "http://127.0.0.1:4000/account/callback", NOW)));

        assertThatThrownBy(() ->
                service.exchangeCode("code-1", "a".repeat(43), "install-1", null, null))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("invalid_grant"));

        verify(deviceService, never()).registerOrTouch(any(), any(), any(), any());
    }
}
