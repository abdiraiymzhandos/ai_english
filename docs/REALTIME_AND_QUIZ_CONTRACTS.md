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

## Quiz identity and uniqueness

- Authenticated identity: `str(request.user.id)`.
- Guest identity: an ensured Django session key.
- Database: one `QuizAttempt` per `(user_id, lesson)`.
- Database: one `QuizAnswer` per `(attempt, question)`.
- The submit view must load the question through both ID and current lesson.
- The database cannot itself enforce question lesson equals attempt lesson; preserve application validation and tests.

## Authoritative quiz state

- Score = count of stored correct answers.
- Mistakes = count of stored incorrect answers.
- Completion depends on distinct stored answers, not browser counters or arithmetic on legacy fields.
- A duplicate submission returns existing state and must not change score, mistakes, progress, or unlocks.
- A timeout stores at most one incorrect answer with an empty selection.
- Three distinct mistakes reset current answer rows and attempt counters; no lesson unlock.
- Passing requires all current lesson questions answered and fewer than three mistakes.
- The next existing numeric lesson is added once to session unlock state; authenticated `current_lesson` advances only upward.

## Known contract limitations

- Quiz start is a GET that can write questions/attempt state.
- Quiz routes do not consistently enforce course entitlement.
- Question generation is exact-delimiter, exists-then-create, non-versioned, and race-prone.
- Historical pass records can lack `QuizAnswer` evidence.
- Lesson IDs encode curriculum order/track/access.
- Frontend does not use returned `next_lesson` for a continuation CTA and retake is broken after pass.

These are backlog issues, not invariants to preserve.

## Required regression matrix

| Case | Expected result |
| --- | --- |
| Same correct answer repeated | One answer, score one, no duplicate progress |
| All unique correct answers | Pass once, unlock next once |
| Cross-lesson question | Reject; attempt unchanged |
| Third unique mistake | Reset answers/state; no unlock |
| Duplicate timeout | One incorrect answer |
| Concurrent attempt create | One attempt |
| Unauthorized/locked lesson quiz | Deny after access-policy task |
| Realtime token | Shared model, ephemeral secret, safety hash, no standard key |
| Realtime error | Generic client response; redacted server detail |
| TTS provider error/empty audio | Controlled exception; existing media preserved after future lifecycle fix |

Run the actual test command defined in [TESTING_AND_QUALITY.md](TESTING_AND_QUALITY.md).
