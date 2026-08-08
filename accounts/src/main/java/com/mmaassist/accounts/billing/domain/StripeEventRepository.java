package com.mmaassist.accounts.billing.domain;

import java.time.Instant;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface StripeEventRepository extends JpaRepository<StripeEvent, String> {

    /**
     * Claims a batch of unprocessed events.
     *
     * <p>{@code for update skip locked} is what makes this safe to run from
     * more than one poller — each grabs a disjoint batch instead of two workers
     * fighting over the same event and processing it twice. Native SQL because
     * JPQL has no way to express it.
     *
     * <p>Must be called inside a transaction; the row locks are released when
     * it commits.
     */
    @Query(value = """
            select * from billing.stripe_events
            where processed_at is null
            order by received_at
            limit :limit
            for update skip locked
            """, nativeQuery = true)
    List<StripeEvent> claimUnprocessed(@Param("limit") int limit);

    /** Feeds the alert on a webhook pipeline that has stopped keeping up. */
    long countByProcessedAtIsNullAndReceivedAtBefore(Instant cutoff);
}
