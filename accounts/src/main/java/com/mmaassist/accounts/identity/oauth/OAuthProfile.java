package com.mmaassist.accounts.identity.oauth;

/**
 * What an identity provider told us about the person who just signed in.
 *
 * @param provider       {@code google} or {@code github}
 * @param providerUserId the provider's immutable subject id
 * @param email          the address, lowercased by the broker
 * @param emailVerified  whether the provider says it verified that address.
 *                       Never assume true — see {@code AccountService}
 * @param displayName    may be null; GitHub users often have no name set
 * @param avatarUrl      may be null
 */
public record OAuthProfile(
        String provider,
        String providerUserId,
        String email,
        boolean emailVerified,
        String displayName,
        String avatarUrl) {
}
