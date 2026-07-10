# Testing And Quality

Audit date: 2026-07-10

This document distinguishes observed test evidence from recommended future gates.

## Verified results

The audit ran this command twice, including once in the final validation pass:

    ../venv/bin/python manage.py test

Results on 2026-07-10:

- 40 tests discovered.
- 40 tests passed on both runs; no test failed.
- Initial runtime: 9.559 seconds. Final validation runtime: 17.146 seconds.

This result applies to the audited revision and environment only. It is not a continuous guarantee.

## Current Automated Test Inventory

| File | Test methods | Current focus |
| --- | ---: | --- |
| lessons/tests.py | 4 | Registration, profile creation, transaction-commit notification behavior, bounded Telegram transport, and failure isolation |
| lessons/test_quiz_integrity.py | 14 | CSRF, quiz idempotency, pass progression, cross-lesson rejection, three-error reset, timeout handling, uniqueness, local media serving, voice Realtime token shape, and backend Realtime TTS |
| whatsapp_agent/tests.py | 22 | Webhook verification, inbound text processing, OpenAI fallback, WhatsApp send behavior, sandbox retry rules, Telegram alert deduplication/failure, access provisioning, and management commands |
| **Total** | **40** | Django server-side tests |

## Manual Diagnostic Scripts

The following files begin with test_ but are manual external-service diagnostics, not automated regression tests:

- lessons/test_realtime_diag.py
- lessons/test_realtime_kk.py

When executed directly, they:

- Require a real OpenAI credential.
- Make external network requests.
- Generate MP3 files.

Recommended action:

- Move them to scripts/ or diagnostics/.
- Rename them as smoke/manual tools.
- Add an explicit cost/network warning.
- Keep them out of automatic test discovery.

## Observed Quality Checks

Results observed during the audit:

| Check | Result |
| --- | --- |
| ../venv/bin/python manage.py test | 40 passed in 9.559 seconds |
| ../venv/bin/python manage.py check | Passed with no Django system-check issue |
| ../venv/bin/python manage.py makemigrations --check --dry-run | No changes detected |
| ../venv/bin/python manage.py check --deploy | Warned that HSTS and SSL redirect were absent and that the loaded local SECRET_KEY was weak |
| git diff --check | Failed on line-ending/trailing-whitespace diagnostics in the pre-existing modified lessons/views.py |
| Flake8 critical-error selection | Found an undefined settings name in lessons/chatgpt_helper.py |
| Full static typing | Not configured |
| Coverage measurement | Not configured |
| Browser test suite | Not present |
| CI workflow | Not present |

The deploy warnings describe the local configuration loaded during the audit and do not prove live production settings.

## Command Matrix

Set PYTHON through the portable interpreter discovery described in ENVIRONMENT_AND_OPERATIONS.md.

### Existing commands

| Purpose | Command | Mutates state? |
| --- | --- | --- |
| Django configuration check | "$PYTHON" manage.py check | No |
| Production-oriented settings warnings | "$PYTHON" manage.py check --deploy | No |
| Model/migration drift | "$PYTHON" manage.py makemigrations --check --dry-run | No |
| Full Django suite | "$PYTHON" manage.py test | Creates and destroys test database only |
| Lessons suite | "$PYTHON" manage.py test lessons | Creates and destroys test database only |
| WhatsApp suite | "$PYTHON" manage.py test whatsapp_agent | Creates and destroys test database only |
| Import/bytecode validation | "$PYTHON" -m compileall english_course lessons whatsapp_agent | Writes bytecode cache |
| Dependency consistency | "$PYTHON" -m pip check | No |
| Patch whitespace validation | git diff --check | No |

### Recommended future commands

Exact tools should be chosen in TEST-004; these are target capabilities, not current repository guarantees.

| Capability | Example |
| --- | --- |
| Formatting check | formatter --check |
| Lint | ruff check or equivalent |
| Type check | mypy with repository configuration |
| Coverage | coverage run plus coverage report with threshold |
| Dependency audit | maintained vulnerability scanner |
| Secret scan | repository and history secret scanner |
| Browser unit tests | JavaScript test runner |
| End-to-end tests | Browser automation against an isolated environment |
| Accessibility | Automated browser accessibility scan plus manual keyboard/screen-reader checks |

## Current Coverage Strengths

### Quiz integrity

The strongest test area covers:

- Valid and invalid CSRF submissions.
- Duplicate answer idempotency.
- Pass state and one-time unlock behavior.
- Cross-lesson question rejection.
- Three-distinct-error reset.
- Timeout idempotency.
- Database uniqueness for attempts.

### Realtime contract

Tests verify:

- Server token minting uses the GA client-secrets endpoint.
- The shared Realtime model is included.
- The safety identifier is hashed.
- Deprecated beta headers are absent.
- Backend WebSocket TTS decodes audio deltas.
- Backend TTS raises a controlled error.

The browser WebRTC implementation itself is not executed by these Django tests.

### WhatsApp behavior

Tests cover:

- GET verification success/failure.
- Inbound message persistence and reply paths.
- OpenAI fallback behavior.
- Meta error handling and the narrowly scoped sandbox retry.
- Telegram alert deduplication and failure handling.
- Existing and new account provisioning.
- Registration and test-send management commands.

### Registration notifications

Tests cover:

- Profile creation and login.
- Notification execution after transaction commit.
- Short Telegram transport timeout.
- Missing configuration and transport failure without blocking registration.

## Material Coverage Gaps

### Security and webhook authenticity

- No POST signature-validation tests because signature validation is not implemented.
- No replay-protection tests.
- No explicit tests that malformed/raw webhook data is redacted.
- No rate-limit or abuse tests.
- No tests for credential absence failing safely across all external integrations.

### Payment and receipt processing

- No focused OCR image extraction tests.
- No PDF extraction tests.
- No confidence-boundary matrix.
- No adversarial or malformed receipt corpus.
- No idempotent duplicate-receipt provisioning test.
- No test that every ambiguous/error path preserves denied access.
- No private-file lifecycle or retention tests.

### Access, profile, and device policy

- Limited direct tests for paid, voice, translator, and expiry combinations.
- No comprehensive guest/unpaid/paid/expired matrix.
- No DeviceLockMiddleware device-count and lock-duration suite.
- No account unlock/admin-action regression tests.
- No missing-profile/lazy-profile tests.

### Classroom

- No teacher-versus-student route authorization tests.
- No group ownership/isolation tests.
- No student/photo upload validation tests.
- No voice-embedding validation, deduplication, or storage-limit tests.
- No classroom token contract tests.
- No private-photo authorization tests.
- No browser face, hand, voice, attendance, or fusion tests.

### Realtime features

- Voice token has a server contract test; translator and classroom token endpoints do not have equivalent coverage.
- No browser SDP negotiation test.
- No JavaScript event-state or cleanup tests.
- No microphone/camera permission-denial automation.
- No long-session timeout or reconnection automation.
- Current prompt-source behavior is not asserted explicitly.

### Lessons and content

- No broad lesson-list and lesson-detail access matrix.
- No authored fixture validity gate.
- No vocabulary delimiter/property tests.
- No explanation regeneration or stale-audio lifecycle tests.
- No test that dump output remains clean JSON.

### PWA, static, and media

- One local media-serving test exists.
- No collectstatic manifest test.
- No root manifest/service-worker success and cache behavior suite.
- No production-style private-media authorization suite.

### Frontend, accessibility, and visual quality

- No JavaScript unit-test framework.
- No browser end-to-end suite.
- No responsive breakpoint regression checks.
- No keyboard-navigation, focus, screen-reader, contrast, reduced-motion, or touch-target gates.
- No performance budget or asset-size gate.

### Operations

- No clean-install test.
- No MySQL CI job.
- No supported-version matrix.
- No backup/restore rehearsal.
- No health/readiness test.
- No deployment smoke automation.

## Existing Quality Infrastructure Gaps

The repository has no checked-in:

- CI workflow.
- pyproject.toml quality configuration.
- pytest configuration.
- tox or nox configuration.
- Coverage configuration or threshold.
- Linter configuration.
- Formatter configuration.
- Type-checker configuration.
- Pre-commit hooks.
- JavaScript package manifest or lockfile.
- Browser test configuration.
- Dependency/security update automation.

The audit machine had some global quality tools, but global availability is not repository setup and is not reproducible.

## Recommended Testing Strategy

### Layer 1: Fast deterministic unit tests

Test pure or mostly pure behavior:

- Phone/input normalization with synthetic identifiers.
- Intent classification.
- Receipt parsing and confidence scoring.
- Access helper matrices.
- Quiz state derivation.
- Prompt/config builders.
- Voice-embedding validation.

Requirements:

- No network.
- No production data.
- Deterministic fixtures.
- Clear boundary-value cases.

### Layer 2: Django integration tests

Test:

- Routes, authentication, CSRF, and authorization.
- Database constraints and transactions.
- File upload/storage behavior using temporary media roots.
- External services through mocks/fakes.
- Webhook signature, replay, and failure behavior.
- Migration-sensitive behavior.

### Layer 3: Contract tests

Assert owned request/response shapes for:

- OpenAI client-secret minting.
- Translator and classroom token endpoints.
- WhatsApp send/download/register calls.
- Telegram transport.
- Receipt media metadata.

Contract tests must not call live paid services in the default suite.

### Layer 4: Browser unit/component tests

Test JavaScript state transitions:

- Voice/translator start, stop, cleanup, timeout, and error.
- Realtime event parsing.
- Classroom enrollment validation and matching logic.
- PWA registration behavior.
- Modal and access-state UI.

### Layer 5: End-to-end and accessibility tests

Run against an isolated environment:

- Guest, student, paid, expired, and teacher journeys.
- Quiz progression.
- Profile/access rendering.
- Classroom CRUD and authorization.
- Mocked Realtime connection UI.
- Webhook test fixtures.
- Responsive layouts and automated accessibility scans.

Camera, microphone, and model-accuracy testing also needs a documented manual/device lab because browser automation alone is insufficient.

### Layer 6: Operational verification

- Clean dependency install.
- SQLite and MySQL jobs.
- collectstatic and manifest verification.
- Health/readiness checks.
- Backup and restore rehearsal.
- Deployment smoke tests.

## Test Data Rules

1. Use synthetic names, phone-like identifiers, receipts, devices, and account data.
2. Never copy production payloads into fixtures.
3. Store binary test samples only when licensing, privacy, and size are documented.
4. Keep OCR samples minimal and synthetic.
5. Use temporary media directories and delete them after tests.
6. Mock external network calls by default.
7. Mark live/cost-incurring diagnostics explicitly and exclude them from CI.
8. Ensure failure output does not print credentials or private payloads.

## Recommended Definition Gates

These gates are recommendations until TEST-004 implements them.

### Every change

- Relevant automated tests pass.
- Django system check passes.
- Migration drift check passes.
- Diff whitespace check passes.
- No credential/private-data material added.
- Canonical docs updated when a contract changes.

### Python/backend change

- Formatter and linter pass.
- Type checks pass for configured scope.
- New/changed branches have tests.
- External calls are mocked and have explicit timeouts/error tests.

### Model or migration change

- Migration is reviewed.
- No unexpected migration drift.
- Forward migration is tested on representative data.
- Rollback/forward-fix strategy is documented.
- Constraints and deduplication paths have tests.

### Security, access, or payment change

- Negative authorization tests are present.
- Idempotency and replay cases are covered.
- No ambiguous receipt or external failure grants access.
- Logs/responses are checked for private-data leakage.
- A security reviewer approves the change.

### Realtime or browser change

- Server contract tests pass.
- JavaScript state tests pass.
- Start/stop/error/timeout cleanup is covered.
- Manual supported-browser microphone/camera check is recorded when relevant.

### Frontend/UX change

- Responsive representative pages pass.
- Keyboard and focus behavior is verified.
- Automated accessibility scan passes the chosen threshold.
- Adjacent feature mounts on the same template are checked.

### Deployment/configuration change

- Clean environment install passes.
- check --deploy findings are reviewed.
- Static manifest builds.
- Selected database backend starts.
- Health and deployment smoke tests pass.
- Rollback and backup prerequisites are explicit.

## Testing Remediation Tasks

### TEST-001 — Add adversarial payment, webhook, credential, and retention tests

**Priority:** Critical

**Scope**

- Implement and test Meta POST signature verification.
- Reject invalid or missing signatures.
- Add replay/idempotency coverage.
- Add synthetic image/PDF receipt fixtures.
- Cover confidence boundaries and parser failures.
- Prove that ambiguous, malformed, duplicate, or external-error cases never grant access.
- Test raw-payload/log redaction.
- Test private receipt-file lifecycle.

**Acceptance criteria**

- Every webhook POST test includes authenticity behavior.
- Receipt provisioning has a complete allow/deny boundary matrix.
- Duplicate delivery cannot grant access twice or create inconsistent state.
- Failure output contains no credential or private payload.

### TEST-002 — Cover entitlement, paywall, classroom ownership, device lock, deletion, and token routes

**Priority:** High

**Scope**

- Table-driven UserProfile entitlement and expiry matrix.
- Guest, student, paid, expired, and teacher route behavior.
- Device registration, limit, lock, logout, unlock, and time-bound behavior.
- Classroom ownership and cross-teacher isolation.
- Photo authorization and upload limits.
- Voice-embedding validation, deduplication, and sample cap.
- Translator and classroom Realtime token contracts.

**Acceptance criteria**

- Every protected route has positive and negative authorization tests.
- Cross-owner classroom access is denied.
- Device policy is deterministic under time mocking.
- All three browser Realtime token families share contract coverage.

### TEST-003 — Add browser JavaScript, accessibility, and mobile flow tests

**Priority:** High

**Scope**

- Add a JavaScript test runner and browser automation.
- Test voice/translator/classroom state machines with mocked WebRTC.
- Test cleanup after failures, timeouts, and user stop.
- Test quiz UI duplicate-submission protection.
- Add responsive and accessibility checks for major journeys.
- Define a small manual device matrix for microphone, camera, and classroom models.

**Acceptance criteria**

- Core browser state transitions run in CI without live paid APIs.
- Major pages pass the agreed automated accessibility threshold.
- Keyboard-only navigation and focus are manually verified.
- Supported-browser/device results are recorded.

### TEST-004 — Add CI, lint/type/format checks, coverage reporting, and secret scanning

**Priority:** High

**Scope**

- Add a CI workflow using the declared Python version.
- Install from the reproducible dependency baseline.
- Add formatting, linting, and type-check configuration.
- Add coverage measurement and an initial ratcheting threshold.
- Run Django checks, migration drift, tests, dependency consistency, and secret scanning.
- Add a MySQL service job if MySQL remains supported.
- Validate collectstatic.

**Acceptance criteria**

- CI runs on every proposed change.
- A clean runner passes installation and all required gates.
- The existing undefined-name error and whitespace/line-ending policy are resolved.
- Coverage is published and cannot silently decrease below the agreed threshold.
- No CI step requires real production credentials.

## Maintenance

Update this document whenever:

- Tests are added, removed, renamed, or moved.
- A test command or interpreter baseline changes.
- CI or a quality tool is introduced.
- A coverage threshold changes.
- A feature changes its maturity/support status.
- A security or operational incident reveals a missing test.

Record the last complete-suite date, revision, environment, test count, result, and duration without recording credentials or private data.
