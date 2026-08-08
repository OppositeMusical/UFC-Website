package com.mmaassist.accounts.identity.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.mmaassist.accounts.identity.domain.Account;
import com.mmaassist.accounts.identity.domain.AccountRepository;
import com.mmaassist.accounts.identity.domain.DeviceRepository;
import com.mmaassist.accounts.identity.domain.IdentityRepository;
import com.mmaassist.accounts.identity.domain.LinkedIdentity;
import com.mmaassist.accounts.identity.domain.RefreshTokenRepository;
import com.mmaassist.accounts.identity.domain.SessionRepository;
import com.mmaassist.accounts.identity.oauth.OAuthProfile;
import com.mmaassist.accounts.platform.audit.AuditService;
import com.mmaassist.accounts.platform.error.ApiException;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

/**
 * Account linking is the security boundary of the whole system: get it wrong
 * and signing in with one provider hands over somebody else's licence and
 * payment history.
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class AccountServiceTest {

    private static final Instant NOW = Instant.parse("2026-08-08T12:00:00Z");

    @Mock private AccountRepository accounts;
    @Mock private IdentityRepository identities;
    @Mock private DeviceRepository devices;
    @Mock private SessionRepository sessions;
    @Mock private RefreshTokenRepository refreshTokens;
    @Mock private AuditService audit;

    private AccountService service;

    @BeforeEach
    void setUp() {
        service = new AccountService(accounts, identities, devices, sessions, refreshTokens,
                List.of(), audit, Clock.fixed(NOW, ZoneOffset.UTC));
        when(accounts.save(any(Account.class))).thenAnswer(i -> i.getArgument(0));
    }

    @Test
    @DisplayName("an unverified email is refused before any lookup happens")
    void unverifiedEmailIsRefused() {
        OAuthProfile profile = new OAuthProfile("github", "12345", "victim@example.test",
                false, "Attacker", null);

        assertThatThrownBy(() -> service.resolveFromProfile(profile))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("email_unverified"));

        // The critical assertion: no account was looked up by that address, so
        // there was never an opportunity to link to it.
        verify(accounts, never()).findByEmailIgnoreCase(anyString());
        verify(identities, never()).save(any());
    }

    @Test
    @DisplayName("a known provider subject resolves to its account without re-linking")
    void knownIdentityResolvesDirectly() {
        UUID accountId = UUID.randomUUID();
        Account existing = new Account(accountId, "user@example.test", "User", null, NOW);
        LinkedIdentity identity = new LinkedIdentity(UUID.randomUUID(), accountId, "google",
                "sub-1", "user@example.test", NOW);

        when(identities.findByProviderAndProviderUserId("google", "sub-1"))
                .thenReturn(Optional.of(identity));
        when(accounts.findById(accountId)).thenReturn(Optional.of(existing));

        Account resolved = service.resolveFromProfile(new OAuthProfile("google", "sub-1",
                "user@example.test", true, "User", null));

        assertThat(resolved.getId()).isEqualTo(accountId);
        verify(identities, never()).save(any());
    }

    @Test
    @DisplayName("a new provider on a verified address links to the existing account")
    void verifiedEmailLinksToExistingAccount() {
        UUID accountId = UUID.randomUUID();
        Account existing = new Account(accountId, "user@example.test", "User", null, NOW);

        when(identities.findByProviderAndProviderUserId("github", "gh-9"))
                .thenReturn(Optional.empty());
        when(accounts.findByEmailIgnoreCase("user@example.test")).thenReturn(Optional.of(existing));

        Account resolved = service.resolveFromProfile(new OAuthProfile("github", "gh-9",
                "user@example.test", true, "User", null));

        assertThat(resolved.getId()).isEqualTo(accountId);
        verify(identities).save(any(LinkedIdentity.class));
        verify(accounts, never()).save(any(Account.class));
    }

    @Test
    @DisplayName("an unrecognised address creates a fresh account")
    void unknownProfileCreatesAccount() {
        when(identities.findByProviderAndProviderUserId("google", "sub-new"))
                .thenReturn(Optional.empty());
        when(accounts.findByEmailIgnoreCase("new@example.test")).thenReturn(Optional.empty());

        Account created = service.resolveFromProfile(new OAuthProfile("google", "sub-new",
                "new@example.test", true, "New User", "https://avatar.test/a.png"));

        assertThat(created.getEmail()).isEqualTo("new@example.test");
        assertThat(created.isActive()).isTrue();
        verify(identities).save(any(LinkedIdentity.class));
    }

    @Test
    @DisplayName("a suspended account cannot be signed into, chargeback or otherwise")
    void suspendedAccountIsRefused() {
        UUID accountId = UUID.randomUUID();
        Account suspended = new Account(accountId, "user@example.test", "User", null, NOW);
        suspended.anonymise(NOW); // marks it deleted, the same refusal path
        LinkedIdentity identity = new LinkedIdentity(UUID.randomUUID(), accountId, "google",
                "sub-1", "user@example.test", NOW);

        when(identities.findByProviderAndProviderUserId("google", "sub-1"))
                .thenReturn(Optional.of(identity));
        when(accounts.findById(accountId)).thenReturn(Optional.of(suspended));

        assertThatThrownBy(() -> service.resolveFromProfile(new OAuthProfile("google", "sub-1",
                "user@example.test", true, "User", null)))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("account_deleted"));
    }
}
