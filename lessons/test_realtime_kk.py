import asyncio
import os

from dotenv import load_dotenv

from english_course.utils.realtime_tts import synthesize_audio_realtime_mp3

load_dotenv()

OUT = "realtime_kk.mp3"


async def synthesize(voice):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY жоқ")
    return await synthesize_audio_realtime_mp3(
        "Сәлем! Өзіңді қысқаша таныстыр да, соңында 2024 және 3.14 сандарын дауыстап айт.",
        api_key=api_key,
        voice=voice,
        system_instructions=(
            "Барлық жауапты қазақ тілінде айт. "
            "Сандар цифр түрінде берілсе де, оларды қазақша сан есіммен толық дауыстап айт. "
            "Дауысың анық әрі табиғи болсын."
        ),
    )


async def main():
    try:
        print("Trying voice=cedar ...")
        audio_bytes = await synthesize("cedar")
    except Exception as exc:
        print("cedar voice failed ->", exc)
        print("Falling back to voice=alloy ...")
        audio_bytes = await synthesize("alloy")

    with open(OUT, "wb") as audio_file:
        audio_file.write(audio_bytes)
    print(f"OK: saved {OUT} ({len(audio_bytes)} bytes).")


if __name__ == "__main__":
    asyncio.run(main())
