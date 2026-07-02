import base64
import hashlib
import json
from datetime import timedelta
from importlib import reload
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import clear_url_caches, reverse
from django.utils import timezone

from english_course.realtime_config import REALTIME_MODEL
from english_course.utils.realtime_tts import RealtimeTTSError, synthesize_audio_realtime_mp3
from .models import Lesson, QuizAnswer, QuizAttempt, QuizQuestion, UserProfile


class QuizIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="student", password="pass12345")
        UserProfile.objects.create(user=self.user)
        self.client.login(username="student", password="pass12345")
        self.lesson = Lesson.objects.create(
            title="Lesson 1",
            content="Content",
            vocabulary="\n".join(f"word{i} – meaning{i}" for i in range(10)),
            grammar="Grammar",
            dialogue="Dialogue",
        )
        self.next_lesson = Lesson.objects.create(
            title="Lesson 2",
            content="Content",
            vocabulary="next – next",
            grammar="Grammar",
            dialogue="Dialogue",
        )
        self.questions = [
            QuizQuestion.objects.create(
                lesson=self.lesson,
                english_word=f"word{i}",
                kazakh_translation=f"meaning{i}",
            )
            for i in range(10)
        ]

    def submit(self, question, answer="", **extra):
        payload = {"question_id": question.id, "answer": answer}
        payload.update(extra)
        return self.client.post(reverse("submit_answer", args=[self.lesson.id]), payload)

    def csrf_client(self):
        client = Client(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="student", password="pass12345"))
        return client

    def test_lesson_detail_sets_csrf_cookie(self):
        client = self.csrf_client()

        response = client.get(reverse("lesson_detail", args=[self.lesson.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", client.cookies)
        self.assertTrue(client.cookies["csrftoken"].value)

    def test_submit_answer_with_valid_csrf_token_succeeds(self):
        client = self.csrf_client()
        client.get(reverse("lesson_detail", args=[self.lesson.id]))
        csrf_token = client.cookies["csrftoken"].value

        response = client.post(
            reverse("submit_answer", args=[self.lesson.id]),
            {
                "question_id": self.questions[0].id,
                "answer": self.questions[0].kazakh_translation,
            },
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["accepted"])

    def test_submit_answer_without_valid_csrf_token_is_rejected(self):
        client = self.csrf_client()

        response = client.post(
            reverse("submit_answer", args=[self.lesson.id]),
            {
                "question_id": self.questions[0].id,
                "answer": self.questions[0].kazakh_translation,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            QuizAttempt.objects.filter(user_id=str(self.user.id), lesson=self.lesson).exists()
        )

    def test_same_correct_answer_submitted_ten_times_counts_once(self):
        question = self.questions[0]
        for _ in range(10):
            response = self.submit(question, question.kazakh_translation)
            self.assertEqual(response.status_code, 200)

        attempt = QuizAttempt.objects.get(user_id=str(self.user.id), lesson=self.lesson)
        self.assertEqual(QuizAnswer.objects.filter(attempt=attempt).count(), 1)
        self.assertEqual(attempt.score, 1)
        self.assertFalse(attempt.is_passed)
        self.assertNotIn(self.next_lesson.id, self.client.session.get("passed_lessons", []))

    def test_all_unique_correct_answers_passes_and_unlocks_next_once(self):
        for question in self.questions:
            response = self.submit(question, question.kazakh_translation)
            self.assertEqual(response.status_code, 200)

        attempt = QuizAttempt.objects.get(user_id=str(self.user.id), lesson=self.lesson)
        self.assertTrue(attempt.is_passed)
        self.assertTrue(attempt.completed)
        self.assertEqual(attempt.score, 10)
        self.assertEqual(self.client.session["passed_lessons"].count(self.next_lesson.id), 1)

        response = self.submit(self.questions[0], self.questions[0].kazakh_translation)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["already_passed"])
        self.assertEqual(self.client.session["passed_lessons"].count(self.next_lesson.id), 1)

    def test_cross_lesson_question_is_rejected_without_changing_attempt(self):
        attempt = QuizAttempt.objects.create(user_id=str(self.user.id), lesson=self.lesson)
        other_lesson = Lesson.objects.create(
            title="Other",
            content="Content",
            vocabulary="other – other",
            grammar="Grammar",
            dialogue="Dialogue",
        )
        other_question = QuizQuestion.objects.create(
            lesson=other_lesson,
            english_word="other",
            kazakh_translation="other",
        )

        response = self.submit(other_question, other_question.kazakh_translation)

        self.assertEqual(response.status_code, 404)
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 0)
        self.assertEqual(attempt.attempts, 0)
        self.assertEqual(attempt.answers.count(), 0)

    def test_three_unique_wrong_answers_restart_and_clear_answers(self):
        for question in self.questions[:2]:
            response = self.submit(question, "wrong")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json().get("restart_required"))

        response = self.submit(self.questions[2], "wrong")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["restart_required"])
        self.assertEqual(data["score"], 0)
        self.assertEqual(data["attempts"], 0)

        attempt = QuizAttempt.objects.get(user_id=str(self.user.id), lesson=self.lesson)
        self.assertEqual(attempt.score, 0)
        self.assertEqual(attempt.attempts, 0)
        self.assertFalse(attempt.is_passed)
        self.assertEqual(attempt.answers.count(), 0)
        self.assertNotIn(self.next_lesson.id, self.client.session.get("passed_lessons", []))

    def test_timeout_creates_one_wrong_answer_and_duplicate_does_not_increment(self):
        question = self.questions[0]
        first = self.submit(question, timed_out="true")
        second = self.submit(question, timed_out="true")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["already_answered"])

        attempt = QuizAttempt.objects.get(user_id=str(self.user.id), lesson=self.lesson)
        self.assertEqual(attempt.answers.count(), 1)
        answer = attempt.answers.get()
        self.assertEqual(answer.selected_answer, "")
        self.assertFalse(answer.is_correct)
        self.assertEqual(attempt.attempts, 1)

    def test_quizattempt_unique_constraint_prevents_duplicates(self):
        QuizAttempt.objects.create(user_id=str(self.user.id), lesson=self.lesson)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuizAttempt.objects.create(user_id=str(self.user.id), lesson=self.lesson)

    def test_quizattempt_score_arithmetic_cannot_pass_quiz(self):
        for method_name in ("add_score", "increase_attempts", "check_pass"):
            self.assertFalse(hasattr(QuizAttempt, method_name))

        attempt = QuizAttempt.objects.create(user_id=str(self.user.id), lesson=self.lesson)
        for _ in self.questions:
            attempt.score += 1
            attempt.save(update_fields=["score"])

        attempt.refresh_from_db()
        self.assertEqual(attempt.score, len(self.questions))
        self.assertEqual(attempt.answers.count(), 0)
        self.assertFalse(attempt.completed)
        self.assertFalse(attempt.is_passed)


class LocalMediaServingTests(TestCase):
    def test_debug_media_url_serves_file_from_media_root(self):
        import english_course.urls as project_urls

        with TemporaryDirectory() as media_root:
            media_file = Path(media_root) / "audio_lesson_test.mp3"
            media_file.write_bytes(b"fake mp3 bytes")

            try:
                with override_settings(DEBUG=True, MEDIA_ROOT=Path(media_root)):
                    clear_url_caches()
                    reload(project_urls)
                    clear_url_caches()
                    response = self.client.get(f"{settings.MEDIA_URL}{media_file.name}")
            finally:
                clear_url_caches()
                reload(project_urls)
                clear_url_caches()

        self.assertEqual(response.status_code, 200)


class RealtimeContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="voice", password="pass12345")
        self.profile = UserProfile.objects.create(
            user=self.user,
            has_voice_access=True,
            voice_access_until=timezone.now() + timedelta(days=1),
            has_translator_access=True,
            translator_access_until=timezone.now() + timedelta(days=1),
        )
        self.lesson = Lesson.objects.create(
            title="Realtime Lesson",
            content="Content",
            vocabulary="word – meaning\nword2 – meaning2\nword3 – meaning3\nword4 – meaning4",
            grammar="Grammar",
            dialogue="Dialogue",
        )
        self.client.login(username="voice", password="pass12345")

    @patch("english_course.realtime.requests.post")
    def test_realtime_browser_token_endpoint_uses_ga_client_secrets(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": "ephemeral-token", "expires_at": 123}
        mock_post.return_value = mock_response

        response = self.client.post(reverse("mint_realtime_token", args=[self.lesson.id]))

        self.assertEqual(response.status_code, 200)
        token_payload = response.json()
        self.assertEqual(token_payload["value"], "ephemeral-token")
        self.assertEqual(token_payload["expires_at"], 123)
        self.assertEqual(token_payload["realtime_model"], REALTIME_MODEL)
        self.assertNotIn("client_secret", token_payload)

        url = mock_post.call_args.args[0]
        kwargs = mock_post.call_args.kwargs
        headers = kwargs["headers"]
        payload = kwargs["json"]

        self.assertEqual(url, "https://api.openai.com/v1/realtime/client_secrets")
        self.assertEqual(payload["session"]["model"], "gpt-realtime-2")
        self.assertEqual(payload["session"]["audio"]["input"]["turn_detection"]["type"], "server_vad")
        self.assertEqual(payload["session"]["audio"]["output"]["voice"], "cedar")
        self.assertNotIn("OpenAI-Beta", headers)
        self.assertIn("OpenAI-Safety-Identifier", headers)
        self.assertEqual(
            headers["OpenAI-Safety-Identifier"],
            hashlib.sha256(str(self.user.id).encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(headers["OpenAI-Safety-Identifier"], str(self.user.id))


class FakeRealtimeWebSocket:
    def __init__(self, events):
        self.events = events
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, message):
        self.sent.append(json.loads(message))

    def __aiter__(self):
        self._iterator = iter(self.events)
        return self

    async def __anext__(self):
        try:
            return json.dumps(next(self._iterator))
        except StopIteration:
            raise StopAsyncIteration


class RealtimeTTSTests(TestCase):
    @patch("english_course.utils.realtime_tts._pcm16_to_mp3_bytes")
    @patch("english_course.utils.realtime_tts.websockets.connect")
    def test_realtime_tts_uses_ga_websocket_and_decodes_audio(self, mock_connect, mock_convert):
        pcm = b"\x01\x02\x03\x04"
        websocket = FakeRealtimeWebSocket([
            {"type": "session.updated"},
            {"type": "response.output_audio.delta", "delta": base64.b64encode(pcm).decode("ascii")},
            {"type": "response.done"},
        ])
        mock_connect.return_value = websocket
        mock_convert.return_value = b"mp3"

        result = async_to_sync(synthesize_audio_realtime_mp3)(
            "Hello",
            api_key="server-key",
            safety_identifier="safe-hash",
        )

        self.assertEqual(result, b"mp3")
        url = mock_connect.call_args.args[0]
        headers = mock_connect.call_args.kwargs["additional_headers"]
        self.assertEqual(url, "wss://api.openai.com/v1/realtime?model=gpt-realtime-2")
        self.assertEqual(headers["Authorization"], "Bearer server-key")
        self.assertEqual(headers["OpenAI-Safety-Identifier"], "safe-hash")
        self.assertNotIn("OpenAI-Beta", headers)
        self.assertEqual(websocket.sent[0]["type"], "session.update")
        self.assertNotIn("model", websocket.sent[0]["session"])
        self.assertEqual(websocket.sent[0]["session"]["audio"]["output"]["voice"], "cedar")
        self.assertEqual(websocket.sent[1]["type"], "conversation.item.create")
        self.assertEqual(websocket.sent[2]["type"], "response.create")
        mock_convert.assert_called_once_with(pcm, sample_rate=24000)

    @patch("english_course.utils.realtime_tts.websockets.connect")
    def test_realtime_tts_error_event_raises_controlled_exception(self, mock_connect):
        websocket = FakeRealtimeWebSocket([
            {"type": "error", "error": {"message": "model error"}},
        ])
        mock_connect.return_value = websocket

        with self.assertRaises(RealtimeTTSError):
            async_to_sync(synthesize_audio_realtime_mp3)(
                "Hello",
                api_key="server-key",
                safety_identifier="safe-hash",
            )
