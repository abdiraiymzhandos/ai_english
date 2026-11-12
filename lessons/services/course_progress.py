"""Legacy curriculum boundaries and progress, independent of paid entitlement.

IDs remain public curriculum identities: 1–250 Kazakh, 251+ Russian.
Session ``passed_lessons`` used to contain *unlocked* IDs, so it is never
evidence of completion. QuizAttempt.is_passed is the durable completion flag.
"""
from ..models import Lesson, QuizAttempt


FREE_LESSON_IDS = frozenset({1, 2, 3, 251, 252, 253})
STAGE_TITLES = ("Beginner", "Elementary", "Pre-Intermediate", "Intermediate", "Upper-Intermediate")


def passed_lesson_ids(request):
    if not hasattr(request, "_passed_lesson_ids"):
        identity = str(request.user.pk) if request.user.is_authenticated else request.session.session_key
        request._passed_lesson_ids = set(
            QuizAttempt.objects.filter(user_id=identity, is_passed=True)
            .values_list("lesson_id", flat=True)
        ) if identity else set()
    return request._passed_lesson_ids


def unlocked_lesson_ids(passed, lesson_ids=()):
    kz = max((pk for pk in passed if 1 <= pk <= 250), default=0)
    ru = max((pk for pk in passed if pk >= 251), default=250)
    unlocked = set(range(1, min(kz + 1, 250) + 1)) | set(range(251, ru + 2))
    # Keep the next existing lesson available if an authored ID is missing.
    for lower, upper in ((kz, 250), (ru, float('inf'))):
        following = [pk for pk in lesson_ids if lower < pk <= upper]
        if following:
            unlocked.add(min(following))
    return unlocked


def lesson_access_denial(request, lesson):
    if lesson.pk in FREE_LESSON_IDS:
        return None
    profile = getattr(request.user, "profile", None)
    paid = bool(profile and profile.has_paid_lesson_access())
    if not request.user.is_authenticated or (not paid and (lesson.pk < 251 or (profile and profile.is_teacher()))):
        return "payment_required"
    if lesson.pk not in unlocked_lesson_ids(passed_lesson_ids(request)):
        previous = Lesson.objects.filter(pk__lt=lesson.pk, pk__gte=251 if lesson.pk >= 251 else 1)
        previous_id = previous.order_by('-pk').values_list('pk', flat=True).first()
        if previous_id is not None and previous_id not in passed_lesson_ids(request):
            return "lesson_locked"
    return None


def next_lesson_id(lesson):
    lessons = Lesson.objects.filter(pk__gt=lesson.pk)
    if lesson.pk < 251:
        lessons = lessons.filter(pk__lte=250)
    return lessons.order_by("pk").values_list("pk", flat=True).first()


def course_stages(passed):
    stages = [{"title": title, "lessons": []} for title in STAGE_TITLES]
    for lesson in Lesson.objects.filter(pk__range=(1, 250)).only("id", "title").order_by("pk"):
        stages[(lesson.pk - 1) // 50]["lessons"].append(lesson)
    for stage in stages:
        total = len(stage["lessons"])
        count = sum(lesson.pk in passed for lesson in stage["lessons"])
        stage["progress"] = {"total": total, "passed": count, "percentage": int(count * 100 / total) if total else 0}
    return stages
