package com.mmaassist.accounts.platform.audit;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema = "platform", name = "audit_log")
public class AuditEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private UUID accountId;

    @Column(nullable = false)
    private String actor;

    @Column(nullable = false)
    private String action;

    @Column
    private String detail;

    @Column(name = "at", nullable = false)
    private Instant at;

    protected AuditEntry() {
    }

    public AuditEntry(UUID accountId, String actor, String action, String detail, Instant at) {
        this.accountId = accountId;
        this.actor = actor;
        this.action = action;
        this.detail = detail;
        this.at = at;
    }

    public Long getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public String getActor() { return actor; }
    public String getAction() { return action; }
    public String getDetail() { return detail; }
    public Instant getAt() { return at; }
}
