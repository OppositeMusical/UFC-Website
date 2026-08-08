package com.mmaassist.accounts.billing.service;

import com.mmaassist.accounts.billing.domain.StripeEvent;
import com.mmaassist.accounts.billing.domain.StripeEventRepository;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import com.stripe.exception.SignatureVerificationException;
import com.stripe.model.Event;
import com.stripe.net.Webhook;
import java.time.Clock;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * The front half of the webhook pipeline: verify, store, acknowledge.
 *
 * <p>Nothing is <em>acted on</em> here. Stripe times out at ten seconds and
 * retries for three days; doing the work inline means a slow database turns
 * into duplicate deliveries, and a bug turns into a retry storm. Storing the
 * raw body and returning 200 makes processing a separate, replayable problem.
 */
@Service
public class WebhookIngestService {

    private static final Logger log = LoggerFactory.getLogger(WebhookIngestService.class);

    public enum Result {
        /** Stored for processing. */
        ACCEPTED,
        /** Stripe has sent this event id before. */
        DUPLICATE
    }

    private final StripeEventRepository events;
    private final AppProperties properties;
    private final Clock clock;

    public WebhookIngestService(StripeEventRepository events, AppProperties properties, Clock clock) {
        this.events = events;
        this.properties = properties;
        this.clock = clock;
    }

    @Transactional
    public Result ingest(String rawPayload, String signatureHeader) {
        String secret = properties.getStripe().getWebhookSecret();
        if (secret == null || secret.isBlank()) {
            // Without a secret every payload is unverifiable, and accepting
            // unverified ones would let anyone grant themselves a licence with
            // a single curl. Refusing is the only safe posture.
            log.error("stripe webhook secret is not configured; refusing webhook");
            throw ApiException.unavailable("webhook_not_configured", "Webhooks are not configured.");
        }

        if (signatureHeader == null || signatureHeader.isBlank()) {
            // Checked here rather than left to the SDK, which dereferences the
            // header and throws NullPointerException - a 500 for what is
            // plainly a bad request, and noise in the error budget every time
            // a scanner probes this path.
            log.warn("rejected webhook with no signature header");
            throw ApiException.badRequest("invalid_signature", "Missing Stripe-Signature header.");
        }

        Event event;
        try {
            event = Webhook.constructEvent(rawPayload, signatureHeader, secret,
                    properties.getStripe().getWebhookTolerance().toSeconds(), clock);
        } catch (SignatureVerificationException e) {
            // Never log the payload of an unverified request: it is attacker
            // controlled and would land unfiltered in the log.
            log.warn("rejected webhook with bad signature");
            throw ApiException.badRequest("invalid_signature", "Signature verification failed.");
        }

        if (events.existsById(event.getId())) {
            return Result.DUPLICATE;
        }

        try {
            events.save(new StripeEvent(event.getId(), event.getType(), event.getApiVersion(),
                    rawPayload, clock.instant()));
        } catch (DataIntegrityViolationException e) {
            // Two concurrent deliveries of the same event. The primary key
            // settled it; the loser has nothing to do.
            return Result.DUPLICATE;
        }

        return Result.ACCEPTED;
    }
}
