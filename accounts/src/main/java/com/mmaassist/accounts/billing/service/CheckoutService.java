package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.Customer;
import com.mmaassist.accounts.billing.domain.CustomerRepository;
import com.mmaassist.accounts.billing.domain.Entitlement;
import com.mmaassist.accounts.billing.domain.Plan;
import com.mmaassist.accounts.billing.domain.PlanRepository;
import com.mmaassist.accounts.identity.service.AccountService;
import com.mmaassist.accounts.platform.audit.AuditService;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import com.mmaassist.accounts.platform.spi.EntitlementLookup;
import java.time.Clock;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CheckoutService {

    private final PlanRepository plans;
    private final CustomerRepository customers;
    private final StripeGateway gateway;
    private final AccountService accounts;
    private final EntitlementLookup entitlements;
    private final AppProperties properties;
    private final AuditService audit;
    private final Clock clock;

    public CheckoutService(PlanRepository plans, CustomerRepository customers, StripeGateway gateway,
                           AccountService accounts, EntitlementLookup entitlements,
                           AppProperties properties, AuditService audit, Clock clock) {
        this.plans = plans;
        this.customers = customers;
        this.gateway = gateway;
        this.accounts = accounts;
        this.entitlements = entitlements;
        this.properties = properties;
        this.audit = audit;
        this.clock = clock;
    }

    /** @return the Stripe-hosted URL to send the browser to. */
    @Transactional
    public String startCheckout(UUID accountId, String planId) {
        Plan plan = plans.findById(planId)
                .filter(Plan::isActive)
                .orElseThrow(() -> ApiException.notFound("unknown_plan", "That plan is not available."));

        if (plan.hasPlaceholderPriceId()) {
            // The seeded catalogue ships with placeholder price ids. Failing
            // loudly here beats sending a customer to a Stripe page that 404s.
            throw ApiException.unavailable("plan_not_configured",
                    "This plan is not connected to a live price yet.");
        }

        EntitlementLookup.Snapshot current = entitlements.forAccount(accountId);
        if (Entitlement.SOURCE_LIFETIME.equals(current.source())) {
            // Selling a subscription to somebody holding a perpetual licence is
            // taking money for nothing, and it is a refund request either way.
            throw ApiException.conflict("already_entitled",
                    "You already own a lifetime licence — there is nothing further to buy.");
        }

        String customerId = customers.findById(accountId)
                .map(Customer::getStripeCustomerId)
                .orElseGet(() -> createCustomer(accountId));

        String successUrl = properties.getSiteOrigin()
                + "/checkout/success?session_id={CHECKOUT_SESSION_ID}";
        String cancelUrl = properties.getSiteOrigin() + "/pricing";

        StripeGateway.CheckoutSession session =
                gateway.createCheckoutSession(accountId, customerId, plan, successUrl, cancelUrl);

        audit.record(accountId, AuditService.ACTOR_SYSTEM, "checkout.started",
                Map.of("planId", planId, "sessionId", session.id()));
        return session.url();
    }

    @Transactional
    public String portalUrl(UUID accountId) {
        String customerId = customers.findById(accountId)
                .map(Customer::getStripeCustomerId)
                .orElseThrow(() -> ApiException.notFound("no_billing_account",
                        "There is nothing to manage yet — you have not bought anything."));

        return gateway.createPortalSession(customerId, properties.getSiteOrigin() + "/account");
    }

    private String createCustomer(UUID accountId) {
        String email = accounts.require(accountId).getEmail();
        String stripeCustomerId = gateway.createCustomer(accountId, email);
        customers.save(new Customer(accountId, stripeCustomerId, clock.instant()));
        return stripeCustomerId;
    }
}
