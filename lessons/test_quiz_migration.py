import uuid

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class QuizRunMigrationTests(TransactionTestCase):
    """Rehearse upgrade and rollback with legacy aggregates and answer evidence."""
    def test_upgrade_preserves_legacy_progress_and_rollback_keeps_answers(self):
        executor = MigrationExecutor(connection)
        before = [('lessons', '0016_quizattempt_unique_constraint')]
        after = [('lessons', '0017_quiz_run_state')]
        executor.migrate(before)
        try:
            old = executor.loader.project_state(before).apps
            Lesson = old.get_model('lessons', 'Lesson')
            Attempt = old.get_model('lessons', 'QuizAttempt')
            Question = old.get_model('lessons', 'QuizQuestion')
            Answer = old.get_model('lessons', 'QuizAnswer')
            lesson = Lesson.objects.create(title='Legacy', vocabulary='one – бір', content='C', grammar='G', dialogue='D')
            first = Attempt.objects.create(user_id='synthetic-one', lesson=lesson, is_passed=True, completed=True, score=10)
            second = Attempt.objects.create(user_id='synthetic-two', lesson=lesson, is_passed=False, score=1)
            Attempt.objects.bulk_create([Attempt(user_id=f'synthetic-batch-{i}', lesson=lesson) for i in range(501)])
            question = Question.objects.create(lesson=lesson, english_word='one', kazakh_translation='бір')
            Answer.objects.create(attempt=second, question=question, selected_answer='бір', is_correct=True)
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            new = executor.loader.project_state(after).apps
            migrated = list(new.get_model('lessons', 'QuizAttempt').objects.order_by('pk'))
            self.assertEqual([a.is_passed for a in migrated[:2]], [True, False])
            self.assertEqual([a.last_passed_score for a in migrated[:2]], [10, None])
            self.assertNotEqual(migrated[0].attempt_token, migrated[1].attempt_token)
            self.assertTrue(all(isinstance(a.attempt_token, uuid.UUID) for a in migrated))
            self.assertEqual(len({a.attempt_token for a in migrated}), 503)
            self.assertTrue(all(a.question_ids == [] for a in migrated))
            self.assertEqual(new.get_model('lessons', 'QuizAnswer').objects.count(), 1)
            executor = MigrationExecutor(connection)
            executor.migrate(before)
            restored = executor.loader.project_state(before).apps
            self.assertEqual(restored.get_model('lessons', 'QuizAnswer').objects.count(), 1)
            self.assertEqual(restored.get_model('lessons', 'QuizAttempt').objects.get(pk=first.pk).score, 10)
        finally:
            MigrationExecutor(connection).migrate(after)
