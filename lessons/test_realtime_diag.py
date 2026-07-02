import asyncio
import os

from dotenv import load_dotenv

from english_course.realtime_config import REALTIME_MODEL
from english_course.utils.realtime_tts import synthesize_audio_realtime_mp3

load_dotenv()

OUT = "realtime_diag.mp3"


async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY жоқ")

    print(f"=== Realtime GA TTS smoke test: {REALTIME_MODEL} ===")
    mp3_bytes = await synthesize_audio_realtime_mp3(
        "Please introduce yourself in one short sentence.",
        api_key=api_key,
        voice="cedar",
        system_instructions=(
            "You are a friendly American English teacher for Kazakh learners. "
            "Speak naturally and clearly."
        ),
    )
    with open(OUT, "wb") as audio_file:
        audio_file.write(mp3_bytes)
    print(f"Saved MP3 => {OUT} ({len(mp3_bytes)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
