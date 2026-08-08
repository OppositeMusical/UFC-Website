package com.mmaassist.accounts.licensing.web;

import com.mmaassist.accounts.licensing.service.LicenceService;
import com.mmaassist.accounts.platform.error.ApiException;
import com.mmaassist.accounts.platform.security.AuthPrincipal;
import java.time.Instant;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/v1/licence")
public class LicenceController {

    private final LicenceService licenceService;

    public LicenceController(LicenceService licenceService) {
        this.licenceService = licenceService;
    }

    /**
     * Issues a licence for the calling install.
     *
     * <p>The device comes from the credential, not the request body. A body
     * field would let any signed-in caller mint a licence naming somebody
     * else's device.
     */
    @PostMapping
    public LicenceResponse issue(AuthPrincipal principal) {
        return respond(principal);
    }

    /**
     * Alias for {@link #issue}. Kept separate because it is what the app calls
     * on its weekly refresh, and having the two named differently makes the
     * access logs legible.
     */
    @PostMapping("/refresh")
    public LicenceResponse refresh(AuthPrincipal principal) {
        return respond(principal);
    }

    private LicenceResponse respond(AuthPrincipal principal) {
        if (!principal.isDesktop() || principal.deviceId() == null) {
            throw ApiException.badRequest("desktop_only",
                    "Licences are issued to a desktop install, using its own access token.");
        }
        LicenceService.IssuedLicence issued =
                licenceService.issue(principal.accountId(), principal.deviceId());
        return new LicenceResponse(issued.token(), issued.tier(), issued.expiresAt(),
                issued.graceDays());
    }

    public record LicenceResponse(String licenceToken, String tier, Instant expiresAt,
                                  int graceDays) {
    }
}
