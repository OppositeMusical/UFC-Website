package com.mmaassist.accounts.billing.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Drains the stored-webhook queue.
 *
 * <p>Not transactional itself: each event gets its own transaction so one bad
 * payload cannot roll back the batch around it.
 */
@Component
public class WebhookPoller {

    private static final Logger log = LoggerFactory.getLogger(WebhookPoller.class);

    private final WebhookEventProcessor processor;

    public WebhookPoller(WebhookEventProcessor processor) {
        this.processor = processor;
    }

    @Scheduled(fixedDelayString = "${app.webhook-processing.poll-interval}")
    public void drain() {
        for (String eventId : processor.claimBatch()) {
            try {
                processor.process(eventId);
            } catch (Exception e) {
                processor.recordFailure(eventId, e);
            }
        }
    }

    /** Visible for tests and for the reconciliation job's catch-up pass. */
    public void drainOnce() {
        drain();
    }
}
