package com.mmaassist.accounts.billing.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * One money movement.
 *
 * <p>{@code cardBrand} and {@code cardLast4} are display fields Stripe hands
 * back; they are the only card-related values that may exist in this database,
 * and support genuinely needs them to answer "which card was that?". A full PAN
 * must never appear here — see the schema comment on {@code billing}.
 */
@Entity
@Table(schema = "billing", name = "payments")
public class Payment {

    public static final String KIND_INVOICE = "invoice";
    public static final String KIND_PAYMENT_INTENT = "payment_intent";
    public static final String KIND_REFUND = "refund";
    public static final String KIND_DISPUTE = "dispute";

    @Id
    private UUID id;

    @Column(name = "account_id")
    private UUID accountId;

    @Column(name = "stripe_object_id", nullable = false)
    private String stripeObjectId;

    @Column(nullable = false)
    private String kind;

    /** Minor units, negative for refunds. */
    @Column(name = "amount_minor", nullable = false)
    private int amountMinor;

    @Column(nullable = false)
    private String currency;

    @Column(nullable = false)
    private String status;

    @Column(name = "card_brand")
    private String cardBrand;

    @Column(name = "card_last4", columnDefinition = "char(4)")
    private String cardLast4;

    @Column(name = "receipt_url")
    private String receiptUrl;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    @Column
    private String raw;

    protected Payment() {
    }

    public Payment(UUID id, UUID accountId, String stripeObjectId, String kind, int amountMinor,
                   String currency, String status, String cardBrand, String cardLast4,
                   String receiptUrl, Instant occurredAt, String raw) {
        this.id = id;
        this.accountId = accountId;
        this.stripeObjectId = stripeObjectId;
        this.kind = kind;
        this.amountMinor = amountMinor;
        this.currency = currency;
        this.status = status;
        this.cardBrand = cardBrand;
        this.cardLast4 = cardLast4;
        this.receiptUrl = receiptUrl;
        this.occurredAt = occurredAt;
        this.raw = raw;
    }

    public UUID getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public String getStripeObjectId() { return stripeObjectId; }
    public String getKind() { return kind; }
    public int getAmountMinor() { return amountMinor; }
    public String getCurrency() { return currency; }
    public String getStatus() { return status; }
    public String getCardBrand() { return cardBrand; }
    public String getCardLast4() { return cardLast4; }
    public String getReceiptUrl() { return receiptUrl; }
    public Instant getOccurredAt() { return occurredAt; }
    public String getRaw() { return raw; }
}
