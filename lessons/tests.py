from unittest.mock import Mock, patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import UserProfile
from .services.registration_notifications import send_registration_notification


class RegistrationNotificationTests(TestCase):
    def _registration_payload(self, *, username="new_user", phone="+77011234567", role="student"):
        return {
            "username": username,
            "phone": phone,
            "role": role,
            "password1": "StrongPass123",
            "password2": "StrongPass123",
        }

    @override_settings(APP_BASE_URL="https://admin.example.test")
    @patch("lessons.services.registration_notifications.send_telegram_message")
    def test_registration_notification_uses_short_telegram_timeout(self, mock_send):
        mock_send.return_value = True
        user = User.objects.create_user(username="timeout_user", password="StrongPass123")
        profile = UserProfile.objects.create(user=user, phone="+77011234567", role="student")

        result = send_registration_notification(user, profile)

        self.assertTrue(result)
        mock_send.assert_called_once()
        text = mock_send.call_args.args[0]
        self.assertIn("timeout_user", text)
        self.assertEqual(mock_send.call_args.kwargs["timeout"], 5)

    @override_settings(
        TELEGRAM_BOT_TOKEN="configured",
        TELEGRAM_CHAT_ID="configured",
        APP_BASE_URL="https://admin.example.test",
    )
    @patch("english_course.services.telegram.requests.post")
    def test_successful_registration_sends_one_telegram_notification(self, mock_post):
        mock_post.return_value = Mock(status_code=200)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(
                reverse("register"),
                self._registration_payload(username="teacher_user", role="teacher"),
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("lesson_list"))
        self.assertEqual(len(callbacks), 1)

        user = User.objects.get(username="teacher_user")
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.phone, "+77011234567")
        self.assertEqual(profile.role, "teacher")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

        mock_post.assert_called_once()
        request_data = mock_post.call_args.kwargs["data"]
        text = request_data["text"]
        self.assertIn("teacher_user", text)
        self.assertIn("📞 Телефон: +77011234567", text)
        self.assertIn("👥 Рөлі: Мұғалім", text)
        self.assertIn("💬 WhatsApp: https://wa.me/77011234567", text)
        self.assertIn(
            f"🔗 Admin: https://admin.example.test{reverse('admin:auth_user_change', args=[user.pk])}",
            text,
        )
        self.assertTrue(request_data["disable_web_page_preview"])

    @override_settings(
        TELEGRAM_BOT_TOKEN="configured",
        TELEGRAM_CHAT_ID="configured",
        APP_BASE_URL="https://admin.example.test",
    )
    @patch("english_course.services.telegram.requests.post")
    def test_telegram_http_failure_does_not_block_registration(self, mock_post):
        mock_post.side_effect = requests.RequestException("network down")

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(
                reverse("register"),
                self._registration_payload(username="failure_user"),
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("lesson_list"))
        self.assertEqual(len(callbacks), 1)
        user = User.objects.get(username="failure_user")
        self.assertTrue(UserProfile.objects.filter(user=user, phone="+77011234567").exists())
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        mock_post.assert_called_once()

    @override_settings(
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_CHAT_ID="",
        APP_BASE_URL="https://admin.example.test",
    )
    @patch("english_course.services.telegram.requests.post")
    def test_missing_telegram_configuration_does_not_attempt_external_request(self, mock_post):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(
                reverse("register"),
                self._registration_payload(username="missing_config_user"),
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(callbacks), 1)
        user = User.objects.get(username="missing_config_user")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        mock_post.assert_not_called()
