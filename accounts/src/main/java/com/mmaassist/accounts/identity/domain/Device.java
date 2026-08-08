package com.mmaassist.accounts.identity.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * A desktop install.
 *
 * <p>{@code installId} is a random UUID the app generates once and keeps in its
 * data directory — deliberately not a hardware fingerprint. The app is portable
 * (SPEC.md 13.1): the same install legitimately runs from a USB stick on
 * several machines, and a hardware id would burn a fresh activation on each.
 * Copying the data folder clones the id, which is fine, because the device cap
 * is a courtesy limit rather than a security control.
 */
@Entity
@Table(schema = "identity", name = "devices")
public class Device {

    @Id
    private UUID id;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(name = "install_id", nullable = false)
    private String installId;

    @Column
    private String name;

    @Column(name = "app_version")
    private String appVersion;

    @Column(name = "first_seen_at", nullable = false)
    private Instant firstSeenAt;

    @Column(name = "last_seen_at", nullable = false)
    private Instant lastSeenAt;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    protected Device() {
    }

    public Device(UUID id, UUID accountId, String installId, String name, String appVersion, Instant now) {
        this.id = id;
        this.accountId = accountId;
        this.installId = installId;
        this.name = name;
        this.appVersion = appVersion;
        this.firstSeenAt = now;
        this.lastSeenAt = now;
    }

    public boolean isActive() {
        return revokedAt == null;
    }

    public void seen(String appVersion, String name, Instant now) {
        if (appVersion != null && !appVersion.isBlank()) {
            this.appVersion = appVersion;
        }
        if (name != null && !name.isBlank()) {
            this.name = name;
        }
        this.lastSeenAt = now;
    }

    public void revoke(Instant now) {
        this.revokedAt = now;
    }

    /** Re-activates a previously revoked install that has signed in again. */
    public void reinstate(Instant now) {
        this.revokedAt = null;
        this.lastSeenAt = now;
    }

    public UUID getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public String getInstallId() { return installId; }
    public String getName() { return name; }
    public String getAppVersion() { return appVersion; }
    public Instant getFirstSeenAt() { return firstSeenAt; }
    public Instant getLastSeenAt() { return lastSeenAt; }
    public Instant getRevokedAt() { return revokedAt; }
}
