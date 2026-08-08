package com.mmaassist.accounts.platform.spi;

import java.util.UUID;

/**
 * Notified when an account is being closed, before its personal fields are
 * stripped.
 *
 * <p>Exists so that {@code identity} does not have to know that {@code billing}
 * has a subscription to cancel. The dependency points at this interface from
 * both sides, which is what keeps the module graph acyclic — see
 * {@code ModuleBoundaryTest}.
 *
 * <p>Implementations run inside the deletion transaction: throwing aborts the
 * deletion, which is the correct outcome if, say, Stripe cannot be reached to
 * cancel an active subscription. Silently deleting the account while continuing
 * to bill the card would be very much worse.
 */
public interface AccountClosureListener {

    void onAccountClosing(UUID accountId);
}
