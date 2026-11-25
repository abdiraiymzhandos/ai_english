"""Durable single-flight generation and atomic publication for private Live previews."""
from datetime import timedelta
from hashlib import sha256
import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.db.models import F, Prefetch
from django.utils import timezone
from openai import OpenAI

from english_course.utils.live_tts import (MAX_CHARS, JobTrace, LiveError, SilentNarration,
                                           script_info, synthesize_audio_live_mp3)
from lessons.models import Explanation, ExplanationPublication, LiveExplanation, LiveExplanationReview
from .explanation_publication import publication_slot
from .explanation_text import TEXT_MODEL, IncompleteExplanation, build_explanation_prompt, generate_explanation_text

logger = logging.getLogger(__name__)
BUSY = ("queued", "running")
QUEUE_TTL = timedelta(minutes=10)
RUN_TTL = timedelta(minutes=12)
MAX_PROMPT_CHARS = 24000


def previews():
    return LiveExplanation.objects.defer("mp3", "pending_input", "retry_text").prefetch_related(Prefetch(
        "reviews", queryset=LiveExplanationReview.objects.exclude(archived_validated=True).defer("mp3").order_by("-pk")[:1],
        to_attr="latest_reviews"))


def enqueue(lesson, section, mode, job):
    if mode == "comparison":
        source = Explanation.objects.filter(lesson=lesson, section=section).values_list("text", flat=True).first()
        if not source or not source.strip() or len(source) > MAX_CHARS:
            raise ValueError("Салыстыруға жарамды сақталған мәтін жоқ немесе мәтін тым ұзын.")
    elif mode == "retry":
        row = previews().filter(lesson=lesson, section=section).first()
        if not row or not row.retry_metadata or row.retry_metadata["characters"] > MAX_CHARS:
            raise ValueError("Аудионы қайта жасауға жарамды Live мәтіні жоқ.")
        source = F("retry_text")  # Snapshot the current text in the same write that admits the job.
    else:
        source = build_explanation_prompt(lesson, section)
        if len(source) > MAX_PROMPT_CHARS:
            raise ValueError("Сабақ мәтіні тым ұзын.")
    if mode != "retry":
        row, _ = previews().get_or_create(lesson=lesson, section=section)
    if row.revision == job or row.reviews.filter(job=job).exists():
        return row
    now = timezone.now()
    # A single conditional UPDATE is the admission/claim boundary on SQLite and MySQL.
    slot = publication_slot(lesson, section)
    with transaction.atomic():
        admitted = LiveExplanation.objects.filter(pk=row.pk).exclude(job=job).exclude(
            status__in=BUSY, deadline__gt=now,
        ).update(status="queued", job=job, pending_input=source, pending_mode=mode, deadline=now + QUEUE_TTL)
        if admitted:
            slot.update(intent=job)
    return previews().get(pk=row.pk)


def execute_next():
    if not settings.LIVE_EXPLANATIONS_ENABLED:
        return False
    now = timezone.now()
    LiveExplanation.objects.filter(status__in=BUSY, deadline__lte=now).update(
        status="failed", pending_input="", deadline=None)
    candidate = LiveExplanation.objects.filter(status="queued", deadline__gt=now).order_by("deadline").values(
        "pk", "job").first()
    if not candidate:
        return False
    current = LiveExplanation.objects.filter(**candidate)
    if not current.filter(status="queued", deadline__gt=timezone.now()).update(
            status="running", deadline=now + RUN_TTL):
        return False
    running = current.filter(status="running")
    trace = JobTrace(candidate["job"])
    try:
        row = running.defer("mp3", "retry_text").get()
        text = row.pending_input
        if row.pending_mode == "fresh":
            trace("astra_started", model=TEXT_MODEL)
            with OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=45) as client:
                text = generate_explanation_text(text, client, allow_empty_fallback=False)
            info = script_info(text)
            trace("astra_completed", **info)
            if not info["words"]:
                raise LiveError("empty Astra script")
            info.update(job=str(row.job), model=TEXT_MODEL, generated_at=timezone.now().isoformat())
            if not running.filter(deadline__gt=timezone.now()).update(retry_text=text, retry_metadata=info):
                return True
        trace("source_ready", mode=row.pending_mode, **script_info(text))
        model, voice = settings.LIVE_EXPLANATION_MODEL, settings.LIVE_EXPLANATION_VOICE
        result = async_to_sync(synthesize_audio_live_mp3)(
            text, api_key=settings.OPENAI_API_KEY, model=model, voice=voice,
            system_instructions=settings.LIVE_EXPLANATION_INSTRUCTIONS, trace=trace,
            nudge_seconds=settings.LIVE_STARTUP_NUDGE_SECONDS, startup_deadline=settings.LIVE_STARTUP_DEADLINE_SECONDS)
        publish = running.filter(deadline__gt=timezone.now())
        recording = dict(text=text, mp3=result.mp3, model=model, voice=voice,
                         metadata=result.metadata, mode=row.pending_mode)
        if result.validated:
            # The job claim owns this revision. Start the SQLite transaction with the conditional
            # write so concurrent readers/writers cannot invalidate a read-to-write upgrade.
            previous = publish.exclude(revision=None).values(
                "revision", "text", "mp3", "model", "voice", "metadata", "mode").first()
            with transaction.atomic():
                saved = publish.update(**recording, source_hash=sha256(text.encode()).hexdigest(), revision=row.job,
                                       published_at=timezone.now(), status="ready", pending_input="", deadline=None)
                if saved:
                    ExplanationPublication.objects.filter(lesson_id=row.lesson_id, section=row.section,
                        intent=row.job).update(live_revision=row.job, live_text=text)
                if saved and previous:
                    previous_job = previous.pop("revision")
                    LiveExplanationReview.objects.create(explanation_id=row.pk, job=previous_job,
                                                         archived_validated=True, **previous)
        else:
            # A stale worker cannot publish, and a failed insert rolls the state transition back.
            with transaction.atomic():
                if publish.update(status="review", pending_input="", deadline=None):
                    LiveExplanationReview.objects.create(explanation_id=row.pk, job=row.job, **recording)
    except Exception as exc:
        trace("job_failed", reason=str(exc) if isinstance(exc, (LiveError, IncompleteExplanation)) else type(exc).__name__)
        logger.warning("Live explanation job %s failed (%s)", candidate["job"], str(exc) if isinstance(exc, LiveError) else type(exc).__name__)
        running.update(status="silent" if isinstance(exc, SilentNarration) else "failed",
                       pending_input="", deadline=None)
    return True
