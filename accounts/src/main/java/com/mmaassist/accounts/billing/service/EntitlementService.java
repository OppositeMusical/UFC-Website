package com.mmaassist.accounts.billing.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mmaassist.accounts.billing.domain.Entitlement;
import com.mmaassist.accounts.billing.domain.EntitlementRepository;
import com.mmaassist.accounts.billing.domain.Plan;
import com.mmaassist.accounts.billing.domain.PlanRepository;
import com.mmaassist.accounts.billing.domain.PurchaseRepository;
import com.mmaassist.accounts.billing.domain.SubscriptionRepository;
import com.mmaassist.accounts.platform.audit.AuditService;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.spi.EntitlementLookup;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Owns the entitlements table: recomputes it, and answers questions about it. */
@Service
public class EntitlementService implements EntitlementLookup {

    private static final Logger log = LoggerFactory.getLogger(EntitlementService.class);

    private final EntitlementRepository entitlements;
    private final PurchaseRepository purchases;
    private final SubscriptionRepository subscriptions;
    private final PlanRepository plans;
    private final AuditService audit;
    private final AppProperties properties;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public EntitlementService(EntitlementRepository entitlements, PurchaseRepository purchases,
                              SubscriptionRepository subscriptions, PlanRepository plans,
                              AuditService audit, AppProperties properties,
                              ObjectMapper objectMapper, Clock clock) {
        this.entitlements = entitlements;
        this.purchases = purchases;
        this.subscriptions = subscriptions;
        this.plans = plans;
        this.audit = audit;
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    /**
     * Recomputes and stores the entitlement for one account.
     *
     * <p>Call this after every billing change, from inside the same transaction
     * as the change. There is no other way an entitlement is allowed to move.
     */
    @Transactional
    public Entitlement recompute(UUID accountId) {
        Instant now = clock.instant();

        EntitlementCalculator.Result result = EntitlementCalculator.calculate(
                purchases.findByAccountId(accountId),
                subscriptions.findByAccountId(accountId),
                properties.getStripe().getDunningGrace(),
                now);

        String features = result.planId() == null ? "{}" : plans.findById(result.planId())
                .map(Plan::getFeatures)
                .orElse("{}");

        Entitlement entitlement = entitlements.findById(accountId)
                .orElseGet(() -> entitlements.save(new Entitlement(accountId, now)));

        String previousTier = entitlement.getTier();
        entitlement.apply(result.tier(), result.source(), features, result.validUntil(), now);

        if (!previousTier.equals(result.tier())) {
            audit.record(accountId, AuditService.ACTOR_SYSTEM, "entitlement.changed",
                    Map.of("from", previousTier, "to", result.tier(),
                            "source", String.valueOf(result.source())));
            log.info("entitlement for {} moved {} -> {} ({})",
                    accountId, previousTier, result.tier(), result.source());
        }
        return entitlement;
    }

    @Override
    @Transactional(readOnly = true)
    public Snapshot forAccount(UUID accountId) {
        return entitlements.findById(accountId)
                .map(this::toSnapshot)
                .orElseGet(Snapshot::free);
    }

    private Snapshot toSnapshot(Entitlement entitlement) {
        // A stored row whose window has closed reads as free until something
        // recomputes it. Trusting the stale row instead would keep handing out
        // Pro after a subscription lapsed, purely because no webhook happened
        // to arrive.
        if (entitlement.getValidUntil() != null && entitlement.getValidUntil().isBefore(clock.instant())) {
            return Snapshot.free();
        }
        return new Snapshot(entitlement.getTier(), entitlement.getSource(),
                parseFeatures(entitlement.getFeatures()), entitlement.getValidUntil());
    }

    private Map<String, Object> parseFeatures(String json) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<Map<String, Object>>() { });
        } catch (Exception e) {
            // Corrupt feature JSON must not take down the account page. Falling
            // back to "no features" is the safe direction to fail in.
            log.warn("could not parse entitlement features: {}", json, e);
            return Map.of();
        }
    }
}
