package com.mmaassist.accounts;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.ArchRule;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * The module seam, enforced.
 *
 * <p>This service is one deployable on purpose — granting an entitlement when a
 * payment succeeds should be one transaction, not a distributed one. That
 * argument only holds while the boundaries stay real, and boundaries that live
 * only in a document stop being true within about a month. These rules are what
 * keep "we could split this later" from becoming a fiction.
 *
 * <p>The permitted direction is
 * {@code licensing → billing → identity → platform}.
 *
 * <p>Written as plain JUnit tests calling {@code rule.check(...)} rather than
 * with {@code @ArchTest} fields: under the ArchUnit JUnit engine surefire
 * reported "Tests run: 0" for this class, which means a violation might have
 * failed silently — a guard nobody can see working is not a guard.
 */
class ModuleBoundaryTest {

    private static JavaClasses productionClasses;

    @BeforeAll
    static void importClasses() {
        productionClasses = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages("com.mmaassist.accounts");
    }

    @Test
    @DisplayName("platform depends on no module above it")
    void platformDependsOnNothingAboveIt() {
        ArchRule rule = noClasses()
                .that().resideInAPackage("..platform..")
                .should().dependOnClassesThat()
                .resideInAnyPackage("..identity..", "..billing..", "..licensing..")
                .because("platform is the base layer; anything it needs from a module belongs "
                        + "behind an interface in platform.spi");

        rule.check(productionClasses);
    }

    @Test
    @DisplayName("identity knows nothing about money")
    void identityKnowsNothingOfBilling() {
        ArchRule rule = noClasses()
                .that().resideInAPackage("..identity..")
                .should().dependOnClassesThat().resideInAnyPackage("..billing..", "..licensing..")
                .because("identity must work in a deployment with no Stripe keys at all; "
                        + "entitlements reach it through platform.spi.EntitlementLookup");

        rule.check(productionClasses);
    }

    @Test
    @DisplayName("billing knows nothing about licensing")
    void billingKnowsNothingOfLicensing() {
        ArchRule rule = noClasses()
                .that().resideInAPackage("..billing..")
                .should().dependOnClassesThat().resideInAPackage("..licensing..")
                .because("licences are derived from entitlements, never the other way round");

        rule.check(productionClasses);
    }

    @Test
    @DisplayName("only the gateway imports the Stripe SDK")
    void onlyTheGatewayTouchesStripe() {
        ArchRule rule = noClasses()
                .that().resideOutsideOfPackage("..billing.service..")
                .should().dependOnClassesThat().resideInAPackage("com.stripe..")
                .because("an SDK upgrade that renames something should break one file, not twelve");

        rule.check(productionClasses);
    }

    @Test
    @DisplayName("the rules are actually evaluated - a deliberately false rule must fail")
    void theseRulesGenuinelyRun() {
        // Guards the guards. If the importer silently produced nothing, every
        // `noClasses()` rule above would pass vacuously and this file would be
        // decoration. A rule that must fail proves the import found real code.
        ArchRule mustFail = noClasses()
                .that().resideInAPackage("..billing..")
                .should().dependOnClassesThat().resideInAPackage("..platform..");

        org.assertj.core.api.Assertions
                .assertThatThrownBy(() -> mustFail.check(productionClasses))
                .isInstanceOf(AssertionError.class);
    }
}
