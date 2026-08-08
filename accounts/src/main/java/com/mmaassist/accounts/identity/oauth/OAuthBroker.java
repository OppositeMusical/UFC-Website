package com.mmaassist.accounts.identity.oauth;

/**
 * One identity provider.
 *
 * <p>These are written by hand rather than via {@code spring-security-oauth2-client}
 * because the two providers disagree in ways the abstraction hides: GitHub is
 * plain OAuth2 with no {@code email} claim and a separate endpoint for verified
 * addresses, while Google is OIDC. The verified-email rule is the security
 * boundary of the whole account system, and it belongs somewhere obvious.
 */
public interface OAuthBroker {

    /** The value stored in {@code identities.provider}. */
    String provider();

    /** Whether client credentials are configured for this provider. */
    boolean isConfigured();

    /** The URL to send the browser to. */
    String authorizationUri(String state, String redirectUri);

    /** Exchanges the authorization code and fetches the profile. */
    OAuthProfile exchangeCode(String code, String redirectUri);
}
