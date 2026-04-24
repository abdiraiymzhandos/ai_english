# PROJECT_CONTEXT.md

## Project Snapshot
- Hybrid scope as of `2026-03-28`: this document describes the stable product architecture first, then a separate `Current Local WIP: Classroom` section for the uncommitted classroom work present in this workspace.
- Stack: Django `5.1.x`, one main app `lessons`, project config in `english_course/`, static assets in `static/`, media served from a hard-coded external `MEDIA_ROOT`.
- Root URL flow is simple: `english_course/urls.py` delegates almost everything to `lessons/urls.py`.
- This is effectively a single dense Django app. `lessons` owns lessons, quizzes, access rules, auth-adjacent product logic, OpenAI integrations, lead capture, and now classroom work.
- Premium/access is flag-based and admin-driven. There is no Stripe, checkout, webhook, or real billing backend in the repo today.
- Realtime AI flows are backend-minted OpenAI session tokens plus client-side WebRTC in the browser.

## Three Truths To Remember First
1. Open `lessons/urls.py`, `lessons/views.py`, and `lessons/models.py` before making assumptions. Most product behavior lives there.
2. Many UI pages are large standalone templates with inline CSS/JS. A backend change often also requires editing a template.
3. Voice, translator, and classroom work are not separate services. They are bolted into the same app and depend on `UserProfile` access flags.

## Django Structure
- `english_course/settings.py`: environment loading, installed apps, middleware, static/media config, ASGI/WSGI setup, OpenAI key loading.
  - Database selection is now env-driven: SQLite by default, MySQL when `USE_MYSQL=1`, so manual comment/uncomment switching is no longer part of deploy flow.
- `english_course/urls.py`: admin + include of `lessons.urls`.
- `english_course/asgi.py`: ASGI entrypoint. Interactive realtime voice is HTTP token minting + browser WebRTC; no deprecated voice websocket route is exposed here now.
- `lessons/`: core product app.
- `lessons/templates/lessons/`: primary template tree.
- `static/js/`: frontend behavior for voice lesson, translator, classroom, PWA, guide modal.
- `lessons/fixtures/`: main content/data dumps. Current fixture files are polluted by a settings print line at the top.

## Main Apps And Responsibilities
- `lessons/models.py`
  - Owns lesson content, quiz state, explanations, user access/profile state, device locking, leads, and local classroom models.
- `lessons/views.py`
  - Owns lesson list/detail pages, AI explanation generation, quiz APIs, translator APIs, voice token minting, lead capture, PWA root files, privacy/profile pages.
- `lessons/urls.py`
  - Main product map. If a task changes behavior, routing usually starts here.
- `whatsapp_agent/`
  - Isolated WhatsApp Cloud API sales app.
  - Owns webhook intake, lead/message/event/receipt models, Telegram alerts, receipt validation, automatic `UserProfile.is_paid` provisioning after high-confidence receipt validation, and template test-send support for Meta API Setup recipients whose raw `input` can differ from the resolved `wa_id`.
- `lessons/views_classroom.py`
  - Local WIP classroom management and classroom realtime token flow.
- `lessons/admin.py`
  - Operational control panel. Access is manually granted here more often than through end-user flows.
- `lessons/middleware.py`
  - Domain redirect + account/device lock behavior.

## URL Routing And Request Flow

### Core user flow
- `/` -> `lesson_list`
  - Computes unlocked lessons from `QuizAttempt`, `request.session`, and `UserProfile` flags.
- `/lesson/<lesson_id>/` -> `lesson_detail`
  - Enforces access rules, loads `Explanation` records, renders lesson page.
- `/start-quiz/<lesson_id>/` -> `start_quiz`
  - Rebuilds quiz questions from lesson vocabulary on demand, returns JSON.
- `/submit-answer/<lesson_id>/` -> `submit_answer`
  - Updates `QuizAttempt`, progresses unlock state, mutates session/profile.
- `/register/`, `/login/`, `/logout/`, `/profile/`
  - Standard auth plus role/phone/profile behavior. `/profile/` now also acts as the main user-facing access dashboard and soft upsell surface.
- `/advertisement/`
  - Sales/upsell page; used as access fallback for locked premium content.

### AI / realtime endpoints
- `/lesson/<lesson_id>/explain-section/` -> AI explanation generation + TTS + DB persistence.
- `/chat-with-gpt/<lesson_id>/` -> lesson-aware Q&A in Kazakh.
- `/motivational-message/` -> small GPT-generated motivational modal.
- `/api/realtime/token/<lesson_id>/` -> ephemeral OpenAI session token for voice lesson.
- `/api/translator/check-access/` -> translator feature gate check.
- `/api/translator/token/` -> ephemeral OpenAI session token for translator assistant.

### PWA and utility endpoints
- `/sw.js` and `/manifest.json`
  - Served from `staticfiles`, not directly from source static paths.
- `/privacy-policy/`
- `/register-lead/`
- `/api/whatsapp/webhook/`
  - WhatsApp Cloud API verification + inbound webhook endpoint for the sales agent.

### Local WIP classroom routes
- `/classroom/`
- `/classroom/new/`
- `/classroom/<group_id>/`
- `/classroom/<group_id>/edit/`
- `/classroom/<group_id>/students/new/`
- `/classroom/student/<student_id>/photo/`
- `/classroom/student/<student_id>/voice/`
- `/classroom/student/<student_id>/delete/`
- `/classroom/photo/<photo_id>/`
- `/classroom/session/`
- `/classroom/session/<group_id>/<lesson_id>/`
- `/api/realtime/classroom/<lesson_id>/<group_id>/`

## Data Model Map
- `Lesson`
  - Main course unit. Stores `title`, `content`, `vocabulary`, `grammar`, `dialogue`.
- `QuizQuestion`
  - `ForeignKey -> Lesson`. Generated from lesson vocabulary text.
- `QuizAttempt`
  - `ForeignKey -> Lesson`.
  - Stores `user_id` as a string, not a foreign key. This is important.
  - Used for both authenticated users and guests via session key.
- `Explanation`
  - `ForeignKey -> Lesson`.
  - Unique per `(lesson, section)`.
  - Stores AI-generated explanation text and audio URL.
- `UserProfile`
  - `OneToOne -> auth.User`.
  - Central access model: `role`, `is_paid`, `has_voice_access`, `voice_access_until`, `has_translator_access`, `translator_access_until`, `current_lesson`, `lock_until`, `phone`.
  - Core helper methods now act as the lightweight access source of truth for stable features: `is_locked()`, `has_paid_lesson_access()`, `has_active_voice_access()`, `has_active_translator_access()`, `can_use_classroom_teacher_features()`, `can_run_classroom_voice_sessions()`.
- `UserDevice`
  - `ForeignKey -> auth.User`.
  - Tracks device IDs for device-limit locking.
- `Lead`
  - Simple marketing capture: `name`, `phone`, `created_at`.

### Current Local WIP: Classroom models
- `ClassGroup`
  - `ForeignKey -> auth.User` as teacher.
  - Unique by `(teacher, school_name, name)`.
- `ClassStudent`
  - `ForeignKey -> ClassGroup`.
  - Optional `ForeignKey -> auth.User`.
  - Stores `face_embedding` and `voice_embeddings`.
- `StudentPhoto`
  - `ForeignKey -> ClassStudent`.
  - Image files stored under `classroom_faces/...`.

## Lesson / Course Logic
- Free lesson IDs are `{1, 2, 3, 251, 252, 253}`.
- Main lesson gating lives in `lesson_list()` and `lesson_detail()`.
- Guests progress through `request.session['passed_lessons']`.
- Authenticated users progress through `QuizAttempt` rows plus session state.
- The repo currently contains `300` lesson fixture records.
- There are two practical tracks in logic:
  - Main track: lesson IDs `< 251`
  - Alternate track: lesson IDs `>= 251`
- Unlocking is range-based from the highest passed lesson, not a separate curriculum model.
- `start_quiz()` always calls `generate_quiz_questions()`, which deletes and rebuilds quiz questions from vocabulary text each time.
- Vocabulary parsing depends on the delimiter `" – "`. Content formatting mistakes can break quiz generation.

## User / Authentication / Access Logic
- Default Django auth user model is used. There is no custom user model.
- Registration is in `lessons/forms.py` + `register()` and now captures:
  - `username`
  - `phone`
  - `role` (`student` or `teacher`)
  - password
- `UserProfile` is the real product-access object.
- Device locking is enforced in `DeviceLockMiddleware`.
  - If a user exceeds 3 devices, the account is locked for 5 days and logged out.
- `WwwRedirectMiddleware` permanently redirects `oqyai.kz` to `https://www.oqyai.kz`.
- Access/subscription is manual/operational:
  - `has_paid_lesson_access()` is the stable check for paid lesson access.
  - `has_active_voice_access()` is the stable check for voice lesson access.
  - `has_active_translator_access()` is the stable check for translator assistant access.
  - Admin actions in `lessons/admin.py` and management commands grant/revoke voice access.
  - Upsell path is WhatsApp, not a payment gateway.

## Payment / Subscription / Access Reality
- There is no real payment gateway in the codebase today.
- No Stripe, no checkout session, no webhook, no invoice model, no subscription provider integration.
- "Subscription" is effectively:
  - sales copy in templates,
  - manual admin flagging,
  - voice-access management commands,
  - WhatsApp contact links.
- New isolated automation:
  - `whatsapp_agent` can now validate inbound WhatsApp receipts conservatively and mark `UserProfile.is_paid=True` automatically when confidence is high.
  - Low-confidence or failed receipt parsing is escalated to Telegram instead of silently granting access.

## AI / Voice / Realtime / Classroom Logic

### Stable baseline AI paths
- `lessons/views.py::explain_section`
  - Uses OpenAI `responses.create(model="gpt-5")` for explanation text.
  - Falls back to chat completions if needed.
  - Uses `english_course/utils/realtime_tts.py` to synthesize audio and persists `Explanation`.
- `lessons/views.py::chat_with_gpt`
  - Lesson-aware chat response in Kazakh.
- `lessons/views.py::motivational_message`
  - Small GPT-generated motivational message.
- `lessons/views.py::mint_realtime_token`
  - Mints OpenAI Realtime session for voice lesson.
- `lessons/views.py::mint_translator_token`
  - Mints OpenAI Realtime session for translator assistant.

### Frontend realtime entry points
- `static/js/voice-lesson.js`
  - Current live voice lesson client.
  - WebRTC-only approach.
  - Connects browser directly to OpenAI Realtime after backend token minting.
- `static/js/translator-assistant.js`
  - Similar WebRTC pattern for live translation/interpreter behavior.
- `english_course/utils/realtime_tts.py`
  - Async helper for Realtime TTS, converts streamed PCM16 to MP3 bytes.

### Docs drift warning
- `VOICE_LESSON_README.md` still contains historical websocket-centric guidance.
- Actual live voice lesson code says `WebRTC ONLY`.

## Templates And Static Files
- Biggest UI hubs:
  - `lessons/templates/lessons/lesson_list.html`
  - `lessons/templates/lessons/lesson_detail.html`
- These are large standalone pages with a lot of inline CSS/JS and product logic embedded in templates.
- `lessons/templates/lessons/auth_base.html`
  - Base shell for login/register/profile/classroom management pages.
- `lessons/templates/lessons/base.html`
  - Exists, but is not the main base for core lesson pages.
- `static/js/guide-modal.js`, `static/css/guide-modal.css`
  - Marketing/help modal on lesson list.
- `static/js/pwa-register.js`
  - PWA registration helper.
- `static/css/voice-lesson.css`, `static/css/translator-assistant.css`
  - Shared frontend styling for premium AI features.

## Localization / Language Strategy
- Formal Django i18n is minimal.
- `LANGUAGE_CODE` is `en-us`, but product UI is mostly Kazakh-first.
- Lesson content is English with Kazakh instructional context.
- The alternate content track is encoded by lesson IDs, not translation catalogs.
- Prompt instructions frequently mix Kazakh and English explicitly.

## Important Scripts / Services / Helpers
- `lessons/admin.py`
  - Highest-leverage operational file for access bugs and manual account management.
- `lessons/management/commands/grant_voice_access.py`
- `lessons/management/commands/revoke_voice_access.py`
- `lessons/test_realtime_diag.py`, `lessons/test_realtime_kk.py`
  - Realtime/OpenAI diagnostics, not proper automated tests.
- `analyze_lessons.py`
  - Likely legacy/local script.
  - Hard-coded Postgres credentials.
  - Uses `psycopg2`, which is not in `requirements.txt`.

## Fixtures / Content Data
- `lessons/fixtures/lessons.json`: `300` lessons.
- `lessons/fixtures/quiz_questions.json`: `1042` rows.
- `lessons/fixtures/explanations.json`: `227` rows.
- `lessons/fixtures/user_profiles.json`: `49` rows.
- Current fixture dumps are not clean JSON at byte 0. They begin with `✅ OpenAI API кілті сәтті жүктелді!`, which suggests `settings.py` print output leaked into `dumpdata` output.

## Current Local WIP: Classroom
- Scope: teacher registration role, classroom management, photo-based roster, voice enrollment, classroom session UI, face/hand/voice-based classroom interaction.
- New local files:
  - `lessons/forms_classroom.py`
  - `lessons/views_classroom.py`
  - `lessons/templates/lessons/classroom/*`
  - `static/js/classroom-lesson.js`
  - `static/js/classroom-voice-enroll.js`
  - migrations `0011` to `0013`
  - `CLASSROOM_MVP_NOTES.md`
- Existing tracked files also modified locally to support classroom:
  - `lessons/models.py`
  - `lessons/forms.py`
  - `lessons/views.py`
  - `lessons/urls.py`
  - `lessons/templates/lessons/register.html`
  - `lessons/templates/lessons/profile.html`
  - `requirements.txt`
  - `english_course/settings.py`
- Classroom runtime shape:
  - teacher-only dashboard and group management,
  - photo upload and photo serving,
  - voice embedding save endpoint,
  - classroom-specific OpenAI Realtime token,
  - `ClassroomLessonManager` extends `VoiceLessonManager`,
  - browser-side face detection, hand raise detection, voice matching, attendance/time events.
  - Access checks now use `UserProfile.can_use_classroom_teacher_features()` for teacher-only pages and `UserProfile.can_run_classroom_voice_sessions()` for live classroom sessions.
- Treat this as local WIP until committed. Do not describe it as fully merged baseline behavior in future tasks.

## Fragile / Risky Areas
- `english_course/settings.py`
  - Raises if `OPENAI_API_KEY` is missing.
  - Prints on import.
  - Hard-coded `DEBUG = True`.
  - Hard-coded `MEDIA_ROOT`.
  - Secure cookies forced even in debug.
- `lessons/consumers.py`
  - Historical deprecated consumer remains in the repo for reference.
  - It is no longer routed, but it still describes a costlier architecture that should not be revived accidentally.
- Deployment drift
  - `Procfile` uses `gunicorn english_course.wsgi`.
  - ASGI/channels exists, but production entrypoint is WSGI.
- `lessons/views.py::generate_quiz_questions`
  - Rebuilds DB quiz data at request time.
  - Depends on vocabulary text formatting.
- Template weight
  - `lesson_list.html` and `lesson_detail.html` are large, mixed responsibility files.
- Access endpoints
  - Important POST endpoints use `csrf_exempt`.
- Tests
  - `lessons/tests.py` is effectively empty.
- Docs drift
  - `VOICE_LESSON_README.md` is partially stale relative to current frontend architecture.

## Top 10 Most Important Files
1. [english_course/settings.py](/home/abdiraiymzhandos/english_platform/english_course/english_course/settings.py)
2. [lessons/urls.py](/home/abdiraiymzhandos/english_platform/english_course/lessons/urls.py)
3. [lessons/models.py](/home/abdiraiymzhandos/english_platform/english_course/lessons/models.py)
4. [lessons/views.py](/home/abdiraiymzhandos/english_platform/english_course/lessons/views.py)
5. [lessons/views_classroom.py](/home/abdiraiymzhandos/english_platform/english_course/lessons/views_classroom.py)
6. [lessons/templates/lessons/lesson_list.html](/home/abdiraiymzhandos/english_platform/english_course/lessons/templates/lessons/lesson_list.html)
7. [lessons/templates/lessons/lesson_detail.html](/home/abdiraiymzhandos/english_platform/english_course/lessons/templates/lessons/lesson_detail.html)
8. [static/js/voice-lesson.js](/home/abdiraiymzhandos/english_platform/english_course/static/js/voice-lesson.js)
9. [static/js/translator-assistant.js](/home/abdiraiymzhandos/english_platform/english_course/static/js/translator-assistant.js)
10. [static/js/classroom-lesson.js](/home/abdiraiymzhandos/english_platform/english_course/static/js/classroom-lesson.js)

## Top 5 Folders To Inspect First
1. [lessons](/home/abdiraiymzhandos/english_platform/english_course/lessons)
2. [lessons/templates/lessons](/home/abdiraiymzhandos/english_platform/english_course/lessons/templates/lessons)
3. [static/js](/home/abdiraiymzhandos/english_platform/english_course/static/js)
4. [english_course](/home/abdiraiymzhandos/english_platform/english_course/english_course)
5. [lessons/fixtures](/home/abdiraiymzhandos/english_platform/english_course/lessons/fixtures)

## Task Routing Cheat Sheet
- Lesson content / unlock / quiz bug
  - Open `lessons/views.py`, `lessons/models.py`, `lesson_list.html`, `lesson_detail.html`.
- Auth / profile / paid-access bug
  - Open `lessons/models.py`, `lessons/views.py`, `lessons/admin.py`, `lessons/middleware.py`, auth templates.
- Voice lesson / translator realtime bug
  - Open `lessons/views.py`, `static/js/voice-lesson.js`, `static/js/translator-assistant.js`, `english_course/utils/realtime_tts.py`.
- Classroom change
  - Open `lessons/views_classroom.py`, `lessons/forms_classroom.py`, classroom templates, `static/js/classroom-lesson.js`, `static/js/classroom-voice-enroll.js`.

## How Future Codex Should Work
1. Read `PROJECT_CONTEXT.md` first
2. Identify task type
3. Open only the relevant files
4. Avoid rescanning the whole repository unless necessary

## Most Important Areas
- Lesson flow and unlock logic.
- `UserProfile`-based access gating.
- OpenAI realtime entrypoints for voice lesson and translator.
- Current classroom stack in local WIP.

## Most Fragile Areas
- `settings.py` import-time side effects and config drift.
- Historical deprecated websocket consumer remains in the repo as reference code.
- Large monolithic templates with inline behavior.
- Access/control logic split across views, middleware, admin, and session state.
  - This is slightly improved by `UserProfile` helper methods, but lesson progression and admin provisioning are still intentionally separate.

## Additional Docs That Would Improve Future Speed
- Environment + deployment doc covering `.env`, media/static, WSGI/ASGI, and production topology.
- Access/admin operations doc covering `UserProfile` flags, admin actions, and voice/translator provisioning.
- Classroom architecture + tuning doc covering face/hand/voice thresholds and teacher workflow.
- Clean fixture/content workflow doc covering `dumpdata`, lesson authoring format, and quiz-generation assumptions.
