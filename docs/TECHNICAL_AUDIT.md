# Technical Audit

## Audit metadata and evidence rules

This technical audit is based on the repository state inspected on 2026-07-10. Application code was not changed. lessons/views.py was already modified in the working tree before the documentation task.

Evidence labels:

- Confirmed: directly supported by code, migrations, repository state, diagnostics, or executed tests.
- Inferred: likely consequence of confirmed implementation, not reproduced under production load.
- Needs verification: depends on production infrastructure or external service state not visible in the repository.
- Needs product-owner confirmation: a repository-visible inconsistency requires a product-policy decision; it is not the same as Needs verification.

Confidence is High, Medium, or Low and reflects evidence quality, not issue severity.

Severity describes consequence using the canonical backlog taxonomy: P0 Critical, P1 High, P2 Medium, and P3 Low. Priority separately describes execution order. Effort uses XS/S/M/L/XL.

Security-specific findings and remediation details are maintained in docs/SECURITY_AUDIT.md. This document focuses on architecture, data design, code boundaries, performance, content operations, deployment, testing, and repository hygiene.

## Current architecture

### Architectural style

OqyAI is a server-rendered Django modular monolith in deployment, but the main lessons app is internally a mixed-responsibility monolith.

- Django serves pages, JSON endpoints, authentication, admin, database access, static/PWA entry points, and protected media.
- Browser Realtime voice, translator, and classroom sessions connect directly to OpenAI after Django mints an ephemeral credential.
- Server-side explanation generation calls OpenAI text APIs, opens an OpenAI Realtime WebSocket for TTS, converts audio, and writes local media during the HTTP request.
- The WhatsApp app receives a webhook and synchronously performs persistence, intent detection, OpenAI generation, provider sends, OCR/PDF processing, Telegram alerts, and Django-user provisioning.
- The declared production process is WSGI Gunicorn. Channels and ASGI exist, but active product Realtime traffic does not traverse Django websockets.

### Responsibility matrix

| Component | Current responsibilities | Appropriate boundary | Boundary concern |
| --- | --- | --- | --- |
| english_course/settings.py | Environment loading, security, hosts, database choice, static/media, logging, OpenAI and messaging settings | Project configuration | One module mixes development and production defaults; import-time OpenAI requirement affects unrelated commands |
| english_course/urls.py | Admin, WhatsApp include, lessons include, DEBUG media | Project routing | Small and understandable |
| english_course/realtime.py | Realtime session configuration, safety identifier, client-secret minting | Shared OpenAI infrastructure | Returns broad upstream payload and has no application quota/usage record |
| english_course/utils/realtime_tts.py | Realtime WebSocket audio collection and MP3 conversion | Shared media/AI infrastructure | No overall deadline or output bound; conversion depends on an external binary |
| english_course/services/telegram.py | Telegram transport | Shared notification infrastructure | Appropriate small module; downstream callers send more personal data than necessary |
| lessons/models.py | Curriculum, quizzes, explanations, profiles, entitlements, devices, marketing leads, classroom, photos and embeddings | Several domain modules | Unrelated domains share one model file and weak implicit invariants |
| lessons/views.py | Registration, pages, access policy, AI prompts/calls, media, quiz, PWA, profile, translator | Several view and service modules | 1,457-line change hotspot with duplicated policy and synchronous work |
| lessons/views_classroom.py | Teacher authorization, classroom CRUD, protected photos, embeddings, Realtime prompt/token | Classroom domain | Better separated than lessons/views.py, but role approval, privacy, prompt construction, and persistence remain coupled |
| lessons/forms.py | Public registration | Account onboarding | Public role selection grants teacher authority |
| lessons/forms_classroom.py | Classroom CRUD and image upload forms | Classroom input validation | Count limit exists, but storage/pixel/total-size policy is absent |
| lessons/middleware.py | Domain redirect and device lock | Request infrastructure | Device enforcement writes and queries business data on every authenticated request |
| whatsapp_agent/models.py | Lead, message, event, and receipt records | WhatsApp domain | Missing idempotency and entitlement/payment relationships |
| whatsapp_agent/services.py | All WhatsApp transport, sales AI, OCR, alerts, and provisioning | Multiple services plus background jobs | 1,301-line synchronous orchestration and direct lessons dependency |
| whatsapp_agent/views.py | Webhook verification and dispatch | Thin inbound adapter | POST authentication is absent; processing should not run inline |
| static/sw.js | PWA install/fetch cache | Public static/offline shell | Caches personalized responses and owns root scope |
| templates and static/js | Rendering plus large amounts of feature behavior | Presentation layer | Inline logic, access hints, AI HTML sinks, and external dependencies are spread across templates |

### Dependency direction

Current direction:

    browser -> lessons views -> lessons models
    browser -> Realtime token view -> OpenAI -> browser WebRTC
    webhook -> whatsapp_agent services -> lessons.UserProfile
    lessons and whatsapp_agent -> english_course Telegram/OpenAI helpers

Desired direction:

    adapters/views -> domain services -> domain models/repositories
    domain services -> infrastructure ports -> OpenAI/Meta/Telegram/storage
    whatsapp payment approval -> entitlement service

The application does not need microservices to achieve this separation. Python modules and transactional service functions inside one Django deployment are sufficient.

## Prioritized issue register

### ARCH-001 — Centralize entitlement and lesson-access policy

- Metadata: Priority Next; severity P1 High; effort L; evidence Confirmed; confidence High; type architectural authorization risk with confirmed route gaps.
- Files/functions: `lessons/models.py::UserProfile.has_paid_lesson_access`, `can_use_classroom_teacher_features`, and access grant helpers; `lessons/views.py::lesson_list`, `lesson_detail`, `vocabulary_list`, `start_quiz`, `submit_answer`, `chat_with_gpt`, `mint_realtime_token`, and `mint_translator_token`; `lessons/views_classroom.py::_require_teacher` and `_require_teacher_voice_access`; `lessons/admin.py` grant actions.
- Evidence detail: Access decisions are duplicated across those helpers, views, classroom guards, sessions, templates, admin actions, and management commands. Lesson access also uses hard-coded primary-key ranges.
- Root cause: Entitlements grew as booleans and view conditions rather than a single policy vocabulary.
- Current consequence: Equivalent users can see different behavior depending on entry route and session history. Vocabulary and quiz/chat routes do not share the detail-page paywall. Teacher, paid, voice, translator, and classroom meanings differ by caller.
- Future consequence: Every new product or track multiplies condition branches, tests, and authorization regressions. Mobile/API clients will reproduce policy independently.
- Recommended solution: Introduce a small entitlement policy service with explicit decisions such as can_view_lesson, can_take_quiz, can_use_voice, can_use_translator, can_manage_classroom, and can_run_classroom_session. Make it the sole backend authority; templates consume its results. Keep UI checks informative, never authoritative.
- Implementation risk: High because current behavior contains undocumented exceptions, two numeric lesson tracks, guest sessions, and separate premium flags. Migrate one endpoint family at a time behind characterization tests.
- Required tests: Guest, authenticated-free, paid, expired, approved teacher, unapproved teacher, voice-only, translator-only, direct URL, missing session, and both curriculum tracks for every decision.
- Dependencies: DATA-002 entitlement ledger and DATA-004 curriculum schema should define the durable inputs. Security teacher approval from SEC-010 is a policy prerequisite.

### ARCH-002 — Split orchestration from oversized views and WhatsApp services

- Metadata: Priority Later; severity P2 Medium; effort L per extraction slice; evidence Confirmed; confidence High; type maintainability and change-risk issue.
- Files/functions: `lessons/views.py` (registration, access, AI, quiz, PWA, and profile functions); `whatsapp_agent/services.py::process_webhook_payload`, `handle_message_event`, `generate_sales_reply`, `evaluate_receipt`, `finalize_receipt`, and `provision_course_access_for_lead`; `whatsapp_agent/views.py::whatsapp_webhook`.
- Evidence detail: `lessons/views.py` is 1,457 lines and `whatsapp_agent/services.py` is 1,301 lines. Each contains unrelated presentation, policy, provider, persistence, and orchestration concerns.
- Root cause: Features were added directly to the nearest existing file and function-based view path.
- Current consequence: A small change requires reading large modules, imports are duplicated, external effects are difficult to mock consistently, and transactional boundaries are implicit.
- Future consequence: Merge conflicts, regressions, slow onboarding, circular dependencies, and inability to move slow work to background workers safely.
- Recommended solution: Keep the modular monolith and extract cohesive modules: accounts/registration, entitlements, curriculum/progression, quiz service, explanation generation, Realtime session factory, classroom service, WhatsApp inbound adapter, Meta transport, sales responder, receipt review, provisioning, and event logging. Views should parse/authorize/call/render.
- Implementation risk: Medium. Pure extraction can subtly change imports, transaction timing, logging, and patch targets in tests. Do not combine extraction with behavior changes.
- Required tests: Existing suite before/after, route response characterization, transaction rollback, external call count/order, and import/compile checks.
- Dependencies: ARCH-001 clarifies policy boundaries; PERF-001 clarifies job boundaries; DATA-001 supplies idempotent webhook ownership.

### ARCH-003 — Centralize versioned AI model and prompt configuration

- Metadata: Priority Later; severity P2 Medium; effort M; evidence Confirmed; confidence High; type AI maintainability and operational risk.
- Files/functions: `english_course/realtime.py::build_realtime_session_config`; `lessons/views.py::_content_creator_instructions`, `_teacher_instructions`, `mint_realtime_token`, `explain_section`, `chat_with_gpt`, and `motivational_message`; `lessons/views_classroom.py::_classroom_instructions`; `whatsapp_agent/services.py::_whatsapp_agent_openai_model` and `_build_sales_system_prompt`.
- Evidence detail: Realtime model selection is centralized, while text models and prompts are embedded in lesson and WhatsApp functions. The current modified voice route uses a lesson-agnostic content-creator prompt while the documented contract says it uses the lesson teacher prompt. That current-tree mismatch is Confirmed; whether content-creator mode is intended is Needs product-owner confirmation. Usage and latency controls are assigned separately to AI-002.
- Root cause: Each AI feature integrated directly with the SDK and copied configuration into its view/service.
- Current consequence: Documentation and runtime prompts drift; model upgrades require broad searches; business facts can disagree with settings; failure and cost behavior differ by feature.
- Future consequence: Uncontrolled spend, difficult prompt evaluation, silent behavioral regressions, and inability to compare models or roll back safely.
- Recommended solution: Define typed feature configurations containing model, prompt builder, timeout, retry policy, maximum input/output, safety policy, and version. Keep prompts in feature-owned modules and record safe prompt/model/outcome metadata. Server-authoritative quota, concurrency, usage, and cost controls remain the separate task AI-002.
- Implementation risk: Medium to High because prompt wording is product behavior. Preserve the user-authored working-tree prompt during extraction; change the selected customer persona only after product-owner confirmation and versioned evaluation.
- Required tests: Prompt snapshot/contract tests, lesson-data inclusion, language requirements, safe error behavior, timeout/retry limits, quota enforcement, and model-config override tests.
- Dependencies: ARCH-002 module extraction and security controls SEC-006 and SEC-011.

### DATA-001 — Make provider messages and webhook work idempotent

- Metadata: Priority Next; severity P1 High; effort M; evidence Confirmed; confidence High; type race and data-integrity risk.
- Files/functions: `whatsapp_agent/models.py::WhatsAppMessage.meta_message_id` and event/lead models; `whatsapp_agent/services.py::handle_message_event`, `_create_inbound_message`, `process_webhook_payload`, `_upsert_lead`, and `send_telegram_alert`; `whatsapp_agent/views.py::whatsapp_webhook`.
- Evidence detail: `WhatsAppMessage.meta_message_id` is indexed but not unique. `handle_message_event` performs exists-then-create. Webhook processing catches failures and returns success after an inbound row may already exist. Lead counters and alert deduplication are read/modify/write.
- Root cause: At-least-once provider delivery was treated as an ordinary synchronous request instead of an idempotent event stream.
- Current consequence: Concurrent duplicates can create multiple messages, receipts, replies, or provisions. A transient failure after message creation can be permanently skipped on provider retry.
- Future consequence: Duplicate charges/access, inconsistent lead states, lost messages, increasing support reconciliation, and unsafe background-worker migration.
- Recommended solution: Persist a minimal verified inbox event with a database-unique provider event ID and raw-body digest. Atomically claim/process it with explicit states and retry metadata. Use provider message ID uniqueness for inbound/outbound messages where present. Make handlers idempotent and use an outbox for sends/alerts.
- Implementation risk: High because uniqueness migrations must inspect and reconcile existing duplicates. Provider status and message IDs may inhabit different namespaces and require typed keys.
- Required tests: Same payload twice, simultaneous duplicate delivery, crash after inbox insert, crash after user provision, retry after provider timeout, out-of-order statuses, missing IDs, and poison-event quarantine.
- Dependencies: SEC-002 signature validation must occur before inbox acceptance; PERF-001 executes claimed jobs; a production-safe deduplication migration is required.

### DATA-002 — Introduce orders, verified payments, and expiring entitlements

- Metadata: Priority Next after critical fail-closed work; severity P1 High; effort XL; evidence Confirmed; confidence High; type missing domain model and data-integrity risk.
- Files/functions: `lessons/models.py::UserProfile`, `has_paid_lesson_access`, `grant_voice_access`, and `grant_translator_access`; `lessons/admin.py` entitlement actions; `whatsapp_agent/models.py::WhatsAppLead` and `WhatsAppReceipt`; `whatsapp_agent/services.py::provision_course_access_for_lead`, `_sync_existing_user_flag`, and `finalize_receipt`.
- Evidence detail: Course access is `UserProfile.is_paid`, voice/translator use flags plus optional expiry, and WhatsApp lead flags duplicate state. There is no order, payment, approval, entitlement source, grant/revoke actor, or course-expiry model.
- Root cause: Administrative booleans preceded payments and multiple premium products.
- Current consequence: Commercial duration cannot be enforced, grants cannot be reconciled to payments, reprocessing is ambiguous, and revocation history is absent.
- Future consequence: Subscription renewal, refunds, institutional licenses, discounts, bundles, and support audits become unsafe or impossible.
- Recommended solution: Add immutable Payment/Approval facts and time-bounded Entitlement records with product, account, source, source reference, starts_at, ends_at, status, grant/revoke actor, and audit timestamps. Compute active access from these records; retain a staged compatibility adapter for existing flags.
- Implementation risk: High. Existing boolean grants need a documented migration policy and may not have a known source or expiry. Never invent historical payment facts.
- Required tests: Active/future/expired/revoked grants, overlapping grants, refund, manual approval, duplicate source reference, concurrency, timezone boundaries, and compatibility with legacy flags during migration.
- Dependencies: SEC-001 containment and trusted payment design; DATA-003 verified account identity; ARCH-001 consumes entitlements.

### DATA-003 — Canonicalize, verify, and safely unique account phones

- Metadata: Priority Next; severity P1 High; effort L; evidence Confirmed; confidence High; type data-integrity and identity-security risk.
- Files/functions: `lessons/models.py::UserProfile.phone`; `lessons/forms.py::CustomRegisterForm`; `lessons/views.py::register`; `whatsapp_agent/services.py::_get_existing_profile_by_phone` and `provision_course_access_for_lead`; profile fixtures used only for aggregate evidence.
- Evidence detail: `UserProfile.phone` is nullable and non-unique. Registration validates format but not ownership. WhatsApp provisioning links by exact phone string and raises only when multiple rows already exist. The populated tracked fixture contains duplicate phone groups.
- Root cause: Phone began as contact metadata and later became an account-linking key.
- Current consequence: Equivalent numbers can differ in format, one unverified account can claim another person's WhatsApp payment, and duplicates block automation.
- Future consequence: Account recovery, notifications, payments, CRM sync, and identity merge become increasingly dangerous.
- Recommended solution: Create a normalized phone identity model or normalized unique field with verification state, verified_at, verification method, and controlled reassignment. Deduplicate existing data through a human-reviewed migration. Never link payment solely from an unverified profile value.
- Implementation risk: High because existing duplicates may represent real shared/contact data. A simple unique migration can fail or merge the wrong people.
- Required tests: Normalization variants, duplicate registration, verification challenge expiry/replay, reassignment, WhatsApp matching, legacy nulls, and concurrent claims.
- Dependencies: Product identity/recovery policy, a manual duplicate-resolution report, DATA-002 payment linkage, and privacy review.

### DATA-004 — Model curriculum track, language, order, access, and publication explicitly

- Metadata: Priority Later; severity P2 Medium; effort XL; evidence Confirmed; confidence High; type curriculum architecture and data risk.
- Files/functions: `lessons/models.py::Lesson` and `UserProfile.current_lesson`; `lessons/views.py::lesson_list`, `lesson_detail`, `_unlock_after_quiz_pass`, and `vocabulary_list`; tracked lesson fixtures for ID/track evidence.
- Evidence detail: Lesson order and language track are inferred from primary-key ranges. Free IDs and stage slices are hard-coded in `lessons/views.py`. `UserProfile.current_lesson` stores an integer rather than a relation.
- Root cause: Fixture insertion order and IDs became product taxonomy.
- Current consequence: Gaps, imports, deletions, and new tracks change navigation and access semantics. One numeric condition allows a non-paying path through the later track while the lesson list omits it.
- Future consequence: Content versioning, localization, reorder, A/B curricula, prerequisites, and institutional tracks cannot be represented safely.
- Recommended solution: Add stable curriculum entities: Course/Track, Stage/Level, Lesson position, published/free state, locale, prerequisite or progression rule, and optional content version. Keep database IDs as identities only. Migrate with an explicit mapping report and preserve public URLs through stable slugs or legacy redirects.
- Implementation risk: High because current IDs are embedded in fixtures, URLs, sessions, quiz attempts, profiles, templates, and tests.
- Required tests: Ordered navigation with gaps, two tracks, free/paid boundaries, unpublished lessons, prerequisite graph, migrated attempts, deep links, and stable redirects.
- Dependencies: CONTENT-001 fixture repair, ARCH-001 policy, product-owned curriculum mapping.

### DATA-006 — Reconcile legacy quiz state, question versions, and restore invariants

- Metadata: Priority Later; severity P2 Medium; effort L; evidence Confirmed; confidence High; type legacy quiz-integrity and restore risk.
- Files/functions: `lessons/models.py::QuizQuestion`, `QuizAttempt`, and `QuizAnswer`; `lessons/views.py::generate_quiz_questions`, `_sync_attempt_from_answers`, `start_quiz`, and `submit_answer`; `lessons/migrations/0014_quizanswer.py`, `0015_dedupe_quizattempt.py`, and `0016_quizattempt_unique_constraint.py`; tracked attempt/question fixtures.
- Evidence detail: `QuizAttempt` stores score, attempts, completed, and passed state while `QuizAnswer` is now authoritative. Migration 0014 added `QuizAnswer` without historical answer backfill. The database cannot enforce that an answer's question belongs to its attempt lesson. Runtime generation has no question uniqueness constraint. The tracked attempt fixture has a duplicate group and no corresponding `QuizAnswer` fixture.
- Root cause: Quiz integrity was strengthened after legacy aggregate attempts already existed.
- Current consequence: Historical passed attempts have no answer evidence; answer deletion/question edits can leave pass flags stale; fixture restore conflicts with current uniqueness; concurrent question generation can duplicate questions.
- Future consequence: Analytics, audit, regrading, content edits, and restore procedures will produce inconsistent results.
- Recommended solution: Document grandfathered legacy passes explicitly. Add model/service validation for cross-lesson answers, question identity/version policy, safe uniqueness where product semantics allow, and a fixture/import validator. Decide whether attempts snapshot a quiz version or are invalidated when content changes.
- Implementation risk: High for historical data. Do not fabricate answers or silently revoke passes.
- Required tests: Legacy pass behavior, question addition/removal, duplicate generation concurrency, cross-lesson writes outside the view, restore on a migrated database, and regrade/version transitions.
- Dependencies: DATA-004 curriculum/content versioning and CONTENT-001 fixtures.

### PERF-001 — Move authenticated webhook work to an idempotent background pipeline

- Metadata: Priority Next after SEC-002 and DATA-001; severity P1 High; effort L; evidence Confirmed; confidence High; type scalability and reliability risk.
- Files/functions: `whatsapp_agent/views.py::whatsapp_webhook`; `whatsapp_agent/services.py::process_webhook_payload`, `handle_message_event`, `download_whatsapp_media`, `evaluate_receipt`, and send/alert functions; `lessons/views.py::explain_section`; `english_course/utils/realtime_tts.py`; `Procfile`.
- Evidence detail: The WhatsApp request synchronously performs database work, OpenAI generation, Meta sends, Telegram sends, media downloads, PDF/image parsing, and OCR. Explanation generation synchronously performs text generation, Realtime TTS, conversion, file writes, and a fallback call. `Procfile` declares a basic synchronous Gunicorn WSGI process.
- Root cause: External workflows were implemented as request-call chains without a durable job boundary.
- Current consequence: Slow responses occupy web workers; one image can consume substantial memory/CPU; provider timeouts create ambiguous partial completion; retries are unsafe.
- Future consequence: Small traffic bursts can exhaust workers, cause provider retry storms, duplicate effects, and make web latency depend on OCR/AI.
- Recommended solution: Verify and persist the inbound event quickly, return an accepted response, and process durable jobs in a worker. Add explicit per-stage state, idempotency keys, timeouts, retry/backoff, dead-letter handling, and operator replay. Move explanation generation to a job with progress/result status. Stream and cap media rather than buffering it entirely.
- Implementation risk: High because asynchronous timing changes user messaging and error recovery. A queue without DATA-001 idempotency would amplify duplicates.
- Required tests: Worker crash/retry at every stage, duplicate jobs, provider timeout, poison document, size limit, cancellation, dead-letter replay, and exactly-once business outcome despite at-least-once job execution.
- Dependencies: DATA-001 first; select a supported broker/worker; deployment monitoring and operational runbook.

### PERF-002 — Bound queries, payloads, and catalog/vocabulary/message collections

- Metadata: Priority Before growth; severity P2 Medium; effort M; evidence Confirmed for unbounded/repeated paths and Inferred for scale impact; confidence High for paths and Medium for production impact; type scaling risk.
- Files/functions: `lessons/middleware.py::DeviceLockMiddleware.process_request` and `process_response`; `lessons/views.py::lesson_list`, `vocabulary_list`, `_quiz_answer_counts`, and `_quiz_state_payload`; `whatsapp_agent/services.py::_build_chat_conversation` and `generate_sales_reply`.
- Evidence detail: Device middleware performs repeated profile/device/count queries per authenticated request. `lesson_list` saves the session on every GET. `vocabulary_list` loads and parses every lesson vocabulary. WhatsApp general replies materialize the lead's message collection before slicing eight. Quiz state performs repeated count/filter queries.
- Root cause: Small initial datasets made whole-table and repeated ORM operations acceptable.
- Current consequence: Avoidable database writes and query volume, growing memory per conversation/vocabulary request, and latency tied to total historical data.
- Future consequence: Database contention and memory growth become visible before the application needs architectural scaling.
- Recommended solution: Profile with query-count tests. Fetch only the last required WhatsApp messages in SQL, paginate admin/history lists, avoid unconditional session saves, combine quiz aggregates, and replace device request-wide counting with a deliberate login/device-registration flow. Cache public curriculum aggregates only after correctness and invalidation are defined.
- Implementation risk: Medium. Optimization can change ordering, session behavior, and device enforcement; measure before and after.
- Required tests: Query-count assertions, ordering correctness, pagination boundaries, cache invalidation after content change, concurrent device registration, and memory/latency benchmarks using representative data.
- Dependencies: ARCH-001 for request policy, DATA-004 for cache keys, production observability.

### DEVOPS-001 — Upgrade to a supported Django/Python baseline

- Metadata: Priority Now/Next; severity P1 High; effort L; evidence Confirmed; confidence High; type unsupported and vulnerable dependency risk.
- Files/functions: `requirements.txt` Django and direct dependency declarations; the local `../venv/bin/python` runtime; `english_course/settings.py`; templates/static and database integrations requiring compatibility testing.
- Evidence detail: `requirements.txt` pins Django 5.1.6 and the local interpreter is Python 3.10.12. The official Django support table lists 5.1 as unsupported since 2025-12-03, and 5.1.7 fixed a moderate denial-of-service issue in 5.1.6. The official Python status page schedules Python 3.10 end of life for October 2026. The repository has no runtime-version file or CI matrix; some packages are unbounded or only lower-bounded.
- Root cause: Dependency capture reflects a working environment rather than an explicit supported platform and update policy.
- Current consequence: Reproduction depends on local knowledge; security/support status is not demonstrated; an unbounded install can change behavior unexpectedly.
- Future consequence: Emergency upgrades become large, Python/runtime drift breaks binary/system dependencies, and deploys differ from tests.
- Recommended solution: Target a currently patched supported release—Django 5.2 LTS is the conservative current line—and a host-supported Python with a longer security window; confirm exact patch versions at implementation time. Pin through a reproducible lock or constraints workflow and upgrade incrementally. Add CI and dependency monitoring. Do not perform a blind bulk upgrade.
- Implementation risk: Medium to High, especially around Django storage settings, auth views, OpenAI SDK schemas, websockets, Pillow/PDF behavior, and MySQL.
- Required tests: Full suite, check --deploy, migrations on SQLite and production-equivalent MySQL, static collection, media upload, OpenAI mocked contracts, OCR/PDF fixtures, and browser smoke tests.
- Dependencies: A production-like CI database, declared OS packages, and confirmation of current official support windows.

### DEVOPS-002 — Create a reproducible dependency, runtime, and environment baseline

- Metadata: Priority Next; severity P1 High; effort M; evidence Confirmed; confidence High; type reproducibility risk.
- Files/functions: `requirements.txt`; `english_course/settings.py` environment/database/OpenAI/static configuration; `Procfile`; absent runtime/lock/build manifests; the documented versus available virtualenv paths; external `ffmpeg` and Tesseract executables/language data.
- Evidence detail: The documented project-local virtualenv path is absent; no Python runtime declaration, dependency lock, build definition, or OS-package manifest exists. MySQL/PostgreSQL drivers are locally installed but undeclared, locally installed `pypdf` is outside the declared range, and TTS/OCR require external binaries. Settings import requires OpenAI and writes console output.
- Root cause: Dependency capture and deployment knowledge reflect one manually maintained host rather than an executable runtime and environment contract.
- Current consequence: Clean setup cannot reproduce the audited environment; management commands depend on an unrelated AI secret; fixture dumps can be polluted by settings output; database and OCR/audio support depend on out-of-band packages.
- Future consequence: New hosts, upgrades, disaster recovery, and release artifacts can disagree on Python, dependencies, database drivers, and system capabilities.
- Recommended solution: Declare the supported Python target, separate direct runtime/development dependencies, choose and declare the production database driver, use a reviewed lock/constraints workflow, document required OS binaries/languages, add a placeholder-only environment schema, and make optional integrations fail with actionable checks. Production settings hardening remains SEC-009; private/shared storage remains MEDIA-001; health/metrics remain DEVOPS-003.
- Implementation risk: Medium. Locking can surface incompatible transitive versions and platform-specific wheels; unused-looking packages may still have out-of-repository deploy use and require production-owner confirmation before removal.
- Required tests: From a clean environment, install, run `pip check`, compile, application tests, Django checks, production-database configuration import/connection, and OCR/TTS binary preflights; run path-safe secret scans without printing values.
- Dependencies: DEVOPS-001 target versions, SEC-009 settings split, selected production database/runtime, and production-owner confirmation for package/process usage.

### CONTENT-001 — Remove private runtime fixtures and regenerate valid sanitized fixtures

- Metadata: Priority Next after SEC-005; severity P1 High; effort M; evidence Confirmed; confidence High; type fixture defect and privacy risk.
- Files/functions: `lessons/fixtures/*.json`; `english_course/settings.py` import-time output; `lessons/models.py::QuizAttempt` and `QuizAnswer`; `lessons/migrations/0014_quizanswer.py` through `0016_quizattempt_unique_constraint.py`.
- Evidence detail: Every tracked lessons fixture begins with settings console output and is invalid JSON. Populated lead, profile, device, and quiz identity data are tracked. The attempt fixture conflicts with current uniqueness and no `QuizAnswer` fixture restores the new invariant.
- Root cause: dumpdata ran through noisy settings against a populated database and the output was committed without schema/privacy validation.
- Current consequence: loaddata is unreliable, personal data is distributed in source history, and fixtures do not describe a coherent current database.
- Future consequence: Test/demo environments fail or inherit private data; migration rehearsals give false confidence; agents treat stale generated content as canonical.
- Recommended solution: Remove populated personal-data fixtures from the current tree after coordinating SEC-014. Create minimal synthetic deterministic fixtures separated by purpose: curriculum seed, quiz-version seed, and test factories. Make fixture validation a CI step and prevent settings output on stdout.
- Implementation risk: High for content preservation and Low for synthetic test data. Do not overwrite the only known curriculum copy without a verified export and product-owner confirmation.
- Required tests: JSON parse, loaddata after all migrations, referential/unique constraints, expected record counts, no personal-data/secret scanner hits, deterministic dump round trip, and representative quiz generation.
- Dependencies: SEC-012/SEC-014 privacy handling, DATA-004 curriculum mapping, DATA-006 quiz policy.

### CONTENT-003 — Version derived quiz, explanation, and prompt/content contracts

- Metadata: Priority Later; severity P2 Medium; effort L; evidence Confirmed; confidence High; type staleness and change-risk issue.
- Files/functions: `lessons/views.py::generate_quiz_questions`, `explain_section`, `_content_creator_instructions`, `_teacher_instructions`, and `mint_realtime_token`; `lessons/models.py::Lesson`, `QuizQuestion`, and `Explanation`; `lessons/admin.py::LessonAdmin`.
- Evidence detail: Quiz questions are generated on first request by parsing an exact delimiter; existing questions remain after lesson vocabulary changes. Explanation text/audio is persisted without model/prompt/content version metadata. The current modified voice route ignores its `Lesson` argument; whether that creator persona is intended is Needs product-owner confirmation.
- Root cause: Authored content, derived quiz rows, generated explanations, and live prompts have no versioned publication workflow.
- Current consequence: Formatting silently disables quizzes, edits leave stale questions/explanations, and the same URL may deliver behavior unrelated to the current lesson.
- Future consequence: Editors cannot safely publish corrections, regenerate selected outputs, compare AI versions, or roll back.
- Recommended solution: Define validation and publication states for Lesson content. Generate and validate derived quiz content before publication. Record source-content hash, prompt version, model, generation status, and reviewed/published state for AI assets. Split content-creator experiences from customer lesson routes only after the intended persona is confirmed.
- Implementation risk: Medium to High because regeneration can invalidate attempts and replace reviewed content.
- Required tests: Vocabulary parser variants, publish validation, stale-hash detection, reviewed-output preservation, regeneration permissions, prompt includes intended lesson data, and rollback.
- Dependencies: DATA-004 curriculum/content version, DATA-006 quiz attempt policy, ARCH-003 prompt registry.

### MEDIA-001 — Introduce classified storage abstraction and reconciliation

- Metadata: Priority Next; severity P1 High; effort L; evidence Confirmed; confidence High; type media lifecycle and scaling risk.
- Files/functions: `lessons/views.py::explain_section`; `english_course/utils/realtime_tts.py`; `lessons/models.py::Explanation`, `StudentPhoto`, and `student_face_upload_path`; `whatsapp_agent/models.py::WhatsAppReceipt.file`; `lessons/views_classroom.py::classroom_student_photo`; `english_course/settings.py::MEDIA_ROOT`.
- Evidence detail: Explanation audio uses direct filesystem glob/open operations and URL strings. `StudentPhoto` and `WhatsAppReceipt` use `FileField`, but no deletion hooks, reconciliation, or retention jobs exist. Local `MEDIA_ROOT` mixes public generated and sensitive data classes.
- Root cause: Local single-host storage was treated as a permanent deployment model.
- Current consequence: Orphaned files, racing explanation replacement, database/file transaction mismatch, and unclear private/public serving.
- Future consequence: Horizontal deployment, backup/restore, retention, and privacy deletion fail across instances.
- Recommended solution: Classify media, use Django storage APIs, separate private and public buckets/prefixes, use immutable object names and database references, delete after transaction commit, and run reconciliation/retention jobs. Never expose the private root through a generic static mapping.
- Implementation risk: High because existing URLs and files need inventory/migration and rollback.
- Required tests: Upload/read authorization, physical deletion, orphan reconciliation, concurrent generation, missing object behavior, signed URL expiry, backup restore, and old URL transition.
- Dependencies: SEC-007, DEVOPS-002, selected storage provider.

### REPO-001 — Remove proven dead code, dependencies, and configuration drift

- Metadata: Priority Later; severity P3 Low; effort M; evidence Confirmed for visible dead/broken paths and Needs verification for out-of-repository deployment use; confidence High for code paths and Medium for deployment use; type maintainability and supply-chain issue.
- Files/functions: `lessons/chatgpt_helper.py`; `lessons/consumers.py`; `lessons/routing.py`; `lessons/auth_base.html`; `.gitignore.save`; `requirements.txt`; `english_course/settings.py::CHANNEL_LAYERS`; `AGENTS.md` environment commands.
- Evidence detail: `lessons/chatgpt_helper.py` references `settings` before importing it and has no demonstrated caller. Consumer/routing modules are historical markers. Channels/Redis/DRF/database-url/ffmpeg-python packages and configuration have no demonstrated active application path; `ffmpeg-python` does not supply the required executable. A duplicate template and tracked ignore-file debris remain. Production process usage outside the repository Needs verification.
- Root cause: Superseded experiments and deployment approaches were retained to preserve context, but active and historical components are not separated mechanically.
- Current consequence: Larger install surface, confusing architecture, false expectations about websocket/Redis capability, broken helper import, and onboarding command drift.
- Future consequence: Dependency vulnerabilities and upgrades consume effort for unused code; future agents may modify the wrong Realtime path.
- Recommended solution: Prove usage before removal. Delete or archive broken/dead code in a dedicated implementation task, remove unused packages/config after import/runtime checks, document OS binaries separately, and correct executable paths. If historical markers remain, exclude them from runtime modules and label them deprecated.
- Implementation risk: Low to Medium; deployment may use packages outside code-visible paths, so production import/process inspection is required.
- Required tests: Import graph, compileall, full tests, collectstatic, production start, Realtime browser smoke test, OCR/TTS smoke tests, and dependency diff review.
- Dependencies: DEVOPS-001/DEVOPS-002 and production-owner confirmation.

### TEST-001 — Add adversarial payment, webhook, credential, and retention tests

- Metadata: Priority Now #6; severity P1 High; effort M; evidence Confirmed; confidence High; type missing security test foundation.
- Files/functions: `whatsapp_agent/tests.py` receipt/provision/send/webhook coverage; `whatsapp_agent/services.py::evaluate_receipt`, `finalize_receipt`, `_send_whatsapp_payload`, and `provision_course_access_for_lead`; `whatsapp_agent/views.py::whatsapp_webhook`; new synthetic payload/receipt builders only.
- Evidence detail: Forty lessons and WhatsApp tests passed, but none cover receipt fraud/replay, webhook signatures, credential persistence, receipt approval, or private-data retention; existing tests explicitly entrench recipient mutation.
- Root cause: Tests were added around recent quiz and transport behavior rather than the payment/webhook threat boundary.
- Current consequence: Passing tests validate unsafe recipient fallback while SEC-001 through SEC-004 have no adversarial regression protection.
- Future consequence: Payment, signature, activation, redaction, and retention fixes can regress silently.
- Recommended solution: Add deterministic fake signed-webhook builders, forged/replayed receipt cases, fail-closed no-grant assertions, destination-integrity and secret-redaction assertions, provider failure/concurrency cases, and retention tests. Use no network calls or private values. Broader authorization tests are TEST-002, browser/XSS/PWA tests are TEST-003, CI is TEST-004, and observability is DEVOPS-003.
- Implementation risk: Low, but tests must replace unsafe expectations without normalizing vulnerable behavior or leaking copied production payloads.
- Required tests: Each acceptance criterion for SEC-001 through SEC-004, including missing/wrong/altered signatures, old/duplicate/cross-lead receipts, no entitlement mutation, no changed recipient, no plaintext secret in persistence/output, provider failure, concurrency, and bounded retention.
- Dependencies: Can begin against current behavior to demonstrate failures; CI execution depends on TEST-004, and implementation passes depend on SEC-001 through SEC-004.

## Performance and scalability assessment

Scale is expressed as active registered users and concurrent/background work, not raw account count alone. Security controls, idempotency, and data correctness are required at every scale.

| Area | Around 100 users | Around 1,000 users | Around 10,000 users | Timing decision |
| --- | --- | --- | --- | --- |
| WhatsApp webhook | Synchronous path may appear adequate but remains unsafe under one slow OCR/AI call | Bursts and retries can exhaust sync workers | Requires durable queue, worker autoscaling, dead-letter/replay, and provider-aware backpressure | PERF-001 and DATA-001 are required now because they protect correctness, not just scale |
| Web process | One or a few sync workers can serve ordinary pages | External calls cause tail latency and worker starvation | Horizontally scaled stateless web workers behind a load balancer | Move slow work before growth; do not adopt microservices now |
| Database | SQLite is acceptable only for isolated local development | Managed MySQL/PostgreSQL-equivalent production database, indexes, backups, query monitoring | Read/write tuning, connection pooling, replicas only if measurements justify | Explicit production DB and backups required now; replicas later |
| Device middleware | Extra queries are visible but tolerable | Repeated per-request counts and session writes create avoidable load | Hot auth path becomes significant | Redesign before 1,000; no specialized device service needed |
| Lesson list and vocabulary | Whole curriculum fits memory | Curriculum and user progress queries should be measured/cached selectively | Pagination/search and precomputed progress may be needed | Query tests now; caching before growth; no search cluster |
| Quiz | Small question sets are inexpensive | Repeated aggregates and runtime generation add write/query load | Prepublished versioned quizzes and batched analytics | Fix invariants now, optimize queries before growth |
| WhatsApp history/events | Small histories hide list materialization and payload duplication | Per-message history load and raw events grow quickly | Retention, pagination, archival/partitioning may be needed | Bounded query and retention before growth; partition later |
| OCR/media | A single large input can still exhaust memory | Worker isolation, strict size/pixel/page/time limits, object storage | Dedicated worker class and autoscaling; malware scanning if risk warrants | Limits and isolation required now; autoscale later |
| AI/Reatime usage | Cost abuse can exceed user volume | Shared per-user quotas and provider budgets required | Usage metering, concurrency scheduling, cost dashboards | Quotas and timeouts required now; sophisticated routing later |
| Media storage | Local disk works for one disposable developer host | Shared/object storage required for multiple workers and reliable backup | Lifecycle tiers/CDN for public assets, private signed delivery | Classify/private storage before growth; CDN optimization later |
| Cache/Redis | Not required for ordinary pages | Useful for shared rate limits, job broker, and selected cache | High availability and eviction/monitoring plan | Introduce only for a concrete queue/rate/cache use case |
| Observability | Structured redacted logs and error alerts | Metrics, traces for external calls, queue dashboard | SLOs, capacity forecasts, sampling and retention tiers | Basic observability required now; full SLO program before 10,000 |
| Deployment | Manual host may work but is not reproducible | Automated build/release, health checks, rollback | Multiple instances, staged rollout, disaster recovery exercises | Reproducible build required before growth |

### Required now

- SEC-001 through SEC-012 containment and trust-boundary work.
- DATA-001 webhook idempotency.
- DATA-002 entitlement/payment ledger design before more payment automation.
- Strict upload/body/time/output limits.
- Reproducible production configuration, backups, secret handling, and structured redacted logs.
- Query-count baselines and bounded WhatsApp history.

### Required before meaningful growth

- PERF-001 worker queue and operational replay.
- Shared/object media storage with private authorization.
- Canonical verified phone identity.
- Explicit curriculum schema and versioned content publication.
- Shared rate-limit state and usage metrics.
- CI against a production-equivalent database and declared Python/Django runtime.

### Later, only when measurements justify it

- Read replicas.
- Event-table partitioning or cold archival.
- CDN for public generated audio.
- Worker autoscaling by queue class.
- Search service for a materially larger content catalog.

### Deliberate non-goals and no-overengineering guidance

- Do not split OqyAI into network microservices now.
- Do not add Kubernetes solely to solve code boundaries.
- Do not introduce event sourcing for ordinary lesson progress.
- Do not shard the database or add replicas without observed capacity pressure.
- Do not cache authorization decisions until invalidation and entitlement semantics are stable.
- Do not add Redis merely because its packages are already present; adopt it for a defined queue, shared limit, or measured cache.

## Code, data, content, and repository observations

### Code quality

| Mapped task | Type / severity / effort | Evidence and confidence | Confirmed observation |
| --- | --- | --- | --- |
| ARCH-002 | Architecture/change risk; P2 Medium; L per slice | Confirmed; High | `lessons/views.py` and `whatsapp_agent/services.py` are the dominant mixed-responsibility change hotspots. |
| SEC-006 / SEC-012 | Security/privacy defects; P1 High; S and L | Confirmed; High | Several `lessons/views.py` endpoints return exception strings to browser JSON and those strings can reach HTML sinks; Realtime token errors use a generic response. |
| REPO-001 | Maintainability; P3 Low; M | Confirmed; High | `lessons/views.py` imports `login` twice and contains comments describing superseded behavior. |
| DATA-002 | Entitlement data integrity; P1 High; XL | Confirmed; High | `UserProfile.grant_voice_access` and `grant_translator_access` reset expiry from current time and can shorten a longer grant; the corresponding management commands accept unvalidated day values. |
| ARCH-002 | Architecture/change risk; P2 Medium; L per slice | Confirmed for missing boundaries; Medium for consequence | Function-based views are not inherently a defect, but authorization, transactions, and external effects currently lack cohesive service boundaries. |

### Data design

| Mapped task | Type / severity / effort | Evidence and confidence | Confirmed observation or inference |
| --- | --- | --- | --- |
| DATA-006 / SEC-012 | Quiz lifecycle and retention; P2/P1; L | Confirmed; High | `QuizAttempt.user_id` is a polymorphic string for account IDs and guest session keys, has no user foreign key/lifecycle relationship, and can survive account deletion. |
| DATA-003 | Identity/data integrity; P1 High; L | Confirmed; High | `lessons.models.Lead` and `whatsapp_agent.models.WhatsAppLead` duplicate contact concepts without a linkage or deduplication policy. |
| REPO-001 / SEC-010 | Schema drift and classroom privacy; P3/P1; M | Confirmed for fields and inspected paths; High | `ClassStudent.user` and `face_embedding` exist but are not used by the inspected server workflows. Removal or future use Needs product-owner confirmation and production-use verification. |
| DATA-002 / DATA-001 | Entitlement and state integrity; P1 High; XL/M | Confirmed; High | WhatsApp lead status/paid fields, profile paid state, receipt validation, and linked username can drift because no database state machine relates them. |
| DEVOPS-002 | Environment/database reproducibility; P1 High; M | Inferred; Medium | Production MySQL collation may apply different text-uniqueness semantics from local SQLite for class/school names; the actual production engine and collation Need verification. |

### Content operations

| Mapped task | Type / severity / effort | Evidence and confidence | Confirmed observation |
| --- | --- | --- | --- |
| DATA-004 | Curriculum architecture; P2 Medium; XL | Confirmed; High | `Lesson` has no publication, slug, locale, track, stage, order, or version fields. |
| CONTENT-003 | Content workflow; P2 Medium; L | Confirmed; High | `LessonAdmin` does not expose quiz, explanation, or classroom models, leaving runtime generation and direct data operations as important content paths. |
| DATA-005 / CONTENT-003 | Generated-content lifecycle; P2 Medium; L | Confirmed; High | `Explanation` has no review/publish, source-hash, model, or prompt-version metadata. |
| BUG-001 / DATA-004 | Commercial/curriculum correctness; P1/P2; S/XL | Confirmed; High | Product price/duration and track visibility are repeated in code, templates, and prompts. The canonical offer and intended later-track visibility each Need product-owner confirmation. |

### Repository hygiene

| Mapped task | Type / severity / effort | Evidence and confidence | Observation |
| --- | --- | --- | --- |
| DEVOPS-006 | Secret/data workflow; P1 High; M | Confirmed positive control; High | `.env`, local databases, media, static collection, and virtual environments are ignored; automated content/path gates and least-privilege permissions are still absent. |
| CONTENT-001 | Fixture defect/privacy; P1 High; M | Confirmed; High | Populated fixtures are tracked and malformed. |
| DEVOPS-002 / TEST-004 | Reproducibility and CI; P1/P2; M/M | Confirmed; High | No CI workflow, runtime declaration, build/lock definition, formatter/linter/type configuration, or sanitized environment example exists. |
| DEVOPS-001 / DEVOPS-002 | Dependency support/reproducibility; P1 High; L/M | Confirmed; Medium | `requirements.txt` mixes exact pins, ranges, duplicated OpenAI declarations, and an unpinned WhiteNoise dependency. |
| DEVOPS-003 / DEVOPS-005 | Observability/release operations; P2 Medium; M/M | Needs verification; Low | Production may have out-of-repository build scripts or monitoring, but none can be credited from repository evidence. |

## Verification evidence

Executed during the audit:

- ../venv/bin/python manage.py test: 40 tests passed on both audit runs.
- ../venv/bin/python manage.py makemigrations --check --dry-run: no changes detected.
- ../venv/bin/python manage.py check --deploy: warnings for HSTS, SSL redirect, and signing-key strength.

Not executed:

- Live OpenAI, Meta, Telegram, OCR, browser camera/microphone, or payment-provider tests.
- Production database, proxy, storage, backup, restore, concurrency, or load tests.
- Destructive fixture loads or migration changes.

Passing tests are evidence of the covered contracts only; they are not production-readiness evidence.

## Recommended technical sequence

1. Contain SEC-001 and remove SEC-003/SEC-004 behavior.
2. Implement SEC-002 and DATA-001 so inbound work has an authenticated, idempotent boundary.
3. Define DATA-002 and DATA-003 before restoring automatic payment provisioning.
4. Fix SEC-006 and SEC-008 because both cross authenticated browser boundaries.
5. Establish ARCH-001 policy tests, then correct route-level access inconsistencies.
6. Add PERF-001 durable jobs and MEDIA-001 storage lifecycle.
7. Introduce DATA-004 and CONTENT-001/CONTENT-002/CONTENT-003 through explicit migration and content-owner review.
8. Decompose modules under ARCH-002 without behavior changes.
9. Centralize AI behavior through ARCH-003.
10. Complete DEVOPS-001/DEVOPS-002 and TEST-001 before broader rollout.
