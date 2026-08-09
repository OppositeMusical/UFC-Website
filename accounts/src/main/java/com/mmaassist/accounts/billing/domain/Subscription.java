package com.mmaassist.accounts.billing.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.Set;
import java.util.UUID;

/**
 * A Stripe subscription, mirrored locally.
 *
 * <p>{@code status} holds Stripe's own vocabulary verbatim. Mapping it onto a
 * local enum would mean deciding today what to do with a status Stripe adds
 * next year, and the failure mode of guessing wrong is an account that silently
 * loses access.
 */
@Entity
@Table(schema = "billing", name = "subscriptions")
public class Subscription {

    public static final String ACTIVE = "active";
    public static final String TRIALING = "trialing";
    public static final String PAST_DUE = "past_due";
    public static final String CANCELED = "canceled";
    public static final String UNPAID = "unpaid";

    /** Statuses that grant access outright. */
    public static final Set<String> GRANTING = Set.of(ACTIVE, TRIALING);

    /** Statuses that will never grant again, so reconciliation can skip them. */
    public static final Set<String> TERMINAL = Set.of(CANCELED, "incomplete_expired");

    @Id
    private UUID id;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(name = "stripe_subscription_id", nullable = false)
    private String stripeSubscriptionId;

    @Column(name = "plan_id", nullable = false)
    private String planId;

    @Column(nullable = false)
    private String status;

    @Column(name = "current_period_end")
    private Instant currentPeriodEnd;

    @Column(name = "cancel_at_period_end", nullable = false)
    private boolean cancelAtPeriodEnd;

    @Column(name = "canceled_at")
    private Instant canceledAt;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Column(name = "source_event_at")
    private Instant sourceEventAt;

    protected Subscription() {
    }

    public Subscription(UUID id, UUID accountId, String stripeSubscriptionId, String planId,
                        String status, Instant currentPeriodEnd, boolean cancelAtPeriodEnd,
                        Instant now) {
        this.id = id;
        this.accountId = accountId;
        this.stripeSubscriptionId = stripeSubscriptionId;
        this.planId = planId;
        this.status = status;
        this.currentPeriodEnd = currentPeriodEnd;
        this.cancelAtPeriodEnd = cancelAtPeriodEnd;
        this.createdAt = now;
        this.updatedAt = now;
    }

    public boolean isGranting() {
        return GRANTING.contains(status);
    }

    public boolean isPastDue() {
        return PAST_DUE.equals(status);
    }

    public boolean isTerminal() {
        return TERMINAL.contains(status);
    }

    /**
     * Applies an update, ignoring one that describes an older state than we
     * already hold.
     *
     * <p>Webhook delivery is not ordered. Without this check, a retried
     * {@code past_due} arriving after the {@code active} that resolved it would
     * cut off a customer who has already paid.
     *
     * @return whether anything changed
     */
    public boolean applyUpdate(String status, Instant currentPeriodEnd, boolean cancelAtPeriodEnd,
                               Instant canceledAt, String planId, Instant eventAt, Instant now) {
        if (eventAt != null && sourceEventAt != null && eventAt.isBefore(sourceEventAt)) {
            return false;
        }
        this.status = status;
        this.currentPeriodEnd = currentPeriodEnd;
        this.cancelAtPeriodEnd = cancelAtPeriodEnd;
        this.canceledAt = canceledAt;
        if (planId != null) {
            this.planId = planId;
        }
        // Only ever move this forward. Reconciliation passes a null eventAt,
        // meaning "Stripe told us directly, this is newer than anything we
        // hold" - but assigning that null would erase the watermark and leave
        // every subsequent out-of-order webhook accepted, silently undoing the
        // guard above.
        if (eventAt != null) {
            this.sourceEventAt = eventAt;
        }
        this.updatedAt = now;
        return true;
    }

    public UUID getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public String getStripeSubscriptionId() { return stripeSubscriptionId; }
    public String getPlanId() { return planId; }
    public String getStatus() { return status; }
    public Instant getCurrentPeriodEnd() { return currentPeriodEnd; }
    public boolean isCancelAtPeriodEnd() { return cancelAtPeriodEnd; }
    public Instant getCanceledAt() { return canceledAt; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public Instant getSourceEventAt() { return sourceEventAt; }
}
