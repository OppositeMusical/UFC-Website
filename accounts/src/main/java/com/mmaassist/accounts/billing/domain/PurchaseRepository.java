package com.mmaassist.accounts.billing.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PurchaseRepository extends JpaRepository<Purchase, UUID> {

    List<Purchase> findByAccountId(UUID accountId);

    Optional<Purchase> findByStripePaymentIntentId(String paymentIntentId);

    Optional<Purchase> findByStripeCheckoutSessionId(String checkoutSessionId);
}
