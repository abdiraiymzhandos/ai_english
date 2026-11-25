import asyncio
import base64
import hashlib
import json
import math
from array import array
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from english_course.utils import live_tts as tts
from .models import Explanation, LiveExplanation
from .services.explanation_text import build_explanation_prompt, generate_explanation_text
from .services.live_explanations import execute_next
from .test_learning_flow import make_lesson


class PromptTests(SimpleTestCase):
    def test_original_prompt_bytes_for_all_four_interpolations(self):
        # Frozen hashes evaluated from the original view before extraction. Includes whitespace.
        hashes = {
            "content": "cd4ccb5fdbedb62767ef7da75ffad9210ca9aea6c192f4645b376c6b8312a3e8",
            "vocabulary": "3e9ec2243fed2d011193a561836903439b1432b9eaa8b93a1ca66563c5879875",
            "grammar": "c74618d9964cbfd58c0492cd62d77a9cefc4d1cc8723f2df09388b8dc46c5e1f",
            "dialogue": "71ade6bcb43fa666abff4506c5593aec1aeebc0d409cf9d55b4784f961080a36",
        }
        lesson = SimpleNamespace(**{key: key + " / мәтін\nline 2" for key in hashes})
        for key, digest in hashes.items():
            self.assertEqual(hashlib.sha256(build_explanation_prompt(lesson, key).encode()).hexdigest(), digest)

    def test_astra_and_empty_output_fallback(self):
        client = MagicMock()
        client.responses.create.return_value.output_text = " "
        client.chat.completions.create.return_value.choices[0].message.content = "  fallback  "
        self.assertEqual(generate_explanation_text("p", client), "fallback")
        client.responses.create.assert_called_once_with(model="gpt-6-astra", input="p", reasoning={"effort": "low"},
                                                       text={"verbosity": "low"})
        client.chat.completions.create.assert_called_once_with(model="gpt-6-astra", messages=[{"role":"user","content":"p"}])

    def test_smoke_requires_explicit_paid_opt_in(self):
        with patch("lessons.management.commands.smoke_live_narration.synthesize_audio_live_mp3") as paid:
            with self.assertRaises(CommandError):
                call_command("smoke_live_narration", input="dummy", output="unused.mp3")
            paid.assert_not_called()


def sample_pcm():
    cycle = [round(1500 * math.sin(2 * math.pi * sample / 60)) for sample in range(60)]
    return array("h", cycle * (tts.RATE // 60)).tobytes()


class Socket:
    def __init__(self, events, final=None):
        self.events = list(events)
        self.sent = []
        self.released = False
        self.final = final or {"type": "session.closed", "reason": "close_requested", "usage": {"seconds": 2}}

    async def send(self, raw):
        event = json.loads(raw)
        self.sent.append(event)
        if event["type"] == "session.close":
            self.events.append(self.final)

    async def recv(self):
        if self.events:
            event = self.events.pop(0)
            if isinstance(event, Exception):
                raise event
            return json.dumps(event)
        await asyncio.sleep(10)

    @asynccontextmanager
    async def connect(self, *args, **kwargs):
        try:
            yield self
        finally:
            self.released = True


def session_events():
    return [
        {"type": "session.started", "session": {"model": tts.LIVE_MODEL, "audio": {
            "format": tts.FORMAT, "output": {"voice": "cedar"}}}},
        {"type": "session.output_audio.delta", "delta": base64.b64encode(sample_pcm()).decode()},
        {"type": "session.output_transcript.delta", "start_ms": 0, "end_ms": 100, "delta": "Білім алу."},
    ]


class ProviderTests(SimpleTestCase):
    async def generate(self, sock, **options):
        with patch.object(tts, "connect", side_effect=sock.connect) as connect, patch.object(tts, "DRAIN_SECONDS", .01):
            try:
                return await tts.synthesize_audio_live_mp3("Білім алу.", api_key="dummy", model=tts.LIVE_MODEL, voice="cedar", **options)
            finally:
                connect.assert_called_once()
                self.assertEqual(connect.call_args.args, ("wss://api.openai.com/v1/live/sessions",))
                self.assertTrue(sock.released)

    async def test_model_handshake_paced_silence_transcript_order_final_usage_and_real_mp3(self):
        sock = Socket(session_events())
        audio = await self.generate(sock)
        self.assertTrue(audio.validated)
        self.assertEqual(audio.metadata["coverage_percent"], 100)
        self.assertGreater(len(audio.mp3), 6000)
        self.assertEqual(audio.metadata["usage_seconds"], 2)
        config = sock.sent[0]["session"]
        self.assertEqual(config["model"], "gpt-live-1.1")
        self.assertEqual(config["input"][-1]["content"][0]["text"], "Білім алу.")
        frames = [e for e in sock.sent if e["type"] == "session.input_audio.append"]
        self.assertTrue(frames)
        self.assertEqual(base64.b64decode(frames[0]["audio"]), bytes(4800))
        self.assertEqual(sock.sent[-1]["type"], "session.close")
        self.assertEqual(audio.metadata["input_frames"], len(frames))
        self.assertEqual(audio.metadata["output_chunks"], 1)
        self.assertGreater(audio.metadata["pcm_peak"], 0)
        self.assertIsNotNone(audio.metadata["first_signal_seconds"])

    async def test_bad_format_empty_disconnect_provider_error_and_invalid_pcm_rejected(self):
        started, chunk, transcript = session_events()
        cases = [[{"type":"error"}], [dict(started, session={})], [started, OSError()],
                 [started, dict(chunk, delta="!!")], [started, dict(chunk, delta="AA==")],
                 [started, {"type":"session.closed"}], [started, chunk, {"type":"error", "error":{"code":"invalid_api_key"}}]]
        for events in cases:
            with self.subTest(events=len(events)), self.assertRaises(tts.LiveError):
                await self.generate(Socket(events))

    async def test_timeout_and_unconfirmed_or_extra_final_transcript(self):
        with patch.object(tts, "MAX_SECONDS", .05), self.assertRaises(tts.LiveError):
            await self.generate(Socket([]))
        for final in ({"type":"session.closed", "reason":"expired"}, {"type":"session.closed","reason":"close_requested"},
                      session_events()[1]):
            with patch.object(tts, "FINALIZE_SECONDS", .05):
                result = await self.generate(Socket(session_events(), final))
            self.assertFalse(result.validated)
            self.assertTrue(result.mp3)
        events = session_events()
        events.append(dict(events[-1], delta=" артық"))
        sock = Socket(events + [OSError()])
        result = await self.generate(sock)
        self.assertFalse(result.validated)
        self.assertEqual(result.metadata["transcript"], "Білім алу. артық")
        self.assertTrue(sock.released)

    async def test_real_loopback_wire_exchange_and_finalization_timeout(self):
        from websockets.legacy.server import serve
        received = []
        async def server(ws):
            received.append(ws.request_headers["Authorization"])
            received.append(json.loads(await ws.recv()))
            started, chunk, transcript = session_events()
            await ws.send(json.dumps(started))
            for _ in range(2):
                received.append(json.loads(await ws.recv()))
            for event in [chunk, transcript]:
                await ws.send(json.dumps(event))
            async for raw in ws:
                if json.loads(raw)["type"] == "session.close":
                    await ws.send(json.dumps({"type":"session.closed","reason":"close_requested","usage":{"seconds":2}}))
                    break

        async with serve(server, "127.0.0.1", 0) as listener:
            port = listener.sockets[0].getsockname()[1]
            with patch.object(tts, "URL", f"ws://127.0.0.1:{port}"), patch.object(tts,"DRAIN_SECONDS",0.01):
                result = await tts.synthesize_audio_live_mp3("Білім алу.", api_key="dummy",
                                                            model=tts.LIVE_MODEL, voice="cedar")
        self.assertEqual(received[0], "Bearer dummy")
        self.assertEqual(received[1]["session"]["model"],tts.LIVE_MODEL)
        self.assertEqual(received[2]["type"], "session.input_audio.append")
        self.assertGreater(len(result.mp3), 6000)
        with patch.object(tts, "FINALIZE_SECONDS", 0.01):
            result = await self.generate(Socket(session_events(), {"type":"session.usage.updated"}))
        self.assertFalse(result.validated)
        self.assertEqual(result.metadata["termination_reason"], "finalization_timeout")

    async def test_full_bilingual_trial_and_missing_final_sentence(self):
        from django.conf import settings
        script = (settings.BASE_DIR / "docs/live-narration-trial.txt").read_text(encoding="utf-8")
        paragraphs = script.strip().split("\n\n")
        pulse = session_events()[1]
        quiet = {"type":"session.output_audio.delta", "delta":base64.b64encode(bytes(2*tts.RATE)).decode()}
        events = [session_events()[0]]
        seconds = 0
        for paragraph in paragraphs:
            duration = max(1, len(tts.words(paragraph)) // 2)
            events.extend([pulse] * duration)
            events.append({"type":"session.output_transcript.delta", "start_ms":seconds*1000,
                           "end_ms":(seconds+duration)*1000, "delta":paragraph+" "})
            seconds += duration
        class TimedSocket(Socket):
            elapsed = 0
            async def recv(self):
                event = json.loads(await super().recv())
                if event["type"] == "session.output_audio.delta":
                    self.elapsed += 1
                return json.dumps(event)
        for complete in (True, False):
            chunks = list(events)
            if not complete:
                chunks[-1] = dict(chunks[-1], delta=paragraphs[-1].rsplit(". ",1)[0])
            sock = TimedSocket(chunks + [quiet]*3 + ([] if complete else [OSError()]))
            with patch.object(tts, "time", SimpleNamespace(monotonic=lambda:sock.elapsed)), patch.object(tts,"connect",sock.connect):
                run = tts.synthesize_audio_live_mp3(script, api_key="dummy",model=tts.LIVE_MODEL,voice="cedar")
                if complete:
                    result = await run
                    self.assertEqual(result.metadata["transcript_words"],len(tts.words(script)))
                    self.assertGreater(result.metadata["audio_seconds"],60)
                else:
                    result = await run
                    self.assertFalse(result.validated)
                    self.assertLess(result.metadata["coverage_percent"], 100)
                    self.assertGreater(result.metadata["audio_seconds"], 60)

    async def test_incomplete_and_absent_transcripts_keep_playable_audio(self):
        started, chunk, transcript = session_events()
        for received, expected_percent in [("Білім", 50), ("", 0)]:
            events = [started, chunk]
            if received:
                events.append(dict(transcript, delta=received))
            with patch.object(tts, "INACTIVITY_SECONDS", .02):
                result = await self.generate(Socket(events))
            self.assertFalse(result.validated)
            self.assertGreater(len(result.mp3), 6000)
            self.assertEqual(result.metadata["coverage_percent"], expected_percent)
            self.assertEqual(result.metadata["transcript"], received)
            self.assertEqual(result.metadata["termination_reason"], "incomplete_narration")
            self.assertEqual(result.metadata["audio_seconds"], 1)

    async def test_silent_output_rejected_after_one_session_even_with_transcript(self):
        started, chunk, transcript = session_events()
        silent = dict(chunk, delta=base64.b64encode(bytes(len(sample_pcm()))).decode())
        for transcript_events in ([], [transcript]):
            sock = Socket([started, silent, *transcript_events])
            with patch.object(tts, "INACTIVITY_SECONDS", .02), self.assertRaises(tts.SilentNarration) as error:
                await self.generate(sock, nudge_seconds=.01, startup_deadline=.22)
            self.assertIn("pcm_peak=0", str(error.exception))
            self.assertIn("end=startup_silence_timeout", str(error.exception))
            self.assertEqual(sum(e["type"] == "session.start" for e in sock.sent), 1)

    async def test_generation_deadline_salvages_pcm_and_corrupt_encoding_fails(self):
        with patch.object(tts, "MAX_SECONDS", 1.1):
            result = await self.generate(Socket(session_events()[:2]))
        self.assertFalse(result.validated)
        self.assertEqual(result.metadata["termination_reason"], "generation_timeout")
        with patch.object(tts.subprocess, "run", return_value=SimpleNamespace(stdout=b"")), self.assertRaises(tts.LiveError):
            await self.generate(Socket(session_events()))

    async def test_waits_for_ack_even_when_nudge_time_has_elapsed(self):
        waiting, acknowledge = asyncio.Event(), asyncio.Event()

        class SlowHandshake(Socket):
            async def recv(self):
                if self.events and self.events[0]["type"] == "session.started":
                    waiting.set()
                    await acknowledge.wait()
                return await super().recv()

        sock = SlowHandshake(session_events())
        run = asyncio.create_task(self.generate(sock, nudge_seconds=.01, startup_deadline=.5))
        await asyncio.wait_for(waiting.wait(), 1)
        await asyncio.sleep(.12)
        self.assertEqual([event["type"] for event in sock.sent], ["session.start"])
        acknowledge.set()
        result = await run
        self.assertTrue(result.validated)
        self.assertEqual(result.metadata["instruction_state"], "unsent")

    async def run_timeline(self, schedule):
        # Wall-clock independent: advance the session clock as each provider event arrives.
        started = session_events()[0]
        class Timeline(Socket):
            elapsed = 0
            async def recv(self):
                if self.events:
                    return await super().recv()
                if not schedule:
                    raise AssertionError("session did not close by end of schedule")
                self.elapsed, event = schedule.pop(0)
                return json.dumps(event)
        sock = Timeline([started])
        take = tts.Capture(tts.words("Білім алу."))
        config = tts.session_config("Білім алу.", tts.LIVE_MODEL, "cedar", tts.LIVE_NARRATION)
        with patch.object(tts, "time", SimpleNamespace(monotonic=lambda: sock.elapsed)):
            await tts.capture(sock, take, config, tts.JobTrace(), nudge_seconds=5, startup_deadline=12)
        return sock, take

    async def test_one_instruction_for_noise_or_silence_then_bounded_close(self):
        _, chunk, transcript = session_events()
        quiet = dict(chunk, delta=base64.b64encode(bytes(4800)).decode())
        noise = dict(chunk, delta=base64.b64encode(array("h", [25, -25] * 1200).tobytes()).decode())
        for reply, state in [
            ({"type": "session.instructions.appended", "client_event_id": tts.NUDGE_ID}, "accepted"),
            ({"type": "error", "error": {"client_event_id": tts.NUDGE_ID, "code": "invalid_command"}}, "rejected"),
        ]:
            sock, take = await self.run_timeline([
                (1, quiet), (4, noise), (5, dict(transcript, delta=" ")), (6, reply),
                (9, quiet), (11, noise), (12, quiet)])
            nudges = [event for event in sock.sent if event["type"] == "session.instructions.append"]
            self.assertEqual(nudges, [dict(type="session.instructions.append", event_id=tts.NUDGE_ID,
                                           delegation_id=None, content=tts.NUDGE)])
            self.assertEqual((take.instruction_state, take.reason, sock.elapsed), (state, "startup_silence_timeout", 12))
            self.assertEqual(take.signal.voiced_bytes, 0)
            self.assertFalse(take.validated)
            self.assertEqual(take.metadata()["audio_kind"], "below_activity_floor")
        with self.assertRaises(tts.SilentNarration):
            tts.encode_mp3(array("h", [25, -25] * tts.RATE).tobytes())

    async def test_no_output_is_distinct_from_digital_silence(self):
        tick = {"type": "session.usage.updated", "usage": {"seconds": 11}}
        for event, expected in [(tick, "no_audio"), ({"type": "session.output_audio.delta",
                                 "delta": base64.b64encode(bytes(4800)).decode()}, "digital_silence")]:
            sock, take = await self.run_timeline([(5, event), (12, tick)])
            self.assertEqual(take.metadata()["audio_kind"], expected)
            self.assertEqual(take.interim_usage_seconds, 11)
            self.assertEqual(take.reason, "startup_silence_timeout")
            self.assertEqual(take.instruction_state, "sent")
            self.assertEqual(sock.sent[-1]["type"], "session.close")

    async def test_delayed_speech_and_natural_pauses_never_restart_narration(self):
        _, chunk, transcript = session_events()
        quiet = dict(chunk, delta=base64.b64encode(bytes(4800)).decode())
        ack = {"type": "session.instructions.appended", "client_event_id": tts.NUDGE_ID}
        for onset in ([(2.54, chunk), (5, quiet)], [(5, quiet), (5.2, ack), (7, chunk)],
                      [(4.9, dict(transcript, delta="Білім ")), (5, quiet), (7, chunk)]):
            final = dict(transcript, delta="алу.") if onset[0][0] == 4.9 else transcript
            sock, take = await self.run_timeline(onset + [(14, quiet), (15, chunk), (15.1, final), (18, quiet)])
            self.assertTrue(take.validated)
            self.assertEqual(take.metadata()["non_silent_seconds"], 2)
            self.assertGreater(take.metadata()["pcm_rms"], 64)
            self.assertEqual(sum(e["type"] == "session.instructions.append" for e in sock.sent),
                             int(onset[0][0] == 5))

    def test_pcm_windows_span_chunks_and_reject_an_isolated_click(self):
        activity = tts.AudioActivity()
        click = array("h", [26000] + [0] * 479).tobytes()
        self.assertFalse(activity.add(click + bytes(960)))
        self.assertFalse(activity.add(array("h", [700] * 4800).tobytes()))
        self.assertFalse(activity.add(sample_pcm()[:700]))
        self.assertTrue(activity.add(sample_pcm()[700:]))
        self.assertEqual(activity.voiced_bytes, 2 * tts.RATE)

    async def test_invalid_input_never_connects(self):
        with patch.object(tts, "connect") as connect:
            for text, model in [("", tts.LIVE_MODEL), ("x"*6001, tts.LIVE_MODEL), ("ok","gpt-realtime-2.1")]:
                with self.assertRaises(tts.LiveError):
                    await tts.synthesize_audio_live_mp3(text, api_key="dummy", model=model, voice="cedar")
            connect.assert_not_called()


@override_settings(LIVE_EXPLANATIONS_ENABLED=True)
class WorkflowTests(TestCase):
    def setUp(self):
        self.lesson = make_lesson(1)
        self.user = User.objects.create_superuser("owner", "owner@example.test")
        self.client.force_login(self.user)
        self.url = reverse("live_explanation", args=[1, "content"])
        self.legacy = Explanation.objects.create(lesson=self.lesson, section="content", text="  Білім алу.  ",
                                                 audio_url="/media/audio_lesson_1_content_saved.mp3")

    def post(self, mode="comparison", job=None):
        return self.client.post(self.url, {"job": job or uuid4(), "mode":mode})

    @override_settings(LIVE_EXPLANATIONS_ENABLED=False)
    def test_disabled_never_queues_or_calls_provider(self):
        with patch("lessons.services.live_explanations.synthesize_audio_live_mp3") as paid:
            self.assertEqual(self.post().status_code, 404)
            self.assertFalse(execute_next())
            self.assertNotContains(self.client.get("/lesson/1/"), "data-live-button")
            self.assertContains(self.client.get("/lesson/1/"), "explain-btn")
            paid.assert_not_called()

    def test_permissions_methods_csrf_and_inputs(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url).status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code,405)
        self.assertEqual(self.client.post(self.url.replace("content","other")).status_code,404)
        self.assertEqual(self.client.post(self.url.replace("/1/","/42/")).status_code,404)
        self.assertEqual(self.client.post(self.url).status_code,400)
        self.assertEqual(self.post("other").status_code,400)
        self.legacy.delete()
        self.assertEqual(self.post().status_code,400)
        self.assertFalse(LiveExplanation.objects.exists())
        audio_url = reverse("live_audio",args=[1,"content",uuid4()])
        for user in (User.objects.create_user("staff", is_staff=True), None):
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            self.assertEqual(self.post().status_code,403)
            self.assertEqual(self.client.get(self.url).status_code,403)
            self.assertEqual(self.client.get(audio_url).status_code,403)
            self.assertNotContains(self.client.get("/lesson/1/"), "live-explanation.js")

    def test_atomic_preview_duplicate_and_failed_regeneration_preserve_both_recordings(self):
        path = "lessons.services.live_explanations."
        binary = tts.encode_mp3(sample_pcm())
        job = uuid4()
        with TemporaryDirectory() as temp, override_settings(MEDIA_ROOT=temp, PRIVATE_EXPLANATION_ROOT=temp):
            old = Path(temp) / Path(self.legacy.audio_url).name
            old.write_bytes(b"old recording")
            with patch(path+"OpenAI") as text_api, patch(path+"synthesize_audio_live_mp3",new_callable=AsyncMock) as paid:
                paid.return_value = tts.Narration(binary, {"usage_seconds": 3}, validated=True)
                self.assertEqual(self.post(job=job).status_code,202)
                self.post()
                self.assertEqual(LiveExplanation.objects.get().job,job)
                self.assertTrue(execute_next())
                self.assertEqual(self.post(job=job).status_code,200)
                self.assertFalse(execute_next())
                self.assertEqual(paid.await_args.args,(self.legacy.text,))
                text_api.assert_not_called()
                self.assertEqual(paid.await_count,1)
                stored = LiveExplanation.objects.get()
                self.assertEqual(stored.source_hash, hashlib.sha256(self.legacy.text.encode()).hexdigest())
                url = self.client.get(self.url).json()["audio_url"]
                self.assertEqual(self.client.get(url).content,binary)
                part = self.client.get(url, HTTP_RANGE="bytes=0-1")
                self.assertEqual((part.status_code,part.content),(206,binary[:2]))
                self.assertIn("no-store",part["Cache-Control"])
                self.assertEqual(self.client.head(url)["Content-Length"],str(len(binary)))
                self.assertEqual(self.client.get(url,HTTP_RANGE="bytes=999999-").status_code,416)
                self.assertContains(self.client.get("/lesson/1/"),url)
                paid.side_effect = tts.LiveError("private failure")
                self.post()
                self.assertTrue(execute_next())
                self.assertEqual(self.client.get(self.url).json()["status"],"failed")
                self.assertEqual(self.client.get(url).content,binary)
                self.assertEqual(old.read_bytes(),b"old recording")
                self.legacy.refresh_from_db()
                self.assertEqual(self.legacy.text,stored.text)
                self.client.logout()
                self.assertEqual(self.client.get(url).status_code,403)

    def test_review_publication_preserves_validated_audio_and_is_private(self):
        binary = tts.encode_mp3(sample_pcm())
        take = LiveExplanation.objects.create(lesson=self.lesson, section="content", status="ready",
                                             revision=uuid4(), mp3=binary, text="Previous validated script.")
        good_url = reverse("live_audio", args=[1, "content", take.revision])
        meta = {"transcript":"Білім <b>", "coverage_percent":50, "audio_seconds":1,
                "termination_reason":"incomplete_narration"}
        job = uuid4()
        path = "lessons.services.live_explanations."
        with patch(path + "OpenAI") as astra, patch(path + "synthesize_audio_live_mp3", new_callable=AsyncMock,
                  return_value=tts.Narration(binary, meta, validated=False)) as paid:
            self.post(job=job)
            self.assertTrue(execute_next())
            self.assertEqual(self.post(job=job).status_code, 200)
            self.assertFalse(execute_next())
            astra.assert_not_called()
            self.assertEqual(paid.await_count, 1)
        payload = self.client.get(self.url).json()
        self.assertEqual(payload["status"], "review")
        review = payload["review"]
        self.assertEqual(review["text"], self.legacy.text)
        self.assertEqual(review["transcript"], meta["transcript"])
        self.assertEqual(review["coverage_percent"], 50)
        self.assertEqual(review["termination_reason"], "incomplete_narration")
        self.assertEqual(payload["audio_url"], good_url)
        self.assertEqual(payload["text"], "Previous validated script.")
        self.assertEqual(self.client.get(good_url).content, binary)
        self.assertEqual(self.client.get(review["audio_url"], HTTP_RANGE="bytes=0-1").content, binary[:2])
        page = self.client.get("/lesson/1/")
        self.assertContains(page, "Аудио толық оқылмауы мүмкін. Тыңдап тексеріңіз.")
        self.assertContains(page, r"\u003Cb\u003E")
        self.assertContains(page, review["audio_url"])
        with override_settings(LIVE_EXPLANATIONS_ENABLED=False):
            self.assertEqual(self.client.get(review["audio_url"]).status_code, 404)
        for user in (User.objects.create_user("review-staff", is_staff=True), None):
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.get(review["audio_url"]).status_code, 403)
            self.assertEqual(self.client.get(self.url, {"reviews": "1"}).status_code, 403)
            self.assertNotContains(self.client.get("/lesson/1/"), "Техникалық ақпарат")

    def test_fresh_mode_uses_prompt_compare_snapshots_exact_text_and_jobs_expire(self):
        self.post()
        self.legacy.text = "Updated"
        self.legacy.save()
        row = LiveExplanation.objects.get()
        self.assertEqual(row.pending_input,"  Білім алу.  ")
        LiveExplanation.objects.update(deadline=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get(self.url).json()["status"],"failed")
        self.assertFalse(execute_next())
        self.post("fresh")
        row.refresh_from_db()
        self.assertEqual(row.pending_input,build_explanation_prompt(self.lesson,"content"))
        path = "lessons.services.live_explanations."
        with patch(path+"OpenAI") as api, patch(path+"synthesize_audio_live_mp3",new_callable=AsyncMock) as paid:
            api.return_value.__enter__.return_value.responses.create.return_value = SimpleNamespace(status="completed", output_text="Fresh.")
            paid.return_value = tts.Narration(tts.encode_mp3(sample_pcm()),{}, validated=True)
            call_command("process_live_explanations", limit=1, stop_requested=lambda: False)
            self.assertEqual(paid.await_args.args,("Fresh.",))
            self.assertEqual(LiveExplanation.objects.get().mode,"fresh")
            self.assertEqual(self.client.get(self.url).json()["status"],"ready")

    def test_fresh_without_realtime_record_and_comparison_have_independent_call_counts(self):
        self.legacy.delete()
        binary = tts.encode_mp3(sample_pcm())
        path = "lessons.services.live_explanations."
        with patch(path+"OpenAI") as api, patch(path+"synthesize_audio_live_mp3", new_callable=AsyncMock,
                  return_value=tts.Narration(binary, {}, validated=True)) as speech, \
                patch("lessons.views.synthesize_audio_realtime_mp3") as realtime:
            client = api.return_value.__enter__.return_value
            client.responses.create.return_value = SimpleNamespace(status="completed", output_text="Fresh script.")
            self.assertEqual(self.post("fresh").status_code, 202)
            self.assertTrue(execute_next())
            self.assertFalse(Explanation.objects.filter(lesson=self.lesson).exists())
            self.assertEqual(speech.await_args.args, ("Fresh script.",))
            self.assertEqual(speech.await_count, 1)
            # Comparison needs text only; no Realtime recording is required.
            Explanation.objects.create(lesson=self.lesson, section="content", text="  Stored.  ")
            self.assertEqual(self.post("comparison").status_code, 202)
            self.assertTrue(execute_next())
            self.assertFalse(execute_next())
            self.assertEqual(speech.await_count, 2)
            self.assertEqual(speech.await_args.args, ("  Stored.  ",))
            client.responses.create.assert_called_once()
            client.chat.completions.create.assert_not_called()
            realtime.assert_not_called()

    def test_empty_fresh_script_has_no_second_paid_call(self):
        path = "lessons.services.live_explanations."
        with patch(path+"OpenAI") as api, patch(path+"synthesize_audio_live_mp3", new_callable=AsyncMock) as speech:
            client = api.return_value.__enter__.return_value
            client.responses.create.return_value = SimpleNamespace(status="completed", output_text="  ")
            self.post("fresh")
            self.assertTrue(execute_next())
            self.assertFalse(execute_next())
            self.assertEqual(self.client.get(self.url).json()["status"], "failed")
            client.responses.create.assert_called_once()
            client.chat.completions.create.assert_not_called()
            speech.assert_not_awaited()

    def test_silence_preserves_validated_take_without_review_or_retry(self):
        binary = tts.encode_mp3(sample_pcm())
        row = LiveExplanation.objects.create(lesson=self.lesson, section="content", status="ready",
                                             revision=uuid4(), text="Previous.", mp3=binary)
        revision = row.revision
        with patch("lessons.services.live_explanations.synthesize_audio_live_mp3", new_callable=AsyncMock,
                   side_effect=tts.SilentNarration("decoded MP3 is silent")) as speech:
            self.post()
            self.assertTrue(execute_next())
            self.assertFalse(execute_next())
            speech.assert_awaited_once()
        row.refresh_from_db()
        self.assertEqual(row.revision, revision)
        self.assertEqual(row.mp3, binary)
        self.assertEqual(self.client.get(self.url).json()["status"], "silent")
        self.assertFalse(row.reviews.exists())

    def test_complete_response_is_extracted_before_socket_and_script_survives_wire_serialization(self):
        script = '  Сабақ. "Go."\n' * 180
        sock = Socket([session_events()[0], OSError()])
        phase = []
        class Response:
            status = "completed"
            @property
            def output_text(self):
                phase.append("extracted")
                return script
        def respond(**kwargs):
            phase.append("responses")
            return Response()
        def connect(*args, **kwargs):
            phase.append("connect")
            return sock.connect()
        with patch("lessons.services.live_explanations.OpenAI") as api, patch.object(tts, "connect", connect), \
                self.assertLogs(tts.logger, level="INFO") as logs:
            api.return_value.__enter__.return_value.responses.create.side_effect = respond
            self.post("fresh")
            self.assertTrue(execute_next())
        self.assertEqual(phase, ["responses", "extracted", "connect"])
        self.assertEqual(sock.sent[0]["session"]["input"][-1]["content"], [{"type": "input_text", "text": script}])
        self.assertEqual(LiveExplanation.objects.get().retry_text, script)
        events = [json.loads(line.split("live_narration ", 1)[1]) for line in logs.output]
        self.assertEqual([e["event"] for e in events][:7], ["astra_started", "astra_completed", "source_ready",
                         "websocket_connecting", "websocket_connected", "session_start_sent", "session_started"])
        self.assertEqual(events[1]["source_hash"], events[5]["source_hash"])
        self.assertFalse(any("Сабақ" in line for line in logs.output))

    def test_partial_astra_response_does_not_replace_retry_script_or_open_socket(self):
        row = LiveExplanation.objects.create(lesson=self.lesson, section="content", retry_text="Earlier.",
                                             retry_metadata=tts.script_info("Earlier."))
        with patch("lessons.services.live_explanations.OpenAI") as api, patch.object(tts, "connect") as connect:
            client = api.return_value.__enter__.return_value
            client.responses.create.return_value = SimpleNamespace(status="incomplete", output_text="Only half")
            self.post("fresh")
            self.assertTrue(execute_next())
            connect.assert_not_called()
            client.responses.create.assert_called_once()
            client.chat.completions.create.assert_not_called()
        row.refresh_from_db()
        self.assertEqual((row.retry_text, row.status), ("Earlier.", "failed"))

    def test_manual_retry_after_silence_uses_saved_text_and_preserves_both_recording_urls(self):
        self.legacy.delete()
        row = LiveExplanation.objects.create(lesson=self.lesson, section="content", status="ready",
                    revision=uuid4(), text="Previous.", mp3=b"previous private bytes", mode="fresh")
        old_url = reverse("live_audio", args=[1, "content", row.revision])
        self.assertEqual(self.post("retry").status_code, 400)
        script = "  Қазақша. English.  "
        job = uuid4()
        with patch("lessons.services.live_explanations.OpenAI") as api, \
                patch("lessons.views.synthesize_audio_realtime_mp3") as realtime, \
                patch("lessons.services.live_explanations.synthesize_audio_live_mp3", new_callable=AsyncMock) as live:
            client = api.return_value.__enter__.return_value
            client.responses.create.return_value = SimpleNamespace(status="completed", output_text=script)
            live.side_effect = [tts.SilentNarration("silent"), tts.Narration(b"new private bytes", {}, True)]
            self.post("fresh", job)
            self.assertTrue(execute_next())
            self.assertFalse(execute_next())
            row.refresh_from_db()
            self.assertEqual(row.retry_text, script)
            self.assertEqual(row.retry_metadata["source_hash"], hashlib.sha256(script.encode()).hexdigest())
            self.assertEqual(row.retry_metadata["job"], str(job))
            self.assertEqual(row.status, "silent")
            self.assertTrue(self.client.get(self.url).json()["can_retry"])
            self.assertEqual(self.client.get(old_url).content, b"previous private bytes")
            self.assertEqual(self.post("retry").status_code, 202)
            self.assertTrue(execute_next())
            self.assertFalse(execute_next())
            self.assertEqual([c.args for c in live.await_args_list], [(script,), (script,)])
            client.responses.create.assert_called_once()
            realtime.assert_not_called()
        data = self.client.get(self.url).json()
        self.assertEqual(data["mode"], "retry")
        self.assertNotIn("review", data)
        self.assertEqual(self.client.get(data["audio_url"]).content, b"new private bytes")
        self.assertEqual(self.client.get(old_url).content, b"previous private bytes")
        self.client.logout()
        self.assertEqual(self.post("retry").status_code, 403)
        self.assertEqual(self.client.get(old_url).status_code, 403)

    def test_realtime_failure_keeps_previous_file_and_text(self):
        with TemporaryDirectory() as temp, override_settings(MEDIA_ROOT=temp, PRIVATE_EXPLANATION_ROOT=temp), patch("lessons.views.OpenAI") as astra, \
                patch("lessons.views.synthesize_audio_realtime_mp3", new_callable=AsyncMock,
                      side_effect=ValueError("mock failure")):
            original = Path(temp) / Path(self.legacy.audio_url).name
            original.write_bytes(b"previous audio")
            astra.return_value.__enter__.return_value.responses.create.return_value.output_text = "New text."
            response = self.client.post(reverse("explain_section", args=[1]), {"section": "content"})
            self.assertEqual(response.status_code, 502)
            self.legacy.refresh_from_db()
            self.assertEqual(self.legacy.text, "  Білім алу.  ")
            self.assertEqual(original.read_bytes(), b"previous audio")

    def test_original_view_keeps_url_contract_models_and_voice_fallback(self):
        original = reverse("explain_section",args=[1])
        self.assertEqual(original,"/lesson/1/explain-section/")
        with TemporaryDirectory() as temp, override_settings(MEDIA_ROOT=temp, PRIVATE_EXPLANATION_ROOT=temp), patch("lessons.views.OpenAI") as api, \
                patch("lessons.views.synthesize_audio_realtime_mp3",new_callable=AsyncMock) as speech:
            api.return_value.__enter__.return_value.responses.create.return_value.output_text = "Existing."
            speech.side_effect = [ValueError("mock"), tts.encode_mp3(sample_pcm())]
            response = self.client.post(original, {"section":"content"})
            self.assertEqual(set(response.json()),{"text","audio_url"})
            self.assertEqual(response.json()["text"],"Existing.")
            self.assertEqual([(c.kwargs["model"],c.kwargs["voice"]) for c in speech.await_args_list],
                             [("gpt-realtime-2.1","cedar"),("gpt-realtime-2.1","alloy")])
            self.assertFalse(LiveExplanation.objects.exists())

    def test_classroom_still_mints_owned_teacher_session_through_realtime(self):
        from .models import ClassGroup, UserProfile
        teacher = User.objects.create_user("teacher")
        UserProfile.objects.create(user=teacher,role="teacher",has_voice_access=True)
        group = ClassGroup.objects.create(teacher=teacher,name="Group")
        self.client.force_login(teacher)
        with patch("lessons.views_classroom.mint_realtime_client_secret",return_value={"value":"mock"}) as mint:
            response = self.client.post(reverse("mint_realtime_classroom_token",args=[1,group.pk]))
            self.assertEqual(response.json(),{"value":"mock"})
            self.assertEqual(mint.call_args.kwargs["voice"],"cedar")
            self.assertFalse(LiveExplanation.objects.exists())

    def test_failed_database_publication_retains_last_preview(self):
        from django.db import DatabaseError
        from django.db.models.query import QuerySet
        binary = tts.encode_mp3(sample_pcm())
        row = LiveExplanation.objects.create(
            lesson=self.lesson, section="content", status="ready", revision=uuid4(), text="Approved.", mp3=binary)
        self.post()
        update = QuerySet.update
        def fail_publication(query, **fields):
            if "mp3" in fields:
                raise DatabaseError("synthetic write failure")
            return update(query, **fields)
        with patch("lessons.services.live_explanations.synthesize_audio_live_mp3",new_callable=AsyncMock,
                   return_value=tts.Narration(binary, {}, validated=True)), patch.object(QuerySet,"update",fail_publication):
            self.assertTrue(execute_next())
        row.refresh_from_db()
        self.assertEqual((row.status, row.text, bytes(row.mp3)), ("failed", "Approved.", binary))



@override_settings(LIVE_EXPLANATIONS_ENABLED=True)
class ConcurrentLiveTests(TransactionTestCase):
    def test_parallel_enqueue_and_worker_claim_charge_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connection, connections
        from .services.live_explanations import enqueue
        if connection.vendor == "sqlite" and connection.is_in_memory_db():
            self.skipTest("Run independent writers on file-backed SQLite or MySQL.")
        lesson = make_lesson(1)
        Explanation.objects.create(lesson=lesson,section="content",text="Білім алу.")
        def race(action):
            barrier = Barrier(2)
            def worker():
                try:
                    barrier.wait(timeout=5)
                    return action()
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker) for _ in range(2)]
                return [f.result(timeout=10) for f in futures]
        race(lambda: enqueue(lesson, "content", "comparison", uuid4()))
        with patch("lessons.services.live_explanations.synthesize_audio_live_mp3",new_callable=AsyncMock,
                   return_value=tts.Narration(tts.encode_mp3(sample_pcm()), {}, validated=True)) as paid:
            self.assertEqual(sorted(race(execute_next)), [False, True])
            self.assertEqual(paid.await_count, 1)
        self.assertEqual(LiveExplanation.objects.get().status,"ready")
