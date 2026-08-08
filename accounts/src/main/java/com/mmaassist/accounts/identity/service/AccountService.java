package com.mmaassist.accounts.identity.service;

import com.mmaassist.accounts.identity.domain.Account;
import com.mmaassist.accounts.identity.domain.AccountRepository;
import com.mmaassist.accounts.identity.domain.Device;
import com.mmaassist.accounts.identity.domain.DeviceRepository;
import com.mmaassist.accounts.identity.domain.IdentityRepository;
import com.mmaassist.accounts.identity.domain.LinkedIdentity;
import com.mmaassist.accounts.identity.domain.RefreshTokenRepository;
import com.mmaassist.accounts.identity.domain.SessionRepository;
import com.mmaassist.accounts.identity.oauth.OAuthProfile;
import com.mmaassist.accounts.platform.audit.AuditService;
import com.mmaassist.accounts.platform.error.ApiException;
import com.mmaassist.accounts.platform.spi.AccountClosureListener;
import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Turning "somebody signed in with Google" into "this account". */
@Service
public class AccountService {

    private static final Logger log = LoggerFactory.getLogger(AccountService.class);

    private final AccountRepository accounts;
    private final IdentityRepository identities;
    private final DeviceRepository devices;
    private final SessionRepository sessions;
    private final RefreshTokenRepository refreshTokens;
    private final List<AccountClosureListener> closureListeners;
    private final AuditService audit;
    private final Clock clock;

    public AccountService(AccountRepository accounts, IdentityRepository identities,
                          DeviceRepository devices, SessionRepository sessions,
                          RefreshTokenRepository refreshTokens,
                          List<AccountClosureListener> closureListeners,
                          AuditService audit, Clock clock) {
        this.accounts = accounts;
        this.identities = identities;
        this.devices = devices;
        this.sessions = sessions;
        this.refreshTokens = refreshTokens;
        this.closureListeners = closureListeners;
        this.audit = audit;
        this.clock = clock;
    }

    /**
     * Resolves a provider profile to an account, creating or linking as needed.
     *
     * <p>The rule, in order:
     * <ol>
     *   <li>a known {@code (provider, subject)} pair is that account, full stop;</li>
     *   <li>otherwise a matching <em>verified</em> email links this provider to
     *       the existing account;</li>
     *   <li>otherwise a new account.</li>
     * </ol>
     *
     * <p>Step 2 is the dangerous one, and it is why an unverified address is
     * refused before any of this runs: if an attacker could present an
     * unverified {@code victim@example.com}, they would be handed the victim's
     * account, their Pro licence, and their payment history.
     */
    @Transactional
    public Account resolveFromProfile(OAuthProfile profile) {
        if (!profile.emailVerified()) {
            throw ApiException.badRequest("email_unverified",
                    "That account's email address is not verified with " + profile.provider()
                            + ". Verify it there first, then sign in again.");
        }

        Instant now = clock.instant();

        Optional<LinkedIdentity> existing =
                identities.findByProviderAndProviderUserId(profile.provider(), profile.providerUserId());

        if (existing.isPresent()) {
            LinkedIdentity identity = existing.get();
            Account account = accounts.findById(identity.getAccountId())
                    .orElseThrow(() -> new IllegalStateException(
                            "identity " + identity.getId() + " points at a missing account"));
            requireUsable(account);
            identity.touch(now);
            account.updateProfile(profile.displayName(), profile.avatarUrl(), now);
            return account;
        }

        Optional<Account> byEmail = accounts.findByEmailIgnoreCase(profile.email());
        if (byEmail.isPresent()) {
            Account account = byEmail.get();
            requireUsable(account);
            identities.save(new LinkedIdentity(UUID.randomUUID(), account.getId(), profile.provider(),
                    profile.providerUserId(), profile.email(), now));
            account.updateProfile(profile.displayName(), profile.avatarUrl(), now);
            audit.record(account.getId(), AuditService.ACTOR_SYSTEM, "identity.linked",
                    Map.of("provider", profile.provider()));
            log.info("linked {} identity to existing account {}", profile.provider(), account.getId());
            return account;
        }

        Account account = accounts.save(new Account(UUID.randomUUID(), profile.email(),
                profile.displayName(), profile.avatarUrl(), now));
        identities.save(new LinkedIdentity(UUID.randomUUID(), account.getId(), profile.provider(),
                profile.providerUserId(), profile.email(), now));
        audit.record(account.getId(), AuditService.ACTOR_SYSTEM, "account.created",
                Map.of("provider", profile.provider()));
        log.info("created account {} via {}", account.getId(), profile.provider());
        return account;
    }

    @Transactional(readOnly = true)
    public Account require(UUID accountId) {
        return accounts.findById(accountId)
                .orElseThrow(() -> ApiException.notFound("account_not_found", "Account not found."));
    }

    @Transactional(readOnly = true)
    public List<String> linkedProviders(UUID accountId) {
        return identities.findByAccountId(accountId).stream()
                .map(LinkedIdentity::getProvider)
                .sorted()
                .toList();
    }

    /**
     * Closes an account: cancels anything billable, drops every credential, and
     * strips the personal fields from the row.
     *
     * <p>The row itself survives, and so do the payment records that reference
     * it. Tax and anti-fraud rules require keeping those for years, and
     * {@code billing.customers} has an {@code on delete restrict} that enforces
     * it rather than trusting this method to remember. The privacy policy has
     * to say so — "we delete everything" would simply be untrue.
     */
    @Transactional
    public void closeAccount(UUID accountId) {
        Account account = require(accountId);
        Instant now = clock.instant();

        // Billing first: if a subscription cannot be cancelled, the whole
        // transaction rolls back and the account stays open. Deleting it while
        // continuing to charge the card would be the worst available outcome.
        for (AccountClosureListener listener : closureListeners) {
            listener.onAccountClosing(accountId);
        }

        sessions.revokeAllForAccount(accountId, now);
        for (Device device : devices.findByAccountIdOrderByLastSeenAtDesc(accountId)) {
            device.revoke(now);
            refreshTokens.revokeAllForDevice(device.getId(), now);
        }
        identities.deleteAll(identities.findByAccountId(accountId));

        account.anonymise(now);
        audit.record(accountId, AuditService.ACTOR_SYSTEM, "account.closed", Map.of());
        log.info("closed account {}", accountId);
    }

    private void requireUsable(Account account) {
        if (Account.STATUS_SUSPENDED.equals(account.getStatus())) {
            throw ApiException.forbidden("account_suspended",
                    "This account is suspended. Contact support.");
        }
        if (Account.STATUS_DELETED.equals(account.getStatus())) {
            // Re-registering with the same address should produce a fresh
            // account rather than resurrect a deleted one, but the deleted row
            // still holds the old (now invalid) address, so it cannot collide.
            throw ApiException.forbidden("account_deleted", "This account has been deleted.");
        }
    }
}
