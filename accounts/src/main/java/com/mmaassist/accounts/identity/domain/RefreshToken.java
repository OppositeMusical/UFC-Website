package com.mmaassist.accounts.identity.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * A long-lived desktop credential, rotated on every use.
 *
 * <p>{@code familyId} groups a rotation chain. Presenting a token that has
 * already been rotated means either a replay or a theft, and the two are
 * indistinguishable from here — so the whole family is revoked and the install
 * has to sign in again. Annoying exactly once, versus a stolen token that works
 * for ninety days.
 */
@Entity
@Table(schema = "identity", name = "refresh_tokens")
public class RefreshToken {

    @Id
    private UUID id;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(name = "device_id")
    private UUID deviceId;

    @Column(name = "token_hash", nullable = false)
    private byte[] tokenHash;

    @Column(name = "family_id", nullable = false)
    private UUID familyId;

    @Column(name = "issued_at", nullable = false)
    private Instant issuedAt;

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    @Column(name = "replaced_by")
    private UUID replacedBy;

    protected RefreshToken() {
    }

    public RefreshToken(UUID id, UUID accountId, UUID deviceId, byte[] tokenHash, UUID familyId,
                        Instant now, Instant expiresAt) {
        this.id = id;
        this.accountId = accountId;
        this.deviceId = deviceId;
        this.tokenHash = tokenHash;
        this.familyId = familyId;
        this.issuedAt = now;
        this.expiresAt = expiresAt;
    }

    public boolean isUsable(Instant now) {
        return revokedAt == null && replacedBy == null && expiresAt.isAfter(now);
    }

    /** True when this token was already exchanged — the signal of a replay. */
    public boolean isSpent() {
        return replacedBy != null;
    }

    public void rotateTo(UUID successorId, Instant now) {
        this.replacedBy = successorId;
        this.revokedAt = now;
    }

    public void revoke(Instant now) {
        if (this.revokedAt == null) {
            this.revokedAt = now;
        }
    }

    public UUID getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public UUID getDeviceId() { return deviceId; }
    public UUID getFamilyId() { return familyId; }
    public Instant getIssuedAt() { return issuedAt; }
    public Instant getExpiresAt() { return expiresAt; }
    public Instant getRevokedAt() { return revokedAt; }
    public UUID getReplacedBy() { return replacedBy; }
}
