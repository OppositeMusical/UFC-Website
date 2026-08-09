package com.mmaassist.accounts.billing.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mmaassist.accounts.billing.domain.Customer;
import com.mmaassist.accounts.billing.domain.CustomerRepository;
import com.mmaassist.accounts.billing.domain.Payment;
import com.mmaassist.accounts.billing.domain.PaymentRepository;
import com.mmaassist.accounts.billing.domain.Plan;
import com.mmaassist.accounts.billing.domain.PlanRepository;
import com.mmaassist.accounts.billing.domain.Purchase;
import com.mmaassist.accounts.billing.domain.PurchaseRepository;
import com.mmaassist.accounts.billing.domain.StripeEvent;
import com.mmaassist.accounts.billing.domain.Subscription;
import com.mmaassist.accounts.billing.domain.SubscriptionRepository;
import com.mmaassist.accounts.platform.audit.AuditService;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * Turns a stored Stripe event into local state.
 *
 * <p>Payloads are read with Jackson rather than deserialised into SDK models.
 * Stripe pins the shape of an event to the API version that produced it, so an
 * SDK upgrade can start failing to parse events that are already in the table.
 * Reading the handful of fields we actually use keeps old events replayable
 * forever.
 *
 * <p>Every branch ends by recomputing the entitlement. That is the invariant
 * worth protecting: there is no path that changes billing state without
 * recomputing what the customer is owed.
 */
@Service
public class StripeEventHandler {

    private static final Logger log = LoggerFactory.getLogger(StripeEventHandler.class);

    private final ObjectMapper objectMapper;
    private final CustomerRepository customers;
    private final SubscriptionRepository subscriptions;
    private final PurchaseRepository purchases;
    private final PaymentRepository payments;
    private final PlanRepository plans;
    private final EntitlementService entitlements;
    private final AuditService audit;
    private final Clock clock;

    public StripeEventHandler(ObjectMapper objectMapper, CustomerRepository customers,
                              SubscriptionRepository subscriptions, PurchaseRepository purchases,
                              PaymentRepository payments, PlanRepository plans,
                              EntitlementService entitlements, AuditService audit, Clock clock) {
        this.objectMapper = objectMapper;
        this.customers = customers;
        this.subscriptions = subscriptions;
        this.purchases = purchases;
        this.payments = payments;
        this.plans = plans;
        this.entitlements = entitlements;
        this.audit = audit;
        this.clock = clock;
    }

    public void handle(StripeEvent event) throws Exception {
        JsonNode root = objectMapper.readTree(event.getPayload());
        JsonNode object = root.path("data").path("object");
        Instant eventAt = root.hasNonNull("created")
                ? Instant.ofEpochSecond(root.get("created").asLong())
                : clock.instant();

        switch (event.getType()) {
            case "checkout.session.completed" -> onCheckoutCompleted(object, eventAt);
            case "customer.subscription.created",
                 "customer.subscription.updated",
                 "customer.subscription.deleted" -> onSubscriptionChanged(object, eventAt);
            case "invoice.paid" -> onInvoicePaid(object, eventAt);
            case "invoice.payment_failed" -> onInvoicePaymentFailed(object, eventAt);
            case "charge.refunded" -> onChargeRefunded(object, eventAt);
            case "charge.dispute.created" -> onDisputeCreated(object, eventAt);
            default -> log.debug("ignoring stripe event type {}", event.getType());
        }
    }

    // -- handlers ------------------------------------------------------------

    private void onCheckoutCompleted(JsonNode session, Instant eventAt) {
        UUID accountId = accountFromSession(session);
        if (accountId == null) {
            // Money arrived that we cannot attribute to anybody. Retrying will
            // not conjure an account, so the event is marked processed - but
            // this is somebody's payment with nothing to show for it, and it
            // needs a human today, not whenever someone reads the warnings.
            log.error("PAYMENT UNATTRIBUTED: checkout session {} has no resolvable account; "
                    + "reconcile it by hand", text(session, "id"));
            return;
        }

        // Make sure the customer mapping exists even if the account reached
        // Stripe by some path that did not create one locally.
        String customerId = text(session, "customer");
        if (customerId != null && customers.findById(accountId).isEmpty()) {
            customers.save(new Customer(accountId, customerId, clock.instant()));
        }

        if (!"payment".equals(text(session, "mode"))) {
            // A subscription checkout is not the authority on subscription
            // state; customer.subscription.* is, and it carries the status and
            // period this session does not have.
            return;
        }

        String paymentIntentId = text(session, "payment_intent");
        if (paymentIntentId == null) {
            log.warn("payment-mode checkout session {} has no payment_intent", text(session, "id"));
            return;
        }
        if (purchases.findByStripePaymentIntentId(paymentIntentId).isPresent()) {
            return; // already recorded; a replay of this event changes nothing
        }

        String planId = session.path("metadata").path("plan_id").asText(null);
        if (planId == null || plans.findById(planId).isEmpty()) {
            log.error("checkout session {} names unknown plan {}", text(session, "id"), planId);
            return;
        }

        purchases.save(new Purchase(UUID.randomUUID(), accountId, paymentIntentId,
                text(session, "id"), planId,
                (int) session.path("amount_total").asLong(),
                session.path("currency").asText("usd"),
                eventAt));

        audit.record(accountId, AuditService.ACTOR_STRIPE, "purchase.recorded",
                Map.of("planId", planId, "paymentIntent", paymentIntentId));
        entitlements.recompute(accountId);
    }

    private void onSubscriptionChanged(JsonNode object, Instant eventAt) {
        String stripeSubscriptionId = text(object, "id");
        UUID accountId = accountFromCustomer(text(object, "customer"));
        if (accountId == null || stripeSubscriptionId == null) {
            log.warn("subscription event {} has no resolvable account", stripeSubscriptionId);
            return;
        }

        String status = object.path("status").asText("incomplete");
        Instant periodEnd = epochSeconds(object.path("current_period_end"));
        boolean cancelAtPeriodEnd = object.path("cancel_at_period_end").asBoolean(false);
        Instant canceledAt = epochSeconds(object.path("canceled_at"));
        String planId = planIdFromSubscription(object);

        Optional<Subscription> existing = subscriptions.findByStripeSubscriptionId(stripeSubscriptionId);
        if (existing.isPresent()) {
            boolean changed = existing.get().applyUpdate(status, periodEnd, cancelAtPeriodEnd,
                    canceledAt, planId, eventAt, clock.instant());
            if (!changed) {
                // An older event arrived after a newer one. Applying it would
                // resurrect state the customer has already moved past.
                log.info("ignoring out-of-order subscription event for {}", stripeSubscriptionId);
                return;
            }
        } else {
            if (planId == null) {
                log.error("subscription {} references an unknown price", stripeSubscriptionId);
                return;
            }
            Subscription subscription = new Subscription(UUID.randomUUID(), accountId,
                    stripeSubscriptionId, planId, status, periodEnd, cancelAtPeriodEnd, clock.instant());
            subscription.applyUpdate(status, periodEnd, cancelAtPeriodEnd, canceledAt, planId,
                    eventAt, clock.instant());
            subscriptions.save(subscription);
        }

        audit.record(accountId, AuditService.ACTOR_STRIPE, "subscription.updated",
                Map.of("subscription", stripeSubscriptionId, "status", status));
        entitlements.recompute(accountId);
    }

    private void onInvoicePaid(JsonNode invoice, Instant eventAt) {
        UUID accountId = accountFromCustomer(text(invoice, "customer"));
        recordPayment(accountId, text(invoice, "id"), Payment.KIND_INVOICE,
                (int) invoice.path("amount_paid").asLong(), invoice.path("currency").asText("usd"),
                "paid", text(invoice, "hosted_invoice_url"), eventAt, invoice);
        if (accountId != null) {
            entitlements.recompute(accountId);
        }
    }

    private void onInvoicePaymentFailed(JsonNode invoice, Instant eventAt) {
        UUID accountId = accountFromCustomer(text(invoice, "customer"));
        recordPayment(accountId, text(invoice, "id"), Payment.KIND_INVOICE,
                (int) invoice.path("amount_due").asLong(), invoice.path("currency").asText("usd"),
                "payment_failed", text(invoice, "hosted_invoice_url"), eventAt, invoice);

        // The subscription's move to past_due arrives as its own event; the
        // dunning grace in EntitlementCalculator is what keeps access alive
        // while Stripe retries the card.
        if (accountId != null) {
            log.info("invoice payment failed for account {}", accountId);
            entitlements.recompute(accountId);
        }
    }

    private void onChargeRefunded(JsonNode charge, Instant eventAt) {
        String paymentIntentId = text(charge, "payment_intent");
        long amount = charge.path("amount").asLong();
        long refunded = charge.path("amount_refunded").asLong();

        UUID accountId = accountFromCustomer(text(charge, "customer"));

        Optional<Purchase> purchase = paymentIntentId == null
                ? Optional.empty()
                : purchases.findByStripePaymentIntentId(paymentIntentId);
        if (purchase.isPresent()) {
            purchase.get().markRefunded(refunded < amount, clock.instant());
            accountId = purchase.get().getAccountId();
        }

        recordPayment(accountId, text(charge, "id") + ":refund", Payment.KIND_REFUND,
                (int) -refunded, charge.path("currency").asText("usd"), "refunded",
                text(charge, "receipt_url"), eventAt, charge);

        if (accountId != null) {
            audit.record(accountId, AuditService.ACTOR_STRIPE, "charge.refunded",
                    Map.of("amountMinor", refunded, "partial", refunded < amount));
            entitlements.recompute(accountId);
        }
    }

    private void onDisputeCreated(JsonNode dispute, Instant eventAt) {
        String paymentIntentId = text(dispute, "payment_intent");
        UUID accountId = null;

        Optional<Purchase> purchase = paymentIntentId == null
                ? Optional.empty()
                : purchases.findByStripePaymentIntentId(paymentIntentId);
        if (purchase.isPresent()) {
            purchase.get().markDisputed();
            accountId = purchase.get().getAccountId();
        }

        recordPayment(accountId, text(dispute, "id"), Payment.KIND_DISPUTE,
                (int) -dispute.path("amount").asLong(), dispute.path("currency").asText("usd"),
                "disputed", null, eventAt, dispute);

        if (accountId != null) {
            audit.record(accountId, AuditService.ACTOR_STRIPE, "charge.disputed",
                    Map.of("dispute", String.valueOf(text(dispute, "id"))));
            entitlements.recompute(accountId);
        }
        // Deliberately loud: a dispute needs a human to decide whether to
        // contest it, and the clock on that is days, not weeks.
        log.error("DISPUTE opened on payment intent {} for account {}", paymentIntentId, accountId);
    }

    // -- helpers -------------------------------------------------------------

    private void recordPayment(UUID accountId, String objectId, String kind, int amountMinor,
                               String currency, String status, String receiptUrl, Instant occurredAt,
                               JsonNode raw) {
        if (objectId == null) {
            return;
        }
        if (payments.findByStripeObjectId(objectId).isPresent()) {
            return;
        }
        payments.save(new Payment(UUID.randomUUID(), accountId, objectId, kind, amountMinor,
                currency, status, cardBrand(raw), cardLast4(raw), receiptUrl, occurredAt,
                raw.toString()));
    }

    private UUID accountFromSession(JsonNode session) {
        String reference = text(session, "client_reference_id");
        if (reference != null) {
            try {
                return UUID.fromString(reference);
            } catch (IllegalArgumentException ignored) {
                // fall through to the metadata and customer lookups
            }
        }
        String metadataAccount = session.path("metadata").path("account_id").asText(null);
        if (metadataAccount != null) {
            try {
                return UUID.fromString(metadataAccount);
            } catch (IllegalArgumentException ignored) {
                // fall through
            }
        }
        return accountFromCustomer(text(session, "customer"));
    }

    private UUID accountFromCustomer(String stripeCustomerId) {
        if (stripeCustomerId == null) {
            return null;
        }
        return customers.findByStripeCustomerId(stripeCustomerId)
                .map(Customer::getAccountId)
                .orElse(null);
    }

    private String planIdFromSubscription(JsonNode subscription) {
        JsonNode items = subscription.path("items").path("data");
        if (!items.isArray() || items.isEmpty()) {
            return null;
        }
        String priceId = items.get(0).path("price").path("id").asText(null);
        if (priceId == null) {
            return null;
        }
        return plans.findByStripePriceId(priceId).map(Plan::getId).orElse(null);
    }

    /** Stripe puts these in different places depending on the object; both are display-only. */
    private static String cardBrand(JsonNode node) {
        JsonNode card = node.path("payment_method_details").path("card");
        return card.hasNonNull("brand") ? card.get("brand").asText() : null;
    }

    private static String cardLast4(JsonNode node) {
        JsonNode card = node.path("payment_method_details").path("card");
        return card.hasNonNull("last4") ? card.get("last4").asText() : null;
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    private static Instant epochSeconds(JsonNode node) {
        return node == null || node.isNull() || !node.isNumber()
                ? null
                : Instant.ofEpochSecond(node.asLong());
    }
}
