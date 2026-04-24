# TASK_PLAYBOOK.md

## How Future Codex Should Work
1. Read `PROJECT_CONTEXT.md` first
2. Read `FILE_MAP.md` and `FEATURES_MAP.md`
3. Read `KNOWN_RISKS.md` before changing sensitive areas
4. Open only relevant source files
5. Avoid full-repo rescans unless necessary

## UI Bug Playbook
- First files to inspect
  - Relevant template under `lessons/templates/lessons/`
  - Related JS in `static/js/`
  - Related CSS in `static/css/`
- Likely root causes
  - inline JS/CSS conflicts
  - template conditional rendering mismatch
  - backend not passing expected context
- Safe sequence of investigation
  - Confirm which page owns the UI.
  - Inspect template conditions and mounted JS.
  - Inspect backend view only if context-driven.
- What not to break
  - Other feature mounts on the same page.
- Quick verification steps
  - Reload page.
  - Verify desktop/mobile basics.
  - Test adjacent UI on the same page.

## Lesson Progression Bug Playbook
- First files to inspect
  - `lessons/views.py`
  - `lessons/models.py`
  - `lessons/templates/lessons/lesson_list.html`
  - `lessons/templates/lessons/lesson_detail.html`
- Likely root causes
  - session `passed_lessons` drift
  - `QuizAttempt` state mismatch
  - free lesson / paid lesson boundary logic
  - alternate-track ID assumptions
- Safe sequence of investigation
  - Trace `lesson_list()` unlock logic.
  - Trace `lesson_detail()` gating logic.
  - Trace `submit_answer()` progression update.
- What not to break
  - Guest progression.
  - Main vs `251+` track behavior.
- Quick verification steps
  - Test guest.
  - Test authenticated unpaid user.
  - Test paid user.
  - Test a lesson below `251` and one above.

## Access / Subscription Bug Playbook
- First files to inspect
  - `lessons/models.py`
  - `lessons/views.py`
  - `lessons/admin.py`
  - `lessons/middleware.py`
  - related template
- Likely root causes
  - wrong `UserProfile` flags
  - expired access dates
  - template/UI and backend checks diverging
  - middleware lock/device behavior
- Safe sequence of investigation
  - Inspect `UserProfile` helpers first: `is_locked()`, `has_paid_lesson_access()`, `has_active_voice_access()`, `has_active_translator_access()`, `can_use_classroom_teacher_features()`, `can_run_classroom_voice_sessions()`.
  - Inspect backend gate for the feature.
  - Inspect page-level conditional rendering.
  - Inspect admin actions if provisioning-related.
- What not to break
  - Paid lesson access while fixing voice/translator access.
  - Device lock behavior unless explicitly in scope.
- Quick verification steps
  - Check exact `UserProfile` state.
  - Hit page and API/token endpoint.
  - Verify behavior before and after expiry.

## Admin Provisioning Issue Playbook
- First files to inspect
  - `lessons/admin.py`
  - `lessons/models.py`
  - `lessons/management/commands/grant_voice_access.py`
  - `lessons/management/commands/revoke_voice_access.py`
- Likely root causes
  - admin action only changes one flag
  - operator expects `is_paid` to imply voice or translator access
  - missing profile or stale profile state
- Safe sequence of investigation
  - Identify which access type failed.
  - Check the corresponding admin action/helper.
  - Confirm whether a management command exists or not.
- What not to break
  - Existing admin workflows.
- Quick verification steps
  - Verify admin action result on `UserProfile`.
  - Verify end-user page/API behavior after provisioning.

## Realtime Voice Bug Playbook
- First files to inspect
  - `lessons/views.py`
  - `static/js/voice-lesson.js`
  - `lessons/templates/lessons/lesson_detail.html`
  - `english_course/settings.py`
- Likely root causes
  - token mint failure
  - missing voice access
  - WebRTC/browser microphone issue
  - keepalive/timeout regression
- Safe sequence of investigation
  - Confirm page mount condition.
  - Confirm `/api/realtime/token/<lesson_id>/` response path.
  - Inspect client connection setup and cleanup.
  - Check settings/env only if server token mint fails.
- What not to break
  - explanation generation and translator flow
  - historical deprecated websocket consumer should not be reintroduced by accident
- Quick verification steps
  - Start/stop session.
  - Confirm audio connects.
  - Confirm timeout/cleanup still works.

## Classroom Bug Playbook
- First files to inspect
  - `lessons/views_classroom.py`
  - `lessons/forms_classroom.py`
  - relevant classroom template
  - `static/js/classroom-lesson.js`
  - `static/js/classroom-voice-enroll.js`
- Likely root causes
  - teacher/voice access gating
  - photo or voice enrollment save path
  - external browser/CDN dependency
  - WIP logic drift between template and JS
- Safe sequence of investigation
  - Confirm whether the bug is enrollment, management, or session runtime.
  - Check whether the relevant guard should use `can_use_classroom_teacher_features()` or `can_run_classroom_voice_sessions()`.
  - Trace backend route first.
  - Then trace template mount.
  - Then inspect client-side detection/enrollment logic.
- What not to break
  - Stable voice lesson flow.
  - Non-classroom access logic.
- Quick verification steps
  - Teacher can access page.
  - Group/student create works.
  - Voice save endpoint responds.
  - Session page loads roster and starts token flow.

## Websocket / Routing Bug Playbook
- First files to inspect
  - `lessons/routing.py`
  - `lessons/consumers.py`
  - `english_course/asgi.py`
  - `static/js/voice-lesson.js`
- Likely root causes
  - confusion between historical websocket code and intended WebRTC path
  - wrong deployment entrypoint
- Safe sequence of investigation
  - Determine whether the bug is actually in active product flow.
  - Confirm whether the task is about historical websocket code or active WebRTC flow.
  - Only then change routing/consumer code.
- What not to break
  - Current WebRTC-only voice lesson path.
- Quick verification steps
  - Verify active client path.
  - Verify no duplicate OpenAI connection path is introduced.

## Fixture / Content Bug Playbook
- First files to inspect
  - relevant file in `lessons/fixtures/`
  - `lessons/views.py`
  - `lessons/models.py`
  - `FIXTURE_CONTENT_WORKFLOW.md`
- Likely root causes
  - polluted fixture output
  - vocabulary delimiter mismatch
  - stale explanation rows after lesson edits
- Safe sequence of investigation
  - Confirm whether the issue is fixture parsing, runtime content, or quiz generation.
  - Inspect exact content formatting.
  - Inspect generation/update code.
- What not to break
  - lesson IDs and track boundaries
  - existing explanation uniqueness assumptions
- Quick verification steps
  - Parse affected fixture.
  - Test representative lesson quiz generation.
  - Confirm explanation/audio still resolves.

## Deployment / Config Bug Playbook
- First files to inspect
  - `english_course/settings.py`
  - `Procfile`
  - `requirements.txt`
  - `english_course/asgi.py`
  - `ENVIRONMENT_DEPLOYMENT.md`
- Likely root causes
  - env var missing
  - static/media path mismatch
  - WSGI/ASGI confusion
  - secure-cookie behavior in current environment
- Safe sequence of investigation
  - Confirm config source and current environment.
  - Inspect settings.
  - Inspect runtime entrypoint.
  - Inspect related view/static behavior.
- What not to break
  - local dev assumptions while changing deploy config
- Quick verification steps
  - App starts.
  - Key routes load.
  - static/media/PWA files resolve.
  - token mint endpoints still work.

## Refactor Task Playbook
- First files to inspect
  - `FILE_MAP.md`
  - `FEATURES_MAP.md`
  - `KNOWN_RISKS.md`
  - exact source files in scope
- Likely root causes of failed refactors
  - hidden cross-coupling in templates and access logic
  - stale docs being mistaken for source of truth
- Safe sequence of investigation
  - Identify the smallest safe boundary.
  - Map inputs, outputs, and shared dependencies.
  - Refactor one layer at a time.
  - Re-run focused manual checks after each slice.
- What not to break
  - session-backed progression
  - `UserProfile` access semantics
  - realtime token APIs
- Quick verification steps
  - Compare behavior before/after on one representative flow per affected feature.

## Default Prompt Template For Future Tasks
```text
Read PROJECT_CONTEXT.md, FILE_MAP.md, FEATURES_MAP.md, and KNOWN_RISKS.md first.

Task:
<describe the bug/change clearly>

Constraints:
<list constraints>

Please inspect only the files relevant to this task first.
Do not rescan the whole repo unless needed.
If the task touches config, access, realtime, or classroom, say which files you are using before editing.
```
