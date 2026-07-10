# OqyAI Feature Roadmap

## Document status

- **Purpose:** distinguish the product that is confirmed in the repository from proposed work, then define ten evidence-based opportunities in stable priority order.
- **Review basis:** static repository inspection only; code presence does not prove production configuration, external-service availability, usability, accuracy, or legal readiness.
- **Last reviewed:** 2026-07-10.
- **Implementation status:** every `FEAT-*` item is a proposal. None should be described as implemented until its acceptance criteria are verified.
- **Measurement status:** no product analytics integration was found. Every KPI baseline and target **Needs analytics data**.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| Implemented | A coherent route/model/template path exists in the repository. Runtime and production quality are still unverified. |
| Partial | A useful path exists, but material lifecycle, state, content, or UX work is missing. |
| Experimental | Substantial code exists, but product correctness, privacy, cost, or external operation is not established. |
| Missing | No coherent current product implementation was found. |
| Proposed | Roadmap work only; not current functionality. |

## Confirmed current feature inventory

### Implemented in code

| Capability | Evidence | Important boundary |
| --- | --- | --- |
| Username/password registration and login | `lessons/forms.py::CustomRegisterForm`; `lessons/views.py::register`; auth routes/templates | Recovery, verification, visible invalid-login feedback, and consent are not complete. |
| Student/teacher profile role | `lessons.models.UserProfile.role`; registration radio field | Teacher status is self-declared, not verified. |
| Course catalog and sequential progress | `lessons/views.py::lesson_list`; `lesson_list.html` | Five stages and ordering are hard-coded by lesson ID; access states are misleading in some unpaid cases. |
| Four-section lesson rendering | `Lesson` fields and `lesson_detail.html` | Sections are free-form text rather than versioned activity blocks. |
| Vocabulary translation quiz and stored answer state | `QuizQuestion`, `QuizAttempt`, `QuizAnswer`; `start_quiz`; `submit_answer` | Quiz covers vocabulary only; retry/next/mastery UX is incomplete. |
| Profile access summary and account deletion | `lessons/views.py::profile`; `profile.html` | Profile editing, order history, recovery, and device management are absent. |
| Classroom group/student/photo CRUD subset | classroom models/forms/views/templates | Individual photo/voice deletion, consent, verified teacher role, and persistent sessions are absent. |
| Privacy-policy page | `privacy_policy.html` | Copy is incomplete and behind current AI, receipt, and classroom processing. |

### Partial

| Capability | Evidence | Missing or incomplete |
| --- | --- | --- |
| AI explanations and educational audio | `Explanation`; `explain_section`; conditional audio players | Fixture coverage is limited; normal learners see blank explanation panels; content edits can leave generated output stale. |
| Global vocabulary view | `vocabulary_list` view/template | It is an unpersonalized raw-line dump with no provenance, mastery, audio workflow, or review scheduling. |
| Course purchase/access | `advertisement`; `UserProfile.is_paid`; WhatsApp handoff | No shared commercial truth, order, paid-until, pending/rejected/refund UI, or in-app reconciliation. |
| Access cards for course, voice, translator, classroom | `views.py::profile`; `profile.html` | Labels/copy are inconsistent and do not form a complete entitlement lifecycle. |
| Responsive rules | media queries in major templates/static CSS | Browser reflow was not tested; fixed widgets and zoom restrictions are known risks. |
| PWA shell | `manifest.json`, `sw.js`, `pwa-register.js`, `base.html` | Active templates do not use the shell; cache list/policy is incomplete. |

### Experimental

| Capability | Evidence | Why experimental |
| --- | --- | --- |
| Individual Realtime voice lesson | `voice-lesson.js`; `mint_realtime_token` | The selected prompt is a social-video joke prompt rather than the lesson-grounded tutor prompt; cost and learning quality are unmeasured. |
| Realtime speech translator | `translator-assistant.js`; translator token/access views | No explicit language controls, consent, cost telemetry, or live service verification. |
| AI classroom session | `views_classroom.py`; `classroom/session.html`; `classroom-lesson.js` | Realtime, face, voice, and hand pipelines are complex; consent, persistent outcomes, correction, and real-class accuracy are not established. |
| WhatsApp sales and automated receipt provisioning | `whatsapp_agent` models/services/views | External operation is environment-dependent; commercial truth is inconsistent; receipt/access lifecycle needs stronger controls. |
| Client-side recognition readiness | face/voice libraries and classroom browser code | “Ready” uses permissive sample counts and has no consent or measured accuracy contract. |

### Missing

| Capability | Repository finding |
| --- | --- |
| Product funnel and learning analytics | No product analytics integration or event schema was found. |
| Order/payment/expiring entitlement ledger | Course access is an indefinite Boolean. |
| Password/phone recovery and account verification | No recovery routes/templates or OTP/email verification flow was found. |
| Versioned, multilingual, draft/publish course CMS | `Lesson` has only free-form content fields and creation time. |
| Personal vocabulary mastery/spaced review | No user-word/review schedule models or flows exist. |
| Persistent classroom sessions, attendance, outcomes, and reports | No classroom session/attendance/outcome model exists. |
| Complete consent and biometric lifecycle | No guardian/school consent record or individual biometric deletion workflow exists. |
| Designed offline lesson packs and reminders | Service-worker placeholders exist, but no safe user-scoped offline/notification product flow exists. |

## Impact-effort priority

The stable roadmap order below balances correctness, revenue integrity, learning value, risk, and dependency order. Impact and effort remain hypotheses until measured.

| Rank | ID | Proposed feature | Horizon | Impact | Effort | Primary outcome |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | FEAT-001 | Commercial truth, order, and entitlement foundation | Strategic foundation | Very high | L | Trust, conversion, revenue correctness |
| 2 | FEAT-002 | Privacy-safe product analytics foundation | Quick-win foundation | Very high | M | Evidence for every later decision |
| 3 | FEAT-003 | Role-aware activation, recovery, resume, and device center | Quick win | High | M | Activation and return success |
| 4 | FEAT-004 | Versioned course authoring and content-QA workspace | Strategic | Very high | L/XL | Safe content scale and quality |
| 5 | FEAT-005 | Mastery-first lesson and quiz flow | Quick win | High | M | Learning completion and continuation |
| 6 | FEAT-006 | Personal vocabulary and spaced-review deck | Strategic | High | M | Habit and long-term retention |
| 7 | FEAT-007 | Lesson-grounded voice tutor with usage controls | Strategic | High | M/L | Premium learning value with cost control |
| 8 | FEAT-008 | Consent-safe classroom readiness and session reports | Long-term | Very high | L/XL | Safe school adoption and teacher value |
| 9 | FEAT-009 | Kazakh-first localization and accessible component system | Quick-win foundation, completed strategically | High | L | Comprehension, inclusion, delivery speed |
| 10 | FEAT-010 | Offline daily plan and opt-in reminders | Long-term | Medium/high | M/L | Mobile reliability and retention |

## Proposed opportunities

## FEAT-001 — Commercial truth, order, and entitlement foundation

- **Status:** Proposed.
- **Category:** Monetization, entitlement, operations.
- **Horizon:** Strategic foundation; start with a narrow external-transfer-compatible slice.
- **Problem:** web offer copy, guide copy, settings, WhatsApp sales instructions, and receipt validation do not share one commercial source. Course access is an indefinite Boolean, so the promised duration, payment state, refunds, renewals, and reconciliation cannot be represented reliably.
- **Target user and outcome:** Kazakh learners purchasing access, plus finance/support operators reviewing it, get one auditable lifecycle from offer view to expiring access while the MVP preserves the existing external payment channel.
- **User story:** as a Kazakh learner, I want to see one clear price and duration, receive an order reference before leaving the app, track review status, and know exactly when my access begins and ends.
- **Current evidence:** `lessons/views.py::advertisement`; `includes/guide-modal.html`; `english_course/settings.py::COURSE_PRICE_KZT`; `whatsapp_agent/services.py::_build_payment_reply`, `_build_sales_system_prompt`, `evaluate_receipt`, and `provision_course_access_for_lead`; `UserProfile.is_paid` and `has_paid_lesson_access()`.
- **Core flow:** choose offer → create order/reference → external payment instructions/handoff → receipt/provider event linked to order → validation/manual review → entitlement grant → in-app and external confirmation → expiry/renew/refund.
- **MVP:**
  - Central offer configuration with product, display price, currency, duration, status, and version.
  - `Order`, `PaymentReview`, and expiring `Entitlement` records with pending, needs-review, confirmed, rejected, refunded, expired states.
  - A signed order reference carried into the WhatsApp conversation and receipt processing.
  - Profile/order status UI and localized recovery instructions.
  - One-time account setup link for newly provisioned users instead of sending a reusable password.
  - Admin review and idempotent grant/revoke actions.
- **Advanced scope:** regulated payment-provider checkout, webhooks, invoices, promotions/coupons, renewals, refunds, subscription grace periods, finance export, fraud/risk scoring, and multi-product bundles for course/voice/translator/classroom.
- **Code relationship:**
  - **Modules:** `lessons/views.py`, `lessons/models.py`, `profile.html`, `advertisement.html`, `whatsapp_agent/services.py`, `whatsapp_agent/models.py`, settings.
  - **Models:** add offer/order/payment/entitlement models; migrate `is_paid` through a compatibility layer before removal.
  - **APIs:** order creation/status and verified payment/receipt transitions; keep server authority.
  - **Jobs:** expiry/renewal reminders and reconciliation; no scheduler currently provides this lifecycle.
  - **Analytics:** `offer_viewed`, `order_created`, `handoff_opened`, `receipt_received`, `review_changed`, `entitlement_granted`, `entitlement_expired`, `refund_completed`.
- **Privacy, security, and AI cost:** receipts and payment metadata are sensitive; restrict access, define retention, encrypt transport/storage as appropriate, audit every state change, deduplicate transaction references, require signed/idempotent callbacks, and use manual review for uncertainty. Do not use an LLM as the authority for access grants. AI cost is not required for the MVP.
- **Effort:** L; provider checkout and finance automation are XL.
- **Business, retention, and conversion impact:** very high conversion/trust impact, fewer receipt escalations, correct renewals/expiry, and measurable revenue attribution. Retention improves when renewal and access state are predictable.
- **Operations:** assign offer owner, finance review owner, support scripts, reconciliation cadence, refund SLA, incident rollback, and migration procedure for existing paid users.
- **KPI:** **Needs analytics data** — offer-to-order, order-to-receipt/payment, validation success, median access time, manual-review rate, entitlement mismatch, renewal, refund, and support-contact rate.
- **Acceptance criteria:**
  1. Every web and WhatsApp offer reads the same active offer version.
  2. Every access grant is traceable to an authorized order/payment/admin event.
  3. Duplicate receipt/provider events cannot grant duplicate access.
  4. New and existing users see pending, confirmed, rejected/needs-review, expiry, and renewal states in Kazakh.
  5. Expiry is enforced server-side and covered by tests.
  6. No reusable password is included in a payment confirmation.
- **Dependencies:** product/legal commercial policy, migration plan, support/finance ownership, messaging-channel order reference support, and a minimal analytics event-contract slice (names, prohibited properties, and idempotency) agreed before instrumentation; this is not a dependency on full analytics delivery.
- **Migration impact:** High—add offer/order/payment-review/entitlement records and backfill `is_paid` through a compatibility layer without inventing payment history.
- **Deployment impact:** Deploy schema first, then dual-write/shadow-read and reconcile before server-authoritative cutover; coordinate finance/support and external messaging copy.
- **Rollback notes:** Retain new audit/ledger records and revert to the compatibility read only if necessary; never restore OCR-only automatic grants or reusable-password delivery.
- **Documentation updates:** Update commercial truth, payment/support, data model, privacy/security, environment, reconciliation, and incident runbooks.

## FEAT-002 — Privacy-safe product analytics foundation

- **Status:** Proposed.
- **Category:** Analytics, experimentation, product operations.
- **Horizon:** Quick-win foundation.
- **Problem:** no trustworthy acquisition, activation, learning, payment, retention, AI usage, or classroom funnel exists. Operational fixtures cannot answer product questions and contain data that should not be repurposed casually.
- **Target user and outcome:** Product, learning, finance, and operations teams get a minimal privacy-safe event system that connects anonymous consideration to learning and entitlement outcomes without collecting chat, audio, receipt, or biometric payloads.
- **User story:** as a product team, we want to know where Kazakh learners succeed or stop so that changes are prioritized with evidence rather than anecdote.
- **Current evidence:** repository search found no analytics vendor/event abstraction; `pwa-register.js::trackInstallation` is an empty placeholder. `WhatsAppAgentEvent` is operational integration logging, not a complete product analytics system.
- **Core flow:** define event → validate schema → emit server/client event with pseudonymous identity and context → deduplicate → retain minimally → aggregate funnel/quality/cost metrics → role-limited dashboard → review data quality.
- **MVP:**
  - Versioned event dictionary, naming rules, required properties, prohibited sensitive properties, and ownership.
  - Server events for registration, quiz completion, order/entitlement changes, and Realtime token/session budgets.
  - Client events for catalog, lesson, paywall, CTA, resume, loading/error, and accessible interaction outcomes.
  - Anonymous-to-user identity merge with consent and deduplication.
  - Basic activation, revenue, learning, retention, AI, and classroom dashboards plus data-quality checks.
- **Advanced scope:** cohort analysis, controlled experiments, feature flags, attribution, learning-outcome studies, anomaly detection, warehouse models, and privacy-preserving school dashboards.
- **Code relationship:**
  - **Modules:** new analytics service called from `lessons/views.py`, `views_classroom.py`, static JS managers, and `whatsapp_agent/services.py` state transitions.
  - **Models:** vendor-backed or minimal first-party event/outbox model; avoid placing analytics fields on core records.
  - **APIs:** authenticated/anonymous event intake with schema validation and rate limits if client events are accepted.
  - **Jobs:** outbox delivery, aggregation, retention deletion, and data-quality alerts.
  - **Analytics:** this feature defines the canonical schema; initial events must cover all later `FEAT-*` KPIs.
- **Privacy, security, and AI cost:** pseudonymize identifiers; never include free text, audio/transcripts, phone, receipts, student names, photos, embeddings, or raw camera/recognition data. Document consent, retention, processor, access, deletion, and school boundaries. No AI cost is required.
- **Effort:** M.
- **Business, retention, and conversion impact:** enables measured conversion and retention work, identifies operational breakage quickly, and prevents expensive feature investment without evidence.
- **Operations:** nominate event owners, schema review, dashboard access roles, retention owner, weekly data-quality review, and incident handling for accidental sensitive collection.
- **KPI:** **Needs analytics data** — event coverage, schema rejection, duplicate rate, identity merge success, dashboard freshness, prohibited-property incidents, and funnel completeness.
- **Acceptance criteria:**
  1. A reviewed event dictionary covers visitor, registration, lesson, quiz, paywall, order, entitlement, voice, and classroom milestones.
  2. Automated tests reject prohibited sensitive properties and malformed events.
  3. Critical state changes emit idempotent server events.
  4. Dashboards reconcile sampled source records within an agreed tolerance.
  5. User deletion/retention workflows remove or anonymize analytics data as documented.
- **Dependencies:** privacy/legal review, identity policy, infrastructure/vendor decision, and the approved offer/order/entitlement vocabulary from the first `FEAT-001` slice; full `FEAT-001` implementation is not a prerequisite.
- **Migration impact:** Optional new event/outbox storage and identity-link data; do not repurpose operational payload tables or migrate sensitive free text.
- **Deployment impact:** Ship schema validation and prohibited-property gates before emitters, then stage server events, client events, dashboards, and retention jobs.
- **Rollback notes:** Disable individual emitters/dashboards without deleting required state-change audit; keep deletion/retention controls active.
- **Documentation updates:** Maintain the event dictionary, identity/consent rules, retention policy, dashboard ownership, data-quality checks, and analytics incident procedure.

## FEAT-003 — Role-aware activation, recovery, resume, and device center

- **Status:** Proposed.
- **Category:** Activation, account, navigation.
- **Horizon:** Quick win, delivered incrementally.
- **Problem:** student and teacher registrations share the same catalog redirect; teacher status is self-declared; invalid login has no visible error; recovery is absent; phone normalization is brittle; returning users lack a direct resume action; device locking has no self-service management and its detail page loses expiry context after logout.
- **Target user and outcome:** New and returning students, verified teachers, and locked-out account holders reach the correct next valuable action and can recover, resume, or manage devices safely without routine support.
- **User story:** as a student, I can register or recover with familiar local phone input and immediately start/resume my lesson; as a verified teacher, I can immediately continue classroom setup; as a user, I can review/revoke devices before a lock blocks me.
- **Current evidence:** `CustomRegisterForm`; `register()` common redirect; `login.html` omits errors; no recovery URLs; `register.html` phone script; `UserProfile.current_lesson`; profile quick links; `DeviceLockMiddleware`; `account_locked` view/template.
- **Core flow:** choose role → normalize/verify identity and accept policy → role-specific activation checklist → start/resume destination → return via preserved `next`; recovery/device flow → successful return.
- **MVP:**
  - Localized login/form error summary and preserved intended destination.
  - Server-side acceptance/normalization of supported local/international phone forms and explicit uniqueness/ownership behavior.
  - Password reset or phone OTP recovery with abuse controls.
  - Student welcome with resume/start; teacher pending-verification state and first-class checklist.
  - Profile/catalog direct resume action.
  - Device list, revoke, clear explanation, and a lock page that displays actionable state without requiring an authenticated session.
- **Advanced scope:** placement check, learning goal/schedule, organization-issued teacher invitations, passkeys, trusted-device naming, account merge, and guided data import.
- **Code relationship:**
  - **Modules:** `forms.py`, `views.py::register/profile`, auth URLs/templates, middleware, profile/catalog templates.
  - **Models:** verification/recovery token, teacher verification/invitation, device metadata/audit; potentially normalized unique phone identity.
  - **APIs:** OTP/request/verify, device revoke, resume destination.
  - **Jobs:** expiring OTP/recovery cleanup and optional reminder; avoid sensitive content in messages.
  - **Analytics:** registration/auth/recovery/role/resume/device milestones and safe failure categories.
- **Privacy, security, and AI cost:** rate-limit and enumerate-safe recovery, hash single-use tokens, expire sessions after credential changes, require verified teacher authorization, protect device endpoints, and avoid exposing whether a phone exists. No AI cost is required.
- **Effort:** M; organization-grade teacher verification can become L.
- **Business, retention, and conversion impact:** higher registration and first-value conversion, fewer lock/recovery tickets, better return completion, and safer teacher acquisition.
- **Operations:** teacher approval owner/SLA, recovery support escalation, duplicate-account merge procedure, and device-lock override audit.
- **KPI:** **Needs analytics data** — registration completion, first-value time, login failure, recovery completion, resume completion, teacher approval time, duplicate-phone rate, and lock-related support.
- **Acceptance criteria:**
  1. Invalid credentials and registration errors are visible, localized, associated with fields, and accessible.
  2. Supported phone forms normalize to one canonical value under unit tests.
  3. Recovery succeeds without account enumeration and invalidates used/expired tokens.
  4. Student and teacher activation destinations differ according to verified state.
  5. Returning learners can resume the exact current lesson in one action.
  6. Users can review/revoke devices and understand a lock without private support details.
- **Dependencies:** `FEAT-002` activation events, privacy/terms version, teacher verification policy, messaging delivery provider, and phone migration/duplicate-resolution plan.
- **Migration impact:** Likely—canonical phone/verification state, single-use recovery records, verified-teacher state, and richer device metadata/audit require staged backfill and conflict review.
- **Deployment impact:** Configure approved delivery channels, base URLs, expiry and abuse limits; stage role/resume/device slices behind server policy.
- **Rollback notes:** Disable new recovery requests or optional onboarding UI safely while retaining token invalidation, teacher verification, device audit, and normalized identity data.
- **Documentation updates:** Update auth/recovery, teacher approval, phone normalization, device support, privacy/terms, analytics, and operations guidance.

## FEAT-004 — Versioned course authoring and content-QA workspace

- **Status:** Proposed.
- **Category:** Educational content, CMS, quality operations.
- **Horizon:** Strategic.
- **Problem:** `Lesson` is five free-form fields ordered by primary key. Stage/language are implicit, draft/publish/version/objective/prerequisite metadata is absent, admin only exposes `Lesson`, fixture JSON is polluted, generated quiz/explanation data can drift, and runtime quiz generation silently depends on a delimiter.
- **Target user and outcome:** Content editors, linguistic reviewers, publishers, and curriculum operators can safely author, validate, preview, publish, localize, and revise 250+ lessons without breaking learner progress or serving stale AI-derived content.
- **User story:** as a content editor, I can revise a draft lesson, see validation and derived-content impact, preview the learner experience, obtain approval, and publish a version without changing stable learner progress unexpectedly.
- **Current evidence:** `Lesson`, `QuizQuestion`, and `Explanation` models; hard-coded `lesson_list` slices; `generate_quiz_questions()` exits when rows exist; `explain_section()` updates generated output; `admin.py` registers no quiz/explanation/classroom content; fixture first-line pollution; Russian content is inferred from IDs.
- **Core flow:** create/import draft → assign language/level/order/objectives → validate sections/vocabulary/question coverage → generate or edit derived content → review/preview → approve/publish version → invalidate/cache safely → monitor defects → archive/rollback.
- **MVP:**
  - Explicit language, translation-group, level, order, objective, estimated duration, status, version, and published-at metadata.
  - Admin/editor screens for lesson, vocabulary, quiz questions, explanations, and audio with inline validation.
  - Deterministic import/export with dry-run, clean JSON, stable IDs, duplicate/reference checks, and rollback instructions.
  - Content fingerprint linking generated questions/explanations/audio to a lesson version; stale indicators after edits.
  - Learner preview and two-person publish approval for high-risk changes.
- **Advanced scope:** structured activity blocks, media library, curriculum graph/prerequisites, localization workflow, teacher feedback/issue queue, diff/rollback UI, automated linguistic checks, and controlled AI authoring assistance.
- **Code relationship:**
  - **Modules:** `lessons/models.py`, `admin.py`, content fixtures/workflow, `views.py` rendering/generation, classroom lesson selection.
  - **Models:** lesson version/revision, language/translation group, explicit vocabulary/activity/question metadata, generation provenance, review/publish audit.
  - **APIs:** preview/validation/import/export/publish; keep learner reads on published versions.
  - **Jobs:** asynchronous validation, audio/AI generation, duplicate checks, and stale-asset cleanup with retries and budgets.
  - **Analytics:** lesson version exposure, content error reports, question quality, publish lead time, and learning outcomes by version.
- **Privacy, security, and AI cost:** granular editor/reviewer/publisher permissions, immutable audit, safe file handling, no operational-user fixtures in content pipelines, output moderation and human approval. AI generation can be expensive; queue it, cap batches/tokens/audio minutes, record prompt/model/version, and never generate implicitly during learner traffic.
- **Effort:** L/XL, best delivered through compatible schema slices.
- **Business, retention, and conversion impact:** improves educational credibility and retention, reduces content incidents, enables Russian/other variants safely, and lowers operational publishing cost.
- **Operations:** content ownership/RACI, editorial style guide, release calendar, QA sample protocol, rollback, stale-content queue, and backup/restore drill.
- **KPI:** **Needs analytics data** — validation catches, publish lead time, stale-derived-content rate, defect reports, rollback rate, explanation/question coverage, and lesson completion by version.
- **Acceptance criteria:**
  1. Published learner content has explicit language, level, order, version, and status.
  2. A draft edit cannot alter the currently published learner version before approval.
  3. Quiz/explanation/audio provenance identifies stale derived content after a source edit.
  4. Import dry-run reports malformed, duplicate, missing-reference, and delimiter issues without writes.
  5. Editors can preview the real learner rendering and roll back a published version.
  6. Content fixtures/export are valid from byte zero and exclude operational user data by default.
- **Dependencies:** migration/version compatibility plan, editorial policy, storage/media strategy, background-job infrastructure, `FEAT-002` outcome events, and an approved language/terminology decision slice; this is not a dependency on the full localization system.
- **Migration impact:** High—backfill explicit language/track/order/status/version and derived-content provenance while preserving stable published reads and progress references.
- **Deployment impact:** Deploy compatible schema and dry-run validation first, then backfill/shadow compare, editor workflow, publishing cutover, and bounded background generation.
- **Rollback notes:** Keep the last approved published version readable and preserve all new revisions/provenance; switch the published pointer back rather than deleting migrated content.
- **Documentation updates:** Update content schema/workflow, editorial and localization glossary, import/export, AI generation, media lifecycle, QA, rollback, and operator training.

## FEAT-005 — Mastery-first lesson and quiz flow

- **Status:** Proposed.
- **Category:** Learning experience, assessment, progression.
- **Horizon:** Quick win for continuation/retry; strategic extension for mastery.
- **Problem:** lessons expose content sections but record only final vocabulary-translation quiz state. The short timer and three-error reset measure speed/persistence as much as learning. Completion ignores `next_lesson`; retry reloads an already-passed attempt; mistakes have no review/explanation.
- **Target user and outcome:** Learners completing lessons—including keyboard, screen-reader, and slower-processing users—get a clear study, practice, feedback, retry, and next-lesson loop with credible mastery evidence.
- **User story:** as a learner, I can study each section, practise without punitive time pressure, understand mistakes, retry a new attempt, and continue to the next lesson with one action.
- **Current evidence:** `lesson_detail.html` tabs/quiz JS; `start_quiz`, `submit_answer`, `_unlock_after_quiz_pass`; `QuizAttempt` unique per user/lesson; `QuizAnswer`; no section-completion or attempt-history model.
- **Core flow:** open/resume lesson → complete or revisit sections → start accessible assessment → answer → immediate explanatory feedback → review mistakes → pass/retry → next lesson → schedule weak items for review.
- **MVP:**
  - Next-lesson and catalog actions using server-returned state.
  - A true new-attempt/review behavior with attempt history or an explicit reset endpoint.
  - Untimed default or accessible extended-time control; optional challenge timer.
  - Correct-answer and concise explanation after response, plus end-of-quiz mistake review.
  - Section visited/completed state and resumable quiz progress.
  - Accessible progress/live feedback and consistent timing copy.
- **Advanced scope:** question types for grammar/listening/dialogue, mastery thresholds, adaptive review, diagnostic placement, teacher assignments, competency maps, and validated learning gains.
- **Code relationship:**
  - **Modules:** lesson template/JS, `views.py` quiz functions, lesson list/profile progress.
  - **Models:** separate quiz session/attempt history, section progress, question version/type/explanation, mastery/review link.
  - **APIs:** start/resume/new attempt, submit, review, complete, next destination.
  - **Jobs:** optional delayed review scheduling; no AI required.
  - **Analytics:** section, assessment, feedback, retry, review, pass, and next-lesson events with question/version IDs only.
- **Privacy, security, and AI cost:** server-authoritative scoring, object ownership, submission rate limits, idempotency, and no answer leakage before submission. No AI cost for MVP; any AI-generated feedback must be pre-reviewed/versioned rather than generated per answer.
- **Effort:** M.
- **Business, retention, and conversion impact:** increases lesson completion and continuation, improves perceived fairness/quality, and produces stronger retention and learning evidence.
- **Operations:** pedagogy owner defines pass/retry/accommodation policy; content team authors explanations; support can inspect safe attempt state; QA maintains assessment fixtures.
- **KPI:** **Needs analytics data** — lesson/section completion, quiz abandonment, first-pass, mistake-review use, retry success, next-lesson continuation, response time distribution, and D7 retention.
- **Acceptance criteria:**
  1. Passing a quiz exposes and successfully opens the authorized next lesson.
  2. Retry creates/resets a legitimate new attempt rather than returning immediately to passed completion.
  3. Learners can complete the required assessment without a short mandatory timer.
  4. Every incorrect answer receives a non-color-only result and reviewable correct answer/explanation.
  5. Refresh/reconnect preserves consistent server state and cannot duplicate accepted answers.
  6. Keyboard and screen-reader users can complete the full quiz.
- **Dependencies:** `FEAT-002` analytics, question/content versioning from `FEAT-004`, pedagogical assessment policy, role/resume state from `FEAT-003`, and central access-policy task `ARCH-001`; no classroom-feature catalog work is a prerequisite.
- **Migration impact:** None for next/retry/accessibility repairs; attempt history, section progress, and mastery extensions require additive version-aware schema and legacy-state handling.
- **Deployment impact:** Coordinate server endpoints and client state under a feature flag; publish reviewed assessment/timing policy and monitor completion/retry errors.
- **Rollback notes:** Preserve accepted progress and correctness fixes; disable optional mastery UI or new writes without reverting to the broken passed-attempt retry behavior.
- **Documentation updates:** Update quiz contracts, pedagogy/pass/retry policy, accessibility, analytics events, test cases, learner help, and support guidance.

## FEAT-006 — Personal vocabulary and spaced-review deck

- **Status:** Proposed.
- **Category:** Learning retention, vocabulary.
- **Horizon:** Strategic.
- **Problem:** the current vocabulary page deduplicates and displays raw full lines from every lesson, including locked content. It has no lesson provenance, saved/weak state, audio action, mastery, due date, or review loop.
- **Target user and outcome:** Learners who want durable vocabulary recall turn authorized lesson words and their own quiz mistakes into a personal, scheduled review habit.
- **User story:** as a learner, I can save a word or automatically capture a mistake, review due items in short sessions, hear pronunciation where available, and see improving recall.
- **Current evidence:** `views.py::vocabulary_list`; `vocabulary_list.html`; `Lesson.vocabulary` delimiter; `QuizQuestion`/`QuizAnswer`; optional explanation audio is section-level rather than word-level.
- **Core flow:** encounter/save/miss word → personal deck with lesson/context → due queue → recall/reveal/grade → schedule update → progress/resume → return weak items to lessons.
- **MVP:**
  - Normalize published vocabulary entries with source lesson/language and stable IDs.
  - User-word state: saved, introduced, weak, mastered, next review, interval, last result.
  - Automatic capture of incorrect quiz items and manual save from lesson.
  - Simple evidence-based spaced schedule, daily due queue, search/filter, no-results/empty states, and accessible keyboard review.
  - Reuse approved audio where possible; do not expose vocabulary from unauthorized lessons.
- **Advanced scope:** multiple review modes, sentence cloze/listening, personalized difficulty, teacher-assigned decks, offline review, pronunciation practice, and safe cohort insights.
- **Code relationship:**
  - **Modules:** vocabulary/lesson templates, quiz submit flow, content parser/CMS.
  - **Models:** normalized vocabulary item, lesson link/translation, user review state, review event.
  - **APIs:** save/remove, due queue, answer/grade, summary.
  - **Jobs:** due-reminder schedule, optional approved audio generation, cleanup of orphan content versions.
  - **Analytics:** word encountered/saved/due/reviewed/result/mastered and deck-session completion.
- **Privacy, security, and AI cost:** user-owned review data with standard ownership/deletion; school dashboards should aggregate minimally. No AI cost is required. Optional TTS must be generated once per approved item with budgets and human pronunciation checks.
- **Effort:** M after content normalization.
- **Business, retention, and conversion impact:** creates a repeatable daily habit, improves long-term recall and D7/D30 retention, and strengthens the paid course value proposition.
- **Operations:** content team resolves parse exceptions/duplicates; pedagogy owner selects scheduling rules; audio QA; reminder frequency and support documentation.
- **KPI:** **Needs analytics data** — lesson-to-save, due-review completion, 7/30-day recall, mastered words, weekly review sessions, reminder return, and course retention correlation.
- **Acceptance criteria:**
  1. Every review item has a published source, language, translation, and stable identifier.
  2. Unauthorized lesson vocabulary is not exposed through deck/search APIs.
  3. Incorrect quiz answers can enter the learner’s weak queue idempotently.
  4. Review results deterministically update the next due date and survive reload.
  5. Empty, due, completed, and offline-unavailable states are localized and accessible.
  6. Account deletion removes personal review state according to policy.
- **Dependencies:** `FEAT-004` normalized/versioned vocabulary, `FEAT-005` assessment integration, and `FEAT-002` analytics; later reminder/offline integration is optional, not a prerequisite.
- **Migration impact:** Add normalized vocabulary/source links, user review state, and review events; backfill only parseable published entries and report ambiguities for editorial resolution.
- **Deployment impact:** Import/validate content before enabling user writes, then stage save/mistake capture, due queue, scheduler, and optional approved audio.
- **Rollback notes:** Disable new review scheduling/UI while retaining user-owned review history and authorization boundaries; do not expose the legacy all-lessons dump.
- **Documentation updates:** Update vocabulary/content operations, scheduling policy, learner help, privacy/deletion, analytics, audio QA, and support procedures.

## FEAT-007 — Lesson-grounded voice tutor with usage controls

- **Status:** Proposed replacement/hardening of an experimental feature.
- **Category:** AI learning, premium voice, cost governance.
- **Horizon:** Strategic; correct grounding and caps before broader promotion.
- **Problem:** the premium UI promises an AI voice teacher for the current lesson, but `mint_realtime_token()` uses `_content_creator_instructions`, which is a static social-video joke persona and does not incorporate the lesson. The lesson-grounded `_teacher_instructions(lesson)` exists but is not selected. Sessions have a client timeout but no server usage ledger, consent/preflight, pause, transcript policy, outcome summary, or measured cost/learning value.
- **Target user and outcome:** Paid learners practicing speaking get a reliable Kazakh-guided session grounded only in their authorized selected lesson, while product/operations owners retain clear privacy and hard cost controls.
- **User story:** as a paid learner, I can test my microphone, understand how audio is processed, practise the current lesson, pause/stop safely, receive a concise summary, and never create unexpected usage beyond my allowance.
- **Current evidence:** prompt functions and selection in `lessons/views.py`; Realtime token helper; `voice-lesson.js` state machine, transcript UI, microphone, 30-minute client timeout; voice entitlement fields/methods on `UserProfile`.
- **Core flow:** entitlement/budget check → consent and mic preflight → mint short-lived session → lesson-grounded dialogue/practice → pause/stop/error recovery → usage finalization → learner summary and next action.
- **MVP:**
  - Select and test the lesson-grounded prompt with explicit lesson-data boundaries.
  - Server-side concurrent-session, daily/monthly minute, and maximum-session controls plus usage records.
  - Kazakh preflight: purpose, processor disclosure, mic test, environment guidance, allowance/time remaining.
  - Explicit start/pause/stop/retry and reliable cleanup on pagehide/navigation.
  - Grounding/quality evaluation set across levels and adversarial lesson content.
  - End summary containing practised items and suggested review without claiming unsupported pronunciation certainty.
- **Advanced scope:** learner-controlled goals, pronunciation rubric with validated confidence, saved opt-in summaries, teacher review, adaptive difficulty, lower-cost model routing, and multi-session progress.
- **Code relationship:**
  - **Modules:** `views.py::_teacher_instructions/mint_realtime_token`, `english_course/realtime.py`, `voice-lesson.js/css`, lesson/profile templates.
  - **Models:** AI usage/session ledger, allowance policy, optional consent version and learner-approved summary.
  - **APIs:** preflight/budget, token mint, heartbeat/finalize, summary/delete.
  - **Jobs:** abandoned-session reconciliation, budget/cost aggregation, anomaly alerts, optional summary generation.
  - **Analytics:** preflight, start, connect, minute, disconnect/error, stop reason, grounding evaluation, summary/review action.
- **Privacy, security, and AI cost:** explain third-party audio processing; minimize/avoid transcript retention by default; allow deletion; prevent prompt injection from lesson content; use short-lived secrets, per-user authorization, concurrency/rate caps, and safety identifiers. AI cost is high and variable; current baseline and provider price **Need analytics data** and current pricing review. Hard server caps are mandatory.
- **Effort:** M for grounding/preflight/caps; L for validated pronunciation and longitudinal adaptation.
- **Business, retention, and conversion impact:** can become a credible premium differentiator and speaking-retention loop; without correction it creates churn and uncontrolled cost.
- **Operations:** cost dashboard/alerts, allowance policy, incident kill switch, session-support runbook, prompt/model release QA, and privacy request handling.
- **KPI:** **Needs analytics data** — preflight-to-connect, connection success, disconnect/error, completed minutes, allowance utilization, cost/completed session, lesson-grounding pass rate, learner-rated usefulness, and review continuation.
- **Acceptance criteria:**
  1. Every session prompt includes the authorized selected lesson and passes grounding tests.
  2. Server policy prevents overlapping and over-budget sessions even if client controls are bypassed.
  3. Consent/preflight explains audio processing and the active allowance before microphone capture.
  4. Pause/stop/navigation releases microphone and finalizes usage under automated browser tests.
  5. Error states provide localized retry/exit guidance without exposing provider internals.
  6. Current per-session and aggregate cost can be reconciled from provider usage to internal records.
- **Dependencies:** `FEAT-001` entitlement policy, `FEAT-002` analytics, `FEAT-004` versioned lesson content, privacy/legal review, and current provider model/pricing evaluation.
- **Migration impact:** Likely additive session/usage/lease and prompt-version records; avoid transcript persistence unless separately approved and retention-governed.
- **Deployment impact:** Ship corrected prompt selection, server limits, preflight/consent, usage finalization, monitoring, and kill switch before enabling broader access.
- **Rollback notes:** Disable token minting or select the prior approved lesson-grounded prompt; retain usage/audit records and never restore the social-content persona for learners.
- **Documentation updates:** Update AI contracts, prompt/model register, privacy/audio processing, allowance/cost policy, evaluation, support, and incident runbooks.

## FEAT-008 — Consent-safe classroom readiness and persistent session reports

- **Status:** Proposed hardening/extension of an experimental feature.
- **Category:** Teacher/classroom, minors privacy, AI operations.
- **Horizon:** Long-term; consent and safe deletion are release gates.
- **Problem:** public users can self-select teacher; classroom stores student names/photos/voice embeddings and uses camera, face, voice, hand, attendance, and OpenAI roster instructions without a consent record. “Ready” accepts one sample despite guidance recommending more. Teachers without voice access receive a plain denial. No persistent session, attendance, outcome, correction, or individual biometric deletion flow exists.
- **Target user and outcome:** Verified teachers and school operators can serve consented students/guardians through a clear, manually controllable classroom workflow with persistent outcomes and a complete sensitive-data lifecycle.
- **User story:** as a verified teacher, I can prove consent, prepare only permitted students, pass a preflight, run or disable recognition, correct attendance, end the session, share a report, and delete a student’s sensitive samples.
- **Current evidence:** classroom models/forms/views/templates; `_require_teacher_voice_access`; `_classroom_instructions` includes roster names; `classroom-voice-enroll.js`; `classroom-lesson.js`; no session/attendance/consent models; privacy child section is disabled.
- **Core flow:** teacher verification → organization/school and guardian consent → roster/minimal data → sample enrollment or opt-out → readiness preflight → session with manual controls → correction/end → saved attendance/outcomes/report → retention/deletion.
- **MVP:**
  - Verified teacher and organization ownership.
  - Versioned consent/authority record per student and processing purpose; recognition off by default without valid consent.
  - Individual photo and voice-sample list/delete; accurate storage/retention copy.
  - Friendly entitlement denial/upgrade and preflight for consent, roster, sample quality, browser, model, mic, camera, and AI budget.
  - `ClassroomSession`, attendance observation/correction, teacher notes/outcomes, end status, and basic export.
  - Manual roll call/call-on-student path that works without recognition.
- **Advanced scope:** assignments, student accounts, standards/competency reports, parent portal, school admin, roster import, safer on-device recognition packages, accuracy calibration by environment, and district deployment controls.
- **Code relationship:**
  - **Modules:** `models.py` classroom entities, `views_classroom.py`, classroom forms/templates, `classroom-lesson.js`, `classroom-voice-enroll.js`, Realtime token layer.
  - **Models:** organization/teacher membership, consent, sample metadata, classroom session, attendance observation/correction, learning outcome/report, AI usage link.
  - **APIs:** consent status, sample list/delete, preflight, session start/end, attendance correction/report/export.
  - **Jobs:** media/sample retention deletion, session reconciliation, report generation, consent expiry reminders, model-asset health checks.
  - **Analytics:** privacy-safe readiness/session/error/correction/report events; never raw names, embeddings, frames, photos, or audio.
- **Privacy, security, and AI cost:** this is the highest privacy-risk feature because it concerns likely minors and biometric-like data. Require verified authority, purpose limitation, opt-out, minimum data, strict object ownership/RBAC, encryption/access logs, retention/deletion, processor review, incident plan, and school contracts. Minimize roster names sent externally. Realtime AI cost is high; enforce teacher/class/session budgets and a kill switch. Recognition accuracy must not drive consequential decisions automatically.
- **Effort:** L/XL.
- **Business, retention, and conversion impact:** enables credible school adoption and recurring teacher value, but only if privacy/readiness/reporting are trustworthy. Persistent reports improve teacher retention; failed recognition or consent can severely damage trust.
- **Operations:** teacher/org onboarding, consent support, data-protection owner, media retention/deletion jobs, recognition calibration protocol, manual fallback, classroom incident and AI-cost runbooks.
- **KPI:** **Needs analytics data** — verified teachers, consent coverage, preflight pass, setup-to-start, session success, manual-fallback use, recognition correction, report completion, deletion SLA, privacy incidents, and cost/session.
- **Acceptance criteria:**
  1. Unverified teachers and students without valid consent cannot enter sensitive enrollment/recognition paths.
  2. Teachers can list and delete every stored photo and voice sample for an owned student.
  3. A session can run with recognition disabled and manual controls available.
  4. Preflight explains every failed requirement and never ends in a bare forbidden response.
  5. Attendance/outcomes are persisted, teacher-correctable, auditable, and exportable.
  6. End/navigation cleanup stops camera, microphone, recognition loops, and Realtime usage.
  7. Retention jobs and account/student deletion remove media and derived data as policy requires.
- **Dependencies:** `FEAT-003` verified teacher identity, `FEAT-001` entitlement, `FEAT-002` analytics, privacy/legal/school policy, private storage/retention jobs, and the AI usage ledger from `FEAT-007`.
- **Migration impact:** High—organization ownership, verified membership, consent, sample metadata, session/attendance/outcome/audit records, plus private-media relocation and retention backfill.
- **Deployment impact:** Default sensitive enrollment/recognition off; deploy consent/authorization and deletion first, then storage/jobs, manual sessions, preflight, and limited approved-school rollout.
- **Rollback notes:** Turn recognition/enrollment off and retain manual classroom/report access where authorized; keep private data protected, auditable, and deletable rather than reversing consent controls.
- **Documentation updates:** Update classroom architecture, school/guardian consent, processor/privacy disclosures, media retention/deletion, teacher training, accuracy limits, AI cost, support, and incident response.

## FEAT-009 — Kazakh-first localization and accessible component system

- **Status:** Proposed foundation and incremental migration.
- **Category:** Localization, accessibility, frontend architecture.
- **Horizon:** Immediate quick repairs followed by strategic completion.
- **Problem:** pages generally declare Kazakh but settings and UI strings are mixed; no localization framework is configured; Russian fixture content is inferred by IDs and hidden. Large standalone templates duplicate controls/styles. Zoom is disabled in auth/paywall pages; clickable `div`s, icon-only controls, non-semantic modals, missing live regions/focus handling, short timers, and unrestricted motion block inclusive use.
- **Target user and outcome:** Kazakh-first learners, intentionally supported Russian-preferring learners, assistive-technology users, and frontend/content teams share one localized accessible shell and component vocabulary without duplicated behavior.
- **User story:** as a Kazakh learner using any input or assistive technology, I can understand and operate every core flow consistently; as a Russian-preferring learner, I see only an intentionally localized supported path.
- **Current evidence:** `LANGUAGE_CODE='en-us'` with no language catalog/middleware; English labels in profile/classroom/PWA; Russian lessons in fixtures but no `Lesson.language`; standalone templates and duplicate auth base; accessibility evidence in catalog, lesson, guide, translator, quiz, and auth viewport markup.
- **Core flow:** determine locale/preference → render canonical shell/navigation/component strings → operate keyboard/touch/screen reader/zoom/reduced motion → preserve locale through auth/external handoff → render only compatible localized content.
- **MVP:**
  - Set and document Kazakh default; add translation infrastructure and terminology glossary.
  - Canonical base shell with navigation, skip link, main landmark, localized title/status/error patterns.
  - Shared form/error, button/link, tab, dialog, progress/status/live-region, loading/empty/error components.
  - Restore zoom; visible focus; replace clickable `div`s; accessible names; focus-managed dialogs; reduced-motion; non-timed quiz path.
  - Store content language/translation relationship before exposing Russian course selection.
  - CI automated accessibility checks plus manual test matrix.
- **Advanced scope:** full Russian UI/content parity, additional locale support, RTL readiness if needed, user font/contrast/motion preferences, accessibility statements, and continuous linguistic/assistive-technology QA.
- **Code relationship:**
  - **Modules:** settings middleware/languages, shared templates/static CSS/JS, all major templates, manifest/PWA strings, content models from FEAT-004.
  - **Models:** user locale preference and content language/translation group; avoid language-by-ID rules.
  - **APIs:** locale-aware errors/content responses; language preference endpoint if required.
  - **Jobs:** translation completeness/duplicate-string reports; no runtime AI translation.
  - **Analytics:** locale, untranslated/error markers, accessibility interaction failures, and task completion without collecting assistive-technology identity unless explicitly justified/consented.
- **Privacy, security, and AI cost:** self-host or review third-party fonts/assets; do not infer sensitive traits from accessibility preferences; keep translated security/error copy accurate. No AI cost is required. AI translation should not publish without human linguistic review.
- **Effort:** L product-wide; first keyboard/zoom/auth/catalog repairs are S/M.
- **Business, retention, and conversion impact:** improves comprehension, reach, legal posture, task completion, and delivery speed; reduces duplicated defects and supports measured locale expansion.
- **Operations:** glossary owner, linguistic reviewers, component governance, browser/assistive test matrix, accessibility defect SLA, and release checklist.
- **KPI:** **Needs analytics data** — mixed/untranslated strings, accessibility defects, keyboard task completion, zoom/reflow pass, locale-specific activation/completion, support contacts, and component adoption.
- **Acceptance criteria:**
  1. Kazakh is the documented default and core strings come from one localized source.
  2. Core visitor/auth/catalog/lesson/quiz/profile flows pass the agreed WCAG 2.2 AA manual and automated checklist.
  3. No core viewport disables zoom; content reflows at target zoom/width.
  4. Dialogs, tabs, forms, dynamic statuses, and icon controls expose correct semantics and focus behavior.
  5. Reduced-motion users receive no unnecessary infinite/large animation.
  6. Russian content selection relies on explicit metadata and has a reviewed completeness report before launch.
- **Dependencies:** explicit content language/translation fields from `FEAT-004`, approved terminology decisions, design tokens, browser/assistive QA capability, and privacy review of third-party assets.
- **Migration impact:** Likely additive user-locale preference and explicit content-language/translation metadata; no language inference from IDs is retained.
- **Deployment impact:** Establish glossary/i18n and shared primitives first, migrate critical flows incrementally, and gate Russian launch on reviewed UI/content completeness.
- **Rollback notes:** Revert an individual component/locale release if needed while retaining zoom, semantic-control fixes, explicit language metadata, and accurate security copy.
- **Documentation updates:** Maintain the terminology glossary, locale/content policy, component usage guide, accessibility standard/test matrix, translation QA, and release checklist.

## FEAT-010 — Offline daily plan and opt-in reminders

- **Status:** Proposed replacement for partial PWA scaffolding.
- **Category:** Mobile reliability, habit, retention.
- **Horizon:** Long-term after shared shell and content versioning; a small daily-plan card can ship earlier.
- **Problem:** PWA files are not integrated into active templates, precache references a missing asset, and cache behavior lacks authenticated-user/version/logout safety. Background sync/push are placeholders. There is no daily learning plan or reminder preference, despite a long sequential curriculum and mobile-first audience.
- **Target user and outcome:** Enrolled learners with intermittent connectivity get a safe localized daily resume/review plan and, only when they opt in, minimally revealing reminders.
- **User story:** as a learner with intermittent connectivity, I can choose a small daily goal, download authorized lesson/review material, continue offline, reconnect safely, and receive reminders only when I opt in.
- **Current evidence:** `static/manifest.json`, `static/sw.js`, `static/js/pwa-register.js`, and links in unused `base.html`; current templates do not extend that shell; service worker has placeholder sync/push and broad runtime caching behavior.
- **Core flow:** choose daily goal/reminder → install or continue in browser → select/download authorized pack → verify version/storage → study/review offline → queue safe progress → reconnect/conflict resolution → localized update/logout cache cleanup.
- **MVP:**
  - Daily plan/resume card based on current lesson and due review, with explicit reminder preference.
  - Register a corrected service worker from the canonical shell.
  - Cache only public shell and explicitly selected authorized, versioned text/assets; localized offline and update UI.
  - User-scoped cache naming/cleanup on logout/account switch; never cache tokens, chat, profile, orders/receipts, or classroom/biometric responses.
  - Idempotent offline progress queue for narrowly defined actions with visible sync/conflict state.
  - Install/reminder prompts shown contextually, not as competing floating controls.
- **Advanced scope:** selectable audio packs with quota controls, background sync, streak/calendar, adaptive daily workload, native push, low-bandwidth media variants, and teacher-assigned offline packs.
- **Code relationship:**
  - **Modules:** canonical base from FEAT-009, manifest/service worker/PWA JS, lesson/review APIs, profile/catalog daily plan.
  - **Models:** reminder preference, daily goal/completion, offline-pack manifest/version, sync idempotency record if server reconciliation requires it.
  - **APIs:** pack manifest/download authorization, daily plan, idempotent progress sync, reminder preference.
  - **Jobs:** opted-in reminder delivery, pack/version cleanup, sync monitoring; push infrastructure is currently only a placeholder.
  - **Analytics:** install prompt/outcome, pack download/failure, offline open/completion, sync/conflict, reminder opt-in/delivery/open, daily goal completion.
- **Privacy, security, and AI cost:** Cache API data is accessible to the origin and shared devices require strict user separation. Do not cache ephemeral secrets or sensitive/private flows; clear on logout; version/integrity-check assets; protect sync against replay; obtain notification consent and minimize content shown on lock screens. No AI cost is required.
- **Effort:** M for shell/daily plan and safe text caching; L for audio packs/push/conflict-rich sync.
- **Business, retention, and conversion impact:** improves reliability and daily return behavior, especially under mobile connectivity constraints; strengthens perceived app value and reduces failed-session abandonment.
- **Operations:** service-worker release/version rollback, cache incident procedure, notification sender/compliance, delivery monitoring, storage quota guidance, and offline support diagnostics.
- **KPI:** **Needs analytics data** — service-worker install success, install acceptance, pack success/failure, offline lesson/review completion, sync success/conflicts, reminder opt-in/open, daily-goal completion, and D7/D30 retention.
- **Acceptance criteria:**
  1. Active product templates register the versioned service worker from one canonical shell.
  2. Install succeeds with a complete existing asset list and provides a deterministic offline fallback.
  3. Automated two-account tests prove private user caches do not cross logout/account boundaries.
  4. Tokens, chat, payment/receipt, profile, and classroom/biometric responses are excluded from caches.
  5. Offline progress sync is idempotent, visible, and conflict-safe for the supported action set.
  6. Notifications are opt-in, localized, revocable, and contain no sensitive content.
- **Dependencies:** `FEAT-009` canonical shell/accessibility/localization, `FEAT-004` content versions, `FEAT-005`/`FEAT-006` progress/review contracts, `FEAT-002` analytics, and approved notification/retention policy.
- **Migration impact:** Optional reminder preference, daily-goal, pack-manifest, and sync-idempotency records; existing progress remains server-authoritative.
- **Deployment impact:** Version/unregister unsafe workers and clear old caches first, then stage the daily plan, explicit pack caching/sync, and consented reminder infrastructure.
- **Rollback notes:** Unregister the worker, delete product caches, pause reminders, and replay/retain acknowledged server progress; never restore broad authenticated-response caching.
- **Documentation updates:** Update offline/cache threat model, pack/version contract, notification consent, conflict/support guidance, service-worker release/rollback, analytics, and operations.

## Delivery horizons

### Quick wins and foundations

- A narrow FEAT-001 slice that approves offer/order/entitlement vocabulary, centralizes offer display, creates an order reference before external handoff, and agrees the minimal shared event contract.
- FEAT-002 full event schema, critical server events, retention controls, and baseline dashboards after that vocabulary is stable.
- FEAT-003 visible auth errors, safe phone normalization, resume action, and actionable lock/device state.
- FEAT-005 next-lesson action, real retry, consistent timer copy, and accessible feedback.
- FEAT-009 zoom restoration, native controls, accessible names/focus, and canonical form/error components.

### Strategic work

- FEAT-001 full order/payment/entitlement lifecycle.
- FEAT-004 versioned multilingual course CMS and QA.
- FEAT-006 personal spaced review.
- FEAT-007 corrected, measured, budgeted voice tutor.
- FEAT-009 complete shared shell/localization/accessibility migration.

### Long-term work

- FEAT-008 verified, consent-safe classroom with persistent reports.
- FEAT-010 safe offline packs, sync, and opt-in reminders.

## Sequencing constraints

1. Start with the FEAT-001 commercial vocabulary and narrow offer/order-reference slice while agreeing only the minimal event contract; do not wait for full analytics.
2. Deliver full FEAT-002 after that state vocabulary, and instrument before evaluating or scaling later conversion/retention changes and the remaining FEAT-001 lifecycle.
3. Approve the small language/terminology decision slice, then add FEAT-004 language/version metadata before the full FEAT-009 localization migration; neither full feature is the other’s prerequisite.
4. Complete the immediate safety/correctness gates in FEAT-007 and FEAT-008 before promoting AI voice/classroom use.
5. Add FEAT-004 content metadata/versioning before exposing localized parallel courses or durable offline packs.
6. Reuse FEAT-009 components in every later flow rather than building more standalone templates.
7. Treat KPI targets as unset until baselines exist: **Needs analytics data**.
