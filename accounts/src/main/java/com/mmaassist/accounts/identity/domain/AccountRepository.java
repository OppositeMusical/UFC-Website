package com.mmaassist.accounts.identity.domain;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface AccountRepository extends JpaRepository<Account, UUID> {

    /**
     * Case-insensitive lookup, matching the {@code lower(email)} unique index.
     * Comparing with {@code =} would let a login find nothing and try to create
     * a second account for the same address in different case — which the index
     * then rejects, turning a routine link into a 500.
     */
    @Query("select a from Account a where lower(a.email) = lower(:email)")
    Optional<Account> findByEmailIgnoreCase(@Param("email") String email);
}
