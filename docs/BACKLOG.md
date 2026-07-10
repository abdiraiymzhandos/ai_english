# Unified task backlog

Audit snapshot: 2026-07-10. Status values: `Proposed`, `Ready`, `In progress`, `Blocked`, `Done`, `Accepted risk`. Every item below is unimplemented unless explicitly changed later. Priority means execution order; severity means consequence.

Effort: `XS` (< a few hours), `S` (up to half a day), `M` (one–two days), `L` (three–five days), `XL` (multi-phase/redesign). Confidence is based on repository evidence, not production observation.

## Execution order summary

| Order | Task | Priority | Severity | Effort | Why first |
| --- | --- | --- | --- | --- | --- |
| 1 | `SEC-001` | Now | P0 | S | Current OCR heuristic can grant access without verified payment |
| 2 | `SEC-002` | Now | P1 | M | Public webhook POST boundary is unauthenticated |
| 3 | `SEC-003` | Now | P1 | S | Reply logic can change the recipient |
| 4 | `SEC-004` | Now | P1 | M | Reusable passwords are sent and retained as chat data |
| 5 | `SEC-005` | Now | P1 | S + operations | Tracked credentials must be treated as compromised |
| 6 | `TEST-001` | Now | P1 | M | Locks adversarial behavior before deeper payment work |
| 7 | `SEC-006` | Now | P1 | S | AI output can execute as same-origin HTML/JavaScript |
| 8 | `BUG-001` | Now | P1 | S | Conflicting price makes legitimate payments fail validation |
| 9 | `DATA-001` | Next | P1 | M | Provider retries can duplicate work/messages/access |
| 10 | `ARCH-001` | Next | P1 | L | Access policy is duplicated and bypassable |

Only one recommendation is active: `SEC-001`. Later ordering can change when production evidence or product-owner answers change.

## Critical and high security

### SEC-001 — Stop OCR-only automatic entitlement grants

- **Metadata:** Category security/payment; status Proposed; priority Now #1; severity P0; effort S for fail-closed change; confidence High; type confirmed exploitable vulnerability.
- **Evidence:** `whatsapp_agent/utils.py::analyze_receipt_text` accepts publicly known merchant fields; `services.py::evaluate_receipt`, `finalize_receipt`, and `process_receipt_message` automatically provision. No transaction identity, payer binding, status/currency check, freshness, or replay uniqueness.
- **Impact:** Business—unpaid course access and fraud; user—incorrect approvals/rejections and support incidents; technical—permanent profile mutation from untrusted media.
- **Dependencies/files:** No prerequisite. Likely `whatsapp_agent/services.py`, settings, admin/tests; no schema required for the immediate fail-closed task.
- **Implementation outline:** Make every receipt pending human review by default; remove automatic call to provisioning; keep evidence/status visible to authorized admin; send neutral pending copy; audit-log explicit later approval without treating OCR as proof.
- **Tests required:** Valid-looking, forged, old, duplicate, cross-lead, low-confidence, and processing-error receipts never set `is_paid` or create a user.
- **Manual QA required:** Submit representative fake media in a non-production environment and verify pending/admin state and that no credentials are sent.
- **Acceptance criteria:** No inbound receipt can grant access without an explicit authorized approval action; default/missing configuration fails closed; existing paid users are unchanged; tests prove negative paths.
- **Change management:** Migration none for fail-closed scope; deployment requires operator communication and monitoring of pending receipts; rollback is code rollback while retaining fail-closed configuration—never re-enable OCR auto-grants; update security, AI, operations, backlog, and customer support runbook.

### SEC-002 — Authenticate Meta webhook POSTs

- **Metadata:** Category security/integration; status Proposed; priority Now #2; severity P1; effort M; confidence High; type confirmed vulnerability.
- **Evidence:** `whatsapp_agent/views.py::whatsapp_webhook` is CSRF-exempt and parses POST bytes without `X-Hub-Signature-256`; the GET verify token authenticates only subscription setup.
- **Impact:** Business—fraudulent cost/messages and service abuse; user—fake conversation/status handling; technical—untrusted DB, OCR, OpenAI, Meta and Telegram work.
- **Dependencies/files:** Rotatable Meta app secret and deployment secret management; `views.py`, settings, tests, sanitized env docs.
- **Implementation outline:** Add required app-secret setting; compute HMAC-SHA256 over exact raw body; constant-time compare; reject missing/invalid/malformed signatures before parsing/storage; optionally verify expected account/phone identity; redact failures.
- **Tests required:** Signature success, wrong secret, altered body, missing header/config, malformed header/body, and no-side-effect assertions.
- **Manual QA required:** Complete Meta verification in a controlled sandbox only after automated tests pass.
- **Acceptance criteria:** All POSTs fail closed unless signature and configured source validation pass; GET handshake remains separate; invalid requests create no event/lead/message and call no external service.
- **Change management:** No migration; configure secret before deploy or webhook returns non-success by design; rollback must not restore unauthenticated handling—disable route instead; update security/environment/testing/WhatsApp docs.

### SEC-003 — Remove production sandbox recipient mutation

- **Metadata:** Category security/privacy; status Proposed; priority Now #3; severity P1; effort S; confidence High; type confirmed vulnerability.
- **Evidence:** `whatsapp_agent/services.py` derives a different sandbox recipient and retries error `131030`; tests explicitly expect changed destinations. The same send path carries success credentials.
- **Impact:** Business—breach/support/regulatory exposure; user—private messages or account access sent to another number; technical—destination integrity is not invariant.
- **Dependencies/files:** `whatsapp_agent/services.py`, tests, management commands; no prerequisite.
- **Implementation outline:** A production reply destination must equal authenticated inbound `wa_id`; remove derivation/metadata fallback from runtime; keep any sandbox send only in an explicit non-production command with a configured allowlisted recipient.
- **Tests required:** A provider error never triggers a different `to`; the sandbox helper cannot run in production mode; credential-bearing copy cannot be sent cross-recipient.
- **Manual QA required:** Inspect mocked outbound request payloads and confirm the recipient always equals the authenticated inbound sender.
- **Acceptance criteria:** Runtime has no computed alternative recipient; failed sends fail/report rather than redirect; unsafe tests are replaced by destination-integrity tests.
- **Change management:** No migration; deploy may reduce test-number convenience; rollback must preserve destination invariant; update security/WhatsApp/testing docs.

### SEC-004 — Replace plaintext password delivery with one-time activation

- **Metadata:** Category security/authentication; status Proposed; priority Now #4; severity P1; effort M; confidence High; type confirmed vulnerability.
- **Evidence:** `whatsapp_agent/services.py::_build_success_reply` includes generated password; outbound `WhatsAppMessage.text_content/raw_payload` persists it; phone-registration command accepts/prints a PIN payload.
- **Impact:** Business—account takeover and breach response; user—reusable credential retained by Meta/DB/logs; technical—secret cannot be reliably erased from downstream systems.
- **Dependencies/files:** Destination integrity (`SEC-003`); auth activation decision. Likely services, auth URLs/views/templates, settings, tests, command.
- **Implementation outline:** Create user with unusable password; send short-lived signed one-time set-password link bound to intended account/phone; prevent replay and expire; redact message/event payloads; stop PIN output and avoid CLI secret arguments where feasible.
- **Tests required:** Prove no plaintext password/PIN enters DB/log/output; cover token expiry, replay, wrong-user denial, successful one-time set, and existing-user behavior.
- **Manual QA required:** Complete the mobile WhatsApp-to-HTTPS set-password journey on a non-production account.
- **Acceptance criteria:** No reusable credential is messaged, persisted, printed, or logged; activation token is short-lived, one-use, host-safe, rate-limited, and audited.
- **Change management:** Migration optional depending token audit design; deployment requires HTTPS/base URL and support copy; rollback disables automated account creation rather than restoring passwords; update auth/security/privacy/operations docs.

### SEC-005 — Rotate exposed credentials and sanitize tracked sources

- **Metadata:** Category secret management; status Proposed; priority Now #5; severity P1; effort S code/docs plus external operations; confidence High; type confirmed credential exposure.
- **Evidence:** A tracked legacy script contains a database credential; the former WhatsApp setup contained a verification credential; `.env` was mode `0644`; older Git objects include configuration/backups. Values are intentionally not repeated.
- **Impact:** Business—unauthorized service/database access; user—private data exposure; technical—secrets remain valid outside code fixes.
- **Dependencies/files:** Authorized owners for each external system. `analyze_lessons.py`, secret store/file permissions, affected docs; history purge is separate `SEC-014`.
- **Implementation outline:** Inventory secret categories without copying values; rotate/revoke at providers/database; remove hard-coded value from current code; restrict local secret permissions; verify apps use new secret store; document rotation date/category privately.
- **Tests required:** Run repository path-only secret scans and application smoke tests with newly issued secrets; never place secret values in tests or output.
- **Manual QA required:** Authorized owners verify provider/database access with redacted evidence and confirm revoked values no longer work.
- **Acceptance criteria:** All potentially exposed active credentials rotated/revoked; no literal production credential in current tracked tree; protected secret files least-privilege; incident owner records completion.
- **Change management:** No DB migration; coordinated deployment/restart; rollback uses newly issued secrets only, never exposed ones; update security/environment/incident documentation.

### SEC-006 — Eliminate AI-output cross-site scripting

- **Metadata:** Category security/frontend; status Proposed; priority Now #7; severity P1; effort S; confidence High; type confirmed vulnerability.
- **Evidence:** `lesson_detail.html` applies `|safe` to stored AI explanations and inserts explanation/chat/error values through `innerHTML`; public user prompts can influence model output.
- **Impact:** Business—account compromise/trust loss; user—same-origin script execution; technical—CSRF actions/data access and persistent malicious explanations.
- **Dependencies/files:** None. Lesson template, optional sanitizer dependency only if an allowlist is truly needed, tests.
- **Implementation outline:** Render plain text with autoescape/`textContent`; create DOM nodes; preserve formatting through CSS/line breaks, not raw HTML; sanitize existing stored output on render; return safe generic errors.
- **Tests required:** Browser automation covers script, image-error, SVG, encoded, stored, and model-like payloads and proves readable text without execution.
- **Manual QA required:** Inspect rendered output and browser developer tools under the intended CSP.
- **Acceptance criteria:** No untrusted AI/user/provider string reaches `|safe`, `innerHTML`, or `insertAdjacentHTML`; formatting remains readable; regression tests cover stored and chat output.
- **Change management:** No migration required; deploy invalidates relevant caches; rollback must keep escaping; update security/AI/testing docs.

### SEC-007 — Make uploaded media private and enforce deletion lifecycle

- **Metadata:** Category security/privacy/storage; status Proposed; priority Next; severity P1; effort L; confidence High; type confirmed design weakness/unverified deployment exposure.
- **Evidence:** Student photos and receipts share `MEDIA_ROOT`; docs historically recommend media mapping; protected photo view can be bypassed if web server serves the path; Django row deletion does not remove files; no receipt/photo retention policy.
- **Impact:** Business—privacy/regulatory/hosting risk; user—child biometric or financial document exposure; technical—orphan files, multi-instance incompatibility.
- **Dependencies/files:** Product retention/consent decision, storage choice; models/views/storage settings/deletion jobs/tests.
- **Implementation outline:** Separate public generated audio from private uploads; authenticated owner/staff download views or private object-store signed URLs; non-guessable keys; MIME/size/dimension caps; transactional save; explicit delete/retention job and audit.
- **Tests required:** Cover cross-user/anonymous and direct-URL denial, physical deletion, orphan reconciliation, oversized/decompression cases, and backup/restore.
- **Manual QA required:** Test authorization and direct media URLs through a production-like web-server/storage mapping.
- **Acceptance criteria:** Private media is never publicly mapped; authorization is enforced per access; documented retention/delete works across DB/storage/backups; failures do not leave partial objects.
- **Change management:** Data/storage migration likely; staged copy/check/cutover and backup; rollback keeps old store private/read-only; update privacy/classroom/environment/operations docs.

### SEC-008 — Stop service-worker caching of private/authenticated responses

- **Metadata:** Category security/PWA; status Proposed; priority Next; severity P1; effort S; confidence High; type confirmed insecure caching design.
- **Evidence:** `static/sw.js` uses cache-first for nearly every same-origin GET, including potential profile/classroom/media responses, and does not clear per-user caches on logout. Precache root can include session-specific content.
- **Impact:** Business—privacy incident/stale conversion state; user—another user on a shared browser can see cached identity/progress; technical—stale CSRF/session-dependent pages.
- **Dependencies/files:** `static/sw.js`, PWA registration/logout behavior/tests; no prerequisite.
- **Implementation outline:** Do not cache navigations or authenticated/private endpoints; allowlist immutable versioned public static only; no credentials/tokens/media/admin/profile/classroom; clear user caches on logout/version change; remove missing precache asset.
- **Tests required:** Browser automation covers login→visit→logout→other user/offline and asserts Cache Storage contains no private response.
- **Manual QA required:** Inspect cache contents and verify that the public offline shell installs and works, or that the PWA is deliberately disabled.
- **Acceptance criteria:** Authenticated HTML/API/private media never enters Cache Storage; logout removes user-scoped data; service-worker install cannot silently fail.
- **Change management:** No migration; bump cache version and force old cache deletion; rollback should unregister worker rather than restore broad caching; update security/UX/PWA docs.

### SEC-009 — Separate and harden production settings

- **Metadata:** Category security/DevOps; status Proposed; priority Next; severity P1; effort M; confidence High; type insecure configuration.
- **Evidence:** `DEBUG` defaults true; secret is not validated; deploy check warns HSTS, SSL redirect, weak loaded secret; hosts/origins and secure cookies share one module; OpenAI is mandatory and prints during import.
- **Impact:** Business—deployment exposure/outage; user—session/transport risk; technical—tests/commands depend on unrelated credentials and local HTTP auth is broken by always-secure cookies.
- **Dependencies/files:** Confirm proxy/HTTPS topology; settings package/environment validation/tests.
- **Implementation outline:** Base/dev/prod settings or typed env layer; production fails closed on DEBUG/secret/hosts/HTTPS/proxy/cookies; development supports localhost; remove import print and unrelated mandatory OpenAI check; document HSTS staged rollout.
- **Tests required:** Run `check` and `check --deploy` in dev/prod matrices; prove missing/weak secrets and production DEBUG fail startup; cover proxy HTTPS/CSRF/session behavior.
- **Manual QA required:** Smoke-test local HTTP authentication and a production-like HTTPS/proxy deployment without exposing configuration.
- **Acceptance criteria:** Production security check has no unexplained warnings; local auth works over intended scheme; management commands not requiring AI start without its key; no secret output.
- **Change management:** No DB migration; staged environment rollout with HSTS caution; rollback uses previous deployment configuration without weakening secret/DEBUG; update AGENTS/environment/security.

### SEC-010 — Gate classroom and biometric enrollment pending verified consent

- **Metadata:** Category authorization/privacy; status Proposed; priority Next; severity P1; effort M for fail-closed gate, XL for complete product; confidence High; type confirmed insecure authorization/missing privacy control.
- **Evidence:** Public registration self-selects teacher; teacher role permits roster/photo/embedding management; likely minor names and audio-related data go to OpenAI; no consent/guardian/retention model.
- **Impact:** Business—child privacy/legal/reputation risk; user—unauthorized collection/use of biometric data; technical—no audit, opt-out, deletion, verified institution.
- **Dependencies/files:** Product/legal policy. Registration/profile, classroom guards/models/forms/templates/tests, privacy copy.
- **Implementation outline:** Immediate gate: staff-approved teacher flag and feature flag disabling new biometric enrollment unless approved consent record exists. Later work is `FEAT-008`, not part of this fail-closed task.
- **Tests required:** Cover student, unapproved-teacher, cross-teacher, absent/expired/revoked-consent denials; prove existing data remains private, read-only where intended, and deletable; cover approval audit.
- **Manual QA required:** Complete approved and non-approved teacher/student journeys using synthetic records.
- **Acceptance criteria:** Public role choice cannot grant classroom access; no photo/voice enrollment or recognition without explicit verified authorization/consent; revocation blocks future processing.
- **Change management:** Approval/consent migration likely; default disabled rollout; rollback keeps enrollment disabled; update privacy, registration, classroom, security, operations.

### SEC-011 — Add abuse limits for authentication, AI, lead, media, and token routes

- **Metadata:** Category defense-in-depth/cost; status Proposed; priority Next; severity P1; effort M; confidence High; type missing defense and confirmed unmetered endpoints.
- **Evidence:** No rate-limit library/config; public chat/motivation/lead routes and login/registration are unbounded; Realtime tokens have no usage/concurrency ledger; media/OCR lacks size/dimension caps.
- **Impact:** Business—AI/hosting cost and denial of service; user—brute force/spam/degraded service; technical—sync workers/resources exhausted.
- **Dependencies/files:** Cache/limit store decision; endpoint decorators/services, upload settings, tests, operational metrics.
- **Implementation outline:** Per-IP/account/feature limits with trusted proxy handling; login backoff; input/body/file bounds; Realtime concurrent/minute caps via `AI-002`; safe 429 and retry headers; admin exemptions explicit/audited.
- **Tests required:** Cover limit boundaries, bursts, concurrency, trusted proxy/IPv6, reset windows, anonymous-session churn, and no external call after rejection.
- **Manual QA required:** Run a controlled non-production load test and inspect rate-limit metrics and user-facing 429 behavior.
- **Acceptance criteria:** Every costly/auth endpoint has documented server-enforced limits and metrics; oversized input fails before download/decode/provider call.
- **Change management:** Cache/ledger migration may be needed; deploy conservative limits with monitoring; rollback raises limits but retains hard safety caps; update AI/security/environment/support docs.

### SEC-012 — Minimize and expire raw payloads, messages, logs, and alerts

- **Metadata:** Category privacy/operations; status Proposed; priority Next; severity P1; effort L; confidence High; type confirmed over-retention/missing governance.
- **Evidence:** Full WhatsApp webhook/message/error payloads, OCR text, receipts, conversation copy and events are stored; Telegram receives PII/context; no retention schedule, data export map, or deletion propagation.
- **Impact:** Business—breach scope/compliance/storage cost; user—indefinite financial/conversation data; technical—duplicated sensitive data and noisy logs.
- **Dependencies/files:** Product/legal retention decisions; models/services/logging/admin/jobs/privacy policy.
- **Implementation outline:** Data inventory/classification; store required normalized fields only; redact secrets/credentials/content; retention timestamps and deletion jobs; account/lead deletion propagation; restrict admin; processor disclosures; incident-safe logging.
- **Tests required:** Scan fixtures/logs; cover retention time travel/jobs, deletion/export, minimum-data alerts, and backup-expiry behavior.
- **Manual QA required:** Review admin/alert permissions and sample redacted records with the privacy and operations owners.
- **Acceptance criteria:** Each sensitive field has purpose, owner, retention and delete rule; raw bodies/errors are not persisted by default; deletion is auditable and tested.
- **Change management:** Data migration/purge with protected backup/legal approval; staged retention jobs; rollback pauses deletion but never restores redacted secrets; update privacy/security/operations/data model.

### SEC-013 — Establish a browser content-security and dependency integrity policy

- **Metadata:** Category browser/supply chain; status Proposed; priority Later; severity P2; effort L; confidence High; type defense-in-depth.
- **Evidence:** Many inline scripts/styles and third-party Bootstrap, icons, fonts, CV/audio/model resources; several unpinned or without SRI; no CSP.
- **Impact:** Business—supply-chain/XSS blast radius; user—third-party tracking/compromise; technical—runtime availability and reproducibility.
- **Dependencies/files:** `SEC-006`, component extraction, asset hosting decision; templates/static/settings.
- **Implementation outline:** Inventory origins; self-host/pin critical dependencies; SRI where possible; remove inline handlers/styles/scripts with nonces/hashes as transition; deploy CSP report-only then enforce; add Permissions/Referrer policies.
- **Tests required:** Exercise the CSP report suite, tampered-asset failure, offline/classroom fallbacks, and assertions that required features are not blocked.
- **Manual QA required:** Run the supported browser matrix and inspect CSP/integrity reports for approved exceptions only.
- **Acceptance criteria:** Enforced documented CSP and locked critical assets; no broad unsafe directives without time-boxed exception; external processors disclosed.
- **Change management:** No migration; report-only staged deploy; rollback CSP policy only while keeping patched assets; update security/UX/environment.

### SEC-014 — Purge private historical Git objects after rotation

- **Metadata:** Category repository/privacy; status Proposed; priority Next after `SEC-005`; severity P1; effort L; confidence High; type confirmed historical exposure/operational task.
- **Evidence:** Git history contains databases, full data backups, and large media archives; current removal/ignore does not remove historical contents.
- **Impact:** Business—continued breach/distribution scope and clone cost; user—historical private data exposure; technical—large repository and irreversible coordination risk.
- **Dependencies/files:** Complete credential rotation, secure backup, repository-host/admin coordination, contributor communication. Entire Git history.
- **Implementation outline:** Identify path categories without exposing contents; legal/owner approval; use history-filter tooling on a protected mirror; verify refs/tags; force-push coordinated; invalidate old clones/forks/releases; document incident.
- **Tests required:** On a disposable fresh clone, run path/object scans, compare repository size, and execute application/test integrity checks; revoked credentials remain revoked regardless of result.
- **Manual QA required:** Obtain peer review of the rewrite map and recovery procedure before any coordinated force-push.
- **Acceptance criteria:** Approved sensitive paths absent from all authoritative refs; rotations complete; all collaborators re-clone; secure evidence/backup retained per policy.
- **Change management:** No DB migration; this is destructive repository deployment and requires explicit authorization; rollback from protected mirror only if integrity failure—privacy incident remains addressed; update incident/security/operations docs.

## Confirmed product and correctness defects

### BUG-001 — Establish one canonical offer price and duration

- **Metadata:** Category commercial correctness; status Proposed; priority Now; severity P1; effort S; confidence High; type confirmed defect; correct value Needs product-owner confirmation.
- **Evidence:** Advertisement/guide and WhatsApp/config/receipt logic use conflicting course prices; copy promises one year while access is permanent.
- **Impact:** Business—failed receipts, disputes, conversion loss; user—misleading purchase; technical—validation and UI drift.
- **Dependencies/files:** Product owner approves price/duration/refund/source. Settings/offer service, advertisement/guide/profile, WhatsApp prompts/replies/receipt tests.
- **Implementation outline:** Define one typed offer configuration consumed by web and deterministic WhatsApp copy; remove prompt literals; show currency/duration consistently; until `DATA-002`, do not claim enforced expiry.
- **Tests required:** Snapshot/unit tests assert every active surface reads the same configured offer and fails safely when it is missing.
- **Manual QA required:** Review the guest→paywall→WhatsApp copy journey in approved Kazakh/Russian variants.
- **Acceptance criteria:** No conflicting amount/duration in active code/templates/prompts; missing offer config fails safely; product approval recorded.
- **Change management:** No migration for copy/config; deploy jointly with support update; rollback uses prior canonical offer, not scattered literals; update project/UX/AI docs.

### BUG-002 — Separate social-content mode from lesson-grounded voice

- **Metadata:** Category AI/product; status Proposed; priority Next; severity P1; effort S; confidence High; type confirmed current-tree defect or intentional WIP requiring decision.
- **Evidence:** `mint_realtime_token` selects a lesson-agnostic content-creator prompt; `_teacher_instructions(lesson)` is unused; UI promises an AI lesson teacher.
- **Impact:** Business—premium promise/cost waste; user—selected lesson ignored; technical—one route has conflicting personas.
- **Dependencies/files:** Product-owner decision; `lessons/views.py`, URL/access if new creator route, tests/docs.
- **Implementation outline:** Default learner endpoint to versioned lesson-grounded prompt; if creator mode is desired, make separate staff-only endpoint/UI/entitlement and tests; preserve user-authored prompt content during decision.
- **Tests required:** A mocked learner token request contains the selected lesson, the creator route is unavailable to learners, and prompt snapshots/evaluations pass.
- **Manual QA required:** Run an authorized Realtime sandbox session and confirm the persona stays lesson-grounded.
- **Acceptance criteria:** Each route has one documented audience/persona/data scope; lesson voice uses selected lesson; no commented toggle determines production behavior.
- **Change management:** No migration; feature flag staged; rollback selects last approved prompt version; update AI/contracts/project/UX.

### BUG-003 — Replace device-cookie lock failure with recoverable device management

- **Metadata:** Category auth/UX; status Proposed; priority Next; severity P2; effort M; confidence High; type confirmed defect/design weakness.
- **Evidence:** Middleware logs out before redirect; lock view only reads expiry for authenticated user; missing cookie creates devices, copied cookie bypasses; existing `last_seen` is not refreshed.
- **Impact:** Business—support burden; user—five-day self-denial with no detail/recovery; technical—multiple DB queries each request and race risk.
- **Dependencies/files:** Device/security policy decision; middleware/models/profile/templates/tests, possible migration.
- **Implementation outline:** Preserve signed lock context or authenticated recovery; device list/revoke; secure cookie attributes; refresh timestamps; prune stale devices; avoid punitive cookie counting as primary control.
- **Tests required:** Cover cookie deletion/copy, concurrent and stale devices, revoke, lock expiry, and authorization boundaries.
- **Manual QA required:** Complete mobile multi-device lock, explanation, revoke, and recovery journeys.
- **Acceptance criteria:** User sees accurate reason/expiry and can recover through approved flow; no lock through simple cookie churn; device operations are auditable.
- **Change management:** Index/timestamp migration possible; monitor lock rates; rollback disables automatic lock rather than trapping users; update security/UX/access docs.

### BUG-004 — Make quiz completion continue and retake correctly

- **Metadata:** Category learning UX; status Proposed; priority Next; severity P2; effort S; confidence High; type confirmed defect.
- **Evidence:** Backend returns `next_lesson`; browser ignores it. Completion reload calls a passed attempt and renders completion again, so “retake” is not a retake.
- **Impact:** Business—reduced lesson continuation/retention; user—dead end/confusing control; technical—frontend/backend contract unused.
- **Dependencies/files:** Decide whether passed quiz retake creates practice-only run; lesson template/JS, quiz endpoint/tests.
- **Implementation outline:** Add next-lesson CTA; label review vs retake; implement safe reset/practice semantics without removing authoritative pass; accessible completion summary.
- **Tests required:** Cover passed and last-lesson states, reload, review/retake, duplicate submissions, and authorization.
- **Manual QA required:** Complete the quiz pass→next and retry flows with keyboard and mobile input.
- **Acceptance criteria:** Pass offers working next action; retake has documented behavior and cannot revoke/duplicate unlock; analytics event hooks ready.
- **Change management:** No migration unless practice attempts are added later; normal deploy; rollback retains next link at minimum; update contracts/UX/testing.

### BUG-005 — Correct auth feedback and phone input normalization

- **Metadata:** Category auth/activation; status Proposed; priority Next; severity P2; effort S; confidence High; type confirmed UX/correctness defect.
- **Evidence:** Login template does not render form errors; registration JavaScript prepends a country digit incorrectly for common local input; no non-field error summary/autocomplete hints.
- **Impact:** Business—registration/login abandonment; user—silent failure/invalid phone; technical—duplicate/non-canonical identity data.
- **Dependencies/files:** Canonical phone approach (`DATA-003`) for full fix; templates/forms/tests.
- **Implementation outline:** Render safe form/non-field errors and focus summary; normalize common Kazakhstan formats server-side; progressive JS formatting; autocomplete/password hints; preserve privacy.
- **Tests required:** Exercise the supported phone-format table, invalid login, server/JavaScript normalization parity, and accessible error markup.
- **Manual QA required:** Verify screen-reader announcements, no-JavaScript registration, and mobile keyboard/input behavior.
- **Acceptance criteria:** Every invalid auth submission explains the actionable error; accepted phones normalize consistently; JS and server agree.
- **Change management:** No migration for display/parser; deploy before phone dedupe; rollback retains server validation; update UX/testing.

## Data integrity and domain model

### DATA-001 — Make provider messages and webhook work idempotent

- **Metadata:** Category data/integration; status Proposed; priority Next; severity P1; effort M; confidence High; type confirmed race/data-integrity risk.
- **Evidence:** `WhatsAppMessage.meta_message_id` is indexed but not unique; code checks then creates; failures after inbound row creation return success and later retry is ignored; lead counters use read/modify/write.
- **Impact:** Business—duplicate/missed messages and approvals; user—multiple or absent replies; technical—non-deterministic webhook retries.
- **Dependencies/files:** `SEC-002`; WhatsApp models/migration/services/tests.
- **Implementation outline:** Normalize provider event/message key; dedupe existing rows; conditional unique constraint; atomic inbox state (`received/processing/succeeded/retryable/failed`); claim with transaction; idempotent outbound/provisioning keys; atomic counters.
- **Tests required:** Cover concurrent duplicate delivery, failure/retry/restart, status-before-message, replay, uniqueness constraints, and migration fixtures.
- **Manual QA required:** Replay representative provider payloads in a sandbox and inspect one resulting state transition and side-effect set.
- **Acceptance criteria:** Same provider event processed at most once; retryable failure can resume; completed side effects are not repeated; state is observable.
- **Change management:** Data migration and index lock planning; deploy schema before code claim logic; rollback keeps uniqueness/inbox records; update data/AI/operations/testing.

### DATA-002 — Introduce orders, verified payments, and expiring entitlements

- **Metadata:** Category commerce/data; status Proposed; priority Next after critical fail-closed work; severity P1; effort XL; confidence High; type missing domain/data-integrity risk.
- **Evidence:** Permanent `UserProfile.is_paid`; no order/payment/transaction/plan/expiry/refund/source/audit; WhatsApp lead links by phone.
- **Impact:** Business—cannot enforce sold duration/refunds/reconciliation; user—ambiguous access; technical—irreversible Boolean and no audit trail.
- **Dependencies/files:** Canonical offer (`BUG-001`), payment verification/product policy, `SEC-001`–`SEC-004`, phone identity. New models/services/admin/views/migrations/tests.
- **Implementation outline:** Immutable offer snapshot/order; payment record with provider/manual reference and unique idempotency key; approval actor/evidence; entitlement start/end/revoke/source; service API used by web/admin/WhatsApp; migrate existing paid flags as legacy entitlements with explicit assumptions.
- **Tests required:** Cover state transitions, duplicate transactions, expiry/time zones, refund/revoke, concurrency, and legacy migration/reconciliation.
- **Manual QA required:** Reconcile synthetic orders to entitlements and exercise pending, approved, expired, refunded, and revoked states in the UI/admin.
- **Acceptance criteria:** Access derives from active entitlement, every grant has source/actor/time/reference, duplicate payment cannot grant twice, one-year promise is enforceable.
- **Change management:** Multi-step migration/backfill with backup; shadow-read then cutover; rollback reads legacy snapshot without deleting new audit data; update all product/security/operations docs.

### DATA-003 — Canonicalize, verify, and safely unique account phones

- **Metadata:** Category identity/data; status Proposed; priority Next; severity P1; effort L; confidence High; type confirmed data-integrity/security risk.
- **Evidence:** `UserProfile.phone` is optional/non-unique; tracked aggregate shows duplicate groups; provisioning exact-matches phone and can bind entitlement to an unverified registration.
- **Impact:** Business—payment/support failures; user—another account can claim a phone/entitlement; technical—ambiguous linkage.
- **Dependencies/files:** Identity/verification product decision and secure OTP/provider; profile model/form/auth/WhatsApp service/migration/tests.
- **Implementation outline:** Canonical E.164 field, verification state/time/channel, deterministic dedupe review, conditional uniqueness for verified phones, challenge/rate limit, never auto-link unverified value.
- **Tests required:** Cover normalization, deduplication, ownership, OTP expiry/replay/rate limits, concurrent claims, and migration conflict reports.
- **Manual QA required:** Complete verification and recovery for supported phone formats and an ambiguous legacy duplicate case.
- **Acceptance criteria:** One verified phone maps to at most one active account; unverified strings cannot receive entitlements; ambiguous legacy rows require human resolution.
- **Change management:** Sensitive data migration with dry-run/report and no value logging; staged verification; rollback preserves verification audit; update privacy/auth/payment docs.

### DATA-004 — Model curriculum track, language, order, access, and publication explicitly

- **Metadata:** Category curriculum/data; status Proposed; priority Later; severity P2; effort XL; confidence High; type architectural/data risk.
- **Evidence:** Lesson primary-key ranges/slices encode five levels, free access, next lesson and Russian track; `current_lesson` is integer; no publication/version metadata.
- **Impact:** Business—unsafe content operations/localization limits; user—wrong locks/order; technical—deletion/import changes behavior.
- **Dependencies/files:** Product curriculum decisions, `CONTENT-001/002`; lesson/profile/quiz models, views/admin/templates/migrations/tests.
- **Implementation outline:** Track/language/level/order/stable slug/free/published/prerequisite fields and constraints; explicit progression selector; migrate IDs 1–300; compatibility redirects; stop using numeric ranges.
- **Tests required:** Cover migration mapping, gaps/duplicate order, track-specific access/progression, delete/reorder/publish, fixture import, and URL compatibility.
- **Manual QA required:** Compare representative legacy and migrated catalog/progress views for each supported track/language.
- **Acceptance criteria:** No active access/progression/level logic depends on numeric ID ranges; every published lesson has one explicit ordered track position.
- **Change management:** High-risk data migration with export/backup/shadow comparison; phased reads; rollback compatibility map; update architecture/content/project/UX.

### DATA-005 — Version explanations and replace generated media atomically

- **Metadata:** Category content/data/files; status Proposed; priority Later; severity P2; effort L; confidence High; type confirmed race/staleness risk.
- **Evidence:** Explanation stores only text/audio URL/time; regeneration deletes matching MP3s before new persistence; no source hash/model/prompt version/reviewer/status.
- **Impact:** Business—broken/stale learning content; user—missing/incorrect audio; technical—worker races/orphans and no reproducibility.
- **Dependencies/files:** Private/public storage direction, `ARCH-003`, content version decision; model migration, service/job, templates/admin/tests.
- **Implementation outline:** Generation record with source hash/prompt/model/status; write new object first; transactionally switch active reference; retain old until commit/retention; stale marker and approval.
- **Tests required:** Cover provider/file/DB failure, concurrent generation, stale sources, version rollback, orphan cleanup, and XSS-safe rendering.
- **Manual QA required:** Generate, approve, supersede, fail, and roll back a synthetic explanation/audio asset while inspecting DB/storage consistency.
- **Acceptance criteria:** Failed/concurrent generation never removes current good artifact; learner sees only approved version tied to source; provenance is queryable.
- **Change management:** Backfill legacy explanation as unknown provenance; storage migration; rollback keeps both versions; update AI/content/data/operations.

### DATA-006 — Reconcile legacy quiz state, question versions, and restore invariants

- **Metadata:** Category quiz/data/restore; status Proposed; priority Later; severity P2; effort L; confidence High; type confirmed legacy-integrity risk.
- **Evidence:** Aggregate attempt fields coexist with answer-authoritative state; historical passes lack answer backfill; question generation can duplicate or become stale; tracked attempt data conflicts with current uniqueness and has no answer fixture.
- **Impact:** Business—unreliable learning analytics; user—pass/progress can change unexpectedly; technical—restore, regrade, and content edits produce inconsistent state.
- **Dependencies/files:** `CONTENT-001`, `DATA-004`; quiz models/migrations/services/import validator/tests.
- **Implementation outline:** Document grandfathered passes; introduce question/content version policy; validate cross-lesson writes outside views; prevent concurrent duplicate generation; define whether edits snapshot or invalidate attempts; produce a dry-run legacy report without fabricating answers.
- **Tests required:** Cover legacy passes, question add/remove, concurrent generation, model-level cross-lesson writes, migrated restore, regrade/version transitions, and no progress loss.
- **Manual QA required:** Inspect a representative legacy learner before/after migration and complete a versioned quiz/review journey.
- **Acceptance criteria:** Legacy state has an explicit non-invented policy; new attempts bind to a known question/content version; restore passes current constraints; edits cannot silently corrupt progress.
- **Change management:** Likely question/version migration; backup/dry-run and shadow report; rollback retains legacy flags/version references; update contracts/content/data/testing.

## Architecture and performance

### ARCH-001 — Centralize entitlement and lesson-access policy

- **Metadata:** Category architecture/authorization; status Proposed; priority Next; severity P1; effort L; confidence High; type architectural risk with confirmed access gaps.
- **Evidence:** Course/free/teacher/session/voice/translator rules are duplicated across `UserProfile`, `lesson_list`, `lesson_detail`, quiz/chat/vocabulary/token views, profile cards, templates, and WhatsApp mutations; quiz/chat/vocabulary endpoints bypass page policy.
- **Impact:** Business—revenue leakage/support; user—inconsistent denial/unlock; technical—every access change risks regression/IDOR.
- **Dependencies/files:** Critical security tasks and approved access matrix; models, a focused policy/service module, all affected views/templates/tests.
- **Implementation outline:** Define typed capability decisions (`view_lesson`, `take_quiz`, `use_voice`, etc.) with reason codes; one selector for curriculum/progress; call in every server endpoint; UI consumes decisions but does not enforce them.
- **Tests required:** Matrix-test guest/unpaid/paid/expired/teacher/staff access across every route, direct URL, session, and missing-profile case, with a query-count guard.
- **Manual QA required:** Walk the representative catalog, lesson, quiz, voice, translator, profile, and classroom paths for each approved role/state.
- **Acceptance criteria:** One documented policy owns capability decisions; all protected endpoints call it; direct APIs and UI agree; denials are safe and localized.
- **Change management:** No migration initially; feature flag/shadow comparison; rollback to previous read path only with tests and logs; update architecture/access/security/UX.

### ARCH-002 — Split orchestration from oversized views and WhatsApp services

- **Metadata:** Category architecture/maintainability; status Proposed; priority Later; severity P2; effort L per extraction slice; confidence High; type maintainability/change-risk issue.
- **Evidence:** `lessons/views.py` and `whatsapp_agent/services.py` exceed 1,300 lines and combine HTTP, policy, DB, prompts, files, external calls, copy and logging.
- **Impact:** Business—slow/risky iteration; user—regressions across unrelated features; technical—poor test isolation and hidden side effects.
- **Dependencies/files:** `TEST-001/002`, `ARCH-001`, fail-closed security fixes. Files depend on selected slice.
- **Implementation outline:** One session extracts one bounded use case (for example receipt intake, explanation generation, or quiz application service) behind existing behavior; explicit inputs/results/exceptions; no generic `utils` dump or speculative repository layer.
- **Tests required:** Add characterization coverage before extraction; assert unchanged routes/responses/queries; add service unit/failure cases and run the full suite.
- **Manual QA required:** Smoke-test the selected end-to-end journey and compare logs/side effects before and after extraction.
- **Acceptance criteria:** Selected view becomes HTTP adaptation only; transaction/external side effects have one owner; no unrelated refactor; metrics/tests remain.
- **Change management:** No migration unless chosen slice needs one; deploy behavior-preserving; rollback revert extraction; update codebase map and task-specific docs.

### ARCH-003 — Centralize versioned AI model and prompt configuration

- **Metadata:** Category AI architecture; status Proposed; priority Later; severity P2; effort M; confidence High; type maintainability/operational risk.
- **Evidence:** Text models and prompts are inline across views/services; Realtime model alone is shared; no prompt ID/version/owner/evaluation.
- **Impact:** Business—cost/brand/learning drift; user—inconsistent personas; technical—untestable toggles and duplicated facts.
- **Dependencies/files:** `BUG-001`, `BUG-002`, `SEC-006`; new focused prompt/config module, views/services/tests.
- **Implementation outline:** Named prompt definitions with version, audience, trusted data builder and approved model settings; central text model env validation; commercial facts passed as trusted config; snapshot/evaluation fixtures.
- **Tests required:** Cover prompt snapshots, lesson-data delimiter/injection cases, invalid model configuration fail-fast, feature-specific selection, and rollback version.
- **Manual QA required:** Review prompt/model metadata and run a controlled sample for each affected AI feature.
- **Acceptance criteria:** Active model/prompt choice is not hard-coded in view bodies; every request logs safe prompt version/model/feature without content; old prompt is rollbackable.
- **Change management:** No data migration; feature flags per prompt version; rollback selects prior version; update AI/contracts/project docs.

### PERF-001 — Move authenticated webhook work to an idempotent background pipeline

- **Metadata:** Category performance/reliability; status Proposed; priority Next after `SEC-002`/`DATA-001`; severity P1; effort L; confidence High; type confirmed scalability/reliability risk.
- **Evidence:** One synchronous Gunicorn request can store data, call OpenAI/Meta/Telegram, download media, parse PDF, resize/OCR images, and provision access; provider acknowledgement can time out.
- **Impact:** Business—lost/duplicate leads and downtime; user—slow/duplicate/missed replies; technical—worker starvation and weak retries.
- **Dependencies/files:** Signed webhook and inbox idempotency, queue choice, observability; services/models/settings/deploy/worker/tests.
- **Implementation outline:** Webhook validates and persists bounded inbox transaction then acknowledges; worker claims events, runs state machine with deadlines/retry/backoff/dead letter; outbox sends idempotently; receipt approval remains fail-closed.
- **Tests required:** Simulate crashes at every stage, duplicate delivery, retry exhaustion, ordering, worker restart, poison media, and load/latency boundaries.
- **Manual QA required:** Operate a non-production worker backlog through pause, retry, dead-letter inspection, and recovery without duplicate sends.
- **Acceptance criteria:** Webhook acknowledgement performs no slow external/OCR work; work resumes safely; operators see backlog/failures; no duplicate side effects.
- **Change management:** Inbox/job schema migration and worker deployment; dual-run/shadow without duplicate sends; rollback pauses consumer while retaining jobs; update architecture/environment/operations.

### PERF-002 — Bound queries, payloads, and catalog/vocabulary/message collections

- **Metadata:** Category performance; status Proposed; priority Before growth; severity P2; effort M; confidence High; type future scaling risk with confirmed unbounded paths.
- **Evidence:** WhatsApp loads all lead messages before slicing; vocabulary loads all course text/words; lesson stages issue multiple slices; profile/admin calculations and raw event history grow; no product pagination.
- **Impact:** Business—latency/hosting cost; user—slow mobile pages; technical—memory/query growth at 1k–10k users.
- **Dependencies/files:** Analytics/profiling baseline; selectors/views/templates/models/index migrations if measured.
- **Implementation outline:** Query last eight messages at DB; paginate/search vocabulary and operational histories; evaluate all lessons once or explicit queries; add indexes only from query plans; set payload caps.
- **Tests required:** Add `assertNumQueries`, representative 250/300-lesson and large-message fixtures, response size/time budgets, and database-plan assertions where stable.
- **Manual QA required:** Inspect production-like database explain plans and page behavior on realistic large datasets.
- **Acceptance criteria:** No request materializes an unbounded user/event/message collection; documented query/payload budgets pass; behavior remains correct.
- **Change management:** Optional concurrent index migration; can deploy incrementally; rollback removes new selector but keeps safe indexes; update technical/testing docs.

## Deployment and operations

### DEVOPS-001 — Upgrade to a supported Django/Python baseline

- **Metadata:** Category dependencies/security; status Proposed; priority Now/Next; severity P1; effort L; confidence High; type confirmed vulnerable/unsupported dependency risk.
- **Evidence:** Environment and requirements pin Django 5.1.6; 5.1.7 fixed a moderate CVE in 5.1.6 and 5.1 ended support 2025-12-03. Python 3.10.12 reaches end of support 2026-10.
- **Impact:** Business—unpatched exposure and harder hosting; user—security/reliability risk; technical—growing upgrade gap.
- **Dependencies/files:** Critical behavior tests, runtime/host compatibility. Requirements, settings, templates/static compatibility, CI/deploy docs.
- **Implementation outline:** Target current patched Django 5.2 LTS on a supported Python (product/host selects 3.12+); review every intervening release/deprecation; update in isolated branch; no unrelated refactor.
- **Tests required:** Run the full suite, system/deploy checks, migration dry run, dependency security scan, and supported-database integration tests.
- **Manual QA required:** Smoke-test auth, admin, static/media handling, MySQL deployment, and supported browsers on the upgraded artifact.
- **Acceptance criteria:** Supported patched versions pinned; all gates pass; deployment/rollback rehearsed; no generated migration unless model state genuinely changed.
- **Change management:** Dependency/runtime deployment; database backup; canary; rollback to last secure supported artifact—not unsupported 5.1 as a long-term plan; update AGENTS/environment/testing/security.

### DEVOPS-002 — Create a reproducible dependency, runtime, and environment baseline

- **Metadata:** Category DevOps; status Proposed; priority Next; severity P1; effort M; confidence High; type confirmed reproducibility risk.
- **Evidence:** Documented `./venv` path fails; no Python runtime declaration/lock/build; MySQL and PostgreSQL drivers installed but undeclared; installed `pypdf` violates requirements range; FFmpeg/Tesseract packages are external; unused packages remain.
- **Impact:** Business—failed deploys; user—feature outages; technical—works-on-one-machine dependency drift.
- **Dependencies/files:** `DEVOPS-001` target versions. Requirements/lock strategy, runtime declaration, sanitized `.env.example`, build docs/CI.
- **Implementation outline:** Separate direct runtime/dev dependencies; include chosen DB driver; pin/lock resolved versions with hashes where platform supports; declare Python/system packages; env schema names/placeholders only; remove unused dependencies after proof.
- **Tests required:** In a fresh clean environment run install, `pip check`, tests, checks, compile, MySQL configuration import, and path-safe secret scans.
- **Manual QA required:** Execute OCR/TTS/external-binary preflight and follow the documented setup without global packages or private files.
- **Acceptance criteria:** A clean documented build reproduces versions and passes gates without global packages or private files; missing optional service produces actionable check.
- **Change management:** No DB migration; build new artifact/canary; rollback previous lock artifact; update README/AGENTS/environment/testing.

### DEVOPS-003 — Add health, structured redacted logging, error tracking, and service metrics

- **Metadata:** Category observability; status Proposed; priority Next; severity P2; effort M; confidence High; type operational recommendation required before growth.
- **Evidence:** Console-only logs, no health/readiness/metrics/error tracker; Telegram business alerts are not monitoring; raw payload/error content can leak.
- **Impact:** Business—slow incident detection; user—long outages; technical—no latency/error/cost visibility.
- **Dependencies/files:** `SEC-012` redaction policy and deployment platform; settings, health view, logging/instrumentation, tests/runbook.
- **Implementation outline:** Liveness without dependencies; readiness for DB/storage/config as appropriate; request correlation; structured redacted logs; error tracker; metrics for requests/jobs/provider latency/errors, queue depth, Realtime mint/minutes and receipt states.
- **Tests required:** Simulate DB/provider failures; cover secret/PII redaction fixtures and health endpoint access, authorization, caching, and cost limits.
- **Manual QA required:** Run an alert-routing drill and verify operators can diagnose the synthetic incident from redacted telemetry.
- **Acceptance criteria:** Operators can detect/localize key failures without private payloads; health endpoints are cheap and do not expose config; alert owner defined.
- **Change management:** No migration unless metric store; staged alert thresholds; rollback exporter while retaining redacted logs/health; update operations/security.

### DEVOPS-004 — Establish database/media backup, restore, rollback, and incident drills

- **Metadata:** Category resilience/operations; status Proposed; priority Next; severity P1; effort M; confidence High; type confirmed missing control/data-loss risk.
- **Evidence:** No backup script/schedule/retention/encryption/restore test; code rollback notes are not data restore; local media contains generated and sensitive files.
- **Impact:** Business—irrecoverable course/user/payment loss; user—lost progress/private files; technical—unsafe migrations/deployments.
- **Dependencies/files:** Confirm production DB/media topology and retention/legal requirements; operations scripts/config/docs, not application secrets.
- **Implementation outline:** Automated encrypted DB and media/object backups; separate private/public classes; retention and access; restore to isolated environment; schema/media consistency checks; RPO/RTO and incident ownership.
- **Tests required:** Automate backup integrity, row/file/checksum sampling, least-privilege checks, and restoration validation where feasible.
- **Manual QA required:** Complete a timed isolated restore and migration-rollback drill with revoked credentials and record RPO/RTO results.
- **Acceptance criteria:** Approved RPO/RTO, monitored backups, successful recent restore drill, least-privilege encrypted storage, operator checklist.
- **Change management:** External infrastructure; no app migration; never overwrite production during drill; rollback disables faulty backup job but preserves prior backups; update operations/implementation plan.

### DEVOPS-005 — Automate guarded build, release, smoke, and rollback stages

- **Metadata:** Category release engineering; status Proposed; priority Next; severity P2; effort M; confidence High; type confirmed operational gap.
- **Evidence:** Only a basic `Procfile` exists; no release phase/CI deploy definition records tests, migration review, `collectstatic`, revision, smoke, or rollback.
- **Impact:** Business—manual deployment outage risk; user—inconsistent releases; technical—unknown code/schema/static state and non-repeatable rollback.
- **Dependencies/files:** `DEVOPS-001/002/003/004`, deployment-platform facts; CI/release config and operations docs.
- **Implementation outline:** Build immutable artifact; require gates; record revision/dependencies/migrations; backup stop condition; reviewed migrate and static stage; canary/health smoke; operator approval and prior-artifact rollback.
- **Tests required:** Pipeline tests cover a successful release and intentional check, migration, static, health, and secret-output failures.
- **Manual QA required:** Run a staging release and rollback drill, then confirm artifact/schema compatibility and operator visibility.
- **Acceptance criteria:** One documented pipeline produces traceable artifact and prevents release on failed gates; operator can identify/restore prior compatible revision.
- **Change management:** Infrastructure config only; migration execution is per reviewed release; rollback artifact/schema compatibility documented; update environment/testing/implementation plan.

### DEVOPS-006 — Enforce secret and operational-data hygiene in developer/deploy workflows

- **Metadata:** Category DevOps/security; status Proposed; priority Now/Next; severity P1; effort M; confidence High; type confirmed process gap.
- **Evidence:** Credential/private-data paths reached Git; local secret/database permissions were permissive; no env example, secret scan, pre-commit/CI data policy, or incident workflow.
- **Impact:** Business—repeat credential/privacy incidents; user—private data in clones/artifacts; technical—unsafe fixtures/logs/backups.
- **Dependencies/files:** `SEC-005`, `SEC-012`, `SEC-014`, `CONTENT-001`, `TEST-004`; repo/CI/deploy configs and runbooks.
- **Implementation outline:** Path/content denylist, secret scan current tree/history, synthetic fixture policy, protected file permissions, artifact exclusions, redacted diagnostics, rotation/incident checklist and owner.
- **Tests required:** Seeded fake secrets/private fixtures are blocked; clean clones/artifacts exclude local data; permission and log-redaction checks emit no live values.
- **Manual QA required:** Review developer/deploy workflows and rehearse the redacted incident response with synthetic credentials.
- **Acceptance criteria:** Automated gates prevent the known incident classes; local/deploy secret files are least-privilege; response workflow is documented and tested.
- **Change management:** No DB migration; introduce gates with reviewed baseline; rollback scanner version but retain denylist/policy; update AGENTS/security/operations/testing.

### MEDIA-001 — Introduce classified storage abstraction and reconciliation

- **Metadata:** Category media architecture/operations; status Proposed; priority Next; severity P1; effort L; confidence High; type confirmed lifecycle/scaling risk.
- **Evidence:** Direct filesystem glob/open for explanation audio, mixed private/public `MEDIA_ROOT`, FileFields without deletion jobs, no storage reconciliation or multi-instance guarantee.
- **Impact:** Business—privacy/data loss and horizontal-deploy blocker; user—missing or retained files; technical—DB/object divergence and racing replacement.
- **Dependencies/files:** `SEC-007`, `DEVOPS-002/004`; storage settings/services, media models/views/jobs/migrations/tests.
- **Implementation outline:** Classify public generated vs private sensitive objects; Django storage API with immutable keys; DB references/status; after-commit deletion; private access/signed URLs; reconciliation and backup/restore.
- **Tests required:** Cover authorized reads, direct denial, concurrent write/switch, physical deletion, missing/orphan reconciliation, multiple workers, and restore.
- **Manual QA required:** Exercise copy/check/cutover and rollback against production-like private/public storage classes.
- **Acceptance criteria:** Application does not rely on one local shared directory; every file class has access/retention/backup owner; DB/storage consistency can be audited and repaired.
- **Change management:** Object inventory/copy/check/cutover migration; dual-read temporarily; rollback keeps both stores private and old URLs compatible; update architecture/security/environment/classroom.

### REPO-001 — Remove proven dead code, dependencies, and configuration drift

- **Metadata:** Category repository hygiene; status Proposed; priority Later; severity P3; effort M; confidence High for visible dead paths, Medium for deployment usage; type maintainability/supply-chain issue.
- **Evidence:** Broken unused `chatgpt_helper.py`; historical empty consumer/routing; unused-looking Channels/Redis/DRF/database-url packages/config; duplicate template; tracked `.gitignore.save`; mixed line endings.
- **Impact:** Business—upgrade/security maintenance cost; user—indirect regression risk; technical—agents choose wrong paths and builds carry unused surface.
- **Dependencies/files:** `DEVOPS-001/002`, production-owner/process inspection, `TEST-004`; affected code/dependencies/config/templates.
- **Implementation outline:** Prove no import/runtime/deploy use; remove one coherent set per change; move manual diagnostics; remove duplicate/debris; document historical decisions; normalize future line endings without rewriting user WIP.
- **Tests required:** Verify the import graph, full tests, compile, static/deploy startup, and dependency/artifact diffs after each removal.
- **Manual QA required:** Smoke-test Realtime, OCR, and TTS paths when their dependency or code path is affected.
- **Acceptance criteria:** Removed paths have no caller/deploy use; dependency set reflects active direct requirements; no bulk unrelated formatting; canonical replacements documented.
- **Change management:** No migration; small reversible commits; rollback dependency/path only if verified consumer emerges; update codebase/environment/testing/docs audit.

## Test and quality foundation

### TEST-001 — Add adversarial payment, webhook, credential, and retention tests

- **Metadata:** Category tests/security; status Proposed; priority Now #6; severity P1; effort M; confidence High; type missing test foundation.
- **Evidence:** Forty tests pass, but none cover receipt validation/replay, webhook signatures, credential persistence, receipt approval, or private-data retention; existing tests entrench recipient mutation.
- **Impact:** Business/user/technical—critical fixes can regress silently.
- **Dependencies/files:** Can begin with current code to demonstrate failures; WhatsApp tests plus fixtures/builders.
- **Implementation outline:** Add fake signed webhook builder; forged/replayed receipt cases; no-grant assertions; destination and secret-redaction assertions; provider/timeouts/concurrency cases; remove unsafe expectations.
- **Tests required:** Regression cases fail against the characterized vulnerable behavior and pass only with tasks `SEC-001`–`SEC-004`; no network or private values.
- **Manual QA required:** Review adversarial fixtures/log output for realism and redaction; no live-provider exercise is required for this test-only task.
- **Acceptance criteria:** Each critical security acceptance criterion has positive and negative automated coverage; test logs are redacted and deterministic.
- **Change management:** Test-only/no migration; run in CI after `TEST-004`; rollback never removes regression tests without accepted-risk record; update testing/security.

### TEST-002 — Cover entitlement, paywall, classroom ownership, device lock, deletion, and token routes

- **Metadata:** Category integration tests; status Proposed; priority Next; severity P1; effort M; confidence High; type missing coverage.
- **Evidence:** No classroom/device/account-deletion/end-to-end access matrix tests; translator/classroom token contracts untested; quiz routes bypass policy.
- **Impact:** Business—revenue/privacy regressions; user—wrong access/lock; technical—architecture cannot be safely changed.
- **Dependencies/files:** Approved access matrix; lessons tests and factories.
- **Implementation outline:** Role/entitlement matrix across direct routes; cross-teacher IDOR; upload denial; device churn/expiry; deletion cascade/files; translator/classroom token payload and errors.
- **Tests required:** Run the full Django suite on SQLite plus selected MySQL CI, with route authorization, deletion/side-effect, and middleware/dashboard query assertions.
- **Manual QA required:** Inspect representative denial/recovery states for accurate localized copy and absence of private detail.
- **Acceptance criteria:** Every protected route has unauthenticated/unauthorized/owner/expired tests; deletion/access side effects proven.
- **Change management:** Test fixtures/migrations only if factories require schema; no deploy behavior; keep tests through refactor; update testing/architecture.

### TEST-003 — Add browser JavaScript, accessibility, and mobile flow tests

- **Metadata:** Category frontend QA; status Proposed; priority Before UX refactor; severity P2; effort L; confidence High; type missing coverage.
- **Evidence:** No JS/package/test config; critical quiz, PWA, modal, Realtime state and XSS behavior lives in browser; static audit found accessibility defects.
- **Impact:** Business—conversion/retention regressions; user—blocked keyboard/mobile use; technical—large templates/scripts lack safety net.
- **Dependencies/files:** Choose minimal browser runner after `DEVOPS-002`; test config and selected templates/JS.
- **Implementation outline:** End-to-end guest→lesson→quiz, auth errors, paywall, XSS, PWA logout cache, keyboard/focus/modal/timer, mobile viewport; mock Realtime/provider APIs.
- **Tests required:** CI headless journeys cover critical JavaScript flows, accessibility assertions, deterministic provider mocks, mobile/desktop widths, and screenshot baselines.
- **Manual QA required:** Run the separate real-device, keyboard, screen-reader, camera, and microphone checklist as applicable.
- **Acceptance criteria:** Critical journeys run deterministically at mobile/desktop; accessibility assertions and screenshots are reviewed; no live paid API.
- **Change management:** Dev dependencies/CI only; no migration; rollback runner version while keeping scenarios; update testing/UX.

### TEST-004 — Add CI, lint/type/format checks, coverage reporting, and secret scanning

- **Metadata:** Category quality/CI; status Proposed; priority Next; severity P2; effort M; confidence High; type missing engineering control.
- **Evidence:** No CI, project lint/type/format/coverage/pre-commit config; dead module has an import-time name error; mixed line endings and user diff make `git diff --check` noisy.
- **Impact:** Business—slow reviews; user—avoidable defects; technical—non-reproducible quality and secret regressions.
- **Dependencies/files:** `DEVOPS-002`; CI workflow/tool configs, `.editorconfig`/`.gitattributes` after preserving current user change.
- **Implementation outline:** Pinned CI environment; check, migration drift, full tests, compile, critical lint, targeted type checks, coverage baseline (ratchet not arbitrary high), secret/path scan and docs links; no autoformat in audit.
- **Tests required:** A clean-clone pipeline passes; intentionally failing migration, lint, type, format, test, coverage, and fake-secret fixtures are caught without private output.
- **Manual QA required:** Review required-check visibility, exception ownership, local command parity, and a failed-gate recovery drill.
- **Acceptance criteria:** Required checks run on every change with documented local equivalents; tool versions pinned; baseline exceptions owned/time-boxed.
- **Change management:** CI/config only; no migration; introduce warnings then required gates; rollback broken tool version, not all checks; update AGENTS/testing/environment.

## Content and UX

### CONTENT-001 — Remove private runtime fixtures and regenerate valid sanitized fixtures

- **Metadata:** Category content/privacy/repository; status Proposed; priority Next after `SEC-005`; severity P1; effort M; confidence High; type confirmed defect/privacy risk.
- **Evidence:** All seven fixtures are invalid JSON from settings output; four contain private runtime data; attempt/profile aggregates conflict with current constraints; no answer fixture.
- **Impact:** Business—privacy and failed restore; user—private identifiers in clones; technical—`loaddata` failure and misleading snapshots.
- **Dependencies/files:** Secure backup/owner decision on canonical lesson source; settings print fix via `SEC-009`; `lessons/fixtures`, tests/content docs.
- **Implementation outline:** Securely remove runtime fixtures from current tree; preserve only authorized off-repo backup; regenerate authored content/test fixtures with deterministic command and no stdout pollution; validate schema/private-field denylist/checksum.
- **Tests required:** Parse JSON and run `loaddata` in a disposable DB; verify counts/references/quiz start, secret/PII path/content scans, and reproducible clean export.
- **Manual QA required:** Inspect a representative authored fixture sample and confirm operational user/device/lead/attempt data is absent.
- **Acceptance criteria:** Repository fixtures are valid, documented, minimal, synthetic/authored only, and restore-tested; no runtime user/device/lead/attempt snapshot remains.
- **Change management:** No production DB mutation; Git history separately `SEC-014`; rollback from secure content export, never private fixture; update content/security/testing.

### CONTENT-002 — Build a dry-run content validator and impact report

- **Metadata:** Category content tooling; status Proposed; priority Later; severity P2; effort M; confidence High; type maintainability/content-quality issue.
- **Evidence:** Quiz parsing silently skips formatting, content has duplicate/localized overlap, no schema/track/version validation, imports are manual.
- **Impact:** Business—slow/risky content operations; user—broken/ambiguous lessons; technical—quiz/explanation/progress drift.
- **Dependencies/files:** `CONTENT-001`, curriculum metadata plan. New management command/service/tests; no direct data writes in dry-run.
- **Implementation outline:** Validate JSON/schema/IDs/encoding/required fields/vocabulary parsing/duplicates/HTML/language; report affected questions/explanations/progress; machine-readable and human summary; non-zero on errors.
- **Tests required:** Cover a golden valid package and every documented failure class, a large 300-lesson package, no-write dry run, and Kazakh/Russian Unicode.
- **Manual QA required:** Review validator reports with a content editor for actionable lesson/field references and safe waiver handling.
- **Acceptance criteria:** Content package cannot proceed without clean dry run or recorded waiver; report identifies exact lesson/field without private data.
- **Change management:** No migration; tool-only; rollback version while retaining validation requirement; update content/testing/AGENTS.

### CONTENT-003 — Version derived quiz, explanation, and prompt/content contracts

- **Metadata:** Category content architecture; status Proposed; priority Later; severity P2; effort L; confidence High; type confirmed staleness/change-risk issue.
- **Evidence:** Questions derive once from exact vocabulary formatting; explanations lack source/prompt/model version; current voice prompt can ignore the lesson; no publish workflow ties derived artifacts to authored content.
- **Impact:** Business—unsafe publishing and AI quality drift; user—stale/unrelated learning material; technical—cannot regenerate, compare, or roll back deterministically.
- **Dependencies/files:** `DATA-004/005/006`, `CONTENT-002`, `ARCH-003`; content models/services/admin/jobs/tests.
- **Implementation outline:** Published content revision; pre-publish derived quiz validation; source hashes; prompt/model versions and generation/review status; explicit stale state; creator route separated from learner route.
- **Tests required:** Cover parser variants, stale detection, reviewed-output preservation, permissioned regeneration, version rollback, and lesson-grounded prompt contracts.
- **Manual QA required:** Edit and republish a synthetic lesson, then inspect stale indicators, approval, regeneration, and coherent rollback.
- **Acceptance criteria:** Every active derived artifact identifies its source/version; content edit produces explicit validated regeneration/stale decision; rollback restores coherent lesson/quiz/explanation behavior.
- **Change management:** Multi-step content metadata migration; preserve old reviewed artifacts; rollback selects prior published revision; update content/AI/contracts/architecture.

### UX-001 — Rebuild the landing/paywall hierarchy around approved commercial truth

- **Metadata:** Category UX/conversion; status Proposed; priority after `BUG-001`; severity P2; effort M; confidence High; type conversion/clarity issue.
- **Evidence:** Root is a dense catalog; primary value/pricing lives in a non-semantic guide modal; unsupported promises and conflicting offers; CTA hierarchy splits register, lesson, guide, motivation, WhatsApp.
- **Impact:** Business—lower activation/conversion/trust; user—unclear first action; technical—copy duplicated in templates/prompts.
- **Dependencies/files:** Approved offer/value/trust claims and analytics; lesson list/advertisement/guide/shared components.
- **Implementation outline:** Mobile-first concise value, target learner/outcomes/evidence, one primary free-lesson CTA, secondary login, transparent canonical offer and trust/privacy link; remove unverified guarantees.
- **Tests required:** Snapshot/content-source and event-schema tests prove active surfaces share approved commercial truth and emit the defined funnel events; KPI baseline Needs analytics data.
- **Manual QA required:** Review the visitor/paywall hierarchy and CTA journey on mobile, desktop, and keyboard with approved Kazakh/Russian copy.
- **Acceptance criteria:** Visitor can identify audience/value/free next step/price-duration without modal; all claims approved and consistent; CTA events defined.
- **Change management:** No migration; A/B only after analytics/traffic; rollback to approved copy; update project/UX/feature docs.

### UX-002 — Add role-aware activation and resume journeys

- **Metadata:** Category UX/activation; status Proposed; priority Later; severity P2; effort M; confidence High; type missing product flow.
- **Evidence:** Registration redirects to catalog; no onboarding completion, resume card/current stage expansion, teacher guided setup, or early-success instrumentation.
- **Impact:** Business—lower first-lesson/classroom activation and retention; user—does not know next step; technical—progress exists but is not orchestrated.
- **Dependencies/files:** Verified role (`SEC-010`), analytics (`FEAT-002`), access policy; registration/catalog/profile/classroom templates/views.
- **Implementation outline:** Student resume/first lesson CTA and short success path; approved teacher invite/setup checklist; preserve skip; state derived from server progress/readiness.
- **Tests required:** Browser journeys cover new/returning, paid/unpaid, student/verified-teacher states and correct resume/authorization destinations; KPIs Need analytics data.
- **Manual QA required:** Complete those activation/resume journeys on representative mobile layouts and review next-action clarity.
- **Acceptance criteria:** Each approved role reaches one clear next action and first value; returning learner resumes accurately; no unauthorized role promotion.
- **Change management:** Optional onboarding-state migration; staged events; rollback preserves direct navigation; update UX/project/analytics dictionary.

### UX-003 — Deliver mastery-oriented quiz review and continuation

- **Metadata:** Category UX/learning; status Proposed; priority Next; severity P2; effort M including `BUG-004`; confidence High; type learning/retention opportunity.
- **Evidence:** Five-second timer, no accommodation, mistake explanation/history, answer review or next action; retake broken.
- **Impact:** Business—lower completion/retention; user—stress without mastery; technical—server has answer data but UI discards learning value.
- **Dependencies/files:** `BUG-004`, analytics; quiz endpoints/template and possibly review model later.
- **Implementation outline:** Accessible timer/default accommodation decision, per-answer feedback, mistake review, completion summary, working retry/practice, next lesson; keep server authoritative.
- **Tests required:** Cover correct/wrong, optional timeout, restart, pass, review/retry, continuation, and state consistency; KPI Needs analytics data.
- **Manual QA required:** Complete keyboard/mobile quiz journeys and obtain pedagogy review of feedback and timing copy.
- **Acceptance criteria:** Learner knows why, can review mistakes, retry without corrupting pass, and continue; accessibility requirements met.
- **Change management:** No migration for MVP; feature flag; rollback keeps correctness fixes; update contracts/UX/feature docs.

### UX-004 — Establish the accessibility baseline and shared semantic patterns

- **Metadata:** Category accessibility/frontend; status Proposed; priority Later; severity P2; effort L; confidence High; type systemic accessibility issue.
- **Evidence:** Zoom disabled, click-only stage/explanation divs, non-semantic modals/chat, missing names/focus/live regions/reduced motion, short timer, inconsistent focus CSS.
- **Impact:** Business—excludes users and increases redesign cost; user—keyboard/low-vision/cognitive barriers; technical—duplicate inaccessible implementations.
- **Dependencies/files:** `TEST-003`; base/templates/CSS/JS/shared components.
- **Implementation outline:** Restore zoom; semantic buttons/tabs/dialogs/headings/landmarks; focus trap/return; labels/names/live regions; reduced motion/contrast/touch targets; timer accommodation; component checklist.
- **Tests required:** Automated WCAG/semantic checks cover critical templates and reusable patterns; KPI baseline Needs analytics data.
- **Manual QA required:** Run keyboard, screen-reader, 200% zoom/reflow, mobile, high-contrast, and reduced-motion tasks.
- **Acceptance criteria:** Critical journeys meet agreed WCAG 2.2 AA criteria with documented exceptions; reusable patterns replace one-off controls.
- **Change management:** No migration; incremental pages; rollback individual component only; update UX/testing/AGENTS.

### UX-005 — Add account recovery, consent, and actionable auth states

- **Metadata:** Category UX/auth; status Proposed; priority Next; severity P2; effort M; confidence High; type missing flow.
- **Evidence:** No password reset/recovery URLs; registration has no terms/privacy acknowledgement or verification; login errors hidden; account lock recovery weak.
- **Impact:** Business—abandonment/support; user—lost account/no informed consent; technical—admin/WhatsApp workarounds.
- **Dependencies/files:** `SEC-004`, `DATA-003`, approved privacy/terms/age policy; auth URLs/forms/templates/tests.
- **Implementation outline:** Secure one-time recovery via verified channel, privacy/terms version acknowledgement, actionable lock state, error summaries and support escalation; rate limit.
- **Tests required:** Cover token expiry/replay, enumeration resistance, rate limits, wrong-user access, consent-version persistence, and session invalidation.
- **Manual QA required:** Complete mobile, keyboard, and no-JavaScript recovery/consent flows and obtain policy-copy approval.
- **Acceptance criteria:** User can safely recover without reusable admin-sent password; consent version is recorded where required; auth failures are clear without account enumeration.
- **Change management:** Consent/audit migration likely; staged channels; rollback disables recovery requests safely; update privacy/auth/UX/operations.

## Confirmed UX audit traceability

`UX-006`–`UX-012` remain stable confirmed-audit IDs in `UX_UI_AUDIT.md`. They are consolidated into the executable tasks and feature specifications below because their implementation boundaries overlap existing security, data, and product work; creating duplicate cards would split ownership and acceptance evidence.

| Confirmed audit ID | Canonical executable scope | Why consolidated |
| --- | --- | --- |
| `UX-006` — Reusable component and template system | `UX-004`; `FEAT-009` | `UX-004` owns semantic shared patterns and tests; `FEAT-009` owns the product-wide shell/component migration. |
| `UX-007` — Privacy and consent disclosures | `SEC-010`, `SEC-012`, `UX-005`; `FEAT-008` | Disclosure cannot be separated safely from verified consent, data minimization/retention, auth acknowledgement, and the classroom biometric lifecycle. |
| `UX-008` — Catalog state, search, and current lesson | `ARCH-001`, `UX-002`; `FEAT-003`, `FEAT-005` | Central access policy owns truthful lock/current states; activation/resume and mastery continuation own learner navigation. Search is an advanced catalog slice, not a parallel entitlement task. |
| `UX-009` — Lesson, chat, and voice loading/error/empty states | `SEC-006`, `BUG-002`, `AI-001`; `FEAT-007` | Safe rendering, correct voice grounding, AI failure policy, and the controlled voice journey share one acceptance boundary. |
| `UX-010` — Classroom readiness and friendly denials | `SEC-010`; `FEAT-008` | The immediate fail-closed authorization/consent gate precedes and is reused by the complete readiness, fallback, deletion, and reporting feature. |
| `UX-011` — Localization consistency | `DATA-004`, `UX-004`; `FEAT-009` | Explicit language/track data and the shared accessible localization system must replace the same ID-derived/mixed-language behavior together. |
| `UX-012` — PWA and offline safety | `SEC-008`; `FEAT-010` | `SEC-008` removes unsafe private caching first; `FEAT-010` defines the later consent-safe, user-scoped offline product. |

## AI operational quality

### AI-001 — Validate, ground, and evaluate AI outputs and prompts

- **Metadata:** Category AI quality/security; status Proposed; priority Later; severity P2; effort M; confidence High; type hallucination/prompt-injection risk.
- **Evidence:** Inline prompts, untrusted lesson/roster/transcript data, no structured output/language/length validation, no moderation/evaluation set or learner feedback.
- **Impact:** Business—brand/learning harm; user—incorrect/inappropriate teaching; technical—silent prompt drift and unsafe persistence.
- **Dependencies/files:** `SEC-006`, `ARCH-003`; prompt definitions, validators, evaluation fixtures/admin review/tests.
- **Implementation outline:** Trusted-data delimiters/roles, language/length/format checks, age/safety policy, curated Kazakh-English evaluation set, human approval for published explanations, report/feedback loop.
- **Tests required:** Use injection, adversarial, empty, HTML, off-language, and hallucination fixtures with deterministic evaluation thresholds; no live call in the unit suite.
- **Manual QA required:** Authorized reviewers score the controlled evaluation set and approve grounding/output-policy changes.
- **Acceptance criteria:** Each AI feature has documented grounding/output policy and minimum evaluation gate; unsafe/unparseable output fails safely and is not published.
- **Change management:** Optional generation metadata migration; prompt version rollout; rollback prior approved prompt; update AI/security/content/testing.

### AI-002 — Add server-authoritative AI usage, concurrency, cost, and latency controls

- **Metadata:** Category AI economics/reliability; status Proposed; priority Before growth; severity P1; effort L; confidence High; type confirmed missing cost control.
- **Evidence:** Public text endpoints and repeated token minting; only bypassable browser timers; no usage records, caps, budget alerts or cost-per-feature telemetry.
- **Impact:** Business—unbounded cost and unknown margin; user—capacity outages/unfair access; technical—cannot enforce sold packages or investigate abuse.
- **Dependencies/files:** Entitlement/offer policy, analytics/observability, limit store; usage model/service/token/text views/jobs/tests.
- **Implementation outline:** Record feature/user/request/session/start/end/provider usage; atomic concurrent-session lease; daily/monthly minutes/call limits; hard server caps and budget alerts; privacy-minimal telemetry; reconcile provider usage where available.
- **Tests required:** Cover concurrent mint/start, abandoned/crashed-session expiry, cap boundaries/time zones, anonymous abuse, provider error/no-charge semantics, and cost aggregation.
- **Manual QA required:** Exercise an authorized sandbox allowance, denial, recovery, and reconciliation flow and inspect cost/latency dashboards.
- **Acceptance criteria:** Server can answer who may start and why, enforce concurrency/minutes/calls, and report cost/latency by feature without retaining unnecessary content.
- **Change management:** Usage/lease migration; shadow count before enforcement; rollback enforcement thresholds while retaining observation/hard emergency cap; update AI/offer/operations/UX.

## Product feature opportunities

Feature IDs are opportunity/epic records, not authorization to implement. Their complete required fields—problem, user, flow, MVP/advanced scope, modules/models/APIs/jobs/analytics, privacy/security/cost, impacts, KPIs, acceptance and dependencies—are canonical in [FEATURE_ROADMAP.md](FEATURE_ROADMAP.md). They are part of this unified backlog and must be decomposed into bounded Task IDs before coding.

| Feature ID | Opportunity | Status | Priority | Effort | Severity if absent | Confidence | Foundation tasks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FEAT-001` | Commercial truth, order and entitlement foundation | Proposed strategic | Next | L/XL | P1 current integrity gap | High | SEC-001–004, BUG-001, DATA-002/003 |
| `FEAT-002` | Privacy-safe analytics foundation | Proposed quick strategic foundation | Next | M | P2 decision gap | High | SEC-012, event/consent decisions |
| `FEAT-003` | Role-aware activation, recovery, resume and device center | Proposed quick win bundle | Later | M | P2 | High | SEC-010, BUG-003/005, UX-002/005 |
| `FEAT-004` | Versioned course authoring and content-QA workspace | Proposed strategic | Later | L/XL | P2 | High | CONTENT-001/002, DATA-004/005 |
| `FEAT-005` | Mastery-first lesson and quiz flow | Proposed quick win | Later | M | P2 | High | BUG-004, UX-003, analytics |
| `FEAT-006` | Personal vocabulary and spaced-review deck | Proposed strategic | Later | M | P3 opportunity | Medium | DATA-004, analytics, normalized vocabulary |
| `FEAT-007` | Lesson-grounded voice tutor with usage controls | Proposed strategic | Later | M/L | P1 current premium defect/cost gap | High | BUG-002, ARCH-003, AI-001/002, entitlements |
| `FEAT-008` | Consent-safe classroom readiness and session reports | Proposed long-term bet | Later | L/XL | P1 current privacy blocker | High | SEC-007/010/012, verified teachers, AI-002 |
| `FEAT-009` | Kazakh-first localization and accessible component system | Proposed strategic | Later | L | P2 | High | DATA-004, UX-004, TEST-003 |
| `FEAT-010` | Safe offline daily plan and opt-in reminders | Proposed later | Later | M/L | P3 opportunity | Medium | SEC-008, content versioning, analytics |

For each feature, migration/deployment/rollback and documentation requirements in the roadmap are mandatory. None should bypass the earlier security/data gates because of product priority.

## Documentation maintenance

When a task starts, change status to `In progress` and link its branch/issue if available. Mark `Done` only with test/QA evidence and deployment state. If scope changes, preserve the stable ID and record the decision; create a new ID for materially different work. Accepted risks need owner, rationale, compensating control, and review date.
