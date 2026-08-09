package com.mmaassist.accounts.identity.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.mmaassist.accounts.identity.domain.Device;
import com.mmaassist.accounts.identity.domain.DeviceRepository;
import com.mmaassist.accounts.identity.domain.RefreshTokenRepository;
import com.mmaassist.accounts.identity.domain.SessionRepository;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class DeviceServiceTest {

    private static final Instant NOW = Instant.parse("2026-08-08T12:00:00Z");
    private static final UUID ACCOUNT = UUID.randomUUID();

    @Mock private DeviceRepository devices;
    @Mock private SessionRepository sessions;
    @Mock private RefreshTokenRepository refreshTokens;

    private DeviceService service;

    @BeforeEach
    void setUp() {
        AppProperties properties = new AppProperties();
        properties.getDesktop().setDeviceLimit(3);
        service = new DeviceService(devices, sessions, refreshTokens, properties,
                Clock.fixed(NOW, ZoneOffset.UTC));
        when(devices.save(any(Device.class))).thenAnswer(i -> i.getArgument(0));
    }

    private Device device(String installId) {
        return new Device(UUID.randomUUID(), ACCOUNT, installId, "A machine", "0.4.0", NOW);
    }

    @Test
    void registersANewInstallUnderTheLimit() {
        when(devices.findByAccountIdAndInstallId(ACCOUNT, "install-1")).thenReturn(Optional.empty());
        when(devices.countByAccountIdAndRevokedAtIsNull(ACCOUNT)).thenReturn(1L);

        Device registered = service.registerOrTouch(ACCOUNT, "install-1", "Laptop", "0.4.0");

        assertThat(registered.getInstallId()).isEqualTo("install-1");
        verify(devices).save(any(Device.class));
    }

    @Test
    @DisplayName("a new install at the cap is refused, and told which devices to remove")
    void refusesANewInstallAtTheLimit() {
        when(devices.findByAccountIdAndInstallId(ACCOUNT, "install-4")).thenReturn(Optional.empty());
        when(devices.countByAccountIdAndRevokedAtIsNull(ACCOUNT)).thenReturn(3L);
        when(devices.findByAccountIdOrderByLastSeenAtDesc(ACCOUNT))
                .thenReturn(List.of(device("install-1"), device("install-2"), device("install-3")));

        assertThatThrownBy(() -> service.registerOrTouch(ACCOUNT, "install-4", "New PC", "0.4.0"))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> {
                    ApiException api = (ApiException) e;
                    assertThat(api.getCode()).isEqualTo("device_limit_exceeded");
                    assertThat(api.getProperties()).containsEntry("limit", 3);
                    // An opaque refusal turns a self-service action into a
                    // support ticket, so the payload names the candidates.
                    assertThat((List<?>) api.getProperties().get("devices")).hasSize(3);
                });

        verify(devices, never()).save(any());
    }

    @Test
    @DisplayName("an install already known is let through even at the cap")
    void knownInstallIsNeverBlocked() {
        Device existing = device("install-1");
        when(devices.findByAccountIdAndInstallId(ACCOUNT, "install-1")).thenReturn(Optional.of(existing));
        when(devices.countByAccountIdAndRevokedAtIsNull(ACCOUNT)).thenReturn(99L);

        Device touched = service.registerOrTouch(ACCOUNT, "install-1", "Laptop", "0.5.0");

        // Otherwise lowering the limit would strand people who had done nothing
        // wrong, on a machine that was already signed in.
        assertThat(touched.getAppVersion()).isEqualTo("0.5.0");
        assertThat(touched.getLastSeenAt()).isEqualTo(NOW);
    }

    @Test
    @DisplayName("reinstating a revoked install has to fit under the cap again")
    void reinstatingARevokedInstallNeedsCapacity() {
        Device revoked = device("install-1");
        revoked.revoke(NOW);
        when(devices.findByAccountIdAndInstallId(ACCOUNT, "install-1")).thenReturn(Optional.of(revoked));
        when(devices.countByAccountIdAndRevokedAtIsNull(ACCOUNT)).thenReturn(3L);
        when(devices.findByAccountIdOrderByLastSeenAtDesc(ACCOUNT)).thenReturn(List.of());

        assertThatThrownBy(() -> service.registerOrTouch(ACCOUNT, "install-1", null, null))
                .isInstanceOf(ApiException.class);

        assertThat(revoked.isActive()).as("still revoked").isFalse();
    }

    @Test
    void revokingADeviceAlsoKillsItsCredentials() {
        Device existing = device("install-1");
        when(devices.findById(existing.getId())).thenReturn(Optional.of(existing));

        service.revoke(ACCOUNT, existing.getId());

        assertThat(existing.isActive()).isFalse();
        verify(sessions).revokeAllForDevice(existing.getId(), NOW);
        verify(refreshTokens).revokeAllForDevice(existing.getId(), NOW);
    }

    @Test
    @DisplayName("one account cannot revoke another's device")
    void cannotRevokeSomeoneElsesDevice() {
        Device other = new Device(UUID.randomUUID(), UUID.randomUUID(), "install-x", null, null, NOW);
        when(devices.findById(other.getId())).thenReturn(Optional.of(other));

        assertThatThrownBy(() -> service.revoke(ACCOUNT, other.getId()))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("device_not_found"));

        assertThat(other.isActive()).isTrue();
    }
}
