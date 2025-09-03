# english_course/utils/realtime_tts.py
import base64, wave
from typing import Optional
from openai import AsyncOpenAI

SAMPLE_RATE = 24000  # Realtime PCM16 әдетте 24kHz

def _pcm16_to_wav_bytes(pcm: bytes, *, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Raw PCM16 mono-ны WAV контейнеріне орап, bytes қайтару."""
    from io import BytesIO
    bio = BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)        # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return bio.getvalue()

async def synthesize_audio_realtime_wav(
    text: str,
    *,
    api_key: str,
    model: str = "gpt-realtime",
    voice: str = "cedar",                 # қол жетпесе, views.py ішінде alloy-ға ауысамыз
    sample_rate: int = SAMPLE_RATE,
    system_instructions: Optional[str] = None,
) -> bytes:
    """
    gpt-realtime арқылы text -> PCM16 stream -> WAV bytes
    """
    client = AsyncOpenAI(api_key=api_key)

    pcm_buf = bytearray()
    async with client.beta.realtime.connect(model=model) as conn:
        session_cfg = {
            "modalities": ["text", "audio"],
            "voice": voice,                      # НАЗАР: voice — жоғарғы деңгейдегі өріс
            "output_audio_format": "pcm16",      # string! ('pcm16' | 'g711_ulaw' | 'g711_alaw')
        }
        if system_instructions:
            session_cfg["instructions"] = system_instructions
        await conn.session.update(session=session_cfg)

        # user input
        await conn.conversation.item.create(item={
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        })

        await conn.response.create()

        async for event in conn:
            et = getattr(event, "type", "")
            if et == "response.audio.delta":
                b64 = getattr(event, "delta", "")
                if b64:
                    pcm_buf.extend(base64.b64decode(b64))
            elif et in ("response.done", "response.completed"):
                break
            elif et in ("error", "response.error"):
                # ашық түрде қате лақтырамыз — views.py фолбэк жасай алады
                err = getattr(event, "error", event)
                raise RuntimeError(f"Realtime error: {err}")

    return _pcm16_to_wav_bytes(bytes(pcm_buf), sample_rate=sample_rate)
