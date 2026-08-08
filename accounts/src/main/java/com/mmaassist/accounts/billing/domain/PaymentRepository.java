package com.mmaassist.accounts.billing.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PaymentRepository extends JpaRepository<Payment, UUID> {

    List<Payment> findByAccountIdOrderByOccurredAtDesc(UUID accountId);

    Optional<Payment> findByStripeObjectId(String stripeObjectId);
}
