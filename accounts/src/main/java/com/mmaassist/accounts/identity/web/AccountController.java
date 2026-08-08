package com.mmaassist.accounts.identity.web;

import com.mmaassist.accounts.identity.domain.Account;
import com.mmaassist.accounts.identity.domain.Device;
import com.mmaassist.accounts.identity.service.AccountService;
import com.mmaassist.accounts.identity.service.DeviceService;
import com.mmaassist.accounts.platform.security.AuthPrincipal;
import com.mmaassist.accounts.platform.spi.EntitlementLookup;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/v1/me")
public class AccountController {

    private final AccountService accountService;
    private final DeviceService deviceService;
    private final EntitlementLookup entitlements;

    public AccountController(AccountService accountService, DeviceService deviceService,
                             EntitlementLookup entitlements) {
        this.accountService = accountService;
        this.deviceService = deviceService;
        this.entitlements = entitlements;
    }

    @GetMapping
    public MeResponse me(AuthPrincipal principal) {
        Account account = accountService.require(principal.accountId());
        EntitlementLookup.Snapshot entitlement = entitlements.forAccount(principal.accountId());

        return new MeResponse(
                new AccountView(account.getId().toString(), account.getEmail(),
                        account.getDisplayName(), account.getAvatarUrl(), account.getCreatedAt()),
                new EntitlementView(entitlement.tier(), entitlement.source(),
                        entitlement.features(), entitlement.validUntil()),
                accountService.linkedProviders(principal.accountId()),
                deviceService.list(principal.accountId()).stream().map(DeviceView::from).toList());
    }

    /**
     * Closes the account.
     *
     * <p>Not reversible, and not complete either: payment records survive
     * because tax and anti-fraud rules require them. The response says so
     * explicitly so the UI can too — a privacy page claiming "everything is
     * deleted" would be a false statement, not a simplification.
     */
    @DeleteMapping
    public ResponseEntity<Map<String, Object>> close(AuthPrincipal principal) {
        accountService.closeAccount(principal.accountId());
        return ResponseEntity.ok(Map.of(
                "status", "closed",
                "retained", "Payment records are kept for tax and anti-fraud purposes. "
                        + "Everything else has been deleted."));
    }

    /** GDPR data export: everything this service holds about the caller. */
    @GetMapping("/export")
    public Map<String, Object> export(AuthPrincipal principal) {
        Account account = accountService.require(principal.accountId());
        EntitlementLookup.Snapshot entitlement = entitlements.forAccount(principal.accountId());

        return Map.of(
                "account", Map.of(
                        "id", account.getId().toString(),
                        "email", account.getEmail(),
                        "displayName", String.valueOf(account.getDisplayName()),
                        "createdAt", account.getCreatedAt().toString()),
                "linkedProviders", accountService.linkedProviders(principal.accountId()),
                "entitlement", Map.of(
                        "tier", entitlement.tier(),
                        "source", String.valueOf(entitlement.source())),
                "devices", deviceService.list(principal.accountId()).stream()
                        .map(DeviceView::from).toList(),
                "note", "Payment history is available from the billing portal linked on your "
                        + "account page.");
    }

    public record MeResponse(AccountView account, EntitlementView entitlement,
                             List<String> linkedProviders, List<DeviceView> devices) {
    }

    public record AccountView(String id, String email, String displayName, String avatarUrl,
                              Instant createdAt) {
    }

    public record EntitlementView(String tier, String source, Map<String, Object> features,
                                  Instant validUntil) {
    }

    public record DeviceView(String id, String name, String appVersion, Instant lastSeenAt) {

        static DeviceView from(Device device) {
            return new DeviceView(device.getId().toString(), device.getName(),
                    device.getAppVersion(), device.getLastSeenAt());
        }
    }
}
