# Environment And Operations

Audit date: 2026-07-10

Status: observed repository behavior plus recommended operational controls. This document does not certify the application as production-ready.

Security rule: only environment variable names and secret/data categories are documented. Values, credentials, PINs, private contacts, payment-recipient identifiers, and customer data must remain outside Git.

## Observed Runtime Baseline

| Area | Observed state |
| --- | --- |
| Framework | Django 5.1.6 |
| Observed Python | Python 3.10.12 |
| Observed project interpreter | ../venv/bin/python |
| Repository-local interpreter | ./venv/bin/python was not present |
| Default local database | SQLite at the repository database path |
| Optional database | MySQL when USE_MYSQL enables it |
| Declared web process | gunicorn english_course.wsgi |
| ASGI application | Django HTTP-only ASGI application |
| Active interactive Realtime transport | Browser WebRTC using server-minted ephemeral OpenAI credentials |
| Static source | static/ |
| Collected static output | staticfiles/ |
| Private/generated media | MEDIA_ROOT, defaulting to repository-local media/ |
| Settings loader | python-dotenv loads the repository .env file |

The observed interpreter path is workspace-specific. Scripts and documentation must not assume that every clone has the same parent-directory layout.

Support/security status verified on 2026-07-10:

- Django 5.1 is listed as unsupported; extended support ended 2025-12-03. The repository's 5.1.6 also predates 5.1.7, which fixed a moderate-severity denial-of-service issue affecting 5.1.6. Sources: [official Django download/support table](https://www.djangoproject.com/download/) and [Django 5.1.7 release notes](https://docs.djangoproject.com/en/dev/releases/5.1.7/).
- Python 3.10 is in security-only maintenance and scheduled to reach end of life in October 2026. Source: [official Python version status](https://devguide.python.org/versions/).

This makes `DEVOPS-001` a current security/reliability task, not merely routine modernization.

## Portable Interpreter Discovery

For local work, choose an interpreter in this order:

1. An explicitly activated virtual environment.
2. A repository-local virtual environment when present.
3. A workspace-level virtual environment when present.
4. A system python3 only for diagnostics when its dependencies have been verified.

Example discovery:

    if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
        PYTHON="$VIRTUAL_ENV/bin/python"
    elif [ -x "./venv/bin/python" ]; then
        PYTHON="./venv/bin/python"
    elif [ -x "../venv/bin/python" ]; then
        PYTHON="../venv/bin/python"
    else
        PYTHON="$(command -v python3)"
    fi

Then use:

    "$PYTHON" --version
    "$PYTHON" -m pip --version
    "$PYTHON" manage.py check

A future reproducible baseline should replace discovery heuristics with a declared Python version and a documented environment-creation command.

## Environment Variable Inventory

Names only are listed below.

### Core Django and OpenAI

- SECRET_KEY
- DEBUG
- OPENAI_API_KEY
- MEDIA_ROOT

### Database selection

- USE_MYSQL
- MYSQL_DATABASE
- MYSQL_USER
- MYSQL_PASSWORD
- MYSQL_HOST
- MYSQL_PORT

### WhatsApp integration

- WHATSAPP_ACCESS_TOKEN
- WHATSAPP_PHONE_NUMBER_ID
- WHATSAPP_WABA_ID
- WHATSAPP_WEBHOOK_VERIFY_TOKEN
- WHATSAPP_GRAPH_API_VERSION
- WHATSAPP_AGENT_OPENAI_MODEL

### Telegram integration

- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

### Application handoff and payment-validation configuration

- APP_BASE_URL
- KASPI_RECEIVER_PHONE
- KASPI_RECEIVER_NAME
- COURSE_PRICE_KZT

No environment variable value belongs in this document. A future .env.example must use empty or clearly synthetic placeholders.

## Settings Behavior

### Import-time OpenAI requirement

english_course/settings.py reads OPENAI_API_KEY during import, raises when it is absent, and prints a success banner when it is present.

Observed consequences:

- Management commands and tests require an OpenAI key even when they do not use OpenAI.
- Settings output polluted every tracked fixture JSON file.
- Command output is noisy and unsuitable for machine-readable dump output.

Recommended behavior:

- Remove the print side effect.
- Validate feature-specific credentials at the feature boundary or through an explicit deployment validation command.
- Allow offline checks and tests to use a safe test configuration.

### Debug and host policy

Observed:

- DEBUG defaults to enabled when absent.
- ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS are hard-coded.
- Secure session and CSRF cookies are always enabled.
- TIME_ZONE is UTC.

Risks:

- An omitted production DEBUG variable can enable debug behavior.
- Hard-coded hosts make environment promotion brittle.
- Secure cookies can make plain-HTTP local authentication confusing.

Recommended:

- Fail closed for production settings.
- Use an explicit environment/profile distinction.
- Keep secure-cookie and proxy/HTTPS behavior consistent with the real reverse proxy.
- Validate host and CSRF origin configuration during deployment.

### Database selection

Observed:

- USE_MYSQL selects MySQL; otherwise SQLite is used.
- MySQL variables are checked for non-empty values.
- The MySQL Django driver is available in the observed environment but is not declared in requirements.txt.

Risk:

- A clean installation from requirements.txt is not guaranteed to start with USE_MYSQL enabled.

Recommended:

- Add the selected MySQL driver to the reproducible dependency baseline.
- Test a clean MySQL-backed startup in CI.
- Document database TLS, connection lifetime, backup, and migration ownership before production use.

### Channels

Observed:

- channels and channels-redis are listed as dependencies.
- CHANNEL_LAYERS uses the in-memory backend.
- ASGI is HTTP-only.
- Active browser voice, translator, and classroom flows do not use Django WebSockets.

Recommended:

- Remove unused Channels/Redis dependencies and configuration if no supported feature needs them.
- If WebSockets are reintroduced, define a shared production channel layer and deploy an ASGI process intentionally.

## Local And Production Distinctions

| Concern | Local observed/default | Production requirement |
| --- | --- | --- |
| Debug | Defaults enabled unless configured | Must be explicitly disabled |
| Database | SQLite | Explicitly selected and backed up; MySQL driver and connectivity validated if used |
| Static | Source files available from static/ | collectstatic completed; collected files served and versioned correctly |
| Media | Local media directory | Durable private storage, access policy, backups, and restore procedure |
| HTTPS | Localhost may use HTTP | HTTPS termination, secure cookies, trusted proxy behavior, and redirect policy |
| Secrets | Ignored .env file | Platform secret manager or protected environment configuration |
| External APIs | Developer credentials and network | Credential validation, timeouts, monitoring, quotas, and incident ownership |
| Browser AI features | Local browser permissions | HTTPS, microphone/camera policy, CDN availability, supported-browser matrix |
| Process management | Development server | Managed Gunicorn process with explicit concurrency, timeout, logging, and restart policy |

## Dependency Baseline

### Python dependencies used by active features

- Django and Gunicorn
- WhiteNoise
- requests
- OpenAI SDK
- websockets
- pydub plus the external FFmpeg executable
- Pillow
- pypdf
- pytesseract
- python-dotenv

### Declared but apparently inactive or indirect dependencies

The current requirements file mixes direct dependencies with a partial environment freeze. Examples include Channels/Redis packages, Django REST Framework, database URL support, `ffmpeg-python`, and low-level transitive packages that do not appear to be imported by active application code.

### Missing or inconsistent declarations

- The MySQL driver required by the optional production database path is not declared.
- analyze_lessons.py imports a PostgreSQL driver that is not declared.
- OpenAI is declared twice, once with extras.
- Some top-level packages are strictly pinned while others are open ranges or unpinned.
- There is no separate development/test requirements file.
- There is no lockfile with hashes.
- There is no declared Python runtime version.
- The observed environment had `pypdf` 6.10.2 while `requirements.txt` requires `<6`, so the audited environment was not installed strictly from the declared file.
- The observed environment had MySQL and PostgreSQL drivers available despite both being undeclared; a clean build cannot rely on them.

### System packages

Observed on the audit machine:

- FFmpeg was installed.
- Tesseract OCR was installed.
- The English, Kazakh, and Russian OCR language packs required by code were installed.

These packages are not provisioned by requirements.txt. A clean deployment needs an explicit operating-system package manifest or image build.

### Browser dependencies

Classroom and other templates load libraries and models from public CDNs. There is no JavaScript package manifest, lockfile, local build, or Subresource Integrity policy.

Risks:

- Availability and supply-chain behavior depend on third parties at runtime.
- Browser compatibility is not tested automatically.
- Large model downloads may exceed acceptable startup time.

## Deployment Topology

### WSGI

Procfile declares:

    web: gunicorn english_course.wsgi

This matches the current active architecture because browser Realtime sessions connect directly to OpenAI after Django mints an ephemeral credential.

The Procfile does not define:

- A migration release phase.
- collectstatic.
- Worker count or class.
- Request timeout.
- Graceful shutdown policy.
- Access/error log format.
- Health-check path.

### ASGI

english_course/asgi.py exposes the normal Django ASGI application and intentionally does not route WebSockets. Merely installing Channels does not make WebSockets available in production.

### Deployment-target ambiguity

Repository documentation references a manually managed hosting environment, while Procfile describes a Procfile-based process. There is no checked-in platform manifest that defines build, runtime, persistence, release, or health behavior.

Before any deployment change, identify the actual target and document:

- Build command.
- Runtime command.
- Persistent filesystem behavior.
- Environment/secrets mechanism.
- Database location and backup owner.
- Static and private-media serving.
- TLS termination and proxy headers.
- Health check and rollback mechanism.

## Static Files And Private Media

### Static

Observed:

- Source: static/
- Output: staticfiles/
- Storage backend: WhiteNoise manifest storage.
- Root service-worker and manifest views read from collected output.

Implications:

- A fresh deployment without collectstatic can return 404 for root PWA assets.
- staticfiles/ is generated and must not be committed.
- A failed manifest build should block deployment.

### Private and generated media

MEDIA_ROOT stores generated explanation audio and can store classroom photos and WhatsApp receipt documents.

WhiteNoise is not a private-media authorization system. Production must define:

- Durable storage.
- Access control.
- Encryption expectations.
- Retention and deletion.
- Malware/content validation where appropriate.
- Backup and restore.
- Data residency and incident handling.

Serving MEDIA_URL from Django is only configured in debug mode. Production media serving is an infrastructure responsibility.

## Observed Diagnostic Results

These are observations from 2026-07-10, not permanent guarantees.

| Command/check | Result |
| --- | --- |
| ../venv/bin/python manage.py check | Passed with no Django system-check issue |
| ../venv/bin/python manage.py makemigrations --check --dry-run | No model drift detected |
| ../venv/bin/python manage.py check --deploy | Reported missing HSTS, missing SSL redirect, and a weak loaded local SECRET_KEY |
| ../venv/bin/python manage.py test | Passed all 40 tests twice; final validation run completed in 17.146 seconds |
| git diff --check | Failed on line-ending/trailing-whitespace diagnostics in the pre-existing modified lessons/views.py |
| Critical-only Flake8 diagnostic | Found one undefined-name error in lessons/chatgpt_helper.py |

The deploy warnings describe the loaded audit environment. They do not prove what the live production environment uses.

## Safe Deployment Checklist

This is a recommended guarded process. It is not evidence that current deployment automation implements it.

### Before deployment

1. Identify the exact target environment and revision.
2. Confirm the worktree and release artifact contain only intended changes.
3. Run the required test and quality gates in an isolated environment.
4. Validate required environment variable names without printing values.
5. Confirm DEBUG, hosts, CSRF origins, HTTPS/proxy, and cookie policy.
6. Confirm the selected database backend and driver.
7. Take and verify a restorable database backup.
8. Back up private media or confirm object-storage versioning.
9. Review migrations and their data/lock implications.
10. Confirm system packages and browser/runtime dependencies.
11. Confirm an operator, rollback revision, and incident channel.

### Build and release

1. Install from the reproducible dependency baseline.
2. Run:

       "$PYTHON" manage.py check
       "$PYTHON" manage.py check --deploy
       "$PYTHON" manage.py makemigrations --check --dry-run

3. Run the complete automated test suite.
4. Run:

       "$PYTHON" manage.py collectstatic --noinput

5. Validate the static manifest.
6. Apply reviewed migrations:

       "$PYTHON" manage.py migrate --noinput

7. Start or reload the declared WSGI process.

### Post-deployment smoke checks

1. Health/readiness endpoint.
2. Authentication and session persistence.
3. Lesson list and one representative lesson.
4. Quiz start and answer submission.
5. Admin access through the intended network controls.
6. Static CSS/JavaScript, manifest, and service worker.
7. Authorized private-media access.
8. A mocked or controlled Realtime token path.
9. Webhook verification and signature rejection behavior.
10. Error reporting and alert delivery.

### Stop conditions

Stop or roll back when:

- Database migration fails or exceeds its reviewed lock window.
- Static manifest generation fails.
- Health/readiness fails.
- Authentication, quiz integrity, or access controls regress.
- Error rate, latency, or external API failure rate exceeds the release threshold.
- Private data is exposed in logs or responses.

## Health And Monitoring Gaps

Observed gaps:

- No health, liveness, readiness, or metrics endpoint.
- No database or storage readiness probe.
- Console-only logging.
- No structured correlation/request identifier.
- No error-tracking service integration.
- No uptime or synthetic monitoring definition.
- Telegram alerts cover business flows, not infrastructure health.
- No external API latency/error dashboards.
- No disk/media usage monitoring.

Recommended minimum:

- A shallow liveness endpoint that does not expose internals.
- A readiness endpoint that safely checks required dependencies.
- Structured logs with request/correlation IDs and redaction.
- Error tracking and release identifiers.
- Alerts for HTTP error rate, latency, database errors, failed background-like webhook work, and storage capacity.
- Synthetic checks for login, static assets, and a non-mutating core page.

## Backup, Restore, Rollback, And Incident Gaps

### Backup gaps

- No checked-in backup command or schedule.
- No retention or encryption policy.
- No private-media backup procedure.
- No documented handling for classroom photos, voice embeddings, messages, or receipts.
- No evidence of restore tests.

### Restore gaps

- No recovery-time or recovery-point objective.
- No clean-room restore procedure.
- No documented reconciliation after restoring a database but not media, or vice versa.

### Rollback gaps

The existing AI runbook discusses restoring code but correctly warns that reversing migrations can lose data. It does not provide:

- A release identifier mechanism.
- Forward-fix versus reverse-migration criteria.
- Database compatibility rules across releases.
- Automated or verified rollback.

### Incident gaps

- No severity model.
- No named incident roles.
- No credential-compromise procedure.
- No webhook abuse or private-data exposure runbook.
- No customer/data-subject notification decision process.
- No post-incident review template.

## Recommended Operational Runbooks

Create and test the following:

1. Standard deployment and verification.
2. Database migration with rollback decision tree.
3. Database backup and clean-room restore.
4. Private-media backup, restore, retention, and deletion.
5. Credential rotation by category.
6. Webhook abuse/signature failure response.
7. External OpenAI, Meta, and Telegram outage/degradation.
8. Static/PWA release failure.
9. Disk exhaustion and media-growth response.
10. Personal-data exposure and log-redaction incident.

## DevOps Remediation Tasks

### DEVOPS-001 — Upgrade to a supported Django/Python baseline

**Problem**

The repository pins Django 5.1.6 and relies on an observed Python 3.10.12 environment without a documented support/upgrade policy.

**Required work**

- At implementation time, use official Django and Python support matrices to choose a currently supported pair.
- Review third-party package compatibility.
- Upgrade one controlled step at a time.
- Run deprecation checks, the complete suite, and representative manual flows.
- Document the support window and next review date.

**Acceptance criteria**

- Python and Django versions are explicitly declared.
- The selected pair is supported at release time.
- A clean environment installs successfully.
- All automated tests pass.
- Deployment and rollback are rehearsed.
- No unresolved framework deprecation warning remains.

### DEVOPS-002 — Create a reproducible dependency, runtime, and environment baseline

**Problem**

The current machine contains undeclared packages and system tools, while requirements.txt is neither a minimal direct-dependency file nor a complete lock.

**Required work**

- Declare the Python version.
- Choose a dependency workflow such as compiled requirements, uv, Poetry, or an equivalent lock mechanism.
- Separate runtime and development/test tools.
- Add the selected database driver.
- Remove unused dependencies after verification.
- Declare FFmpeg, Tesseract, and required OCR language packs in a build image or OS manifest.
- Add a sanitized .env.example.
- Verify installation in a clean CI job.

**Acceptance criteria**

- A documented one-command clean setup succeeds.
- Dependency versions and hashes are reproducible.
- MySQL mode starts from declared dependencies when selected.
- OCR and audio prerequisites are automatically provisioned or checked.
- pip check passes in the isolated project environment.
- No credential or private identifier is present in the baseline files.

### DEVOPS-003 — Add health, structured redacted logging, error tracking, and service metrics

- Add liveness and readiness endpoints.
- Add structured, redacted logging and error tracking.
- Define alert thresholds and ownership.
- Ensure webhook payloads and personal data are not copied indiscriminately into logs/events.

### DEVOPS-004 — Establish database/media backup, restore, rollback, and incident drills

- Define database and private-media backup policies.
- Automate backups.
- Perform and record a clean-room restore.
- Define recovery objectives and restore ownership.

### DEVOPS-005 — Automate guarded build, release, smoke, and rollback stages

- Define build, test, collectstatic, migration, deploy, smoke, and rollback stages.
- Prevent deployment when required gates fail.
- Record revision and migration state per release.

### DEVOPS-006 — Enforce secret and operational-data hygiene in developer/deploy workflows

- Remove sensitive values from tracked documentation and scripts.
- Rotate any active exposed credential.
- Remove personal/operational fixtures.
- Assess and, where required, purge historical database or secret material.
- Restrict local secret/database file permissions.
