package com.mmaassist.accounts.platform.config;

import com.mmaassist.accounts.platform.security.AuthPrincipalArgumentResolver;
import java.time.Clock;
import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final AppProperties properties;
    private final AuthPrincipalArgumentResolver principalResolver;

    public WebConfig(AppProperties properties, AuthPrincipalArgumentResolver principalResolver) {
        this.properties = properties;
        this.principalResolver = principalResolver;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        // Exactly one origin, and credentials allowed. A wildcard is not merely
        // sloppy here: the browser refuses to send cookies to a wildcard origin,
        // so it would break sign-in as well as widen the surface.
        //
        // Only /v1/** is mapped. The Stripe webhook is server-to-server and has
        // no business answering a preflight.
        registry.addMapping("/v1/**")
                .allowedOrigins(properties.getSiteOrigin())
                .allowedMethods("GET", "POST", "DELETE", "OPTIONS")
                .allowedHeaders("Content-Type", "Authorization")
                .allowCredentials(true)
                .maxAge(3600);
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(principalResolver);
    }

    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }

    /**
     * Shared HTTP client for outbound identity-provider calls. Timeouts are
     * short and explicit: a hung IdP must fail the login, not hold a request
     * thread until the container gives up.
     */
    @Bean
    public RestClient.Builder restClientBuilder() {
        var factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000);
        factory.setReadTimeout(10000);
        return RestClient.builder().requestFactory(factory);
    }
}
