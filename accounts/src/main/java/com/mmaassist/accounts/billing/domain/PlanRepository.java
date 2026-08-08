package com.mmaassist.accounts.billing.domain;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PlanRepository extends JpaRepository<Plan, String> {

    List<Plan> findByActiveTrueOrderBySortOrderAsc();

    Optional<Plan> findByStripePriceId(String stripePriceId);
}
