# FILE_MAP.md

Use this after `PROJECT_CONTEXT.md`. This file is for fast navigation, not architecture narrative.

## Top Important Folders

| Path | Purpose | Open When |
| --- | --- | --- |
| `lessons/` | Main product app: models, views, URLs, middleware, admin, fixtures, management commands | Almost every backend/product task |
| `whatsapp_agent/` | Isolated WhatsApp sales automation app: webhook, lead/message/receipt models, Telegram alerts, receipt processing, management commands, Meta template test-send support | WhatsApp Cloud API, receipt automation, sales-agent tasks |
| `lessons/templates/lessons/` | Main UI layer; many pages contain inline JS/CSS and product behavior | Any user-facing page change or UI bug |
| `static/js/` | Realtime voice, translator assistant, classroom JS, PWA, guide modal | Frontend logic, realtime bugs, classroom work |
| `english_course/` | Django project config: settings, root URLs, ASGI/WSGI, utils | Config, deployment, routing, OpenAI/TTS helpers |
| `lessons/fixtures/` | Lesson/content data dumps and related seed data | Content edits, fixture bugs, quiz/content investigations |
| `lessons/management/commands/` | Manual operational commands | Voice access provisioning or ops tooling |
| `static/css/` | Styles for voice lesson, translator, guide modal | Styling changes for premium features |
| `staticfiles/` | Collected static output, not source of truth | Only when debugging deploy/collectstatic behavior |

## Top Important Files

| File | What It Controls | When To Edit It | Common Risks |
| --- | --- | --- | --- |
| `english_course/settings.py` | Environment loading, installed apps, middleware, env-driven DB selection, static/media, security, OpenAI key loading | Config, deployment, env, static/media, middleware changes | Import-time side effects, remaining hard-coded paths, debug/security drift |
| `english_course/urls.py` | Root URL handoff | Only when adding/removing top-level routing | Easy to forget `lessons.urls` is the real surface |
| `whatsapp_agent/services.py` | WhatsApp sales-agent business logic, Cloud API sends/downloads, template test sends, Telegram alerts, receipt validation, account provisioning | WhatsApp automation behavior changes | External API calls, Meta test-recipient input vs `wa_id` confusion, receipt confidence rules, paid-access automation |
| `whatsapp_agent/views.py` | Meta webhook verification + POST intake | Webhook verification or inbound parsing changes | Must never crash on malformed payloads |
| `whatsapp_agent/models.py` | WhatsApp leads, messages, events, and receipts | Data model/admin/reporting changes for the sales agent | Avoid coupling to unrelated lesson models |
| `english_course/asgi.py` | ASGI entrypoint | ASGI/deployment work or historical realtime cleanup | Should remain explicit about HTTP-only ASGI unless a new websocket architecture is intentionally added |
| `english_course/utils/realtime_tts.py` | Realtime TTS helper used for lesson explanations | TTS/audio generation fixes | Realtime API assumptions, audio conversion path |
| `lessons/urls.py` | Main product route map | Adding/changing behavior endpoints | Very dense surface; easy to miss related routes |
| `lessons/models.py` | Lessons, quiz attempts, explanations, user profile/access, devices, leads, classroom WIP models | Data model, access logic, classroom data, content schema | `QuizAttempt.user_id` is string-based; `UserProfile` helpers are now the first access source to inspect |
| `lessons/views.py` | Lesson flow, explanation generation, quiz APIs, voice/translator token minting, leads, profile, PWA endpoints | Most product/backend behavior changes | Monolithic; lesson progression is still sensitive even though core access checks now lean on `UserProfile` helpers |
| `lessons/views_classroom.py` | Local classroom WIP backend | Classroom management/session changes | WIP, teacher-only gates, photo/voice endpoints; classroom guards should follow `UserProfile` helper methods |
| `lessons/forms.py` | Registration form | Register/profile role or phone changes | Tied to `UserProfile` creation assumptions |
| `lessons/forms_classroom.py` | Classroom forms | Group/student/photo/session form changes | WIP, multi-file upload validation |
| `lessons/middleware.py` | Domain redirect + device lock | Access/account lock bugs | Device logic can create/alter profile state on request |
| `lessons/admin.py` | Admin operations for lessons and user access | Admin/provisioning changes | Manual access flow depends on this file |
| `lessons/templates/lessons/lesson_list.html` | Main landing/course page, guide modal, translator launcher, motivational UI | UI changes on home/course list | Large mixed-responsibility template |
| `lessons/templates/lessons/lesson_detail.html` | Lesson detail page, voice lesson mount, quiz UI | Lesson page UI or behavior changes | Large template with inline JS/CSS and multiple features |
| `lessons/templates/lessons/profile.html` | User-facing access dashboard, upgrade surface, account info, account deletion, classroom entry link | Profile UX, access presentation, upgrade CTA changes | Must stay aligned with view-computed access flags and `UserProfile` helpers |
| `static/js/voice-lesson.js` | Voice lesson WebRTC client | Voice bugs, OpenAI realtime issues | Long file, browser audio edge cases |
| `static/js/translator-assistant.js` | Translator assistant WebRTC client | Translator bugs | Similar complexity to voice lesson; easy duplication mistakes |
| `static/js/classroom-lesson.js` | Classroom session runtime | Classroom session/detection/attendance logic | WIP, large, browser-only detection stack, many thresholds |
| `static/js/classroom-voice-enroll.js` | Classroom voice enrollment modal | Voice sample enrollment fixes | WIP, MFCC/spectrum fallback complexity |
| `requirements.txt` | Python deps | New library, deploy failures, audio/image changes | Dependency drift and deploy mismatch |
| `Procfile` | Production process entrypoint | Deployment/runtime changes | WSGI entrypoint may not match realtime expectations |

## If Task Is About Lesson Flow, Open These First
- `lessons/views.py`
- `lessons/models.py`
- `lessons/urls.py`
- `lessons/templates/lessons/lesson_list.html`
- `lessons/templates/lessons/lesson_detail.html`

## If Task Is About Unlock / Access / Subscription, Open These First
- `lessons/models.py`
- `lessons/views.py`
- `lessons/middleware.py`
- `lessons/admin.py`
- `lessons/templates/lessons/advertisement.html`
- `lessons/templates/lessons/profile.html`

## If Task Is About Admin / Provisioning, Open These First
- `lessons/admin.py`
- `lessons/models.py`
- `lessons/management/commands/grant_voice_access.py`
- `lessons/management/commands/revoke_voice_access.py`
- `lessons/views.py`

## If Task Is About Realtime Voice, Open These First
- `lessons/views.py`
- `static/js/voice-lesson.js`
- `english_course/utils/realtime_tts.py`
- `lessons/templates/lessons/lesson_detail.html`
- `english_course/settings.py`

## If Task Is About Translator Assistant, Open These First
- `lessons/views.py`
- `static/js/translator-assistant.js`
- `lessons/templates/lessons/lesson_list.html`
- `lessons/models.py`
- `english_course/settings.py`

## If Task Is About Classroom, Open These First
- `lessons/views_classroom.py`
- `lessons/forms_classroom.py`
- `lessons/models.py`
- `lessons/templates/lessons/classroom/group_detail.html`
- `lessons/templates/lessons/classroom/session.html`
- `static/js/classroom-lesson.js`
- `static/js/classroom-voice-enroll.js`

## If Task Is About Templates / UI, Open These First
- `lessons/templates/lessons/lesson_list.html`
- `lessons/templates/lessons/lesson_detail.html`
- `lessons/templates/lessons/auth_base.html`
- `static/css/voice-lesson.css`
- `static/css/translator-assistant.css`
- Relevant feature JS file in `static/js/`

## If Task Is About Fixtures / Content, Open These First
- `lessons/fixtures/lessons.json`
- `lessons/fixtures/quiz_questions.json`
- `lessons/fixtures/explanations.json`
- `lessons/views.py`
- `lessons/models.py`
- `analyze_lessons.py` only if you verify it is actually relevant

## If Task Is About Deployment / Config, Open These First
- `english_course/settings.py`
- `Procfile`
- `requirements.txt`
- `english_course/asgi.py`
- `english_course/urls.py`
- `whatsapp_agent/views.py` if the deploy issue is on `/api/whatsapp/webhook/`
- `lessons/views.py` for `sw.js` and `manifest.json`

## Avoid Opening These Too Early Unless Needed
- `lessons/templates/lessons/lesson_list.html`
  - Huge template; only open once you know the bug is on the course list or translator launcher path.
- `lessons/templates/lessons/lesson_detail.html`
  - Huge template; avoid unless the bug is specifically on lesson detail, quiz UI, or voice lesson mount.
- `static/js/classroom-lesson.js`
  - Large WIP runtime file with many unrelated concerns.
- `static/js/voice-lesson.js`
  - Large file; do not open for generic access bugs unless voice is involved.
- `lessons/fixtures/*.json`
  - Large data dumps; open only the relevant fixture once you know the task is content/data related.
- `staticfiles/`
  - Generated output, not source of truth.
- `VOICE_LESSON_README.md`
  - Useful context, but partially stale relative to actual code.
- `CLASSROOM_MVP_NOTES.md`
  - Useful design notes, but code is the source of truth.
