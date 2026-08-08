package com.mmaassist.accounts.identity.oauth;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * GitHub hands back a list of addresses, and only one of them is safe to key an
 * account on. Picking the wrong one is account takeover.
 */
class GithubBrokerEmailTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    @DisplayName("picks the address that is both primary and verified")
    void picksPrimaryVerified() throws Exception {
        String json = """
                [
                  {"email":"old@example.test","primary":false,"verified":true},
                  {"email":"Real@Example.test","primary":true,"verified":true},
                  {"email":"other@example.test","primary":false,"verified":false}
                ]""";

        assertThat(GithubBroker.primaryVerifiedEmail(objectMapper.readTree(json)))
                .isEqualTo("real@example.test");
    }

    @Test
    @DisplayName("an unverified primary is refused - this is the takeover vector")
    void refusesUnverifiedPrimary() throws Exception {
        String json = """
                [{"email":"victim@example.test","primary":true,"verified":false}]""";

        assertThat(GithubBroker.primaryVerifiedEmail(objectMapper.readTree(json))).isNull();
    }

    @Test
    @DisplayName("a verified but non-primary address is not promoted")
    void doesNotFallBackToNonPrimary() throws Exception {
        String json = """
                [{"email":"secondary@example.test","primary":false,"verified":true}]""";

        assertThat(GithubBroker.primaryVerifiedEmail(objectMapper.readTree(json))).isNull();
    }

    @Test
    void handlesEmptyAndMalformedResponses() throws Exception {
        assertThat(GithubBroker.primaryVerifiedEmail(objectMapper.readTree("[]"))).isNull();
        assertThat(GithubBroker.primaryVerifiedEmail(objectMapper.readTree("{}"))).isNull();
        assertThat(GithubBroker.primaryVerifiedEmail(null)).isNull();
    }
}
