package com.mmaassist.accounts.billing.web;

import com.mmaassist.accounts.billing.service.WebhookIngestService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The only unauthenticated write endpoint in the service.
 *
 * <p>Two details are load-bearing and easy to undo by accident:
 *
 * <ol>
 *   <li>The body is taken as a {@code String}. Binding it to a DTO would have
 *       Jackson parse and re-serialise it first, and the HMAC is computed over
 *       the exact bytes Stripe sent — key order and whitespace included. The
 *       signature would then fail for every legitimate request.</li>
 *   <li>It returns as soon as the event is stored. Stripe gives a handler ten
 *       seconds and retries for three days; doing the work here turns a slow
 *       query into duplicate deliveries.</li>
 * </ol>
 */
@RestController
@RequestMapping("/webhooks")
public class StripeWebhookController {

    private final WebhookIngestService ingestService;

    public StripeWebhookController(WebhookIngestService ingestService) {
        this.ingestService = ingestService;
    }

    @PostMapping(value = "/stripe", consumes = MediaType.ALL_VALUE)
    public ResponseEntity<String> receive(@RequestBody String payload,
                                          @RequestHeader(value = "Stripe-Signature",
                                                  required = false) String signature) {
        WebhookIngestService.Result result = ingestService.ingest(payload, signature);
        // A duplicate is a success from Stripe's point of view: the event has
        // been received. Anything other than 2xx here schedules a retry.
        return ResponseEntity.ok(result == WebhookIngestService.Result.DUPLICATE
                ? "duplicate" : "accepted");
    }
}
