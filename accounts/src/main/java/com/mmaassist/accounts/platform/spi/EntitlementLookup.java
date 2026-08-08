package com.mmaassist.accounts.platform.spi;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Read-only view of what an account is entitled to.
 *
 * <p>Implemented by {@code billing}, consumed by {@code identity} (for
 * {@code /v1/me}) and {@code licensing} (to mint a token). Declaring it here
 * means the identity module never has to know that entitlements have anything
 * to do with payments.
 */
public interface EntitlementLookup {

    Snapshot forAccount(UUID accountId);

    /**
     * @param tier       {@code free} or {@code pro}
     * @param source     {@code subscription}, {@code lifetime}, {@code grant}, or null when free
     * @param features   feature flags the desktop app gates on
     * @param validUntil when the entitlement lapses; null means perpetual
     */
    record Snapshot(String tier, String source, Map<String, Object> features, Instant validUntil) {

        public static final String TIER_FREE = "free";
        public static final String TIER_PRO = "pro";

        public static Snapshot free() {
            return new Snapshot(TIER_FREE, null, Map.of(), null);
        }

        public boolean isPro() {
            return TIER_PRO.equals(tier);
        }
    }
}
