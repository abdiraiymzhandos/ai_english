import logging
import re

from django.conf import settings
from django.urls import reverse

from english_course.services.telegram import send_telegram_message


logger = logging.getLogger(__name__)


def _normalized_kazakhstan_phone_for_whatsapp(phone):
    digits = re.sub(r"[\s+\-()]", "", phone or "")
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7") and digits.isdigit():
        return digits
    return ""


def _build_registration_alert_text(user, profile):
    phone = profile.phone or ""
    display_phone = phone or "көрсетілмеген"
    whatsapp_phone = _normalized_kazakhstan_phone_for_whatsapp(phone)
    whatsapp_url = f"https://wa.me/{whatsapp_phone}" if whatsapp_phone else "жоқ"
    admin_path = reverse("admin:auth_user_change", args=[user.pk])
    base_url = (getattr(settings, "APP_BASE_URL", "") or "").rstrip("/")
    admin_url = f"{base_url}{admin_path}" if base_url else admin_path

    return "\n".join(
        [
            "🆕 Жаңа OqyAI тіркелуі",
            "",
            f"👤 Username: {user.username}",
            f"📞 Телефон: {display_phone}",
            f"👥 Рөлі: {profile.get_role_display()}",
            f"💬 WhatsApp: {whatsapp_url}",
            f"🔗 Admin: {admin_url}",
        ]
    )


def send_registration_notification(user, profile) -> bool:
    try:
        return send_telegram_message(_build_registration_alert_text(user, profile), timeout=5)
    except Exception as exc:
        logger.warning("Registration Telegram notification failed: %s", type(exc).__name__)
        return False
