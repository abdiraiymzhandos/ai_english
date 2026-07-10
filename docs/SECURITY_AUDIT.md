# Security Audit

## Audit metadata

| Field | Value |
| --- | --- |
| Audit date | 2026-07-10 |
| Repository | OqyAI Django project |
| Scope | Django configuration, authentication and authorization, lesson and classroom endpoints, OpenAI integrations, PWA caching, media, WhatsApp and Telegram integrations, payment receipt automation, tracked fixtures, dependency and deployment evidence |
| Method | Static source review, migration and test review, repository-state inspection, Django deployment checks, and existing automated tests |
| Working-tree baseline | lessons/views.py was already modified before this documentation task; the audit did not alter application code |
| Audit outputs | This document and docs/TECHNICAL_AUDIT.md |

## Evidence vocabulary

- Confirmed: directly demonstrated by repository code, tracked data shape, a local diagnostic, or an executed test.
- Inferred: a technically credible consequence of confirmed code, but not reproduced against production.
- Needs verification: depends on production infrastructure, external configuration, legal requirements, or third-party behavior not visible in the repository.
- Needs product-owner confirmation: repository evidence exposes a product-policy decision that code inspection cannot resolve; this is separate from Needs verification.
- Confidence High: evidence is direct and the conclusion has little ambiguity.
- Confidence Medium: evidence is direct but exploitation or impact depends on runtime conditions.
- Confidence Low: evidence is incomplete and should be treated as a question, not a fact.

Severity describes potential harm: P0 Critical, P1 High, P2 Medium, and P3 Low. Priority separately describes execution order: Now, Next, or Later. Effort follows the canonical backlog's XS/S/M/L/XL scale.

## Executive conclusion

The current WhatsApp payment path must not be treated as a trustworthy automatic entitlement system. A reusable receipt can satisfy the OCR score, POST webhooks are not authenticated with a Meta request signature, an active fallback can change the reply recipient, and generated account passwords are retained as message text. These are independent failures at the same trust boundary.

The browser application also inserts AI-controlled strings into HTML and uses a service worker that can cache authenticated pages. Classroom access can be self-selected during registration and permits collection of minors' names, photos, and voice-derived embeddings without a verified teacher or consent record.

The safest production posture is:

1. Stop OCR-only automatic entitlement grants.
2. Reject unsigned WhatsApp POSTs.
3. Never mutate a message recipient.
4. Replace delivered passwords with an expiring activation flow.
5. Remove HTML injection sinks and restrict service-worker caching to public static assets.

## Finding summary

| Security ID | Priority | Severity | Finding | Classification | Confidence |
| --- | --- | --- | --- | --- | --- |
| SEC-001 | Now #1 | P0 Critical | OCR-only automatic entitlement is replayable | Confirmed | High |
| SEC-002 | Now #2 | P1 High | Meta POST signatures are not validated | Confirmed | High |
| SEC-003 | Now #3 | P1 High | Sandbox fallback mutates the recipient | Confirmed | High |
| SEC-004 | Now #4 | P1 High | Generated passwords are delivered and persisted as plaintext | Confirmed | High |
| SEC-005 | Now #5 | P1 High | Sensitive configuration is tracked and local secret permissions are permissive | Confirmed | High |
| SEC-006 | Now #7 | P1 High | AI and user-controlled output reaches HTML execution sinks | Confirmed | High |
| SEC-007 | Next | P1 High | Private media authorization and deletion lifecycle are incomplete | Confirmed and Needs verification | High |
| SEC-008 | Next | P1 High | Service worker can cache private authenticated responses | Confirmed | High |
| SEC-009 | Next | P1 High | Production HTTPS and secret hardening is incomplete in repository settings | Confirmed and Needs verification | High |
| SEC-010 | Next | P1 High | Teacher identity and biometric consent are not verified | Confirmed and Needs verification | High |
| SEC-011 | Next | P1 High | Login, public write paths, and AI usage lack application-level limits | Confirmed | High |
| SEC-012 | Next | P1 High | Payload, error, and personal-data logging lacks minimization and retention | Confirmed | High |
| SEC-013 | Later | P2 Medium | Third-party runtime assets lack CSP and integrity controls | Confirmed | High |
| SEC-014 | Next after SEC-005 | P1 High | Sensitive tracked history requires coordinated purge after rotation | Confirmed and Needs verification | High |

## Detailed findings

### SEC-001 — Stop OCR-only automatic entitlement grants

| Field | Detail |
| --- | --- |
| Priority | Now #1 |
| Severity | P0 Critical |
| Affected component | WhatsApp receipt download, OCR analysis, receipt finalization, and course provisioning |
| Evidence | whatsapp_agent/utils.py: analyze_receipt_text; whatsapp_agent/services.py: evaluate_receipt, finalize_receipt, provision_course_access_for_lead; whatsapp_agent/models.py: WhatsAppReceipt |
| Classification / confidence | Confirmed / High |
| Attack scenario | A WhatsApp user submits an old or copied receipt that contains the configured amount and merchant identity. The scorer does not require a unique transaction reference, payer binding, currency, successful-payment state, or a fresh timestamp. The same proof can be submitted by another lead and automatically produce a paid account. |
| Impact | Revenue loss, unauthorized course access, creation of fraudulent accounts, unreliable payment records, and difficult revocation or dispute handling |
| Remediation | Immediately route every receipt to manual approval. Add a payment or entitlement ledger linked to the approving actor and source receipt. Before automation returns, require a trusted payment-provider identifier, uniqueness at the database level, expected currency and status, timestamp freshness, payer or order binding, and replay-safe state transitions. OCR should assist review, not constitute proof of payment. |
| Validation | Submit the same receipt to two leads and confirm the second is rejected. Test an old receipt, altered amount, missing currency, failed status, duplicate provider reference, and concurrent duplicate submissions. Confirm no UserProfile entitlement changes before an auditable approval transaction commits. |
| Estimated effort | S for the fail-closed containment; the later trusted payment/ledger redesign is DATA-002 (XL) |

### SEC-002 — Authenticate Meta webhook POSTs

| Field | Detail |
| --- | --- |
| Priority | Now #2 |
| Severity | P1 High |
| Affected component | POST /api/whatsapp/webhook/ |
| Evidence | whatsapp_agent/views.py: whatsapp_webhook; english_course/settings.py: WhatsApp settings |
| Classification / confidence | Confirmed / High |
| Attack scenario | Any network client posts a forged webhook body. The endpoint is correctly exempt from browser CSRF, but it does not verify a Meta HMAC signature over the raw body and does not validate that the event targets the configured business phone identity. |
| Impact | Forged leads and messages, database and log growth, OpenAI and Telegram cost, attempted outbound messages, status corruption, and a path into receipt processing |
| Remediation | Add a required app-secret setting. Verify the raw request body with HMAC-SHA256 and constant-time comparison before JSON parsing. Fail closed when configuration or signature is absent or malformed. Validate expected webhook object and configured phone identity. Keep CSRF exemption only for this signed machine endpoint. |
| Validation | Tests must reject missing, malformed, wrong-secret, modified-body, and replayed signatures and accept a correct signature. Assert that rejected requests create no event, lead, message, receipt, external call, or log containing the body. |
| Estimated effort | M |

### SEC-003 — Remove production sandbox recipient mutation

| Field | Detail |
| --- | --- |
| Priority | Now #3 |
| Severity | P1 High |
| Affected component | WhatsApp outbound send retry |
| Evidence | whatsapp_agent/services.py: _derive_sandbox_test_recipient, _lead_sandbox_test_recipient, _fallback_recipient_for_131030, _send_whatsapp_payload, _upsert_lead; whatsapp_agent/tests.py: WhatsAppSendTests |
| Classification / confidence | Confirmed / High |
| Attack scenario | A reply to the authenticated inbound sender receives a provider error. Production code derives a different numeric recipient and retries the full message there. A receipt-success reply may contain account activation information. Existing tests explicitly require the changed recipient. |
| Impact | Disclosure of private conversation or account credentials to another person, misdirected sales messages, and loss of recipient integrity |
| Remediation | Remove automatic recipient derivation and retry. The recipient for an inbound conversation must be the exact provider-authenticated sender identity. Keep test-recipient behavior in an explicit management command or isolated non-production setting with an allowlist and no customer data. |
| Validation | Assert every retry preserves the original authenticated recipient. A provider recipient error must end in a recorded failure and human-visible recovery state. Add a regression test proving credential-bearing content is never resent to another recipient. |
| Estimated effort | S |

### SEC-004 — Replace plaintext password delivery with one-time activation

| Field | Detail |
| --- | --- |
| Priority | Now #4 |
| Severity | P1 High |
| Affected component | WhatsApp account provisioning, outbound-message persistence, operational registration command |
| Evidence | whatsapp_agent/services.py: generate_password usage, _build_success_reply, _record_outbound_message, _send_whatsapp_payload; whatsapp_agent/management/commands/whatsapp_register_phone.py: handle |
| Classification / confidence | Confirmed / High |
| Attack scenario | Provisioning creates a password and inserts it into a WhatsApp message. The same message and raw provider request are stored in WhatsAppMessage and can also enter failure/event diagnostics. A separate command prints a sensitive registration PIN payload and accepts it on the command line. |
| Impact | Long-lived plaintext credentials in databases, backups, admin views, logs, and support tools; account takeover after data exposure; secrets in shell history or process inspection |
| Remediation | Create accounts with an unusable password or random internal secret and send a short-lived, single-use activation link. Redact all credential-like content before message/event persistence. Accept operational secrets through a protected prompt or secret manager, never print them, and make logs safe by construction. Force password creation after identity verification. |
| Validation | Search current and historical message/event records for credential markers after a test provision and confirm none exist. Verify activation tokens expire, are single-use, are bound to the intended account, and are invalidated after use. Confirm command output and process arguments contain no secret. |
| Estimated effort | M |

### SEC-005 — Rotate exposed credentials and sanitize tracked sources

| Field | Detail |
| --- | --- |
| Priority | Now #5 |
| Severity | P1 High |
| Affected component | Current tracked `analyze_lessons.py`, repository documentation and history, local environment file, and secret-management workflow |
| Evidence | At audit start, `WHATSAPP_AGENT_SETUP.md` contained a sensitive webhook-verification setting; it is now sanitized. Current tracked `analyze_lessons.py` contains a credential-bearing database connection path. Values are intentionally omitted. `.gitignore` ignores `.env`; local `.env` mode was inspected as `0644` without reading its contents; no `.env.example` exists. |
| Classification / confidence | Confirmed / High |
| Attack scenario | A credential embedded in a tracked script or formerly embedded in setup documentation is available to repository readers and remains in history even after current documentation is sanitized. On a shared host, a local secret file readable by other users can expose application and provider credentials. Developers have no sanitized environment template and may copy live values into code or documentation. |
| Impact | Provider account abuse, forged verification handshakes, broader credential compromise, and repeated secret leakage during onboarding |
| Remediation | Rotate every potentially exposed credential first. Replace populated examples with placeholders. Change local secret permissions to owner-only, use a deployment secret store, add a sanitized .env.example containing names only, and enable pre-commit and CI secret scanning. Do not record values in tickets or audit files. |
| Validation | Verify rotation in each provider console, owner-only local permissions, no tracked .env files, a placeholder-only example, and clean secret-scanner results for the current tree. History remediation is SEC-014. |
| Estimated effort | S for code/docs plus external rotation operations |

### SEC-006 — Eliminate AI-output cross-site scripting

| Field | Detail |
| --- | --- |
| Priority | Now #7 |
| Severity | P1 High |
| Affected component | Lesson explanations, lesson chat, motivational modal |
| Evidence | lessons/templates/lessons/lesson_detail.html: explanation fields rendered with the safe filter, highlightEnglishText, explanationContainer.innerHTML, appendMessage; lessons/templates/lessons/lesson_list.html: showMotivationalModal and insertAdjacentHTML; lessons/views.py: explain_section, chat_with_gpt, motivational_message |
| Classification / confidence | Confirmed / High |
| Attack scenario | An AI response, stored Explanation text, upstream error, or reflected chat content contains active HTML. The browser inserts it through innerHTML or insertAdjacentHTML, or bypasses Django escaping with the safe filter. Model output is not a trusted HTML source. |
| Impact | Script execution in an authenticated origin, CSRF token and non-HttpOnly cookie access, actions as the current user, classroom data access, and persistent execution through stored explanations |
| Remediation | Treat AI output as plain text and render with textContent or normal Django escaping. If limited formatting is required, pass output through a maintained allowlist sanitizer with URLs and attributes restricted. Remove the safe filters and the HTML-rewrite highlighter; perform highlighting with text-node traversal. Return generic server errors. Add a restrictive CSP as defense in depth, not as the primary fix. |
| Validation | Feed script, image-event, SVG, malformed-tag, template, and encoded payloads through chat, explanation, motivational, and error responses. Assert they render visibly as text and never create executable DOM nodes. Add browser-level regression tests. |
| Estimated effort | S |

### SEC-007 — Make uploaded media private and enforce deletion lifecycle

| Field | Detail |
| --- | --- |
| Priority | Next |
| Severity | P1 High |
| Affected component | Classroom photos, WhatsApp receipts, generated lesson audio, MEDIA_ROOT deployment |
| Evidence | lessons/models.py: StudentPhoto and student_face_upload_path; whatsapp_agent/models.py: WhatsAppReceipt.file; lessons/views_classroom.py: classroom_student_photo; lessons/views.py: explain_section file deletion/write; english_course/settings.py: MEDIA_ROOT; english_course/urls.py: DEBUG media mapping |
| Classification / confidence | Confirmed for incomplete lifecycle; Needs verification for production direct exposure / High |
| Attack scenario | Database deletion removes a model row but Django does not automatically remove the underlying file. Generated explanation replacement uses glob deletion and local writes that can race. If production maps the entire media directory directly, possession or discovery of a media URL may bypass the guarded classroom-photo view and expose classroom images or receipts. |
| Impact | Orphaned sensitive files, retention beyond account deletion, unauthorized access if media is directly served, broken references under concurrent generation, and inconsistent multi-instance storage |
| Remediation | Separate public generated audio from private classroom and receipt storage. Serve private objects only through an authorization layer or short-lived signed URL. Add file-size, pixel-count, MIME/content, and PDF complexity limits. Define retention and deletion jobs; delete physical files after committed model deletion. Use storage APIs rather than direct filesystem glob/open operations. |
| Validation | Verify one teacher cannot fetch another teacher's media through every URL form. Delete students, users, receipts, and explanations and assert physical objects are removed after commit. Test concurrent generation and multi-worker storage. Inspect the production web-server media mapping before declaring exposure fixed. |
| Estimated effort | L |

### SEC-008 — Stop service-worker caching of private/authenticated responses

| Field | Detail |
| --- | --- |
| Priority | Next |
| Severity | P1 High |
| Affected component | PWA service worker and authenticated GET pages |
| Evidence | static/sw.js: urlsToCache, fetch handler, caches.match, cache.put; static/js/pwa-register.js: root-scope registration |
| Classification / confidence | Confirmed / High |
| Attack scenario | The root-scoped service worker caches any successful same-origin basic GET response except a narrow Realtime list. That includes profile, lesson, classroom, and authorized photo responses. Cache keys do not separate Django users. A later account on the same browser can receive a prior user's cached page or image, and logout does not clear the cache. |
| Impact | Cross-account disclosure on shared devices, stale authorization decisions, private classroom media retained offline, and inability to revoke cached content |
| Remediation | Cache only explicit versioned public static assets. Use network-only behavior for navigation, auth, profile, classroom, media, and all personalized paths. Respect Cache-Control: no-store/private and clear relevant caches on logout and service-worker upgrades. Avoid pre-caching the personalized root page. |
| Validation | Browser test with two accounts on one profile: visit private pages and photos as account A, log out, log in as B, go offline, and confirm no A content is returned. Inspect Cache Storage and assert no authenticated response is present. |
| Estimated effort | S |

### SEC-009 — Separate and harden production settings

| Field | Detail |
| --- | --- |
| Priority | Next |
| Severity | P1 High |
| Affected component | Django settings and deployment edge |
| Evidence | english_course/settings.py: SECRET_KEY, DEBUG default, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, cookie settings, logging; executed manage.py check --deploy reported security.W004, security.W008, and security.W009 |
| Classification / confidence | Confirmed repository/local diagnostic; Needs verification at production edge / High |
| Attack scenario | A weak signing key or accidental DEBUG deployment undermines Django security. Without an independently configured HTTPS redirect and HSTS policy, clients can reach an insecure origin or remain vulnerable to downgrade. Hard-coded host/origin settings drift from deployment. |
| Impact | Signed-token compromise, debug information exposure, insecure transport, session/CSRF failures, and fragile deploys |
| Remediation | Fail startup when production SECRET_KEY is absent or weak, and rotate the currently suspect key with a session-invalidation plan. Default DEBUG to false. Split environment-specific settings or use a strict typed configuration layer. Configure HTTPS redirect, HSTS rollout, proxy SSL header, secure cookies, and trusted origins according to the actual edge. Remove settings import prints and make OpenAI optional for non-AI management commands. |
| Validation | Run check --deploy in the production configuration with no warnings or documented edge-owned exceptions. Verify HTTP-to-HTTPS behavior, HSTS headers, secure cookie behavior, proxy scheme detection, invalid Host rejection, and that production never starts with DEBUG enabled or a weak key. |
| Estimated effort | M |

### SEC-010 — Gate classroom and biometric enrollment pending verified consent

| Field | Detail |
| --- | --- |
| Priority | Next |
| Severity | P1 High |
| Affected component | Registration, classroom authorization, student roster, photos, voice embeddings, OpenAI classroom prompt |
| Evidence | lessons/forms.py: CustomRegisterForm role field; lessons/views.py: register; lessons/models.py: UserProfile role, ClassStudent, StudentPhoto; lessons/views_classroom.py: teacher guards, _classroom_instructions, photo and voice enrollment |
| Classification / confidence | Confirmed technical behavior; Needs verification for legal basis and consent / High |
| Attack scenario | Any registrant self-selects the teacher role and immediately gains classroom management. The account can create named student rosters, upload photos, and store voice-derived embeddings. Student names, school, and class are inserted into an OpenAI session prompt. No consent, guardian, school, retention, or verified-teacher record exists in the schema. |
| Impact | Unauthorized collection of minors' personal and biometric-like data, third-party processing without documented basis, impersonation of a teacher, and regulatory/reputational harm |
| Remediation | Make teacher access an admin-approved state or Django permission, not a registration choice. Design consent and lawful-basis records with policy/legal review before collecting minors' photos or voice features. Minimize identifiers sent to OpenAI, define retention/deletion, audit access, and disable biometric enrollment until those controls exist. |
| Validation | A newly registered account must fail every classroom endpoint until approved. Test cross-teacher isolation, approval/revocation, consent-required enrollment, deletion, audit events, and prompt minimization. Obtain documented product/legal sign-off. |
| Estimated effort | M for the fail-closed gate; XL for the complete product and policy program |

### SEC-011 — Add abuse limits for authentication, AI, lead, media, and token routes

| Field | Detail |
| --- | --- |
| Priority | Next |
| Severity | P1 High |
| Affected component | Login, registration, lead capture, quiz generation, chat, motivational messages, Realtime token minting, webhook processing |
| Evidence | lessons/urls.py and lessons/views.py public endpoints; Django LoginView without throttling; no rate-limit middleware or dependency; Realtime mint endpoints enforce access but not usage budgets |
| Classification / confidence | Confirmed / High |
| Attack scenario | Automated clients attempt passwords, create accounts/leads, cause runtime quiz writes, call public OpenAI-backed endpoints, or repeatedly mint premium Realtime credentials. A valid premium account can consume unbounded sessions. |
| Impact | Account compromise, provider cost, database growth, worker exhaustion, and degraded service |
| Remediation | Add layered limits by account, IP/network signal, endpoint, and provider budget. Apply progressive login throttling without account enumeration, CAPTCHA only where justified, per-user AI concurrency and daily budgets, webhook signature checks, body-size limits, and provider usage alerts. Limits must work across workers through shared state. |
| Validation | Automated threshold tests, distributed-worker tests, successful-user recovery tests, IPv4/IPv6 normalization, and confirmation that limits cannot be bypassed by changing sessions. Verify provider-side spend caps and alerts separately. |
| Estimated effort | M |

### SEC-012 — Minimize and expire raw payloads, messages, logs, and alerts

| Field | Detail |
| --- | --- |
| Priority | Next |
| Severity | P1 High |
| Affected component | WhatsApp messages/events, malformed webhook logging, provider errors, Telegram alerts, tracked fixtures |
| Evidence | whatsapp_agent/models.py: raw_payload, metadata, extracted_text and event payload; whatsapp_agent/views.py: malformed raw body; whatsapp_agent/services.py: webhook_received, response/error payloads, admin alerts; lessons/services/registration_notifications.py |
| Classification / confidence | Confirmed / High |
| Attack scenario | Full inbound bodies, message payloads, provider responses, OCR text, customer phone/name, and operational errors are duplicated across models and Telegram. There is no retention schedule, field allowlist, redaction layer, or cleanup job. Malicious bodies can amplify storage and place sensitive content in support systems. |
| Impact | Larger breach scope, unnecessary third-party disclosure, database growth, credentials or personal data in backups, and difficult deletion compliance |
| Remediation | Define an allowlisted event schema, redact phone/message/credential fields, bound body and text lengths, avoid raw malformed-body persistence, and introduce per-data-class retention. Keep audit facts such as event ID and status without entire payloads. Review Telegram as a data processor and minimize alert content. Remove populated personal-data fixtures from source control. |
| Validation | Unit-test the redactor against nested payloads and credential patterns. Run retention jobs on representative data. Confirm account deletion and approved privacy requests remove or irreversibly anonymize linked records and files while preserving minimal financial audit data where legally required. |
| Estimated effort | L |

### SEC-013 — Establish a browser content-security and dependency integrity policy

| Field | Detail |
| --- | --- |
| Priority | Later |
| Severity | P2 Medium |
| Affected component | Base, lesson, privacy, and classroom templates; browser ML models and libraries |
| Evidence | lessons/templates/lessons/base.html, lesson_detail.html, lesson_list.html, privacy_policy.html, classroom/session.html, classroom/group_detail.html load third-party scripts/styles/models; no CSP configuration or integrity attributes were found |
| Classification / confidence | Confirmed / High |
| Attack scenario | A compromised third-party CDN, dependency path, or remotely hosted model supplies malicious JavaScript or altered assets to authenticated classroom users. Inline scripts and styles make a restrictive CSP difficult to deploy. |
| Impact | Origin-level script execution, classroom microphone/camera and personal-data access, supply-chain compromise, and availability failures |
| Remediation | Inventory every external origin and dependency. Prefer self-hosted, version-locked, reviewed assets. Use integrity and crossorigin where immutable CDN assets remain. Move inline code to versioned static files and deploy CSP in report-only mode before enforcement. Restrict script, style, connect, worker, media, frame, and model sources to the minimum required set. |
| Validation | CSP report-only collection shows no unexplained origins; enforced CSP blocks an injected script; integrity mismatch blocks altered assets; classroom features pass with pinned/self-hosted models and libraries. |
| Estimated effort | L |

### SEC-014 — Purge private historical Git objects after rotation

| Field | Detail |
| --- | --- |
| Priority | Next after SEC-005 |
| Severity | P1 High |
| Affected component | Git history, clones, caches, tracked fixtures and setup documentation |
| Evidence | Populated personal-data fixtures and `analyze_lessons.py`'s credential-bearing connection path are tracked. The WhatsApp setup contained a sensitive setting at audit start and is now sanitized. Current-tree sanitization alone leaves prior commits and clones. Values are intentionally omitted. |
| Classification / confidence | Confirmed repository exposure; Needs verification for all mirrors and credential liveness / High |
| Attack scenario | A credential is removed from the latest commit but remains retrievable from history, forks, CI caches, backups, or developer clones. Populated lead, profile, device, and attempt fixtures remain part of historical source distribution. |
| Impact | Persistent secret and personal-data exposure, false confidence after a normal deletion commit, and compliance burden |
| Remediation | Rotate credentials before rewriting history. Inventory remotes, forks, archives, CI artifacts, and deploy caches. Obtain owner approval for a coordinated history rewrite with a tool such as git-filter-repo, then force-update protected remotes and require fresh clones. Handle personal-data erasure with legal/operational guidance. Never rewrite history as an uncoordinated coding task. |
| Validation | Secret scanning of all refs and a fresh clone is clean; old credentials fail at providers; CI artifacts and deployment bundles are purged; collaborators confirm clone replacement. Preserve an approved incident record outside the rewritten repository. |
| Estimated effort | L, including coordination |

## Checked non-findings and positive controls

These checks do not make the application secure overall, but they avoid overstating the audit.

| Check | Result | Classification | Confidence |
| --- | --- | --- | --- |
| Raw SQL injection surface | No use of raw(), RawSQL, cursor(), or direct execute() was found in application Python. Normal ORM parameterization is used. | Confirmed | High |
| Classroom object ownership | Group, student, photo, embedding, session, and classroom-token queries consistently filter through teacher=request.user or equivalent owner relationships in lessons/views_classroom.py. | Confirmed | High |
| CSRF on normal browser POSTs | CsrfViewMiddleware is enabled. Quiz, explanation, chat, motivational, translator, classroom, registration, lead, profile, and login flows retain Django CSRF behavior. Browser code sends CSRF headers for AJAX POSTs. | Confirmed | High |
| WhatsApp CSRF exemption | Exemption is appropriate for a machine webhook only after SEC-002 signature validation is added. It is not itself evidence of a browser CSRF bug. | Confirmed | High |
| OpenAI standard API key exposure | Browser Realtime endpoints mint ephemeral credentials; no code path was found that intentionally returns the standard OpenAI API key. | Confirmed | High |
| Classroom horizontal authorization | Direct object lookups inspected in views_classroom.py include the owning teacher filter. No confirmed cross-teacher IDOR was found. | Confirmed | High |
| Quiz cross-lesson answer submission | submit_answer restricts the question to the URL lesson and tests cover rejection. The equivalent invariant is not database-enforced. | Confirmed | High |
| .env tracking | .env is ignored and was not listed as a tracked file. Its contents were not inspected for this audit. | Confirmed | High |

## Production items not verifiable from this repository

| Item | Why it matters | Classification | Confidence |
| --- | --- | --- | --- |
| Reverse-proxy HTTPS redirect, HSTS, and proxy scheme headers | The repository check reports gaps, but an edge may supply some controls. | Needs verification | Medium |
| Production SECRET_KEY strength and rotation status | The local loaded configuration failed Django's strength check; production may differ. | Needs verification | Medium |
| WAF, upstream rate limiting, and provider spend caps | No application controls are present, but external controls may exist. | Needs verification | Low |
| Production media mapping | Direct mapping of MEDIA_ROOT could bypass guarded views; server configuration is not in the repository. | Needs verification | Medium |
| Database engine, transport encryption, backups, and at-rest encryption | Settings support MySQL optionally but do not prove production topology or backup controls. | Needs verification | Low |
| Log aggregation, access control, retention, and backup retention | Application payloads are sensitive; downstream handling is unknown. | Needs verification | Low |
| Credential liveness and all exposed-history locations | No credential values were tested or reproduced. Rotation must be confirmed at each provider. | Needs verification | Medium |
| OpenAI, Meta, Telegram, hosting, and CDN data-processing terms | Required for privacy and minors' data review; contracts are external. | Needs verification | Low |
| Classroom consent and school authorization | No technical record exists; offline agreements may exist. | Needs verification | Low |
| WhatsApp production activation state | Setup documentation and current provider state may differ. | Needs verification | Low |

## Security validation baseline

The following commands were executed during the audit:

- Django application tests for lessons and whatsapp_agent: 40 tests passed.
- Django migration drift check: no model changes detected.
- Django deployment check: warnings for HSTS, SSL redirect, and signing-key strength.

The passing suite does not cover SEC-001, SEC-002, SEC-006, SEC-007, SEC-008, SEC-010, or the production items above. Security remediation is complete only when focused negative tests exist and the relevant production configuration is independently verified.
