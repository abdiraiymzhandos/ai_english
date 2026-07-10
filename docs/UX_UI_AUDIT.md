# OqyAI UX/UI Audit

## Document status

- **Purpose:** evidence-based UX/UI source of truth for the current Django product.
- **Review type:** static repository inspection only.
- **Audience:** product, design, engineering, operations, QA, and future AI coding agents.
- **Last reviewed:** 2026-07-10.
- **Change scope:** this document records findings and recommendations; it does not claim that any recommendation is implemented.

## Scope and limitations

The review covered the student and teacher-facing Django templates, inline and static CSS, browser JavaScript, route/view relationships, forms, educational fixtures, content admin, profile/access presentation, Realtime voice and translator interfaces, classroom enrollment/session interfaces, privacy copy, WhatsApp-assisted purchase flow, and PWA files.

This was not a browser or production review. No page was rendered at mobile, tablet, or desktop widths; no screen reader, keyboard-only walkthrough, color-contrast scanner, browser accessibility tree, network throttling, camera, microphone, payment channel, OpenAI session, service worker, or external messaging integration was exercised. Runtime database contents can differ from the fixture snapshots. Responsive, accessibility, loading-state, and interaction findings are therefore source-based and must be validated in a browser. Code presence is not proof that an external service is configured or production-ready.

No product analytics integration was found. Fixture attempts, leads, profiles, and devices are operational snapshots, not trustworthy funnel analytics. Every KPI baseline and target in this document therefore **Needs analytics data**.

## Current Kazakh learner journey

### 1. Visitor and consideration

A visitor lands directly on the course catalog rather than a dedicated value-led landing page. `lessons.views.lesson_list` renders five hard-coded 50-lesson stages, a manually opened course guide, registration/login controls, a motivation action, and a floating translator action. The visitor can enter the first course lesson and progress through free access, but catalog cards do not clearly distinguish completed, current, free, or premium states.

### 2. Registration and activation

Registration asks for username, phone, role, and password, then logs the user in and returns them to the catalog (`lessons/forms.py::CustomRegisterForm`; `lessons/views.py::register`). The user self-selects student or teacher. There is no explicit privacy/terms acknowledgement, account verification, placement/goal selection, role-specific welcome, or automatic resume/start instruction.

### 3. Learning loop

Each lesson presents vocabulary, content, grammar, and dialogue tabs, optional stored explanations/audio, a general GPT chat, an optional premium voice interface, and a timed vocabulary quiz (`lessons/templates/lessons/lesson_detail.html`). Passing the quiz unlocks the next lesson in backend/session state. The completion interface does not use the returned next-lesson ID, and its retry action cannot restart an already-passed attempt.

### 4. Purchase and access

Non-free access redirects to `advertisement.html`, then hands the learner to an external WhatsApp-assisted payment and receipt flow. The public offer, guide, configured commercial settings, and WhatsApp sales/receipt logic do not share one source of truth. There is no in-app order, pending review, rejected receipt, refund, or paid-until state. Course access is represented by `UserProfile.is_paid`, an indefinite Boolean.

### 5. Paid use and retention

The profile exposes separate course, voice, translator, and teacher/classroom access cards, but mixes English and Kazakh labels and does not make the current lesson a direct resume destination. The catalog is collapsed by stage, lacks lesson search and completed/current markers, and the quiz completion state has no effective continuation action. There is no personal review queue, daily plan, reminder preference, or verified offline flow.

### 6. Teacher branch

A self-declared teacher can open classroom management, create groups and students, upload photos, record voice embeddings, and prepare a live Realtime/camera recognition session. Teachers without voice access can still see session-start actions, which lead to a plain forbidden response. Readiness is described as demo readiness; consent, individual biometric deletion, persistent attendance/session reports, and manual recognition correction are absent.

## Issue summary

Severity follows the canonical backlog mapping: **P0 Critical**, **P1 High**, **P2 Medium**, and **P3 Low**. UX-001 through UX-005 use their canonical backlog task severity. For the remaining audit findings, the severity reflects the UX workstream; the related blocker column preserves higher security, privacy, commercial, or architecture criticality without creating duplicate tasks. Complexity estimates are relative: **S** is a focused change, **M** spans a flow or shared component, and **L** requires cross-cutting data/product work.

| ID | Severity | Related canonical blocker | Affected flow | Source evidence | Confirmed issue | Complexity |
| --- | --- | --- | --- | --- | --- | --- |
| UX-001 | P2 Medium | `BUG-001` P1 | Visitor, paywall, purchase | Confirmed / High | Offer/value/price/access-duration and CTA behavior do not share one commercial source of truth. | L |
| UX-002 | P2 Medium | `SEC-010` P1 | Registration, first session, return visit | Confirmed / High | Activation is not role-aware and neither student nor teacher receives a reliable resume/next action. | M |
| UX-003 | P2 Medium | `BUG-004` P2 | Lesson quiz, progression | Confirmed / High | Quiz completion ignores `next_lesson`; retry reloads an already-passed state; the timed reset model is punitive. | M |
| UX-004 | P2 Medium | `TEST-003` P2 | All interactive flows | Confirmed / High; browser effects: Needs verification | Keyboard, zoom, modal semantics, live feedback, time limits, and reduced-motion support are incomplete. | L |
| UX-005 | P2 Medium | `BUG-005` P2; `SEC-004` P1 | Login, registration, recovery | Confirmed / High | Invalid-login feedback and password recovery are absent; phone normalization mishandles a common local input form. | M |
| UX-006 | P2 Medium | — | All templates | Confirmed / High; rendered effects: Needs verification | Large standalone templates and duplicated design rules create inconsistent navigation, forms, status, and responsive behavior. | L |
| UX-007 | P1 High | `SEC-010`, `SEC-012` P1 | Registration, AI, payment, classroom | Confirmed / High; policy: Needs product-owner confirmation | Consent and privacy copy do not cover implemented AI, receipt, classroom, and minors/biometric processing. | L |
| UX-008 | P2 Medium | `ARCH-001` P1; `DATA-004` P2 | Catalog, progress, resume | Confirmed / High; rendered effects: Needs verification | Catalog states can appear unlocked before redirecting to a paywall and do not identify completed/current/premium lessons. | M |
| UX-009 | P1 High | `BUG-002`, `AI-002` P1 | Lesson explanations, chat, voice | Confirmed / High; live AI effects: Needs verification | Empty, retry, timeout, consent, and recovery states are incomplete; the premium voice prompt is not lesson-grounded. | M |
| UX-010 | P1 High | `SEC-010` P1 | Teacher/classroom | Confirmed / High; device behavior: Needs verification | Readiness actions can lead to a plain denial; readiness thresholds, consent, deletion, and saved outcomes are incomplete. | L |
| UX-011 | P2 Medium | `DATA-004` P2 | Kazakh/Russian experience | Confirmed / High; comprehension: Needs verification | UI language is mixed, Django defaults to `en-us`, and the Russian fixture track has no product-level language model/navigation. | L |
| UX-012 | P1 High | `SEC-008` P1 | Install, offline, retention | Confirmed / High; runtime caching: Needs verification | PWA assets exist but are not integrated into active templates; current precache and private-data rules are unsafe/incomplete. | M |

## Detailed findings

### UX-001 — Rebuild the landing/paywall hierarchy around approved commercial truth

- **Affected flow:** visitor consideration → free lesson → paywall → external purchase → paid access.
- **Evidence status/confidence:** **Confirmed / High** for conflicting tracked offer values, missing order states, and Boolean entitlement. Approved price, duration, offer wording, and purchase policy: **Needs product-owner confirmation**. Browser and conversion effects: **Needs verification**.
- **Problem and evidence:** the catalog is the landing page (`lessons/urls.py`, root route to `lesson_list`) and provides a guide rather than a concise outcome/proof/plan comparison. The public advertisement supplies one offer in `lessons/views.py::advertisement`; `includes/guide-modal.html` presents additional plan and monthly/yearly wording; the WhatsApp sales prompt, receipt validator, and `COURSE_PRICE_KZT` use a different commercial value (`whatsapp_agent/services.py::_build_payment_reply`, `_build_sales_system_prompt`, and `evaluate_receipt`; `english_course/settings.py`). The external CTA has no in-app order context, pending state, receipt state, expiry, or recovery. `UserProfile.has_paid_lesson_access()` returns only `bool(self.is_paid)`.
- **User impact:** a Kazakh learner can receive contradictory pricing/plan information, leave the product without a durable purchase reference, submit a receipt for the amount shown on the web and fail automated validation, or be unable to tell when access starts or ends.
- **Business impact:** reduced trust and conversion, preventable manual support, receipt escalations, incorrect lifetime access, and inability to measure or reconcile revenue entitlements.
- **Recommendation:** establish a single offer catalog consumed by web copy, profile cards, WhatsApp prompts, receipt validation, and operations. Keep the first MVP compatible with the existing external transfer flow, but create an order/reference before handoff and render pending, confirmed, needs-review, rejected, refunded, and expiry states. Replace reusable password delivery with a one-time account setup path.
- **Complexity:** L.
- **KPI:** **Needs analytics data** — paywall-to-CTA rate, CTA-to-payment-intent rate, receipt validation rate, median receipt-to-access time, manual escalation rate, price-mismatch incidents, and refund/support rate.
- **Validation method:** automated tests proving every channel reads the same offer; end-to-end sandbox purchase cases for new/existing/duplicate-phone users; content review in Kazakh; operations reconciliation; browser verification of all order states.

### UX-002 — Add role-aware activation and resume journeys

- **Affected flow:** registration → first useful action; returning learner/teacher → resume.
- **Evidence status/confidence:** **Confirmed / High** for the shared redirect, self-selected role, missing onboarding state, and current profile/catalog links. Activation and discovery effects: **Needs verification** in a browser and analytics. Teacher approval and onboarding policy: **Needs product-owner confirmation**.
- **Problem and evidence:** `CustomRegisterForm` lets a user select student or teacher, and `register()` saves the role, logs in, and redirects both roles to `lesson_list`. A teacher is authorized whenever `UserProfile.is_teacher()` is true (`models.py::can_use_classroom_teacher_features`; `views_classroom.py::_require_teacher`). Students receive no goal/level/start checkpoint. Teachers receive no verified role step or first-class setup. Profile summary shows `current_lesson`, but quick lessons route to the catalog rather than that lesson (`profile.html`; `views.py::profile`).
- **User impact:** first-time users must infer the next action; a returning learner must reopen stages to find progress; a teacher must discover classroom through profile; an unverified self-declared role reaches sensitive classroom tooling.
- **Business impact:** weaker activation and retention, avoidable role confusion, increased support, and unsafe access expansion.
- **Recommendation:** add a short role-aware activation flow. Student MVP: confirm language, learning goal, optional level/start point, and a direct “start/resume lesson” action. Teacher MVP: verified/approved teacher state, school/class setup checklist, and a clear voice-access requirement. Preserve intended destinations through login and surface resume on catalog/profile.
- **Complexity:** M, with teacher verification policy potentially L.
- **KPI:** **Needs analytics data** — registration completion, first lesson started within ten minutes, first quiz completion, teacher verification completion, first class created, return-to-resume rate, and D1/D7 retention.
- **Validation method:** role-specific usability tests in Kazakh, authorization tests, new/returning session browser tests, and funnel event verification.

### UX-003 — Deliver mastery-oriented quiz review and continuation

- **Affected flow:** lesson study → quiz → feedback → next lesson/review.
- **Evidence status/confidence:** **Confirmed / High** for the unused `next_lesson`, passed-attempt reload, timer mismatch, and reset behavior. Accessibility and learning effects: **Needs verification** with learners and browsers. Approved retake/mastery policy: **Needs product-owner confirmation**.
- **Problem and evidence:** `submit_answer()` returns `next_lesson`, but the browser does not consume it. `showQuizComplete()` offers only a reload-based retry (`lesson_detail.html`). On reload, `start_quiz()` reports the attempt as passed, and the UI immediately returns to completion, so retry is ineffective. The UI allows five seconds per question, resets all answers after three mistakes, and provides only brief color/button feedback without a mistake review or explanation. The initial static timer text says four seconds while the running logic and rules say five.
- **User impact:** a successful learner reaches a dead end; a learner who wants reinforcement cannot retry; time pressure and full reset can penalize reading speed, anxiety, motor, or cognitive differences rather than mastery.
- **Business impact:** lower next-lesson continuation, weaker learning credibility, reduced retention, and unusable retry analytics.
- **Recommendation:** render a completion summary with “next lesson,” “review mistakes,” and a true new attempt. Use an untimed or generous default with an optional challenge timer, preserve progress across errors, and show the correct answer plus a short explanation. Model attempts separately if historical retries must be retained.
- **Complexity:** M.
- **KPI:** **Needs analytics data** — quiz start/completion, first-pass rate, review use, retry success, time per question, abandonment, and next-lesson continuation.
- **Validation method:** backend attempt-state tests; browser tests for pass/fail/retry/reload; keyboard and screen-reader quiz walkthrough; timed/untimed usability study.

### UX-004 — Establish the accessibility baseline and shared semantic patterns

- **Affected flow:** authentication, catalog, lessons, chat, guide, translator, quiz, voice, and classroom.
- **Evidence status/confidence:** **Confirmed / High** for the source-level semantics, viewport restrictions, missing attributes, timer, and motion rules. Actual keyboard, screen-reader, focus, reflow, contrast, and reduced-motion behavior: **Needs verification** in supported browsers and assistive technologies.
- **Problem and evidence:** `auth_base.html` and `advertisement.html` disable page zoom with `maximum-scale=1`/`user-scalable=no`. Catalog `.stage-card` is a click-only `div` (`lesson_list.html`); lesson `.explanation-toggle` is a click-only `div`; guide step dots are click-only `div`s. Theme, chat-open, chat-close, translator-close, and send icon controls lack reliable accessible names. Guide, translator, voice-enrollment, and chat surfaces do not implement dialog semantics, focus entry/trap/return, or consistent Escape handling. Dynamic status/conversation/quiz updates lack `aria-live`; progress bars lack values/names. The quiz enforces a short timer. CSS contains extensive motion and infinite animation without `prefers-reduced-motion` handling.
- **User impact:** keyboard, switch, low-vision, screen-reader, motion-sensitive, and slower-processing users may be unable to discover, operate, or complete core flows.
- **Business impact:** lost learners, support burden, legal/reputational risk, and unreliable education outcomes.
- **Recommendation:** restore zoom; use native buttons/links; implement semantic tablists/dialogs/progress/status; provide visible focus, accessible names, focus management, live announcements, reduced motion, and non-timed accommodation. Create a reusable accessibility checklist and CI/browser audit rather than isolated patches.
- **Complexity:** L across the product; several immediate repairs are S.
- **KPI:** **Needs analytics data** — keyboard-only task completion, accessibility defect count by severity, zoom/reflow pass rate, timed-quiz abandonment, and assistive-technology support incidents.
- **Validation method:** WCAG 2.2 AA review; automated axe/lighthouse checks; manual keyboard, 200%/400% zoom and reflow; VoiceOver/NVDA walkthroughs; reduced-motion and high-contrast testing.

### UX-005 — Add account recovery, consent, and actionable auth states

- **Affected flow:** register → login → recover → return to intended page.
- **Evidence status/confidence:** **Confirmed / High** for missing rendered errors/recovery routes, client/server phone handling, non-unique phones, and duplicate-match failure. Mobile input effects and common user-entry behavior: **Needs verification**. Recovery channel and phone-ownership policy: **Needs product-owner confirmation**.
- **Problem and evidence:** `login.html` renders username/password but not `form.errors`, non-field errors, or messages. `lessons/urls.py` has no password-reset flow. Registration renders only the first field error and no non-field errors. Phone validation requires one exact international pattern; the input script prepends the country digit when input does not start with it, so a commonly entered domestic prefix can be transformed incorrectly (`register.html`; `forms.py`). The phone field is not unique, while WhatsApp provisioning fails when multiple profiles share it (`whatsapp_agent/services.py::_get_existing_profile_by_phone`).
- **User impact:** invalid login appears to do nothing, lost credentials have no self-service recovery, and correct local phone habits can produce invalid data or duplicate-account purchase issues.
- **Business impact:** registration/login abandonment, manual account support, failed payment linking, and duplicate identities.
- **Recommendation:** show safe localized auth errors, preserve `next`, add phone/email recovery or OTP, normalize accepted local formats server-side, use `type="tel"`/`inputmode="tel"`/autocomplete, define phone ownership/uniqueness rules, and show non-field errors. Add password reveal and clear requirements without weakening validation.
- **Complexity:** M.
- **KPI:** **Needs analytics data** — registration validation failure by field, login failure/recovery success, duplicate-phone rate, time to recover, and intended-destination completion.
- **Validation method:** form unit tests for local/international inputs; duplicate/concurrent registration tests; browser login-error/recovery tests; usability testing with Kazakh phone-entry conventions.

### UX-006 — Reusable component and template system

- **Affected flow:** every rendered page and future frontend change.
- **Evidence status/confidence:** **Confirmed / High** for standalone templates, duplicated files/rules, inline assets, and missing shared-shell use. Resulting visual, responsive, focus, and navigation inconsistencies: **Needs verification** in rendered pages.
- **Problem and evidence:** core templates are standalone and large: `lesson_detail.html`, `classroom/session.html`, `lesson_list.html`, and `profile.html` each embed substantial CSS/JS. `lessons/auth_base.html` exists identically both outside and inside the template directory. Most pages do not share `base.html`; navigation, forms, buttons, modals, statuses, breakpoints, and language vary. Some plain CSS contains unsupported SCSS-style `@extend`. The same lesson-tab/highlight/theme patterns are duplicated between student and classroom templates.
- **User impact:** inconsistent navigation, language, error behavior, focus, responsive layout, and visual hierarchy.
- **Business impact:** slower delivery, regression risk, duplicated fixes, and higher accessibility/localization cost.
- **Recommendation:** introduce a canonical application shell and small template components for navigation, forms/errors, buttons, access badges, empty/error/loading states, dialogs, tabs, and progress. Move page styles/scripts into versioned static assets and share lesson behavior through one tested module. Migrate incrementally, starting with authentication and catalog.
- **Complexity:** L.
- **KPI:** **Needs analytics data** — frontend defect/regression rate, duplicated selector/template count, time to ship a shared UI change, page-weight change, and component accessibility pass rate.
- **Validation method:** template snapshot/browser tests, visual regression at target breakpoints, duplicate-code/static analysis, and incremental page parity review.

### UX-007 — Privacy and consent disclosures

- **Affected flow:** registration, AI chat/voice/translator, WhatsApp receipt processing, classroom photo/voice/camera, account deletion.
- **Evidence status/confidence:** **Confirmed / High** for the tracked processing, absent consent fields/routes, stale policy text, and mismatched deletion claims. Applicable legal duties and approved age, guardian, consent, retention, and processor policy: **Needs product-owner confirmation** with legal/privacy review. User comprehension: **Needs verification**.
- **Problem and evidence:** registration has no policy acknowledgement. `privacy_policy.html` is dated January 2025, describes an unsupported language offering, omits implemented WhatsApp/Meta messages, receipt files/OCR text, Telegram escalation, classroom photos, voice embeddings, face/hand recognition, attendance, and student-name disclosure to OpenAI. Its children section is commented out. It describes profile editing that the UI does not offer and WhatsApp-request deletion despite direct profile deletion. Classroom student copy says photos are local and deletable at any time, but `StudentPhoto.image` is server-side and no individual delete route exists.
- **User impact:** learners, parents, students, and schools cannot make an informed choice or exercise the promised controls.
- **Business impact:** critical trust, legal, school adoption, and incident-response risk.
- **Recommendation:** complete a legal/privacy data-flow review; publish accurate Kazakh-first notices; add versioned acceptance where required; add just-in-time AI/mic/camera/biometric notices; model guardian/school consent and opt-out; expose individual photo/voice/session deletion and data export; define retention and processors. Do not enable classroom recognition until required consent is recorded.
- **Complexity:** L and policy-dependent.
- **KPI:** **Needs analytics data** — current-policy acceptance, classroom consent coverage, opt-out completion, deletion/export SLA, unconsented processing incidents, and privacy support volume.
- **Validation method:** data inventory and processor review, legal sign-off, consent-state authorization tests, deletion/export tests including stored media, and school/parent comprehension testing.

### UX-008 — Catalog state, search, and current lesson

- **Affected flow:** catalog discovery → resume → locked/paywalled lesson.
- **Evidence status/confidence:** **Confirmed / High** for independently derived access state, template links, missing row states/search, hard-coded stages, and omitted fixture track. Rendered redirect experience and learner comprehension: **Needs verification**. Approved curriculum/access display rules: **Needs product-owner confirmation**.
- **Problem and evidence:** `lesson_list()` calculates sequential unlocked IDs independently from paid entitlement, while `lesson_detail()` redirects unpaid non-free access to advertisement. The template renders unlocked IDs as ordinary lesson links, so a lesson may appear available before redirect. Individual rows do not distinguish passed/current/next/free/premium. Stages are click-to-expand, initially collapsed, and do not auto-open the current stage. There is no lesson search/filter. Five stages and 50-lesson slices are hard-coded; the Russian fixture track is excluded.
- **User impact:** learners cannot confidently identify what they completed, what to do next, or why a visible lesson redirected. Long catalogs impose avoidable navigation work.
- **Business impact:** lower resume and conversion success, misleading paywall encounters, and weak progress comprehension.
- **Recommendation:** derive one catalog access-state object on the server for every lesson: completed, current, available free, available paid, premium locked, prerequisite locked. Auto-open/scroll to current, add resume and search, display explicit lock reasons/CTA, and preserve the chosen lesson through purchase/login.
- **Complexity:** M.
- **KPI:** **Needs analytics data** — resume click-through, catalog-to-lesson time, locked-row click-to-purchase, unexpected redirect rate, search usage/success, and next-lesson start.
- **Validation method:** access matrix tests for guest/free/paid/teacher roles; sequential progress browser tests; usability test locating current and named lessons; responsive/keyboard catalog review.

### UX-009 — Lesson, chat, and voice loading/error/empty states

- **Affected flow:** open lesson → switch section → request help → start/stop voice.
- **Evidence status/confidence:** **Confirmed / High** for template states, endpoint access, client timeout/control omissions, fixture coverage, and the current-tree prompt selection. Actual API, microphone, network, generated-output, and learner experience: **Needs verification**. Approved voice persona and usage policy: **Needs product-owner confirmation**.
- **Problem and evidence:** explanation toggles render unconditionally even when the context has no explanation, producing blank panels. The fixture snapshot has explanations for only a minority of lessons. Chat has text loading/error output but no retry, cancel, clear/history, rate/usage, disclosure, or accessible live announcements. `chat_with_gpt()` is not access-scoped in the endpoint. The premium voice UI exposes connection/error statuses and a 30-minute client timeout, but no consent/preflight, mute/pause, recovery instructions, learning summary, or server-visible usage meter. Most importantly, `mint_realtime_token()` selects `_content_creator_instructions`, a static social-video joke prompt, instead of the lesson-grounded `_teacher_instructions(lesson)`.
- **User impact:** empty help appears broken; AI failures are hard to recover from; microphone/data use is unclear; paid voice can teach unrelated content.
- **Business impact:** premium dissatisfaction, AI cost without learning value, support load, and weak trust.
- **Recommendation:** conditionally render explanations with “not yet available”; standardize skeleton/loading/retry/empty/error components; add accessible chat lifecycle controls and server rate limits; fix voice grounding before promotion; add mic test, explicit consent, stop/pause, retry, server-enforced usage budget, and a short lesson summary.
- **Complexity:** M, with content completion potentially L.
- **KPI:** **Needs analytics data** — explanation availability, chat success/error/retry, voice start success, disconnect rate, completed minutes, cost per completed session, learner usefulness, and off-lesson response defects.
- **Validation method:** fixture/runtime coverage report; forced API/network/mic-denial tests; prompt grounding evaluation against lesson fixtures; cost/concurrency tests; assistive-technology status announcement review.

### UX-010 — Classroom readiness and friendly denials

- **Affected flow:** teacher dashboard → prepare roster → select session → AI/camera/recognition → end/report.
- **Evidence status/confidence:** **Confirmed / High** for CTA/403 behavior, readiness calculation, self-selected teacher role, and absent persistence/consent/deletion models. Camera, microphone, model loading, recognition accuracy, and live cleanup: **Needs verification**. Teacher eligibility and biometric/guardian policy: **Needs product-owner confirmation**.
- **Problem and evidence:** dashboard and group pages provide useful empty/readiness states, but “start session” actions are shown even when `_require_teacher_voice_access()` will return a plain English 403. Readiness counts any one photo and any one voice sample as ready (`views_classroom.py::_serialize_group_summary`) while guidance recommends several samples. Any public registrant can self-assign teacher. There is no consent state, individual photo/voice deletion, saved `ClassroomSession`/attendance/outcome model, manual correction, or end-session report. Recognition status is mostly transient DOM/OpenAI event state.
- **User impact:** teachers encounter unexplained denial, cannot trust readiness labels, cannot correct or retain attendance/outcomes, and cannot demonstrate consent/deletion to schools or parents.
- **Business impact:** failed demos/classes, high setup/support cost, school/privacy risk, and no evidence of classroom learning value.
- **Recommendation:** gate and explain access before showing session CTAs; provide a preflight checklist for voice entitlement, consent, roster, samples, browser, mic, camera, and model readiness; define enforceable sample-quality thresholds; persist a session record and teacher-correctable attendance/outcomes; add explicit end/cleanup/report flows.
- **Complexity:** L.
- **KPI:** **Needs analytics data** — setup-to-start time, friendly-denial conversion, preflight pass rate, session-start success, recognition correction rate, consent coverage, report completion, and AI cost/session.
- **Validation method:** role/entitlement matrix tests; camera/mic/model failure simulation; school privacy acceptance; real classroom pilot with manual ground truth; navigation/pagehide cleanup test.

### UX-011 — Localization consistency

- **Affected flow:** all Kazakh UI; optional Russian learner journey.
- **Evidence status/confidence:** **Confirmed / High** for mixed tracked strings, Django locale configuration, absent translation infrastructure, and fixture/catalog modeling. Learner comprehension and locale-specific behavior: **Needs verification**. Supported-language offering, terminology, and Russian-track scope: **Needs product-owner confirmation**.
- **Problem and evidence:** templates generally declare `lang="kk"`, but Django `LANGUAGE_CODE` is `en-us` and no `LANGUAGES`, `LocaleMiddleware`, translation tags, or message catalogs are present. Profile uses Account, Access, Active, Buy, Lessons, Voice, Translator, and Danger Zone. Classroom includes Mic, fast/precise, live session, and demo terminology. PWA status/install copy is English. Fixtures contain a 50-lesson Russian-localized parallel course, but `Lesson` has no language field and the catalog intentionally slices only IDs 1–250. Privacy copy refers to a different language offering.
- **User impact:** mixed terminology raises comprehension cost for beginner Kazakh learners; Russian content is not reliably discoverable or selectable.
- **Business impact:** weaker trust, harder support/content operations, duplicated templates, and inability to compare language-specific activation.
- **Recommendation:** make Kazakh the explicit default product locale, centralize strings, standardize a terminology glossary, and add a stored language preference. Add language/translation-group metadata to content before exposing Russian lessons; do not infer language from ID ranges. Localize dates, errors, PWA, accessibility names, and external handoff copy together.
- **Complexity:** L.
- **KPI:** **Needs analytics data** — untranslated/mixed-string count, locale selection, language-specific registration and lesson completion, language-switch errors, and comprehension-task success.
- **Validation method:** Kazakh linguistic QA, terminology review with teachers, automated template string scan, locale browser tests, and Russian content-pair integrity tests.

### UX-012 — PWA and offline safety

- **Affected flow:** install → reopen → offline lesson → reconnect/logout/update.
- **Evidence status/confidence:** **Confirmed / High** for inactive shell integration, missing precache asset, cache strategy, and placeholder handlers. Service-worker install/activation, private-response cache effects, quota, updates, and shared-device behavior: **Needs verification** in supported browsers. Intended offline scope and retention policy: **Needs product-owner confirmation**.
- **Problem and evidence:** manifest/service-worker registration is linked only from `base.html`, but active templates are standalone or extend `auth_base.html`; repository search found no template extending `lessons/base.html`. `sw.js` precaches a missing image and uses `cache.addAll`, so the app shell can fail atomically. Runtime caching does not define authenticated/private-page, logout, version, quota, or learner-switch rules. Background sync and push handlers are placeholders. PWA copy is English and the install control would compete with other fixed buttons.
- **User impact:** install/offline behavior may be absent, stale, or misleading; shared-device users risk seeing cached private content if caching is expanded without policy.
- **Business impact:** failed retention promise, stale releases, support issues, and privacy risk.
- **Recommendation:** treat offline as a designed product capability after the shared shell and content versioning exist. Register from the canonical shell; use an explicit public shell and authorized lesson-pack strategy; never cache tokens, receipts, chat, profile, or classroom/biometric responses; clear user-scoped caches on logout; provide localized offline/update states and quota controls.
- **Complexity:** M for safe shell integration; L for downloadable lesson packs/audio.
- **KPI:** **Needs analytics data** — service-worker install/activation success, install acceptance, offline lesson completion, stale-cache incidents, update adoption, cache failures, and retention of installed users.
- **Validation method:** Playwright offline/update/logout tests, two-account shared-device test, cache inspection, quota/eviction test, slow-network audit, and privacy review.

## Cross-cutting accessibility validation checklist

Because this was a static-only review, none of the following is yet a verified pass:

1. Keyboard order, visible focus, no keyboard traps, and equivalent operation for every clickable surface.
2. Semantic headings, landmarks, tab relationships, dialog names, focus entry/return, and Escape behavior.
3. Form label/error association and error summary focus.
4. Accessible names for icon/emoji-only controls.
5. Status/live-region behavior for chat, quiz, Realtime voice, translator, enrollment, and classroom recognition.
6. 200% text zoom and 320 CSS-pixel reflow without clipping; 400% zoom for applicable content.
7. Color contrast for text, placeholders, badges, focus indicators, and state changes.
8. Reduced-motion behavior for shimmer, pulse, modal, hover, and transcript animations.
9. Non-color cues and non-timed alternatives for quiz and recognition feedback.
10. Captions/transcripts or equivalent alternatives for educational audio where required.

## Measurement prerequisite

Do not assign numeric success targets from fixture counts. First define privacy-safe product events and establish a clean baseline. Required funnel joins include anonymous visit → registration → role activation → lesson start → quiz completion → paywall → external purchase intent → receipt/order state → entitlement → next lesson/return visit. Baselines and targets **Need analytics data**.
