package com.mmaassist.accounts.platform.security;

import com.mmaassist.accounts.platform.config.AppProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Resolves the caller from either an {@code Authorization: Bearer} header
 * (desktop) or the session cookie (browser), and parks the result on the
 * request for {@link AuthPrincipalArgumentResolver} to pick up.
 *
 * <p>This filter never rejects anything. Endpoints declare their own
 * requirement by taking an {@link AuthPrincipal} parameter, which keeps "is
 * this endpoint public?" visible in the controller signature instead of in a
 * URL-pattern table that drifts out of step with the routes.
 */
@Component
public class AuthenticationFilter extends OncePerRequestFilter {

    public static final String PRINCIPAL_ATTRIBUTE = "com.mmaassist.principal";

    private static final String BEARER_PREFIX = "Bearer ";

    private final SessionAuthenticator authenticator;
    private final AppProperties properties;

    public AuthenticationFilter(SessionAuthenticator authenticator, AppProperties properties) {
        this.authenticator = authenticator;
        this.properties = properties;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        extractToken(request)
                .flatMap(authenticator::authenticate)
                .ifPresent(principal -> request.setAttribute(PRINCIPAL_ATTRIBUTE, principal));
        chain.doFilter(request, response);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // The Stripe webhook authenticates by signature, not by session, and
        // actuator has no notion of a user.
        String path = request.getRequestURI();
        return path.startsWith("/webhooks/") || path.startsWith("/actuator/");
    }

    private java.util.Optional<String> extractToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith(BEARER_PREFIX)) {
            String value = header.substring(BEARER_PREFIX.length()).trim();
            return value.isEmpty() ? java.util.Optional.empty() : java.util.Optional.of(value);
        }

        Cookie[] cookies = request.getCookies();
        if (cookies != null) {
            for (Cookie cookie : cookies) {
                if (properties.getSession().getCookieName().equals(cookie.getName())) {
                    return java.util.Optional.ofNullable(cookie.getValue()).filter(v -> !v.isBlank());
                }
            }
        }
        return java.util.Optional.empty();
    }
}
