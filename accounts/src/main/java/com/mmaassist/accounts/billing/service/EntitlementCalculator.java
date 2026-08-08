package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.Entitlement;
import com.mmaassist.accounts.billing.domain.Purchase;
import com.mmaassist.accounts.billing.domain.Subscription;
import java.time.Duration;
import java.time.Instant;
import java.util.Collection;
import java.util.Comparator;
import java.util.Optional;

/**
 * Decides what an account is entitled to, given everything it has ever bought.
 *
 * <p>Deliberately a pure function over plain arguments: no repositories, no
 * clock field, no Spring. This is the single most consequential piece of logic
 * in the service — it is what stands between a customer and the thing they paid
 * for — and it should be possible to enumerate every input combination in a
 * table test without a database anywhere near it.
 *
 * <p>Precedence, highest first:
 * <ol>
 *   <li><b>Lifetime purchase</b> — perpetual, and outranks everything. Someone
 *       who bought lifetime and later also subscribed does not lose access when
 *       the subscription lapses.</li>
 *   <li><b>Active or trialing subscription</b> — until the period ends.</li>
 *   <li><b>Past-due subscription</b> — until the period ends plus the dunning
 *       grace, because a failed renewal is usually an expired card rather than
 *       a departing customer. Stripe's Smart Retries run for about two weeks;
 *       cutting access on day one turns a card update into a refund request.</li>
 *   <li>Otherwise free.</li>
 * </ol>
 */
public final class EntitlementCalculator {

    /**
     * @param planId the plan whose feature set applies; null when free
     * @param validUntil null means perpetual
     */
    public record Result(String tier, String source, String planId, Instant validUntil) {

        public static Result free() {
            return new Result(Entitlement.TIER_FREE, null, null, null);
        }

        public boolean isPro() {
            return Entitlement.TIER_PRO.equals(tier);
        }
    }

    private EntitlementCalculator() {
    }

    public static Result calculate(Collection<Purchase> purchases,
                                   Collection<Subscription> subscriptions,
                                   Duration dunningGrace,
                                   Instant now) {

        Optional<Purchase> lifetime = purchases.stream()
                .filter(Purchase::grantsAccess)
                .findFirst();
        if (lifetime.isPresent()) {
            return new Result(Entitlement.TIER_PRO, Entitlement.SOURCE_LIFETIME,
                    lifetime.get().getPlanId(), null);
        }

        Optional<Subscription> granting = subscriptions.stream()
                .filter(Subscription::isGranting)
                .max(Comparator.comparing(Subscription::getCurrentPeriodEnd,
                        Comparator.nullsFirst(Comparator.naturalOrder())));
        if (granting.isPresent()) {
            Subscription subscription = granting.get();
            // A null period end leaves validUntil null, which the licence
            // signer reads as "use the standard token lifetime". That caps the
            // exposure at one token's worth of time rather than granting
            // something perpetual off a malformed record.
            return new Result(Entitlement.TIER_PRO, Entitlement.SOURCE_SUBSCRIPTION,
                    subscription.getPlanId(), subscription.getCurrentPeriodEnd());
        }

        Optional<Subscription> pastDue = subscriptions.stream()
                .filter(Subscription::isPastDue)
                .filter(s -> s.getCurrentPeriodEnd() != null)
                .max(Comparator.comparing(Subscription::getCurrentPeriodEnd));
        if (pastDue.isPresent()) {
            Instant graceEnds = pastDue.get().getCurrentPeriodEnd().plus(dunningGrace);
            // Only grant while the grace window is genuinely open. Stripe will
            // move a long-dead subscription to unpaid or canceled, but webhooks
            // lag and reconciliation runs nightly, so this must not depend on
            // either having happened yet.
            if (graceEnds.isAfter(now)) {
                return new Result(Entitlement.TIER_PRO, Entitlement.SOURCE_SUBSCRIPTION,
                        pastDue.get().getPlanId(), graceEnds);
            }
        }

        return Result.free();
    }
}
