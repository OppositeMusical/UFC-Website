package com.mmaassist.accounts.platform.audit;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class AuditService {

    private static final Logger log = LoggerFactory.getLogger(AuditService.class);

    public static final String ACTOR_SYSTEM = "system";
    public static final String ACTOR_STRIPE = "stripe";

    private final AuditRepository repository;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public AuditService(AuditRepository repository, ObjectMapper objectMapper, Clock clock) {
        this.repository = repository;
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    public void record(UUID accountId, String actor, String action, Map<String, ?> detail) {
        String serialised = null;
        if (detail != null && !detail.isEmpty()) {
            try {
                serialised = objectMapper.writeValueAsString(detail);
            } catch (Exception e) {
                // An audit record with a missing detail blob still beats losing
                // the record, and beats failing the operation being audited.
                log.warn("could not serialise audit detail for action {}", action, e);
            }
        }
        repository.save(new AuditEntry(accountId, actor, action, serialised, clock.instant()));
    }
}
