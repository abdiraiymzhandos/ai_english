# english_course/utils/realtime_tts.py
import base64
import json
import logging
import wave
from io import BytesIO
from typing import Optional

import websockets
from pydub import AudioSegment

from english_course.realtime_config import REALTIME_MODEL, REALTIME_WEBSOCKET_URL

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000


class RealtimeTTSError(RuntimeError):
    pass


def _pcm16_to_mp3_bytes(pcm: bytes, *, sample_rate: int = SAMPLE_RATE) -> bytes:
    wav_bytes = _pcm16_to_wav_bytes(pcm, sample_rate=sample_rate)
    audio = AudioSegment.from_file(BytesIO(wav_bytes), format="wav")
    bio = BytesIO()
    audio.export(bio, format="mp3", bitrate="128k")
    return bio.getvalue()


def _pcm16_to_wav_bytes(pcm: bytes, *, sample_rate: int = SAMPLE_RATE) -> bytes:
    bio = BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return bio.getvalue()


def _ws_url(model: str) -> str:
    return f"{REALTIME_WEBSOCKET_URL}?model={model}"


async def synthesize_audio_realtime_mp3(
    text: str,
    *,
    api_key: str,
    model: str = REALTIME_MODEL,
    voice: str = "cedar",
    sample_rate: int = SAMPLE_RATE,
    system_instructions: Optional[str] = None,
    safety_identifier: Optional[str] = None,
) -> bytes:
    """
    Generate MP3 bytes with the GA Realtime server WebSocket API.
    The caller owns persistence; this function never writes files.
    """
    if not text:
        raise RealtimeTTSError("No text provided for realtime audio synthesis")

    url = _ws_url(model)
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    if safety_identifier:
        headers["OpenAI-Safety-Identifier"] = safety_identifier

    instructions = system_instructions or (
        "Read the user's text aloud clearly and naturally. Do not add extra words."
    )
    session_update = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": instructions,
            "output_modalities": ["audio"],
            "audio": {
                "output": {
                    "voice": voice,
                    "format": {
                        "type": "audio/pcm",
                        "rate": sample_rate,
                    },
                },
            },
        },
    }
    user_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }
    response_create = {
        "type": "response.create",
        "response": {
            "output_modalities": ["audio"],
            "audio": {
                "output": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": sample_rate,
                    },
                },
            },
        },
    }

    pcm_buf = bytearray()
    completed = False

    logger.info("Connecting to Realtime TTS WebSocket with model %s", model)
    try:
        async with websockets.connect(url, additional_headers=headers) as websocket:
            await websocket.send(json.dumps(session_update))
            await websocket.send(json.dumps(user_item))
            await websocket.send(json.dumps(response_create))

            async for raw_message in websocket:
                try:
                    event = json.loads(raw_message)
                except (TypeError, ValueError) as exc:
                    raise RealtimeTTSError("Invalid JSON event from Realtime TTS") from exc

                event_type = event.get("type", "")
                if event_type == "response.output_audio.delta":
                    delta = event.get("delta", "")
                    if delta:
                        pcm_buf.extend(base64.b64decode(delta))
                elif event_type == "response.done":
                    completed = True
                    break
                elif event_type == "error":
                    error = event.get("error") or {}
                    message = error.get("message") if isinstance(error, dict) else str(error)
                    raise RealtimeTTSError(message or "Realtime TTS error")
                elif event_type in {"response.failed", "response.incomplete"}:
                    raise RealtimeTTSError(f"Realtime TTS ended with {event_type}")
    except RealtimeTTSError:
        raise
    except Exception as exc:
        logger.exception("Realtime TTS WebSocket failure")
        raise RealtimeTTSError("Realtime TTS connection failed") from exc

    if not completed:
        raise RealtimeTTSError("Realtime TTS response did not complete")
    if not pcm_buf:
        raise RealtimeTTSError("Realtime TTS returned no audio")

    return _pcm16_to_mp3_bytes(bytes(pcm_buf), sample_rate=sample_rate)


async def synthesize_audio_realtime_wav(*args, **kwargs) -> bytes:
    """Backward-compatible wrapper; returns MP3 bytes despite the legacy name."""
    return await synthesize_audio_realtime_mp3(*args, **kwargs)
