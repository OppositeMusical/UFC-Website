package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.StripeEventRepository;
import com.mmaassist.accounts.billing.domain.Subscription;
import com.mmaassist.accounts.billing.domain.SubscriptionRepository;
import com.mmaassist.accounts.platform.audit.AuditService;
import com.mmaassist.accounts.platform.config.AppProperties;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * Nightly check that our idea of who has paid still matches Stripe's.
 *
 * <p>Webhooks are best-effort. Stripe retries for three days and then stops, so
 * an outage longer than that leaves permanent drift with nothing to detect it.
 * This is the backstop.
 *
 * <p>It repairs discrepancies <em>and</em> logs them at warn. Repairing quietly
 * would hide the actual bug — a webhook endpoint that has been failing for a
 * week looks exactly like a healthy system if something keeps tidying up after
 * it.
 */
@Component
public class ReconciliationJob {

    private static final Logger log = LoggerFactory.getLogger(ReconciliationJob.class);

    private final SubscriptionRepository subscriptions;
    private final StripeEventRepository events;
    private final StripeGateway gateway;
    private final EntitlementService entitlements;
    private final AuditService audit;
    private final AppProperties properties;
    private final Clock clock;

    public ReconciliationJob(SubscriptionRepository subscriptions, StripeEventRepository events,
                             StripeGateway gateway, EntitlementService entitlements,
                             AuditService audit, AppProperties properties, Clock clock) {
        this.subscriptions = subscriptions;
        this.events = events;
        this.gateway = gateway;
        this.entitlements = entitlements;
        this.audit = audit;
        this.properties = properties;
        this.clock = clock;
    }

    @Scheduled(cron = "${app.reconciliation.cron}")
    @Transactional
    public void reconcile() {
        if (!gateway.isConfigured()) {
            return;
        }

        int drifted = 0;
        // Terminal subscriptions cannot come back, so re-fetching them every
        // night is pure API budget for a guaranteed answer.
        for (Subscription local : subscriptions.findByStatusNotIn(Subscription.TERMINAL)) {
            try {
                StripeGateway.RemoteSubscription remote =
                        gateway.retrieveSubscription(local.getStripeSubscriptionId());

                boolean statusDrift = !local.getStatus().equals(remote.status());
                boolean periodDrift = local.getCurrentPeriodEnd() == null
                        ? remote.currentPeriodEnd() != null
                        : !local.getCurrentPeriodEnd().equals(remote.currentPeriodEnd());

                if (statusDrift || periodDrift) {
                    log.warn("reconciliation drift on {}: local status={} periodEnd={}, "
                                    + "stripe status={} periodEnd={} - check the webhook endpoint",
                            local.getStripeSubscriptionId(), local.getStatus(),
                            local.getCurrentPeriodEnd(), remote.status(), remote.currentPeriodEnd());

                    // A null event timestamp means "newer than anything we
                    // hold", which is right: Stripe just told us directly.
                    local.applyUpdate(remote.status(), remote.currentPeriodEnd(),
                            remote.cancelAtPeriodEnd(), remote.canceledAt(), null, null, clock.instant());
                    entitlements.recompute(local.getAccountId());

                    audit.record(local.getAccountId(), AuditService.ACTOR_SYSTEM,
                            "reconciliation.repaired",
                            Map.of("subscription", local.getStripeSubscriptionId(),
                                    "status", remote.status()));
                    drifted++;
                }
            } catch (Exception e) {
                // One unreachable subscription must not abandon the rest.
                log.error("could not reconcile subscription {}", local.getStripeSubscriptionId(), e);
            }
        }

        long stuck = events.countByProcessedAtIsNullAndReceivedAtBefore(
                clock.instant().minus(Duration.ofMinutes(5)));
        if (stuck > 0) {
            log.error("{} stripe events have been unprocessed for over five minutes", stuck);
        }

        log.info("reconciliation finished: {} drifted subscription(s), {} stuck event(s)",
                drifted, stuck);
    }

    /** Visible for tests: the lookback the job would use for a time-boxed sweep. */
    Instant lookbackFrom() {
        return clock.instant().minus(properties.getReconciliation().getLookback());
    }
}
