# OqyAI project context

Audit snapshot: 2026-07-10. Evidence labels in this document use `Confirmed`, `Inferred`, `Needs verification`, and `Needs product-owner confirmation`.

## Vision and audience

OqyAI is an English-learning platform primarily designed for Kazakh-speaking learners. The code and lesson copy target beginner through upper-intermediate study and emphasize Kazakh explanations, structured vocabulary/grammar/dialogue, quizzes, and AI-assisted speaking. `Confirmed / High` — `lessons/models.py`, `lessons/views.py`, lesson templates, and `lessons/fixtures/lessons.json`.

The intended minimum learner age appears to be 12 in prompts and old policy text, but the active product has no age gate or guardian-consent model. `Needs product-owner confirmation / High risk`.

## Current product state

| Capability | State | Evidence and caveat |
| --- | --- | --- |
| Account registration/login/logout/profile deletion | Implemented | Django auth plus `UserProfile`; no password reset, phone verification, or email flow |
| Student and teacher roles | Implemented but unsafe | Teacher is self-selected at public registration; task `SEC-010` |
| 250-lesson web catalog | Implemented | Five hard-coded 50-lesson slices; order and level depend on IDs |
| Additional Russian-localized lesson data | Data present, product incomplete | Fixture IDs 251–300; catalog currently renders only the first 250 queryset rows |
| Vocabulary/content/grammar/dialogue lesson view | Implemented | Server-rendered template; no explicit publish/version state |
| Vocabulary quiz and progression | Implemented | Database-backed idempotency tests exist; access policy and UX gaps remain |
| Stored AI explanations and MP3 audio | Implemented/admin-triggered | Partial fixture coverage; unsafe rendering and replacement lifecycle risks |
| Lesson chat and motivational AI | Implemented but unmetered | Public, synchronous, no quota/rate limit; output XSS risk |
| Premium Realtime voice lesson | Implemented transport; current behavior disputed | Pre-existing worktree change connects a social-content prompt instead of the lesson tutor; `Needs product-owner confirmation` |
| Realtime translator | Implemented | Separate entitlement; no explicit language selectors or usage ledger |
| Teacher classroom | Experimental/partially implemented | Groups, rosters, photos, voice embeddings, camera recognition, live Realtime; no persistent attendance/session outcomes or consent lifecycle |
| PWA | Partial/broken | Manifest/service worker exist; active templates do not consistently register them and precache references a missing asset |
| WhatsApp sales agent | Implemented but unsafe | Synchronous sales/replies, receipt OCR, Telegram alerts, and provisioning; critical tasks `SEC-001`–`SEC-004` |
| Payment/subscription system | Missing as a domain | No order/payment/transaction/expiring course entitlement; a receipt image can set a permanent Boolean |
| Product analytics | Missing | KPI baselines require analytics data |

## Confirmed roles

- Guest: views the catalog and free lesson pages; quiz identity uses a session key.
- Student: authenticated learner with optional course, voice, and translator access.
- Teacher: authenticated profile role that can manage owned classroom data; currently self-provisioned.
- Staff/superuser: Django admin; superuser can generate lesson explanations.
- WhatsApp lead/customer: separate phone-based record, not a verified Django identity or foreign key.
- Product/operations administrator: inferred from Django admin actions and Telegram alerts; formal ownership is not documented.

There is no confirmed parent role, content-editor role, finance reviewer role, or support role. `Needs product-owner confirmation`.

## Primary user flows

### Learner

1. Visitor lands directly on the lesson catalog, not a dedicated marketing/onboarding page.
2. Visitor can open free lessons or register with username, Kazakhstan phone, role, and password.
3. Registration creates `User` and `UserProfile`, logs the user in, and sends registration PII to configured Telegram operations.
4. Learner opens lesson sections, optional stored explanations/audio, chat, and a timed vocabulary quiz.
5. Passing all lesson questions with fewer than three mistakes records the pass and unlocks the next numeric lesson.
6. Premium lesson access is a permanent `is_paid` flag; voice and translator use separate flags/expiry timestamps.
7. Upgrade CTAs lead to WhatsApp or an advertisement page.

There is no explicit onboarding completion, placement test, daily plan, saved vocabulary review, mistake history UI, or retention loop. `Confirmed missing / High`.

### Teacher/classroom

1. A user registers as teacher or is assigned that role.
2. Teacher creates owned groups and students, uploads photos, and stores browser-derived voice embeddings.
3. With active voice access, teacher selects any lesson and launches a camera/microphone Realtime session.
4. Browser code performs face/hand/voice matching and sends control events to the AI teacher.

Classroom session results and attendance are not persisted. Consent, guardian authorization, biometric deletion, and opt-out rules are missing. Treat classroom as experimental.

### WhatsApp sale/payment

1. Meta posts an inbound webhook.
2. Django stores the lead/message/raw payload and handles intent synchronously.
3. Text can call OpenAI for a sales reply; receipt media is downloaded and OCR/PDF text is analyzed.
4. Current high-confidence OCR can immediately set/create permanent course access and send credentials.

This flow is not safe as payment proof. `SEC-001` is the required next implementation task.

## Monetization and commercial truth

- Course, voice, and translator are separately provisioned in `UserProfile`.
- Web UI advertises one course price while WhatsApp/configured receipt validation uses another. `Confirmed defect / High`; the correct price is `Needs product-owner confirmation`.
- Copy promises one-year course access, but course access has no start or expiry. `Confirmed defect / High`.
- Voice and translator durations exist but pricing/packaging rules are not modeled. `Needs product-owner confirmation`.
- There is no payment provider verification, transaction identifier, refund state, invoice, order history, or entitlement audit ledger.

## Architecture summary

OqyAI is a server-rendered Django monolith with two first-party apps. `lessons` is the dominant app and owns content, quiz, access, AI, profile, and classroom domains. `whatsapp_agent` owns messaging/OCR records but directly mutates `lessons.UserProfile`, so the boundary is coupled. External OpenAI, Meta, and Telegram calls happen synchronously in web requests. Local filesystem media is used. See [docs/ARCHITECTURE_AND_CODEBASE.md](docs/ARCHITECTURE_AND_CODEBASE.md).

## Domain terminology

- Lesson: one authored record with title, content, vocabulary, grammar, and dialogue.
- Explanation: generated text/audio for one lesson section.
- Quiz question: one English word and Kazakh translation, often derived from vocabulary lines.
- Quiz attempt/answer: server-authoritative progress for a user ID or guest session.
- Course access: current permanent `UserProfile.is_paid` flag; not a real subscription.
- Voice/translator access: separate feature flags with optional expiry.
- Classroom: teacher-owned group/student/biometric runtime, currently experimental.
- WhatsApp lead: phone-keyed sales record; not verified account ownership.
- Receipt validation: current OCR heuristic; not a bank/payment confirmation.

## Deployment summary

- `Procfile` declares synchronous Gunicorn over WSGI.
- SQLite is the default; optional MySQL is selected by environment.
- Static source is collected for WhiteNoise; media persistence and private serving are not solved for multi-instance/ephemeral hosting.
- The audited environment used Python 3.10.12 and Django 5.1.6. Django 5.1 is unsupported and 5.1.6 predates security fixes.
- No CI, worker queue, health endpoint, error tracker, backup automation, or restore drill is present.
- Deployment ownership/topology is `Needs product-owner/operations confirmation`.

## Highest risks and immediate priorities

1. `SEC-001`: fail closed on OCR receipts; require manual approval until verified payment exists.
2. `SEC-002`: authenticate Meta webhook POSTs.
3. `SEC-003`: remove recipient mutation/sandbox fallback from production replies.
4. `SEC-004`: eliminate reusable plaintext password delivery and persistence.
5. `SEC-005`: rotate exposed credentials and sanitize current tracked material before history cleanup.
6. Resolve commercial price/duration truth (`BUG-001`, `DATA-002`).
7. Fix AI output XSS and public AI abuse controls (`SEC-006`, `SEC-011`).
8. Establish privacy controls for classroom/receipts/media (`SEC-007`, `SEC-010`, `SEC-012`).
9. Upgrade supported framework/runtime and reproduce dependencies (`DEVOPS-001`, `DEVOPS-002`).
10. Add tests around these boundaries before architectural cleanup.

## Product-owner decisions required

- What is the canonical course price, currency, duration, refund policy, and source of truth?
- Must every payment be manually approved, or will a verifiable payment-provider integration be introduced?
- Is teacher registration open, invitation-only, school-admin-approved, or staff-approved?
- Is the current social-content voice prompt intentional, and should it be a separate creator-only feature?
- Are IDs 251–300 an active Russian course, preview content, or historical data?
- What age floor and guardian/biometric-consent policy apply to classroom learners?
- Which data must be retained, where, and for how long across chat, audio, photos, embeddings, receipts, raw webhooks, and Telegram?
- What is the actual production host/database/media/backup topology and who owns incidents?
- Which voice/translator packages and usage caps are sold?

## Sources of truth

- [Documentation index](docs/INDEX.md)
- [Architecture and codebase map](docs/ARCHITECTURE_AND_CODEBASE.md)
- [Security audit](docs/SECURITY_AUDIT.md)
- [Technical audit](docs/TECHNICAL_AUDIT.md)
- [AI integrations](docs/AI_INTEGRATIONS.md)
- [Content operations](docs/CONTENT_OPERATIONS.md)
- [UX/UI audit](docs/UX_UI_AUDIT.md)
- [Feature roadmap](docs/FEATURE_ROADMAP.md)
- [Unified backlog](docs/BACKLOG.md)
- [Phased implementation plan](docs/IMPLEMENTATION_PLAN.md)
