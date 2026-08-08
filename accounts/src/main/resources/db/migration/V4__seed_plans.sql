-- The three purchasable plans.
--
-- Stripe price ids are environment-specific (test mode and live mode issue
-- different ones), so these are placeholders that must be updated per
-- environment before checkout works. `PlanCatalogueValidator` logs a warning at
-- startup for any active plan still carrying a placeholder, rather than letting
-- the first real customer discover it.
insert into billing.plans
    (id, stripe_price_id, kind, billing_interval, amount_minor, currency,
     features, display_name, description, sort_order, active)
values
    ('pro_monthly', 'price_REPLACE_ME_monthly', 'subscription', 'month', 499, 'usd',
     '{"cloud_providers":true,"all_platforms":true,"kalshi_market":true,"unlimited_history":true}',
     'Pro Monthly', 'Everything unlocked, cancel anytime.', 10, true),

    ('pro_annual', 'price_REPLACE_ME_annual', 'subscription', 'year', 3900, 'usd',
     '{"cloud_providers":true,"all_platforms":true,"kalshi_market":true,"unlimited_history":true}',
     'Pro Annual', 'Two months free compared with monthly.', 20, true),

    ('lifetime', 'price_REPLACE_ME_lifetime', 'one_time', null, 7900, 'usd',
     '{"cloud_providers":true,"all_platforms":true,"kalshi_market":true,"unlimited_history":true}',
     'Lifetime', 'Pay once. Yours for good, including future versions.', 30, true);
