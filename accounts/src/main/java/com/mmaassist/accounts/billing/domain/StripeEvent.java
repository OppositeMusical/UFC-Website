package com.mmaassist.accounts.billing.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

/**
 * A received webhook, stored before it is acted on.
 *
 * <p>Stripe's event id is the primary key, and that is the entire idempotency
 * mechanism: a duplicate delivery — which Stripe makes no promise to avoid —
 * loses the insert on the unique constraint instead of granting a second
 * licence.
 *
 * <p>The raw payload is kept so a processing bug is replayable. Stripe stops
 * retrying after three days; without the body, a bug found on day four means a
 * payment that can only be reconstructed by hand.
 */
@Entity
@Table(schema = "billing", name = "stripe_events")
public class StripeEvent {

    @Id
    private String id;

    @Column(nullable = false)
    private String type;

    @Column(name = "api_version")
    private String apiVersion;

    @Column(nullable = false)
    private String payload;

    @Column(name = "received_at", nullable = false)
    private Instant receivedAt;

    @Column(name = "processed_at")
    private Instant processedAt;

    @Column(nullable = false)
    private int attempts;

    @Column(name = "last_error")
    private String lastError;

    protected StripeEvent() {
    }

    public StripeEvent(String id, String type, String apiVersion, String payload, Instant receivedAt) {
        this.id = id;
        this.type = type;
        this.apiVersion = apiVersion;
        this.payload = payload;
        this.receivedAt = receivedAt;
        this.attempts = 0;
    }

    public void markProcessed(Instant now) {
        this.processedAt = now;
        this.lastError = null;
        this.attempts++;
    }

    public void markFailed(String error) {
        this.attempts++;
        // Bounded: a stack trace from a nested Stripe failure can be enormous,
        // and the column is here for triage, not archaeology.
        this.lastError = error == null ? null : error.substring(0, Math.min(error.length(), 2000));
    }

    /**
     * Gives up after {@code maxAttempts}.
     *
     * <p>Poison events are marked processed rather than retried forever, so one
     * unparseable payload cannot starve the queue behind it. The row keeps its
     * {@code last_error}, and the alert on non-empty {@code last_error} is what
     * surfaces it.
     */
    public boolean isExhausted(int maxAttempts) {
        return attempts >= maxAttempts;
    }

    /**
     * Stops the poller retrying, without erasing why it failed.
     *
     * <p>Unlike {@link #markProcessed}, {@code last_error} survives — that
     * column is what the "webhook needs a human" alert reads, and clearing it
     * would make a permanently failed payment look handled.
     */
    public void giveUp(Instant now) {
        this.processedAt = now;
    }

    public String getId() { return id; }
    public String getType() { return type; }
    public String getApiVersion() { return apiVersion; }
    public String getPayload() { return payload; }
    public Instant getReceivedAt() { return receivedAt; }
    public Instant getProcessedAt() { return processedAt; }
    public int getAttempts() { return attempts; }
    public String getLastError() { return lastError; }
}
