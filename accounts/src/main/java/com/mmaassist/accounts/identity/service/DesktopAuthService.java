package com.mmaassist.accounts.identity.service;

import com.mmaassist.accounts.identity.domain.Device;
import com.mmaassist.accounts.identity.domain.RefreshToken;
import com.mmaassist.accounts.identity.domain.RefreshTokenRepository;
import com.mmaassist.accounts.identity.oauth.DesktopAuthorizationCodes;
import com.mmaassist.accounts.identity.oauth.Pkce;
import com.mmaassist.accounts.platform.audit.AuditService;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import com.mmaassist.accounts.platform.security.Tokens;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** The desktop half of sign-in: code exchange and refresh-token rotation. */
@Service
public class DesktopAuthService {

    private static final Logger log = LoggerFactory.getLogger(DesktopAuthService.class);

    /**
     * The only redirect target the desktop flow will ever accept.
     *
     * <p>Loopback literal only. {@code localhost} is excluded deliberately: it
     * is a name, and on a machine with a doctored hosts file or an unusual
     * resolver it can point somewhere that is not this computer — at which
     * point the authorization code leaves the machine.
     */
    private static final Pattern LOOPBACK_REDIRECT =
            Pattern.compile("^http://127\\.0\\.0\\.1:(\\d{1,5})/account/callback$");

    public record IssuedTokens(
            String accessToken, Instant accessTokenExpiresAt,
            String refreshToken, Instant refreshTokenExpiresAt,
            UUID accountId, UUID deviceId) {
    }

    private final DesktopAuthorizationCodes codes;
    private final SessionService sessionService;
    private final DeviceService deviceService;
    private final RefreshTokenRepository refreshTokens;
    private final AppProperties properties;
    private final AuditService audit;
    private final Clock clock;

    public DesktopAuthService(DesktopAuthorizationCodes codes, SessionService sessionService,
                              DeviceService deviceService, RefreshTokenRepository refreshTokens,
                              AppProperties properties, AuditService audit, Clock clock) {
        this.codes = codes;
        this.sessionService = sessionService;
        this.deviceService = deviceService;
        this.refreshTokens = refreshTokens;
        this.properties = properties;
        this.audit = audit;
        this.clock = clock;
    }

    /** Validates the app's callback URL before we ever redirect a browser at it. */
    public static String requireLoopbackRedirect(String redirectUri) {
        if (redirectUri == null || !LOOPBACK_REDIRECT.matcher(redirectUri).matches()) {
            throw ApiException.badRequest("invalid_redirect_uri",
                    "The desktop callback must be http://127.0.0.1:<port>/account/callback");
        }
        return redirectUri;
    }

    @Transactional
    public IssuedTokens exchangeCode(String code, String codeVerifier, String installId,
                                     String deviceName, String appVersion) {
        DesktopAuthorizationCodes.Issued issued = codes.consume(code)
                .orElseThrow(() -> ApiException.badRequest("invalid_grant",
                        "That sign-in code has expired or was already used. Sign in again."));

        if (!Pkce.verify(codeVerifier, issued.codeChallenge())) {
            // Someone redeemed a code they intercepted but cannot prove they
            // requested. Worth an audit row: it is otherwise invisible.
            audit.record(issued.accountId(), AuditService.ACTOR_SYSTEM, "desktop.pkce_failed", Map.of());
            log.warn("PKCE verification failed for account {}", issued.accountId());
            throw ApiException.badRequest("invalid_grant", "Sign-in verification failed. Try again.");
        }

        Device device = deviceService.registerOrTouch(issued.accountId(), installId, deviceName, appVersion);
        return issueFor(issued.accountId(), device.getId(), UUID.randomUUID()).tokens();
    }

    /**
     * Rotates a refresh token.
     *
     * <p>Presenting one that has already been exchanged means either a replay
     * or a stolen token, and from here the two are indistinguishable — so the
     * entire family is revoked and that install signs in again. Inconvenient
     * exactly once, against a stolen token that would otherwise work for ninety
     * days.
     */
    @Transactional
    public IssuedTokens refresh(String presentedToken) {
        Instant now = clock.instant();
        RefreshToken token = refreshTokens.findByTokenHash(Tokens.hash(presentedToken))
                .orElseThrow(() -> ApiException.unauthorized("Sign in again."));

        if (token.isSpent()) {
            refreshTokens.revokeFamily(token.getFamilyId(), now);
            sessionService.revokeAllForAccount(token.getAccountId());
            audit.record(token.getAccountId(), AuditService.ACTOR_SYSTEM, "refresh_token.reused",
                    Map.of("familyId", token.getFamilyId().toString()));
            log.warn("refresh token reuse detected for account {}, family {} revoked",
                    token.getAccountId(), token.getFamilyId());
            throw ApiException.unauthorized("Your session was ended for security. Sign in again.");
        }

        if (!token.isUsable(now)) {
            throw ApiException.unauthorized("Sign in again.");
        }

        Minted minted = issueFor(token.getAccountId(), token.getDeviceId(), token.getFamilyId());
        // Marking the old token spent is what makes the *next* replay of it
        // detectable, so it has to point at the successor's id.
        token.rotateTo(minted.refreshTokenId(), now);
        return minted.tokens();
    }

    /** The tokens handed back, plus the row id the predecessor has to point at. */
    private record Minted(IssuedTokens tokens, UUID refreshTokenId) {
    }

    private Minted issueFor(UUID accountId, UUID deviceId, UUID familyId) {
        Instant now = clock.instant();
        SessionService.Issued session = sessionService.createDesktopSession(accountId, deviceId);

        String rawRefresh = Tokens.generate();
        UUID refreshTokenId = UUID.randomUUID();
        Instant refreshExpiry = now.plus(properties.getDesktop().getRefreshTokenTtl());
        refreshTokens.save(new RefreshToken(refreshTokenId, accountId, deviceId,
                Tokens.hash(rawRefresh), familyId, now, refreshExpiry));

        return new Minted(
                new IssuedTokens(session.token(), session.session().getExpiresAt(),
                        rawRefresh, refreshExpiry, accountId, deviceId),
                refreshTokenId);
    }
}
