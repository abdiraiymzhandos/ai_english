from hashlib import sha256
import re
from uuid import UUID, uuid4

from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from english_course.utils.live_tts import MAX_CHARS

from .services.course_progress import lesson_access_denial
from .services.explanation_publication import playable_mp3, publication_slot, realtime_path
from .models import ExplanationPublication, Explanation, Lesson, LiveExplanation, LiveExplanationReview
from .services.live_explanations import BUSY, enqueue, previews


def enabled_for(user):
    return settings.LIVE_EXPLANATIONS_ENABLED and user.is_active and user.is_superuser


def check_access(request, section):
    if not settings.LIVE_EXPLANATIONS_ENABLED or section not in dict(Explanation.SECTION_CHOICES):
        raise Http404
    if not enabled_for(request.user):
        return JsonResponse({"error": "Рұқсат жоқ."}, status=403)


TERMINATION_LABELS = {
    "startup_silence_timeout": "Сеанс басталғанда дыбыс шықпады",
    "close_requested": "Сеанс жабылды",
    "incomplete_narration": "Оқу аяқталмай, дыбыс тоқтады",
    "generation_timeout": "Генерация уақыты аяқталды",
    "finalization_timeout": "Сеансты жабу уақыты аяқталды",
    "connection_lost": "Байланыс үзілді",
    "remote_hangup": "Провайдер байланысты жапты",
    "expired": "Сеанс мерзімі аяқталды",
    "session_closed": "Сеанс аяқталды",
    "audio_limit": "Аудио ұзақтығының шегіне жетті",
    "invalid_stream_event": "Сеанстан жарамсыз жауап келді",
    "invalid_audio_chunk": "Аудио ағыны үзілді",
    "provider_error": "Провайдер қатесі",
}


def recording_data(take, audio_url):
    meta = take.metadata
    reason = meta.get("termination_reason")
    measurements = {key: meta[key] for key in ("input_frames", "output_chunks", "pcm_peak", "pcm_rms",
                    "first_signal_seconds", "non_silent_seconds", "instruction_state") if meta.get(key) is not None}
    return dict(measurements=measurements, text=take.text, model=take.model, voice=take.voice, mode=take.mode, audio_url=audio_url,
                source_hash=sha256(take.text.encode()).hexdigest(), usage_seconds=meta.get("usage_seconds"),
                transcript=meta.get("transcript"), coverage_percent=meta.get("coverage_percent"),
                audio_seconds=meta.get("audio_seconds"), termination_reason=reason,
                termination_label=TERMINATION_LABELS.get(reason))


def review_data(review, lesson_id, section):
    route = "live_audio" if review.archived_validated else "live_review_audio"
    data = recording_data(review, reverse(route, args=[lesson_id, section, review.job]))
    if review.archived_validated:
        data["revision"] = str(review.job)
    data["created_at"] = review.created_at.isoformat()
    return data


def preview_data(row, slot=None):
    if not row:
        return {"status": "idle"}
    status = row.status
    if status in BUSY and row.deadline <= timezone.now():
        status = "failed"
    data = {"status": status, "can_retry": bool(row.retry_metadata and row.retry_metadata["characters"] <= MAX_CHARS)}
    data["published_revision"] = str(slot.live_revision) if slot and slot.live_revision else None
    if row.revision:
        data["revision"] = str(row.revision)
        data.update(recording_data(row, reverse("live_audio", args=[row.lesson_id, row.section, row.revision])))
    if row.latest_reviews:
        review = row.latest_reviews[0]
        data["review"] = review_data(review, row.lesson_id, row.section)
    return data


@never_cache
@require_http_methods(["GET", "POST"])
def preview(request, lesson_id, section):
    denied = check_access(request, section)
    if denied is not None:
        return denied
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    slot = ExplanationPublication.objects.filter(lesson=lesson, section=section)
    if request.method == "GET":
        if request.GET.get("reviews") == "1":
            reviews = LiveExplanationReview.objects.filter(explanation__lesson=lesson,
                explanation__section=section).defer("mp3").order_by("-pk")
            return JsonResponse({"reviews": [review_data(item, lesson_id, section) for item in reviews]})
        return JsonResponse(preview_data(previews().filter(lesson=lesson, section=section).first(), slot.first()))
    try:
        job = UUID(request.POST.get("job", ""))
    except ValueError:
        return JsonResponse({"error": "Сұрау жарамсыз."}, status=400)
    mode = request.POST.get("mode", "fresh")
    if mode not in ("fresh", "comparison", "retry"):
        return JsonResponse({"error": "Мәтін көзі жарамсыз."}, status=400)
    try:
        row = enqueue(lesson, section, mode, job)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(preview_data(row, slot.first()), status=202 if row.status in BUSY else 200)


@never_cache
@require_http_methods(["GET", "HEAD"])
def audio(request, lesson_id, section, revision, review=False):
    denied = check_access(request, section)
    if denied is not None:
        return denied
    # Safari/WebView players may request only part of an MP3. Each version is immutable.
    history = LiveExplanationReview.objects.filter(explanation__lesson_id=lesson_id,
                                                 explanation__section=section, job=revision)
    if review:
        raw = history.exclude(archived_validated=True).values_list("mp3", flat=True).first()
    else:
        raw = LiveExplanation.objects.filter(lesson_id=lesson_id, section=section,
                                             revision=revision).values_list("mp3", flat=True).first()
        if raw is None:
            raw = history.filter(archived_validated=True).values_list("mp3", flat=True).first()
    return mp3_response(request, raw)


def mp3_response(request, raw):
    if not raw:
        raise Http404
    size = len(raw)
    start, end = 0, size - 1
    partial = request.headers.get("Range")
    if partial:
        match = re.fullmatch(r"bytes=(\d{0,12})-(\d{0,12})", partial)
        if match and any(match.groups()):
            left, right = match.groups()
            start = int(left) if left else max(0, size - int(right))
            end = min(end, int(right)) if left and right else end
        else:
            start = size
        if start > end:
            return HttpResponse(status=416, headers={"Content-Range": f"bytes */{size}"})
    response = HttpResponse(raw[start:end+1] if request.method == "GET" else b"",
                            status=206 if partial else 200, content_type="audio/mpeg")
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = end - start + 1
    response["Content-Disposition"] = 'inline; filename="explanation.mp3"'
    if partial:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    return response

@never_cache
@require_http_methods(["GET", "HEAD"])
def published_audio(request, lesson_id, section, revision):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    if lesson_access_denial(request, lesson):
        return HttpResponse(status=403)
    # Include the publication predicate in each byte query, including archived validated takes.
    allowed = ExplanationPublication.objects.filter(lesson=lesson, section=section,
                                                   live_revision=revision).values("lesson_id")
    raw = LiveExplanation.objects.filter(lesson_id__in=allowed, section=section,
                                         revision=revision).values_list("mp3", flat=True).first()
    if raw is None:
        raw = LiveExplanationReview.objects.filter(explanation__lesson_id__in=allowed, explanation__section=section,
                    job=revision, archived_validated=True).values_list("mp3", flat=True).first()
    return mp3_response(request, raw)


def realtime_file(lesson_id, section, url):
    legacy = re.fullmatch(rf"/media/audio_lesson_{int(lesson_id)}_{re.escape(section)}_[\w-]+\.mp3", url)
    if legacy:
        return Path(settings.MEDIA_ROOT) / url.rsplit("/", 1)[1]
    try:
        revision = UUID(url.rsplit("/", 1)[-1].removesuffix(".mp3"))
    except ValueError:
        return None
    if url == reverse("realtime_explanation_audio", args=[lesson_id, section, revision]):
        return realtime_path(revision)


@never_cache
@require_http_methods(["GET", "HEAD"])
def realtime_audio(request, lesson_id, section, revision):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    admin = request.user.is_active and request.user.is_superuser
    if not admin and lesson_access_denial(request, lesson):
        return HttpResponse(status=403)
    recordings = Explanation.objects.filter(lesson=lesson, section=section, audio_url=request.path)
    if not admin:
        recordings = recordings.exclude(lesson_id__in=ExplanationPublication.objects.filter(
            lesson=lesson, section=section, live_revision__isnull=False).values("lesson_id"))
    if not recordings.exists():
        raise Http404
    path = realtime_file(lesson.pk, section, request.path)
    if path is None or not path.is_file():
        raise Http404
    return mp3_response(request, path.read_bytes())


@never_cache
@require_http_methods(["POST"])
def select_publication(request, lesson_id, section):
    denied = check_access(request, section)
    if denied is not None:
        return denied
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    revision = request.POST.get("revision")
    selected_url = request.POST.get("audio_url", "")
    if revision:
        try:
            revision = UUID(revision)
        except ValueError:
            raise Http404
        recording = LiveExplanation.objects.filter(lesson=lesson, section=section, revision=revision
                                                   ).values("text", "mp3").first()
        if recording is None:
            recording = get_object_or_404(
                LiveExplanationReview.objects.values("text", "mp3"), explanation__lesson=lesson,
                explanation__section=section, job=revision, archived_validated=True)
        text, raw = recording["text"], recording["mp3"]
    else:
        get_object_or_404(Explanation.objects.only("id"), lesson=lesson, section=section, audio_url=selected_url)
        path = realtime_file(lesson_id, section, selected_url)
        raw = path.read_bytes() if path and path.is_file() else None
        text = ""
    if not playable_mp3(raw):
        return JsonResponse({"error": "Жазба қолжетімсіз."}, status=409)

    slot = publication_slot(lesson, section)
    with transaction.atomic():
        # Validated Live UUIDs are immutable, including after archival. Realtime's row is replaceable.
        slot.update(intent=uuid4(), live_revision=revision or None, live_text=text)
        if not revision:
            get_object_or_404(Explanation.objects.only("id"), lesson=lesson, section=section, audio_url=selected_url)
    return JsonResponse({"published_revision": str(revision) if revision else None})
