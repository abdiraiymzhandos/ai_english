"""Lesson-bound questions and isolated runs; historical completion is monotonic."""
import hashlib
import json
import random
import re
import uuid

from ..models import QuizQuestion


class QuizContentError(ValueError):
    pass


def vocabulary_pairs(lesson):
    pairs = []
    for line in lesson.vocabulary.splitlines():
        if not line.strip():
            continue
        parts = re.split(r"\s*[–—]\s*|\s+-\s+", line.strip(), maxsplit=1)
        if len(parts) != 2 or not all(parts) or len(parts[0]) > 100 or len(parts[1]) > 255:
            raise QuizContentError("Сабақ сөздігінің пішімін тексеру қажет.")
        pair = tuple(part.strip() for part in parts)
        if pair not in pairs:
            pairs.append(pair)
    if len(pairs) < 4:
        raise QuizContentError("Бұл сабақта жеткілікті сөздер жоқ!")
    return pairs


def vocabulary_digest(pairs):
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False).encode("utf-8")).hexdigest()


def prepare_questions(lesson, pairs):
    """Caller locks the lesson row. Keep old rows/answers as historical evidence.

    Only exact pairs in this lesson's current vocabulary can be served. Reuse
    the first matching row if legacy generation created duplicate rows.
    """
    existing = {}
    for question in lesson.quiz_questions.order_by("pk"):
        existing.setdefault((question.english_word, question.kazakh_translation), question)
    missing = [QuizQuestion(lesson=lesson, english_word=word, kazakh_translation=meaning)
               for word, meaning in pairs if (word, meaning) not in existing]
    if missing:
        # Reload after bulk_create: MySQL may not return inserted primary keys.
        QuizQuestion.objects.bulk_create(missing)
        for question in lesson.quiz_questions.order_by("pk"):
            existing.setdefault((question.english_word, question.kazakh_translation), question)
    return [existing[pair] for pair in pairs]


def reset_run(attempt):
    attempt.answers.all().delete()
    attempt.attempt_token = uuid.uuid4()
    attempt.score = 0
    attempt.attempts = 0
    attempt.completed = False


def bind_questions(attempt, questions, digest):
    ids = [question.pk for question in questions]
    changed = bool(attempt.vocabulary_hash and (attempt.vocabulary_hash != digest or attempt.question_ids != ids))
    if changed:
        reset_run(attempt)
    elif not attempt.vocabulary_hash and not attempt.completed:
        # Retain valid pre-migration answers; stale/foreign answers cannot count.
        attempt.answers.exclude(question_id__in=ids).delete()
    if changed or not attempt.vocabulary_hash:
        attempt.vocabulary_hash = digest
        attempt.question_ids = ids
        attempt.save()


def question_data(questions):
    translations = list(dict.fromkeys(q.kazakh_translation for q in questions))
    data = []
    for question in questions:
        choices = random.sample([word for word in translations if word != question.kazakh_translation], min(3, len(translations) - 1))
        # Never invent a correct translation or borrow from another lesson.
        choices.append(question.kazakh_translation)
        random.shuffle(choices)
        data.append({"id": question.pk, "english_word": question.english_word, "choices": choices})
    return data


def answer_state(attempt):
    answers = list(attempt.answers.filter(question_id__in=attempt.question_ids, question__lesson_id=attempt.lesson_id)
                   .values_list("question_id", "is_correct"))
    ids = {pk for pk, _ in answers}
    score = sum(correct for _, correct in answers)
    return ids, score, len(answers) - score


def state_payload(attempt, *, answers=None, **extra):
    ids, score, mistakes = answers if answers is not None else answer_state(attempt)
    # Legacy completions have aggregate scores but no fabricated answer rows.
    if attempt.completed and not ids:
        score, mistakes = attempt.score, attempt.attempts
    return {
        "lesson_id": attempt.lesson_id,
        "attempt_token": str(attempt.attempt_token),
        "score": score,
        "attempts": mistakes,
        "passed": attempt.completed and attempt.is_passed,
        "lesson_completed": attempt.is_passed,
        "completed": attempt.completed,
        "previous_score": attempt.last_passed_score,
        "previous_total": attempt.last_passed_total,
        "answered_count": len(ids),
        "total_questions": len(attempt.question_ids),
        "already_answered_question_ids": sorted(ids),
        "next_question_id": next((pk for pk in attempt.question_ids if pk not in ids), None),
        **extra,
    }
