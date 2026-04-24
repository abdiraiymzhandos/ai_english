import json
import logging
import mimetypes
import os

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms_classroom import ClassGroupForm, ClassStudentForm, StudentPhotoForm, ClassroomSessionSelectForm
from .models import ClassGroup, ClassStudent, StudentPhoto, Lesson

logger = logging.getLogger(__name__)

REALTIME_MODEL = "gpt-realtime"
VOICE_EMBEDDING_SIZE = 13
VOICE_EMBEDDING_LIMIT = 5


def _is_teacher(user):
    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_use_classroom_teacher_features())


def _require_teacher(request):
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Authentication required")
    if not _is_teacher(request.user):
        return HttpResponseForbidden("Teacher access required")
    return None


def _require_teacher_voice_access(request):
    guard = _require_teacher(request)
    if guard:
        return guard
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.can_run_classroom_voice_sessions():
        return HttpResponseForbidden("Voice access required")
    return None


def _classroom_instructions(lesson: Lesson, group: ClassGroup) -> str:
    student_names = list(group.students.values_list("full_name", flat=True))
    student_list = ", ".join(student_names) if student_names else ""
    student_count = len(student_names)
    school_label = group.school_name or "Unknown school"

    lessons_data = (
        f"Lesson {lesson.id}: {lesson.title}\n"
        f"Vocabulary: {lesson.vocabulary}\n"
        f"Content: {lesson.content}\n"
        f"Grammar: {lesson.grammar}\n"
        f"Dialogue: {lesson.dialogue}\n"
    )

    return (
        "You are a real English teacher teaching a live classroom lesson to school students. "
        "Teach like a calm, structured, supportive professional teacher, not like a chatbot and not like a rapid practice bot. "
        "Speak mainly in Kazakh, with short English examples from the lesson materials. "
        "Your job is to teach the lesson step by step in a natural classroom order.\n\n"

        f"School: {school_label}. Class: {group.name}. Students: {student_count}.\n"
        + (f"Student list: {student_list}\n\n" if student_list else "\n")
        + lessons_data
        + "\n"

        "Teaching instructions:\n"
        "- Start the lesson naturally: greet the class and briefly introduce today's lesson.\n"
        "- Teach in this order: introduction -> vocabulary -> content/dialogue -> grammar -> guided practice -> short speaking practice -> short review.\n"
        "- Do not jump straight into questioning students before teaching the material.\n"
        "- First teach all vocabulary clearly before moving on.\n"
        "- Do not skip vocabulary items. Teach every vocabulary word from the lesson.\n"
        "- For each vocabulary word, give: the English word, the Kazakh meaning, and one short simple example sentence.\n"
        "- Keep the example sentence short, clear, and easy for students.\n"
        "- After vocabulary, teach the main content and dialogue and explain the meaning simply.\n"
        "- When teaching the content or dialogue, briefly explain important grammar or sentence patterns if they help students understand the lesson better, but keep it short and natural.\n"
        "- Then teach the grammar point briefly and clearly using examples from the lesson.\n"
        "- Only after teaching the material, move into guided practice and short questions.\n"
        "- Use the dialogue as practice only after students understand the vocabulary and grammar.\n"
        "- Ask short, level-appropriate questions and wait for answers.\n"
        "- If students struggle, help them by simplifying, giving hints, or starting the sentence for them.\n"
        "- Correct gently and encourage participation.\n"
        "- Keep sentences short, audio-friendly, and classroom-appropriate.\n"
        "- Stay focused on the provided lesson material and do not go far beyond it.\n"
        "- Finish with a short review of what was learned.\n\n"

        "Speaking and interruption rules:\n"
        "- Do not react to random background sounds, short noise, unclear speech, or side conversations.\n"
        "- Do not interrupt your own teaching because of small sounds or uncertain voice activity.\n"
        "- Continue speaking normally unless there is a clear student response, a clear teacher-directed classroom event, or a clear pause for student participation.\n"
        "- If a sound is unclear, ignore it and continue the lesson naturally.\n"
        "- Do not stop your explanation after every small sound.\n"
        "- Only switch from teaching mode to response mode when a student response is clear and relevant.\n"
        "- If there is no clear answer after a short pause, encourage once, simplify if needed, then continue the lesson.\n"
        "- Keep control of the classroom flow like a real teacher.\n\n"

        "Classroom behavior rules:\n"
        "- Call a student by name only when prompted by classroom events or when clearly appropriate.\n"
        "- Attendance and system updates are silent by default.\n"
        "- Do not mention hidden technical events, confidence scores, or system behavior.\n"
        "- If time updates arrive, adjust pacing so the lesson finishes smoothly.\n\n"

        "When you receive a message starting with 'EVENT:', follow it as a control command.\n"
        "EVENT: HAND_RAISE name=<StudentName> -> Address that student by name and ask one short lesson-related question.\n"
        "EVENT: CONFIRM_STUDENT candidate=<StudentName> -> Ask the student to confirm their name briefly.\n"
        "EVENT: TIME_REMAINING minutes=<m> seconds=<s> -> Adjust pacing to finish on time.\n"
        "EVENT: ATTENDANCE present=<names> missing=<names> -> Update attendance silently only.\n"
        "EVENT: ROLL_CALL -> Ask students to say their names briefly.\n"
        "EVENT: VOICE_DETECTED name=<StudentName> -> Treat that student as the likely speaker only if the student response is clear enough to continue naturally.\n"
    )


def _serialize_group_summary(group: ClassGroup) -> dict:
    students = list(group.students.all())
    student_count = len(students)
    photo_ready_count = 0
    voice_ready_count = 0
    demo_ready_count = 0

    for student in students:
        photo_count = len(student.photos.all())
        voice_count = len(student.voice_embeddings or [])
        has_photo = photo_count > 0
        has_voice = voice_count > 0
        if has_photo:
            photo_ready_count += 1
        if has_voice:
            voice_ready_count += 1
        if has_photo and has_voice:
            demo_ready_count += 1

    return {
        "group": group,
        "student_count": student_count,
        "photo_ready_count": photo_ready_count,
        "voice_ready_count": voice_ready_count,
        "demo_ready_count": demo_ready_count,
    }


@login_required
def classroom_dashboard(request):
    guard = _require_teacher(request)
    if guard:
        return guard

    groups = (
        ClassGroup.objects
        .filter(teacher=request.user)
        .prefetch_related("students__photos")
    )
    group_cards = [_serialize_group_summary(group) for group in groups]
    summary = {
        "groups_count": len(group_cards),
        "students_count": sum(card["student_count"] for card in group_cards),
        "photo_ready_count": sum(card["photo_ready_count"] for card in group_cards),
        "voice_ready_count": sum(card["voice_ready_count"] for card in group_cards),
        "demo_ready_count": sum(card["demo_ready_count"] for card in group_cards),
    }
    return render(request, "lessons/classroom/dashboard.html", {
        "group_cards": group_cards,
        "summary": summary,
    })


@login_required
def classroom_group_create(request):
    guard = _require_teacher(request)
    if guard:
        return guard

    if request.method == "POST":
        form = ClassGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.teacher = request.user
            group.save()
            return redirect("classroom_group_detail", group_id=group.id)
    else:
        form = ClassGroupForm()

    return render(request, "lessons/classroom/group_form.html", {"form": form})


@login_required
def classroom_group_detail(request, group_id):
    guard = _require_teacher(request)
    if guard:
        return guard

    group = get_object_or_404(
        ClassGroup.objects.prefetch_related("students__photos"),
        id=group_id,
        teacher=request.user,
    )
    students = list(group.students.all())
    student_cards = []
    for student in students:
        photo_count = len(student.photos.all())
        voice_count = len(student.voice_embeddings or [])
        student_cards.append({
            "student": student,
            "photo_count": photo_count,
            "voice_count": voice_count,
            "has_photo": photo_count > 0,
            "has_voice": voice_count > 0,
        })
    return render(request, "lessons/classroom/group_detail.html", {
        "group": group,
        "student_cards": student_cards,
        "group_summary": _serialize_group_summary(group),
    })


@login_required
def classroom_group_edit(request, group_id):
    guard = _require_teacher(request)
    if guard:
        return guard

    group = get_object_or_404(ClassGroup, id=group_id, teacher=request.user)

    if request.method == "POST":
        form = ClassGroupForm(request.POST, instance=group)
        form.fields["name"].disabled = True
        if form.is_valid():
            form.save()
            return redirect("classroom_group_detail", group_id=group.id)
    else:
        form = ClassGroupForm(instance=group)
        form.fields["name"].disabled = True

    return render(request, "lessons/classroom/group_form.html", {
        "form": form,
        "group": group,
        "is_edit": True,
    })


@login_required
def classroom_student_create(request, group_id):
    guard = _require_teacher(request)
    if guard:
        return guard

    group = get_object_or_404(ClassGroup, id=group_id, teacher=request.user)

    if request.method == "POST":
        student_form = ClassStudentForm(request.POST)
        photo_form = StudentPhotoForm(request.POST, request.FILES)
        if student_form.is_valid() and photo_form.is_valid():
            student = student_form.save(commit=False)
            student.group = group
            student.save()

            images = photo_form.cleaned_data.get("image") or []
            for image in images:
                StudentPhoto.objects.create(student=student, image=image)

            return redirect("classroom_group_detail", group_id=group.id)
    else:
        student_form = ClassStudentForm()
        photo_form = StudentPhotoForm()

    return render(request, "lessons/classroom/student_form.html", {
        "group": group,
        "student_form": student_form,
        "photo_form": photo_form,
    })


@login_required
def classroom_student_add_photo(request, student_id):
    guard = _require_teacher(request)
    if guard:
        return guard

    student = get_object_or_404(ClassStudent, id=student_id, group__teacher=request.user)

    if request.method == "POST":
        photo_form = StudentPhotoForm(request.POST, request.FILES)
        if photo_form.is_valid():
            images = photo_form.cleaned_data.get("image") or []
            for image in images:
                StudentPhoto.objects.create(student=student, image=image)
            return redirect("classroom_group_detail", group_id=student.group.id)
    else:
        photo_form = StudentPhotoForm()

    return render(request, "lessons/classroom/student_photo_form.html", {
        "student": student,
        "photo_form": photo_form,
    })


@login_required
def classroom_student_delete(request, student_id):
    guard = _require_teacher(request)
    if guard:
        return guard

    student = get_object_or_404(ClassStudent, id=student_id, group__teacher=request.user)
    group_id = student.group.id
    if request.method == "POST":
        student.delete()
        return redirect("classroom_group_detail", group_id=group_id)

    return render(request, "lessons/classroom/student_delete.html", {"student": student})


@login_required
def classroom_session_select(request):
    guard = _require_teacher_voice_access(request)
    if guard:
        return guard

    initial = {}
    group_id = request.GET.get("group_id")
    if group_id:
        try:
            group = ClassGroup.objects.get(id=group_id, teacher=request.user)
            initial["group"] = group
        except ClassGroup.DoesNotExist:
            pass

    groups = (
        ClassGroup.objects
        .filter(teacher=request.user)
        .prefetch_related("students__photos")
    )
    group_cards = [_serialize_group_summary(group) for group in groups]

    if request.method == "POST":
        form = ClassroomSessionSelectForm(request.user, request.POST, initial=initial)
        if form.is_valid():
            group = form.cleaned_data["group"]
            lesson = form.cleaned_data["lesson"]
            return redirect("classroom_session", group_id=group.id, lesson_id=lesson.id)
    else:
        form = ClassroomSessionSelectForm(request.user, initial=initial)

    selected_group = initial.get("group")
    return render(request, "lessons/classroom/session_select.html", {
        "form": form,
        "group_cards": group_cards,
        "groups_count": len(group_cards),
        "lessons_count": form.fields["lesson"].queryset.count(),
        "selected_group_id": getattr(selected_group, "id", None),
    })


@login_required
def classroom_session(request, group_id, lesson_id):
    guard = _require_teacher_voice_access(request)
    if guard:
        return guard

    group = get_object_or_404(ClassGroup, id=group_id, teacher=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id)

    roster = []
    for student in group.students.prefetch_related("photos"):
        photos = list(student.photos.all())
        photo_urls = [reverse("classroom_student_photo", args=[photo.id]) for photo in photos]
        photo_url = photo_urls[0] if photo_urls else ""
        voice_embeddings = student.voice_embeddings or []
        roster.append({
            "id": student.id,
            "name": student.full_name,
            "photo_url": photo_url,
            "photos": photo_urls,
            "photo_count": len(photo_urls),
            "voice_embeddings": voice_embeddings,
            "voice_count": len(voice_embeddings),
        })

    session_summary = {
        "total_students": len(roster),
        "photo_ready_count": sum(1 for item in roster if item["photo_count"] > 0),
        "voice_ready_count": sum(1 for item in roster if item["voice_count"] > 0),
        "demo_ready_count": sum(1 for item in roster if item["photo_count"] > 0 and item["voice_count"] > 0),
        "missing_photo_count": sum(1 for item in roster if item["photo_count"] == 0),
        "missing_voice_count": sum(1 for item in roster if item["voice_count"] == 0),
    }

    return render(request, "lessons/classroom/session.html", {
        "group": group,
        "lesson": lesson,
        "roster": roster,
        "session_summary": session_summary,
    })


@login_required
def classroom_student_photo(request, photo_id):
    guard = _require_teacher(request)
    if guard:
        return guard

    photo = get_object_or_404(StudentPhoto, id=photo_id, student__group__teacher=request.user)
    if not photo.image:
        return HttpResponseBadRequest("Photo missing")

    content_type, _ = mimetypes.guess_type(photo.image.name)
    response = FileResponse(photo.image.open("rb"), content_type=content_type or "image/jpeg")
    response["Content-Disposition"] = "inline"
    return response


@require_POST
@login_required
def classroom_student_voice_embedding(request, student_id):
    guard = _require_teacher(request)
    if guard:
        return guard

    student = get_object_or_404(ClassStudent, id=student_id, group__teacher=request.user)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except ValueError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    embedding = payload.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        return JsonResponse({"error": "Invalid embedding"}, status=400)

    sanitized = []
    for value in embedding:
        if isinstance(value, (int, float)):
            sanitized.append(float(value))
    if len(sanitized) < VOICE_EMBEDDING_SIZE:
        return JsonResponse({"error": "Embedding must include enough numeric values"}, status=400)

    sanitized = sanitized[:VOICE_EMBEDDING_SIZE]

    embeddings = []
    for sample in student.voice_embeddings or []:
        if not isinstance(sample, list):
            continue
        cleaned = [float(value) for value in sample if isinstance(value, (int, float))]
        if len(cleaned) >= VOICE_EMBEDDING_SIZE:
            embeddings.append(cleaned[:VOICE_EMBEDDING_SIZE])

    signature = tuple(round(value, 5) for value in sanitized)
    if any(tuple(round(value, 5) for value in sample) == signature for sample in embeddings):
        return JsonResponse({"ok": True, "count": len(embeddings), "duplicate": True})

    embeddings.append(sanitized)
    if len(embeddings) > VOICE_EMBEDDING_LIMIT:
        embeddings = embeddings[-VOICE_EMBEDDING_LIMIT:]

    student.voice_embeddings = embeddings
    student.save(update_fields=["voice_embeddings"])

    return JsonResponse({"ok": True, "count": len(embeddings)})


@csrf_exempt
@require_POST
@login_required
def mint_realtime_classroom_token(request, lesson_id, group_id):
    guard = _require_teacher_voice_access(request)
    if guard:
        return guard

    api_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        return HttpResponseBadRequest("OpenAI API key missing")

    lesson = get_object_or_404(Lesson, id=lesson_id)
    group = get_object_or_404(ClassGroup, id=group_id, teacher=request.user)

    payload = {
        "model": REALTIME_MODEL,
        "modalities": ["audio", "text"],
        "voice": "cedar",
        "turn_detection": {"type": "server_vad"},
        "instructions": _classroom_instructions(lesson, group),
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "realtime=v1",
            },
            json=payload,
            timeout=20,
        )
        if response.status_code >= 400:
            try:
                err_payload = response.json()
            except ValueError:
                err_payload = {"error": response.text}
            logger.error(
                "OpenAI realtime session error %s for classroom lesson %s: %s",
                response.status_code,
                lesson_id,
                err_payload,
            )
            return JsonResponse({"error": "OpenAI realtime session error", "details": err_payload}, status=502)
    except requests.RequestException as exc:
        logger.exception("Failed to mint classroom realtime session token for lesson %s", lesson_id)
        return JsonResponse({"error": "OpenAI realtime session error", "details": str(exc)}, status=502)

    try:
        data = response.json()
    except ValueError as exc:
        logger.exception("Invalid JSON from OpenAI realtime session: %s", exc)
        return JsonResponse({"error": "Invalid response from OpenAI"}, status=502)

    return JsonResponse(data)
