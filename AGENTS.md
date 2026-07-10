# AGENTS.md

This is the primary entry point for human engineers and AI coding agents working on OqyAI.

## Product and users

OqyAI teaches American English primarily to Kazakh-speaking learners. The implemented web product includes structured lessons, vocabulary quizzes, progress, stored AI explanations/audio, premium Realtime voice and translator features, an experimental teacher classroom, and a WhatsApp sales workflow. Russian-localized lesson data exists in the repository but its product status is incomplete. See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Read before changing anything

1. Run `git status --short`, identify pre-existing changes, and preserve them.
2. Read the task-specific sources below.
3. Treat [docs/BACKLOG.md](docs/BACKLOG.md) Task IDs as the unit of implementation. Do not combine unrelated tasks.
4. Do not treat old notes, local databases, or fixture snapshots as production truth.

| Task type | Required reading |
| --- | --- |
| Architecture or cross-app change | [Architecture and codebase map](docs/ARCHITECTURE_AND_CODEBASE.md), [technical audit](docs/TECHNICAL_AUDIT.md) |
| Security, authentication, privacy | [Security audit](docs/SECURITY_AUDIT.md), [environment and operations](docs/ENVIRONMENT_AND_OPERATIONS.md) |
| Database, models, migrations | [Architecture/data model](docs/ARCHITECTURE_AND_CODEBASE.md#conceptual-data-model), [backlog](docs/BACKLOG.md) |
| Lesson, quiz, fixtures, content | [Content operations](docs/CONTENT_OPERATIONS.md), [Realtime and quiz contracts](docs/REALTIME_AND_QUIZ_CONTRACTS.md) |
| AI, voice, translator, prompts | [AI integrations](docs/AI_INTEGRATIONS.md), [security audit](docs/SECURITY_AUDIT.md) |
| WhatsApp, receipts, payment | [Security audit](docs/SECURITY_AUDIT.md), [AI integrations](docs/AI_INTEGRATIONS.md), [implementation plan](docs/IMPLEMENTATION_PLAN.md) |
| Classroom | [Classroom architecture](CLASSROOM_ARCHITECTURE.md), [UX audit](docs/UX_UI_AUDIT.md), [security audit](docs/SECURITY_AUDIT.md) |
| UX, accessibility, conversion | [UX/UI audit](docs/UX_UI_AUDIT.md), [feature roadmap](docs/FEATURE_ROADMAP.md) |
| Deployment or operations | [Environment and operations](docs/ENVIRONMENT_AND_OPERATIONS.md), [testing and quality](docs/TESTING_AND_QUALITY.md) |

## Stack and repository shape

- Python/Django 5.1.6 in the audited environment; this series is unsupported and upgrade task `DEVOPS-001` is high priority.
- Django apps: `lessons` and `whatsapp_agent`.
- Default local database: SQLite. Optional MySQL configuration exists.
- WSGI deployment entry point: `english_course.wsgi`; ASGI is HTTP-only.
- OpenAI text and Realtime APIs; browser Realtime uses server-minted ephemeral credentials and direct WebRTC.
- Source static assets: `static/`; collected output: `staticfiles/`.
- Local media contains generated explanation audio and sensitive uploads; it must not be treated as public by default.

Important entry points:

- `english_course/settings.py`: all settings and external-service environment variables.
- `english_course/realtime.py`: Realtime session configuration and ephemeral credential minting.
- `lessons/models.py`: learning, access, device, and classroom data.
- `lessons/views.py`: lesson/auth/quiz/AI/profile flows; currently oversized and high-risk.
- `lessons/views_classroom.py`: classroom ownership, uploads, biometrics, and Realtime tokens.
- `whatsapp_agent/services.py`: sales, outbound messaging, OCR receipts, and provisioning; high-risk.
- `lessons/templates/` and `static/`: server-rendered UI and browser behavior.

## Environment and commands

Clean setup and dependency installation are **not currently reproducible**. The repository has a current [requirements.txt](requirements.txt), but no declared Python runtime, resolved lockfile, hash-locked dependency set, or system-package manifest; the audited environment also differed from the declared requirements. Treat `requirements.txt` as the only tracked install input, not as proof that a clean environment will match or start. See `DEVOPS-002` in the [backlog](docs/BACKLOG.md#devops-002--create-a-reproducible-dependency-runtime-and-environment-baseline) and the [environment audit](docs/ENVIRONMENT_AND_OPERATIONS.md#devops-002--create-a-reproducible-dependency-runtime-and-environment-baseline).

The only verified interpreter for the audited workspace was `../venv/bin/python` (Python 3.10.12); `python` was not on `PATH`. That path is local evidence, not a portable runtime declaration. For the existing audited environment, run:

```bash
../venv/bin/python -m pip check
../venv/bin/python manage.py check
../venv/bin/python manage.py makemigrations --check --dry-run
../venv/bin/python manage.py test
../venv/bin/python -m compileall english_course lessons whatsapp_agent
git diff --check
```

If a task explicitly authorizes installation into a chosen isolated environment, the repository-backed input is `python -m pip install -r requirements.txt`; record the selected interpreter and resolver output, then run `python -m pip check`. Do not describe that command as a reproducible setup until `DEVOPS-002` supplies and validates the missing runtime, lock, database driver, and system packages. Do not install or upgrade dependencies unless the task explicitly requires it.

## Current business rules and invariants

- Django's default `User` is the account identity; `UserProfile` holds product role and entitlements.
- `is_paid`, voice access, and translator access are separate flags. Voice and translator can expire; course access currently cannot.
- Public registration currently accepts a self-selected teacher role. This is a confirmed security/product risk, not an approved invariant.
- Course order, free lessons, level, and language track are inferred from numeric lesson IDs. Preserve IDs until `DATA-004` explicitly replaces this design.
- `QuizAttempt.user_id` is a string: authenticated user ID or anonymous session key.
- One `QuizAttempt` per `(user_id, lesson)` and one `QuizAnswer` per `(attempt, question)` are database constraints.
- Quiz answers, not browser counters, are authoritative for score and mistakes. Cross-lesson answers must be rejected; duplicate submissions must be idempotent.
- Current WhatsApp receipt OCR is **not proof of payment**. Never extend or depend on automatic access grants before `SEC-001`.
- A WhatsApp reply must never be rerouted to a derived phone number. Current sandbox fallback is a finding (`SEC-003`), not a valid production rule.
- Classroom student names, photos, voice embeddings, and camera-derived signals are sensitive—likely children's—data.

## Security and privacy rules

- Never read a secret value into chat, logs, diffs, documentation, tests, screenshots, or browser JSON.
- Never edit `.env` casually. Use names/placeholders in `.env.example` only after `DEVOPS-002` is authorized.
- Treat any tracked credential as compromised; rotate before coordinated Git-history cleanup.
- Never commit `db.sqlite3`, `.env*`, media, receipts, classroom images, generated audio, `staticfiles/`, caches, or user-data fixtures.
- Verify authorization at every server endpoint; hiding a control in a template is not access control.
- Escape AI/user output by default. Do not use `|safe` or `innerHTML` with untrusted content.
- Webhooks require provider signature verification and idempotency.
- Do not expose the standard OpenAI key to browsers. Realtime clients receive ephemeral credentials only.
- Add explicit size/type limits and retention/deletion behavior for uploads.
- Do not send reusable passwords through messaging systems or persist them in conversation logs.
- Changes involving payment, entitlement, minors, biometrics, or account deletion require negative security tests.

## Code and architecture conventions

- Keep views thin. Put reusable business rules in focused services/selectors, not generic utility dumps or hidden signals.
- Keep app boundaries explicit. `whatsapp_agent` should request an entitlement operation through a stable domain service rather than mutating profile flags ad hoc.
- Centralize entitlement policy, curriculum order, external API clients, model selection, and prompt versions.
- Prefer ORM queries with explicit ownership filters, `select_related`/`prefetch_related` where measured, bounded querysets, and transactions around multi-row invariants.
- Use timezone-aware datetimes. Product-facing timezone and locale changes require product-owner confirmation.
- Preserve Kazakh, Russian, and English user-facing content unless correcting a confirmed defect. Do not casually translate educational material or prompts.
- Do not silently change prices, plan duration, free lesson policy, teacher eligibility, or AI persona.

## Migration rules

- Never edit an applied migration to change history.
- Run drift checks before and after model work.
- Inspect real data shape before adding uniqueness or non-null constraints; provide a deterministic data migration and rollback plan.
- Back up and rehearse restore before destructive production migrations.
- Do not infer production schema from the ignored local SQLite database; it contains local drift.

## Testing expectations

- Add regression tests that fail before the fix and cover success, denial, duplicate/retry, ownership, and error paths.
- Payment/security tasks need adversarial tests, not only happy paths.
- UI changes need mobile, keyboard, focus, empty/loading/error, and Kazakh-copy checks.
- AI changes mock external calls for automated tests and separately document any credentialed manual test.
- Do not claim a live integration passed unless it was actually exercised.
- See [docs/TESTING_AND_QUALITY.md](docs/TESTING_AND_QUALITY.md) for the current 40-test baseline and gaps.

## Dangerous or sensitive areas

- `analyze_lessons.py`: legacy script with a tracked credential; do not execute.
- `WHATSAPP_AGENT_SETUP.md`: sanitized/deprecated; never restore live operational values.
- `lessons/fixtures/`: currently invalid JSON; several files contain private runtime snapshots.
- `whatsapp_agent/services.py`: can message users and grant course access.
- `lessons/middleware.py`: can lock and log out accounts.
- `lessons/views.py::explain_section`: deletes/replaces generated media and calls paid APIs.
- classroom uploads/embeddings and WhatsApp receipts under media storage.
- migrations `0014`–`0016`: quiz-answer and deduplication history.

## Documentation update rules

- Update the source-of-truth document listed in [docs/INDEX.md](docs/INDEX.md), then link to it; do not duplicate it.
- Mark implemented, partial, experimental, proposed, and unverified states explicitly.
- Add or update evidence paths, Task IDs, tests, migration impact, deployment impact, and rollback notes when a task changes.
- Record product assumptions as `Needs product-owner confirmation`.
- Do not add current secret values, production identifiers, private data, or short-lived external status to Markdown.

## Definition of done

A task is done only when its acceptance criteria are met; automated tests and required manual QA pass; authorization/privacy/error paths are covered; migrations and rollback are safe; documentation is updated; no unrelated or generated files changed; and `git status`, `git diff --check`, and the final diff were reviewed. Deployment is a separate authorization unless explicitly included.
