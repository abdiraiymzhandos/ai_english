from datetime import timedelta
from unittest.mock import patch
import time
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from .models import UserProfile, QuizAttempt
from .test_learning_flow import make_lesson


class ProfileUITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('profile-test', password='test-password', email='learner@example.test')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        for pk in (1, 2, 3, 251):
            make_lesson(pk)
        self.client.force_login(self.user)

    def test_progress_uses_completion_and_current_catalog(self):
        self.profile.current_lesson = 250
        self.profile.save()
        QuizAttempt.objects.create(user_id=str(self.user.pk), lesson_id=1, is_passed=True)
        QuizAttempt.objects.create(user_id=str(self.user.pk), lesson_id=251, is_passed=True)
        response = self.client.get('/profile/')
        self.assertEqual(response.context['passed_main_lessons'], 1)
        self.assertEqual(response.context['total_lessons'], 3)
        self.assertEqual(response.context['progress_percentage'], 33)
        self.assertEqual(response.context['resume_url'], '/lesson/2/')
        self.assertContains(response, 'learner@example.test')
        self.assertContains(response, 'loading.js')
        self.assertContains(response, 'css/profile.css')
        self.assertIn('no-store', response['Cache-Control'])

    def test_expiry_flag_and_indefinite_access_matrix(self):
        for enabled, expiry, allowed in ((False, None, False), (False, timezone.now()+timedelta(days=1), False), (True, timezone.now()-timedelta(seconds=1), False), (True, timezone.now()+timedelta(days=1), True), (True, None, True)):
            with self.subTest(enabled=enabled, expiry=expiry):
                self.profile.has_translator_access = enabled
                self.profile.translator_access_until = expiry
                self.profile.save()
                response = self.client.get('/profile/')
                self.assertEqual('id="translator-link"' in response.content.decode(), allowed)
                self.assertNotContains(response, 'translator-assistant.js')
                self.assertEqual(self.client.get('/translator/').status_code, 200 if allowed else 403)
                self.assertEqual(self.client.get(reverse('check_translator_access')).json()['has_access'], allowed)
                self.profile.refresh_from_db()
                self.assertEqual(self.profile.translator_access_until, expiry)
                self.assertEqual(self.profile.has_translator_access, enabled)

    @patch('lessons.views.mint_realtime_client_secret')
    def test_denied_token_never_calls_provider(self, mint):
        for expired in (False, True):
            self.profile.has_translator_access = expired
            self.profile.translator_access_until = timezone.now()-timedelta(days=1)
            self.profile.save()
            self.assertEqual(self.client.post(reverse('mint_translator_token')).status_code, 403)
        mint.assert_not_called()

    def test_anonymous_and_csrf_guards(self):
        self.client.logout()
        self.assertEqual(self.client.get('/translator/').status_code, 302)
        self.assertEqual(self.client.get('/api/translator/check-access/').status_code, 401)
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.user)
        self.assertEqual(guarded.post('/api/translator/token/').status_code, 403)
        self.assertEqual(guarded.post('/profile/', {'password':'test-password', 'confirm':'on'}).status_code, 403)

    def test_general_pages_have_no_translator_resources(self):
        self.profile.has_translator_access = True
        self.profile.save()
        for url in ('/', '/lesson/1/', '/profile/'):
            response = self.client.get(url)
            for fragment in ('translator-floating-btn', 'translator-assistant.js', 'translator-assistant.css', 'translatorAssistantConfig'):
                self.assertNotContains(response, fragment)

    def test_delete_requires_correct_password_and_confirmation(self):
        for payload in ({'password':'wrong', 'confirm':'on'}, {'password':'test-password'}):
            self.assertEqual(self.client.post('/profile/', payload).status_code, 200)
            self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_profile_query_measurement(self):
        self.client.get('/profile/')
        with CaptureQueriesContext(connection) as queries:
            start = time.perf_counter()
            response = self.client.get('/profile/')
            elapsed = (time.perf_counter()-start)*1000
        self.assertLessEqual(len(queries), 9)
        print('PROFILE_MEASUREMENT', len(queries), round(elapsed, 3), len(response.content))

    @patch('lessons.views.mint_realtime_client_secret')
    def test_authorized_translator_token_preserves_contract(self, mint):
        self.profile.has_translator_access = True
        self.profile.translator_access_until = timezone.now()+timedelta(days=1)
        self.profile.save()
        mint.return_value = {'value':'synthetic-ephemeral-token', 'expires_at':123}
        response = self.client.post(reverse('mint_translator_token'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['value'], 'synthetic-ephemeral-token')
        self.assertEqual(mint.call_args.kwargs['feature'], 'translator')
        self.assertEqual(mint.call_args.kwargs['voice'], 'cedar')

    def test_empty_curriculum_and_teacher_navigation(self):
        from .models import Lesson
        Lesson.objects.all().delete()
        self.profile.role = 'teacher'
        self.profile.save()
        response = self.client.get('/profile/')
        self.assertEqual(response.context['total_lessons'], 0)
        self.assertEqual(response.context['progress_percentage'], 0)
        self.assertContains(response, reverse('classroom_dashboard'))
        self.assertNotContains(response, '/lesson/0/')

    def test_logout_is_profile_only_and_requires_csrf_post(self):
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.user)
        attempt = QuizAttempt.objects.create(user_id=str(self.user.pk), lesson_id=1, is_passed=True)
        dashboard = guarded.get('/')
        self.assertNotContains(dashboard, 'action="/logout/"')
        self.assertContains(dashboard, 'href="/profile/"')
        profile = guarded.get('/profile/')
        self.assertContains(profile, 'Аккаунттан шығу')
        self.assertContains(profile, '<form method="post" action="/logout/">')
        self.assertEqual(guarded.get('/logout/').status_code, 405)
        self.assertEqual(guarded.post('/logout/').status_code, 403)
        self.assertIn('_auth_user_id', guarded.session)
        from django.conf import settings
        token = guarded.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertRedirects(guarded.post('/logout/', {'csrfmiddlewaretoken': token}), '/login/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', guarded.session)
        for url in ('/profile/', '/translator/', '/vocabulary/'):
            response = guarded.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response.url)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_passed)
