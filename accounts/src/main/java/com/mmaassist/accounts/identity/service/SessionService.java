package com.mmaassist.accounts.identity.service;

import com.mmaassist.accounts.identity.domain.Account;
import com.mmaassist.accounts.identity.domain.AccountRepository;
import com.mmaassist.accounts.identity.domain.AuthSession;
import com.mmaassist.accounts.identity.domain.SessionRepository;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.security.AuthPrincipal;
import com.mmaassist.accounts.platform.security.SessionAuthenticator;
import com.mmaassist.accounts.platform.security.Tokens;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Issues, resolves and revokes bearer credentials. */
@Service
public class SessionService implements SessionAuthenticator {

    /**
     * How stale {@code last_seen_at} is allowed to get before a read turns into
     * a write. Updating it on every request would put a row update in front of
     * every single API call to record something nothing depends on to the
     * second.
     */
    private static final Duration LAST_SEEN_RESOLUTION = Duration.ofMinutes(5);

    /** A freshly issued credential: the raw token exists only in this record. */
    public record Issued(String token, AuthSession session) {
    }

    private final SessionRepository sessions;
    private final AccountRepository accounts;
    private final AppProperties properties;
    private final Clock clock;

    public SessionService(SessionRepository sessions, AccountRepository accounts,
                          AppProperties properties, Clock clock) {
        this.sessions = sessions;
        this.accounts = accounts;
        this.properties = properties;
        this.clock = clock;
    }

    @Transactional
    public Issued createWebSession(UUID accountId, String userAgent, String ip) {
        return create(accountId, AuthSession.KIND_WEB, null, userAgent, ip,
                properties.getSession().getTtl());
    }

    @Transactional
    public Issued createDesktopSession(UUID accountId, UUID deviceId) {
        return create(accountId, AuthSession.KIND_DESKTOP, deviceId, null, null,
                properties.getDesktop().getAccessTokenTtl());
    }

    private Issued create(UUID accountId, String kind, UUID deviceId, String userAgent, String ip,
                          Duration ttl) {
        Instant now = clock.instant();
        String token = Tokens.generate();
        AuthSession session = new AuthSession(UUID.randomUUID(), accountId, kind,
                Tokens.hash(token), deviceId, truncate(userAgent, 500), truncate(ip, 64),
                now, now.plus(ttl));
        return new Issued(token, sessions.save(session));
    }

    @Override
    @Transactional
    public Optional<AuthPrincipal> authenticate(String token) {
        Instant now = clock.instant();
        return sessions.findByTokenHash(Tokens.hash(token))
                .filter(session -> session.isUsable(now))
                .filter(session -> accountIsUsable(session.getAccountId()))
                .map(session -> {
                    if (session.getLastSeenAt().plus(LAST_SEEN_RESOLUTION).isBefore(now)) {
                        session.touch(now);
                    }
                    return new AuthPrincipal(session.getAccountId(), session.getId(),
                            session.getKind(), session.getDeviceId());
                });
    }

    /**
     * A suspended account's live sessions stop working immediately rather than
     * at their next expiry. Suspension exists for chargebacks and abuse, where
     * "in up to 30 days" is not a useful answer.
     */
    private boolean accountIsUsable(UUID accountId) {
        return accounts.findById(accountId).map(Account::isActive).orElse(false);
    }

    @Transactional
    public void revoke(UUID sessionId) {
        sessions.findById(sessionId).ifPresent(session -> session.revoke(clock.instant()));
    }

    @Transactional
    public void revokeAllForAccount(UUID accountId) {
        sessions.revokeAllForAccount(accountId, clock.instant());
    }

    /**
     * Expired sessions are deleted, not merely left revoked: they are worthless
     * after expiry and this table sees a row per login forever otherwise. Kept
     * for 30 days past expiry so "where was I logged in?" support questions are
     * still answerable.
     */
    @Scheduled(cron = "0 30 4 * * *")
    @Transactional
    public void purgeExpiredSessions() {
        sessions.deleteExpiredBefore(clock.instant().minus(Duration.ofDays(30)));
    }

    private static String truncate(String value, int max) {
        if (value == null) {
            return null;
        }
        return value.length() <= max ? value : value.substring(0, max);
    }
}
