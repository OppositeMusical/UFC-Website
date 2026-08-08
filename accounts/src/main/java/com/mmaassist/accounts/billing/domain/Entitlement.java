package com.mmaassist.accounts.billing.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * The cached answer to "what does this account get?".
 *
 * <p>Recomputed inside the same transaction as any billing change, and read by
 * both the website and the desktop app. Deriving the answer at each read site
 * instead is how two code paths end up disagreeing about whether somebody is
 * Pro — which, when one of them is the thing that mints licence tokens, is a
 * disagreement a customer notices.
 */
@Entity
@Table(schema = "billing", name = "entitlements")
public class Entitlement {

    public static final String TIER_FREE = "free";
    public static final String TIER_PRO = "pro";

    public static final String SOURCE_SUBSCRIPTION = "subscription";
    public static final String SOURCE_LIFETIME = "lifetime";
    public static final String SOURCE_GRANT = "grant";

    @Id
    @Column(name = "account_id")
    private UUID accountId;

    @Column(nullable = false)
    private String tier;

    @Column
    private String source;

    @Column(nullable = false)
    private String features;

    /** Null means perpetual — a lifetime purchase or a manual grant. */
    @Column(name = "valid_until")
    private Instant validUntil;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Entitlement() {
    }

    public Entitlement(UUID accountId, Instant now) {
        this.accountId = accountId;
        this.tier = TIER_FREE;
        this.features = "{}";
        this.updatedAt = now;
    }

    public void apply(String tier, String source, String features, Instant validUntil, Instant now) {
        this.tier = tier;
        this.source = source;
        this.features = features == null ? "{}" : features;
        this.validUntil = validUntil;
        this.updatedAt = now;
    }

    public boolean isPro() {
        return TIER_PRO.equals(tier);
    }

    public UUID getAccountId() { return accountId; }
    public String getTier() { return tier; }
    public String getSource() { return source; }
    public String getFeatures() { return features; }
    public Instant getValidUntil() { return validUntil; }
    public Instant getUpdatedAt() { return updatedAt; }
}
