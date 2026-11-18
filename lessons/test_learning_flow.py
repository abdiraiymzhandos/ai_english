"""Synthetic course regressions; no runtime fixtures or external API calls."""
import json
import os
import statistics
import time
from io import StringIO

from django.contrib.auth.models import User
from django.db import connection
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Lesson, QuizAnswer, QuizAttempt, QuizQuestion, UserProfile


def make_lesson(pk):
    return Lesson.objects.create(
        id=pk, title=f"Lesson {pk}", content="Content", grammar="Grammar",
        dialogue="Dialogue",
        vocabulary="\n".join(f"word{pk}_{i} – meaning{pk}_{i}" for i in range(4)),
    )


class LearningFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner")
        self.profile = UserProfile.objects.create(user=self.user, is_paid=True)
        self.client.force_login(self.user)
        self.lesson = make_lesson(1)
        self.next_lesson = make_lesson(2)

    def start(self, lesson=None, client=None):
        return (client or self.client).get(reverse("start_quiz", args=[(lesson or self.lesson).pk]))

    def submit(self, state, question, answer=None, client=None, lesson=None):
        payload = {"question_id": question.pk, "answer": answer if answer is not None else question.kazakh_translation}
        if "attempt_token" in state:
            payload["attempt_token"] = state["attempt_token"]
        return (client or self.client).post(reverse("submit_answer", args=[(lesson or self.lesson).pk]), payload)

    def complete(self, lesson=None):
        lesson = lesson or self.lesson
        state = self.start(lesson).json()
        for question in lesson.quiz_questions.filter(id__in=[q["id"] for q in state["questions"]]):
            response = self.submit(state, question, lesson=lesson)
            self.assertEqual(response.status_code, 200)
        return response.json()

    def test_beginner_fiftieth_completion_is_100_percent(self):
        for pk in range(3, 51):
            make_lesson(pk)
        QuizAttempt.objects.bulk_create([
            QuizAttempt(user_id=str(self.user.pk), lesson_id=pk, is_passed=True, completed=True)
            for pk in range(1, 50)
        ])
        before = self.client.get(reverse("lesson_list"))
        self.assertEqual(before.context["stages"][0]["progress"]["passed"], 49)
        self.complete(Lesson.objects.get(pk=50))
        after = self.client.get(reverse("lesson_list"))
        self.assertEqual(after.context["stages"][0]["progress"], {"total": 50, "passed": 50, "percentage": 100})

    def test_payment_flag_does_not_erase_completed_progress(self):
        for pk in range(3, 51):
            make_lesson(pk)
        QuizAttempt.objects.bulk_create([
            QuizAttempt(user_id=str(self.user.pk), lesson_id=pk, is_passed=True, completed=True)
            for pk in range(1, 51)
        ])
        self.profile.is_paid = False
        self.profile.save()
        response = self.client.get(reverse("lesson_list"))
        self.assertEqual(response.context["stages"][0]["progress"]["percentage"], 100)
        self.assertRedirects(self.client.get(reverse("lesson_detail", args=[50])), reverse("advertisement"))

    def test_guest_dashboard_refresh_never_fabricates_progress(self):
        guest = Client()
        for _ in range(4):
            response = guest.get(reverse("lesson_list"))
            self.assertEqual(response.context["stages"][0]["progress"]["passed"], 0)

    def test_level_boundaries_do_not_shift_when_a_lesson_is_missing(self):
        Lesson.objects.filter(pk=2).delete()
        for pk in range(3, 52):
            make_lesson(pk)
        response = self.client.get(reverse("lesson_list"))
        ids = [lesson.pk for lesson in response.context["stages"][0]["lessons"]]
        self.assertNotIn(51, ids)

    def test_stale_questions_are_never_served_or_deleted(self):
        stale = QuizQuestion.objects.create(lesson=self.lesson, english_word="unrelated", kazakh_translation="foreign")
        response = self.start()
        self.assertEqual(response.status_code, 200)
        self.assertEqual({q["english_word"] for q in response.json()["questions"]}, {f"word1_{i}" for i in range(4)})
        self.assertTrue(QuizQuestion.objects.filter(pk=stale.pk).exists())

    def test_legacy_pass_keeps_its_saved_score(self):
        QuizAttempt.objects.create(user_id=str(self.user.pk), lesson=self.lesson, is_passed=True, completed=True, score=4)
        response = self.start()
        self.assertTrue(response.json()["passed"])
        self.assertEqual(response.json()["score"], 4)

    def test_track_end_does_not_unlock_other_language(self):
        last = make_lesson(250)
        make_lesson(251)
        QuizAttempt.objects.create(user_id=str(self.user.pk), lesson=make_lesson(249), is_passed=True)
        self.client.get(reverse("lesson_list"))
        state = self.complete(last)
        self.assertIsNone(state["next_lesson"])
        self.profile.refresh_from_db()
        self.assertLessEqual(self.profile.current_lesson, 250)

    def test_retake_resets_current_run_and_failed_retake_preserves_completion(self):
        passed = self.complete()
        response = self.client.post(reverse('restart_quiz', args=[1]), {'attempt_token': passed['attempt_token']})
        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertNotEqual(state['attempt_token'], passed['attempt_token'])
        self.assertEqual((state['score'], state['attempts'], state['answered_count']), (0, 0, 0))
        self.assertFalse(state['passed'])
        self.assertTrue(state['lesson_completed'])
        self.assertEqual(state['previous_score'], 4)
        for question in self.lesson.quiz_questions.all()[:3]:
            response = self.submit(state, question, answer='wrong')
        failed = response.json()
        self.assertTrue(failed['restart_required'])
        self.assertTrue(failed['lesson_completed'])
        attempt = QuizAttempt.objects.get(user_id=str(self.user.pk), lesson=self.lesson)
        self.assertTrue(attempt.is_passed)
        self.assertFalse(attempt.completed)
        self.assertEqual(attempt.last_passed_score, 4)
        self.assertEqual(attempt.answers.count(), 0)
        self.assertIn(2, self.client.get(reverse('lesson_list')).context['passed_lessons'])
        self.assertEqual(QuizAttempt.objects.filter(user_id=str(self.user.pk), is_passed=True).count(), 1)
        self.assertEqual(self.submit(state, self.lesson.quiz_questions.first()).status_code, 409)

    def test_repeated_successful_retakes_do_not_duplicate_progress(self):
        state = self.complete()
        for _ in range(3):
            self.client.post(reverse('restart_quiz', args=[1]), {'attempt_token': state['attempt_token']})
            state = self.complete()
        self.assertEqual(QuizAttempt.objects.filter(is_passed=True, user_id=str(self.user.pk)).count(), 1)
        progress = self.client.get(reverse('lesson_list')).context['stages'][0]['progress']
        self.assertEqual(progress, {'total': 2, 'passed': 1, 'percentage': 50})

    def test_old_answer_and_duplicate_restart_cannot_change_fresh_run(self):
        state = self.start().json()
        url = reverse('restart_quiz', args=[1])
        response = self.client.post(url, {'attempt_token': state['attempt_token']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(url, {'attempt_token': state['attempt_token']}).status_code, 409)
        question = self.lesson.quiz_questions.first()
        self.assertEqual(self.submit(state, question).status_code, 409)
        self.assertEqual(QuizAnswer.objects.count(), 0)

    def test_lesson_questions_and_tokens_are_isolated_across_users_tracks_and_reloads(self):
        other = User.objects.create_user(username='other')
        UserProfile.objects.create(user=other, is_paid=True)
        other_client = Client()
        other_client.force_login(other)
        lessons = [self.lesson, self.next_lesson, make_lesson(251), make_lesson(252)]
        tokens = set()
        for client in [self.client, other_client]:
            for lesson in lessons:
                for _ in range(2):
                    response = self.start(lesson, client)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('no-store', response['Cache-Control'])
                    state = response.json()
                    self.assertEqual(state['lesson_id'], lesson.pk)
                    self.assertEqual({q['english_word'] for q in state['questions']}, {f'word{lesson.pk}_{i}' for i in range(4)})
                    meanings = {f'meaning{lesson.pk}_{i}' for i in range(4)}
                    for question in state['questions']:
                        self.assertEqual(len(question['choices']), len(set(question['choices'])))
                        self.assertEqual(set(question['choices']), meanings)
                tokens.add(state['attempt_token'])
        self.assertEqual(len(tokens), 8)
        state = self.start().json()
        question = self.lesson.quiz_questions.first()
        self.assertEqual(self.submit(state, question, client=other_client).status_code, 409)
        self.assertEqual(self.submit(state, question, lesson=self.next_lesson).status_code, 409)

    def test_content_edit_invalidates_run_and_preserves_pass_and_historical_questions(self):
        old = self.complete()
        ids = set(self.lesson.quiz_questions.values_list('pk', flat=True))
        self.lesson.vocabulary = '\n'.join(f'new{i} — translated{i}' for i in range(4))
        self.lesson.save(update_fields=['vocabulary'])
        self.assertEqual(self.submit(old, self.lesson.quiz_questions.first()).status_code, 409)
        new = self.start().json()
        self.assertNotEqual(old['attempt_token'], new['attempt_token'])
        self.assertTrue(new['lesson_completed'])
        self.assertFalse(new['completed'])
        self.assertEqual(new['previous_score'], 4)
        self.assertEqual(QuizQuestion.objects.filter(pk__in=ids).count(), 4)
        self.assertEqual({q['english_word'] for q in new['questions']}, {f'new{i}' for i in range(4)})

    def test_full_answer_evidence_repairs_missing_pass_but_partial_evidence_does_not(self):
        state = self.start().json()
        attempt = QuizAttempt.objects.get(user_id=str(self.user.pk), lesson=self.lesson)
        questions = list(self.lesson.quiz_questions.all())
        QuizAnswer.objects.bulk_create([QuizAnswer(attempt=attempt, question=q, selected_answer=q.kazakh_translation, is_correct=True) for q in questions[:3]])
        self.assertFalse(self.start().json()['lesson_completed'])
        QuizAnswer.objects.create(attempt=attempt, question=questions[3], selected_answer=questions[3].kazakh_translation, is_correct=True)
        self.assertTrue(self.start().json()['lesson_completed'])
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_passed)
        self.assertEqual(attempt.score, 4)

    def test_complete_answer_evidence_repairs_inconsistent_completed_flag(self):
        self.start()
        attempt = QuizAttempt.objects.get(user_id=str(self.user.pk), lesson=self.lesson)
        for question in self.lesson.quiz_questions.all():
            QuizAnswer.objects.create(attempt=attempt, question=question,
                                      selected_answer=question.kazakh_translation, is_correct=True)
        attempt.completed = True
        attempt.save(update_fields=['completed'])
        self.assertTrue(self.start().json()['lesson_completed'])
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_passed)
        self.assertEqual(attempt.score, 4)

    def test_missing_lesson_id_does_not_block_next_existing_lesson(self):
        self.next_lesson.delete()
        next_lesson = make_lesson(4)
        result = self.complete()
        self.assertEqual(result['next_lesson'], 4)
        self.assertTrue(result['can_continue'])
        self.assertIn(4, self.client.get(reverse('lesson_list')).context['passed_lessons'])
        self.assertEqual(self.client.get(reverse('lesson_detail', args=[4])).status_code, 200)
        self.assertEqual(self.start(next_lesson).status_code, 200)

    def test_result_omits_next_action_when_successor_requires_payment(self):
        self.next_lesson.delete()
        make_lesson(4)
        self.profile.is_paid = False
        self.profile.save()
        result = self.complete()
        self.assertEqual(result['next_lesson'], 4)
        self.assertFalse(result['can_continue'])
        self.assertFalse(self.start().json()['can_continue'])

    def test_quiz_access_matches_lesson_page_for_guests_unpaid_locked_and_teacher(self):
        locked = make_lesson(4)
        for client in [Client(), self.client]:
            for name in ['start_quiz', 'restart_quiz', 'submit_answer']:
                request = client.get if name == 'start_quiz' else client.post
                self.assertEqual(request(reverse(name, args=[locked.pk])).status_code, 403)
        QuizAttempt.objects.create(user_id=str(self.user.pk), lesson=make_lesson(3), is_passed=True)
        self.profile.is_paid = False
        self.profile.save()
        self.assertEqual(self.start(locked).status_code, 403)
        russian = make_lesson(254)
        QuizAttempt.objects.create(user_id=str(self.user.pk), lesson=make_lesson(253), is_passed=True)
        self.assertEqual(self.start(russian).status_code, 200)  # Preserve existing Russian student policy.
        self.profile.role = 'teacher'
        self.profile.save()
        self.assertEqual(self.start(russian).status_code, 403)

    def test_restart_requires_post_csrf_and_matching_token(self):
        url = reverse('restart_quiz', args=[1])
        self.assertEqual(self.client.get(url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        state = self.start(client=client).json()
        self.assertEqual(client.post(url, {'attempt_token': state['attempt_token']}).status_code, 403)
        client.get(reverse('lesson_detail', args=[1]))
        csrf = client.cookies['csrftoken'].value
        self.assertEqual(client.post(url, {'attempt_token': 'wrong'}, HTTP_X_CSRFTOKEN=csrf).status_code, 409)
        self.assertEqual(client.post(url, {'attempt_token': state['attempt_token']}, HTTP_X_CSRFTOKEN=csrf).status_code, 200)

    def test_guest_completed_progress_comes_from_answers_not_session_unlocks(self):
        guest = Client()
        state = self.start(client=guest).json()
        for question in self.lesson.quiz_questions.all():
            self.submit(state, question, client=guest)
        for _ in range(3):
            response = guest.get(reverse('lesson_list'))
            self.assertEqual(response.context['stages'][0]['progress']['passed'], 1)

    def test_parser_variants_duplicates_and_invalid_content(self):
        self.lesson.vocabulary = 'one – бір\ntwo — екі\nthree - үш\nfour – төрт\none – бір'
        self.lesson.save()
        detail = self.client.get(reverse('lesson_detail', args=[1]))
        self.assertEqual(detail.context['quiz_question_count'], 4)
        self.assertIsNone(detail.context['quiz_previous_score'])
        self.assertFalse(QuizAttempt.objects.filter(lesson=self.lesson).exists())
        first = self.start().json()
        second = self.start().json()
        self.assertEqual(len(first['questions']), 4)
        self.assertEqual({q['id'] for q in first['questions']}, {q['id'] for q in second['questions']})
        self.assertEqual(self.lesson.quiz_questions.count(), 4)
        self.lesson.vocabulary += '\nmissing translation'
        self.lesson.save()
        self.assertEqual(self.start().status_code, 400)
        self.assertIsNone(self.client.get(reverse('lesson_detail', args=[1])).context['quiz_question_count'])

    def test_vocabulary_supports_full_unicode_on_the_database_connection(self):
        self.lesson.vocabulary = 'smile – күлімдеу 😊\nwave – қол бұлғау 👋\nrun – жүгіру\nread – оқу'
        self.lesson.save(update_fields=['vocabulary'])
        state = self.start().json()
        self.assertEqual(len(state['questions']), 4)
        self.assertEqual(self.complete()['score'], 4)

    def test_invalid_question_input_and_missing_token_are_controlled_errors(self):
        state = self.start().json()
        question = self.lesson.quiz_questions.first()
        url = reverse('submit_answer', args=[1])
        self.assertEqual(self.client.post(url, {'question_id': 'bad'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'question_id': question.pk}).status_code, 409)
        self.assertEqual(self.submit(state, question, answer='x' * 256).status_code, 400)

    def test_passed_lesson_renders_previous_score_and_retake_button(self):
        self.complete()
        self.lesson.vocabulary += '\nextra – қосымша'
        self.lesson.save(update_fields=['vocabulary'])
        response = self.client.get(reverse('lesson_detail', args=[1]))
        self.assertContains(response, 'Тестті қайта тапсыру')
        self.assertEqual(response.context['quiz_previous_score'], 4)
        self.assertEqual(response.context['quiz_previous_total'], 4)
        self.assertContains(response, '5 сұрақ')
        self.assertContains(response, '<strong id="quiz-previous-value">4 / 4</strong>', html=True)

    def test_dashboard_does_not_write_session_or_fetch_lesson_bodies(self):
        self.client.get(reverse('lesson_list'))
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('lesson_list'))
        sql = '\n'.join(q['sql'] for q in queries)
        self.assertNotIn('UPDATE "django_session"', sql)
        self.assertNotIn('"lessons_lesson"."content"', sql)
        self.assertEqual(response.status_code, 200)

    def test_read_only_audit_identifies_missing_completion_without_repair(self):
        self.complete()
        before = QuizAttempt.objects.count()
        output = StringIO()
        call_command('audit_learning_data', user_id=str(self.user.pk), stdout=output)
        report = json.loads(output.getvalue())
        self.assertTrue(report['read_only'])
        self.assertEqual(report['progress']['missing_completion_lesson_ids'], [2])
        self.assertEqual(QuizAttempt.objects.count(), before)

    @override_settings(DEBUG=True)
    def test_worker_is_revalidated_and_learning_responses_are_not_cacheable(self):
        response = self.client.get('/sw.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-cache')
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertContains(response, 'english-course-static-v3')
        for url in ['/', '/lesson/1/', '/start-quiz/1/']:
            self.assertIn('no-store', self.client.get(url)['Cache-Control'])

    def test_legacy_duplicate_questions_are_canonicalized_without_deletion(self):
        for _ in range(2):
            QuizQuestion.objects.create(lesson=self.lesson, english_word='word1_0', kazakh_translation='meaning1_0')
        state = self.start().json()
        self.assertEqual(len(state['questions']), 4)
        self.assertEqual(self.lesson.quiz_questions.count(), 5)
        self.assertEqual(self.complete()['score'], 4)

    def test_mutated_stored_question_cannot_become_an_unrelated_correct_answer(self):
        state = self.start().json()
        question = self.lesson.quiz_questions.first()
        question.kazakh_translation = 'unrelated'
        question.save()
        self.assertEqual(self.submit(state, question).status_code, 409)
        self.assertEqual(QuizAnswer.objects.count(), 0)


class CoursePerformanceTests(TestCase):
    """Set OQYAI_BENCHMARK=1 to print comparable warm-client measurements."""
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="benchmark")
        UserProfile.objects.create(user=cls.user, is_paid=True)
        for pk in range(1, 301):
            make_lesson(pk)

    def test_course_request_measurements(self):
        self.client.force_login(self.user)
        self.client.get(reverse("lesson_list"))
        self.client.get(reverse("lesson_detail", args=[1]))
        start = self.client.get(reverse("start_quiz", args=[1])).json()
        question = QuizQuestion.objects.filter(lesson_id=1).first()
        answer = {"question_id": question.pk, "answer": question.kazakh_translation}
        if "attempt_token" in start:
            answer["attempt_token"] = start["attempt_token"]
        cases = {
            "dashboard": lambda: self.client.get(reverse("lesson_list")),
            "lesson": lambda: self.client.get(reverse("lesson_detail", args=[1])),
            "quiz_start": lambda: self.client.get(reverse("start_quiz", args=[1])),
            "answer_retry": lambda: self.client.post(reverse("submit_answer", args=[1]), answer),
            "paywall": lambda: self.client.get(reverse("advertisement")),
        }
        budgets = {'dashboard': 9, 'lesson': 10, 'quiz_start': 15, 'answer_retry': 15, 'paywall': 7}
        for name, operation in cases.items():
            operation()
            times, counts, sql_times = [], [], []
            for _ in range(10):
                with CaptureQueriesContext(connection) as queries:
                    begin = time.perf_counter()
                    response = operation()
                    times.append((time.perf_counter() - begin) * 1000)
                self.assertEqual(response.status_code, 200)
                counts.append(len(queries))
                sql_times.append(sum(float(q["time"]) for q in queries) * 1000)
            self.assertLessEqual(max(counts), budgets[name], name)
            if os.getenv("OQYAI_BENCHMARK"):
                print("OQYAI_BENCHMARK", json.dumps({"case": name, "queries": counts,
                    "median_ms": round(statistics.median(times), 3),
                    "median_sql_ms": statistics.median(sql_times), "bytes": len(response.content)}))
