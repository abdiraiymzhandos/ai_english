"""The publication slot is scoped to a section. A null revision selects its legacy Realtime row."""
import subprocess
from pathlib import Path

from django.conf import settings
from django.urls import reverse

from lessons.models import ExplanationPublication


def publication_slot(lesson, section):
    row, _ = ExplanationPublication.objects.only("pk").get_or_create(lesson=lesson, section=section)
    return ExplanationPublication.objects.filter(pk=row.pk)


def published_url(lesson_id, section, revision):
    return reverse("published_explanation_audio", args=[lesson_id, section, revision])


def realtime_path(revision):
    return Path(settings.PRIVATE_EXPLANATION_ROOT) / (str(revision) + ".mp3")


def playable_mp3(data):
    if not data:
        return False
    try:
        decoded = subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-f", "mp3", "-i", "pipe:0",
            "-ac", "1", "-ar", "24000", "-f", "s16le", "pipe:1",
        ], input=data, capture_output=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return any(decoded.stdout)
