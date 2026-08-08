package com.mmaassist.accounts.identity.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * A live bearer credential: a browser cookie session or a desktop access token.
 *
 * <p>One table for both because they are the same thing — an opaque secret that
 * maps to an account — and one lookup path means one place to get expiry and
 * revocation right.
 *
 * <p>Only {@code tokenHash} is stored. A dump of this table does not let anyone
 * log in as anybody.
 */
@Entity
@Table(schema = "identity", name = "sessions")
public class AuthSession {

    public static final String KIND_WEB = "web";
    public static final String KIND_DESKTOP = "desktop";

    @Id
    private UUID id;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(nullable = false)
    private String kind;

    @Column(name = "token_hash", nullable = false)
    private byte[] tokenHash;

    @Column(name = "device_id")
    private UUID deviceId;

    @Column(name = "user_agent")
    private String userAgent;

    @Column
    private String ip;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "last_seen_at", nullable = false)
    private Instant lastSeenAt;

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    protected AuthSession() {
    }

    public AuthSession(UUID id, UUID accountId, String kind, byte[] tokenHash, UUID deviceId,
                       String userAgent, String ip, Instant now, Instant expiresAt) {
        this.id = id;
        this.accountId = accountId;
        this.kind = kind;
        this.tokenHash = tokenHash;
        this.deviceId = deviceId;
        this.userAgent = userAgent;
        this.ip = ip;
        this.createdAt = now;
        this.lastSeenAt = now;
        this.expiresAt = expiresAt;
    }

    public boolean isUsable(Instant now) {
        return revokedAt == null && expiresAt.isAfter(now);
    }

    public void touch(Instant now) {
        this.lastSeenAt = now;
    }

    public void revoke(Instant now) {
        this.revokedAt = now;
    }

    public UUID getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public String getKind() { return kind; }
    public UUID getDeviceId() { return deviceId; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getLastSeenAt() { return lastSeenAt; }
    public Instant getExpiresAt() { return expiresAt; }
    public Instant getRevokedAt() { return revokedAt; }
    public String getUserAgent() { return userAgent; }
    public String getIp() { return ip; }
}
