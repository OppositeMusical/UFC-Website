package com.mmaassist.accounts.platform.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.mmaassist.accounts.platform.error.ApiException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class RateLimiterTest {

    private static final Duration WINDOW = Duration.ofMinutes(1);

    @Test
    void allowsUpToCapacityThenRefuses() {
        MutableClock clock = new MutableClock(Instant.parse("2026-08-08T12:00:00Z"));
        RateLimiter limiter = new RateLimiter(clock);

        for (int i = 0; i < 5; i++) {
            assertThat(limiter.tryAcquire("ip:1.2.3.4", 5, WINDOW)).as("attempt %d", i).isTrue();
        }
        assertThat(limiter.tryAcquire("ip:1.2.3.4", 5, WINDOW)).isFalse();
    }

    @Test
    @DisplayName("budget refills as time passes")
    void refillsOverTime() {
        MutableClock clock = new MutableClock(Instant.parse("2026-08-08T12:00:00Z"));
        RateLimiter limiter = new RateLimiter(clock);

        for (int i = 0; i < 5; i++) {
            limiter.tryAcquire("ip:1.2.3.4", 5, WINDOW);
        }
        assertThat(limiter.tryAcquire("ip:1.2.3.4", 5, WINDOW)).isFalse();

        // One fifth of the window returns one token.
        clock.advance(Duration.ofSeconds(13));
        assertThat(limiter.tryAcquire("ip:1.2.3.4", 5, WINDOW)).isTrue();
        assertThat(limiter.tryAcquire("ip:1.2.3.4", 5, WINDOW)).isFalse();
    }

    @Test
    @DisplayName("one caller's budget is not another's")
    void keysAreIndependent() {
        MutableClock clock = new MutableClock(Instant.parse("2026-08-08T12:00:00Z"));
        RateLimiter limiter = new RateLimiter(clock);

        for (int i = 0; i < 5; i++) {
            limiter.tryAcquire("ip:1.1.1.1", 5, WINDOW);
        }

        assertThat(limiter.tryAcquire("ip:1.1.1.1", 5, WINDOW)).isFalse();
        assertThat(limiter.tryAcquire("ip:2.2.2.2", 5, WINDOW)).isTrue();
    }

    @Test
    void requireThrowsWhenExhausted() {
        MutableClock clock = new MutableClock(Instant.parse("2026-08-08T12:00:00Z"));
        RateLimiter limiter = new RateLimiter(clock);

        limiter.require("checkout:acct", 1, WINDOW);

        assertThatThrownBy(() -> limiter.require("checkout:acct", 1, WINDOW))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("rate_limited"));
    }

    @Test
    @DisplayName("idle buckets are evicted, so the map does not grow with every IP ever seen")
    void evictsIdleBuckets() {
        MutableClock clock = new MutableClock(Instant.parse("2026-08-08T12:00:00Z"));
        RateLimiter limiter = new RateLimiter(clock);

        limiter.tryAcquire("ip:1.1.1.1", 5, WINDOW);
        assertThat(limiter.trackedKeys()).isEqualTo(1);

        clock.advance(Duration.ofMinutes(11));
        limiter.evictIdleBuckets();

        assertThat(limiter.trackedKeys()).isZero();
    }

    /** A clock the test drives, so nothing here sleeps. */
    private static final class MutableClock extends Clock {

        private Instant now;

        private MutableClock(Instant now) {
            this.now = now;
        }

        void advance(Duration by) {
            now = now.plus(by);
        }

        @Override
        public ZoneId getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return now;
        }
    }
}
