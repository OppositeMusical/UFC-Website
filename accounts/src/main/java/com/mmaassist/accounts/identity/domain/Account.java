package com.mmaassist.accounts.identity.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/**
 * A user.
 *
 * <p>There is no password column, and there never will be: credentials are the
 * identity providers' problem. {@code email} is always an address a provider
 * told us it had verified — see {@code AccountService} for why that matters.
 */
@Entity
@Table(schema = "identity", name = "accounts")
public class Account {

    public static final String STATUS_ACTIVE = "active";
    public static final String STATUS_SUSPENDED = "suspended";
    public static final String STATUS_DELETED = "deleted";

    @Id
    private UUID id;

    @Column(nullable = false)
    private String email;

    @Column(name = "display_name")
    private String displayName;

    @Column(name = "avatar_url")
    private String avatarUrl;

    @Column(nullable = false)
    private String status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Column(name = "deleted_at")
    private Instant deletedAt;

    protected Account() {
    }

    public Account(UUID id, String email, String displayName, String avatarUrl, Instant now) {
        this.id = id;
        this.email = email;
        this.displayName = displayName;
        this.avatarUrl = avatarUrl;
        this.status = STATUS_ACTIVE;
        this.createdAt = now;
        this.updatedAt = now;
    }

    public boolean isActive() {
        return STATUS_ACTIVE.equals(status);
    }

    /** Irreversibly strips the personal fields, keeping the row for referential integrity. */
    public void anonymise(Instant now) {
        this.email = "deleted+" + id + "@invalid";
        this.displayName = null;
        this.avatarUrl = null;
        this.status = STATUS_DELETED;
        this.deletedAt = now;
        this.updatedAt = now;
    }

    public void updateProfile(String displayName, String avatarUrl, Instant now) {
        this.displayName = displayName;
        this.avatarUrl = avatarUrl;
        this.updatedAt = now;
    }

    public UUID getId() { return id; }
    public String getEmail() { return email; }
    public String getDisplayName() { return displayName; }
    public String getAvatarUrl() { return avatarUrl; }
    public String getStatus() { return status; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public Instant getDeletedAt() { return deletedAt; }
}
