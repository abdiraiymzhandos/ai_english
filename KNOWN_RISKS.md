# KNOWN_RISKS.md

Read this before editing access, realtime, templates, config, or fixtures.

## Ranked Risk List

### 1. `settings.py` import-time side effects and hard-coded config
- Description
  - `english_course/settings.py` raises if `OPENAI_API_KEY` is missing, prints on import, hard-codes `DEBUG`, `MEDIA_ROOT`, hosts, and secure-cookie behavior.
- Why it is risky
  - Import-time behavior can break management commands, tests, dumps, and local tooling.
  - Hard-coded values make deploy changes easy to get wrong.
- Affected files
  - `english_course/settings.py`
  - `lessons/fixtures/*.json`
- Symptoms to watch for
  - `dumpdata` output polluted with `✅ OpenAI API кілті сәтті жүктелді!`
  - unexpected startup failures when env vars are missing
  - local auth/session oddities because secure cookies are forced in debug
- Safe-edit advice
  - Change settings incrementally.
  - Re-check management commands and fixture output after any edit.
  - Separate “make configurable” work from unrelated feature work.

### 2. Historical deprecated websocket consumer remains in the repo
- Description
  - `lessons/consumers.py` is deprecated historical code for the old websocket bridge. It is no longer exposed by active routing, but it remains in the repo and can still mislead future work.
- Why it is risky
  - Future engineers can debug the wrong realtime path or accidentally reintroduce an expensive old flow.
- Affected files
  - `lessons/consumers.py`
  - `lessons/routing.py`
  - `english_course/asgi.py`
  - `VOICE_LESSON_README.md`
- Symptoms to watch for
  - confusion between WebRTC and websocket implementations
  - duplicate OpenAI session usage
  - websocket voice traffic appearing during supposedly WebRTC-only flows
- Safe-edit advice
  - Treat the active interactive path as token minting plus browser WebRTC by default.
  - If you touch routing or ASGI, do not reintroduce this consumer casually.

### 3. Access logic is split across many layers
- Description
  - Access decisions still span views, templates, middleware, session state, `UserProfile`, admin actions, and management commands, even though the main stable checks now have `UserProfile` helper methods.
- Why it is risky
  - Small changes can create inconsistent behavior between guest/auth users or UI/backend checks.
- Affected files
  - `lessons/models.py`
  - `lessons/views.py`
  - `lessons/middleware.py`
  - `lessons/admin.py`
  - templates under `lessons/templates/lessons/`
- Symptoms to watch for
  - user sees feature CTA but backend rejects token request
  - lessons visible in list but inaccessible in detail
  - admin marks user paid but voice/translator still blocked
- Safe-edit advice
  - Start with `UserProfile` helpers, then trace both page rendering and API/token checks.
  - Verify guest, regular user, paid user, and expired-access user separately.

### 4. Large mixed-responsibility templates
- Description
  - `lesson_list.html` and `lesson_detail.html` mix layout, styling, inline JS, product rules, and feature mounts.
- Why it is risky
  - Easy to break unrelated behavior when making small UI edits.
- Affected files
  - `lessons/templates/lessons/lesson_list.html`
  - `lessons/templates/lessons/lesson_detail.html`
- Symptoms to watch for
  - regressions in translator launcher, voice mount, modal behavior, or quiz UI
  - CSS/JS side effects from “small” template edits
- Safe-edit advice
  - Search within the whole template before editing one block.
  - Re-test all feature mounts on that page, not just the target change.

### 5. `generate_quiz_questions()` rebuilds DB data during request handling
- Description
  - `start_quiz()` calls `generate_quiz_questions()` and deletes/recreates quiz questions based on lesson vocabulary text.
- Why it is risky
  - Runtime requests mutate content-derived DB state.
  - Formatting changes in vocabulary can silently break quizzes.
- Affected files
  - `lessons/views.py`
  - `lessons/models.py`
  - `lessons/fixtures/lessons.json`
- Symptoms to watch for
  - missing quiz choices
  - unstable question sets
  - quiz failures after content edits
- Safe-edit advice
  - Treat content formatting and quiz generation as coupled.
  - Verify quiz generation after any vocabulary edit.

### 6. Weak or absent automated tests
- Description
  - `lessons/tests.py` is effectively empty. Realtime diagnostics are scripts, not regression tests.
- Why it is risky
  - Most regressions will only be caught manually.
- Affected files
  - `lessons/tests.py`
  - `lessons/test_realtime_diag.py`
  - `lessons/test_realtime_kk.py`
- Symptoms to watch for
  - regressions escaping until manual QA
- Safe-edit advice
  - Run focused manual verification for every changed flow.
  - Add narrow tests when touching stable logic if feasible.

### 7. Deployment drift between WSGI, ASGI, and channels
- Description
  - Channels and ASGI exist, but `Procfile` points to WSGI.
- Why it is risky
  - It is easy to assume a deploy topology that is not actually active.
- Affected files
  - `Procfile`
  - `english_course/asgi.py`
  - `english_course/settings.py`
- Symptoms to watch for
  - websocket expectations failing in production
  - routing changes having no effect
- Safe-edit advice
  - Verify actual deployment entrypoint before changing realtime/server transport behavior.

### 8. Fixture dumps are polluted and content files are format-sensitive
- Description
  - Fixture JSON files start with a printed line, and quiz generation relies on exact vocabulary formatting.
- Why it is risky
  - Tooling that assumes clean JSON fails.
  - Content edits can break runtime generation.
- Affected files
  - `lessons/fixtures/*.json`
  - `english_course/settings.py`
  - `lessons/views.py`
- Symptoms to watch for
  - JSON parse errors
  - malformed dumps
  - quiz generation issues
- Safe-edit advice
  - Clean or regenerate fixtures only after disabling noisy settings output.
  - Validate content format after edits.

### 9. Classroom stack is local WIP and browser-heavy
- Description
  - Classroom introduces teacher role logic, new models/views/templates, browser-side CV/audio tooling, and many tunable thresholds.
- Why it is risky
  - It is not stable baseline yet.
  - Performance and accuracy depend on browser/runtime conditions and external CDNs.
- Affected files
  - `lessons/views_classroom.py`
  - `lessons/forms_classroom.py`
  - `static/js/classroom-lesson.js`
  - `static/js/classroom-voice-enroll.js`
  - classroom templates
- Symptoms to watch for
  - feature works locally but not elsewhere
  - camera/mic/detection failures
  - incorrect student matching
- Safe-edit advice
  - Verify in code before assuming intended behavior.
  - Separate classroom changes from stable lesson/access changes.

### 10. Docs drift from code
- Description
  - `VOICE_LESSON_README.md` and `CLASSROOM_MVP_NOTES.md` are helpful, but code has moved.
- Why it is risky
  - Future work can be based on outdated assumptions.
- Affected files
  - `VOICE_LESSON_README.md`
  - `CLASSROOM_MVP_NOTES.md`
  - related code files
- Symptoms to watch for
  - editing the wrong transport path
  - assuming stored face embeddings or older websocket flows
- Safe-edit advice
  - Treat docs as secondary.
  - Confirm behavior in code before implementing.

## Before Editing Checklist
- Read `PROJECT_CONTEXT.md`.
- Read `FILE_MAP.md` and identify the smallest set of relevant source files.
- If touching config, read `english_course/settings.py` fully first.
- If touching access, trace both UI and backend/token checks.
- If touching realtime, verify whether the task is on the active WebRTC flow or only on historical websocket reference code.
- If touching content/quiz logic, inspect vocabulary formatting and fixture state first.
- If touching classroom, confirm whether the behavior is stable baseline or local WIP.

## After Editing Verification Checklist
- Confirm imports and startup still work with current env assumptions.
- Re-check the exact affected route and any related API/token endpoint.
- Re-test the user states that matter: guest, authenticated, paid, expired, teacher if relevant.
- Re-test both template rendering and backend enforcement for access-sensitive changes.
- If changing templates, test all mounted features on that page.
- If changing content/quiz logic, verify quiz generation still works on a representative lesson.
- If changing realtime logic, verify token minting, browser connection, and cleanup/timeout paths.
- If changing settings or fixture workflow, confirm fixture output is still valid and unpolluted.
