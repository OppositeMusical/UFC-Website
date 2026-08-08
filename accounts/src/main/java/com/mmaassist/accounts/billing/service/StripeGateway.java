package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.Plan;
import java.time.Instant;
import java.util.UUID;

/**
 * Every outbound call to Stripe, behind one interface.
 *
 * <p>Two reasons it exists rather than calling the SDK from services directly:
 * tests never need Stripe classes on the stack, and an SDK upgrade that renames
 * something breaks exactly one file.
 *
 * <p>Note what is <em>not</em> here: nothing reads a card, and nothing accepts
 * one. Card data never reaches this service at all — Checkout is a redirect to
 * Stripe's own domain — which is what keeps the integration at PCI SAQ A.
 */
public interface StripeGateway {

    boolean isConfigured();

    /** @return the Stripe customer id. */
    String createCustomer(UUID accountId, String email);

    CheckoutSession createCheckoutSession(UUID accountId, String customerId, Plan plan,
                                          String successUrl, String cancelUrl);

    /** @return the URL of a Billing Portal session. */
    String createPortalSession(String customerId, String returnUrl);

    void cancelSubscription(String stripeSubscriptionId, boolean immediately);

    /** Used by reconciliation to compare Stripe's truth against ours. */
    RemoteSubscription retrieveSubscription(String stripeSubscriptionId);

    record CheckoutSession(String id, String url) {
    }

    record RemoteSubscription(String id, String status, Instant currentPeriodEnd,
                              boolean cancelAtPeriodEnd, Instant canceledAt, String priceId) {
    }
}
