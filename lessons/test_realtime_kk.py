import os, asyncio, base64, wave
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
OUT = "realtime_kk.wav"
SAMPLE_RATE = 24000

def save_pcm16_as_wav(pcm_bytes: bytes, path: str, *, sr: int = SAMPLE_RATE):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm_bytes)

async def synthesize(voice_try: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY жоқ")
    client = AsyncOpenAI(api_key=api_key)

    pcm = bytearray()
    async with client.beta.realtime.connect(model="gpt-realtime") as conn:
        # Нұсқаулар: қазақша сөйлеу + сандарды сөзбен айту
        await conn.session.update(session={
            "modalities": ["text", "audio"],
            "voice": voice_try,                 # алдымен cedar-ды сұраймыз
            "output_audio_format": "pcm16",
            "instructions": (
                "Барлық жауапты қазақ тілінде айт. "
                "Сандар цифр түрінде берілсе де, оларды қазақша сан есіммен толық дауыстап айт "
                "(мысалы, 123 → «жүз жиырма үш»). "
                "Дауысың анық әрі табиғи болсын."
            ),
        })

        # Мәтін береміз (қалағаныңды қой)
        await conn.conversation.item.create(item={
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text",
                        "text": "Сәлем! Өзіңді қысқаша таныстыр да, соңында 2024 және 3.14 сандарын дауыстап айт."}]
        })
        await conn.response.create()

        async for event in conn:
            et = getattr(event, "type", "")
            if et == "response.audio.delta":
                b64 = getattr(event, "delta", "")
                if b64:
                    pcm.extend(base64.b64decode(b64))
            elif et in ("error", "response.error"):
                # дауысты қолдамаса осында қате келеді
                raise RuntimeError(getattr(event, "error", event))
            elif et in ("response.done", "response.completed"):
                break
    return bytes(pcm)

async def main():
    # 1) Алдымен cedar-мен әрекет жасап көреміз
    try:
        print("Trying voice=cedar ...")
        pcm = await synthesize("cedar")
    except Exception as e:
        print("cedar voice failed →", e)
        print("Falling back to voice=alloy ...")
        pcm = await synthesize("alloy")

    save_pcm16_as_wav(pcm, OUT)
    print(f"OK ✓ Saved {OUT} ({len(pcm)} bytes). Open and listen.")

if __name__ == "__main__":
    asyncio.run(main())
