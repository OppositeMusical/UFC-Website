package com.mmaassist.accounts.licensing.domain;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface LicenceTokenRepository extends JpaRepository<LicenceToken, UUID> {

    List<LicenceToken> findByDeviceIdAndRevokedAtIsNull(UUID deviceId);

    @Modifying
    @Query("update LicenceToken t set t.revokedAt = :now "
            + "where t.deviceId = :deviceId and t.revokedAt is null")
    int revokeForDevice(@Param("deviceId") UUID deviceId, @Param("now") Instant now);

    /** Expired tokens are worthless; this table would otherwise grow forever. */
    @Modifying
    @Query("delete from LicenceToken t where t.expiresAt < :cutoff")
    int deleteExpiredBefore(@Param("cutoff") Instant cutoff);
}
