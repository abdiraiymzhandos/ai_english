# FEATURES_MAP.md

Use this after `PROJECT_CONTEXT.md` and `FILE_MAP.md`. This file maps real features to code, not intended architecture.

## Lessons / Course Flow
- Feature goal
  - Show lesson catalog, gate locked lessons, and render lesson content with explanations and quiz flow.
- Main files
  - `lessons/views.py`
  - `lessons/models.py`
  - `lessons/urls.py`
  - `lessons/templates/lessons/lesson_list.html`
  - `lessons/templates/lessons/lesson_detail.html`
- Request/data flow
  - `/` -> `lesson_list()` computes unlocked lessons from `QuizAttempt`, session, and `UserProfile`.
  - `/lesson/<id>/` -> `lesson_detail()` enforces access and loads `Explanation`.
  - Quiz APIs mutate `QuizAttempt` and update session/profile progression.
- Dependencies
  - `Lesson`, `QuizAttempt`, `Explanation`, session storage.
- Admin/config dependencies
  - `UserProfile.is_paid` changes visible access.
- Fragile points
  - Unlock logic is split between session state and DB state.
  - Lesson gating changes can break guest and auth users differently.

## Authentication / User Profile / Access
- Feature goal
  - Provide account registration/login and control feature access through `UserProfile`.
- Main files
  - `lessons/forms.py`
  - `lessons/views.py`
  - `lessons/models.py`
  - `lessons/middleware.py`
  - `lessons/templates/lessons/register.html`
  - `lessons/templates/lessons/login.html`
  - `lessons/templates/lessons/profile.html`
- Request/data flow
  - Registration creates Django user, then creates `UserProfile`.
  - Middleware enforces device limit and account lock behavior.
  - Views and templates now lean on `UserProfile` helper methods for the main stable checks: paid lesson access, active voice access, active translator access, account lock, and classroom teacher/session access.
  - `/profile/` now mirrors those same access decisions back to the user as a card-based access dashboard and upgrade surface.
- Dependencies
  - Django auth user, `UserProfile`, `UserDevice`, sessions, auth decorators.
- Admin/config dependencies
  - Admin changes to `UserProfile` drive real user access.
- Fragile points
  - Access behavior is still cross-cutting, but the main stable checks now live on `UserProfile` helper methods instead of being fully inline.
  - Middleware can affect profile state even on unrelated requests.

## Admin Operations
- Feature goal
  - Let operators mark users paid, grant/revoke premium access, and inspect account state.
- Main files
  - `lessons/admin.py`
  - `lessons/models.py`
  - `lessons/management/commands/grant_voice_access.py`
  - `lessons/management/commands/revoke_voice_access.py`
- Request/data flow
  - Mostly manual through Django admin actions.
  - Voice access can also be changed via management commands.
- Dependencies
  - `UserProfile`, Django admin, Django auth user.
- Admin/config dependencies
  - This feature is itself admin-driven.
- Fragile points
  - `mark_as_paid` does not automatically grant voice or translator access.
  - Classroom models are not registered in admin.

## Realtime Voice Lesson
- Feature goal
  - Give paid/authorized users a live AI voice teacher on lesson detail pages.
- Main files
  - `lessons/views.py`
  - `static/js/voice-lesson.js`
  - `lessons/templates/lessons/lesson_detail.html`
  - `english_course/utils/realtime_tts.py`
  - `english_course/settings.py`
- Request/data flow
  - Lesson detail page mounts the voice UI if the user has active voice access.
  - Frontend requests `/api/realtime/token/<lesson_id>/`.
  - Backend builds lesson-specific instructions and mints an OpenAI Realtime session.
  - Browser talks directly to OpenAI via WebRTC.
- Dependencies
  - `OPENAI_API_KEY`, browser microphone, OpenAI Realtime API, WebRTC.
- Admin/config dependencies
  - `UserProfile.has_active_voice_access()` backed by `has_voice_access` and `voice_access_until`.
- Fragile points
  - Browser audio/device quirks.
  - Timeout/keepalive logic is easy to regress.
  - Historical websocket consumer still exists in the repo, but it is no longer routed and can still confuse debugging.

## Translator Assistant
- Feature goal
  - Provide a live speech-to-speech interpreter/assistant for users with translator access.
- Main files
  - `lessons/views.py`
  - `static/js/translator-assistant.js`
  - `lessons/templates/lessons/lesson_list.html`
  - `lessons/models.py`
- Request/data flow
  - Lesson list page exposes translator launcher UI.
  - Frontend checks `/api/translator/check-access/`.
  - Frontend requests `/api/translator/token/` when starting a session.
  - Browser talks directly to OpenAI Realtime via WebRTC.
- Dependencies
  - `OPENAI_API_KEY`, browser microphone, OpenAI Realtime API, WebRTC.
- Admin/config dependencies
  - `UserProfile.has_active_translator_access()` backed by `has_translator_access` and `translator_access_until`.
- Fragile points
  - Access errors can look like UI bugs.
  - Voice lesson and translator share many browser/runtime assumptions but separate code paths.

## Classroom / Enrollment / Session Flow
- Feature goal
  - Let teacher accounts manage class groups/students and run a browser-based classroom AI session.
- Status
  - Current local WIP, not stable committed baseline. Verify in code before assuming production usage.
- Main files
  - `lessons/views_classroom.py`
  - `lessons/forms_classroom.py`
  - `lessons/models.py`
  - `lessons/templates/lessons/classroom/dashboard.html`
  - `lessons/templates/lessons/classroom/group_detail.html`
  - `lessons/templates/lessons/classroom/session.html`
  - `static/js/classroom-lesson.js`
  - `static/js/classroom-voice-enroll.js`
- Request/data flow
  - Teacher creates class group and students.
  - Student photos are uploaded and stored on server.
  - Voice samples are recorded in browser and saved as embeddings via `/classroom/student/<student_id>/voice/`.
  - Session select page chooses class + lesson.
  - Session page loads roster and uses browser-side face/hand/voice detection.
  - Backend mints classroom-specific OpenAI Realtime session via `/api/realtime/classroom/<lesson_id>/<group_id>/`.
- Dependencies
  - Teacher role, voice access, browser camera/mic, OpenAI Realtime, face-api.js, MediaPipe, onnxruntime-web, Meyda.
- Admin/config dependencies
  - Teacher access currently depends on `UserProfile.can_use_classroom_teacher_features()` and `UserProfile.can_run_classroom_voice_sessions()` in local WIP.
- Fragile points
  - WIP status.
  - Heavy browser-side dependencies from external CDNs.
  - Voice enrollment logic exists in more than one JS location; verify intended source of truth.
  - `face_embedding` model field exists, but the current flow appears photo-driven; verify persistence path in code.

## Quiz / Content Generation
- Feature goal
  - Generate quiz options from lesson vocabulary and store/generate section explanations.
- Main files
  - `lessons/views.py`
  - `lessons/models.py`
  - `lessons/fixtures/lessons.json`
  - `lessons/fixtures/quiz_questions.json`
  - `lessons/fixtures/explanations.json`
- Request/data flow
  - `start_quiz()` calls `generate_quiz_questions()` on demand.
  - `generate_quiz_questions()` parses lesson vocabulary and rebuilds DB question rows.
  - `explain_section()` generates AI text and TTS audio, then updates `Explanation`.
- Dependencies
  - Vocabulary text formatting, OpenAI API, media storage.
- Admin/config dependencies
  - Superuser check for explanation generation endpoint.
- Fragile points
  - Content formatting errors break quiz generation.
  - Explanations can go stale after lesson edits.
  - Rebuilding questions inside request flow can create surprising side effects.

## Localization / Multilingual Behavior
- Feature goal
  - Present a Kazakh-first learning experience with English lesson content and some alternate-track content.
- Main files
  - `lessons/views.py`
  - `lessons/models.py`
  - `lessons/templates/lessons/*.html`
  - `lessons/fixtures/lessons.json`
- Request/data flow
  - UI copy is mostly authored directly in templates and prompts.
  - Alternate content track is encoded through lesson ID ranges, not Django translation catalogs.
- Dependencies
  - Prompt wording, lesson ID conventions, template strings.
- Admin/config dependencies
  - None beyond content management.
- Fragile points
  - There is little formal i18n structure.
  - Changing lesson ID assumptions can break the alternate track.

## Lead Capture / Marketing / Privacy
- Feature goal
  - Capture marketing leads, upsell premium features, expose privacy policy and guide modal.
- Main files
  - `lessons/views.py`
  - `lessons/models.py`
  - `lessons/templates/lessons/advertisement.html`
  - `lessons/templates/lessons/privacy_policy.html`
  - `lessons/templates/lessons/includes/guide-modal.html`
  - `lessons/templates/lessons/lesson_list.html`
- Request/data flow
  - Lead form posts to `/register-lead/`.
  - Advertisement and guide modal route users to registration or WhatsApp.
- Dependencies
  - `Lead` model, template-side forms, WhatsApp links.
- Admin/config dependencies
  - Admin can inspect leads.
- Fragile points
  - Marketing copy and actual access behavior can drift.

## WhatsApp Sales Agent
- Feature goal
  - Handle inbound WhatsApp sales conversations, payment-intent routing, receipt capture, Telegram escalation, and automatic paid-course access for high-confidence receipts.
- Main files
  - `whatsapp_agent/models.py`
  - `whatsapp_agent/services.py`
  - `whatsapp_agent/views.py`
  - `whatsapp_agent/admin.py`
  - `whatsapp_agent/management/commands/*`
  - `english_course/settings.py`
  - `english_course/urls.py`
- Request/data flow
  - Meta verifies `GET /api/whatsapp/webhook/`.
  - Meta posts inbound payloads to `POST /api/whatsapp/webhook/`.
  - The app creates/updates `WhatsAppLead` + `WhatsAppMessage`, detects language and intent, calls OpenAI for the normal sales reply path, and sends outbound WhatsApp text replies back to the inbound `wa_id` / lead phone.
  - If Meta sandbox rejects the `wa_id` with error code `131030`, the app retries that outbound send once with the derived sandbox/test-recipient format, for example `77781029394` -> `787781029394`.
  - Local ops can also send WhatsApp templates through `whatsapp_test_send`; the Meta API Setup test-recipient `input` value can differ from the resolved `wa_id`, so template smoke tests should use the exact Meta-shown input.
  - Receipt media is downloaded from WhatsApp Cloud API, stored in Django media, extracted with OCR/PDF text parsing, scored, and either auto-provisions `UserProfile.is_paid` or escalates to Telegram.
- Dependencies
  - Existing `settings.OPENAI_API_KEY`
  - Existing Django `auth.User` + `lessons.UserProfile`
  - WhatsApp Cloud API access token + phone number ID
  - Telegram Bot API token + chat ID
- Admin/config dependencies
  - Paid-course access is still the existing `UserProfile.is_paid` / `has_paid_lesson_access()` path.
  - No new billing backend was introduced.
- Fragile points
  - There is no job queue; webhook processing is synchronous and relies on bounded external request timeouts.
  - Manual Meta template testing and inbound customer-service replies intentionally use different recipient values.
  - Meta sandbox may reject the inbound `wa_id` even when the raw test-recipient input is allowed; retry is intentionally limited to exact Meta error code `131030`.
  - Receipt validation is intentionally conservative: low-confidence cases alert Telegram instead of auto-granting access.
  - Meta test-recipient `input` values can differ from the eventual `wa_id`; using the wrong one causes confusing `(#131030) Recipient phone number not in allowed list` failures.
  - Existing site templates still contain older hard-coded WhatsApp CTAs; they were left untouched until the production Cloud API number is fully registered.

## PWA / Static Root Files
- Feature goal
  - Serve `sw.js` and `manifest.json` from root for installable/PWA behavior.
- Main files
  - `lessons/views.py`
  - `lessons/templates/lessons/base.html`
  - `static/js/pwa-register.js`
- Request/data flow
  - Views read files from `staticfiles`, not source `static/`.
- Dependencies
  - `collectstatic`, WhiteNoise/static output.
- Admin/config dependencies
  - Deployment/static configuration.
- Fragile points
  - Missing `collectstatic` output breaks root-file serving.

## Feature Boundaries
- `lessons/views.py` is the center of gravity for stable features.
- `UserProfile` is the shared access boundary across premium features.
- Classroom work is intentionally separate in `views_classroom.py` and classroom templates, but still depends on the same `UserProfile` and lesson models.
- Realtime browser features do not rely on Django websockets for the current intended path; they rely on backend token minting and browser-side WebRTC.

## Shared Dependencies Across Multiple Features
- `UserProfile` flags.
- Session state.
- `OPENAI_API_KEY`.
- Large templates with embedded JS/CSS.
- `lessons/urls.py` as the request surface.
- `english_course/settings.py` for deployment-sensitive behavior, including env-driven `DEBUG` and SQLite/MySQL backend selection via `USE_MYSQL`.
