# ENVIRONMENT_DEPLOYMENT.md

Use this with `PROJECT_CONTEXT.md`. This file is only for environment and deployment-sensitive facts found in code.

## Current Environment Shape
- Django `5.1.x`.
- One main app: `lessons`.
- Database backend is now env-driven in `english_course/settings.py`:
  - default/local: SQLite at `db.sqlite3`
  - production when `USE_MYSQL=1`: MySQL from `MYSQL_*` env vars
- No custom user model.
- `channels` is installed and ASGI config exists.
- Current ASGI app is HTTP-only; the deprecated interactive voice websocket route is no longer exposed.
- WhiteNoise is enabled for static handling.
- `Procfile` uses `gunicorn english_course.wsgi`.
- Media is stored outside the repo source tree via a hard-coded absolute `MEDIA_ROOT`.

## Environment Variables Found In Code

| Variable | Usage | Current Behavior |
| --- | --- | --- |
| `DEBUG` | Django debug mode | Defaults to `"1"` locally; set `DEBUG=0` in production |
| `USE_MYSQL` | Select database backend | `"1"` = MySQL, anything else = SQLite |
| `MYSQL_DATABASE` | MySQL database name | Required when `USE_MYSQL=1` |
| `MYSQL_USER` | MySQL username | Required when `USE_MYSQL=1` |
| `MYSQL_PASSWORD` | MySQL password | Required when `USE_MYSQL=1` |
| `MYSQL_HOST` | MySQL host | Required when `USE_MYSQL=1` |
| `MYSQL_PORT` | MySQL port | Defaults to `3306`; should still be set explicitly in production |
| `OPENAI_API_KEY` | OpenAI text, TTS, realtime token minting | Required at import time in `english_course/settings.py`; app raises if missing |
| `SECRET_KEY` | Django secret key | Loaded from env in `english_course/settings.py` |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp Cloud API outbound sends + media download | Required for live WhatsApp agent operation |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Cloud API send target | Required for outbound sends |
| `WHATSAPP_WABA_ID` | WhatsApp Business Account reference | Stored for deployment/config parity |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Meta webhook verification | Must match the Meta webhook configuration |
| `TELEGRAM_BOT_TOKEN` | Telegram admin alerts | Required for Telegram alert delivery |
| `TELEGRAM_CHAT_ID` | Telegram admin chat target | Required for Telegram alert delivery |
| `APP_BASE_URL` | Login link and app handoff messaging | Defaults to `https://www.oqyai.kz` in code if missing |
| `KASPI_RECEIVER_PHONE` | Receipt validation + payment instructions | Defaults to the current Kaspi receiver phone in code |
| `KASPI_RECEIVER_NAME` | Receipt validation + payment instructions | Defaults to the current Kaspi receiver name in code |
| `COURSE_PRICE_KZT` | Receipt validation + payment instructions | Defaults to `25000` in code |

## Configurable Vs Hard-Coded

| Setting Area | Current Shape | Notes |
| --- | --- | --- |
| OpenAI key | Env-driven | Hard fail on missing key |
| Secret key | Env-driven | No local fallback in code |
| Database | Env-driven via `USE_MYSQL` | No manual comment/uncomment path needed now |
| `DEBUG` | Env-driven | Defaults to local-friendly `"1"` |
| `ALLOWED_HOSTS` | Hard-coded list | Includes localhost, PythonAnywhere, `oqyai.kz` |
| `CSRF_TRUSTED_ORIGINS` | Hard-coded list | Production-sensitive |
| `MEDIA_ROOT` | Hard-coded absolute path | `/home/abdiraiymzhandos/media/` |
| Secure cookies | Hard-coded `True` | Can affect local/debug auth behavior |
| `TIME_ZONE` | Hard-coded `UTC` | App logic uses timezone-aware access checks |
| Channel layer | Hard-coded in-memory backend | Currently low impact because interactive voice no longer uses Django websocket routing |

## Deployment-Sensitive Files
- `english_course/settings.py`
- `english_course/asgi.py`
- `english_course/urls.py`
- `whatsapp_agent/views.py`
- `whatsapp_agent/services.py`
- `lessons/views.py`
- `Procfile`
- `requirements.txt`
- `lessons/templates/lessons/base.html`

## Static / Template / Media Implications
- `BASE_DIR` is now defined once as a `Path` and reused for `.env` loading, templates, static files, and the default SQLite path.
- Static source lives under `static/`.
- Collected static output lives under `staticfiles/`.
- WhiteNoise uses `ManifestStaticFilesStorage`, so `collectstatic` matters.
- `lessons/views.py::service_worker()` and `pwa_manifest()` read from `staticfiles`, not `static`.
- `lessons/templates/lessons/base.html` points to `/manifest.json`.
- Generated lesson audio and classroom photos use `MEDIA_ROOT`.
- Verify in code/infrastructure how media is served in production; only debug/static helper behavior is visible in repo.

## Realtime / OpenAI Deployment Concerns
- Token minting is server-side in `lessons/views.py` and `lessons/views_classroom.py`.
- Browser talks directly to OpenAI Realtime after the server returns a session payload.
- Realtime voice/translator/classroom sessions need:
  - working `OPENAI_API_KEY`
  - outbound network access from server
  - browser microphone access
  - HTTPS in real browser environments for media APIs
- `english_course/utils/realtime_tts.py` uses the OpenAI Realtime client for audio synthesis.
- If a websocket architecture is ever reintroduced, the current in-memory channel layer is a deployment limitation.

## Import-Time Settings Warning
- `english_course/settings.py` prints `✅ OpenAI API кілті сәтті жүктелді!` on import.
- That print has already polluted fixture files in this repo.
- Any management command, dump, or tool that imports Django settings can inherit this side effect.

## Verify Before Changing In Production
- Confirm `USE_MYSQL=1` is set in production before expecting MySQL to be used.
- Confirm `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, and `MYSQL_PORT` are present in the production environment.
- Confirm whether the real deploy uses `wsgi` only or also runs `asgi`.
- Confirm whether `MEDIA_ROOT` matches the deployed filesystem layout.
- Confirm whether secure-cookie settings are correct for the target environment.
- Confirm whether `collectstatic` output includes `sw.js` and `manifest.json`.
- Confirm whether `OPENAI_API_KEY` is present before changing any startup behavior.
- Confirm whether the new WhatsApp webhook URL is reachable at `https://www.oqyai.kz/api/whatsapp/webhook/`.
- Confirm whether the Cloud API phone number is registered before switching live traffic to the new sales number.
- Confirm whether any change to `ALLOWED_HOSTS` or `CSRF_TRUSTED_ORIGINS` matches the actual domain setup.
- Confirm whether a config change is safe for both local development and production.
