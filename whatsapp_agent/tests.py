import json
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from lessons.models import UserProfile
from whatsapp_agent.models import WhatsAppAgentEvent, WhatsAppLead, WhatsAppMessage
from whatsapp_agent.services import (
    WhatsAppAPIError,
    provision_course_access_for_lead,
    send_whatsapp_template,
    send_whatsapp_text,
)


@override_settings(
    WHATSAPP_WEBHOOK_VERIFY_TOKEN="verify-me",
    WHATSAPP_ACCESS_TOKEN="token",
    WHATSAPP_PHONE_NUMBER_ID="1086276117905375",
    TELEGRAM_BOT_TOKEN="telegram-token",
    TELEGRAM_CHAT_ID="8409596705",
    APP_BASE_URL="https://www.oqyai.kz",
    KASPI_RECEIVER_PHONE="+77472445338",
    KASPI_RECEIVER_NAME="Әбдірайым Жақсылық Байсафарұлы",
    COURSE_PRICE_KZT=25000,
    OPENAI_API_KEY="test-openai-key",
)
class WhatsAppWebhookTests(TestCase):
    def _build_text_payload(self, body, *, message_id="wamid-1", from_wa_id="77781029394", profile_name="Aruzhan"):
        return {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [
                                    {
                                        "wa_id": from_wa_id,
                                        "profile": {"name": profile_name},
                                    }
                                ],
                                "messages": [
                                    {
                                        "id": message_id,
                                        "from": from_wa_id,
                                        "timestamp": "1710000000",
                                        "type": "text",
                                        "text": {"body": body},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

    def test_webhook_verification_succeeds(self):
        response = self.client.get(
            reverse("whatsapp_webhook"),
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "abc123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "abc123")

    def test_webhook_verification_rejects_bad_token(self):
        response = self.client.get(
            reverse("whatsapp_webhook"),
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "bad-token",
                "hub.challenge": "abc123",
            },
        )
        self.assertEqual(response.status_code, 403)

    @patch("whatsapp_agent.services.send_telegram_alert")
    @patch("whatsapp_agent.services.send_whatsapp_text")
    def test_buying_intent_message_creates_lead_and_replies(self, mock_send_whatsapp, mock_send_telegram):
        payload = self._build_text_payload(
            "Қалай сатып аламын?",
            from_wa_id="77471095715",
        )

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        lead = WhatsAppLead.objects.get(phone_number="+77471095715")
        self.assertEqual(lead.status, "payment_intent")
        self.assertEqual(lead.language_preference, "kk")
        self.assertEqual(lead.last_intent, "buying_intent")
        self.assertTrue(WhatsAppMessage.objects.filter(meta_message_id="wamid-1").exists())
        mock_send_whatsapp.assert_called_once()
        mock_send_telegram.assert_called_once()

    @patch("whatsapp_agent.services.requests.post")
    @patch("whatsapp_agent.services.OpenAI")
    def test_general_inbound_text_calls_openai_sends_reply_and_records_outbound(self, mock_openai, mock_post):
        mock_openai.return_value.responses.create.return_value = MagicMock(
            output_text=(
                "Сәлеметсіз бе 😊 OqyAI-де 250 дайын ағылшын сабағы бар.\n\n"
                "Қай деңгейден бастағыңыз келеді?"
            )
        )
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = '{"messages":[{"id":"wamid-out-1"}]}'
        mock_post.return_value.json.return_value = {"messages": [{"id": "wamid-out-1"}]}

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(self._build_text_payload("Сәлем", message_id="wamid-in-1")),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        lead = WhatsAppLead.objects.get(phone_number="+77781029394")
        self.assertEqual(lead.status, "engaged")
        self.assertEqual(lead.last_intent, "general")
        self.assertEqual(lead.metadata["last_inbound_wa_id"], "77781029394")
        self.assertEqual(lead.message_count, 1)

        inbound = WhatsAppMessage.objects.get(meta_message_id="wamid-in-1")
        self.assertEqual(inbound.direction, "inbound")
        self.assertEqual(inbound.text_content, "Сәлем")

        outbound = WhatsAppMessage.objects.get(meta_message_id="wamid-out-1")
        self.assertEqual(outbound.direction, "outbound")
        self.assertEqual(outbound.message_type, "text")
        self.assertFalse(outbound.failed)
        self.assertIn("Қай деңгейден бастағыңыз келеді?", outbound.text_content)
        self.assertEqual(outbound.raw_payload["request"]["to"], "77781029394")

        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(mock_post.call_args.kwargs["json"]["to"], "77781029394")
        self.assertEqual(
            mock_openai.return_value.responses.create.call_args.kwargs["model"],
            "gpt-5",
        )
        self.assertIn(
            "user: Сәлем",
            mock_openai.return_value.responses.create.call_args.kwargs["input"],
        )

        event = WhatsAppAgentEvent.objects.get(event_type="whatsapp_send_success")
        self.assertEqual(event.payload["message_id"], "wamid-out-1")
        self.assertEqual(event.payload["to"], "77781029394")

    @patch("whatsapp_agent.services.send_telegram_alert")
    @patch("whatsapp_agent.services.requests.post")
    @patch("whatsapp_agent.services.OpenAI")
    def test_openai_failure_uses_fallback_and_logs_error_event(
        self,
        mock_openai,
        mock_post,
        mock_send_telegram,
    ):
        mock_openai.return_value.responses.create.side_effect = RuntimeError("OpenAI boom")
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = '{"messages":[{"id":"wamid-out-2"}]}'
        mock_post.return_value.json.return_value = {"messages": [{"id": "wamid-out-2"}]}

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(self._build_text_payload("Бағасы қанша?", message_id="wamid-in-2")),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        outbound = WhatsAppMessage.objects.get(meta_message_id="wamid-out-2")
        self.assertTrue(outbound.text_content.startswith("Көмектесемін."))
        mock_send_telegram.assert_called_once()

        event = WhatsAppAgentEvent.objects.get(event_type="openai_failure")
        self.assertIn("OpenAI boom", event.payload["error"])
        self.assertEqual(event.payload["model"], "gpt-5")

    @patch("whatsapp_agent.services.send_telegram_alert")
    @patch("whatsapp_agent.services.requests.post")
    @patch("whatsapp_agent.services.OpenAI")
    def test_whatsapp_send_failure_logs_full_meta_error_and_records_failed_outbound(
        self,
        mock_openai,
        mock_post,
        mock_send_telegram,
    ):
        mock_openai.return_value.responses.create.return_value = MagicMock(output_text="Сәлем! 😊")
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = '{"error":{"message":"Outside 24-hour window","code":131047}}'
        mock_post.return_value.json.return_value = {
            "error": {
                "message": "Outside 24-hour window",
                "code": 131047,
            }
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(self._build_text_payload("Сәлем", message_id="wamid-in-3")),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        failed_outbound = WhatsAppMessage.objects.get(direction="outbound")
        self.assertTrue(failed_outbound.failed)
        self.assertEqual(failed_outbound.text_content, "Сәлем! 😊")
        self.assertEqual(failed_outbound.raw_payload["parsed_json_error"]["code"], 131047)
        self.assertIn("Outside 24-hour window", failed_outbound.raw_payload["response_text"])

        event = WhatsAppAgentEvent.objects.get(event_type="whatsapp_send_failed")
        self.assertEqual(event.payload["status_code"], 400)
        self.assertIn("Outside 24-hour window", event.payload["response_text"])
        self.assertEqual(event.payload["parsed_json_error"]["code"], 131047)
        self.assertTrue(WhatsAppAgentEvent.objects.filter(event_type="webhook_message_failed").exists())
        mock_send_telegram.assert_called_once()


@override_settings(
    APP_BASE_URL="https://www.oqyai.kz",
    OPENAI_API_KEY="test-openai-key",
)
class ProvisioningTests(TestCase):
    def test_provision_course_access_links_existing_profile_by_phone(self):
        user = User.objects.create_user(username="existing", password="old-password")
        profile = UserProfile.objects.create(user=user, phone="+77011234567", is_paid=False, role="student")
        lead = WhatsAppLead.objects.create(phone_number="+77011234567", first_name="Aliya")

        result = provision_course_access_for_lead(lead)

        profile.refresh_from_db()
        lead.refresh_from_db()
        self.assertFalse(result["created"])
        self.assertTrue(profile.is_paid)
        self.assertTrue(lead.paid_access_granted)
        self.assertTrue(lead.existing_user_linked)

    def test_provision_course_access_creates_new_user_when_phone_missing(self):
        lead = WhatsAppLead.objects.create(
            phone_number="+77017654321",
            first_name="Dias",
            metadata={"profile_name": "Dias Sapar"},
        )

        result = provision_course_access_for_lead(lead)

        lead.refresh_from_db()
        self.assertTrue(result["created"])
        self.assertTrue(result["password"])
        self.assertTrue(UserProfile.objects.filter(user=result["user"], phone="+77017654321", is_paid=True).exists())
        self.assertTrue(lead.paid_access_granted)


@override_settings(
    WHATSAPP_ACCESS_TOKEN="test-token",
    WHATSAPP_PHONE_NUMBER_ID="1086276117905375",
    WHATSAPP_GRAPH_API_VERSION="v23.0",
    OPENAI_API_KEY="test-openai-key",
)
class WhatsAppRegisterPhoneCommandTests(TestCase):
    @patch("whatsapp_agent.management.commands.whatsapp_register_phone.requests.post")
    def test_register_phone_command_posts_expected_payload(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = '{"success":true}'
        mock_post.return_value.json.return_value = {"success": True}

        stdout = StringIO()
        call_command("whatsapp_register_phone", "--pin", "123456", stdout=stdout)

        mock_post.assert_called_once_with(
            "https://graph.facebook.com/v23.0/1086276117905375/register",
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "pin": "123456",
            },
            timeout=30,
        )
        output = stdout.getvalue()
        self.assertIn("HTTP 200", output)
        self.assertIn('{"success":true}', output)

    def test_register_phone_command_rejects_non_six_digit_pin(self):
        with self.assertRaises(CommandError):
            call_command("whatsapp_register_phone", "--pin", "12345")

    @patch("whatsapp_agent.management.commands.whatsapp_register_phone.requests.post")
    def test_register_phone_command_surfaces_non_2xx_error_details(self, mock_post):
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = '{"error":{"message":"Invalid parameter","code":100}}'
        mock_post.return_value.json.return_value = {
            "error": {
                "message": "Invalid parameter",
                "code": 100,
            }
        }

        with self.assertRaises(CommandError) as exc_info:
            call_command("whatsapp_register_phone", "--pin", "123456")

        self.assertIn("HTTP 400", str(exc_info.exception))
        self.assertIn("response.text=", str(exc_info.exception))
        self.assertIn("parsed_json_error=", str(exc_info.exception))


@override_settings(
    WHATSAPP_ACCESS_TOKEN="test-token",
    WHATSAPP_PHONE_NUMBER_ID="1086276117905375",
    WHATSAPP_GRAPH_API_VERSION="v23.0",
    OPENAI_API_KEY="test-openai-key",
)
class WhatsAppSendTests(TestCase):
    def _mock_meta_response(self, status_code, body, parsed_json):
        response = MagicMock()
        response.status_code = status_code
        response.text = body
        response.json.return_value = parsed_json
        return response

    @patch("whatsapp_agent.services.requests.post")
    def test_send_whatsapp_text_keeps_safe_normalization_for_real_numbers(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = '{"messages":[{"id":"wamid-text"}]}'
        mock_post.return_value.json.return_value = {"messages": [{"id": "wamid-text"}]}

        response = send_whatsapp_text("87011234567", "Salem")

        self.assertEqual(response["messages"][0]["id"], "wamid-text")
        self.assertEqual(mock_post.call_args.kwargs["json"]["to"], "77011234567")

    @patch("whatsapp_agent.services.requests.post")
    def test_send_whatsapp_text_retries_131030_with_sandbox_recipient(self, mock_post):
        lead = WhatsAppLead.objects.create(
            phone_number="+77781029394",
            metadata={
                "last_inbound_wa_id": "77781029394",
                "sandbox_test_recipient": "787781029394",
            },
        )
        mock_post.side_effect = [
            self._mock_meta_response(
                400,
                '{"error":{"message":"(#131030) Recipient phone number not in allowed list","code":131030}}',
                {
                    "error": {
                        "message": "(#131030) Recipient phone number not in allowed list",
                        "code": 131030,
                    }
                },
            ),
            self._mock_meta_response(
                200,
                '{"messages":[{"id":"wamid-fallback"}]}',
                {"messages": [{"id": "wamid-fallback"}]},
            ),
        ]

        response = send_whatsapp_text("77781029394", "Salem", lead=lead)

        self.assertEqual(response["messages"][0]["id"], "wamid-fallback")
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_post.call_args_list[0].kwargs["json"]["to"], "77781029394")
        self.assertEqual(mock_post.call_args_list[1].kwargs["json"]["to"], "787781029394")

        outbound = WhatsAppMessage.objects.get(meta_message_id="wamid-fallback")
        self.assertEqual(outbound.direction, "outbound")
        self.assertFalse(outbound.failed)
        self.assertEqual(outbound.raw_payload["request"]["to"], "787781029394")
        self.assertEqual(outbound.raw_payload["retry"]["original_recipient"], "77781029394")
        self.assertEqual(outbound.raw_payload["retry"]["fallback_recipient"], "787781029394")

        retry_events = list(
            WhatsAppAgentEvent.objects.filter(event_type="whatsapp_send_retry_fallback").order_by("created_at", "id")
        )
        self.assertEqual([event.payload["status"] for event in retry_events], ["attempting", "succeeded"])
        success_event = WhatsAppAgentEvent.objects.get(event_type="whatsapp_send_success")
        self.assertEqual(success_event.payload["to"], "787781029394")
        self.assertEqual(success_event.payload["retry"]["first_error"]["status_code"], 400)

    @patch("whatsapp_agent.services.requests.post")
    def test_send_whatsapp_text_does_not_retry_non_131030(self, mock_post):
        lead = WhatsAppLead.objects.create(
            phone_number="+77781029394",
            metadata={
                "last_inbound_wa_id": "77781029394",
                "sandbox_test_recipient": "787781029394",
            },
        )
        mock_post.return_value = self._mock_meta_response(
            400,
            '{"error":{"message":"Outside 24-hour window","code":131047}}',
            {
                "error": {
                    "message": "Outside 24-hour window",
                    "code": 131047,
                }
            },
        )

        with self.assertRaises(WhatsAppAPIError):
            send_whatsapp_text("77781029394", "Salem", lead=lead)

        self.assertEqual(mock_post.call_count, 1)
        self.assertFalse(WhatsAppAgentEvent.objects.filter(event_type="whatsapp_send_retry_fallback").exists())
        failed_outbound = WhatsAppMessage.objects.get(direction="outbound")
        self.assertTrue(failed_outbound.failed)
        self.assertEqual(failed_outbound.raw_payload["request"]["to"], "77781029394")
        self.assertEqual(failed_outbound.raw_payload["parsed_json_error"]["code"], 131047)

    @patch("whatsapp_agent.services.requests.post")
    def test_send_whatsapp_text_records_final_failure_when_sandbox_retry_fails(self, mock_post):
        lead = WhatsAppLead.objects.create(
            phone_number="+77781029394",
            metadata={"last_inbound_wa_id": "77781029394"},
        )
        mock_post.side_effect = [
            self._mock_meta_response(
                400,
                '{"error":{"message":"(#131030) Recipient phone number not in allowed list","code":131030}}',
                {
                    "error": {
                        "message": "(#131030) Recipient phone number not in allowed list",
                        "code": 131030,
                    }
                },
            ),
            self._mock_meta_response(
                400,
                '{"error":{"message":"Fallback recipient also rejected","code":131030}}',
                {
                    "error": {
                        "message": "Fallback recipient also rejected",
                        "code": 131030,
                    }
                },
            ),
        ]

        with self.assertRaises(WhatsAppAPIError):
            send_whatsapp_text("77781029394", "Salem", lead=lead)

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_post.call_args_list[1].kwargs["json"]["to"], "787781029394")
        failed_outbound = WhatsAppMessage.objects.get(direction="outbound")
        self.assertTrue(failed_outbound.failed)
        self.assertEqual(failed_outbound.raw_payload["request"]["to"], "787781029394")
        self.assertEqual(failed_outbound.raw_payload["retry"]["original_recipient"], "77781029394")
        self.assertEqual(failed_outbound.raw_payload["parsed_json_error"]["message"], "Fallback recipient also rejected")

        retry_statuses = [
            event.payload["status"]
            for event in WhatsAppAgentEvent.objects.filter(event_type="whatsapp_send_retry_fallback").order_by(
                "created_at",
                "id",
            )
        ]
        self.assertEqual(retry_statuses, ["attempting", "failed"])
        failure_event = WhatsAppAgentEvent.objects.get(event_type="whatsapp_send_failed")
        self.assertEqual(failure_event.payload["to"], "787781029394")
        self.assertEqual(failure_event.payload["retry"]["first_error"]["parsed_json_error"]["code"], 131030)

    @patch("whatsapp_agent.services.requests.post")
    def test_send_whatsapp_template_uses_raw_meta_test_recipient_input(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = '{"messages":[{"id":"wamid-template"}]}'
        mock_post.return_value.json.return_value = {"messages": [{"id": "wamid-template"}]}

        response = send_whatsapp_template("787781029394")

        self.assertEqual(response["messages"][0]["id"], "wamid-template")
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["to"], "787781029394")
        self.assertEqual(payload["type"], "template")
        self.assertEqual(payload["template"]["name"], "hello_world")
        self.assertEqual(payload["template"]["language"]["code"], "en_US")

    @patch("whatsapp_agent.services.requests.post")
    def test_send_whatsapp_template_surfaces_non_2xx_error_details(self, mock_post):
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = '{"error":{"message":"(#131030) Recipient phone number not in allowed list"}}'
        mock_post.return_value.json.return_value = {
            "error": {
                "message": "(#131030) Recipient phone number not in allowed list",
                "code": 131030,
            }
        }

        with self.assertRaises(WhatsAppAPIError) as exc_info:
            send_whatsapp_template("77781029394")

        error = exc_info.exception
        self.assertEqual(error.status_code, 400)
        self.assertIn("response.text=", str(error))
        self.assertIn("parsed_json_error=", str(error))
        event = WhatsAppAgentEvent.objects.get(event_type="whatsapp_template_send_failed")
        self.assertEqual(event.payload["status_code"], 400)
        self.assertIn("Recipient phone number not in allowed list", event.payload["response_text"])
        self.assertEqual(event.payload["parsed_json_error"]["code"], 131030)


@override_settings(OPENAI_API_KEY="test-openai-key")
class WhatsAppTestSendCommandTests(TestCase):
    @patch("whatsapp_agent.management.commands.whatsapp_test_send.send_whatsapp_template")
    def test_test_send_command_supports_template_send(self, mock_send_template):
        mock_send_template.return_value = {"messages": [{"id": "wamid-template"}]}

        stdout = StringIO()
        call_command(
            "whatsapp_test_send",
            "--to",
            "787781029394",
            "--template",
            "hello_world",
            stdout=stdout,
        )

        mock_send_template.assert_called_once_with(
            "787781029394",
            template_name="hello_world",
            language_code="en_US",
        )
        self.assertIn("wamid-template", stdout.getvalue())

    def test_test_send_command_requires_exactly_one_message_mode(self):
        with self.assertRaises(CommandError):
            call_command("whatsapp_test_send", "--to", "787781029394")

        with self.assertRaises(CommandError):
            call_command(
                "whatsapp_test_send",
                "--to",
                "787781029394",
                "--text",
                "hi",
                "--template",
                "hello_world",
            )
