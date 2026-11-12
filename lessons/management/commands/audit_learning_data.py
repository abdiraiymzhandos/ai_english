"""Read-only curriculum/quiz diagnostics; never repair or fabricate progress."""
import json

from django.core.management.base import BaseCommand, CommandError

from lessons.models import Lesson, QuizAttempt
from lessons.services.quiz import QuizContentError, vocabulary_pairs


class Command(BaseCommand):
    help = 'Report stale vocabulary and optionally missing completion IDs. Does not write data.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', help='Internal account ID or guest session key; never printed.')
        parser.add_argument('--track', choices=['kk', 'ru'], default='kk')
        parser.add_argument('--level', type=int, default=1, help='50-lesson level (1–5).')

    def handle(self, *args, **options):
        if not 1 <= options['level'] <= 5:
            raise CommandError('--level must be between 1 and 5')
        report = {'read_only': True, 'invalid_vocabulary_lessons': [], 'stale_question_counts': {}, 'duplicate_question_counts': {}}
        for lesson in Lesson.objects.prefetch_related('quiz_questions').order_by('pk'):
            try:
                pairs = set(vocabulary_pairs(lesson))
            except QuizContentError:
                report['invalid_vocabulary_lessons'].append(lesson.pk)
                continue
            seen, stale, duplicates = set(), 0, 0
            for question in lesson.quiz_questions.all():
                pair = (question.english_word, question.kazakh_translation)
                stale += pair not in pairs
                duplicates += pair in seen
                seen.add(pair)
            if stale:
                report['stale_question_counts'][lesson.pk] = stale
            if duplicates:
                report['duplicate_question_counts'][lesson.pk] = duplicates
        if options['user_id']:
            start = (250 if options['track'] == 'ru' else 0) + (options['level'] - 1) * 50 + 1
            end = start + 49
            lesson_ids = set(Lesson.objects.filter(pk__range=(start, end)).values_list('pk', flat=True))
            passed = set(QuizAttempt.objects.filter(user_id=options['user_id'], lesson_id__in=lesson_ids, is_passed=True)
                         .values_list('lesson_id', flat=True))
            report['progress'] = {
                'range': [start, end], 'completed': len(passed), 'available_lessons': len(lesson_ids),
                'missing_completion_lesson_ids': sorted(lesson_ids - passed),
                'missing_curriculum_lesson_ids': sorted(set(range(start, end + 1)) - lesson_ids),
            }
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
