package com.mmaassist.accounts;

import com.mmaassist.accounts.platform.config.AppProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Accounts, payments, and desktop licensing for MMA Assist.
 *
 * <p>One deployable, three modules ({@code identity}, {@code billing},
 * {@code licensing}) over one database. Granting an entitlement when a payment
 * succeeds is a single transaction; splitting that across a network boundary
 * would buy nothing at this traffic level and cost correctness. The module
 * boundaries are enforced by {@code ModuleBoundaryTest} so the seam stays real
 * if it ever does need to split.
 */
@SpringBootApplication
@EnableConfigurationProperties(AppProperties.class)
@EnableScheduling
public class AccountsApplication {

    public static void main(String[] args) {
        SpringApplication.run(AccountsApplication.class, args);
    }
}
