package com.mmaassist.accounts.platform.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Everything under the {@code app.*} prefix in application.yml. */
@ConfigurationProperties(prefix = "app")
public class AppProperties {

    /** The single origin allowed to make credentialed browser requests. */
    private String siteOrigin = "http://localhost:5173";

    /** Public base URL of this service; used to build OAuth redirect URIs. */
    private String apiBaseUrl = "http://localhost:8080";

    private Session session = new Session();
    private Desktop desktop = new Desktop();
    private OAuth oauth = new OAuth();
    private Stripe stripe = new Stripe();
    private Licence licence = new Licence();
    private WebhookProcessing webhookProcessing = new WebhookProcessing();
    private Reconciliation reconciliation = new Reconciliation();

    public static class Session {
        private String cookieName = "mma_session";

        /**
         * Empty means "host-only cookie", which is correct for local development.
         * In production this is {@code .mmaassist.com} so the cookie is sent to
         * the API subdomain.
         */
        private String cookieDomain = "";

        private boolean cookieSecure = false;
        private Duration ttl = Duration.ofDays(30);

        public String getCookieName() { return cookieName; }
        public void setCookieName(String v) { this.cookieName = v; }
        public String getCookieDomain() { return cookieDomain; }
        public void setCookieDomain(String v) { this.cookieDomain = v; }
        public boolean isCookieSecure() { return cookieSecure; }
        public void setCookieSecure(boolean v) { this.cookieSecure = v; }
        public Duration getTtl() { return ttl; }
        public void setTtl(Duration v) { this.ttl = v; }
    }

    public static class Desktop {
        private Duration accessTokenTtl = Duration.ofMinutes(15);
        private Duration refreshTokenTtl = Duration.ofDays(90);
        private Duration authorizationCodeTtl = Duration.ofSeconds(60);

        /** A courtesy cap, not a security control. See the spec, section 1.1. */
        private int deviceLimit = 5;

        public Duration getAccessTokenTtl() { return accessTokenTtl; }
        public void setAccessTokenTtl(Duration v) { this.accessTokenTtl = v; }
        public Duration getRefreshTokenTtl() { return refreshTokenTtl; }
        public void setRefreshTokenTtl(Duration v) { this.refreshTokenTtl = v; }
        public Duration getAuthorizationCodeTtl() { return authorizationCodeTtl; }
        public void setAuthorizationCodeTtl(Duration v) { this.authorizationCodeTtl = v; }
        public int getDeviceLimit() { return deviceLimit; }
        public void setDeviceLimit(int v) { this.deviceLimit = v; }
    }

    public static class OAuth {
        private Provider google = new Provider();
        private Provider github = new Provider();

        public Provider getGoogle() { return google; }
        public void setGoogle(Provider v) { this.google = v; }
        public Provider getGithub() { return github; }
        public void setGithub(Provider v) { this.github = v; }

        public static class Provider {
            private String clientId = "";
            private String clientSecret = "";
            private String authorizationUri = "";
            private String tokenUri = "";
            private String userInfoUri = "";
            private String userEmailsUri = "";

            public boolean isConfigured() {
                return !clientId.isBlank() && !clientSecret.isBlank();
            }

            public String getClientId() { return clientId; }
            public void setClientId(String v) { this.clientId = v; }
            public String getClientSecret() { return clientSecret; }
            public void setClientSecret(String v) { this.clientSecret = v; }
            public String getAuthorizationUri() { return authorizationUri; }
            public void setAuthorizationUri(String v) { this.authorizationUri = v; }
            public String getTokenUri() { return tokenUri; }
            public void setTokenUri(String v) { this.tokenUri = v; }
            public String getUserInfoUri() { return userInfoUri; }
            public void setUserInfoUri(String v) { this.userInfoUri = v; }
            public String getUserEmailsUri() { return userEmailsUri; }
            public void setUserEmailsUri(String v) { this.userEmailsUri = v; }
        }
    }

    public static class Stripe {
        private String secretKey = "";
        private String webhookSecret = "";
        private Duration webhookTolerance = Duration.ofMinutes(5);
        private Duration dunningGrace = Duration.ofDays(7);

        public boolean isConfigured() { return !secretKey.isBlank(); }

        public String getSecretKey() { return secretKey; }
        public void setSecretKey(String v) { this.secretKey = v; }
        public String getWebhookSecret() { return webhookSecret; }
        public void setWebhookSecret(String v) { this.webhookSecret = v; }
        public Duration getWebhookTolerance() { return webhookTolerance; }
        public void setWebhookTolerance(Duration v) { this.webhookTolerance = v; }
        public Duration getDunningGrace() { return dunningGrace; }
        public void setDunningGrace(Duration v) { this.dunningGrace = v; }
    }

    public static class Licence {
        private String signingKey = "";
        private String kid = "dev";
        private String issuer = "http://localhost:8080";
        private String audience = "mma-assist-desktop";
        private Duration subscriptionTtl = Duration.ofDays(14);
        private Duration lifetimeTtl = Duration.ofDays(180);
        private int graceDays = 7;

        public String getSigningKey() { return signingKey; }
        public void setSigningKey(String v) { this.signingKey = v; }
        public String getKid() { return kid; }
        public void setKid(String v) { this.kid = v; }
        public String getIssuer() { return issuer; }
        public void setIssuer(String v) { this.issuer = v; }
        public String getAudience() { return audience; }
        public void setAudience(String v) { this.audience = v; }
        public Duration getSubscriptionTtl() { return subscriptionTtl; }
        public void setSubscriptionTtl(Duration v) { this.subscriptionTtl = v; }
        public Duration getLifetimeTtl() { return lifetimeTtl; }
        public void setLifetimeTtl(Duration v) { this.lifetimeTtl = v; }
        public int getGraceDays() { return graceDays; }
        public void setGraceDays(int v) { this.graceDays = v; }
    }

    public static class WebhookProcessing {
        private Duration pollInterval = Duration.ofSeconds(5);
        private int batchSize = 20;
        private int maxAttempts = 5;

        public Duration getPollInterval() { return pollInterval; }
        public void setPollInterval(Duration v) { this.pollInterval = v; }
        public int getBatchSize() { return batchSize; }
        public void setBatchSize(int v) { this.batchSize = v; }
        public int getMaxAttempts() { return maxAttempts; }
        public void setMaxAttempts(int v) { this.maxAttempts = v; }
    }

    public static class Reconciliation {
        private String cron = "0 15 3 * * *";
        private Duration lookback = Duration.ofHours(48);

        public String getCron() { return cron; }
        public void setCron(String v) { this.cron = v; }
        public Duration getLookback() { return lookback; }
        public void setLookback(Duration v) { this.lookback = v; }
    }

    public String getSiteOrigin() { return siteOrigin; }
    public void setSiteOrigin(String v) { this.siteOrigin = v; }
    public String getApiBaseUrl() { return apiBaseUrl; }
    public void setApiBaseUrl(String v) { this.apiBaseUrl = v; }
    public Session getSession() { return session; }
    public void setSession(Session v) { this.session = v; }
    public Desktop getDesktop() { return desktop; }
    public void setDesktop(Desktop v) { this.desktop = v; }
    public OAuth getOauth() { return oauth; }
    public void setOauth(OAuth v) { this.oauth = v; }
    public Stripe getStripe() { return stripe; }
    public void setStripe(Stripe v) { this.stripe = v; }
    public Licence getLicence() { return licence; }
    public void setLicence(Licence v) { this.licence = v; }
    public WebhookProcessing getWebhookProcessing() { return webhookProcessing; }
    public void setWebhookProcessing(WebhookProcessing v) { this.webhookProcessing = v; }
    public Reconciliation getReconciliation() { return reconciliation; }
    public void setReconciliation(Reconciliation v) { this.reconciliation = v; }
}
