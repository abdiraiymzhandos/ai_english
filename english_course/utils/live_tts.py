"""One bounded, server-side GPT-Live narration. No Django, storage or SDK dependency."""
import asyncio
import audioop
import base64
import binascii
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
import json
import logging
import math
import re
import subprocess
import sys
import time
import unicodedata

from websockets.exceptions import ConnectionClosed, InvalidStatusCode
from websockets.legacy.client import connect

from .live_defaults import LIVE_MODEL, LIVE_NARRATION, STARTUP_DEADLINE_SECONDS, STARTUP_NUDGE_SECONDS

URL = "wss://api.openai.com/v1/live/sessions"
RATE = 24000
FORMAT = {"type": "audio/pcm", "rate": RATE}
MAX_CHARS = 6000
MAX_SECONDS = 360
DRAIN_SECONDS = 2.0
FINALIZE_SECONDS = 15
INACTIVITY_SECONDS = 25


NUDGE_ID = "lesson_narration_start"
NUDGE = ("Begin reading the supplied user script aloud now, once, starting with its first word. "
         "Read the entire script exactly. Do not wait for the caller or add an introduction.")
logger = logging.getLogger(__name__)


class JobTrace:
    def __init__(self, job=None):
        self.job = str(job) if job else None
        self.start = time.monotonic()

    def __call__(self, event, **fields):
        logger.info("live_narration %s", json.dumps({
            "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "elapsed_s": round(time.monotonic() - self.start, 3),
            "job": self.job, "event": event, **fields,
        }))


def script_info(text):
    return {"source_hash": sha256(text.encode()).hexdigest(), "characters": len(text),
            "words": len(words(text))}


class LiveError(Exception):
    """Messages are diagnostic categories suitable for logs, never raw provider payloads."""


class SilentNarration(LiveError):
    """A structurally valid stream with no signal to review."""


@dataclass
class Narration:
    mp3: bytes
    metadata: dict
    validated: bool


def words(text):
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text).casefold(), re.UNICODE)


def session_config(text, model, voice, instructions):
    def message(role, value):
        return {"type": "message", "role": role, "content": [{"type": "input_text", "text": value}]}

    return {"model": model, "audio": {"format": FORMAT, "output": {"voice": voice}},
            "instructions": instructions, "delegation": {"type": "client"}, "store": False,
            "input": [message("developer", "Take the first speaking turn immediately. Read the following user message "
                                        "aloud verbatim, starting with its first word. Do not wait for a spoken cue."),
                      message("user", text)]}


async def send(ws, event_type, **fields):
    await ws.send(json.dumps({"type": event_type, **fields}, ensure_ascii=False))


async def pace_silence(ws, take, trace):
    # Each 100 ms of transport input takes 100 ms of wall-clock time. Never catch up in bursts.
    frame = base64.b64encode(bytes(RATE * 2 // 10)).decode("ascii")
    while True:
        await send(ws, "session.input_audio.append", audio=frame)
        take.input_frames += 1
        if take.input_frames == 1:
            trace("first_input_frame")
        await asyncio.sleep(0.1)


async def receive(ws):
    event = json.loads(await ws.recv())
    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        raise LiveError("invalid event")
    return event


class AudioActivity:
    """Measure contiguous 20 ms windows across arbitrary PCM16LE packet boundaries."""
    window_bytes = RATE * 2 // 50
    min_windows = 3

    def __init__(self):
        self.tail = b""
        self.run = 0
        self.voiced_bytes = 0
        self.peak = 0

    def add(self, pcm):
        native = audioop.byteswap(pcm, 2) if sys.byteorder != "little" else pcm
        self.peak = max(self.peak, audioop.max(native, 2))
        data = self.tail + native
        end = len(data) - len(data) % self.window_bytes
        self.tail = data[end:]
        before = self.voiced_bytes
        for pos in range(0, end, self.window_bytes):
            window = data[pos:pos + self.window_bytes]
            # DC offset can have high raw RMS despite carrying no audible variation.
            mean = audioop.avg(window, 2)
            low, high = audioop.minmax(window, 2)
            ac_power = audioop.rms(window, 2) ** 2 - mean ** 2
            if ac_power < 64 ** 2 or max(high - mean, mean - low) < 128:
                self.run = 0
                continue
            self.run += 1
            if self.run == self.min_windows:
                self.voiced_bytes += self.min_windows * self.window_bytes
            elif self.run > self.min_windows:
                self.voiced_bytes += self.window_bytes
        return self.voiced_bytes > before


@dataclass
class Capture:
    expected: list
    pcm: bytearray = field(default_factory=bytearray)
    transcript: str = ""
    first_ms: int = None
    end_ms: int = 0
    signal: AudioActivity = field(default_factory=AudioActivity)
    instruction_state: str = "unsent"
    transcript_events: int = 0
    transcript_evidence: bool = False
    provider_close_reason: str = ""
    input_frames: int = 0
    output_chunks: int = 0
    first_signal_seconds: float = None
    uncertain: bool = False
    validated: bool = False
    reason: str = ""
    usage_seconds: float = None
    interim_usage_seconds: float = None

    def add_transcript(self, event):
        delta = event.get("delta")
        if not isinstance(delta, str):
            self.uncertain = True
            return
        space = MAX_CHARS * 3 - len(self.transcript)
        self.transcript += delta[:space]
        begin, end = event.get("start_ms"), event.get("end_ms")
        if (len(delta) > space or type(begin) != int or type(end) != int or
                not 0 <= begin <= end <= 1000 * MAX_SECONDS):
            self.uncertain = True
            return
        meaningful = bool(words(delta))
        if meaningful:
            self.transcript_evidence = True
        if self.first_ms is None:
            self.first_ms = begin
        self.end_ms = max(self.end_ms, end)
        return meaningful

    def complete(self, elapsed):
        return (not self.uncertain and self.first_ms is not None
                and words(self.transcript) == self.expected
                and len(self.pcm) / (2 * RATE) >= (self.end_ms - self.first_ms) / 1000 - 0.1
                and self.signal.voiced_bytes / (2 * RATE) >= len(self.expected) * 0.065
                and elapsed >= self.end_ms / 1000)

    def metadata(self):
        received = words(self.transcript)
        alignment = SequenceMatcher(None, self.expected, received, autojunk=False)
        matched = sum(block.size for block in alignment.get_matching_blocks())
        if not self.pcm:
            audio_kind = "no_audio"
        elif not self.signal.peak:
            audio_kind = "digital_silence"
        elif self.signal.voiced_bytes:
            audio_kind = "meaningful"
        else:
            audio_kind = "below_activity_floor"
        return {"audio_kind": audio_kind, "interim_usage_seconds": self.interim_usage_seconds,
                "usage_seconds": self.usage_seconds, "audio_seconds": len(self.pcm) / (2 * RATE),
                "input_frames": self.input_frames, "output_chunks": self.output_chunks,
                "pcm_peak": self.signal.peak, "first_signal_seconds": self.first_signal_seconds,
                "pcm_rms": audioop.rms(self.pcm if sys.byteorder == "little" else audioop.byteswap(self.pcm, 2), 2),
                "non_silent_seconds": self.signal.voiced_bytes / (2 * RATE),
                "instruction_state": self.instruction_state, "provider_close_reason": self.provider_close_reason,
                "transcript_words": len(received), "transcript": self.transcript,
                "coverage_percent": round(100 * matched / len(self.expected), 1),
                "termination_reason": self.reason, "validated": self.validated}


def usage_seconds(event):
    seconds = (event.get("usage") or {}).get("seconds")
    if type(seconds) in (float, int) and math.isfinite(seconds) and seconds >= 0:
        return seconds


async def capture(ws, take, config, trace, nudge_seconds, startup_deadline):
    await send(ws, "session.start", session=config)
    trace("session_start_sent", **script_info(config["input"][-1]["content"][0]["text"]),
          instructions_hash=sha256(config["instructions"].encode()).hexdigest())
    try:
        started = await asyncio.wait_for(receive(ws), 12)
    except asyncio.TimeoutError:
        raise LiveError("session_ack_timeout") from None
    if started["type"] == "error":
        raise LiveError("session_start_rejected")
    session = started.get("session", {})
    audio = session.get("audio", {})
    if (started["type"] != "session.started" or session.get("model") != config["model"] or
            audio.get("format") != FORMAT or audio.get("output", {}).get("voice") != config["audio"]["output"]["voice"]):
        raise LiveError("unexpected negotiated session")

    trace("session_started", model=session["model"], voice=audio["output"]["voice"], rate=RATE)
    start = last_activity = time.monotonic()
    closing = None
    remote_closed = False
    candidate_until = start
    silence = asyncio.create_task(pace_silence(ws, take, trace))
    try:
        while True:
            now = time.monotonic()
            if closing is not None and now - closing >= FINALIZE_SECONDS:
                take.reason = "finalization_timeout"
                return
            if closing is None and silence.done():
                silence.result()
            try:
                event = await asyncio.wait_for(receive(ws), 0.1)
            except asyncio.TimeoutError:
                event = {"type": None}  # Evaluate session deadlines even without any output.
            except (ValueError, LiveError):
                take.reason = "invalid_stream_event"
                return
            kind = event["type"]
            if kind == "session.output_audio.delta":
                try:
                    chunk = base64.b64decode(event.get("delta"), validate=True)
                except (ValueError, TypeError, binascii.Error):
                    take.reason = "invalid_audio_chunk"
                    return
                if len(chunk) % 2:
                    take.reason = "invalid_audio_chunk"
                    return
                take.output_chunks += 1
                if take.output_chunks == 1:
                    trace("first_output_chunk", samples=len(chunk) // 2)
                remaining = int(RATE * MAX_SECONDS) * 2 - len(take.pcm)
                limited = len(chunk) > remaining
                chunk = chunk[:remaining]
                take.pcm.extend(chunk)
                if take.signal.add(chunk):
                    last_activity = time.monotonic()
                    if take.first_signal_seconds is None:
                        take.first_signal_seconds = round(last_activity - start, 3)
                        trace("first_meaningful_audio", peak=take.signal.peak)
                    if closing is not None:
                        take.uncertain = True
                if take.signal.run:
                    # Give a partial first syllable the next input interval to cross the duration floor.
                    candidate_until = time.monotonic() + 0.1
                if limited:
                    take.reason = "audio_limit"
                    return
            elif kind == "session.output_transcript.delta":
                take.transcript_events += 1
                if take.transcript_events == 1:
                    trace("first_transcript_event")
                if take.add_transcript(event):
                    last_activity = time.monotonic()
            elif kind == "session.instructions.appended" and event.get("client_event_id") == NUDGE_ID:
                take.instruction_state = "accepted"
                trace("startup_instruction_accepted")
            elif kind == "error":
                error = event.get("error") or {}
                rejected = (error.get("client_event_id") or event.get("client_event_id")) == NUDGE_ID
                if rejected:
                    take.instruction_state = "rejected"
                    trace("startup_instruction_rejected")
                category = str(error.get("type", "")) + " " + str(error.get("code", ""))
                if any(word in category.lower() for word in ("auth", "api_key", "permission", "policy", "safety")):
                    raise LiveError("provider denied request")
                if not rejected:
                    take.reason = "provider_error"
                    return
            elif kind == "session.usage.updated":
                take.interim_usage_seconds = usage_seconds(event)
            elif kind == "session.closed":
                remote_closed = True
                reason = event.get("reason")
                take.provider_close_reason = reason if reason in (
                    "content", "close_requested", "expired", "remote_hangup", "connection_lost") else "session_closed"
                trace("session_closed", reason=take.provider_close_reason)
                if reason == "content":
                    raise LiveError("provider denied request")
                take.usage_seconds = usage_seconds(event)
                take.validated = (closing is not None and not take.reason and reason == "close_requested"
                                  and take.usage_seconds is not None and take.complete(time.monotonic() - start))
                if not take.reason:
                    take.reason = reason if reason in ("close_requested", "expired", "remote_hangup",
                                                       "connection_lost") else "session_closed"
                return
            if closing is not None:
                continue
            now = time.monotonic()
            elapsed, idle = now - start, now - last_activity
            if take.first_signal_seconds is None and elapsed >= startup_deadline:
                take.reason = "startup_silence_timeout"
            elif idle >= DRAIN_SECONDS and take.complete(elapsed):
                trace("narration_complete")
            elif take.first_signal_seconds is not None and idle >= INACTIVITY_SECONDS:
                take.reason = "incomplete_narration"
            else:
                if (elapsed >= nudge_seconds and take.input_frames and take.instruction_state == "unsent"
                        and take.first_signal_seconds is None and not take.transcript_evidence
                        and now >= candidate_until):
                    await send(ws, "session.instructions.append", event_id=NUDGE_ID,
                               delegation_id=None, content=NUDGE)
                    take.instruction_state = "sent"
                    trace("startup_instruction_sent")
                continue
            silence.cancel()
            with suppress(asyncio.CancelledError):
                await silence
            await send(ws, "session.close")
            trace("session_close_requested", reason=take.reason or "narration_complete")
            closing = now
    finally:
        silence.cancel()
        with suppress(asyncio.CancelledError, OSError, ConnectionClosed):
            await silence
        if closing is None and not remote_closed:
            with suppress(Exception):
                await asyncio.wait_for(send(ws, "session.close"), 1)
                trace("session_close_requested", reason=take.reason or "cleanup")


def encode_mp3(pcm):
    """Bound both encoding and a full decoding pass; reject short or corrupt output."""
    def ffmpeg(args, data):
        return subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror",
                               *args, "pipe:1"], input=data, capture_output=True, timeout=20, check=True).stdout
    mp3 = ffmpeg(["-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", "pipe:0", "-c:a", "libmp3lame",
                  "-b:a", "64k", "-f", "mp3"], pcm)
    decoded = ffmpeg(["-f", "mp3", "-i", "pipe:0", "-ac", "1", "-ar", str(RATE), "-f", "s16le"], mp3)
    if not mp3 or not decoded or abs(len(decoded) - len(pcm)) > RATE // 2:
        raise LiveError("invalid MP3")
    activity = AudioActivity()
    if not activity.add(decoded):
        raise SilentNarration("decoded MP3 is silent" if not activity.peak else "decoded MP3 is below activity floor")
    return mp3


async def synthesize_audio_live_mp3(text, *, api_key, model, voice, system_instructions=LIVE_NARRATION,
                                    trace=None, nudge_seconds=STARTUP_NUDGE_SECONDS,
                                    startup_deadline=STARTUP_DEADLINE_SECONDS):
    if (not api_key or model != LIVE_MODEL or not voice or not system_instructions or
            len(text) > MAX_CHARS or not words(text)):
        raise LiveError("invalid narration configuration or script")
    if not 0 < nudge_seconds < startup_deadline <= 360:
        raise LiveError("invalid startup timing")
    trace = trace or JobTrace()
    start = time.monotonic()
    config = session_config(text, model, voice, system_instructions)
    take = Capture(words(text))

    async def record():
        trace("websocket_connecting")
        async with connect(URL, extra_headers={"Authorization": "Bearer " + api_key}, open_timeout=10,
                           close_timeout=2, max_size=512 * 1024, max_queue=4, compression=None) as ws:
            trace("websocket_connected")
            await capture(ws, take, config, trace, nudge_seconds, startup_deadline)
    try:
        try:
            await asyncio.wait_for(record(), MAX_SECONDS)
        except asyncio.TimeoutError:
            take.reason = "generation_timeout"
        except ConnectionClosed as exc:
            if exc.code in (1008, 4401, 4403):
                raise LiveError("provider denied request") from None
            take.reason = "connection_lost"
        except OSError:
            take.reason = "connection_lost"
        if not take.pcm:
            raise LiveError(take.reason or "no_audio")
        try:
            mp3 = encode_mp3(take.pcm)
        except SilentNarration as exc:
            raise SilentNarration(f"{exc}; end={take.reason}, pcm_peak={take.signal.peak}") from None
    except LiveError as exc:
        if not take.reason:
            take.reason = str(exc)
        trace("audio_failed", error=str(exc))
        raise
    except InvalidStatusCode as exc:
        take.reason = f"handshake_http_{exc.status_code}"
        raise LiveError(take.reason) from None
    except Exception as exc:
        take.reason = type(exc).__name__
        raise LiveError(take.reason) from None
    finally:
        metadata = take.metadata()
        trace("audio_summary", **{k: v for k, v in metadata.items() if k != "transcript"})
    metadata["latency_seconds"] = round(time.monotonic() - start, 3)
    return Narration(mp3, metadata, take.validated)
