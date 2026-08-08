package com.mmaassist.accounts.platform.web;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Response headers this service sets on everything it serves.
 *
 * <p>Spring Security would supply these; it is deliberately not on the
 * classpath (see README, "no Spring Security"), so they are set explicitly
 * rather than assumed.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class SecurityHeadersFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.setHeader("X-Frame-Options", "DENY");
        response.setHeader("Referrer-Policy", "no-referrer");
        response.setHeader("Cross-Origin-Opener-Policy", "same-origin");

        // API responses carry entitlement state and personal data. A shared
        // cache holding "tier: pro" and replaying it to the next visitor is a
        // failure mode worth spending a header on.
        if (request.getRequestURI().startsWith("/v1/")) {
            response.setHeader("Cache-Control", "no-store");
        }

        chain.doFilter(request, response);
    }
}
