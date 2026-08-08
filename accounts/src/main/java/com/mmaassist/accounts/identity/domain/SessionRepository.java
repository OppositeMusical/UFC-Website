package com.mmaassist.accounts.identity.domain;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface SessionRepository extends JpaRepository<AuthSession, UUID> {

    Optional<AuthSession> findByTokenHash(byte[] tokenHash);

    List<AuthSession> findByAccountIdAndRevokedAtIsNull(UUID accountId);

    @Modifying
    @Query("update AuthSession s set s.revokedAt = :now "
            + "where s.accountId = :accountId and s.revokedAt is null")
    int revokeAllForAccount(@Param("accountId") UUID accountId, @Param("now") Instant now);

    @Modifying
    @Query("update AuthSession s set s.revokedAt = :now "
            + "where s.deviceId = :deviceId and s.revokedAt is null")
    int revokeAllForDevice(@Param("deviceId") UUID deviceId, @Param("now") Instant now);

    @Modifying
    @Query("delete from AuthSession s where s.expiresAt < :cutoff")
    int deleteExpiredBefore(@Param("cutoff") Instant cutoff);
}
