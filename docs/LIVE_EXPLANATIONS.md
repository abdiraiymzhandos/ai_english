# Lesson explanation generation, private review and student publication

Experimental and disabled by default. In Vocabulary, Content, Grammar and Dialogue, an active superuser can select **Live түсіндіру** for a fresh explanation or select **Салыстыру үшін сақталған мәтінді оқу** first to narrate the exact stored Realtime text. After a fresh Astra response, **Соңғы мәтінмен аудионы қайта жасау** narrates that exact Live script again, even if audio generation failed. Comparison and manual audio-only retry each use one Live session and zero text or Realtime requests. The original **Түсіндіру** continues to generate the learner-facing explanation. Each section pairs the selected script with one player. The turquoise Түсініктеме disclosure starts collapsed and controls only the text. English highlighting is applied to escaped text nodes. Superusers can switch saved recordings without generation. The database holds the student selection per lesson and section. Browser storage remembers only a superuser’s private preview. Live diagnostics are under Техникалық ақпарат.

## What students receive

A successful Realtime generation or validated Live generation publishes the text and recording together. Students who can open the lesson see its educational text and one player. Free lessons follow the same guest access rules as their lesson pages. Paid and progression-locked lessons apply the same `lesson_access_denial` check to audio GET, HEAD and range requests.

Migration `lessons.0022_explanation_publication` adds one publication row per participating lesson section. Existing Realtime records remain the default. Existing validated Live takes stay private until selected. The publication row pins an immutable Live UUID and its source text, or selects the current Realtime row. A per-request token prevents a superseded job from changing the student selection. Archiving a validated Live take preserves its UUID and protected playback. Migration also carries forward the tokens of pending jobs.

The superuser selector previews recordings privately. **Оқушыларға жариялау** publishes the selected validated take without a provider request. Unverified takes carry a warning and have no publication action. The separate **Техникалық ақпарат** disclosure and preview endpoints require an active superuser. Turning off `LIVE_EXPLANATIONS_ENABLED` disables Live generation and its admin controls. Already published audio continues to play without the flag, a worker, or an API key.

New Realtime MP3s go into `PRIVATE_EXPLANATION_ROOT` (default `private_explanations/` inside the Django checkout). Keep this directory outside all web-server static mappings, writable by Django and included in backups. Django checks the published version before serving the file. Legacy `/media/audio_lesson_…mp3` URLs retain their paths and use the same check **when routed through Django**. A hosting-level static mapping for `/media/` can bypass Django on those legacy files. Before rollout, route those URLs to Django and verify denial of an unpublished legacy MP3 directly on the host. Other uploaded media need their existing serving arrangements. No production mapping was changed here.

## Transport decision

The official model matrix explicitly marks `/v1/audio/speech` unsupported for GPT-Live-1.1. Its appearance in the endpoint list caused the apparent discrepancy. The Speech reference's MP3 output and 4,096-character input limit apply to its enumerated TTS models. No Speech request was made. [Model support matrix](https://developers.openai.com/api/docs/models/gpt-live-1.1.md) · [Speech reference](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create)

The server opens the primary Live WebSocket with its project bearer key and sends the model inside `session.start`. The schema lists both `cedar` and `marin`. The experiment defaults to `cedar` for comparison with the first-choice Realtime voice. A developer startup message requests the first speaking turn immediately, without a spoken cue. Each generation opens an independent session. Startup instructions and paced input can still yield silence. A user message contains the unmodified script. After checking the negotiated model, voice and PCM format, the worker sends 100 ms of mono, 24 kHz PCM16LE silence every 100 ms. It never captures a microphone. Client delegation with no tools and `store=false` avoids delegated model calls and stored Live recordings. [Primary WebSocket reference](https://developers.openai.com/api/reference/resources/live/primary-websocket.md) · [WebSocket guide](https://developers.openai.com/api/docs/guides/voice-websockets) · [Migration guide](https://developers.openai.com/api/docs/guides/live-migration)

Live has no end-of-narration event. Validation checks word order, transcript timing, voiced audio, final usage and graceful closure. The worker encodes received PCM and decodes the MP3 to verify playback even when transcript checks fail. Playable partial takes carry the warning **Аудио толық оқылмауы мүмкін. Тыңдап тексеріңіз.** The private player shows the script, received transcript, duration, model, voice and termination reason. Coverage is the percentage of source words matched in ordered blocks of normalized transcript words. Extra words can leave coverage at 100% and still trigger a warning. Only the Live session provides transcript evidence. Missing transcript yields 0% coverage. An activity detector measures mono PCM16LE in contiguous 20 ms windows across packet boundaries. Three consecutive windows with DC-adjusted RMS of at least 64 and peak deviation of at least 128 (16-bit units) establish sustained activity. The decoded MP3 must also pass this test. Missing audio, digital silence, below-floor noise, denied sessions and corrupt MP3s fail without replacing a recording. Sustained activity can establish audibility. Checking that the sound is the intended narration still requires the transcript or a listener. [Session lifecycle](https://developers.openai.com/api/docs/guides/live-conversations) · [Live prompting](https://developers.openai.com/api/docs/guides/live-prompting)

## Startup, retry and diagnostics

A fresh job uses the synchronous, non-streaming Astra Responses client. It requires a completed response and a script containing words. The worker stores the full script, SHA-256, counts, job ID, model and generation time before opening the Live socket. A response marked incomplete, including one containing a partial script, stops before Live. The previous retry source survives. Comparison snapshots Realtime text and leaves the Live retry source intact.

The first WebSocket command sends both the startup directions and complete script in `session.start`. The script is the one `input_text` part of a user message in `session.input`. Startup history supports up to 128 messages and a configurable rendered-token limit of 8,192 by default. Frontend instructions have a separate 16,384-token limit. OqyAI keeps its existing 6,000-character local script bound and sends accepted scripts intact. The worker verifies the model, voice and audio format in `session.started` before it starts the audio producer or startup timer. One consumer handles the output throughout the session. [Live primary WebSocket](https://developers.openai.com/api/reference/resources/live/primary-websocket)

After five seconds without sustained audio or a valid transcript word, the worker sends one session-wide `session.instructions.append` with a client event ID, `delegation_id: null` and a short plain-text direction to read the existing script. The append limit is 500 tokens. The documented `<say>` pattern embeds a short literal passage. Referencing the existing script keeps bilingual lessons intact and avoids repeating their first words. The worker records a correlated `session.instructions.appended` or error. Acceptance confirms receipt. The provider can still remain silent. At 25 seconds without meaningful audio the worker requests closure and allows up to 15 seconds for final usage. After speech starts, pauses use the existing 25-second inactivity allowance. [Session management](https://developers.openai.com/api/docs/guides/live-conversations) · [Live prompting](https://developers.openai.com/api/docs/guides/live-prompting)

In the worker console, filter `live_narration` by job UUID. Each event includes UTC time and elapsed monotonic seconds. Compare the source hash in `astra_completed`, `source_ready` and `session_start_sent`. The trace records the socket and acknowledgment, first input and output, first meaningful PCM, first transcript, any startup instruction and acknowledgment, completion and closure. The final summary includes signal classification, peak, RMS, non-silent duration, frames/chunks, coverage, application stop reason, provider close reason and available usage. The logs exclude lesson text, transcript content and credentials.

The retained 129.94-second cedar take contains 260 source and transcript words. Offline decoding measured peak 21,484 and RMS 1,822. Its first sustained activity under the current detector begins at 2.68 seconds and totals 87.22 seconds. The older 25.38-second review has 272 source words and zero transcript words, peak and RMS. Both scripts have normal punctuation and line breaks. The two later unsuccessful jobs reported 246–247 input frames, 253–254 output chunks, zero peak and zero transcript words. Their scripts were cleared by the old worker. Historical data cannot establish the model's internal reason for staying silent.

## Jobs, privacy and cost

- The CSRF-protected POST snapshots the shared educational prompt or exact stored text. The web request returns promptly. The existing worker claims one Live job at a time alongside notification and analytics polling. The browser polls the private status URL and can resume after reload. PythonAnywhere documents a five-minute web-worker timeout. [PythonAnywhere async work](https://help.pythonanywhere.com/pages/AsyncInWebApps/)
- One row per lesson/section holds the pending operation and last successful recording. Conditional updates bind a job to its UUID and deadline and coalesce simultaneous clicks and worker claims. An expired or interrupted job needs a new deliberate request. A failed regeneration can still display the last successful take.
- Migration `lessons.0019_live_explanation` adds one table, a unique constraint and a queue index. A single database update publishes the MP3 bytes, text, SHA-256, model, voice, source mode, publication time, final usage and elapsed time. Each validated take gets a new private URL. Replacing it archives the old validated bytes in the same transaction and keeps the old protected URL playable. Source reads on lessons and polls exclude the audio column. The MP3 filename is `live-<section>-<revision>.mp3` under the authorized lesson endpoint. Django serves byte ranges for mobile players. Each playback request reads the bounded MP3 from the database before slicing the requested range. Public media, static mappings and the legacy Realtime deletion glob cannot reach the recording. DB backups now contain private experimental recordings and should retain their existing restricted access.
- Migration `lessons.0020_live_explanation_review` adds a separate private recording per unverified job. A review take is available in the recording selector and requires explicit selection. Opening Live баптаулары also loads older review choices. Each diagnostic MP3 keeps its job-specific protected URL after later attempts. Older validated rows can lack a stored transcript and coverage. Interrupted sessions may lack final usage. A review is a terminal result and incurs no automatic retry.
- Migration `lessons.0021_live_retry_source` adds private retry text and metadata, seeds them from the most recent retained fresh recording per section, and distinguishes archived validated takes from unverified reviews. A previous failure can only be backfilled if its script survived.
- Active superusers can generate, read status or stream MP3s while the flag is on. Pages, status and audio use private/no-store caching. Disabling the flag also prevents the worker from claiming a job. The standalone smoke command has its own explicit paid opt-in.
- Local bounds are 24,000 characters for an interpolated fresh prompt, 6,000 for spoken text, six minutes for a Live session and its audio (about 2.9 MB at 64 kbit/s), ten seconds to connect, twelve for startup, 25 for inactivity, fifteen for finalization, and twenty per FFmpeg pass. Queued work expires after ten minutes and running claims after twelve. Fresh Astra requests use a 45-second SDK timeout and zero SDK retries. Fresh Live jobs make one Astra Responses request. Empty text ends the job before speech synthesis. The original Realtime button retains its empty-output fallback. Comparison mode reads the exact stored explanation without a text request. All three Live modes use one Live session for a valid script and never call Realtime TTS. There is no automatic provider or voice fallback.
- Estimate the Live portion in USD as `usage_seconds / 60 × 0.05` at the reviewed active rate. Six minutes is approximately $0.30 before text charges. WebSocket silence consumes active session time. The $0.02/min standby rate applies to paused WebRTC inference. Final usage is available on success, interrupted attempts can still incur cost, and the provider invoice is authoritative. [OpenAI pricing](https://developers.openai.com/api/docs/pricing)

## Configuration and local checks

| Setting | Default | Purpose |
|---|---|---|
| `LIVE_EXPLANATIONS_ENABLED` | `false` | Set `true` or `1` in both web and worker environments |
| `LIVE_EXPLANATION_MODEL` | `gpt-live-1.1` | This experiment verifies this model at startup |
| `LIVE_EXPLANATION_VOICE` | `cedar` | Independently selectable supported Live built-in voice |
| `LIVE_STARTUP_NUDGE_SECONDS` | `5` | Seconds after acknowledgment before the one-time instruction |
| `LIVE_STARTUP_DEADLINE_SECONDS` | `25` | Request close after this many seconds without sustained audio |
| `LIVE_EXPLANATION_INSTRUCTIONS` | Bilingual narration directions in `live_defaults.py` | Optional voice-direction override |

For local SQLite, stop the running server and worker with Ctrl+C. Run the following in the server terminal.

```bash
cd ~/english_platform/english_course
export USE_MYSQL=0 LIVE_EXPLANATIONS_ENABLED=true
../venv/bin/python manage.py migrate lessons 0022
../venv/bin/python manage.py runserver
```

Start the worker in its own terminal.

```bash
cd ~/english_platform/english_course
export USE_MYSQL=0 LIVE_EXPLANATIONS_ENABLED=true
../venv/bin/python manage.py run_background_worker --allow-sqlite
```

Uses the existing `OPENAI_API_KEY`, Python 3.10, Django 5.1.6, websockets and FFmpeg with libmp3lame. The first new Realtime generation creates its private storage directory. Live MP3s stay in the database. Run from the local Django checkout using the project interpreter. Automated tests use synthetic audio and mocked providers, including a local loopback WebSocket.

```bash
cd ~/english_platform/english_course
export USE_MYSQL=0 OPENAI_API_KEY=test-placeholder
../venv/bin/python manage.py check
../venv/bin/python manage.py makemigrations --check --dry-run
../venv/bin/python manage.py test --noinput
node --check static/js/live-explanation.js
node --test lessons/js_tests/*.cjs
git diff --check
```

With Selenium and a matching Chromium/ChromeDriver available, run the normal browser suite. These paths select the installed local pair. Use a file-backed SQLite test database for independent concurrent writers or run the concurrency tests on disposable MySQL.

```bash
export PYTHONPATH="$HOME/.local/lib/python3.10/site-packages${PYTHONPATH:+:$PYTHONPATH}"
export OQYAI_CHROMIUM="$HOME/.cache/selenium/chrome/linux64/157.0.8103.78/chrome"
export OQYAI_CHROMEDRIVER="$HOME/.cache/selenium/chromedriver/linux64/157.0.8103.78/chromedriver"
../venv/bin/python manage.py test lessons.browser_checks --noinput
```

## Reproduce the publication checks locally

Run these in a separate test terminal. The settings file places SQLite in a new temporary directory for independent worker connections. The provider calls in these tests are mocked.

```bash
cd ~/english_platform/english_course
publication_tests=$(mktemp -d)
cat > "$publication_tests/publication_test_settings.py" <<'PYSETTINGS'
from english_course.settings import *
from pathlib import Path
test_directory = Path(__file__).resolve().parent
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                        "NAME": test_directory / "empty.sqlite3",
                        "TEST": {"NAME": test_directory / "tests.sqlite3"}}}
PYSETTINGS
export USE_MYSQL=0 OPENAI_API_KEY=test-placeholder DJANGO_SETTINGS_MODULE=publication_test_settings
export PYTHONPATH="$publication_tests:$HOME/.local/lib/python3.10/site-packages"
export OQYAI_CHROMIUM="$HOME/.cache/selenium/chrome/linux64/157.0.8103.78/chrome"
export OQYAI_CHROMEDRIVER="$HOME/.cache/selenium/chromedriver/linux64/157.0.8103.78/chromedriver"
../venv/bin/python manage.py test lessons.test_explanation_publication lessons.test_live_explanations lessons.test_learning_flow --noinput
../venv/bin/python manage.py test lessons.browser_checks.LearningBrowserChecks.test_shared_explanation_player_in_all_sections lessons.browser_checks.LearningBrowserChecks.test_observable_audio_failures --noinput
```

## Opt-in listening test

Use a separate local shell with the authorized project key and a private directory outside the checkout. The following command incurs **one paid Live session**. It accepts UTF-8, publishes a playback-checked MP3 and reports its transcript validation status, refuses an existing output file, and prints final seconds, duration and latency. It does not read or write lesson rows.

```bash
cd ~/english_platform/english_course
umask 077
trial=$(mktemp -d)
printf '%s' 'Бірінші сабақта біз ағылшын тілін үйренеміз.' > "$trial/script.txt"
../venv/bin/python manage.py smoke_live_narration --authorize-paid-call \
  --input "$trial/script.txt" --output "$trial/live.mp3"
```

For a controlled local A/B, use a separate explicit paid Realtime request with the same UTF-8 file, existing lesson narration directions and first-choice voice. The command uses an exclusive output file. For an existing lesson that already has a recording, using the UI comparison checkbox saves the cost of generating another reference. Historical recordings do not record whether the legacy fallback voice was used.

```bash
export OQYAI_TRIAL_DIR="$trial"
../venv/bin/python manage.py shell <<'PY'
import asyncio, os, time
from pathlib import Path
from django.conf import settings
from english_course.realtime_config import REALTIME_MODEL
from english_course.utils.realtime_tts import LESSON_NARRATION_INSTRUCTIONS, synthesize_audio_realtime_mp3
trial = Path(os.environ["OQYAI_TRIAL_DIR"])
text = (trial / "script.txt").read_text(encoding="utf-8")
start = time.monotonic()
with (trial / "reference.mp3").open("xb") as output:
    audio = asyncio.run(asyncio.wait_for(synthesize_audio_realtime_mp3(
        f"<<READ_START>>\n{text}\n<<READ_END>>", api_key=settings.OPENAI_API_KEY,
        model=REALTIME_MODEL, voice="cedar", system_instructions=LESSON_NARRATION_INSTRUCTIONS), 360))
    output.write(audio)
print("reference_latency_seconds", round(time.monotonic() - start, 2))
PY
sha256sum "$trial/script.txt"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$trial/reference.mp3"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$trial/live.mp3"
```

Use each line below as its own script in a fresh trial directory. This exercises the first spoken word for each sample. The last example starts with the letter itself.

1. Бірінші сабақта біз ағылшын тілін үйренеміз.
2. Білім алу өте маңызды.
3. Бүгін біз бірге жаңа сөздерді үйренеміз.
4. Тіл үйрену үшін күн сайын жаттығу керек.
5. Beautiful. Бұл әдемі дегенді білдіреді. She is beautiful. Ол әдемі.
6. Інім бүгін ағылшын тілін үйреніп жүр.

For the **full-length trial**, copy the supplied bilingual grammar explanation with `cp docs/live-narration-trial.txt "$trial/script.txt"` before generating either take, or select a complete stored vocabulary or grammar explanation with repeated transitions and a known final sentence. Run the comparison checkbox or copy its exact text to the trial file. Record the source hash and both voice IDs when available. Randomize playback order and have a fluent Kazakh/US-English listener score first word, і versus и, Kazakh vowels and accent, US stress, switching and pauses. Record added/missing words and the final audible sentence verbatim. Record both durations, latency, Live usage seconds, estimated Live cost and available provider billing for the reference. Label missing usage as unknown. No real narration or pronunciation assessment was performed during implementation.

## PythonAnywhere rollout and rollback

After owner review and publication of the code, leave the flag off for the first rollout. Verify the production backup, free DB storage, outbound WebSocket connectivity and FFmpeg availability. Allow headroom for a roughly 3 MB binary DB update and the SQL driver's representation (`max_allowed_packet` of 8 MiB or more gives margin). Use the current production virtual environment. Inspect the migration plan before applying it.

```bash
cd /home/abdiraiymzhandos/ai_english
git status --short --branch
git pull --ff-only origin main
venv/bin/python manage.py check
venv/bin/python manage.py makemigrations --check --dry-run
venv/bin/python manage.py migrate lessons 0022 --plan
venv/bin/python manage.py migrate lessons 0022 --noinput
venv/bin/python manage.py collectstatic --noinput
ffmpeg -version
ffmpeg -hide_banner -encoders | grep libmp3lame
venv/bin/python manage.py showmigrations lessons
```

Select **Web → Reload**. After an authorized local smoke and listening review, set `LIVE_EXPLANATIONS_ENABLED=true` in the environment loaded by both processes. Reload the web app and restart the **existing** `run_background_worker` Always-on Task once. Its command stays the same. Check an authorized lesson plus a learner session. Verify that a submitted job reaches ready, its range request succeeds, and the two recordings survive reload. Successful validated generation automatically publishes to authorized learners.

To disable, set the flag to `false`, reload Web and restart that same task. An already-running paid request can finish during shutdown. Expired jobs require deliberate resubmission. Existing private rows can stay in place. For permanent removal, first export any private previews the owner wants to retain and stop the Live poller. On this release, inspect `venv/bin/python manage.py migrate lessons 0018 --plan`. Only with owner approval and a plan removing solely the four explanation migrations (0022 through 0019), run `venv/bin/python manage.py migrate lessons 0018 --noinput`. Reversing 0022 removes global selections and restores Realtime defaults. Reversing 0020 and 0019 deletes the experimental recordings. If later migrations depend on 0019, create a forward removal migration instead. Remove the Live routes, worker registration, provider, UI and table model in the reviewed code release. The shared prompt service and original Realtime system can remain in use.

## Unified interface and publication files

| Area | Files |
|---|---|
| Storage and selection | `lessons/models.py`, `lessons/services/live_explanations.py`, new `lessons/services/explanation_publication.py`, new `lessons/migrations/0022_explanation_publication.py` |
| Access and application settings | `lessons/views.py`, `lessons/views_live.py`, `lessons/urls.py`, `english_course/urls.py`, `english_course/settings.py`, `.gitignore` |
| Shared lesson interface | `lessons/templates/lessons/lesson_detail.html`, new `lessons/templates/lessons/includes/explanation.html`, `lessons/templates/lessons/includes/live_explanation.html`, `lessons/templates/lessons/includes/live_recording.html`, `static/js/live-explanation.js`, `static/css/live-explanation.css` |
| Tests and documentation | new `lessons/test_explanation_publication.py`, `lessons/test_live_explanations.py`, `lessons/browser_checks.py`, `docs/AI_INTEGRATIONS.md`, `docs/LIVE_EXPLANATIONS.md` |

## Change inventory

| Area | Modified | Added |
|---|---|---|
| Configuration and speech | `english_course/settings.py`, `english_course/utils/realtime_tts.py` | `english_course/utils/live_defaults.py`, `english_course/utils/live_tts.py` |
| Generation and storage | `lessons/models.py`, `insights/management/commands/run_background_worker.py` | `lessons/services/explanation_text.py`, `lessons/services/live_explanations.py`, `lessons/migrations/0019_live_explanation.py`, `lessons/migrations/0020_live_explanation_review.py`, `lessons/migrations/0021_live_retry_source.py`, `lessons/management/commands/process_live_explanations.py`, `lessons/management/commands/smoke_live_narration.py` |
| HTTP and UI | `lessons/views.py`, `lessons/urls.py`, `lessons/templates/lessons/lesson_detail.html` | `lessons/views_live.py`, `lessons/templates/lessons/includes/live_explanation.html`, `lessons/templates/lessons/includes/live_recording.html`, `static/js/live-explanation.js`, `static/css/live-explanation.css` |
| Tests and operator materials | `lessons/browser_checks.py`, `docs/AI_INTEGRATIONS.md` | `lessons/test_live_explanations.py`, `docs/LIVE_EXPLANATIONS.md`, `docs/live-narration-trial.txt` |

## Startup regression verification on 25 November 2026

The file-backed SQLite run discovered 174 tests, with 166 passing and eight skipped. The 32 focused Live tests passed, including the concurrent job claim. The Chromium Live browser journey passed with a manual retry and comparison across the four sections. A disposable migration rehearsal checked retry-source selection and preserved six existing synthetic recordings. Provider traffic in the Live tests used mocks, synthetic PCM and a loopback WebSocket. Real-provider startup reliability with the additional instruction still requires a manual trial.

### Files changed for the startup fix

| Area | Files |
|---|---|
| Transport and timing | `english_course/utils/live_tts.py`, `english_course/utils/live_defaults.py`, `english_course/settings.py`, `lessons/management/commands/smoke_live_narration.py` |
| Source persistence and playback | `lessons/services/explanation_text.py`, `lessons/services/live_explanations.py`, `lessons/models.py`, `lessons/views_live.py` |
| New migration | `lessons/migrations/0021_live_retry_source.py` |
| Superuser controls | `lessons/templates/lessons/includes/live_explanation.html`, `lessons/templates/lessons/includes/live_recording.html`, `static/js/live-explanation.js` |
| Verification and operations | `lessons/test_live_explanations.py`, `lessons/browser_checks.py`, `docs/LIVE_EXPLANATIONS.md` |

## Earlier feature verification

| Final run | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Full Django suite, disposable MySQL | 159 | 0 | 0 |
| Full Django suite, file-backed SQLite | 151 | 0 | 8 |
| Full Django suite, in-memory SQLite | 147 | 0 | 12 |
| Live tests with OpenAI SDK 1.109.1 and websockets 12, file-backed SQLite | 17 | 0 | 0 |
| Chromium 157 browser suite, disposable MySQL | 29 | 0 | 0 |
| Node regression suite | 7 | 0 | 0 |

The four additional in-memory skips require independent database writers. Chromium loaded both MP3 players in each section, exercised the comparison control and keyboard activation, and restored all four private previews after reload. Earlier combined browser runs exposed shared-tab input state and SQLite teardown contention. The final browser run isolated each journey in a fresh tab. A synthetic ultrasonic input in an early full-length test was suppressed by MP3 encoding; the final fixture uses an audible 400 Hz signal. No real narration was used to measure pronunciation.

Django checks, migration drift, JavaScript syntax, Python compilation and Git whitespace checks passed. A disposable SQLite rehearsal applied 0019, reversed it, checked the retained legacy explanation, and reapplied it. The existing local environment still fails `pip check` because httpcore 1.0.7 requires h11 below 0.15 and has 0.16.0 installed. Project dependencies were unchanged.
