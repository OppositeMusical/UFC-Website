package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.Plan;
import com.mmaassist.accounts.billing.domain.PlanRepository;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * Startup check that the seeded plan catalogue has been pointed at real Stripe
 * prices.
 *
 * <p>Price ids differ between test mode and live mode, so the migration seeds
 * placeholders. Saying so at boot beats the alternative discovery route, which
 * is a customer clicking Buy and landing on a Stripe error page.
 *
 * <p>A warning rather than a startup failure: a deployment with no Stripe keys
 * at all is a perfectly good way to run the identity half of this service.
 */
@Component
public class PlanCatalogueValidator {

    private static final Logger log = LoggerFactory.getLogger(PlanCatalogueValidator.class);

    private final PlanRepository plans;
    private final StripeGateway gateway;

    public PlanCatalogueValidator(PlanRepository plans, StripeGateway gateway) {
        this.plans = plans;
        this.gateway = gateway;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void checkPlans() {
        if (!gateway.isConfigured()) {
            log.warn("Stripe is not configured - checkout and the billing portal are disabled.");
            return;
        }

        List<String> unconfigured = plans.findByActiveTrueOrderBySortOrderAsc().stream()
                .filter(Plan::hasPlaceholderPriceId)
                .map(Plan::getId)
                .toList();

        if (!unconfigured.isEmpty()) {
            log.error("These active plans still carry placeholder Stripe price ids and cannot be "
                    + "bought: {}. Update billing.plans.stripe_price_id for this environment.",
                    unconfigured);
        }
    }
}
