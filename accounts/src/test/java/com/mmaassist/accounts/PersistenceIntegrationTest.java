package com.mmaassist.accounts;

import static org.assertj.core.api.Assertions.assertThat;

import com.mmaassist.accounts.billing.domain.Entitlement;
import com.mmaassist.accounts.billing.domain.Plan;
import com.mmaassist.accounts.billing.domain.PlanRepository;
import com.mmaassist.accounts.billing.domain.Purchase;
import com.mmaassist.accounts.billing.domain.PurchaseRepository;
import com.mmaassist.accounts.billing.service.EntitlementService;
import com.mmaassist.accounts.identity.domain.Account;
import com.mmaassist.accounts.identity.domain.AccountRepository;
import com.mmaassist.accounts.identity.domain.LinkedIdentity;
import com.mmaassist.accounts.identity.domain.IdentityRepository;
import com.mmaassist.accounts.platform.spi.EntitlementLookup;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * Boots the real application against a real PostgreSQL.
 *
 * <p>This is the only test that can catch the class of bug the unit tests
 * structurally cannot: a Flyway migration that does not apply, a JPA mapping
 * that disagrees with the column it claims (Hibernate runs with
 * {@code ddl-auto: validate}, so a drifted entity fails startup here), and a
 * native query — {@code for update skip locked} — with no JPQL equivalent to
 * fall back on.
 *
 * <p>H2 is deliberately not used as a stand-in. It disagrees with PostgreSQL on
 * exactly the features this schema leans on, so a green H2 run would be
 * reassurance rather than evidence.
 *
 * <p>Skipped when Docker is unavailable, which includes some sandboxed
 * development environments. It is not optional in CI.
 */
@SpringBootTest
@Testcontainers
@EnabledIf("dockerAvailable")
class PersistenceIntegrationTest {

    @Container
    @SuppressWarnings("resource") // Testcontainers manages the lifecycle
    static final PostgreSQLContainer<?> POSTGRES =
            new PostgreSQLContainer<>("postgres:16-alpine")
                    .withDatabaseName("mmaassist")
                    .withUsername("test")
                    .withPassword("test");

    static boolean dockerAvailable() {
        try {
            return org.testcontainers.DockerClientFactory.instance().isDockerAvailable();
        } catch (Throwable t) {
            return false;
        }
    }

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
    }

    @Autowired private AccountRepository accounts;
    @Autowired private IdentityRepository identities;
    @Autowired private PurchaseRepository purchases;
    @Autowired private PlanRepository plans;
    @Autowired private EntitlementService entitlements;

    @Test
    @DisplayName("the migrations apply and seed the plan catalogue")
    void migrationsApplyAndSeedPlans() {
        assertThat(plans.findByActiveTrueOrderBySortOrderAsc())
                .extracting(Plan::getId)
                .containsExactly("pro_monthly", "pro_annual", "lifetime");
    }

    @Test
    @DisplayName("an account and its linked identity round-trip")
    void accountRoundTrips() {
        UUID accountId = UUID.randomUUID();
        Instant now = Instant.parse("2026-08-08T12:00:00Z");

        accounts.save(new Account(accountId, "roundtrip@example.test", "Round Trip", null, now));
        identities.save(new LinkedIdentity(UUID.randomUUID(), accountId, "google",
                "sub-" + accountId, "roundtrip@example.test", now));

        assertThat(accounts.findByEmailIgnoreCase("ROUNDTRIP@EXAMPLE.TEST"))
                .as("the lower(email) index is what makes this work")
                .isPresent();
        assertThat(identities.findByProviderAndProviderUserId("google", "sub-" + accountId))
                .isPresent();
    }

    @Test
    @DisplayName("a lifetime purchase produces a perpetual pro entitlement end to end")
    void purchaseGrantsEntitlement() {
        UUID accountId = UUID.randomUUID();
        Instant now = Instant.parse("2026-08-08T12:00:00Z");

        accounts.save(new Account(accountId, "buyer-" + accountId + "@example.test", "Buyer", null, now));
        purchases.save(new Purchase(UUID.randomUUID(), accountId, "pi_" + accountId,
                "cs_" + accountId, "lifetime", 7900, "usd", now));

        Entitlement entitlement = entitlements.recompute(accountId);

        assertThat(entitlement.getTier()).isEqualTo(Entitlement.TIER_PRO);
        assertThat(entitlement.getSource()).isEqualTo(Entitlement.SOURCE_LIFETIME);
        assertThat(entitlement.getValidUntil()).isNull();

        EntitlementLookup.Snapshot snapshot = entitlements.forAccount(accountId);
        assertThat(snapshot.isPro()).isTrue();
        assertThat(snapshot.features()).containsEntry("cloud_providers", true);
    }

    @Test
    @DisplayName("an account with nothing bought reads as free")
    void unknownAccountIsFree() {
        assertThat(entitlements.forAccount(UUID.randomUUID()).isPro()).isFalse();
    }
}
