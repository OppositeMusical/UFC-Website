package com.mmaassist.accounts.identity.web;

import com.mmaassist.accounts.identity.domain.Account;
import com.mmaassist.accounts.identity.oauth.OAuthBroker;
import com.mmaassist.accounts.identity.oauth.OAuthBrokers;
import com.mmaassist.accounts.identity.oauth.OAuthProfile;
import com.mmaassist.accounts.identity.oauth.DesktopAuthorizationCodes;
import com.mmaassist.accounts.identity.oauth.PendingAuthorizationStore;
import com.mmaassist.accounts.identity.service.AccountService;
import com.mmaassist.accounts.identity.service.DesktopAuthService;
import com.mmaassist.accounts.identity.service.SessionService;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import com.mmaassist.accounts.platform.security.AuthPrincipal;
import com.mmaassist.accounts.platform.security.RateLimiter;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.net.URI;
import java.time.Duration;
import java.util.Map;
import java.util.Optional;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/v1/auth")
public class AuthController {

    private static final Duration RATE_WINDOW = Duration.ofMinutes(1);
    private static final int START_LIMIT = 10;
    private static final int TOKEN_LIMIT = 20;

    private final OAuthBrokers brokers;
    private final PendingAuthorizationStore pending;
    private final DesktopAuthorizationCodes desktopCodes;
    private final AccountService accountService;
    private final SessionService sessionService;
    private final DesktopAuthService desktopAuthService;
    private final AppProperties properties;
    private final RateLimiter rateLimiter;

    public AuthController(OAuthBrokers brokers, PendingAuthorizationStore pending,
                          DesktopAuthorizationCodes desktopCodes, AccountService accountService,
                          SessionService sessionService, DesktopAuthService desktopAuthService,
                          AppProperties properties, RateLimiter rateLimiter) {
        this.brokers = brokers;
        this.pending = pending;
        this.desktopCodes = desktopCodes;
        this.accountService = accountService;
        this.sessionService = sessionService;
        this.desktopAuthService = desktopAuthService;
        this.properties = properties;
        this.rateLimiter = rateLimiter;
    }

    /** Which sign-in buttons the site and the desktop app should render. */
    @GetMapping("/providers")
    public Map<String, Object> providers() {
        return Map.of("providers", brokers.configuredProviders());
    }

    /** Browser sign-in. Ends with a session cookie and a redirect back to the site. */
    @GetMapping("/{provider}/start")
    public ResponseEntity<Void> startWebLogin(@PathVariable String provider,
                                              @RequestParam(required = false) String redirect,
                                              HttpServletRequest request) {
        rateLimiter.require("auth-start:" + clientIp(request), START_LIMIT, RATE_WINDOW);

        OAuthBroker broker = brokers.require(provider);
        String state = pending.start(broker.provider(), PendingAuthorizationStore.Flow.WEB,
                safeReturnPath(redirect), null, null);
        return redirectTo(broker.authorizationUri(state, callbackUri(broker.provider())));
    }

    /**
     * Desktop sign-in (RFC 8252). The app opens this in the system browser —
     * never an embedded webview, which Google blocks for OAuth and which a user
     * has no way to distinguish from a phishing page.
     */
    @GetMapping("/desktop/start")
    public ResponseEntity<Void> startDesktopLogin(@RequestParam String provider,
                                                  @RequestParam("code_challenge") String codeChallenge,
                                                  @RequestParam(value = "code_challenge_method",
                                                          defaultValue = "S256") String method,
                                                  @RequestParam("redirect_uri") String redirectUri,
                                                  HttpServletRequest request) {
        rateLimiter.require("auth-start:" + clientIp(request), START_LIMIT, RATE_WINDOW);

        if (!"S256".equals(method)) {
            // `plain` offers no protection whatsoever; accepting it would let a
            // downgrade undo PKCE entirely.
            throw ApiException.badRequest("unsupported_challenge_method",
                    "Only S256 PKCE challenges are accepted.");
        }
        if (codeChallenge == null || codeChallenge.isBlank()) {
            throw ApiException.badRequest("invalid_request", "A PKCE code challenge is required.");
        }
        DesktopAuthService.requireLoopbackRedirect(redirectUri);

        OAuthBroker broker = brokers.require(provider);
        String state = pending.start(broker.provider(), PendingAuthorizationStore.Flow.DESKTOP,
                null, codeChallenge, redirectUri);
        return redirectTo(broker.authorizationUri(state, callbackUri(broker.provider())));
    }

    /** Where both flows come back to. What happens next depends on which one started. */
    @GetMapping("/{provider}/callback")
    public ResponseEntity<Void> callback(@PathVariable String provider,
                                         @RequestParam(required = false) String code,
                                         @RequestParam(required = false) String state,
                                         @RequestParam(required = false) String error,
                                         HttpServletRequest request) {
        PendingAuthorizationStore.Pending flow = pending.consume(state)
                .orElseThrow(() -> ApiException.badRequest("invalid_state",
                        "That sign-in attempt expired or was already used. Start again."));

        // The user pressed Cancel on the consent screen. That is not an error
        // worth a stack trace or a scary page - send them back where they came from.
        if (error != null && !error.isBlank()) {
            return redirectTo(properties.getSiteOrigin() + "/login?error=" + encode(error));
        }
        if (code == null || code.isBlank()) {
            throw ApiException.badRequest("invalid_request", "No authorization code was returned.");
        }
        if (!flow.provider().equals(provider)) {
            throw ApiException.badRequest("invalid_state", "Sign-in provider mismatch.");
        }

        OAuthBroker broker = brokers.require(provider);
        OAuthProfile profile = broker.exchangeCode(code, callbackUri(provider));
        Account account = accountService.resolveFromProfile(profile);

        if (flow.flow() == PendingAuthorizationStore.Flow.DESKTOP) {
            String desktopCode = desktopCodes.issue(account.getId(), flow.codeChallenge(),
                    flow.loopbackRedirectUri());
            return redirectTo(flow.loopbackRedirectUri() + "?code=" + encode(desktopCode));
        }

        SessionService.Issued issued = sessionService.createWebSession(
                account.getId(), request.getHeader(HttpHeaders.USER_AGENT), clientIp(request));

        return ResponseEntity.status(302)
                .location(URI.create(properties.getSiteOrigin() + flow.returnPath()))
                .header(HttpHeaders.SET_COOKIE, sessionCookie(issued.token()).toString())
                .build();
    }

    /** Desktop code exchange. Returns tokens; the licence is a separate call. */
    @PostMapping("/desktop/token")
    public DesktopTokenResponse desktopToken(@Valid @RequestBody DesktopTokenRequest body,
                                             HttpServletRequest request) {
        rateLimiter.require("auth-token:" + clientIp(request), TOKEN_LIMIT, RATE_WINDOW);

        DesktopAuthService.IssuedTokens tokens = desktopAuthService.exchangeCode(
                body.code(), body.codeVerifier(), body.installId(), body.deviceName(), body.appVersion());
        return DesktopTokenResponse.from(tokens);
    }

    @PostMapping("/refresh")
    public DesktopTokenResponse refresh(@Valid @RequestBody RefreshRequest body,
                                        HttpServletRequest request) {
        rateLimiter.require("auth-refresh:" + clientIp(request), TOKEN_LIMIT, RATE_WINDOW);
        return DesktopTokenResponse.from(desktopAuthService.refresh(body.refreshToken()));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(Optional<AuthPrincipal> principal) {
        principal.ifPresent(p -> sessionService.revoke(p.sessionId()));
        // Clearing the cookie is unconditional: a request carrying a session
        // this service no longer recognises should still end up cookie-free.
        return ResponseEntity.noContent()
                .header(HttpHeaders.SET_COOKIE, expiredSessionCookie().toString())
                .build();
    }

    // -- helpers -------------------------------------------------------------

    private ResponseEntity<Void> redirectTo(String location) {
        return ResponseEntity.status(302).location(URI.create(location)).build();
    }

    private String callbackUri(String provider) {
        return properties.getApiBaseUrl() + "/v1/auth/" + provider + "/callback";
    }

    private ResponseCookie sessionCookie(String token) {
        ResponseCookie.ResponseCookieBuilder builder = ResponseCookie
                .from(properties.getSession().getCookieName(), token)
                .httpOnly(true)
                .secure(properties.getSession().isCookieSecure())
                // Lax, not None: the API and the site share a registrable
                // domain, so the cookie still travels, and Lax is what stops a
                // cross-site POST from riding on it. That is the CSRF defence
                // for this service - there is no token to check.
                .sameSite("Lax")
                .path("/")
                .maxAge(properties.getSession().getTtl());
        if (!properties.getSession().getCookieDomain().isBlank()) {
            builder.domain(properties.getSession().getCookieDomain());
        }
        return builder.build();
    }

    private ResponseCookie expiredSessionCookie() {
        ResponseCookie.ResponseCookieBuilder builder = ResponseCookie
                .from(properties.getSession().getCookieName(), "")
                .httpOnly(true)
                .secure(properties.getSession().isCookieSecure())
                .sameSite("Lax")
                .path("/")
                .maxAge(0);
        if (!properties.getSession().getCookieDomain().isBlank()) {
            builder.domain(properties.getSession().getCookieDomain());
        }
        return builder.build();
    }

    /**
     * Only same-site relative paths are ever echoed into a redirect.
     *
     * <p>A {@code redirect} parameter that reaches {@code Location:} unchecked
     * is an open redirect, and an open redirect on an auth endpoint is a
     * phishing primitive: the link genuinely is our domain right up until it
     * bounces. Rejected: absolute URLs, protocol-relative {@code //evil.com},
     * and backslashes, which some browsers normalise to forward slashes.
     */
    static String safeReturnPath(String raw) {
        if (raw == null || raw.isBlank()) {
            return "/account";
        }
        if (!raw.startsWith("/") || raw.startsWith("//") || raw.contains("\\")) {
            return "/account";
        }
        return raw;
    }

    private static String clientIp(HttpServletRequest request) {
        // server.forward-headers-strategy=framework has already applied
        // X-Forwarded-For, so this is the real client address behind Railway.
        String addr = request.getRemoteAddr();
        return addr == null ? "unknown" : addr;
    }

    private static String encode(String value) {
        return java.net.URLEncoder.encode(value, java.nio.charset.StandardCharsets.UTF_8);
    }

    // -- payloads ------------------------------------------------------------

    public record DesktopTokenRequest(
            @NotBlank String code,
            @NotBlank String codeVerifier,
            @NotBlank String installId,
            String deviceName,
            String appVersion) {
    }

    public record RefreshRequest(@NotBlank String refreshToken) {
    }

    public record DesktopTokenResponse(
            String accessToken,
            String tokenType,
            long expiresIn,
            String refreshToken,
            String accountId,
            String deviceId) {

        static DesktopTokenResponse from(DesktopAuthService.IssuedTokens tokens) {
            long expiresIn = Duration.between(java.time.Instant.now(), tokens.accessTokenExpiresAt())
                    .getSeconds();
            return new DesktopTokenResponse(tokens.accessToken(), "Bearer", Math.max(expiresIn, 0),
                    tokens.refreshToken(), tokens.accountId().toString(),
                    tokens.deviceId() == null ? null : tokens.deviceId().toString());
        }
    }
}
