package com.mmaassist.accounts.billing.web;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mmaassist.accounts.billing.domain.Plan;
import com.mmaassist.accounts.billing.domain.PlanRepository;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The public plan catalogue.
 *
 * <p>The pricing page renders from this, so a price change is a row update
 * rather than a frontend deploy — and the price the site shows is by
 * construction the price Stripe will charge.
 */
@RestController
@RequestMapping("/v1/plans")
public class PlanController {

    private final PlanRepository plans;
    private final ObjectMapper objectMapper;

    public PlanController(PlanRepository plans, ObjectMapper objectMapper) {
        this.plans = plans;
        this.objectMapper = objectMapper;
    }

    @GetMapping
    public Map<String, Object> list() {
        List<PlanView> views = plans.findByActiveTrueOrderBySortOrderAsc().stream()
                .map(this::toView)
                .toList();
        return Map.of("plans", views);
    }

    private PlanView toView(Plan plan) {
        Map<String, Object> features;
        try {
            features = objectMapper.readValue(plan.getFeatures(),
                    new TypeReference<Map<String, Object>>() { });
        } catch (Exception e) {
            features = Map.of();
        }
        // Note what is absent: stripe_price_id. It is not secret, but the
        // browser has no use for it - checkout is started by plan id, server
        // side, so a tampered price can never reach Stripe.
        return new PlanView(plan.getId(), plan.getDisplayName(), plan.getDescription(),
                plan.getKind(), plan.getBillingInterval(), plan.getAmountMinor(),
                plan.getCurrency(), features);
    }

    public record PlanView(String id, String displayName, String description, String kind,
                           String interval, int amountMinor, String currency,
                           Map<String, Object> features) {
    }
}
