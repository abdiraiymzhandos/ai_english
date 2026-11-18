"""Exercise real row locks; SQLite explicitly skips these tests."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth.models import User
from django.db import close_old_connections, connections
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from .models import QuizAnswer, QuizAttempt, QuizQuestion, UserProfile
from .test_learning_flow import make_lesson


@skipUnlessDBFeature('has_select_for_update')
class QuizConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.lesson = make_lesson(1)
        make_lesson(2)
        self.user = User.objects.create_user(username='concurrent-learner')
        UserProfile.objects.create(user=self.user, is_paid=True)
        self.clients = [self.make_client(self.user, index) for index in range(2)]

    def make_client(self, user, index):
        client = Client()
        client.force_login(user)
        client.cookies['device_id'] = f'synthetic-device-{index}'
        return client

    def parallel(self, calls):
        barrier = Barrier(len(calls))

        def execute(call):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                response = call()
                return response.status_code, response.json()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(calls)) as pool:
            futures = [pool.submit(execute, call) for call in calls]
            return [future.result(timeout=20) for future in futures]

    def start(self):
        return self.clients[0].get(reverse('start_quiz', args=[1])).json()

    def payload(self, state, question, answer=None):
        return {'attempt_token': state['attempt_token'], 'question_id': question.pk,
                'answer': question.kazakh_translation if answer is None else answer}

    def test_simultaneous_starts_create_one_question_set_and_separate_user_runs(self):
        other = User.objects.create_user(username='concurrent-other')
        UserProfile.objects.create(user=other)
        self.clients[1] = self.make_client(other, 1)
        results = self.parallel([lambda client=client: client.get(reverse('start_quiz', args=[1])) for client in self.clients])
        self.assertEqual([status for status, _ in results], [200, 200])
        self.assertEqual(QuizQuestion.objects.count(), 4)
        self.assertEqual(QuizAttempt.objects.count(), 2)
        self.assertNotEqual(results[0][1]['attempt_token'], results[1][1]['attempt_token'])

    def test_simultaneous_duplicate_answer_counts_once(self):
        state = self.start()
        data = self.payload(state, self.lesson.quiz_questions.first())
        results = self.parallel([lambda client=client: client.post(reverse('submit_answer', args=[1]), data) for client in self.clients])
        self.assertEqual([status for status, _ in results], [200, 200])
        self.assertEqual(sum(body['accepted'] for _, body in results), 1)
        self.assertEqual(QuizAnswer.objects.count(), 1)
        self.assertEqual(QuizAttempt.objects.get().score, 1)

    def test_simultaneous_final_answer_passes_once(self):
        state = self.start()
        questions = list(self.lesson.quiz_questions.order_by('pk'))
        for question in questions[:3]:
            self.clients[0].post(reverse('submit_answer', args=[1]), self.payload(state, question))
        data = self.payload(state, questions[3])
        results = self.parallel([lambda client=client: client.post(reverse('submit_answer', args=[1]), data) for client in self.clients])
        self.assertEqual([status for status, _ in results], [200, 200])
        self.assertTrue(all(body['passed'] for _, body in results))
        self.assertEqual(QuizAttempt.objects.filter(is_passed=True).count(), 1)
        self.assertEqual(QuizAnswer.objects.count(), 4)
        self.assertEqual(UserProfile.objects.get(user=self.user).current_lesson, 2)

    def test_restart_and_delayed_answer_never_write_into_new_run(self):
        state = self.start()
        data = self.payload(state, self.lesson.quiz_questions.first())
        results = self.parallel([
            lambda: self.clients[0].post(reverse('restart_quiz', args=[1]), {'attempt_token': state['attempt_token']}),
            lambda: self.clients[1].post(reverse('submit_answer', args=[1]), data),
        ])
        self.assertEqual(results[0][0], 200)
        self.assertIn(results[1][0], [200, 409])
        attempt = QuizAttempt.objects.get()
        self.assertEqual(attempt.score, 0)
        self.assertEqual(attempt.answers.count(), 0)
        self.assertNotEqual(str(attempt.attempt_token), state['attempt_token'])

    def test_duplicate_third_mistake_cannot_enter_reset_run(self):
        state = self.start()
        questions = list(self.lesson.quiz_questions.order_by('pk'))
        for question in questions[:2]:
            self.clients[0].post(reverse('submit_answer', args=[1]), self.payload(state, question, 'wrong'))
        data = self.payload(state, questions[2], 'wrong')
        results = self.parallel([lambda client=client: client.post(reverse('submit_answer', args=[1]), data) for client in self.clients])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        attempt = QuizAttempt.objects.get()
        self.assertFalse(attempt.is_passed)
        self.assertEqual((attempt.score, attempt.attempts, attempt.answers.count()), (0, 0, 0))

    def test_racing_different_choices_both_report_the_stored_outcome(self):
        state = self.start()
        question = self.lesson.quiz_questions.first()
        choices = [question.kazakh_translation, 'different choice']
        results = self.parallel([
            lambda client=client, choice=choice: client.post(
                reverse('submit_answer', args=[1]), self.payload(state, question, choice)
            ) for client, choice in zip(self.clients, choices)
        ])
        stored = QuizAnswer.objects.get()
        for status, body in results:
            self.assertEqual(status, 200)
            self.assertEqual(body['correct'], stored.is_correct)
            self.assertEqual(body['correct_answer'], question.kazakh_translation)
            self.assertEqual(body['answered_count'], 1)
            self.assertEqual(body['attempts'], int(not stored.is_correct))
        self.assertEqual(sum(body['accepted'] for _, body in results), 1)
