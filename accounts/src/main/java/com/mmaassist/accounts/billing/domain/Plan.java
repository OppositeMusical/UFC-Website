package com.mmaassist.accounts.billing.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * A purchasable plan, mirroring a Stripe price.
 *
 * <p>The website renders its pricing page from this table, so changing a price
 * is a row update rather than a frontend deploy.
 */
@Entity
@Table(schema = "billing", name = "plans")
public class Plan {

    public static final String KIND_SUBSCRIPTION = "subscription";
    public static final String KIND_ONE_TIME = "one_time";

    @Id
    private String id;

    @Column(name = "stripe_price_id", nullable = false)
    private String stripePriceId;

    @Column(nullable = false)
    private String kind;

    @Column(name = "billing_interval")
    private String billingInterval;

    @Column(name = "amount_minor", nullable = false)
    private int amountMinor;

    @Column(nullable = false)
    private String currency;

    /** JSON object of feature flags. See the README on why this is text. */
    @Column(nullable = false)
    private String features;

    @Column(name = "display_name", nullable = false)
    private String displayName;

    @Column
    private String description;

    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    @Column(nullable = false)
    private boolean active;

    protected Plan() {
    }

    public boolean isSubscription() {
        return KIND_SUBSCRIPTION.equals(kind);
    }

    /** True while the seeded placeholder price id has not been replaced. */
    public boolean hasPlaceholderPriceId() {
        return stripePriceId != null && stripePriceId.startsWith("price_REPLACE_ME");
    }

    public String getId() { return id; }
    public String getStripePriceId() { return stripePriceId; }
    public String getKind() { return kind; }
    public String getBillingInterval() { return billingInterval; }
    public int getAmountMinor() { return amountMinor; }
    public String getCurrency() { return currency; }
    public String getFeatures() { return features; }
    public String getDisplayName() { return displayName; }
    public String getDescription() { return description; }
    public int getSortOrder() { return sortOrder; }
    public boolean isActive() { return active; }
}
