package com.mmaassist.accounts.billing.web;

import com.mmaassist.accounts.billing.service.CheckoutService;
import com.mmaassist.accounts.platform.security.AuthPrincipal;
import com.mmaassist.accounts.platform.security.RateLimiter;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.time.Duration;
import java.util.Map;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/v1")
public class CheckoutController {

    private static final int CHECKOUT_LIMIT = 5;
    private static final Duration WINDOW = Duration.ofMinutes(1);

    private final CheckoutService checkoutService;
    private final RateLimiter rateLimiter;

    public CheckoutController(CheckoutService checkoutService, RateLimiter rateLimiter) {
        this.checkoutService = checkoutService;
        this.rateLimiter = rateLimiter;
    }

    /**
     * Starts a purchase.
     *
     * <p>The body names a plan, never a price or an amount. A client that could
     * name its own price would be a client that could set it.
     */
    @PostMapping("/checkout")
    public Map<String, String> checkout(@Valid @RequestBody CheckoutRequest body,
                                        AuthPrincipal principal) {
        // Keyed by account, not IP: creating Stripe sessions in a loop costs us
        // API budget whoever is doing it.
        rateLimiter.require("checkout:" + principal.accountId(), CHECKOUT_LIMIT, WINDOW);
        return Map.of("checkoutUrl", checkoutService.startCheckout(principal.accountId(), body.planId()));
    }

    /**
     * Opens Stripe's Billing Portal.
     *
     * <p>Cancelling, updating a card and downloading invoices all live there.
     * Rebuilding any of it here would mean holding more payment state, for a
     * worse result.
     */
    @PostMapping("/portal")
    public Map<String, String> portal(AuthPrincipal principal) {
        rateLimiter.require("portal:" + principal.accountId(), CHECKOUT_LIMIT, WINDOW);
        return Map.of("portalUrl", checkoutService.portalUrl(principal.accountId()));
    }

    public record CheckoutRequest(@NotBlank String planId) {
    }
}
