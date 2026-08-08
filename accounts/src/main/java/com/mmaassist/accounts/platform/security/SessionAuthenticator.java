package com.mmaassist.accounts.platform.security;

import java.util.Optional;

/**
 * Resolves an opaque credential to a principal.
 *
 * <p>Declared in {@code platform} and implemented in {@code identity} so the
 * authentication filter does not have to reach into the identity module — the
 * dependency points inward, and {@code ModuleBoundaryTest} enforces it.
 */
public interface SessionAuthenticator {

    Optional<AuthPrincipal> authenticate(String token);
}
