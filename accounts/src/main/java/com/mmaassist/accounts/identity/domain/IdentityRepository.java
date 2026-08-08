package com.mmaassist.accounts.identity.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface IdentityRepository extends JpaRepository<LinkedIdentity, UUID> {

    Optional<LinkedIdentity> findByProviderAndProviderUserId(String provider, String providerUserId);

    List<LinkedIdentity> findByAccountId(UUID accountId);
}
