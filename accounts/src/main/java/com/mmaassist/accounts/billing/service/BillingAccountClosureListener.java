package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.Subscription;
import com.mmaassist.accounts.billing.domain.SubscriptionRepository;
import com.mmaassist.accounts.platform.spi.AccountClosureListener;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Cancels anything still billable when an account is deleted.
 *
 * <p>Immediately, not at period end: someone who has asked to be deleted should
 * not see another charge, and there is no account left to serve the remaining
 * days to. If Stripe cannot be reached, this throws and the deletion rolls
 * back — an account that quietly disappears while its card keeps being charged
 * is the worst outcome available here, and it is worth failing the request to
 * avoid.
 */
@Component
public class BillingAccountClosureListener implements AccountClosureListener {

    private static final Logger log = LoggerFactory.getLogger(BillingAccountClosureListener.class);

    private final SubscriptionRepository subscriptions;
    private final StripeGateway gateway;

    public BillingAccountClosureListener(SubscriptionRepository subscriptions, StripeGateway gateway) {
        this.subscriptions = subscriptions;
        this.gateway = gateway;
    }

    @Override
    public void onAccountClosing(UUID accountId) {
        for (Subscription subscription : subscriptions.findByAccountId(accountId)) {
            if (subscription.isTerminal()) {
                continue;
            }
            log.info("cancelling subscription {} for closing account {}",
                    subscription.getStripeSubscriptionId(), accountId);
            gateway.cancelSubscription(subscription.getStripeSubscriptionId(), true);
        }
    }
}
