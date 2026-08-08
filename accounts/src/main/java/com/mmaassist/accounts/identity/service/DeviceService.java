package com.mmaassist.accounts.identity.service;

import com.mmaassist.accounts.identity.domain.Device;
import com.mmaassist.accounts.identity.domain.DeviceRepository;
import com.mmaassist.accounts.identity.domain.RefreshTokenRepository;
import com.mmaassist.accounts.identity.domain.SessionRepository;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DeviceService {

    private final DeviceRepository devices;
    private final SessionRepository sessions;
    private final RefreshTokenRepository refreshTokens;
    private final AppProperties properties;
    private final Clock clock;

    public DeviceService(DeviceRepository devices, SessionRepository sessions,
                         RefreshTokenRepository refreshTokens, AppProperties properties, Clock clock) {
        this.devices = devices;
        this.sessions = sessions;
        this.refreshTokens = refreshTokens;
        this.properties = properties;
        this.clock = clock;
    }

    /**
     * Finds the install or registers it, enforcing the device cap.
     *
     * <p>An install that is already known never trips the cap, however many
     * there are — otherwise raising the limit would strand existing users, and
     * a signed-in machine could lose access because of something that happened
     * on a different one.
     */
    @Transactional
    public Device registerOrTouch(UUID accountId, String installId, String name, String appVersion) {
        Instant now = clock.instant();
        Optional<Device> existing = devices.findByAccountIdAndInstallId(accountId, installId);

        if (existing.isPresent()) {
            Device device = existing.get();
            if (!device.isActive()) {
                requireCapacity(accountId);
                device.reinstate(now);
            }
            device.seen(appVersion, name, now);
            return device;
        }

        requireCapacity(accountId);
        return devices.save(new Device(UUID.randomUUID(), accountId, installId, name, appVersion, now));
    }

    private void requireCapacity(UUID accountId) {
        int limit = properties.getDesktop().getDeviceLimit();
        if (devices.countByAccountIdAndRevokedAtIsNull(accountId) >= limit) {
            // Naming the devices matters: the user has to be able to work out
            // which one to remove, and an opaque refusal turns a self-service
            // action into a support ticket.
            throw ApiException.forbidden("device_limit_exceeded",
                            "You are signed in on the maximum of " + limit
                                    + " devices. Remove one from your account page first.")
                    .with("limit", limit)
                    .with("devices", list(accountId).stream()
                            .map(d -> java.util.Map.of(
                                    "id", d.getId().toString(),
                                    "name", d.getName() == null ? "Unnamed device" : d.getName(),
                                    "lastSeenAt", d.getLastSeenAt().toString()))
                            .toList());
        }
    }

    @Transactional(readOnly = true)
    public List<Device> list(UUID accountId) {
        return devices.findByAccountIdOrderByLastSeenAtDesc(accountId).stream()
                .filter(Device::isActive)
                .toList();
    }

    /**
     * Signs a device out and stops its licence from refreshing. Its current
     * licence token keeps working until it expires — revoking that instantly is
     * what {@code billing.licence_tokens.revoked_at} is for, and the licence
     * module handles it.
     */
    @Transactional
    public void revoke(UUID accountId, UUID deviceId) {
        Device device = devices.findById(deviceId)
                .filter(d -> d.getAccountId().equals(accountId))
                .orElseThrow(() -> ApiException.notFound("device_not_found", "Device not found."));

        Instant now = clock.instant();
        device.revoke(now);
        sessions.revokeAllForDevice(deviceId, now);
        refreshTokens.revokeAllForDevice(deviceId, now);
    }
}
