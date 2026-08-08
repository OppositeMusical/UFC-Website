package com.mmaassist.accounts.licensing.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * A licence token that has been handed out.
 *
 * <p>The app verifies tokens offline, so this table cannot stop one working —
 * short expiry is the real revocation mechanism. What it does buy is the
 * ability to refuse a <em>refresh</em> for a specific device the moment its
 * owner signs it out, which turns "up to fourteen days" into "at the next
 * check-in".
 */
@Entity
@Table(schema = "licensing", name = "licence_tokens")
public class LicenceToken {

    @Id
    private UUID jti;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(name = "device_id")
    private UUID deviceId;

    @Column(name = "issued_at", nullable = false)
    private Instant issuedAt;

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    protected LicenceToken() {
    }

    public LicenceToken(UUID jti, UUID accountId, UUID deviceId, Instant issuedAt, Instant expiresAt) {
        this.jti = jti;
        this.accountId = accountId;
        this.deviceId = deviceId;
        this.issuedAt = issuedAt;
        this.expiresAt = expiresAt;
    }

    public void revoke(Instant now) {
        if (revokedAt == null) {
            this.revokedAt = now;
        }
    }

    public UUID getJti() { return jti; }
    public UUID getAccountId() { return accountId; }
    public UUID getDeviceId() { return deviceId; }
    public Instant getIssuedAt() { return issuedAt; }
    public Instant getExpiresAt() { return expiresAt; }
    public Instant getRevokedAt() { return revokedAt; }
}
