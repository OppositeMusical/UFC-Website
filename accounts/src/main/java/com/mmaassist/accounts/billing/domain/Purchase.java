package com.mmaassist.accounts.billing.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/** A one-time purchase — in practice, the lifetime licence. */
@Entity
@Table(schema = "billing", name = "purchases")
public class Purchase {

    public static final String SUCCEEDED = "succeeded";
    public static final String REFUNDED = "refunded";
    public static final String PARTIALLY_REFUNDED = "partially_refunded";
    public static final String DISPUTED = "disputed";

    @Id
    private UUID id;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(name = "stripe_payment_intent_id", nullable = false)
    private String stripePaymentIntentId;

    @Column(name = "stripe_checkout_session_id")
    private String stripeCheckoutSessionId;

    @Column(name = "plan_id", nullable = false)
    private String planId;

    @Column(name = "amount_minor", nullable = false)
    private int amountMinor;

    @Column(nullable = false)
    private String currency;

    @Column(nullable = false)
    private String status;

    @Column(name = "purchased_at", nullable = false)
    private Instant purchasedAt;

    @Column(name = "refunded_at")
    private Instant refundedAt;

    protected Purchase() {
    }

    public Purchase(UUID id, UUID accountId, String stripePaymentIntentId,
                    String stripeCheckoutSessionId, String planId, int amountMinor,
                    String currency, Instant purchasedAt) {
        this.id = id;
        this.accountId = accountId;
        this.stripePaymentIntentId = stripePaymentIntentId;
        this.stripeCheckoutSessionId = stripeCheckoutSessionId;
        this.planId = planId;
        this.amountMinor = amountMinor;
        this.currency = currency;
        this.status = SUCCEEDED;
        this.purchasedAt = purchasedAt;
    }

    /** Only a fully succeeded purchase grants a lifetime licence. */
    public boolean grantsAccess() {
        return SUCCEEDED.equals(status);
    }

    public void markRefunded(boolean partial, Instant now) {
        // A partial refund still revokes: there is no half a lifetime licence,
        // and the alternative is deciding what fraction of "forever" was kept.
        this.status = partial ? PARTIALLY_REFUNDED : REFUNDED;
        this.refundedAt = now;
    }

    public void markDisputed() {
        this.status = DISPUTED;
    }

    public UUID getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public String getStripePaymentIntentId() { return stripePaymentIntentId; }
    public String getStripeCheckoutSessionId() { return stripeCheckoutSessionId; }
    public String getPlanId() { return planId; }
    public int getAmountMinor() { return amountMinor; }
    public String getCurrency() { return currency; }
    public String getStatus() { return status; }
    public Instant getPurchasedAt() { return purchasedAt; }
    public Instant getRefundedAt() { return refundedAt; }
}
