package com.mmaassist.accounts.billing.web;

import com.mmaassist.accounts.billing.domain.Payment;
import com.mmaassist.accounts.billing.domain.PaymentRepository;
import com.mmaassist.accounts.billing.domain.Subscription;
import com.mmaassist.accounts.billing.domain.SubscriptionRepository;
import com.mmaassist.accounts.platform.security.AuthPrincipal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** What the account page needs to render a billing section. */
@RestController
@RequestMapping("/v1")
public class BillingController {

    private final SubscriptionRepository subscriptions;
    private final PaymentRepository payments;

    public BillingController(SubscriptionRepository subscriptions, PaymentRepository payments) {
        this.subscriptions = subscriptions;
        this.payments = payments;
    }

    @GetMapping("/billing/summary")
    public Map<String, Object> summary(AuthPrincipal principal) {
        List<SubscriptionView> active = subscriptions.findByAccountId(principal.accountId()).stream()
                .filter(s -> !s.isTerminal())
                .map(SubscriptionView::from)
                .toList();
        return Map.of("subscriptions", active);
    }

    @GetMapping("/payments")
    public Map<String, Object> payments(AuthPrincipal principal) {
        List<PaymentView> history = payments
                .findByAccountIdOrderByOccurredAtDesc(principal.accountId()).stream()
                .map(PaymentView::from)
                .toList();
        return Map.of("payments", history);
    }

    public record SubscriptionView(String planId, String status, Instant currentPeriodEnd,
                                   boolean cancelAtPeriodEnd) {

        static SubscriptionView from(Subscription s) {
            return new SubscriptionView(s.getPlanId(), s.getStatus(), s.getCurrentPeriodEnd(),
                    s.isCancelAtPeriodEnd());
        }
    }

    /** Note the absence of anything resembling a card number. */
    public record PaymentView(String kind, int amountMinor, String currency, String status,
                              String cardBrand, String cardLast4, String receiptUrl,
                              Instant occurredAt) {

        static PaymentView from(Payment p) {
            return new PaymentView(p.getKind(), p.getAmountMinor(), p.getCurrency(), p.getStatus(),
                    p.getCardBrand(), p.getCardLast4(), p.getReceiptUrl(), p.getOccurredAt());
        }
    }
}
