package com.mmaassist.accounts.billing.domain;

import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface EntitlementRepository extends JpaRepository<Entitlement, UUID> {
}
