# Realtime and quiz contracts

Audit snapshot: 2026-07-10. These are current technical invariants, not product pricing/behavior promises.

## Realtime configuration

- Active shared model constant: `REALTIME_MODEL = "gpt-realtime-2"` in `english_course/realtime_config.py`.
- Django mints ephemeral browser credentials through the configured `/v1/realtime/client_secrets` endpoint.
- The standard OpenAI API key must remain server-side.
- Browser clients create one `oai-events` data channel and post SDP to `/v1/realtime/calls` with the ephemeral credential.
- Browser audio plays through the remote WebRTC track. Clients consume text/transcript/control events; they do not need to decode server `response.output_audio.delta` for playback.
- Backend explanation TTS is different: it connects to the Realtime WebSocket, collects `response.output_audio.delta`, converts PCM to MP3, and never owns persistence.
- `OpenAI-Safety-Identifier` is a SHA-256 hash of internal user ID or anonymous session key.

Entry points:

| Feature | Django | Browser/backend |
| --- | --- | --- |
| Individual voice | `lessons.views.mint_realtime_token` | `static/js/voice-lesson.js` |
| Translator | `lessons.views.mint_translator_token` | `static/js/translator-assistant.js` |
| Classroom | `lessons.views_classroom.mint_realtime_classroom_token` | `static/js/classroom-lesson.js` |
| Explanation audio | `english_course.utils.realtime_tts.synthesize_audio_realtime_mp3` | Backend WebSocket |

## Prompt warning

Current pre-existing worktree state selects `_content_creator_instructions()` for individual voice. That prompt does not use the lesson and conflicts with the learner voice product. `_teacher_instructions(lesson)` remains in code but is not selected. Intent is `Needs product-owner confirmation`; track resolution as `BUG-002`.

Classroom instructions include lesson and roster names. Translator uses an inline interpreter prompt. See [AI integrations](AI_INTEGRATIONS.md).

## Realtime security/cost rules

- Token routes require POST, CSRF, authentication, and their feature entitlement.
- Never return the standard key or a raw internal user ID.
- Provider errors returned to clients must be generic; logs must be redacted.
- Client-side 30-minute timers are not authoritative cost control. Server quotas/concurrency/minute accounting are required by `AI-002`/`SEC-011`.
- Tests must mock external calls unless a credentialed manual test is explicitly authorized and documented.

## Quiz identity and uniqueness (updated 2026-11-13)

Implementation: `lessons/services/quiz.py`, `lessons/services/course_progress.py`, and the quiz views in `lessons/views.py`. Verification and deployment evidence: [learning fixes report](../OQYAI_BUGFIX_AND_PERFORMANCE_REPORT.md).

- Authenticated identity is `str(request.user.id)`; guest identity is an ensured Django session key.
- One `QuizAttempt` per `(user_id, lesson)` and one current `QuizAnswer` per `(attempt, question)` remain database constraints.
- Every run has an `attempt_token`, ordered `question_ids`, and a hash of normalized vocabulary pairs. Answer and restart POSTs require the token. A previous run/user/lesson token is rejected with HTTP 409.
- Quiz start, restart, and answer routes enforce the existing lesson-detail access policy, including its existing Russian student policy. Free lesson IDs and entitlement flags are unchanged.
- Current run state is never HTTP/service-worker cached. The worker only caches content-hashed public static assets and deletes old OqyAI page/API caches when it activates.

## Permanent completion and current run

- `QuizAttempt.is_passed` means the lesson has been passed at least once. Retakes and content changes never clear it.
- `completed` describes the current run. JSON `passed` means this run is complete; `lesson_completed` describes the permanent pass.
- `last_passed_score` and `last_passed_total` retain the latest successful result while practicing. This is not a complete attempt-history ledger.
- `POST /restart-quiz/<lesson_id>/` clears current answers/counters, rotates the token, and binds current vocabulary. It preserves permanent completion and previously unlocked lessons.
- Migration `0017_quiz_run_state` preserves existing aggregate pass flags/scores without inventing answers. Legacy totals remain unknown. Every existing run receives its own UUID.
- An aggregate-only historical pass retains its saved score on start. Complete valid answer evidence can repair inconsistent completion/pass flags on start. Partial or absent evidence cannot create a pass.

## Authoritative scoring and progression

- Score and mistakes come from stored distinct answers belonging to this run's lesson and question IDs.
- Duplicate submissions return saved state without incrementing counters. The browser advances from that authoritative state even after a lost response.
- A timeout records one incorrect answer with an empty selection. The existing five-second browser timer and three-mistake limit are retained; there is still no new server-enforced per-question deadline.
- Three distinct mistakes clear current answers/counters and rotate the run token. Permanent completion remains intact; a delayed old answer is rejected.
- Passing requires every current question answered and fewer than three mistakes. It can occur only once per lesson for progress counting; successful retakes update the saved result.
- Progress counts distinct permanent passes independently of payment eligibility. Session `passed_lessons` is an old unlock hint, never completion evidence.
- Kazakh level boundaries are IDs 1–50, 51–100, 101–150, 151–200, 201–250. Missing IDs do not shift later lessons into an earlier level. Russian IDs 251+ are separate; the existing catalog still presents only the five Kazakh levels.
- Next-lesson lookup stays within the current track. The final lesson can complete without a successor. Profile advancement is monotonic, using a conditional SQL update.

## Current vocabulary contract

- Each non-empty vocabulary line must contain an English term and translation separated by an en dash, em dash, or spaced hyphen. Duplicate pairs are collapsed; invalid/oversized entries and fewer than four pairs produce a controlled content error.
- Questions are selected by exact current vocabulary pairs and current lesson, not merely by the existence of stored question rows. Missing pairs are added under a lesson-row transaction lock.
- Old and duplicate question rows remain stored, preserving history; only one matching row per pair is served. No question row is deleted or edited during start.
- Correct answers and distinct distractors come from the selected lesson. A lesson with repeated translations can have fewer than four choices; placeholders and cross-lesson translations are not injected.
- Vocabulary changes reject stale answer POSTs. Opening the quiz binds the new vocabulary and resets only the current run, preserving prior completion.

## Mobile quiz presentation — 2026-11-15

The lesson quiz uses a native modal, full viewport on mobile with safe-area padding and a bounded desktop layout. The lesson remains scroll-locked until close; question choices scroll internally when long. Inline rules replace the confirmation popup. Existing question choices are rendered unchanged (including fewer than four choices for repeated translations).

The five-second browser timer arms after two animation frames once the modal and choices are rendered, and stops during requests/feedback. The fill follows the question deadline, with one-second steps under reduced motion. Returning to the tab reconciles elapsed time and submits an expired question once. The tab retains the deadline for the same attempt token and question across reloads. Page-history restoration reloads authoritative state. Close cancels timers and ignores late responses by epoch without undoing accepted server answers. Tokens, CSRF, exact-payload retry, server scoring, three-mistake reset, permanent completion, and next-lesson guards remain unchanged. No backend or schema changes. See [implementation checkpoint and verification](QUIZ_MOBILE_REDESIGN_PROGRESS.md).

### Answer feedback and lives (2026-11-19)

After validating and recording a submission, the server returns `correct_answer` for that question. A replay returns the same correction and the original `selected_answer`. The client uses these fields to color the choices for 500 ms on success and 1,250 ms on a mistake or timeout. Start and restart responses continue to provide unlabeled choices. Hearts reflect the server's mistake count. On the third mistake the server resets the run and also returns `finished_score` and `finished_count` for the result screen. The successor ID remains available in `next_lesson`; `can_continue` controls the next-lesson link using the lesson page's access policy. The single horizontal bar shows remaining time. The question counter shows the current position and total as text.

## Remaining limitations

- Start is still a GET that can initialize/synchronize state for compatibility.
- Curriculum metadata remains ID-based. Full versioned publishing and full attempt history are separate backlog work.
- Local MySQL 8.0.46 migration/rollback and five concurrent-write tests pass. The actual production schema/version/data volume still requires staging rehearsal; SQLite alone does not verify row locks.
- Browser networking, native Safari/WebView behavior, and production data require the checks listed in the report.

## Regression coverage

`lessons/test_quiz_integrity.py`, `lessons/test_learning_flow.py`, and `lessons/test_quiz_migration.py` cover idempotency, CSRF/access denial, last-lesson progress, legacy state, stale content, both tracks, distinct users, repeated retakes, lost-run tokens, malformed content, query budgets, and migration/rollback. `lessons/test_quiz_concurrency.py` exercises simultaneous starts, duplicate answers/final passes, and reset/restart races on real row-lock databases. `lessons/browser_checks.py` exercises browser behavior with synthetic data and mocked AI. `lessons/js_tests/service-worker.test.cjs` checks cache isolation.

Commands and current results are in [testing and quality](TESTING_AND_QUALITY.md).
