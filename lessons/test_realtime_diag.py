# test_realtime_diag.py
import os, asyncio, base64, wave
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
OUT = "realtime_diag.wav"

SAMPLE_RATE = 24000  # Realtime әдетте 24 kHz PCM береді

def save_pcm16_as_wav(pcm_bytes: bytes, path: str, *, sample_rate: int = SAMPLE_RATE):
    """Raw PCM16 mono -> WAV файлға орау."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)

async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY жоқ")

    client = AsyncOpenAI(api_key=api_key)

    pcm_buf = bytearray()
    text_buf = []
    audio_chunks = 0
    text_chunks = 0

    print("=== Realtime test ===")
    async with client.beta.realtime.connect(model="gpt-realtime") as conn:
        print("Connected. Sending session.update ...")

        # НАЗАР: output_audio_format — string!
        await conn.session.update(session={
            "modalities": ["text", "audio"],
            "voice": "alloy",                    # қолжетімді дауыс
            "output_audio_format": "pcm16",      # дұрыс формат
            "instructions": (
                "You are a friendly American English teacher for Kazakh learners. "
                "Speak naturally and clearly."
            ),
        })

        # Тесті нақтылау үшін user мәтінін жібереміз
        await conn.conversation.item.create(item={
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text",
                         "text": "Please introduce yourself in 1–2 sentences, then say one simple tip for learning English."}]
        })

        await conn.response.create()

        async for event in conn:
            et = getattr(event, "type", "")

            if et == "session.created":
                s = event.session
                print(f"session.created → model={getattr(s,'model',None)}  "
                      f"voice={getattr(s,'voice',None)}  "
                      f"out_fmt={getattr(s,'output_audio_format',None)}")

            elif et == "response.text.delta":
                text_chunks += 1
                text_buf.append(getattr(event, "delta", ""))

            elif et == "response.audio.delta":
                audio_chunks += 1
                b64 = getattr(event, "delta", "")
                if b64:
                    pcm_buf.extend(base64.b64decode(b64))

            elif et in ("response.done", "response.completed"):
                break

            elif et in ("error", "response.error"):
                print("!!! Realtime error:", getattr(event, "error", event))
                break

    # WAV-қа сақтаймыз (PCM16-ны орап)
    if pcm_buf:
        save_pcm16_as_wav(bytes(pcm_buf), OUT, sample_rate=SAMPLE_RATE)
        print(f"Saved WAV => {OUT} ({len(pcm_buf)} raw PCM bytes)")
    else:
        print("WARNING: audio buffer is empty.")

    preview = "".join(text_buf)
    print(f"Audio chunks: {audio_chunks}  Text chunks: {text_chunks}")
    print("Text preview:", (preview[:140] + ("..." if len(preview) > 140 else "")) or "(no text)")

if __name__ == "__main__":
    asyncio.run(main())
