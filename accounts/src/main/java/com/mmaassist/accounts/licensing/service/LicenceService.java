package com.mmaassist.accounts.licensing.service;

import com.mmaassist.accounts.identity.domain.Device;
import com.mmaassist.accounts.identity.domain.DeviceRepository;
import com.mmaassist.accounts.identity.service.AccountService;
import com.mmaassist.accounts.licensing.LicenceTokenSigner;
import com.mmaassist.accounts.licensing.domain.LicenceToken;
import com.mmaassist.accounts.licensing.domain.LicenceTokenRepository;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import com.mmaassist.accounts.platform.spi.EntitlementLookup;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Mints licence tokens against the current entitlement. */
@Service
public class LicenceService {

    private static final Logger log = LoggerFactory.getLogger(LicenceService.class);

    public record IssuedLicence(String token, String tier, Instant expiresAt, int graceDays) {
    }

    private final EntitlementLookup entitlements;
    private final LicenceTokenSigner signer;
    private final LicenceTokenRepository tokens;
    private final DeviceRepository devices;
    private final AccountService accounts;
    private final AppProperties properties;
    private final Clock clock;

    public LicenceService(EntitlementLookup entitlements, LicenceTokenSigner signer,
                          LicenceTokenRepository tokens, DeviceRepository devices,
                          AccountService accounts, AppProperties properties, Clock clock) {
        this.entitlements = entitlements;
        this.signer = signer;
        this.tokens = tokens;
        this.devices = devices;
        this.accounts = accounts;
        this.properties = properties;
        this.clock = clock;
    }

    /**
     * Issues a licence for one device, superseding whatever that device held.
     *
     * <p>A free-tier account gets a token too, saying so. Returning an error
     * instead would leave the app unable to tell "not entitled" apart from
     * "server unreachable", and it would retry the call forever.
     */
    @Transactional
    public IssuedLicence issue(UUID accountId, UUID deviceId) {
        Instant now = clock.instant();

        Device device = devices.findById(deviceId)
                .filter(d -> d.getAccountId().equals(accountId))
                .orElseThrow(() -> ApiException.notFound("device_not_found", "Unknown device."));
        if (!device.isActive()) {
            throw ApiException.forbidden("device_revoked",
                    "This device was signed out from your account page. Sign in again.");
        }

        EntitlementLookup.Snapshot entitlement = entitlements.forAccount(accountId);
        Instant expiresAt = expiryFor(entitlement, now);

        // One live token per device: the previous one is revoked so a refresh
        // cannot be used to keep an old, more generous licence alive.
        tokens.revokeForDevice(deviceId, now);

        UUID jti = UUID.randomUUID();
        tokens.save(new LicenceToken(jti, accountId, deviceId, now, expiresAt));

        String email = accounts.require(accountId).getEmail();
        String token = signer.sign(accountId, deviceId, jti, entitlement.tier(),
                entitlement.features(), email, now, expiresAt);

        log.debug("issued {} licence for account {} device {} until {}",
                entitlement.tier(), accountId, deviceId, expiresAt);
        return new IssuedLicence(token, entitlement.tier(), expiresAt,
                properties.getLicence().getGraceDays());
    }

    /**
     * How long this token should live.
     *
     * <p>The standard lifetime, unless the entitlement itself runs out sooner —
     * a subscription cancelled mid-period must not hand out a token that
     * outlives the period it paid for. A lifetime purchase gets the longer
     * window because there is nothing to re-check.
     */
    private Instant expiryFor(EntitlementLookup.Snapshot entitlement, Instant now) {
        Duration ttl = "lifetime".equals(entitlement.source())
                ? properties.getLicence().getLifetimeTtl()
                : properties.getLicence().getSubscriptionTtl();

        Instant expiry = now.plus(ttl);
        if (entitlement.validUntil() != null && entitlement.validUntil().isBefore(expiry)) {
            expiry = entitlement.validUntil();
        }
        // A lapsed entitlement still gets a (free-tier) token, and a token that
        // has already expired is not one - give it a short life so the app
        // stops asking for a while.
        if (!expiry.isAfter(now)) {
            expiry = now.plus(Duration.ofDays(1));
        }
        return expiry;
    }

    @Scheduled(cron = "0 45 4 * * *")
    @Transactional
    public void purgeExpiredTokens() {
        tokens.deleteExpiredBefore(clock.instant().minus(Duration.ofDays(30)));
    }
}
