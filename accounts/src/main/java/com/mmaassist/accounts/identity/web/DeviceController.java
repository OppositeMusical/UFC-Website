package com.mmaassist.accounts.identity.web;

import com.mmaassist.accounts.identity.service.DeviceService;
import com.mmaassist.accounts.platform.security.AuthPrincipal;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/v1/devices")
public class DeviceController {

    private final DeviceService deviceService;

    public DeviceController(DeviceService deviceService) {
        this.deviceService = deviceService;
    }

    /**
     * Signs a device out. Reachable from the browser (the account page) and
     * from the desktop app itself, so an install can remove itself when the
     * user signs out locally.
     */
    @DeleteMapping("/{deviceId}")
    public ResponseEntity<Void> revoke(@PathVariable UUID deviceId, AuthPrincipal principal) {
        deviceService.revoke(principal.accountId(), deviceId);
        return ResponseEntity.noContent().build();
    }
}
