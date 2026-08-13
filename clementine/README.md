# 🍊 Clementine

**A verified, women-only dating-safety network — product & engineering plan.**

Clementine is a planned social app in the category proven by Tea Dating Advice: an anonymous, identity-verified community where women share dating experiences, look up a prospective date before meeting him, and receive alerts when new safety-relevant information surfaces. The plan's thesis is that the category's value is real and its two demonstrated failure modes — legal exposure and catastrophic data breach — are engineering and policy problems that can be designed out from day one.

## The plan

Read in order, or jump to the area you own:

| Doc | Contents |
|---|---|
| [01 — Product Specification](01-product-spec.md) | Vision, personas, competitive landscape (Tea, Garbo, Lulu, AWDTSG groups), full feature catalog tiered MVP → v2, monetization (Clementine Plus), success metrics, non-goals |
| [02 — System Architecture](02-architecture.md) | TypeScript modular monolith on AWS Fargate with isolated verification/moderation/records services, React Native (Expo) client, data tier, vendor choices, viral-burst scaling story, cost model |
| [03 — Data Model](03-data-model.md) | Full ERD, 18 entities with per-column PII classification, subject identity resolution, retention & deletion matrix, hot-path indexing |
| [04 — API Design](04-api-design.md) | Three API planes (member / subject portal / admin), endpoint catalog with per-endpoint authorization, webhook contracts, rate limiting, error model |
| [05 — Trust & Safety](05-trust-and-safety.md) | Abuse-vector inventory with mitigations, staged moderation pipeline with pre-publication PII blocking, content policy, subject notice/dispute/appeal flow, legal posture (§230, GDPR/CCPA), T&S operations |
| [06 — Security & Privacy Engineering](06-security-and-privacy.md) | Threat model, Tea-breach post-mortem → structural controls, verify-then-delete media pipeline, E2E-encrypted DMs with message franking, incident response, SOC 2 roadmap |
| [07 — UX Flows & Screens](07-ux-flows.md) | Screen map, onboarding/verification, guardrail-heavy post composer, search, alerts, subject portal, anti-brigading UI, accessibility, visual identity |
| [08 — Roadmap & Execution](08-roadmap.md) | Phase 0 validation → 16-week MVP with explicit cutline → growth & monetization → messaging, 5.5-FTE team plan, budget, KPIs, launch strategy, top-10 risk register |

## What the app does

- **Verified women-only membership** — selfie/ID verification at signup, after which members are anonymous personas inside the app. Verification media is purged within 24 hours of a decision (never held more than 7 days), so a breach cannot leak what Tea's did.
- **Local feeds & flags** — city-based feeds of first-person dating experiences labeled with red/green flags, screened before publication.
- **Look him up** — search a first name + photo + coarse location to find prior reports; reverse-image search to catch catfishing; metered public-records checks (sex-offender registry, criminal records).
- **Alerts** — get notified when someone you searched or follow gets a new report.
- **Community** — advice threads at launch; E2E-encrypted DMs and group chats later, stored as ciphertext the server cannot decrypt.
- **Safety hub** — hotlines and guides, never paywalled.

## What makes this plan different

The plan treats the people *described* in posts as stakeholders, not just the members posting:

1. **Pre-publication screening** hard-blocks doxxing content (addresses, phone numbers, workplaces, socials) before anything goes live.
2. **A public Subject Portal** gives any man named in a post a notice, dispute, and takedown path — with identity verification before anything is disclosed to him, so the portal can't be used to probe the database.
3. **Delete-by-default data handling** — verification media, DMs, and search history all have short, machine-enforced retention; the design assumes the app will one day be breached and subpoenaed, and minimizes what either event can expose.
4. **Growth is throttled by safety capacity** — launch is city-by-city behind waitlists, and the roadmap's phase gates halt expansion when moderation SLAs break.

## Status

📋 Planning phase. No code yet — these documents are the blueprint for Phase 0 (validation) and Phase 1 (MVP build).
