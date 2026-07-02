# AI Voice Lesson Feature

For current Realtime contracts, read `docs/REALTIME_AND_QUIZ_CONTRACTS.md` first.

## Current Architecture
The active voice lesson is WebRTC-only:

1. `lessons.views.mint_realtime_token` validates the user has active voice access.
2. Django posts to `POST /v1/realtime/client_secrets` with the GA Realtime session shape and model `gpt-realtime-2`.
3. Django sends `OpenAI-Safety-Identifier` as a SHA-256 hash of the internal user ID.
4. Browser receives only the ephemeral client secret.
5. `static/js/voice-lesson.js` creates one data channel named `oai-events`.
6. Browser posts SDP to `POST /v1/realtime/calls` with `Content-Type: application/sdp`.
7. Remote audio plays through WebRTC.

There is no active Django websocket bridge for the voice lesson.

## Key Files
- `english_course/realtime_config.py`: shared `REALTIME_MODEL`.
- `english_course/realtime.py`: client-secret minting and safety identifier helper.
- `lessons/views.py`: voice token endpoint and teacher instructions.
- `static/js/voice-lesson.js`: browser WebRTC client.
- `static/css/voice-lesson.css`: voice UI styling.
- `lessons/templates/lessons/lesson_detail.html`: voice UI mount.

## Access
Voice lesson access requires:
- authenticated user;
- `UserProfile.has_active_voice_access()`.

Admin can grant/revoke voice access through Django admin actions or the management commands in `lessons/management/commands/`.

## Browser Behavior
- Requests microphone permission before connecting.
- Uses echo cancellation, noise suppression, and auto gain control where the browser supports them.
- Maintains remote audio playback through an invisible `<audio>` element.
- Auto-stops long sessions after the configured max duration.
- Shows browser-safe errors when token or SDP setup fails.

## Troubleshooting
| Symptom | Check |
| --- | --- |
| Access denied | `UserProfile.has_voice_access` and `voice_access_until` |
| Token error | Django logs for `/v1/realtime/client_secrets` request |
| SDP error | Browser console and `/v1/realtime/calls` response |
| No microphone | Browser permissions and HTTPS/localhost rules |
| No audio playback | Browser autoplay policy and remote track events |

## Manual Test
1. Log in as a user with active voice access.
2. Open a lesson detail page.
3. Click the voice lesson start button.
4. Grant microphone permission.
5. Confirm connection status changes to connected.
6. Confirm remote audio plays and transcript/text deltas appear when available.
7. Stop the session and confirm microphone tracks are released.
