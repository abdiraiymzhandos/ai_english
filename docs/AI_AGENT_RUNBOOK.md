# AI Agent Runbook

## Safe Git Workflow
```bash
git status --short
git branch --show-current
git log --oneline -10
git diff --stat
git diff
```

Rules:
- Do not commit, push, deploy, or rewrite history unless the user explicitly asks.
- Do not revert user changes.
- Do not edit `.env`.
- Do not commit `venv/`, `staticfiles/`, `media/`, `db.sqlite3`, or generated audio.
- Before editing, read `AGENTS.md` and the docs listed there.

## Local Virtualenv
The repo contains a local `venv/`. Prefer it because `python` may not exist globally.

```bash
./venv/bin/python --version
./venv/bin/python -m pip install -r requirements.txt
```

## Migrations
Create migrations only when model changes require them:

```bash
./venv/bin/python manage.py makemigrations lessons
./venv/bin/python manage.py migrate
```

Check for unexpected model drift:

```bash
./venv/bin/python manage.py makemigrations lessons --check --dry-run
```

Migration safety:
- Keep schema and data migrations ordered.
- For quiz integrity, create `QuizAnswer`, dedupe `QuizAttempt`, then add the attempt unique constraint.
- Never assume production data is clean.

## Tests
```bash
./venv/bin/python manage.py check
./venv/bin/python manage.py test lessons
./venv/bin/python manage.py test whatsapp_agent
./venv/bin/python -m compileall english_course lessons whatsapp_agent
```

## Static Files
```bash
./venv/bin/python manage.py collectstatic --noinput
```

Do not commit collected files under `staticfiles/`.

## Local Server
```bash
./venv/bin/python manage.py runserver
```

Manual local checks:
- `/`
- `/lesson/1/`
- `/admin/`
- `/manifest.json`
- `/sw.js`

## PythonAnywhere Deployment Checklist
1. Confirm `.env` or environment variables are set outside Git.
2. Confirm `OPENAI_API_KEY` and `SECRET_KEY` exist.
3. If using MySQL, set:
   - `USE_MYSQL=1`
   - `MYSQL_DATABASE`
   - `MYSQL_USER`
   - `MYSQL_PASSWORD`
   - `MYSQL_HOST`
   - `MYSQL_PORT`
4. Confirm `MEDIA_ROOT` points to the production media directory if the default repo-local media path is not desired.
5. Pull or upload code.
6. Install dependencies:

```bash
./venv/bin/python -m pip install -r requirements.txt
```

7. Run:

```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py check
```

8. Reload the web app.
9. Smoke test lesson page, admin, static assets, media playback, voice token endpoints, and WhatsApp webhook verification if relevant.

## Rollback Checklist
1. Identify the deployed revision or file set to restore.
2. Preserve `.env`, media files, uploaded classroom photos, and database.
3. Revert code only, not generated runtime data.
4. If rolling back migrations, confirm data loss risk first.
5. Reload app.
6. Run:

```bash
./venv/bin/python manage.py check
```

7. Smoke test the failing feature and one adjacent feature.

## Troubleshooting
| Symptom | Likely Cause | Check | Fix |
| --- | --- | --- | --- |
| `OPENAI_API_KEY жүктелмеді` | Missing env var | environment / `.env` outside Git | Set key and restart |
| `Invalid URL (POST /v1/realtime/sessions)` | Old Realtime beta endpoint | `rg '/v1/realtime/sessions'` | Use `/v1/realtime/client_secrets` |
| `beta_api_shape_disabled` | Old beta shape/header | `rg 'OpenAI-Beta|modalities'` | Use GA `session.audio` shape |
| Browser SDP fails | Wrong WebRTC endpoint or token | browser console and Django logs | POST SDP to `/v1/realtime/calls` with ephemeral secret |
| Voice/translator access denied | Profile flag/expiry | inspect `UserProfile` | Grant correct access in admin |
| Quiz score increments on repeated click | Frontend or backend duplicate handling broken | `QuizAnswer` rows | Ensure unique answer per question and UI `isSubmitting` |
| Quiz timeout not saved | Frontend-only timeout | network tab | POST `timed_out=true` |
| `/static/css/style.css` 404 | Source stylesheet missing or collectstatic stale | `static/css/style.css`, template head | Restore valid project source and run `collectstatic` |
| `/manifest.json` or `/sw.js` 404 | `collectstatic` missing | `staticfiles/` contents | Run `collectstatic` |
| Explanation audio fails | Realtime WebSocket or ffmpeg/pydub problem | Django logs | Check OpenAI key, model, ffmpeg availability |
| Media does not load | Wrong media root/URL serving | `MEDIA_ROOT`, web server media mapping | Set `MEDIA_ROOT` and configure media serving |

## Required Runtime Audits
```bash
rg -n 'gpt-realtime-1\.5|/v1/realtime/sessions|OpenAI-Beta: realtime=v1|client\.beta\.realtime' \
  english_course lessons static whatsapp_agent \
  --glob '!**/__pycache__/**'
```

Expected result: no active runtime matches.

```bash
git diff --check
git status --short
git diff --stat
```
