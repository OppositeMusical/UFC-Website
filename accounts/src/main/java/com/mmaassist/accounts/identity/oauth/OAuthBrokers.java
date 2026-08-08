package com.mmaassist.accounts.identity.oauth;

import com.mmaassist.accounts.platform.error.ApiException;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

/** Looks a broker up by the provider name that appeared in the URL. */
@Component
public class OAuthBrokers {

    private final Map<String, OAuthBroker> byName;

    public OAuthBrokers(List<OAuthBroker> brokers) {
        this.byName = brokers.stream()
                .collect(Collectors.toMap(OAuthBroker::provider, Function.identity()));
    }

    public OAuthBroker require(String provider) {
        OAuthBroker broker = byName.get(provider == null ? "" : provider.toLowerCase(java.util.Locale.ROOT));
        if (broker == null) {
            throw ApiException.notFound("unknown_provider", "Unknown sign-in provider.");
        }
        if (!broker.isConfigured()) {
            // A missing client secret is a deployment mistake. Saying so beats
            // a redirect to an OAuth error page that blames the user.
            throw ApiException.unavailable("provider_not_configured",
                    "Sign-in with " + broker.provider() + " is not available right now.");
        }
        return broker;
    }

    public List<String> configuredProviders() {
        return byName.values().stream()
                .filter(OAuthBroker::isConfigured)
                .map(OAuthBroker::provider)
                .sorted()
                .toList();
    }
}
