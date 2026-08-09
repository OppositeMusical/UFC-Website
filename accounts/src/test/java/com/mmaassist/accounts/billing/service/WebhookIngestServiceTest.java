package com.mmaassist.accounts.billing.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.mmaassist.accounts.billing.domain.StripeEvent;
import com.mmaassist.accounts.billing.domain.StripeEventRepository;
import com.mmaassist.accounts.platform.config.AppProperties;
import com.mmaassist.accounts.platform.error.ApiException;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;

/**
 * The webhook is the only unauthenticated write endpoint in the service, and
 * the only thing standing between the internet and a free Pro licence is this
 * signature check. It is tested against real HMACs rather than a stubbed
 * verifier.
 */
@ExtendWith(MockitoExtension.class)
class WebhookIngestServiceTest {

    private static final String SECRET = "whsec_test_secret_value";
    private static final Instant NOW = Instant.parse("2026-08-08T12:00:00Z");

    private static final String PAYLOAD = """
            {"id":"evt_test_1","object":"event","api_version":"2024-06-20",\
            "created":1786305600,"type":"checkout.session.completed","livemode":false,\
            "data":{"object":{"id":"cs_test_1","object":"checkout.session","mode":"payment"}}}""";

    @Mock
    private StripeEventRepository events;

    private WebhookIngestService service;

    @BeforeEach
    void setUp() {
        AppProperties properties = new AppProperties();
        properties.getStripe().setWebhookSecret(SECRET);
        properties.getStripe().setWebhookTolerance(Duration.ofMinutes(5));

        service = new WebhookIngestService(events, properties,
                Clock.fixed(NOW, ZoneOffset.UTC));
    }

    @Test
    @DisplayName("a correctly signed event is stored")
    void validSignatureIsAccepted() {
        when(events.existsById("evt_test_1")).thenReturn(false);

        WebhookIngestService.Result result =
                service.ingest(PAYLOAD, signatureHeader(PAYLOAD, SECRET, NOW.getEpochSecond()));

        assertThat(result).isEqualTo(WebhookIngestService.Result.ACCEPTED);
        verify(events).save(any(StripeEvent.class));
    }

    @Test
    @DisplayName("a forged signature is refused, and nothing is stored")
    void forgedSignatureIsRejected() {
        String forged = signatureHeader(PAYLOAD, "whsec_not_the_real_secret", NOW.getEpochSecond());

        assertThatThrownBy(() -> service.ingest(PAYLOAD, forged))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("invalid_signature"));

        verify(events, never()).save(any());
    }

    @Test
    @DisplayName("a payload edited after signing is refused")
    void tamperedPayloadIsRejected() {
        String header = signatureHeader(PAYLOAD, SECRET, NOW.getEpochSecond());
        String tampered = PAYLOAD.replace("cs_test_1", "cs_test_2");

        assertThatThrownBy(() -> service.ingest(tampered, header))
                .isInstanceOf(ApiException.class);

        verify(events, never()).save(any());
    }

    @Test
    @DisplayName("a signature older than the tolerance is refused, so captures cannot be replayed")
    void staleSignatureIsRejected() {
        long tenMinutesAgo = NOW.minus(Duration.ofMinutes(10)).getEpochSecond();
        String header = signatureHeader(PAYLOAD, SECRET, tenMinutesAgo);

        assertThatThrownBy(() -> service.ingest(PAYLOAD, header))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("invalid_signature"));
    }

    @Test
    @DisplayName("a missing signature header is refused")
    void missingSignatureIsRejected() {
        assertThatThrownBy(() -> service.ingest(PAYLOAD, null))
                .isInstanceOf(ApiException.class);
    }

    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings = {
            "garbage", "[1,2]", "\"just a string\"", "42", "",
    })
    @DisplayName("a body that is not a JSON object is a 400, never a 500")
    void unparseableBodyIsABadRequest(String body) {
        // Regression test. Stripe's constructEvent deserialises before it
        // verifies, so these throw an unchecked Gson error from inside the SDK.
        // Uncaught, that was a 500 on an endpoint the entire internet can
        // reach - anyone could manufacture server errors with curl.
        String header = signatureHeader(body, SECRET, NOW.getEpochSecond());

        assertThatThrownBy(() -> service.ingest(body, header))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> {
                    ApiException api = (ApiException) e;
                    assertThat(api.getStatus().is4xxClientError())
                            .as("must be a client error, not a server error")
                            .isTrue();
                    assertThat(api.getCode()).isIn("invalid_payload", "invalid_signature");
                });

        verify(events, never()).save(any());
    }

    @Test
    @DisplayName("a signed payload carrying no event id is refused rather than hitting the primary key")
    void payloadWithoutEventIdIsRejected() {
        String body = "{\"object\":\"event\",\"type\":\"checkout.session.completed\"}";

        assertThatThrownBy(() ->
                service.ingest(body, signatureHeader(body, SECRET, NOW.getEpochSecond())))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode()).isEqualTo("invalid_payload"));

        verify(events, never()).save(any());
    }

    @Test
    @DisplayName("re-delivery of an event we already hold changes nothing")
    void duplicateEventIsIgnored() {
        when(events.existsById("evt_test_1")).thenReturn(true);

        WebhookIngestService.Result result =
                service.ingest(PAYLOAD, signatureHeader(PAYLOAD, SECRET, NOW.getEpochSecond()));

        assertThat(result).isEqualTo(WebhookIngestService.Result.DUPLICATE);
        verify(events, never()).save(any());
    }

    @Test
    @DisplayName("two simultaneous deliveries: the primary key settles it, and the loser is not an error")
    void concurrentDuplicateLosesTheInsertRace() {
        when(events.existsById("evt_test_1")).thenReturn(false);
        when(events.save(any(StripeEvent.class)))
                .thenThrow(new DataIntegrityViolationException("duplicate key"));

        WebhookIngestService.Result result =
                service.ingest(PAYLOAD, signatureHeader(PAYLOAD, SECRET, NOW.getEpochSecond()));

        assertThat(result).isEqualTo(WebhookIngestService.Result.DUPLICATE);
    }

    @Test
    @DisplayName("with no secret configured, every webhook is refused rather than trusted")
    void unconfiguredSecretRefusesEverything() {
        AppProperties blank = new AppProperties();
        blank.getStripe().setWebhookSecret("");
        WebhookIngestService unconfigured =
                new WebhookIngestService(events, blank, Clock.fixed(NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> unconfigured.ingest(PAYLOAD, "t=1,v1=whatever"))
                .isInstanceOf(ApiException.class)
                .satisfies(e -> assertThat(((ApiException) e).getCode())
                        .isEqualTo("webhook_not_configured"));

        verify(events, never()).existsById(anyString());
    }

    /** Builds the {@code Stripe-Signature} header exactly as Stripe does. */
    private static String signatureHeader(String payload, String secret, long timestamp) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] digest = mac.doFinal(
                    (timestamp + "." + payload).getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(String.format("%02x", b));
            }
            return "t=" + timestamp + ",v1=" + hex;
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}
