# CLASSROOM_ARCHITECTURE.md

Use this with `PROJECT_CONTEXT.md`, `FILE_MAP.md`, and `KNOWN_RISKS.md`.

## Stable Baseline Classroom-Related Architecture
- Stable committed baseline does not appear to have a fully established classroom subsystem yet.
- The current classroom stack in this repo is local worktree WIP.
- Stable pieces reused by classroom WIP:
  - `UserProfile` access model in `lessons/models.py`
  - lesson content from `Lesson`
  - auth shell template `lessons/templates/lessons/auth_base.html`
  - voice token minting pattern from `lessons/views.py` and `static/js/voice-lesson.js`

## Current Local WIP: Classroom Overview
- Goal
  - Teacher accounts can create groups, add students/photos, enroll voice samples, and run a classroom AI session.
- Important warning
  - Treat all classroom behavior as WIP until committed. Verify in code before assuming production truth.

## Main Classroom Files

| File | Purpose |
| --- | --- |
| `lessons/views_classroom.py` | Backend for classroom dashboard, group/student CRUD, photo serving, voice embedding save, session token minting |
| `lessons/forms_classroom.py` | Group, student, multi-photo, and session-select forms |
| `lessons/models.py` | `ClassGroup`, `ClassStudent`, `StudentPhoto`, `UserProfile.role`, `voice_embeddings` |
| `lessons/templates/lessons/classroom/dashboard.html` | Teacher dashboard listing groups |
| `lessons/templates/lessons/classroom/group_detail.html` | Group roster, photo add, delete, standalone voice enrollment modal |
| `lessons/templates/lessons/classroom/session_select.html` | Select class + lesson before session |
| `lessons/templates/lessons/classroom/session.html` | Session runtime page with camera, roster, voice lesson container |
| `static/js/classroom-lesson.js` | Session runtime manager: face/hand/voice matching, attendance, OpenAI events |
| `static/js/classroom-voice-enroll.js` | Standalone voice enrollment flow used on group detail page |
| `CLASSROOM_MVP_NOTES.md` | Design notes and historical context; code is still source of truth |

## Classroom Data Model
- `UserProfile.role`
  - Teacher/student distinction for local WIP access checks.
- `ClassGroup`
  - Owned by teacher.
  - Unique by `(teacher, school_name, name)`.
- `ClassStudent`
  - Belongs to group.
  - Has `notes`, optional linked `user`, `face_embedding`, `voice_embeddings`.
- `StudentPhoto`
  - Stores uploaded images for a student.
- Verify in code before relying on `face_embedding`
  - The field exists, but current runtime appears to derive face descriptors in browser from photos each session rather than saving a server-side face embedding workflow.

## Backend / View Endpoints

| Route | Handler | Purpose |
| --- | --- | --- |
| `/classroom/` | `classroom_dashboard` | Teacher group list |
| `/classroom/new/` | `classroom_group_create` | Create class group |
| `/classroom/<group_id>/` | `classroom_group_detail` | Group roster and actions |
| `/classroom/<group_id>/edit/` | `classroom_group_edit` | Backfill/change school name |
| `/classroom/<group_id>/students/new/` | `classroom_student_create` | Add student and photos |
| `/classroom/student/<student_id>/photo/` | `classroom_student_add_photo` | Add more photos |
| `/classroom/student/<student_id>/voice/` | `classroom_student_voice_embedding` | Save voice embedding sample |
| `/classroom/student/<student_id>/delete/` | `classroom_student_delete` | Remove student |
| `/classroom/photo/<photo_id>/` | `classroom_student_photo` | Serve photo back to teacher/browser |
| `/classroom/session/` | `classroom_session_select` | Select group + lesson |
| `/classroom/session/<group_id>/<lesson_id>/` | `classroom_session` | Session runtime page |
| `/api/realtime/classroom/<lesson_id>/<group_id>/` | `mint_realtime_classroom_token` | Classroom-specific OpenAI Realtime session payload |

## Enrollment Flow
1. Teacher registers or has `role=teacher` in local WIP.
2. Teacher opens classroom dashboard and creates a `ClassGroup`.
3. Teacher adds students with photos.
4. Group detail page shows roster and launches `static/js/classroom-voice-enroll.js` for voice enrollment.
5. Browser records audio, extracts embeddings, and posts JSON to `/classroom/student/<student_id>/voice/`.
6. Backend appends embedding to `ClassStudent.voice_embeddings` and caps stored samples at 5.

## Session / Runtime Flow
1. Teacher opens session select page and chooses class + lesson.
2. Backend `classroom_session()` serializes roster data into the template:
   - student IDs
   - names
   - photo URLs
   - voice embeddings
3. Session template loads:
   - `voice-lesson.js`
   - `classroom-lesson.js`
   - external browser-side CV/audio libs
4. `ClassroomLessonManager` extends `VoiceLessonManager`.
5. Browser requests classroom realtime token from `/api/realtime/classroom/<lesson_id>/<group_id>/`.
6. Browser opens OpenAI Realtime session via WebRTC.
7. Browser-side logic handles face detection, hand raise matching, voice matching, attendance/time events, and sends event-style prompts into the OpenAI session.

## JS / Frontend Pieces
- `static/js/classroom-lesson.js`
  - Extends the normal voice lesson manager.
  - Handles camera preview.
  - Loads face/hand/voice tooling.
  - Sends classroom control events such as hand raise, voice detected, attendance, and time remaining.
- `static/js/classroom-voice-enroll.js`
  - Used on `group_detail.html`.
  - Handles recording, preview, MFCC extraction, spectrum fallback, and save.
- Verify in code before editing enrollment logic
  - `classroom-lesson.js` also contains voice enrollment methods, but the visible group-detail enrollment flow uses the standalone `classroom-voice-enroll.js` modal. Confirm which path is intended before consolidating behavior.

## Realtime / Websocket Interactions
- Intended classroom transport is not Django websocket.
- Classroom follows the same pattern as the voice lesson:
  - backend mints token
  - browser talks directly to OpenAI Realtime via WebRTC
- The only websocket code in repo is the older deprecated `lessons/consumers.py` route, which is not classroom-specific.

## External Browser Dependencies
- `face-api.js`
- `onnxruntime-web`
- `@mediapipe/face_detection`
- `@mediapipe/hands`
- `meyda`
- These are loaded from CDNs in `lessons/templates/lessons/classroom/session.html`.
- Verify in code before changing production behavior that CDN access, CSP, and browser support are acceptable.

## Fragile Or Incomplete Areas
- Entire classroom stack is WIP.
- Many thresholds and weights are configured inline in `session.html`.
- External models/libs are runtime dependencies.
- Accuracy depends on browser/device conditions.
- `face_embedding` persistence path is unclear from current flow; verify before using it.
- Voice enrollment logic is duplicated across files; verify intended source of truth.
- Classroom access is coupled to teacher role plus active voice access.

## If Asked To Modify Classroom, Read These Files First
- `lessons/views_classroom.py`
- `lessons/forms_classroom.py`
- `lessons/models.py`
- `lessons/templates/lessons/classroom/group_detail.html`
- `lessons/templates/lessons/classroom/session.html`
- `static/js/classroom-lesson.js`
- `static/js/classroom-voice-enroll.js`
- `KNOWN_RISKS.md`

## Verify In Code Before Editing
- Whether classroom is meant to be treated as production-ready or local-only WIP.
- Whether `UserProfile.role` behavior is fully merged or still local.
- Whether `face_embedding` should be persisted or ignored.
- Whether the duplicate voice enrollment logic should stay duplicated.
- Whether any deployment environment can actually support the required CDNs/browser APIs.
