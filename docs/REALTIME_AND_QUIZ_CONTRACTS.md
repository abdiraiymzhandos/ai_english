# Realtime And Quiz Contracts

## Realtime Model Rule
All active Realtime features use the shared model in `english_course/realtime_config.py`:

```python
REALTIME_MODEL = "gpt-realtime-2"
```

Do not hard-code another active Realtime model in views, browser clients, diagnostics, or utilities.

## Active Realtime Entry Points
| Feature | Server Entry Point | Browser/Utility |
| --- | --- | --- |
| Voice Lesson | `lessons.views.mint_realtime_token` at `/api/realtime/token/<lesson_id>/` | `static/js/voice-lesson.js` |
| Translator | `lessons.views.mint_translator_token` at `/api/translator/token/` | `static/js/translator-assistant.js` |
| Classroom | `lessons.views_classroom.mint_realtime_classroom_token` at `/api/realtime/classroom/<lesson_id>/<group_id>/` | `static/js/classroom-lesson.js` |
| Explanation Audio | `english_course.utils.realtime_tts.synthesize_audio_realtime_mp3` | backend WebSocket only |

Historical Django websocket consumers are not active product runtime.

## Browser WebRTC Contract
Server-side token creation:
- Django validates auth/access.
- Django posts to `https://api.openai.com/v1/realtime/client_secrets`.
- Request JSON uses GA nested session shape:

```json
{
  "session": {
    "type": "realtime",
    "model": "gpt-realtime-2",
    "instructions": "feature-specific instructions",
    "audio": {
      "input": {
        "turn_detection": {
          "type": "server_vad"
        }
      },
      "output": {
        "voice": "cedar"
      }
    }
  }
}
```

Browser connection:
- Browser receives only an ephemeral client secret response, not the standard OpenAI API key.
- Browser creates exactly one data channel:

```javascript
pc.createDataChannel("oai-events")
```

- Browser posts SDP to:

```text
POST https://api.openai.com/v1/realtime/calls
Content-Type: application/sdp
Authorization: Bearer <ephemeral client secret>
```

- The model must not be sent in a WebRTC URL query string.
- The browser should not send old beta `session.update` payloads with top-level `modalities`.

## Server WebSocket Contract For Explanation Audio
The backend connects to:

```text
wss://api.openai.com/v1/realtime?model=gpt-realtime-2
```

Required headers:
- `Authorization: Bearer <server API key>`
- `OpenAI-Safety-Identifier: <sha256 hash>`

Event sequence:
1. `session.update` with GA `session.type`, `instructions`, `output_modalities`, and `audio.output.voice`; the model is selected only in the WebSocket URL.
2. `conversation.item.create` containing the explanation text as `input_text`.
3. `response.create` requesting audio output.
4. Collect only `response.output_audio.delta`.
5. Stop on `response.done`.
6. Raise controlled errors on `error`, `response.failed`, incomplete responses, or empty audio.
7. Return MP3 bytes to the caller. The utility never writes files.

## Expected Realtime Events
Browser clients must handle at minimum:
- `response.output_text.delta`
- `response.output_audio.delta`
- `response.output_audio_transcript.delta`
- `response.output_audio_transcript.done`
- `response.done`
- `error`

Current browser clients use remote WebRTC audio for playback and transcript/text deltas for UI text.

## Security Requirements
- Never expose the standard OpenAI API key to the browser.
- Never expose raw Django user IDs in OpenAI safety identifiers or browser JSON.
- `OpenAI-Safety-Identifier` is SHA-256 of:
  - authenticated user: internal user ID string;
  - anonymous user: Django session key.
- Token endpoints require current access checks.
- Token creation failures are logged server-side with details and returned to browsers as safe generic errors.
- Quiz answer POSTs require CSRF.

## Feature-Specific Prompt Preservation
- Voice Lesson uses `_teacher_instructions(lesson)` in `lessons/views.py`.
- Translator uses `translator_instructions` in `lessons/views.py`.
- Classroom uses `_classroom_instructions(lesson, group)` in `lessons/views_classroom.py`.
- Explanation audio uses the existing narration instructions in `explain_section()`.

## Quiz Idempotency Rules
- `QuizAttempt` unique constraint: one attempt per `user_id + lesson`.
- `QuizAnswer` unique constraint: one answer per `attempt + question`.
- Duplicate POST for the same question returns `already_answered: true`.
- Duplicate POST never increments score.
- Duplicate POST never increments mistakes.
- Duplicate POST never unlocks the next lesson.
- Timeout posts use `timed_out=true` and store one incorrect answer with an empty selected answer.
- Cross-lesson question IDs are rejected by querying `QuizQuestion(id=question_id, lesson=lesson)`.

## Quiz Progression Rules
- Score is the count of distinct correct `QuizAnswer` rows.
- Mistakes are the count of distinct incorrect `QuizAnswer` rows.
- Completion is based on `attempt.answers.count()`, never `score + attempts`.
- Three distinct wrong answers:
  - return `restart_required: true`;
  - reset score, mistakes, completed, and pass state;
  - delete answer rows for the attempt;
  - do not unlock any lesson.
- Passing:
  - requires every distinct lesson question to be answered;
  - requires fewer than three mistakes;
  - persists pass state once;
  - unlocks the next existing lesson once;
  - updates authenticated profile progress only when the next lesson is higher.

## Test Matrix
| Area | Required Test |
| --- | --- |
| Repeated correct click | Same correct answer submitted 10 times creates one `QuizAnswer`, score 1, not passed |
| Normal pass | All unique correct answers pass and unlock next lesson once |
| Cross-lesson question | Wrong lesson question rejected and attempt unchanged |
| Three mistakes | Third unique wrong answer resets state and clears answers |
| Timeout | Timeout creates one wrong answer; duplicate timeout does not add another mistake |
| Attempt uniqueness | DB prevents duplicate `QuizAttempt(user_id, lesson)` |
| Browser token | Uses `/v1/realtime/client_secrets`, `gpt-realtime-2`, safety header, no beta header |
| Server TTS | Uses GA WebSocket endpoint, decodes `response.output_audio.delta`, returns MP3, controlled error on `error` |

Run:

```bash
./venv/bin/python manage.py test lessons
```
