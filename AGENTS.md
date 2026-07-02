# AGENTS.md

This is the first file an AI coding agent should read in this repository.

## What OqyAI Is
OqyAI is a Django-based English learning platform for Kazakh-speaking students. It serves lesson content, vocabulary quizzes, AI-generated explanations with audio, premium realtime voice lessons, a translator assistant, a classroom mode, and an isolated WhatsApp sales agent.

## Core Stack
- Django 5.1.x with the default Django user model.
- Main app: `lessons`.
- Secondary app: `whatsapp_agent`.
- OpenAI integrations: Responses/Chat Completions for text, GA Realtime for browser voice sessions and explanation audio.
- Static files: source in `static/`, collected output in `staticfiles/`.
- Media: generated explanation audio and classroom photos under `settings.MEDIA_ROOT`.
- Local default database: SQLite. Production can use MySQL with `USE_MYSQL=1`.

## App And Module Map
- `english_course/settings.py`: env loading, database selection, static/media, OpenAI key, middleware, ASGI/WSGI.
- `english_course/realtime.py`: shared GA Realtime client-secret minting and safety identifiers.
- `english_course/utils/realtime_tts.py`: backend GA Realtime WebSocket TTS for explanation MP3s.
- `lessons/models.py`: lessons, quiz attempts/answers/questions, explanations, profiles/access, devices, leads, classroom models.
- `lessons/views.py`: lesson flow, quiz APIs, explanations, voice and translator token endpoints, profile/PWA views.
- `lessons/views_classroom.py`: classroom management, photo/voice enrollment, classroom token endpoint.
- `lessons/templates/lessons/`: large mixed UI templates; `lesson_detail.html` owns quiz and voice lesson mount.
- `static/js/voice-lesson.js`: browser WebRTC voice lesson client.
- `static/js/translator-assistant.js`: browser WebRTC translator client.
- `static/js/classroom-lesson.js`: classroom runtime and Realtime event sender.
- `whatsapp_agent/`: WhatsApp Cloud API sales automation and receipt workflow.

## Canonical Reading Order
1. `AGENTS.md`
2. `docs/ARCHITECTURE_AND_DATA_FLOW.md`
3. `docs/REALTIME_AND_QUIZ_CONTRACTS.md`
4. `docs/AI_AGENT_RUNBOOK.md`
5. `PROJECT_CONTEXT.md`
6. `FILE_MAP.md`
7. `FEATURES_MAP.md`
8. `KNOWN_RISKS.md`
9. Task-specific docs such as `CLASSROOM_ARCHITECTURE.md`, `FIXTURE_CONTENT_WORKFLOW.md`, and `WHATSAPP_AGENT_SETUP.md`

## Local Startup
Use the local virtualenv when present because this environment may not expose `python` globally:

```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py runserver
```

## Tests And Checks
```bash
./venv/bin/python manage.py makemigrations lessons --check --dry-run
./venv/bin/python manage.py check
./venv/bin/python manage.py test lessons
./venv/bin/python -m compileall english_course lessons whatsapp_agent
git diff --check
```

## Deployment Overview
- `Procfile` uses WSGI: `gunicorn english_course.wsgi`.
- Channels is installed, but active interactive voice does not use Django websocket routing.
- Run migrations before deploy.
- Run `collectstatic --noinput`; do not commit `staticfiles/`.
- PythonAnywhere production should set `USE_MYSQL=1` and all `MYSQL_*` env vars if MySQL is expected.
- Media serving must point at `MEDIA_ROOT`; local default is `<repo>/media`, production can set `MEDIA_ROOT`.

## Strict Rules
- Never edit `.env`.
- Never expose secrets, tokens, API keys, phone tokens, or raw user IDs in logs or browser JSON.
- Never commit or intentionally modify generated/local-only paths: `venv/`, `staticfiles/`, `media/`, `db.sqlite3`, `.env`.
- Preserve portable media settings:

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
```

- Do not restore hard-coded PythonAnywhere media paths.

## Database And Migration Safety
- `QuizAttempt.user_id` is a string. Authenticated users use `str(user.id)`; guests use Django session keys.
- `QuizAttempt` is unique per `(user_id, lesson)`.
- `QuizAnswer` is unique per `(attempt, question)`.
- Never hand-edit old migrations unless explicitly repairing migration history.
- Data migrations must be production-safe and preserve the selected canonical row when deduping.
- Avoid deleting quiz questions on quiz start because answer rows reference question IDs.

## Static And Media Behavior
- Source static files live in `static/`.
- Collected static files live in `staticfiles/` and are generated only.
- Lesson explanation audio is saved as MP3 under `settings.MEDIA_ROOT` and referenced through `MEDIA_URL`.
- `static/css/style.css` is a small legacy project stylesheet and is referenced from `lesson_detail.html`.

## Current Realtime Architecture
- Active Realtime model: `gpt-realtime-2`.
- Browser voice features mint ephemeral credentials server-side with `POST /v1/realtime/client_secrets`.
- Browser WebRTC clients create one data channel named `oai-events`.
- Browser SDP goes to `POST /v1/realtime/calls` with the ephemeral credential and `application/sdp`.
- The browser never receives the standard OpenAI API key.
- Server-side explanation MP3 generation uses a backend WebSocket to `wss://api.openai.com/v1/realtime?model=gpt-realtime-2`.
- `OpenAI-Safety-Identifier` is a SHA-256 hash of internal user ID or Django session key.

## Quiz Integrity Invariants
- Only the backend is authoritative for quiz score, mistakes, completion, pass state, and progression.
- One attempt exists per user/session and lesson.
- One answer exists per attempt and question.
- Duplicate answer submissions must not increase score, mistakes, or unlock progress.
- Cross-lesson question submissions are rejected.
- Timeout submissions create one incorrect answer with an empty selected answer.
- Three distinct wrong answers reset the attempt and clear stored answers.
- A quiz passes only after every distinct lesson question has an answer and fewer than three mistakes.

## Review Before Commit
Run:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

Check for:
- Accidental `.env`, `media/`, `staticfiles/`, `db.sqlite3`, or generated-file changes.
- Secret leakage or raw user IDs in browser-visible responses.
- Obsolete Realtime beta strings.
- Unintended changes to local WIP settings.
- Migrations in the right order and tests covering the changed behavior.
