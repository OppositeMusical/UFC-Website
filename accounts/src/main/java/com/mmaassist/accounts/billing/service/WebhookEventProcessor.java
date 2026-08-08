package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.StripeEvent;
import com.mmaassist.accounts.billing.domain.StripeEventRepository;
import com.mmaassist.accounts.platform.config.AppProperties;
import java.time.Clock;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * The transactional half of webhook processing.
 *
 * <p>Split from {@link WebhookPoller} because the three steps need three
 * different transactions: claiming a batch, processing one event (which must
 * roll back cleanly on its own), and recording a failure (which must commit
 * even though the processing transaction rolled back). Spring's proxies only
 * apply across bean boundaries, so a single class calling its own
 * {@code @Transactional} methods would silently run all three in one.
 */
@Service
public class WebhookEventProcessor {

    private static final Logger log = LoggerFactory.getLogger(WebhookEventProcessor.class);

    private final StripeEventRepository events;
    private final StripeEventHandler handler;
    private final AppProperties properties;
    private final Clock clock;

    public WebhookEventProcessor(StripeEventRepository events, StripeEventHandler handler,
                                 AppProperties properties, Clock clock) {
        this.events = events;
        this.handler = handler;
        this.properties = properties;
        this.clock = clock;
    }

    @Transactional
    public List<String> claimBatch() {
        return events.claimUnprocessed(properties.getWebhookProcessing().getBatchSize()).stream()
                .map(StripeEvent::getId)
                .toList();
    }

    /**
     * Processes one event.
     *
     * <p>{@code rollbackFor = Exception.class} matters: the handler throws
     * checked exceptions when a payload will not parse, and Spring's default
     * only rolls back on unchecked ones — so without it a half-applied event
     * would commit.
     */
    @Transactional(rollbackFor = Exception.class)
    public void process(String eventId) throws Exception {
        StripeEvent event = events.findById(eventId).orElse(null);
        if (event == null || event.getProcessedAt() != null) {
            return;
        }
        handler.handle(event);
        event.markProcessed(clock.instant());
    }

    /** Runs in its own transaction, because the one that failed is rolling back. */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordFailure(String eventId, Exception failure) {
        events.findById(eventId).ifPresent(event -> {
            event.markFailed(failure.toString());
            if (event.isExhausted(properties.getWebhookProcessing().getMaxAttempts())) {
                // One unparseable payload must not starve every event behind
                // it. Park it and shout.
                event.giveUp(clock.instant());
                log.error("giving up on stripe event {} after {} attempts - needs a human",
                        eventId, event.getAttempts(), failure);
            } else {
                log.warn("stripe event {} failed (attempt {})", eventId, event.getAttempts(), failure);
            }
        });
    }
}
