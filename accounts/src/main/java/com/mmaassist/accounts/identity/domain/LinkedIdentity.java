package com.mmaassist.accounts.identity.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/** A single provider login linked to an account. An account may hold several. */
@Entity
@Table(schema = "identity", name = "identities")
public class LinkedIdentity {

    @Id
    private UUID id;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(nullable = false)
    private String provider;

    /**
     * The provider's immutable subject id — Google's {@code sub}, GitHub's
     * numeric user id. Never the email address: addresses get released and
     * re-registered, and keying on one would eventually hand an account to a
     * stranger.
     */
    @Column(name = "provider_user_id", nullable = false)
    private String providerUserId;

    @Column(name = "email_at_link")
    private String emailAtLink;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "last_login_at")
    private Instant lastLoginAt;

    protected LinkedIdentity() {
    }

    public LinkedIdentity(UUID id, UUID accountId, String provider, String providerUserId,
                          String emailAtLink, Instant now) {
        this.id = id;
        this.accountId = accountId;
        this.provider = provider;
        this.providerUserId = providerUserId;
        this.emailAtLink = emailAtLink;
        this.createdAt = now;
        this.lastLoginAt = now;
    }

    public void touch(Instant now) {
        this.lastLoginAt = now;
    }

    public UUID getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public String getProvider() { return provider; }
    public String getProviderUserId() { return providerUserId; }
    public String getEmailAtLink() { return emailAtLink; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getLastLoginAt() { return lastLoginAt; }
}
