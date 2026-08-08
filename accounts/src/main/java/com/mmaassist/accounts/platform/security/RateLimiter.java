package com.mmaassist.accounts.platform.security;

import com.mmaassist.accounts.platform.error.ApiException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * An in-memory token bucket, keyed by whatever the caller decides identifies an
 * abuser (usually IP, sometimes account id).
 *
 * <p>In-memory is correct while {@code numReplicas} is 1, and the limits here
 * are about blunting brute force and runaway retries rather than enforcing a
 * quota. A second replica makes the effective limit N times the configured one,
 * which is a reason to move this to Redis at that point, not a reason to reach
 * for Redis now.
 */
@Component
public class RateLimiter {

    private static final Duration IDLE_EVICTION = Duration.ofMinutes(10);

    private final Clock clock;
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    public RateLimiter(Clock clock) {
        this.clock = clock;
    }

    /** @return false when the caller has run out of budget. */
    public boolean tryAcquire(String key, int capacity, Duration window) {
        Bucket bucket = buckets.computeIfAbsent(key, k -> new Bucket(capacity, clock.instant()));
        return bucket.tryAcquire(clock.instant(), capacity, window);
    }

    /** Same, but throws the 429 so call sites stay one line. */
    public void require(String key, int capacity, Duration window) {
        if (!tryAcquire(key, capacity, window)) {
            throw ApiException.tooManyRequests("Too many requests. Try again shortly.");
        }
    }

    @Scheduled(fixedDelay = 5 * 60 * 1000L)
    void evictIdleBuckets() {
        Instant cutoff = clock.instant().minus(IDLE_EVICTION);
        buckets.entrySet().removeIf(entry -> entry.getValue().idleSince(cutoff));
    }

    /** Visible for tests. */
    int trackedKeys() {
        return buckets.size();
    }

    private static final class Bucket {
        private double tokens;
        private Instant lastRefill;

        Bucket(int capacity, Instant now) {
            this.tokens = capacity;
            this.lastRefill = now;
        }

        synchronized boolean tryAcquire(Instant now, int capacity, Duration window) {
            double perSecond = capacity / (double) window.toSeconds();
            double elapsed = Duration.between(lastRefill, now).toMillis() / 1000.0;
            if (elapsed > 0) {
                tokens = Math.min(capacity, tokens + elapsed * perSecond);
                lastRefill = now;
            }
            if (tokens >= 1.0) {
                tokens -= 1.0;
                return true;
            }
            return false;
        }

        synchronized boolean idleSince(Instant cutoff) {
            return lastRefill.isBefore(cutoff);
        }
    }
}
