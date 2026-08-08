package com.mmaassist.accounts.billing.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/** Maps an account to its Stripe customer. */
@Entity
@Table(schema = "billing", name = "customers")
public class Customer {

    @Id
    @Column(name = "account_id")
    private UUID accountId;

    @Column(name = "stripe_customer_id", nullable = false)
    private String stripeCustomerId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected Customer() {
    }

    public Customer(UUID accountId, String stripeCustomerId, Instant createdAt) {
        this.accountId = accountId;
        this.stripeCustomerId = stripeCustomerId;
        this.createdAt = createdAt;
    }

    public UUID getAccountId() { return accountId; }
    public String getStripeCustomerId() { return stripeCustomerId; }
    public Instant getCreatedAt() { return createdAt; }
}
