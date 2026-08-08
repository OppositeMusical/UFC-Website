package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.Plan;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import com.stripe.exception.StripeException;
import com.stripe.model.Customer;
import com.stripe.model.Subscription;
import com.stripe.model.SubscriptionItem;
import com.stripe.net.RequestOptions;
import com.stripe.param.CustomerCreateParams;
import com.stripe.param.SubscriptionUpdateParams;
import com.stripe.param.checkout.SessionCreateParams;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/** The only class in the service that imports {@code com.stripe}. */
@Component
public class StripeApiGateway implements StripeGateway {

    private static final Logger log = LoggerFactory.getLogger(StripeApiGateway.class);

    private final AppProperties properties;

    public StripeApiGateway(AppProperties properties) {
        this.properties = properties;
    }

    @Override
    public boolean isConfigured() {
        return properties.getStripe().isConfigured();
    }

    @Override
    public String createCustomer(UUID accountId, String email) {
        requireConfigured();
        CustomerCreateParams params = CustomerCreateParams.builder()
                .setEmail(email)
                // Lets support start from a Stripe dashboard row and get back
                // to an account, which is the direction that question is
                // usually asked in.
                .putMetadata("account_id", accountId.toString())
                .build();
        try {
            // A retry after a timeout must not create a second customer for the
            // same account, which would split their payment history in two.
            return Customer.create(params, options("customer:" + accountId)).getId();
        } catch (StripeException e) {
            throw stripeFailure("create customer", e);
        }
    }

    @Override
    public CheckoutSession createCheckoutSession(UUID accountId, String customerId, Plan plan,
                                                 String successUrl, String cancelUrl) {
        requireConfigured();

        SessionCreateParams.Builder builder = SessionCreateParams.builder()
                .setMode(plan.isSubscription()
                        ? SessionCreateParams.Mode.SUBSCRIPTION
                        : SessionCreateParams.Mode.PAYMENT)
                .setCustomer(customerId)
                .setSuccessUrl(successUrl)
                .setCancelUrl(cancelUrl)
                // client_reference_id is what ties the completed session back to
                // an account. Without it the webhook has a payment and no idea
                // who made it.
                .setClientReferenceId(accountId.toString())
                .putMetadata("account_id", accountId.toString())
                .putMetadata("plan_id", plan.getId())
                .addLineItem(SessionCreateParams.LineItem.builder()
                        .setPrice(plan.getStripePriceId())
                        .setQuantity(1L)
                        .build())
                .setAutomaticTax(SessionCreateParams.AutomaticTax.builder()
                        .setEnabled(true)
                        .build())
                // Automatic tax needs an address to compute against, and Stripe
                // refuses the session without permission to save the one the
                // customer types at checkout.
                .setCustomerUpdate(SessionCreateParams.CustomerUpdate.builder()
                        .setAddress(SessionCreateParams.CustomerUpdate.Address.AUTO)
                        .build());

        try {
            com.stripe.model.checkout.Session session =
                    com.stripe.model.checkout.Session.create(builder.build(), options(null));
            return new CheckoutSession(session.getId(), session.getUrl());
        } catch (StripeException e) {
            throw stripeFailure("create checkout session", e);
        }
    }

    @Override
    public String createPortalSession(String customerId, String returnUrl) {
        requireConfigured();
        try {
            return com.stripe.model.billingportal.Session.create(
                            com.stripe.param.billingportal.SessionCreateParams.builder()
                                    .setCustomer(customerId)
                                    .setReturnUrl(returnUrl)
                                    .build(),
                            options(null))
                    .getUrl();
        } catch (StripeException e) {
            throw stripeFailure("create portal session", e);
        }
    }

    @Override
    public void cancelSubscription(String stripeSubscriptionId, boolean immediately) {
        requireConfigured();
        try {
            Subscription subscription = Subscription.retrieve(stripeSubscriptionId, options(null));
            if (immediately) {
                subscription.cancel();
            } else {
                subscription.update(SubscriptionUpdateParams.builder()
                        .setCancelAtPeriodEnd(true)
                        .build());
            }
        } catch (StripeException e) {
            throw stripeFailure("cancel subscription", e);
        }
    }

    @Override
    public RemoteSubscription retrieveSubscription(String stripeSubscriptionId) {
        requireConfigured();
        try {
            Subscription subscription = Subscription.retrieve(stripeSubscriptionId, options(null));
            return new RemoteSubscription(
                    subscription.getId(),
                    subscription.getStatus(),
                    toInstant(subscription.getCurrentPeriodEnd()),
                    Boolean.TRUE.equals(subscription.getCancelAtPeriodEnd()),
                    toInstant(subscription.getCanceledAt()),
                    firstPriceId(subscription));
        } catch (StripeException e) {
            throw stripeFailure("retrieve subscription", e);
        }
    }

    private static String firstPriceId(Subscription subscription) {
        if (subscription.getItems() == null || subscription.getItems().getData() == null
                || subscription.getItems().getData().isEmpty()) {
            return null;
        }
        SubscriptionItem item = subscription.getItems().getData().get(0);
        return item.getPrice() == null ? null : item.getPrice().getId();
    }

    static Instant toInstant(Long epochSeconds) {
        return epochSeconds == null ? null : Instant.ofEpochSecond(epochSeconds);
    }

    private RequestOptions options(String idempotencyKey) {
        RequestOptions.RequestOptionsBuilder builder = RequestOptions.builder()
                // Per-call rather than the global Stripe.apiKey: no shared
                // mutable state, and tests never have to reset it.
                .setApiKey(properties.getStripe().getSecretKey());
        if (idempotencyKey != null) {
            builder.setIdempotencyKey(idempotencyKey);
        }
        return builder.build();
    }

    private void requireConfigured() {
        if (!isConfigured()) {
            throw ApiException.unavailable("billing_unavailable",
                    "Payments are not configured on this deployment.");
        }
    }

    private ApiException stripeFailure(String operation, StripeException e) {
        // The message can carry customer details and request ids; log it, and
        // hand the caller something that says nothing useful to an attacker.
        log.error("stripe call failed: {}", operation, e);
        return ApiException.unavailable("stripe_unavailable",
                "Could not reach our payment provider. Please try again.");
    }
}
