from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Explanation, ExplanationPublication, LiveExplanation, QuizAttempt, UserProfile
from .services.explanation_publication import published_url
from .services.live_explanations import execute_next
from .test_learning_flow import make_lesson
from .test_live_explanations import sample_pcm, tts


@override_settings(LIVE_EXPLANATIONS_ENABLED=True)
class PublicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mp3 = tts.encode_mp3(sample_pcm())
        cls.owner = User.objects.create_superuser("publisher")
        cls.student = User.objects.create_user("reader")
        cls.other = User.objects.create_user("other-reader")
        cls.lesson = make_lesson(1)
        make_lesson(3)
        make_lesson(4)

    def setUp(self):
        self.client.force_login(self.owner)
        self.reader = Client()
        self.reader.force_login(self.student)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.media = Path(temp.name)
        storage = override_settings(MEDIA_ROOT=self.media, PRIVATE_EXPLANATION_ROOT=self.media / "private")
        storage.enable()
        self.addCleanup(storage.disable)
        self.original = Explanation.objects.create(lesson=self.lesson, section="content", text="Legacy text.",
                                                  audio_url="/media/audio_lesson_1_content_legacy.mp3")
        (self.media / self.original.audio_url.split("/")[-1]).write_bytes(self.mp3)
        self.url = reverse("live_explanation", args=[1, "content"])
        self.publish = reverse("select_explanation_publication", args=[1, "content"])

    def generate_live(self, valid=True, script="Live script.", before_worker=None):
        job = uuid4()
        self.assertEqual(self.client.post(self.url, {"mode":"fresh","job":job}).status_code, 202)
        if before_worker:
            before_worker()
        with patch("lessons.services.live_explanations.OpenAI") as astra, patch(
                "lessons.services.live_explanations.synthesize_audio_live_mp3", new_callable=AsyncMock,
                return_value=tts.Narration(self.mp3, {"transcript": "Private transcript"}, valid)):
            response = astra.return_value.__enter__.return_value.responses.create.return_value
            response.status, response.output_text = "completed", script
            self.assertTrue(execute_next())
        return job

    def test_publication_across_users_flag_off_and_private_endpoint_denial(self):
        self.assertContains(self.reader.get("/lesson/1/"), "Legacy text.")
        job = self.generate_live()
        public = published_url(1, "content", job)
        self.reader.logout()
        for user in (self.student, self.other):
            browser = Client()
            browser.force_login(user)
            page = browser.get("/lesson/1/")
            self.assertContains(page, public)
            self.assertContains(page, "Live script.")
            self.assertNotContains(page, "Legacy text.")
            for private in ("Техникалық ақпарат", "Private transcript", "Live түсіндіру", "data-publish-url", "explain-btn\""):
                self.assertNotContains(page, private)
            self.assertEqual(browser.get(self.url).status_code, 403)
            self.assertEqual(browser.post(self.url, {"job":uuid4()}).status_code, 403)
            self.assertEqual(browser.post(self.publish, {"revision":job}).status_code, 403)
            self.assertEqual(browser.post(reverse("explain_section", args=[1]), {"section":"content"}).status_code, 403)
            self.assertEqual(browser.get(reverse("live_audio", args=[1,"content",job])).status_code, 403)
            self.assertEqual(browser.get(self.original.audio_url).status_code, 404)
            self.assertEqual(browser.get(self.original.audio_url + "/").status_code, 404)
            with override_settings(LIVE_EXPLANATIONS_ENABLED=False, OPENAI_API_KEY=None):
                self.assertContains(browser.get("/lesson/1/"), public)
                self.assertEqual(browser.get(public, HTTP_RANGE="bytes=2-12").content, self.mp3[2:13])
                self.assertEqual(browser.head(public)["Content-Length"], str(len(self.mp3)))
                self.assertEqual(browser.get(public, HTTP_RANGE="bytes=222222222-").status_code, 416)
            self.assertEqual(browser.get(published_url(1,"grammar",job)).status_code, 404)
            self.assertEqual(browser.get(published_url(3,"content",job)).status_code, 404)

    def test_review_failure_manual_switch_and_stale_completion(self):
        old = self.generate_live()
        public = published_url(1,"content",old)
        review = self.generate_live(False, "Incomplete.")
        self.assertEqual(self.reader.get(public).content, self.mp3)
        self.assertEqual(self.reader.get(published_url(1,"content",review)).status_code, 404)
        self.assertEqual(self.client.post(self.publish, {"revision":review}).status_code, 404)
        self.assertEqual(self.reader.get(reverse("live_review_audio", args=[1,"content",review])).status_code,403)
        with patch("lessons.services.live_explanations.OpenAI") as astra:
            stale = self.generate_live(script="Late result.", before_worker=lambda: self.assertEqual(
                self.client.post(self.publish, {"revision": old}).status_code, 200))
            self.assertEqual(self.reader.get(public).content, self.mp3)  # old revision moved to the archive
            self.assertEqual(self.reader.get(published_url(1,"content",stale)).status_code, 404)
            self.assertContains(self.reader.get("/lesson/1/"), "Live script.")
            self.assertEqual(self.client.post(self.publish, {"audio_url":self.original.audio_url}).status_code,200)
            self.assertEqual(self.reader.get(public).status_code,404)
            self.assertEqual(self.reader.get(self.original.audio_url).content,self.mp3)
            self.assertEqual(self.client.post(self.publish, {"revision":old}).status_code,200)
            self.assertEqual(self.reader.get(public).content,self.mp3)
            astra.assert_not_called()

    def test_lesson_gate_enforces_payment_and_progress_on_direct_audio(self):
        job = uuid4()
        LiveExplanation.objects.create(lesson_id=4, section="grammar", revision=job, text="Paid", mp3=self.mp3)
        url = published_url(4,"grammar",job)
        self.assertEqual(self.client.post(reverse("select_explanation_publication",args=[4,"grammar"]),
                                          {"revision":job}).status_code,200)
        self.assertEqual(Client().get(url).status_code,403)
        self.assertEqual(self.reader.get(url).status_code,403)
        profile, _ = UserProfile.objects.get_or_create(user=self.student)
        profile.is_paid = True
        profile.save()
        self.assertEqual(self.reader.get(url).status_code,403)
        QuizAttempt.objects.create(user_id=str(self.student.pk), lesson_id=3, is_passed=True)
        self.assertContains(self.reader.get("/lesson/4/"), url)
        self.assertEqual(self.reader.get(url).content,self.mp3)
        self.assertContains(self.reader.get("/lesson/1/"),self.original.audio_url)

    def test_realtime_publication_and_rejection_preserve_existing_takes(self):
        previous = self.generate_live()
        public = published_url(1,"content",previous)
        url = reverse("explain_section",args=[1])
        with patch("lessons.views.OpenAI") as api, patch("lessons.views.synthesize_audio_realtime_mp3",
                  new_callable=AsyncMock) as speech:
            api.return_value.__enter__.return_value.responses.create.return_value.output_text = "Realtime result."
            speech.return_value = b"invalid"
            self.assertEqual(self.client.post(url, {"section":"content"}).status_code,502)
            self.assertEqual(self.reader.get(public).content,self.mp3)
            speech.return_value = self.mp3
            audio = self.client.post(url, {"section":"content"}).json()["audio_url"]
        page = self.reader.get("/lesson/1/")
        self.assertContains(page, "Realtime result.")
        self.assertContains(page, audio)
        self.assertEqual(self.reader.get(audio).content,self.mp3)
        self.assertEqual(self.reader.get(public).status_code,404)
        self.assertTrue(LiveExplanation.objects.filter(revision=previous).exists())
        self.assertIsNone(ExplanationPublication.objects.get().live_revision)

    def test_a_superseded_realtime_request_cannot_replace_a_manual_publication(self):
        revision = self.generate_live()
        url = reverse("explain_section", args=[1])

        def finish_text(**kwargs):
            from types import SimpleNamespace
            self.assertEqual(self.client.post(self.publish, {"revision": revision}).status_code, 200)
            return SimpleNamespace(output_text="Late Realtime text.")

        with patch("lessons.views.OpenAI") as api, patch("lessons.views.synthesize_audio_realtime_mp3",
                  new_callable=AsyncMock, return_value=self.mp3):
            api.return_value.__enter__.return_value.responses.create.side_effect = finish_text
            self.assertEqual(self.client.post(url, {"section": "content"}).status_code, 409)
        self.assertContains(self.reader.get("/lesson/1/"), published_url(1,"content",revision))
        self.assertEqual(Explanation.objects.get().audio_url,self.original.audio_url)
        self.assertFalse((self.media / "private").exists())

    def test_silent_or_damaged_saved_recording_cannot_be_selected(self):
        from io import BytesIO
        from pydub import AudioSegment

        published = self.generate_live()
        silent = BytesIO()
        AudioSegment.silent(duration=500).export(silent, format="mp3")
        row = LiveExplanation.objects.get()
        damaged = row.reviews.create(job=uuid4(), archived_validated=True, mp3=b"damaged",
                                     text="Damaged", mode="fresh", metadata={})
        self.assertEqual(self.client.post(self.publish, {"revision":damaged.job}).status_code,409)
        (self.media / self.original.audio_url.split("/")[-1]).write_bytes(silent.getvalue())
        self.assertEqual(self.client.post(self.publish, {"audio_url":self.original.audio_url}).status_code,409)
        self.assertEqual(self.reader.get(published_url(1,"content",published)).content,self.mp3)
