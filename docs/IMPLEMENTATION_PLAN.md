# Phased implementation plan

Audit snapshot: 2026-07-10. This plan orders the stable records in [BACKLOG.md](BACKLOG.md); it does not authorize deployment, external messages, secret rotation, production data changes, or Git-history rewriting. Each Task ID should normally be a separate Codex session, review, and deployable change.

## Delivery principles

- Fail closed before redesigning: stop unsafe side effects first.
- Add adversarial regression coverage before extracting architecture.
- Never combine security fixes, migrations, UI redesign, dependency upgrades, and new features in one change.
- Deploy schema compatibility before code that requires it; keep rollback reads until cutover is proven.
- Use product analytics only after a privacy-approved event dictionary; do not infer KPI baselines from fixture snapshots.
- Every phase can stop safely at a completed task boundary.

## Phase 0 — Immediate payment and credential containment

- **Objective:** Remove the direct paths to fraudulent access and cross-recipient/credential disclosure.
- **Included Task IDs, in order:** `SEC-001`, `SEC-002`, `SEC-003`, `SEC-004`, `SEC-005`, with workflow guard `DEVOPS-006` begun after rotation.
- **Explicitly excluded:** New payment model, background queue, price redesign, general refactor, Git-history rewrite, classroom work.
- **Prerequisites:** Explicit owner for receipt review and external credential rotation; safe test environment; preserve existing user WIP in `lessons/views.py`.
- **Expected files:** `whatsapp_agent/views.py`, `services.py`, tests, auth activation files, settings/env schema, legacy credential-bearing current source, security/operations docs.
- **Expected migrations:** None for `SEC-001`–`003`; `SEC-004` may use no persistent token model or one small activation-audit migration; review independently.
- **Automated tests:** Forged/replayed receipt never grants; signature negative matrix; destination never changes; no plaintext secret in DB/log/output; activation expiry/replay; full 40-test baseline plus new tests.
- **Manual QA:** Controlled unsigned/signed webhook, pending receipt/admin review, WhatsApp activation on a non-production recipient, old-secret revocation checks with redacted evidence.
- **Security validation:** Independent review of raw-body HMAC, fail-closed config, side-effect assertions, logs/database secret scan, destination binding.
- **Deployment considerations:** Ship each task separately. `SEC-001` first; communicate manual review. Configure app secret before `SEC-002`. Never test against real customers without authorization.
- **Risks:** Lost automated sales convenience, webhook outage from wrong secret, activation link host error, incomplete rotation inventory.
- **Rollback:** Disable webhook/auto account creation or keep receipts pending; never restore OCR grants, unsigned POST, recipient mutation, plaintext passwords, or exposed credentials.
- **Completion criteria:** All five task acceptance criteria pass; no receipt auto-grant; valid Meta requests only; recipient invariant; one-time activation; rotations recorded privately.

## Phase 0B — Separately authorized repository-history containment

- **Objective:** Remove private backups, media, and credential-bearing objects from authoritative Git history only after every exposed credential category is rotated.
- **Included Task IDs:** `SEC-014` only, executed as its own incident operation.
- **Explicitly excluded:** Runtime code fixes, production data changes, deployment, ordinary repository cleanup, and credential rotation itself.
- **Prerequisites:** `SEC-005` complete; explicit repository-owner authorization; protected mirror; path/category inventory; legal/privacy review; hosting-admin and contributor coordination.
- **Expected files:** Git objects, refs, tags, and hosted repository state; no application working-tree file should be edited as part of the rewrite.
- **Expected migrations:** None.
- **Automated tests:** Fresh-clone path/object scans, repository-size comparison, application compile/check/test baseline, and ref/tag integrity checks without printing sensitive content.
- **Manual QA:** Peer review of the redacted path inventory and rewrite plan; verify authoritative host refs/releases; confirm every contributor re-clones and abandons old history.
- **Security validation:** Prove rotations/revocations happened before rewriting; scan current and historical refs by path/category; retain incident evidence outside the cleaned repository with restricted access.
- **Deployment considerations:** This requires a coordinated force-update of repository history and invalidates existing clones; schedule and communicate it separately from an application release.
- **Risks:** Irrecoverable history loss, missed refs/forks/releases, stale clones reintroducing private objects, and false confidence if credentials were not revoked.
- **Rollback:** Use the protected mirror only to recover repository integrity; do not restore private objects to authoritative refs. Credential revocation is never rolled back.
- **Completion criteria:** Approved sensitive paths are absent from every authoritative ref; fresh-clone scans pass; application validation passes; rotations remain complete; contributors have re-cloned.

## Phase 1 — Security regression foundation and browser/data containment

- **Objective:** Prevent recurrence and close immediately exploitable application/browser/privacy gaps.
- **Included Task IDs:** `TEST-001`, `SEC-006`, `SEC-008`, `SEC-009`, `SEC-011`, then fail-closed part of `SEC-010`.
- **Explicitly excluded:** Complete classroom product, object-store migration, CSP overhaul, entitlement redesign, UX rebrand.
- **Prerequisites:** Phase 0 complete; production proxy/HTTPS facts; product decision to disable/unapprove classroom biometric enrollment by default.
- **Expected files:** WhatsApp/security tests; lesson template/chat rendering; service worker/PWA; settings; rate-limit/config modules; classroom/registration guards.
- **Expected migrations:** Possibly teacher approval/consent gate; usage ledger is deferred to `AI-002`; otherwise none.
- **Automated tests:** Critical adversarial suite, XSS payloads, PWA logout/cache, settings matrix/deploy checks, rate boundaries, unapproved teacher/consent denials.
- **Manual QA:** Browser devtools Cache Storage; login/session over local and proxy-like HTTPS; keyboard lesson chat; approved/unapproved classroom paths.
- **Security validation:** Same-origin XSS review, secure-cookie/proxy/HSTS staged assessment, upload/body caps, role escalation checks.
- **Deployment considerations:** Bump/delete old service-worker caches; introduce conservative limits with metrics; stage HSTS only after domain/proxy confirmation.
- **Risks:** Cached old worker remains active, false-positive throttling, production host misconfiguration, existing teacher workflow interruption.
- **Rollback:** Unregister worker, adjust limits, or disable classroom; retain escaping, strong settings validation, and role gate.
- **Completion criteria:** No untrusted HTML execution; no private cache; hardened environment gates; expensive/auth routes bounded; classroom cannot self-authorize collection.

## Phase 1B — Idempotent webhook intake and durable execution

- **Objective:** Make authenticated provider events resumable and move slow OCR/provider/notification work out of synchronous web requests before commercial automation grows.
- **Included Task IDs, in order:** `DATA-001`, then `PERF-001`.
- **Explicitly excluded:** New payment/entitlement models, automatic payment approval, microservices, worker autoscaling, general view refactoring.
- **Prerequisites:** `SEC-001` and `SEC-002` complete; event identity and retry semantics agreed; queue/worker operations owner; redacted observability baseline.
- **Expected files:** WhatsApp event/message models and migrations, webhook/service state machine, worker/queue settings and process declaration, tests, environment/operations documentation.
- **Expected migrations:** Provider-event uniqueness plus durable inbox/outbox/job status and attempt metadata; deduplicate safely before adding constraints.
- **Automated tests:** Concurrent duplicate delivery, crash/retry at every transition, status-before-message, poison media, retry exhaustion/dead letter, worker restart, no duplicate reply/provisioning, and bounded acknowledgement latency.
- **Manual QA:** Controlled signed webhook through enqueue/worker/retry/replay in a non-production environment; pause/resume worker; inspect redacted queue/failure visibility.
- **Security validation:** Signature/source checks occur before persistence; receipts remain pending; jobs cannot bypass authorization or destination binding; payload/log retention is minimized.
- **Deployment considerations:** Deploy compatible schema first, then inbox writer, then a paused consumer; canary the worker and retain queued work on rollback. This requires a separately supervised worker process.
- **Risks:** Duplicate side effects during cutover, lost ordering, poison jobs, queue outage, sensitive dead-letter payloads, and premature infrastructure complexity.
- **Rollback:** Pause consumers while preserving durable inbox/outbox records; return to fail-closed manual handling without deleting queued evidence or reintroducing synchronous automatic grants.
- **Completion criteria:** One provider event has one durable identity; webhook acknowledgement performs no slow OCR/external work; crashes resume without duplicate effects; operators can inspect/retry failures safely.

## Phase 2 — Commercial truth and auditable identity/entitlements

- **Objective:** Replace contradictory copy and unverified permanent access with a coherent commerce domain.
- **Included Task IDs:** `BUG-001`, `DATA-003`, `DATA-002`, then `FEAT-001` only after decomposition.
- **Explicitly excluded:** Automatic bank verification unless a real provider is approved; subscription billing complexity; referrals; broad profile redesign.
- **Prerequisites:** Phase 0, Phase 1, and Phase 1B; approved offer/refund/manual-payment policy; verified phone/identity approach; backup/restore plan for migrations.
- **Expected files:** Offer configuration/service, WhatsApp sales/payment integration services, profile identity models/forms, new order/payment/entitlement models/services/admin/views/templates/tests.
- **Expected migrations:** Phone normalization/verification/dedupe; order/payment/entitlement and legacy paid backfill.
- **Automated tests:** Idempotency concurrency, offer consistency, phone ambiguity/claim, payment state machine, duplicate transaction, expiry/refund/revoke, legacy backfill and access compatibility.
- **Manual QA:** Guest paywall→WhatsApp→pending→approved→activation→expiry/revoke; ambiguous legacy account; admin reconciliation.
- **Security validation:** Approval authorization, transaction uniqueness, no phone-only unverified binding, audit immutability, retention/access of payment evidence.
- **Deployment considerations:** Schema-first, backfill report, shadow-read new entitlement beside `is_paid`, reconcile, then cut over. Keep receipts manual until verified provider proof exists.
- **Risks:** Wrong legacy mapping, locking legitimate users, price rollout mismatch, long index operations.
- **Rollback:** Preserve new audit tables and compatibility reader; revert cutover without deleting orders/payments; never return to OCR proof.
- **Completion criteria:** One commercial source; all grants auditable/expiring; verified identity rules; duplicated events do not duplicate side effects; support can reconcile.

## Phase 3 — Reproducible secure delivery and recovery

- **Objective:** Make builds, upgrades, deployments, and data recovery repeatable before major feature work.
- **Included Task IDs:** `TEST-004`, `DEVOPS-002`, `DEVOPS-001`, `DEVOPS-004`, `DEVOPS-003`, `DEVOPS-005`.
- **Explicitly excluded:** Kubernetes/microservices, multi-region, Redis merely because it exists, aggressive autoscaling.
- **Prerequisites:** Critical behavior tests; production host/database/media facts and operations owner; supported runtime compatibility.
- **Expected files:** Requirements/lock/runtime/build/CI configs, sanitized env example, settings, health/logging instrumentation, backup/restore scripts/runbooks.
- **Expected migrations:** None expected for framework/runtime; observability may add no product schema. Migration drift must remain zero.
- **Automated tests:** Clean build, dependency check/security scan, full tests/compile/lint/type baseline, deploy check, SQLite and selected MySQL jobs, health/log redaction.
- **Manual QA:** Staging admin/auth/static/media/AI mocked smoke; canary; encrypted backup and isolated restore drill with measured RPO/RTO.
- **Security validation:** Patched supported Django/Python, secrets absent from artifact/logs, least-privilege backup access, strong production config.
- **Deployment considerations:** Upgrade Django 5.2 LTS and supported Python in isolated artifact; canary and rollback artifact; provision Tesseract languages/FFmpeg/DB driver explicitly.
- **Risks:** Framework behavior change, host runtime mismatch, false CI failures, backup job silently incomplete.
- **Rollback:** Previous known-good secure artifact plus database compatibility; never use backup drill against production; retain monitoring and backups.
- **Completion criteria:** Fresh clone builds and passes required gates; supported versions; clean deploy check; monitored backups and successful restore; actionable health/error telemetry.

## Phase 4 — Access, data lifecycle, and bounded architecture cleanup

- **Objective:** Establish safe domain boundaries after security and test foundations.
- **Included Task IDs:** `ARCH-001`, `TEST-002`, `SEC-007`, `MEDIA-001`, `SEC-012`, `ARCH-003`, then one bounded slice of `ARCH-002` at a time.
- **Explicitly excluded:** Whole-repo rewrite, generic repository pattern, new frontend framework, microservices.
- **Prerequisites:** Phases 0–3; approved access matrix, data retention/deletion policy, private storage topology.
- **Expected files:** Capability policy/service, all protected views, media storage/deletion, retention jobs/admin, prompt/model definitions, selected thin-view extraction, tests/docs.
- **Expected migrations:** Private file metadata/retention/audit; optional generation metadata; no speculative schema.
- **Automated tests:** Full access matrix/IDOR, file authorization/deletion/orphan reconciliation, retention/export/deletion, prompt snapshots/injection, characterization/query tests.
- **Manual QA:** Guest/unpaid/paid/expired/teacher/staff direct URLs; private receipt/photo access; account deletion; approved AI feature behavior.
- **Security validation:** Authorization in server endpoints, processor data minimization, deletion through backups policy, AI output/instruction boundaries.
- **Deployment considerations:** Shadow access decisions and storage copy before cutover; retention purge dry run and approval; extraction changes behavior-preserving.
- **Risks:** Accidental access denial/data deletion, stale media URLs, prompt behavior drift.
- **Rollback:** Keep old storage private/read-only and dual references until verification; pause purge; select prior approved prompt; never bypass centralized authorization.
- **Completion criteria:** One access policy; private media lifecycle; bounded retention; prompt/model versions; chosen view slice has isolated orchestration with unchanged contract.

## Phase 5 — Content integrity and learner activation quick wins

- **Objective:** Repair unsafe content operations and the highest-value learner/auth/quiz journey defects.
- **Included Task IDs:** `CONTENT-001`, `CONTENT-002`, `BUG-005`, `BUG-003`, `UX-005`, `BUG-004`, `UX-003`, `UX-001`, `UX-002`, decomposed `FEAT-003`, with `REPO-001` only in bounded cleanup changes after its prerequisites.
- **Explicitly excluded:** Full curriculum migration, adaptive AI, gamification, spaced repetition, design-system rewrite.
- **Prerequisites:** Offer truth, verified teacher/identity/privacy policy, CI/browser-test capability, analytics event plan for KPI measurement.
- **Expected files:** Fixtures/content command/tests, auth/recovery/consent and device middleware/views/templates, lesson quiz/template/JS, catalog/landing/guide/shared copy.
- **Expected migrations:** Consent/recovery/device audit as approved; no content data import; no curriculum schema yet.
- **Automated tests:** Fixture validity/private-data denylist, content validator cases, auth recovery and device-lock/revoke paths, quiz review/continuation, critical browser/mobile/accessibility checks, offer snapshot.
- **Manual QA:** New/returning/locked learner and approved teacher; mobile Kazakh copy; no-JS auth; device review/recovery; quiz errors/timeouts/review; landing comprehension with product review.
- **Security validation:** No production fixture dump, safe recovery/non-enumeration, protected device actions, consent version, no raw AI HTML, authorization preserved.
- **Deployment considerations:** Do not load regenerated fixtures into production as part of this phase; copy changes need support alignment; instrument before measuring.
- **Risks:** Content source confusion, recovery channel abuse, accidental device lockout, conversion claim inaccuracies, quiz behavior surprise.
- **Rollback:** Revert UI copy/flow while retaining correctness/security; keep sanitized fixtures and validator; disable recovery safely, not by sending passwords; retain an audited staff unlock path.
- **Completion criteria:** Valid safe content packages; actionable auth/recovery/device management; quiz mastery/next action; clear canonical landing/offer; role-aware activation/resume; KPI events defined.

## Phase 6 — Explicit curriculum, authoring, accessibility, and retention

- **Objective:** Build a versioned learning foundation and habit features after activation is measurable.
- **Included Task IDs:** `DATA-004`, `DATA-005`, `DATA-006`, `CONTENT-003`, `UX-004`, `TEST-003`, decomposed `FEAT-002`, `FEAT-004`, `FEAT-005`, then `FEAT-006`.
- **Explicitly excluded:** AI-adaptive path until mastery data quality is demonstrated; community/social features; certificates without criteria.
- **Prerequisites:** Analytics/privacy foundation, content-owner workflow, qualified educational reviewer, backup/restore, browser tests.
- **Expected files:** Curriculum/content version models/admin/import, explanation generation lifecycle, semantic components/CSS/JS, analytics events, review scheduler/models.
- **Expected migrations:** Curriculum mapping/order/version; explanation provenance; content publication; saved vocabulary/review schedule.
- **Automated tests:** Mapping/rollback, content version progress compatibility, atomic media, semantic browser/accessibility, spaced scheduling/timezone/idempotency.
- **Manual QA:** Content author preview/publish/rollback, learner on old/new version, 200% zoom/screen reader/mobile, due-review journey.
- **Security validation:** Content role permissions/audit, analytics minimization, no private offline cache, safe published AI output.
- **Deployment considerations:** Dry-run curriculum mapping, shadow progression, immutable old versions, gradual accessible component rollout.
- **Risks:** Progress corruption, content duplication, analytics bias, accessibility regressions during visual consolidation.
- **Rollback:** Compatibility map and old published version; pause new review scheduling; retain data/events; revert component per page.
- **Completion criteria:** Explicit track/order/publication/version; safe author workflow; measured mastery flow; accessibility critical journeys pass; spaced review shows justified adoption metrics.

## Phase 7 — Controlled AI voice and classroom strategy

- **Objective:** Restore grounded paid AI value with enforceable economics; only then decide classroom productization.
- **Included Task IDs:** `BUG-002`, `AI-001`, `AI-002`, decomposed `FEAT-007`; `FEAT-008` only after consent/legal/product gate.
- **Explicitly excluded:** Unlimited voice, autonomous content publishing, production biometric recognition without consent/accuracy controls.
- **Prerequisites:** Entitlements/offers, prompt registry, analytics/observability, privacy disclosures/retention, verified teachers, private storage, product/provider cost review.
- **Expected files:** Prompt/evaluation definitions, usage/lease models/services, token views, voice UI/preflight/summary, optional classroom consent/session/report models.
- **Expected migrations:** AI usage/session ledger; optional learning summary; classroom consent/session/attendance/correction audit only if approved.
- **Automated tests:** Lesson grounding, prompt injection/output validation, concurrent caps/crash leases/time budgets, transcript retention choice, classroom consent/owner/correction.
- **Manual QA:** Authorized provider sandbox for audio quality/disconnect/cost; learner usefulness review; teacher consent/no-recognition/session report pilot.
- **Security validation:** Data minimization, provider disclosure, server caps, child/guardian consent and opt-out, no silent biometric certainty.
- **Deployment considerations:** Small canary/budget cap; emergency kill switch; monitor cost/completed session; classroom remains disabled until completion gate.
- **Risks:** Variable cost, provider drift, pedagogical hallucination, microphone/browser failure, child privacy/recognition error.
- **Rollback:** Disable minting/new sessions via feature flag; retain entitlement/account and audit records; prior approved prompt; no data loss.
- **Completion criteria:** Grounded voice meets reliability/quality/cost/privacy gates; usage enforced server-side; classroom either passes consent/report pilot criteria or remains explicitly experimental/off.

## Phase 8 — Growth scaling and optional offline engagement

- **Objective:** Scale only observed bottlenecks and add safe habit mechanisms after core retention evidence.
- **Included Task IDs:** `PERF-002`, `SEC-013`, decomposed `FEAT-009` and `FEAT-010`.
- **Explicitly excluded:** Multi-region, microservices, complex event streaming, premature sharding.
- **Prerequisites:** Observability/load evidence, the Phase 1B idempotent-job foundation, privacy-safe analytics, content versioning, and stable accessible components.
- **Expected files:** Bounded selectors/indexes, CSP/asset packaging, localization catalogs/components, service worker/daily plan/reminder system, and existing worker configuration only where reminders require it.
- **Expected migrations:** Measured indexes plus approved locale/reminder preferences and schedule; avoid speculative denormalization.
- **Automated tests:** Query and payload budgets under representative load, CSP asset policy, locale fallbacks, offline cache isolation/logout, and notification consent/idempotency.
- **Manual QA:** 100/1k/10k representative load stages, Kazakh/Russian UI, offline shared-device/privacy, and opt-in reminder experience.
- **Security validation:** No private cached content, CSP enforced, localization does not weaken escaping, and reminders are consented, authenticated, and rate-limited.
- **Deployment considerations:** Stage measured indexes, use CSP report-only first, evict old cache versions, and roll out locale/offline/reminders gradually with existing worker monitoring.
- **Risks:** Stale offline content, notification fatigue, CDN/model breakage, localization regressions, and indexes locking tables.
- **Rollback:** Revert the query path while retaining safe indexes; unregister the service worker and clear caches; disable locale/reminder rollout while retaining consent/preferences.
- **Completion criteria:** Measured latency/reliability targets at required scale; no unbounded collections; enforced browser policy; offline/reminders improve measured retention without privacy or fatigue regression.

## Scale gates

| Scale | Required before claiming readiness |
| --- | --- |
| About 100 active users | Phases 0–3; backups/restore, critical security, supported runtime, basic monitoring; SQLite only for low-write/local use with explicit limits |
| About 1,000 active users | Central access, private durable media, idempotent worker pipeline, bounded queries, AI usage caps, MySQL/PostgreSQL production tuning and load test |
| About 10,000 active users | Proven queue/backpressure, object storage/CDN for public assets, database query/index/capacity evidence, structured observability/on-call, retention jobs, disaster-recovery drill |

Do not infer readiness from passing unit tests alone.

Recommended next task: `SEC-001` — Stop OCR-only automatic entitlement grants
