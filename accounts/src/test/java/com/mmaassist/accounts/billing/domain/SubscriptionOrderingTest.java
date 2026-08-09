package com.mmaassist.accounts.billing.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Stripe does not order webhook deliveries, and getting this wrong cuts off a
 * customer who has already paid: a retried {@code past_due} landing after the
 * {@code active} that resolved it would otherwise win.
 */
class SubscriptionOrderingTest {

    private static final Instant NOW = Instant.parse("2026-08-08T12:00:00Z");
    private static final Instant EARLIER = NOW.minus(Duration.ofHours(2));
    private static final Instant LATER = NOW.plus(Duration.ofHours(2));

    private Subscription subscription() {
        return new Subscription(UUID.randomUUID(), UUID.randomUUID(), "sub_1", "pro_monthly",
                Subscription.ACTIVE, NOW.plus(Duration.ofDays(30)), false, NOW);
    }

    @Test
    @DisplayName("a newer event is applied")
    void newerEventApplies() {
        Subscription subscription = subscription();
        subscription.applyUpdate(Subscription.ACTIVE, NOW, false, null, null, EARLIER, NOW);

        boolean changed = subscription.applyUpdate(
                Subscription.PAST_DUE, NOW, false, null, null, LATER, NOW);

        assertThat(changed).isTrue();
        assertThat(subscription.getStatus()).isEqualTo(Subscription.PAST_DUE);
    }

    @Test
    @DisplayName("an older event is ignored")
    void olderEventIsIgnored() {
        Subscription subscription = subscription();
        subscription.applyUpdate(Subscription.ACTIVE, NOW, false, null, null, LATER, NOW);

        boolean changed = subscription.applyUpdate(
                Subscription.PAST_DUE, NOW, false, null, null, EARLIER, NOW);

        assertThat(changed).isFalse();
        assertThat(subscription.getStatus())
                .as("a stale past_due must not cut off a paid-up customer")
                .isEqualTo(Subscription.ACTIVE);
    }

    @Test
    @DisplayName("reconciliation applies without erasing the ordering watermark")
    void reconciliationDoesNotWipeTheWatermark() {
        // Regression test. ReconciliationJob passes a null eventAt, meaning
        // "Stripe told us directly". Assigning that null through to
        // source_event_at reset the watermark, after which every subsequent
        // out-of-order webhook was accepted - the guard silently stopped
        // existing, on exactly the subscriptions that had needed repairing.
        Subscription subscription = subscription();
        subscription.applyUpdate(Subscription.ACTIVE, NOW, false, null, null, LATER, NOW);

        subscription.applyUpdate(Subscription.PAST_DUE, NOW, false, null, null, null, NOW);

        assertThat(subscription.getStatus()).isEqualTo(Subscription.PAST_DUE);
        assertThat(subscription.getSourceEventAt())
                .as("the watermark must survive a direct-from-Stripe update")
                .isEqualTo(LATER);

        boolean staleApplied = subscription.applyUpdate(
                Subscription.CANCELED, NOW, false, null, null, EARLIER, NOW);

        assertThat(staleApplied).as("the guard still works after reconciliation").isFalse();
        assertThat(subscription.getStatus()).isEqualTo(Subscription.PAST_DUE);
    }

    @Test
    @DisplayName("the first event is always applied, whatever its timestamp")
    void firstEventAlwaysApplies() {
        Subscription subscription = subscription();

        assertThat(subscription.getSourceEventAt()).isNull();
        assertThat(subscription.applyUpdate(Subscription.ACTIVE, NOW, false, null, null,
                EARLIER, NOW)).isTrue();
    }
}
