package com.mmaassist.accounts.identity.oauth;

import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.security.Tokens;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Authorization codes this service issues to the desktop app, once the identity
 * provider round trip has already succeeded.
 *
 * <p>These live for sixty seconds and can be redeemed exactly once. Both
 * properties matter: the code travels over plain HTTP to 127.0.0.1 (which is
 * the standard, and safe, loopback arrangement — it never leaves the machine),
 * so its window of usefulness should be as small as the exchange needs.
 */
@Component
public class DesktopAuthorizationCodes {

    public record Issued(UUID accountId, String codeChallenge, String redirectUri, Instant createdAt) {
    }

    private final Map<String, Issued> codes = new ConcurrentHashMap<>();
    private final Clock clock;
    private final AppProperties properties;

    public DesktopAuthorizationCodes(Clock clock, AppProperties properties) {
        this.clock = clock;
        this.properties = properties;
    }

    public String issue(UUID accountId, String codeChallenge, String redirectUri) {
        String code = Tokens.generate();
        codes.put(code, new Issued(accountId, codeChallenge, redirectUri, clock.instant()));
        return code;
    }

    public Optional<Issued> consume(String code) {
        if (code == null || code.isBlank()) {
            return Optional.empty();
        }
        Issued issued = codes.remove(code);
        if (issued == null) {
            return Optional.empty();
        }
        Instant expiry = issued.createdAt().plus(properties.getDesktop().getAuthorizationCodeTtl());
        return expiry.isAfter(clock.instant()) ? Optional.of(issued) : Optional.empty();
    }

    @Scheduled(fixedDelay = 60_000L)
    void evictExpired() {
        Instant cutoff = clock.instant().minus(properties.getDesktop().getAuthorizationCodeTtl());
        codes.entrySet().removeIf(entry -> entry.getValue().createdAt().isBefore(cutoff));
    }
}
