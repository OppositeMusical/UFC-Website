package com.mmaassist.accounts.licensing.web;

import com.mmaassist.accounts.licensing.LicenceTokenSigner;
import java.util.List;
import java.util.Map;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The public verification key.
 *
 * <p>The desktop app ships with the current key baked in, and falls back to
 * this document when it meets a {@code kid} it does not recognise — which is
 * what lets the signing key be rotated without shipping a new build.
 *
 * <p>Cached for an hour: long enough to be cheap, short enough that a rotation
 * propagates the same day.
 */
@RestController
public class JwksController {

    private final LicenceTokenSigner signer;

    public JwksController(LicenceTokenSigner signer) {
        this.signer = signer;
    }

    @GetMapping("/.well-known/jwks.json")
    public ResponseEntity<Map<String, Object>> jwks() {
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(java.time.Duration.ofHours(1)).cachePublic())
                .body(Map.of("keys", List.of(signer.publicJwk())));
    }
}
