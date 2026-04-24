# Classroom MVP Notes

## Goal (Why we are building this)
Build a classroom / group mode for the English AI teacher that can teach 10–20 students at once, identify students by face, and respond to hand-raise events by calling the student by name. The MVP must run on a single teacher laptop with browser-only processing for maximum privacy (no camera frames uploaded). The system should feel like a real classroom lesson: AI asks questions, waits for answers, and adapts to lesson context.

### MVP outcomes we want
- Teacher can register as a teacher, create class groups (e.g., 7A), and add students + photos for training.
- In the classroom session, the camera recognizes student faces locally.
- When a student raises a hand, AI calls that student by name and asks a short question.
- No video frames or biometric processing leave the teacher’s browser.

This file documents what was added/changed to support the classroom (group) mode with browser-only face/hand detection.

## Summary
- Added teacher/student roles during registration and stored on user profiles.
- Added classroom data models (class groups, students, student photos).
- Added school name on class groups to isolate data per school + class.
- Added teacher-only classroom pages to manage classes/students and start a session.
- Added a classroom Realtime token endpoint with group-aware instructions.
- Added a classroom session UI with camera preview, detection controls, and roster.
- Added browser-only face recognition (face-api.js) and hand-raise detection (MediaPipe Hands).
- Added ArcFace recognition (onnxruntime-web + MediaPipe Face Detection) with face-api.js fallback and higher-res camera capture.
- Added voice enrollment during student onboarding (group detail screen), saved on server.
- Added voice recognition (MFCC + cosine) to detect speakers when camera misses students.
- Added a voice enrollment modal UI (record/stop/re-record/save + preview) with spectrum fallback to avoid "insufficient sample" errors.
- Added in-session voice recognition status messaging (recognized/candidate/unknown) with auto-clear and tuned thresholds.
- Added confidence fusion (face + voice + hand raise) with low-confidence confirmation.
- Fixed face recognition model loading (valid CDN + fallback) and improved error messaging.
- Enabled multi-photo upload (up to 10 at once) for student photos.
- Tightened access control for unpaid teachers and premium voice/face features.

## New/Updated Backend

### User role (teacher/student)
- `lessons/models.py`
  - Added `role` to `UserProfile` with `student/teacher` choices.
  - Added `is_teacher()` helper.
- `lessons/forms.py`
  - Added `role` field to `CustomRegisterForm`.
- `lessons/views.py`
  - Registration now saves `role` into `UserProfile`.
- `lessons/templates/lessons/register.html`
  - Added role selector UI.
- `lessons/templates/lessons/profile.html`
  - Added classroom link for teacher accounts.

### Classroom models
- `lessons/models.py`
  - `ClassGroup`: teacher-owned class (e.g., 7A).
  - `ClassGroup.school_name`: required school name for isolation.
  - `ClassStudent`: student records with optional notes and face embedding placeholder.
  - `ClassStudent.voice_embeddings`: list of voice embeddings saved on server (pilot).
  - `StudentPhoto`: photo storage for face recognition training.
  - `student_face_upload_path()` for photo upload path.

### Classroom views and forms
- `lessons/forms_classroom.py`
  - `ClassGroupForm` now includes required `school_name`.
  - `ClassStudentForm`, `StudentPhotoForm`, `ClassroomSessionSelectForm`.
- `lessons/views_classroom.py`
  - Teacher-only screens: dashboard, group create/detail, student create/delete, add photo.
  - Minimal class edit view to backfill `school_name` (name locked).
  - Session selection and session view.
  - Photo serving endpoint (teacher-only).
  - Voice embedding endpoint (teacher-only).
  - `mint_realtime_classroom_token()` for group-aware session instructions.

### URLs
- `lessons/urls.py`
  - Added classroom routes and the classroom realtime token endpoint:
    - `/classroom/`, `/classroom/new/`, `/classroom/<group_id>/`, etc.
    - `/classroom/<group_id>/edit/` (school name only)
    - `/classroom/session/` and `/classroom/session/<group_id>/<lesson_id>/`
    - `/api/realtime/classroom/<lesson_id>/<group_id>/`
    - `/classroom/student/<student_id>/voice/` (save voice embedding)

## Frontend and UI

### Classroom templates
- `lessons/templates/lessons/classroom/dashboard.html`
- `lessons/templates/lessons/classroom/group_form.html`
- `lessons/templates/lessons/classroom/group_detail.html`
- `lessons/templates/lessons/classroom/student_form.html`
- `lessons/templates/lessons/classroom/student_photo_form.html`
- `lessons/templates/lessons/classroom/student_delete.html`
- `lessons/templates/lessons/classroom/session_select.html`
- `lessons/templates/lessons/classroom/session.html`

### Classroom JS
- `static/js/classroom-lesson.js`
  - Extends `VoiceLessonManager`.
  - Loads face-api.js models and MediaPipe Hands.
  - Builds a `FaceMatcher` from roster photos.
  - Tracks hands and detects raises relative to face bounding boxes.
  - Sends `EVENT: HAND_RAISE name=<StudentName>` to the Realtime session.
  - Sends `EVENT: CONFIRM_STUDENT candidate=<StudentName>` when confidence is low.
  - Sends `EVENT: TIME_REMAINING minutes=<m> seconds=<s>` for pacing.
  - Sends `EVENT: ATTENDANCE present=<names> missing=<names>` silently.
  - Sends `EVENT: VOICE_DETECTED name=<StudentName>` when voice is matched.
  - Shows voice recognition status messages in the session UI (recognized/candidate/unknown).
  - Adds confidence fusion (face + voice + hand raise) before calling a student.
  - Draws face boxes + labels + hand markers on a canvas overlay.
  - Adds model-loading fallback to `/static/models/face-api` and clearer detection errors.
- `static/js/classroom-voice-enroll.js`
  - Voice enrollment flow on the group detail screen.
  - Recorder modal UI with preview, re-record, and save.
  - Captures MFCC frames live and falls back to spectrum frames if needed.
  - Averages, normalizes, and saves embeddings to server.

### Classroom session UI updates
- `lessons/templates/lessons/classroom/session.html`
  - Added canvas overlay for detection.
  - Added start/stop detection buttons.
  - Added CDN scripts for `face-api.js` and `@mediapipe/hands`.
  - Added CDN script for `meyda` (MFCC extraction).
  - Added `window.CLASSROOM_FACE_MODEL_URL` and `window.CLASSROOM_HANDS_ASSET_URL` config.
  - Updated face-api weights URL to a valid CDN path.
  - Added roll-call button (student self-confirmation only).
  - Voice config tweaks: `CLASSROOM_VOICE_DISPLAY_THRESHOLD`, lower `CLASSROOM_VOICE_MIN_RMS` for easier activation.

## Privacy Design (Browser-only)
- Camera frames are processed in the browser only.
- Face recognition uses local photo URLs and face-api.js in the browser.
- No video frames are uploaded to the server or external services.
- Voice embeddings are stored server-side for pilot persistence (no raw audio uploaded).

## Dependencies
- `requirements.txt`
  - Added `Pillow` for image handling in Django.

## Fixes Applied (Sep 2024)

### 1) Face Recognition Not Starting
**Symptom:** Clicking “Face/Hand Detection” showed “Detection іске қосылмады”.  
**Root cause:** Face-api model weights were loaded from `https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/weights`, which does not include weights (404).  
**Fix:** Use a valid weights CDN and add a fallback to local `/static/models/face-api`. Surface the real error message in UI.

Files:
- `lessons/templates/lessons/classroom/session.html`
- `static/js/classroom-lesson.js`

### 2) Multi-Photo Upload (Up to 10 at Once)
**Problem:** Student photos could only be added one by one.  
**Fix:** Added a multiple-image field with max-10 validation, updated views to save all uploaded images, and updated UI hints.

Files:
- `lessons/forms_classroom.py`
- `lessons/views_classroom.py`
- `lessons/templates/lessons/classroom/student_form.html`
- `lessons/templates/lessons/classroom/student_photo_form.html`

### 3) Paid Access for Teachers (Voice + Classroom)
**Problem:** Teachers who selected “Мен мұғаліммін” could access premium lessons or start classroom voice/face sessions without admin approval.  
**Fix:** Classroom session + realtime token now require `has_active_voice_access`. Unpaid teachers only see free lessons. Voice token endpoint rejects users without voice access.

Files:
- `lessons/views_classroom.py`
- `lessons/views.py`

## How to Test Locally
1) Install dependencies:
   - `pip install -r requirements.txt`
2) Create migrations and migrate:
   - `python manage.py makemigrations lessons`
   - `python manage.py migrate`
3) Register a user as "teacher".
4) Go to `/classroom/` and create a class (e.g., 7A) with a school name.
5) Add students with 3-5 photos each for better recognition.
6) In the class detail screen, add 1–3 voice samples per student.
6) Start a classroom session and click:
   - "Камераны қосу"
   - "Face/Hand Detection"
   - Start the voice lesson
7) Raise a hand in front of the camera and confirm AI asks by name.
8) If confidence is low, AI asks the student to confirm their name.
8) Add 5–10 photos at once on student create / add photo and confirm all are saved.
9) Test access control: unpaid teacher should not start classroom session until voice access is granted in admin.

## Optional Offline Models
If you want fully offline face detection weights:
- Download the face-api weights to `static/models/face-api`.
- Update `window.CLASSROOM_FACE_MODEL_URL` in `lessons/templates/lessons/classroom/session.html` to use local path.

## Next Improvements (planned / open items)
1) **Face recognition accuracy**
  - Add multiple photos per student (5–10 angles, lighting).
  - Add a per-student confidence indicator in the roster UI.
  - Add a manual correction UI (click a face box → select student name) to improve matching.

2) **Hand raise detection reliability**
   - Add smoothing and debounce for hand raises (e.g., sustained raise for N frames).
   - Allow per-classroom tuning for threshold/cooldown.
   - Track left/right hand and ignore non-raise gestures.

3) **Better classroom orchestration**
   - Add “next student” queue logic (rotate through class).
   - Add “ask the whole class” mode and timed follow-up prompts.
   - Add per-student participation tracking (local counters only).

4) **Privacy hardening**
   - Option to store no photos at all (only in-memory embeddings).
   - One-click “erase roster photos” per class.
   - Clear consent text shown to teachers before enabling detection.

5) **UX improvements**
  - Show overlay badges: “Recognized” / “Unknown”.
  - Display last question asked + who is speaking.
  - Add a simple “class status” panel (camera on, detection on, AI connected).

## Next Tasks (after latest fixes)
1) Verify face model loading in production (CSP/mixed-content not blocking CDN).
2) Add recognition confidence UI in roster and/or overlay badges.
3) Add hand-raise smoothing + cooldown controls per classroom.
4) Consider saving embeddings to DB to avoid reprocessing on each session.

## Voice Recognition (Pilot)
Goal: identify students by voice when the camera can't see everyone.

### Enrollment (before lesson)
- Location: class detail page (`group_detail`).
- Teacher clicks "Дауыс үлгісі" for each student.
- Recorder modal: start/stop/re-record/save + audio preview.
- Records ~10 seconds (configurable) and extracts MFCC frames (Meyda).
- If MFCC frames are missing, uses a spectrum (AnalyserNode) fallback so it still saves.
- Saves to server via `POST /classroom/student/<student_id>/voice/`.
- Stored on `ClassStudent.voice_embeddings` (max 5 samples).

### Runtime matching (during lesson)
- `static/js/classroom-lesson.js` builds a voice embedding map from roster.
- Uses cosine similarity vs stored samples.
- Emits `EVENT: VOICE_DETECTED name=<StudentName> confidence=<0-1>`.
- Shows UI status messages: recognized / candidate / unknown (auto-clears).
- Silent by default in AI audio; only used for internal state and confidence fusion.

### Voice Config (session.html)
- `CLASSROOM_VOICE_MATCH_THRESHOLD` (match quality).
- `CLASSROOM_VOICE_DISPLAY_THRESHOLD` (show “candidate” message).
- `CLASSROOM_VOICE_MIN_RMS` (speech activation).
- `CLASSROOM_VOICE_STATUS_TIMEOUT_MS` (UI message auto-clear, default 6000).

## Confidence Fusion (Face + Voice + Hand Raise)
Goal: avoid wrong calls when confidence is low.

### Logic
- Face confidence: derived from ArcFace score or face-api distance.
- Voice confidence: recent voice match within a freshness window.
- Hand raise: adds a small boost.
- Final fusion score = weighted average.
- If fusion score < threshold → send `EVENT: CONFIRM_STUDENT candidate=<StudentName>`.
  - AI must ask the student to confirm their name (no teacher involvement).

### Defaults (config)
- `CLASSROOM_FUSION_THRESHOLD = 0.7`
- `CLASSROOM_FUSION_FACE_WEIGHT = 0.5`
- `CLASSROOM_FUSION_VOICE_WEIGHT = 0.35`
- `CLASSROOM_FUSION_HAND_WEIGHT = 0.15`
- `CLASSROOM_VOICE_FRESH_WINDOW_MS = 15000`

## Attendance & Voice Event Policy
- Attendance/voice events are silent by default.
- AI should only acknowledge after a student responds to a confirmation prompt.
- Roll-call button triggers a student self-identification prompt, not a list readout.

## ArcFace (InsightFace) Integration (Current)
Goal: Use ArcFace-level embeddings in-browser with a safe fallback to face-api.js.

### Current ArcFace Stack
- **Models:** ArcFace ONNX + MediaPipe Face Detection (full-range model).
- **Runtime:** onnxruntime-web (WebGPU/WebGL/WASM).
- **Flow:** detect faces → align by eyes → 112x112 crop → ArcFace embedding → cosine match.
- **Preprocess:** RGB, 112x112, normalized (x - 127.5) / 128, NHWC tensor.
- **Fallback:** If ArcFace fails to load, auto-switch to face-api.js.
- **Key files:**
  - `static/js/classroom-lesson.js` (ArcFace pipeline, alignment, matching)
  - `lessons/templates/lessons/classroom/session.html` (CDN scripts + config)

### Config (session.html)
- `window.CLASSROOM_USE_ARCFACE` (true/false)
- `window.CLASSROOM_ARCFACE_MODEL_URL`
- `window.CLASSROOM_ORT_WASM_URL`
- `window.CLASSROOM_FACE_DETECTOR_ASSET_URL`
- `window.CLASSROOM_FACE_DETECTOR_MODEL` (`full` recommended for long distance)
- `window.CLASSROOM_FACE_DETECTOR_MIN_CONF` (lower to detect smaller faces)
- `window.CLASSROOM_ARCFACE_THRESHOLD` (typical 0.35–0.6)
- `window.CLASSROOM_ARCFACE_COLOR_ORDER` (`rgb` default)
- `window.CLASSROOM_MIN_FACE_SIZE`
- `window.CLASSROOM_MAX_FACES`

### Optional Local Models
- Place ArcFace at `static/models/arcface/arcface.onnx`.
- Update `CLASSROOM_ARCFACE_MODEL_URL` to `/static/models/arcface/arcface.onnx`.
- MediaPipe Face Detection assets can also be hosted locally if needed.
- Default CDN ArcFace model is large (~136 MB), so local hosting improves load time.

### Future Enhancements (ArcFace)
1) Save embeddings to DB to avoid recomputation (privacy decision).
2) Replace MediaPipe detector with RetinaFace if accuracy is still limited at long range.
3) Add per-student confidence indicators in the roster UI.

### Performance Notes
- ArcFace in browser is heavier; WebGPU/WebGL improves FPS.
- High-res camera input helps recognition at 3m more than model changes alone.

### Testing Checklist for ArcFace
1) Models load without 404s.
2) Real-time detection runs >10 FPS on teacher laptop.
3) Accuracy improves on varied angles/light and at 3m.
4) No face/hand data leaves browser.

## Open Questions / Decisions
- Should we store only embeddings in the DB and delete photos after enrollment?
- Do we want a strict “no storage” mode with local-only photos and embeddings?
- Do we need bilingual classroom instructions (Kazakh + Russian) in group mode?

## Short Explanation for Future Agents
We are building a classroom mode for the AI English teacher. The teacher creates classes and uploads student photos. In the session, the browser runs face recognition (ArcFace pipeline with face-api.js fallback) and hand detection (MediaPipe Hands) locally. When a hand raise is detected and matched to a known student, the system sends an `EVENT: HAND_RAISE name=...` message to the OpenAI Realtime session, prompting the AI to ask that student a question by name. Privacy is priority: no camera frames are uploaded, all detection happens in-browser. The goal now is to improve recognition accuracy, hand-raise reliability, and classroom orchestration while keeping privacy-first design.

## Files Touched (quick list)
- `lessons/models.py`
- `lessons/forms.py`
- `lessons/views.py`
- `lessons/views_classroom.py` (new)
- `lessons/forms_classroom.py` (new)
- `lessons/urls.py`
- `lessons/templates/lessons/register.html`
- `lessons/templates/lessons/profile.html`
- `lessons/templates/lessons/classroom/*.html` (new)
- `static/js/classroom-lesson.js` (new)
- `static/js/classroom-voice-enroll.js` (new)
- `lessons/templates/lessons/classroom/session.html`
- `requirements.txt`

## File Map (what each file does)
- `CLASSROOM_MVP_NOTES.md`: canonical context for classroom MVP, changes, and policies.
- `lessons/models.py`: classroom data models (ClassGroup, ClassStudent, StudentPhoto, voice embeddings).
- `lessons/migrations/0011_userprofile_role_classgroup_classstudent_and_more.py`: initial classroom schema.
- `lessons/migrations/0012_classstudent_voice_embeddings.py`: adds voice embedding storage.
- `lessons/migrations/0013_alter_classgroup_unique_together_and_more.py`: adds `school_name` + uniqueness.
- `lessons/forms_classroom.py`: forms for class create/edit, student create, photo upload, session select.
- `lessons/views_classroom.py`: teacher-only classroom views, token minting, instructions, voice embedding API.
- `lessons/urls.py`: routes for classroom pages, realtime token, and voice embedding endpoint.
- `lessons/templates/lessons/classroom/dashboard.html`: list classes and start sessions.
- `lessons/templates/lessons/classroom/group_form.html`: create/edit class (school name).
- `lessons/templates/lessons/classroom/group_detail.html`: roster + onboarding voice enrollment.
- `lessons/templates/lessons/classroom/student_form.html`: create student + photo upload.
- `lessons/templates/lessons/classroom/student_photo_form.html`: add photos to an existing student.
- `lessons/templates/lessons/classroom/student_delete.html`: delete student confirmation.
- `lessons/templates/lessons/classroom/session_select.html`: pick class + lesson.
- `lessons/templates/lessons/classroom/session.html`: live classroom session UI + JS config.
- `static/js/voice-lesson.js`: WebRTC voice lesson engine (timer, session, data channel).
- `static/js/classroom-lesson.js`: classroom runtime (face/hand/voice detect, fusion, events).
- `static/js/classroom-voice-enroll.js`: onboarding voice enrollment and server save.
- `requirements.txt`: backend dependencies (Pillow for image handling).
