from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from english_course.utils.live_tts import LiveError, MAX_CHARS, synthesize_audio_live_mp3


class Command(BaseCommand):
    help = "Explicitly paid single Live narration of a local UTF-8 script, outside lesson data."

    def add_arguments(self, parser):
        parser.add_argument("--authorize-paid-call", action="store_true")
        parser.add_argument("--input", required=True, type=Path)
        parser.add_argument("--output", required=True, type=Path)

    def handle(self, *args, **options):
        if not options["authorize_paid_call"]:
            raise CommandError("One paid Live call requires --authorize-paid-call.")
        output = options["output"].absolute()
        if output.exists() or output.suffix != ".mp3" or not output.parent.is_dir():
            raise CommandError("Choose a new .mp3 in an existing private directory.")
        for root in [settings.BASE_DIR, settings.MEDIA_ROOT, settings.STATIC_ROOT, *settings.STATICFILES_DIRS]:
            if output.resolve().is_relative_to(Path(root).resolve()):
                raise CommandError("Choose a private directory outside the checkout, media and static roots.")
        with options["input"].open(encoding="utf-8") as stream:
            text = stream.read(MAX_CHARS + 1)
        try:
            audio = async_to_sync(synthesize_audio_live_mp3)(
                text, api_key=settings.OPENAI_API_KEY, model=settings.LIVE_EXPLANATION_MODEL,
                voice=settings.LIVE_EXPLANATION_VOICE, system_instructions=settings.LIVE_EXPLANATION_INSTRUCTIONS,
                nudge_seconds=settings.LIVE_STARTUP_NUDGE_SECONDS, startup_deadline=settings.LIVE_STARTUP_DEADLINE_SECONDS)
        except LiveError as exc:
            raise CommandError(f"Live narration failed ({exc}).") from None
        with tempfile.NamedTemporaryFile(dir=output.parent) as temp:
            temp.write(audio.mp3)
            temp.flush()
            os.link(temp.name, output)  # Atomic publication, never overwrites an existing result.
        self.stdout.write(json.dumps(dict(audio.metadata, model=settings.LIVE_EXPLANATION_MODEL,
                                          voice=settings.LIVE_EXPLANATION_VOICE,
                                          source_hash=sha256(text.encode()).hexdigest())))
