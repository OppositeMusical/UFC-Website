package com.mmaassist.accounts.identity.oauth;

import com.mmaassist.accounts.platform.security.Tokens;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * In-flight OAuth round trips, keyed by the {@code state} parameter.
 *
 * <p>Holding this in memory has one visible consequence: a deploy that lands
 * while somebody is mid-login loses their state, and they see "that sign-in
 * link expired, try again" rather than being signed in. That is a ten-second
 * annoyance a handful of times a year, against a Redis dependency and its
 * failure modes forever. It does, however, mean this service cannot run more
 * than one replica without moving this store — the same constraint the rate
 * limiter has.
 */
@Component
public class PendingAuthorizationStore {

    /** Long enough to finish an IdP consent screen, short enough not to accumulate. */
    private static final Duration TTL = Duration.ofMinutes(10);

    public enum Flow {
        /** Browser sign-in; ends in a session cookie. */
        WEB,
        /** Desktop sign-in; ends in an authorization code sent to a loopback URI. */
        DESKTOP
    }

    /**
     * @param returnPath          WEB: the site path to land on afterwards
     * @param codeChallenge       DESKTOP: the app's PKCE challenge
     * @param loopbackRedirectUri DESKTOP: the app's 127.0.0.1 callback
     */
    public record Pending(
            String provider,
            Flow flow,
            String returnPath,
            String codeChallenge,
            String loopbackRedirectUri,
            Instant createdAt) {
    }

    private final Map<String, Pending> byState = new ConcurrentHashMap<>();
    private final Clock clock;

    public PendingAuthorizationStore(Clock clock) {
        this.clock = clock;
    }

    /** @return the opaque {@code state} to hand to the identity provider. */
    public String start(String provider, Flow flow, String returnPath,
                        String codeChallenge, String loopbackRedirectUri) {
        String state = Tokens.generate();
        byState.put(state, new Pending(provider, flow, returnPath, codeChallenge,
                loopbackRedirectUri, clock.instant()));
        return state;
    }

    /** Single use: a replayed state finds nothing. */
    public Optional<Pending> consume(String state) {
        if (state == null || state.isBlank()) {
            return Optional.empty();
        }
        Pending pending = byState.remove(state);
        if (pending == null) {
            return Optional.empty();
        }
        if (pending.createdAt().plus(TTL).isBefore(clock.instant())) {
            return Optional.empty();
        }
        return Optional.of(pending);
    }

    @Scheduled(fixedDelay = 60_000L)
    void evictExpired() {
        Instant cutoff = clock.instant().minus(TTL);
        byState.entrySet().removeIf(entry -> entry.getValue().createdAt().isBefore(cutoff));
    }

    /** Visible for tests. */
    int size() {
        return byState.size();
    }
}
