package com.mmaassist.accounts.identity.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DeviceRepository extends JpaRepository<Device, UUID> {

    Optional<Device> findByAccountIdAndInstallId(UUID accountId, String installId);

    List<Device> findByAccountIdOrderByLastSeenAtDesc(UUID accountId);

    long countByAccountIdAndRevokedAtIsNull(UUID accountId);
}
