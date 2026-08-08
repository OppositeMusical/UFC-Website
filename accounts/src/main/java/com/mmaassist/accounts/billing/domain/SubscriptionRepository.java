package com.mmaassist.accounts.billing.domain;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SubscriptionRepository extends JpaRepository<Subscription, UUID> {

    List<Subscription> findByAccountId(UUID accountId);

    Optional<Subscription> findByStripeSubscriptionId(String stripeSubscriptionId);

    /**
     * Everything reconciliation still needs to check. A canceled subscription
     * cannot come back, so re-fetching it every night is pure API budget.
     */
    List<Subscription> findByStatusNotIn(Collection<String> statuses);
}
