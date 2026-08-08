package com.mmaassist.accounts.billing.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.mmaassist.accounts.billing.domain.Entitlement;
import com.mmaassist.accounts.billing.domain.Purchase;
import com.mmaassist.accounts.billing.domain.Subscription;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * The function that decides who paid gets exhaustive coverage, because every
 * other guard in the service is downstream of it being right.
 */
class EntitlementCalculatorTest {

    private static final Instant NOW = Instant.parse("2026-08-08T12:00:00Z");
    private static final Duration GRACE = Duration.ofDays(7);
    private static final UUID ACCOUNT = UUID.randomUUID();

    @Test
    @DisplayName("nothing bought is free")
    void nothingIsFree() {
        var result = EntitlementCalculator.calculate(List.of(), List.of(), GRACE, NOW);

        assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        assertThat(result.source()).isNull();
        assertThat(result.validUntil()).isNull();
        assertThat(result.planId()).isNull();
    }

    @Nested
    @DisplayName("lifetime purchases")
    class Lifetime {

        @Test
        void grantsPerpetualPro() {
            var result = EntitlementCalculator.calculate(
                    List.of(purchase("lifetime")), List.of(), GRACE, NOW);

            assertThat(result.isPro()).isTrue();
            assertThat(result.source()).isEqualTo(Entitlement.SOURCE_LIFETIME);
            assertThat(result.planId()).isEqualTo("lifetime");
            assertThat(result.validUntil()).as("perpetual").isNull();
        }

        @Test
        @DisplayName("a refund revokes it")
        void refundRevokes() {
            Purchase refunded = purchase("lifetime");
            refunded.markRefunded(false, NOW);

            var result = EntitlementCalculator.calculate(List.of(refunded), List.of(), GRACE, NOW);

            assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        }

        @Test
        @DisplayName("a partial refund also revokes - there is no half a lifetime licence")
        void partialRefundRevokes() {
            Purchase refunded = purchase("lifetime");
            refunded.markRefunded(true, NOW);

            var result = EntitlementCalculator.calculate(List.of(refunded), List.of(), GRACE, NOW);

            assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        }

        @Test
        void disputeRevokes() {
            Purchase disputed = purchase("lifetime");
            disputed.markDisputed();

            var result = EntitlementCalculator.calculate(List.of(disputed), List.of(), GRACE, NOW);

            assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        }

        @Test
        @DisplayName("outranks a subscription, so a lapse cannot take it away")
        void outranksSubscription() {
            var result = EntitlementCalculator.calculate(
                    List.of(purchase("lifetime")),
                    List.of(subscription(Subscription.CANCELED, NOW.minus(Duration.ofDays(60)))),
                    GRACE, NOW);

            assertThat(result.source()).isEqualTo(Entitlement.SOURCE_LIFETIME);
            assertThat(result.validUntil()).isNull();
        }

        @Test
        @DisplayName("a refunded lifetime still falls back to an active subscription")
        void refundedFallsBackToSubscription() {
            Purchase refunded = purchase("lifetime");
            refunded.markRefunded(false, NOW);
            Instant periodEnd = NOW.plus(Duration.ofDays(20));

            var result = EntitlementCalculator.calculate(
                    List.of(refunded), List.of(subscription(Subscription.ACTIVE, periodEnd)), GRACE, NOW);

            assertThat(result.source()).isEqualTo(Entitlement.SOURCE_SUBSCRIPTION);
            assertThat(result.validUntil()).isEqualTo(periodEnd);
        }
    }

    @Nested
    @DisplayName("subscriptions")
    class Subscriptions {

        @Test
        void activeGrantsUntilPeriodEnd() {
            Instant periodEnd = NOW.plus(Duration.ofDays(12));

            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.ACTIVE, periodEnd)), GRACE, NOW);

            assertThat(result.isPro()).isTrue();
            assertThat(result.source()).isEqualTo(Entitlement.SOURCE_SUBSCRIPTION);
            assertThat(result.validUntil()).isEqualTo(periodEnd);
        }

        @Test
        @DisplayName("a trial is as good as a paid period")
        void trialingGrants() {
            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.TRIALING, NOW.plus(Duration.ofDays(7)))),
                    GRACE, NOW);

            assertThat(result.isPro()).isTrue();
        }

        @Test
        void canceledGrantsNothing() {
            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.CANCELED, NOW.plus(Duration.ofDays(5)))),
                    GRACE, NOW);

            assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        }

        @Test
        void unpaidGrantsNothing() {
            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.UNPAID, NOW.plus(Duration.ofDays(5)))),
                    GRACE, NOW);

            assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        }

        @Test
        @DisplayName("the longest-running of several wins")
        void latestPeriodEndWins() {
            Instant soon = NOW.plus(Duration.ofDays(3));
            Instant later = NOW.plus(Duration.ofDays(300));

            var result = EntitlementCalculator.calculate(List.of(),
                    List.of(subscription(Subscription.ACTIVE, soon),
                            subscription(Subscription.ACTIVE, later)),
                    GRACE, NOW);

            assertThat(result.validUntil()).isEqualTo(later);
        }

        @Test
        @DisplayName("a missing period end grants, but without a perpetual window")
        void nullPeriodEndGrantsWithoutWindow() {
            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.ACTIVE, null)), GRACE, NOW);

            assertThat(result.isPro()).isTrue();
            assertThat(result.validUntil()).isNull();
        }
    }

    @Nested
    @DisplayName("past due keeps access during the dunning window")
    class PastDue {

        @Test
        void grantsInsideGrace() {
            Instant periodEnd = NOW.minus(Duration.ofDays(2));

            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.PAST_DUE, periodEnd)), GRACE, NOW);

            assertThat(result.isPro()).isTrue();
            assertThat(result.validUntil()).isEqualTo(periodEnd.plus(GRACE));
        }

        @Test
        void stopsAfterGrace() {
            Instant periodEnd = NOW.minus(Duration.ofDays(8));

            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.PAST_DUE, periodEnd)), GRACE, NOW);

            assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        }

        @Test
        @DisplayName("the boundary is exclusive: grace expiring exactly now is over")
        void graceBoundaryIsExclusive() {
            Instant periodEnd = NOW.minus(GRACE);

            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.PAST_DUE, periodEnd)), GRACE, NOW);

            assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        }

        @Test
        @DisplayName("no period end means no computable window, so no access")
        void nullPeriodEndGrantsNothing() {
            var result = EntitlementCalculator.calculate(
                    List.of(), List.of(subscription(Subscription.PAST_DUE, null)), GRACE, NOW);

            assertThat(result.tier()).isEqualTo(Entitlement.TIER_FREE);
        }

        @Test
        @DisplayName("an active subscription beats a past-due one")
        void activeBeatsPastDue() {
            Instant activeEnd = NOW.plus(Duration.ofDays(10));

            var result = EntitlementCalculator.calculate(List.of(),
                    List.of(subscription(Subscription.PAST_DUE, NOW.minus(Duration.ofDays(1))),
                            subscription(Subscription.ACTIVE, activeEnd)),
                    GRACE, NOW);

            assertThat(result.validUntil()).isEqualTo(activeEnd);
        }
    }

    // -- fixtures ------------------------------------------------------------

    private static Purchase purchase(String planId) {
        return new Purchase(UUID.randomUUID(), ACCOUNT, "pi_" + UUID.randomUUID(), "cs_test",
                planId, 7900, "usd", NOW.minus(Duration.ofDays(1)));
    }

    private static Subscription subscription(String status, Instant periodEnd) {
        return new Subscription(UUID.randomUUID(), ACCOUNT, "sub_" + UUID.randomUUID(),
                "pro_monthly", status, periodEnd, false, NOW);
    }
}
