import json
import logging
import mimetypes
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from openai import OpenAI

from lessons.models import UserProfile

from .models import WhatsAppAgentEvent, WhatsAppLead, WhatsAppMessage, WhatsAppReceipt
from .utils import (
    analyze_receipt_text,
    build_base_username,
    clip_text,
    detect_intent,
    detect_language,
    extract_receipt_text,
    generate_password,
    normalize_phone_number,
    parse_meta_timestamp,
    resolve_outbound_whatsapp_recipient,
)


logger = logging.getLogger(__name__)

APPLE_APP_URL = "https://apps.apple.com/us/app/oqyai/id6754454949"
ANDROID_APP_URL = "https://play.google.com/store/apps/details?id=com.oqyai.app"


class WhatsAppAPIError(RuntimeError):
    def __init__(self, action, status_code=None, response_text="", response_json=None):
        self.action = action
        self.status_code = status_code
        self.response_text = (response_text or "").strip()
        self.response_json = response_json
        self.parsed_error = response_json.get("error") if isinstance(response_json, dict) else response_json

        parts = [f"{action} failed"]
        if status_code is not None:
            parts.append(f"HTTP {status_code}")
        if self.response_text:
            parts.append(f"response.text={self.response_text}")
        if self.parsed_error is not None:
            parts.append(
                "parsed_json_error="
                + json.dumps(self.parsed_error, ensure_ascii=False, default=str)
            )
        elif response_json is not None:
            parts.append(
                "response_json="
                + json.dumps(response_json, ensure_ascii=False, default=str)
            )

        super().__init__(". ".join(parts))


def _safe_payload(payload):
    return json.loads(json.dumps(payload or {}, default=str))


def log_agent_event(event_type, lead=None, payload=None):
    return WhatsAppAgentEvent.objects.create(
        lead=lead,
        event_type=event_type,
        payload=_safe_payload(payload),
    )


def _current_customer_name(lead):
    metadata = lead.metadata or {}
    return metadata.get("profile_name") or lead.first_name or "Unknown"


def _build_admin_alert(lead, event_name, latest_message="", receipt_attached=False, human_attention=False, extra_lines=None):
    lines = [
        f"OqyAI WhatsApp alert: {event_name}",
        f"Customer: {_current_customer_name(lead)}",
        f"Phone: {lead.phone_number}",
        f"Intent: {lead.last_intent or 'unknown'}",
        f"Lead status: {lead.status}",
        f"Receipt attached: {'yes' if receipt_attached else 'no'}",
        f"Paid access granted: {'yes' if lead.paid_access_granted else 'no'}",
        f"Human attention: {'yes' if human_attention else 'no'}",
    ]
    if latest_message:
        lines.append(f"Latest message: {clip_text(latest_message)}")
    for line in extra_lines or []:
        if line:
            lines.append(line)
    return "\n".join(lines)


def send_telegram_alert(text, lead=None, event_type="general", dedupe_key=None, payload=None, window_minutes=15):
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", "")
    event_name = f"telegram_alert:{event_type}"
    dedupe_key = dedupe_key or event_type
    cutoff = timezone.now() - timedelta(minutes=window_minutes)

    recent_events = WhatsAppAgentEvent.objects.filter(
        event_type=event_name,
        created_at__gte=cutoff,
    )
    if lead:
        recent_events = recent_events.filter(lead=lead)

    for event in recent_events.only("payload"):
        if (event.payload or {}).get("dedupe_key") == dedupe_key:
            return False

    if not token or not chat_id:
        log_agent_event(
            "telegram_alert_skipped",
            lead=lead,
            payload={"event_type": event_type, "dedupe_key": dedupe_key, "reason": "missing_config"},
        )
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Telegram alert failed for %s", event_type)
        log_agent_event(
            "telegram_alert_failed",
            lead=lead,
            payload={"event_type": event_type, "dedupe_key": dedupe_key, "error": str(exc)},
        )
        return False

    log_agent_event(
        event_name,
        lead=lead,
        payload={**_safe_payload(payload), "dedupe_key": dedupe_key},
    )
    return True


def _whatsapp_api_url(path_suffix):
    version = getattr(settings, "WHATSAPP_GRAPH_API_VERSION", "v23.0")
    return f"https://graph.facebook.com/{version}/{path_suffix}"


def _parse_response_json(response):
    try:
        return response.json()
    except ValueError:
        return None


def _raise_whatsapp_api_error(response, *, action, lead=None, event_type, payload=None):
    response_json = _parse_response_json(response)
    response_text = (response.text or "").strip()
    parsed_error = response_json.get("error") if isinstance(response_json, dict) else response_json

    logger.error(
        "%s failed with HTTP %s. response.text=%s parsed_json_error=%s",
        action,
        response.status_code,
        clip_text(response_text or "<empty>", 1000),
        parsed_error,
    )
    log_agent_event(
        event_type,
        lead=lead,
        payload={
            **_safe_payload(payload),
            "status_code": response.status_code,
            "response_text": response_text,
            "response_json": response_json,
            "parsed_json_error": parsed_error,
        },
    )
    raise WhatsAppAPIError(
        action=action,
        status_code=response.status_code,
        response_text=response_text,
        response_json=response_json,
    )


def _send_whatsapp_payload(
    *,
    to_phone,
    request_payload,
    lead=None,
    success_event_type,
    failure_event_type,
    success_payload=None,
    message_text="",
    outbound_message_type=None,
):
    access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    if not access_token or not phone_number_id:
        raise RuntimeError("WhatsApp Cloud API settings are missing")

    request_url = _whatsapp_api_url(f"{phone_number_id}/messages")
    try:
        response = requests.post(
            request_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.exception("Failed to send WhatsApp message to %s", to_phone)
        log_agent_event(
            failure_event_type,
            lead=lead,
            payload={
                "to": to_phone,
                "request_payload": request_payload,
                "error": str(exc),
            },
        )
        raise

    if not 200 <= response.status_code < 300:
        _raise_whatsapp_api_error(
            response,
            action=f"WhatsApp {request_payload.get('type') or 'message'} send to {to_phone}",
            lead=lead,
            event_type=failure_event_type,
            payload={
                "to": to_phone,
                "request_url": request_url,
                "request_payload": request_payload,
            },
        )

    data = _parse_response_json(response) or {}

    message_id = ((data.get("messages") or [{}])[0]).get("id", "")
    if lead:
        if outbound_message_type:
            WhatsAppMessage.objects.create(
                lead=lead,
                meta_message_id=message_id,
                direction="outbound",
                message_type=outbound_message_type,
                text_content=message_text,
                raw_payload={"request": request_payload, "response": data},
            )
        lead.last_bot_message_at = timezone.now()
        lead.save(update_fields=["last_bot_message_at", "updated_at"])

    log_agent_event(
        success_event_type,
        lead=lead,
        payload={
            "to": to_phone,
            "message_id": message_id,
            **_safe_payload(success_payload),
        },
    )
    return data


def send_whatsapp_text(to_phone, text, lead=None):
    request_payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": resolve_outbound_whatsapp_recipient(to_phone),
        "type": "text",
        "text": {
            "preview_url": False,
            "body": (text or "").strip()[:4096],
        },
    }
    return _send_whatsapp_payload(
        to_phone=to_phone,
        request_payload=request_payload,
        lead=lead,
        success_event_type="whatsapp_send_success",
        failure_event_type="whatsapp_send_failed",
        message_text=text,
        outbound_message_type="text",
    )


def send_whatsapp_template(to_phone, template_name="hello_world", language_code="en_US", lead=None):
    template_name = (template_name or "hello_world").strip()
    language_code = (language_code or "en_US").strip()
    request_payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": resolve_outbound_whatsapp_recipient(to_phone, prefer_exact_input=True),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code,
            },
        },
    }
    return _send_whatsapp_payload(
        to_phone=to_phone,
        request_payload=request_payload,
        lead=lead,
        success_event_type="whatsapp_template_send_success",
        failure_event_type="whatsapp_template_send_failed",
        success_payload={
            "template_name": template_name,
            "language_code": language_code,
        },
    )


def download_whatsapp_media(media_id):
    access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    if not access_token:
        raise RuntimeError("WhatsApp access token is missing")

    headers = {"Authorization": f"Bearer {access_token}"}
    meta_response = requests.get(_whatsapp_api_url(media_id), headers=headers, timeout=20)
    if not 200 <= meta_response.status_code < 300:
        _raise_whatsapp_api_error(
            meta_response,
            action=f"WhatsApp media metadata fetch for {media_id}",
            event_type="whatsapp_media_metadata_failed",
            payload={"media_id": media_id},
        )
    metadata = _parse_response_json(meta_response) or {}

    file_response = requests.get(metadata["url"], headers=headers, timeout=30)
    if not 200 <= file_response.status_code < 300:
        _raise_whatsapp_api_error(
            file_response,
            action=f"WhatsApp media download for {media_id}",
            event_type="whatsapp_media_download_failed",
            payload={"media_id": media_id, "metadata": metadata},
        )

    mime_type = metadata.get("mime_type") or "application/octet-stream"
    extension = mimetypes.guess_extension(mime_type) or ""
    filename = metadata.get("id", media_id)
    if extension and not filename.endswith(extension):
        filename = f"{filename}{extension}"

    return {
        "content": file_response.content,
        "mime_type": mime_type,
        "filename": filename,
        "metadata": metadata,
    }


def _resolve_reply_language(lead):
    return lead.language_preference if lead.language_preference in {"kk", "ru"} else "kk"


def _build_payment_reply(lead):
    amount = getattr(settings, "COURSE_PRICE_KZT", 25000)
    phone = getattr(settings, "KASPI_RECEIVER_PHONE", "+77472445338")
    name = getattr(settings, "KASPI_RECEIVER_NAME", "Әбдірайым Жақсылық Байсафарұлы")
    if _resolve_reply_language(lead) == "ru":
        return (
            f"В OqyAI есть 250 готовых уроков английского. Сам курс на казахском языке, и он подходит даже новичкам.\n\n"
            f"Цена: {amount} KZT. Оплата через Kaspi transfer:\n{phone}\n{name}\n\n"
            f"После оплаты отправьте чек сюда."
        )
    return (
        f"OqyAI-де 250 дайын ағылшын сабағы бар. Курс beginners-ке де ыңғайлы, нөлден бастауға болады.\n\n"
        f"Бағасы: {amount} KZT. Төлем Kaspi transfer арқылы:\n{phone}\n{name}\n\n"
        f"Төлем жасағаннан кейін чекті осы чатқа жіберіңіз."
    )


def _build_receipt_prompt_reply(lead):
    if _resolve_reply_language(lead) == "ru":
        return "Если оплата уже сделана, просто отправьте сюда чек или PDF."
    return "Егер төлем жасалған болса, чекті немесе PDF-ті осы чатқа жібере салыңыз."


def _build_handoff_reply(lead):
    if _resolve_reply_language(lead) == "ru":
        return "Сообщение передано человеку. Он посмотрит и вернется сюда."
    return "Хабарламаңыз адамға жіберілді. Қарап шығып, осы чатқа жауап береді."


def _build_wait_reply(lead):
    if _resolve_reply_language(lead) == "ru":
        return "Чек получил. Проверка пока не завершена, админ посмотрит и вернется сюда."
    return "Чекті алдым. Тексеру толық аяқталмағандықтан, админ қарап шығады."


def _build_fallback_reply(lead):
    if _resolve_reply_language(lead) == "ru":
        return "Помогу. Напишите коротко, что именно вас интересует: курс, цена или оплата. Сам курс на казахском языке."
    return "Көмектесемін. Қысқаша жазыңызшы: курс, баға немесе төлем туралы ма?"


def _build_success_reply(lead, provision_result):
    app_base_url = getattr(settings, "APP_BASE_URL", "https://www.oqyai.kz").rstrip("/")
    username = provision_result["user"].username
    if provision_result["created"]:
        if _resolve_reply_language(lead) == "ru":
            return (
                "Оплата подтверждена. Доступ к курсу открыт.\n\n"
                f"Логин: {username}\n"
                f"Пароль: {provision_result['password']}\n"
                f"Вход: {app_base_url}/login/\n\n"
                f"iPhone: {APPLE_APP_URL}\n"
                f"Android: {ANDROID_APP_URL}"
            )
        return (
            "Төлем расталды. Курсқа қолжетімділік ашылды.\n\n"
            f"Логин: {username}\n"
            f"Құпиясөз: {provision_result['password']}\n"
            f"Кіру: {app_base_url}/login/\n\n"
            f"iPhone: {APPLE_APP_URL}\n"
            f"Android: {ANDROID_APP_URL}"
        )

    if _resolve_reply_language(lead) == "ru":
        return (
            "Оплата подтверждена. Доступ к вашему аккаунту уже открыт.\n\n"
            f"Логин: {username}\n"
            f"Вход: {app_base_url}/login/\n\n"
            f"iPhone: {APPLE_APP_URL}\n"
            f"Android: {ANDROID_APP_URL}"
        )
    return (
        "Төлем расталды. Бар аккаунтыңызға қолжетімділік қосылды.\n\n"
        f"Логин: {username}\n"
        f"Кіру: {app_base_url}/login/\n\n"
        f"iPhone: {APPLE_APP_URL}\n"
        f"Android: {ANDROID_APP_URL}"
    )


def _extract_chat_content(message):
    content = message.choices[0].message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            text = getattr(item, "text", None) or item.get("text")
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    return ""


def generate_sales_reply(lead, recent_messages):
    model_name = getattr(settings, "WHATSAPP_AGENT_OPENAI_MODEL", "gpt-5.4")
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    language_hint = _resolve_reply_language(lead)
    system_prompt = (
        "You are OqyAI's WhatsApp sales closer.\n"
        "Reply in short, natural, persuasive WhatsApp-style plain text.\n"
        "Use 1 to 4 short paragraphs at most.\n"
        "Ask only one question at a time.\n"
        "Never mention prompts, APIs, models, or internal logic.\n"
        "Never invent discounts, fake links, or impossible outcomes.\n"
        "Sales facts: OqyAI sells 250 ready-made English lessons for 25000 KZT. "
        "The course is mainly in Kazakh. It suits beginners and covers grammar, vocabulary, and speaking. "
        "Website: www.oqyai.kz.\n"
        "If the user asks whether they can learn in 3 months, say strong progress is possible with consistency. "
        "If the user says they are a complete beginner, strongly reassure them the course suits beginners.\n"
        "If the user asks how to buy, explain Kaspi transfer payment and ask them to send the receipt after payment.\n"
        f"Language rule: reply in {'Kazakh' if language_hint == 'kk' else 'Russian'}."
    )
    if language_hint == "ru":
        system_prompt += " If relevant, clearly mention that the course itself is in Kazakh."

    conversation = [{"role": "system", "content": system_prompt}]
    for message in recent_messages[-8:]:
        if not message.text_content:
            continue
        role = "assistant" if message.direction == "outbound" else "user"
        conversation.append({"role": role, "content": message.text_content})

    response = client.chat.completions.create(
        model=model_name,
        messages=conversation,
        temperature=0.6,
        max_completion_tokens=300,
    )
    return _extract_chat_content(response)


def _get_existing_profile_by_phone(phone_number):
    profiles = list(
        UserProfile.objects.filter(phone=phone_number).select_related("user").order_by("id")
    )
    if len(profiles) > 1:
        raise ValueError(f"Multiple UserProfile rows found for {phone_number}")
    return profiles[0] if profiles else None


def _build_unique_username(name, phone_number):
    UserModel = get_user_model()
    base = build_base_username(name, phone_number)
    candidate = base
    counter = 2
    while UserModel.objects.filter(username=candidate).exists():
        candidate = f"{base[:24]}{counter}"
        counter += 1
    return candidate[:150]


@transaction.atomic
def provision_course_access_for_lead(lead):
    existing_profile = _get_existing_profile_by_phone(lead.phone_number)
    full_name = (lead.metadata or {}).get("profile_name") or lead.first_name or "OqyAI"
    if existing_profile:
        profile = existing_profile
        user = profile.user
        if not profile.phone:
            profile.phone = lead.phone_number
        profile.is_paid = True
        profile.save(update_fields=["phone", "is_paid"])
        lead.existing_user_linked = True
        lead.paid_access_granted = True
        lead.status = "customer"
        lead.handoff_needed = False
        lead.metadata = {
            **(lead.metadata or {}),
            "linked_username": user.username,
        }
        lead.save(
            update_fields=[
                "existing_user_linked",
                "paid_access_granted",
                "status",
                "handoff_needed",
                "metadata",
                "updated_at",
            ]
        )
        return {"created": False, "user": user, "profile": profile, "password": None}

    UserModel = get_user_model()
    password = generate_password()
    username = _build_unique_username(full_name, lead.phone_number)
    user = UserModel.objects.create_user(
        username=username,
        password=password,
        first_name=full_name[:150],
    )
    profile = UserProfile.objects.create(
        user=user,
        phone=lead.phone_number,
        role="student",
        is_paid=True,
    )
    lead.existing_user_linked = False
    lead.paid_access_granted = True
    lead.status = "customer"
    lead.handoff_needed = False
    lead.metadata = {
        **(lead.metadata or {}),
        "linked_username": user.username,
    }
    lead.save(
        update_fields=[
            "existing_user_linked",
            "paid_access_granted",
            "status",
            "handoff_needed",
            "metadata",
            "updated_at",
        ]
    )
    return {"created": True, "user": user, "profile": profile, "password": password}


def _sync_existing_user_flag(lead):
    try:
        profile = _get_existing_profile_by_phone(lead.phone_number)
    except ValueError:
        lead.handoff_needed = True
        lead.save(update_fields=["handoff_needed", "updated_at"])
        return
    linked = bool(profile)
    if lead.existing_user_linked != linked:
        lead.existing_user_linked = linked
        lead.save(update_fields=["existing_user_linked", "updated_at"])


def _message_file_type(message):
    if message.message_type == "image":
        return "image"
    if message.message_type == "document" and message.media_mime_type == "application/pdf":
        return "pdf"
    if message.message_type == "document" and message.media_mime_type.startswith("image/"):
        return "image"
    return "unknown"


def create_receipt_from_message(lead, message):
    media = download_whatsapp_media(message.media_id)
    receipt = WhatsAppReceipt.objects.create(
        lead=lead,
        message=message,
        file_type=_message_file_type(message),
    )
    filename = media["filename"] or f"{message.media_id}.bin"
    receipt.file.save(filename, ContentFile(media["content"]), save=False)
    receipt.save()
    return receipt


def evaluate_receipt(receipt):
    expected_amount = getattr(settings, "COURSE_PRICE_KZT", 25000)
    expected_phone = getattr(settings, "KASPI_RECEIVER_PHONE", "+77472445338")
    expected_name = getattr(settings, "KASPI_RECEIVER_NAME", "Әбдірайым Жақсылық Байсафарұлы")

    extracted_text = extract_receipt_text(receipt.file.path, receipt.file_type) if receipt.file else ""
    analysis = analyze_receipt_text(extracted_text, expected_amount, expected_phone, expected_name)

    receipt.extracted_text = extracted_text
    receipt.amount_detected = analysis["amount_detected"]
    receipt.receiver_phone_detected = analysis["receiver_phone_detected"]
    receipt.receiver_name_detected = analysis["receiver_name_detected"]
    receipt.timestamp_detected = analysis["timestamp_detected"]
    receipt.validation_confidence = analysis["validation_confidence"]
    receipt.is_validated = analysis["is_validated"]
    receipt.validation_notes = analysis["validation_notes"]
    receipt.save()
    return analysis


def finalize_receipt(receipt, notify_user=True):
    lead = receipt.lead
    if receipt.is_validated:
        try:
            provision_result = provision_course_access_for_lead(lead)
        except Exception as exc:
            logger.exception("Failed to provision paid access from receipt %s", receipt.pk)
            lead.handoff_needed = True
            lead.status = "receipt_received"
            lead.save(update_fields=["handoff_needed", "status", "updated_at"])
            send_telegram_alert(
                _build_admin_alert(
                    lead,
                    "critical automation failure",
                    latest_message=receipt.message.text_content if receipt.message else "",
                    receipt_attached=True,
                    human_attention=True,
                    extra_lines=[f"Automation error: {exc}"],
                ),
                lead=lead,
                event_type="critical_failure",
                dedupe_key=f"receipt-failure-{receipt.pk}",
            )
            return {"validated": True, "granted": False, "error": str(exc)}

        if notify_user:
            send_whatsapp_text(lead.phone_number, _build_success_reply(lead, provision_result), lead=lead)

        send_telegram_alert(
            _build_admin_alert(
                lead,
                "paid access granted",
                latest_message=receipt.message.text_content if receipt.message else "",
                receipt_attached=True,
                human_attention=False,
                extra_lines=[
                    f"Receipt confidence: {receipt.validation_confidence:.2f}",
                    f"Linked username: {provision_result['user'].username}",
                    f"Existing account: {'yes' if not provision_result['created'] else 'no'}",
                ],
            ),
            lead=lead,
            event_type="access_granted",
            dedupe_key=f"access-granted-{receipt.pk}",
        )
        return {"validated": True, "granted": True, "provision": provision_result}

    lead.status = "receipt_received"
    lead.handoff_needed = True
    lead.save(update_fields=["status", "handoff_needed", "updated_at"])
    if notify_user:
        send_whatsapp_text(lead.phone_number, _build_wait_reply(lead), lead=lead)
    send_telegram_alert(
        _build_admin_alert(
            lead,
            "receipt validation low confidence",
            latest_message=receipt.message.text_content if receipt.message else "",
            receipt_attached=True,
            human_attention=True,
            extra_lines=[
                f"Receipt confidence: {receipt.validation_confidence:.2f}",
                f"Notes: {receipt.validation_notes}",
            ],
        ),
        lead=lead,
        event_type="receipt_low_confidence",
        dedupe_key=f"receipt-low-{receipt.pk}",
    )
    return {"validated": False, "granted": False}


def process_receipt_message(lead, message):
    send_telegram_alert(
        _build_admin_alert(
            lead,
            "receipt submitted",
            latest_message=message.text_content,
            receipt_attached=True,
            human_attention=False,
        ),
        lead=lead,
        event_type="receipt_received",
        dedupe_key=message.meta_message_id or f"receipt-{message.pk}",
    )
    try:
        receipt = create_receipt_from_message(lead, message)
        evaluate_receipt(receipt)
        return finalize_receipt(receipt, notify_user=True)
    except Exception as exc:
        logger.exception("Receipt processing failed for lead %s", lead.pk)
        lead.handoff_needed = True
        lead.status = "receipt_received"
        lead.save(update_fields=["handoff_needed", "status", "updated_at"])
        send_telegram_alert(
            _build_admin_alert(
                lead,
                "receipt parse failed",
                latest_message=message.text_content,
                receipt_attached=True,
                human_attention=True,
                extra_lines=[f"Receipt processing error: {exc}"],
            ),
            lead=lead,
            event_type="receipt_parse_failed",
            dedupe_key=message.meta_message_id or f"receipt-error-{message.pk}",
        )
        send_whatsapp_text(lead.phone_number, _build_wait_reply(lead), lead=lead)
        return {"validated": False, "granted": False, "error": str(exc)}


def reprocess_receipt(receipt, notify_user=False):
    evaluate_receipt(receipt)
    return finalize_receipt(receipt, notify_user=notify_user)


def _build_contacts_map(value):
    contacts_map = {}
    for contact in value.get("contacts", []) or []:
        wa_id = normalize_phone_number(contact.get("wa_id"))
        contacts_map[wa_id] = (contact.get("profile") or {}).get("name", "")
    return contacts_map


def _upsert_lead(message_payload, contacts_map):
    phone_number = normalize_phone_number(message_payload.get("from"))
    profile_name = contacts_map.get(phone_number, "").strip()
    first_name = profile_name.split()[0] if profile_name else None
    text_content = ((message_payload.get("text") or {}).get("body") or "").strip()
    message_language = detect_language(text_content)
    lead, created = WhatsAppLead.objects.get_or_create(
        phone_number=phone_number,
        defaults={
            "first_name": first_name,
            "language_preference": message_language,
            "metadata": {"profile_name": profile_name} if profile_name else {},
        },
    )
    updates = []
    metadata = dict(lead.metadata or {})
    if profile_name:
        metadata["profile_name"] = profile_name
    if lead.metadata != metadata:
        lead.metadata = metadata
        updates.append("metadata")
    if first_name and lead.first_name != first_name:
        lead.first_name = first_name
        updates.append("first_name")
    if message_language != "unknown" and lead.language_preference != message_language:
        lead.language_preference = message_language
        updates.append("language_preference")
    lead.last_user_message_at = parse_meta_timestamp(message_payload.get("timestamp"))
    lead.message_count = lead.message_count + 1
    if created:
        updates.extend(["last_user_message_at", "message_count"])
    else:
        updates.extend(["last_user_message_at", "message_count", "updated_at"])
    if lead.status == "new":
        lead.status = "engaged"
        updates.append("status")
    lead.save(update_fields=list(dict.fromkeys(updates)))
    _sync_existing_user_flag(lead)
    return lead


def _create_inbound_message(lead, message_payload):
    message_type = message_payload.get("type") or "unknown"
    text_content = ((message_payload.get("text") or {}).get("body") or "").strip()
    media_data = message_payload.get(message_type) or {}
    message = WhatsAppMessage.objects.create(
        lead=lead,
        meta_message_id=message_payload.get("id"),
        direction="inbound",
        message_type=message_type if message_type in dict(WhatsAppMessage.MESSAGE_TYPE_CHOICES) else "unknown",
        text_content=text_content,
        media_id=media_data.get("id", ""),
        media_mime_type=media_data.get("mime_type", ""),
        raw_payload=_safe_payload(message_payload),
    )
    return message


def handle_status_event(status_payload):
    message_id = status_payload.get("id")
    if not message_id:
        return
    message = WhatsAppMessage.objects.filter(meta_message_id=message_id).select_related("lead").first()
    status_value = status_payload.get("status")
    if message:
        changed_fields = []
        if status_value == "delivered" and not message.delivered:
            message.delivered = True
            changed_fields.append("delivered")
        if status_value == "read" and not message.read:
            message.read = True
            changed_fields.append("read")
        if status_value == "failed" and not message.failed:
            message.failed = True
            changed_fields.append("failed")
        if changed_fields:
            message.save(update_fields=changed_fields)
        lead = message.lead
    else:
        lead = None

    log_agent_event(
        f"whatsapp_status:{status_value or 'unknown'}",
        lead=lead,
        payload=status_payload,
    )
    if status_value == "failed" and lead:
        send_telegram_alert(
            _build_admin_alert(
                lead,
                "outbound message failed",
                human_attention=True,
                extra_lines=[f"Status payload: {status_payload}"],
            ),
            lead=lead,
            event_type="whatsapp_send_failure",
            dedupe_key=f"status-failed-{message_id}",
        )


def _maybe_send_reply(lead, text):
    if not text:
        return
    send_whatsapp_text(lead.phone_number, text, lead=lead)


def handle_message_event(message_payload, value):
    message_id = message_payload.get("id")
    if message_id and WhatsAppMessage.objects.filter(meta_message_id=message_id).exists():
        return

    contacts_map = _build_contacts_map(value)
    lead = _upsert_lead(message_payload, contacts_map)
    message = _create_inbound_message(lead, message_payload)
    latest_text = message.text_content
    intent = detect_intent(latest_text)
    lead.last_intent = intent

    if message.message_type in {"image", "document"}:
        lead.last_intent = "receipt_submission"
        lead.save(update_fields=["last_intent", "updated_at"])
        return process_receipt_message(lead, message)

    if intent == "handoff":
        lead.handoff_needed = True
        lead.status = "handed_off"
        lead.save(update_fields=["handoff_needed", "status", "last_intent", "updated_at"])
        _maybe_send_reply(lead, _build_handoff_reply(lead))
        send_telegram_alert(
            _build_admin_alert(
                lead,
                "human handoff needed",
                latest_message=latest_text,
                human_attention=True,
            ),
            lead=lead,
            event_type="handoff_needed",
            dedupe_key="handoff-needed",
        )
        return

    if intent in {"buying_intent", "payment_submitted"}:
        lead.status = "payment_intent"
        lead.save(update_fields=["status", "last_intent", "updated_at"])
        reply_text = _build_receipt_prompt_reply(lead) if intent == "payment_submitted" else _build_payment_reply(lead)
        _maybe_send_reply(lead, reply_text)
        send_telegram_alert(
            _build_admin_alert(
                lead,
                "strong buying intent",
                latest_message=latest_text,
                human_attention=False,
            ),
            lead=lead,
            event_type="payment_intent",
            dedupe_key="payment-intent",
        )
        return

    if message.message_type not in {"text", "interactive"}:
        lead.handoff_needed = True
        lead.save(update_fields=["handoff_needed", "last_intent", "updated_at"])
        send_telegram_alert(
            _build_admin_alert(
                lead,
                "unsupported message type",
                latest_message=latest_text,
                human_attention=True,
                extra_lines=[f"Message type: {message.message_type}"],
            ),
            lead=lead,
            event_type="unsupported_message",
            dedupe_key=f"unsupported-{message.message_type}",
        )
        _maybe_send_reply(lead, _build_fallback_reply(lead))
        return

    try:
        reply_text = generate_sales_reply(lead, list(lead.messages.all()))
    except Exception as exc:
        logger.exception("OpenAI sales reply failed for lead %s", lead.pk)
        send_telegram_alert(
            _build_admin_alert(
                lead,
                "OpenAI failure",
                latest_message=latest_text,
                human_attention=True,
                extra_lines=[f"OpenAI error: {exc}"],
            ),
            lead=lead,
            event_type="openai_failure",
            dedupe_key=f"openai-failure-{lead.pk}",
        )
        reply_text = _build_fallback_reply(lead)

    if lead.status == "engaged" and lead.message_count >= 2:
        lead.status = "warm"
        lead.save(update_fields=["status", "last_intent", "updated_at"])
    else:
        lead.save(update_fields=["last_intent", "updated_at"])
    _maybe_send_reply(lead, reply_text)


def process_webhook_payload(payload):
    log_agent_event("webhook_received", payload=payload)
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            for status_payload in value.get("statuses", []) or []:
                try:
                    handle_status_event(status_payload)
                except Exception as exc:
                    logger.exception("Failed to process WhatsApp status payload")
                    send_telegram_alert(
                        f"OqyAI WhatsApp alert: webhook status parse failure\nError: {exc}\nPayload: {clip_text(json.dumps(status_payload, default=str), 500)}",
                        event_type="webhook_status_failure",
                        dedupe_key=f"status-{status_payload.get('id')}",
                    )
                    log_agent_event("webhook_status_failed", payload={"error": str(exc), "status": status_payload})

            for message_payload in value.get("messages", []) or []:
                try:
                    handle_message_event(message_payload, value)
                except Exception as exc:
                    logger.exception("Failed to process WhatsApp inbound message")
                    phone_number = normalize_phone_number(message_payload.get("from"))
                    lead = WhatsAppLead.objects.filter(phone_number=phone_number).first()
                    send_telegram_alert(
                        _build_admin_alert(
                            lead or WhatsAppLead(phone_number=phone_number or "unknown"),
                            "critical automation failure",
                            latest_message=((message_payload.get("text") or {}).get("body") or ""),
                            receipt_attached=bool(message_payload.get("image") or message_payload.get("document")),
                            human_attention=True,
                            extra_lines=[f"Message processing error: {exc}"],
                        ),
                        lead=lead,
                        event_type="critical_failure",
                        dedupe_key=f"message-failure-{message_payload.get('id')}",
                    )
                    log_agent_event(
                        "webhook_message_failed",
                        lead=lead,
                        payload={"error": str(exc), "message": message_payload},
                    )
