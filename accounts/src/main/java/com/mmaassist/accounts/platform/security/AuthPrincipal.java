package com.mmaassist.accounts.platform.security;

import java.util.UUID;

/**
 * The authenticated caller.
 *
 * @param accountId the account behind the credential
 * @param sessionId the session row the credential resolved to, so logout can
 *                  revoke exactly this one
 * @param kind      {@code web} for cookie sessions, {@code desktop} for bearer
 *                  tokens issued to an installed app
 * @param deviceId  the desktop install, when the credential is bound to one
 */
public record AuthPrincipal(UUID accountId, UUID sessionId, String kind, UUID deviceId) {

    public boolean isDesktop() {
        return "desktop".equals(kind);
    }
}
