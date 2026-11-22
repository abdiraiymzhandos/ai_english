import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from lessons.models import RegistrationNotification

from english_course.services.telegram import RetryableTelegramFailure, send_telegram_message


logger = logging.getLogger(__name__)


def whatsapp_digits(phone):
    if not re.fullmatch(r"\+?[0-9 ()-]+", phone or ""):
        return ""
    digits = re.sub(r"[^0-9]", "", phone)
    if len(digits) == 11 and digits[0] in "78" and not (phone.startswith("+") and digits[0] == "8"):
        return "7" + digits[1:]
    return ""


def _build_registration_alert_text(user, profile):
    phone = profile.phone or ""
    display_phone = phone or "көрсетілмеген"
    whatsapp_phone = whatsapp_digits(phone)
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
        return send_telegram_message(_build_registration_alert_text(user, profile), timeout=5, signal_retry=True)
    except RetryableTelegramFailure:
        raise
    except Exception as exc:
        logger.warning("Registration Telegram notification failed: %s", type(exc).__name__)
        return False


def enqueue_registration_notification(user):
    try:
        with transaction.atomic():
            RegistrationNotification.objects.get_or_create(user=user)
    except DatabaseError as exc:
        logger.warning("Registration notification enqueue failed: %s", type(exc).__name__)


def process_registration_notifications(limit, *, stop_requested=None):
    jobs = RegistrationNotification.objects.filter(status='pending', next_attempt__lte=timezone.now())
    processed = 0
    for pk in list(jobs.order_by('next_attempt', 'pk').values_list('pk', flat=True)[:limit]):
        if stop_requested and stop_requested():
            break
        # Commit the claim before any external side effect. A crashed claim needs manual review.
        if not jobs.filter(pk=pk).update(status='sending', attempts=F('attempts') + 1, updated_at=timezone.now()):
            continue
        job = RegistrationNotification.objects.select_related('user__profile').get(pk=pk)
        try:
            success = send_registration_notification(job.user, job.user.profile)
            job.status = 'sent' if success else 'review'
        except RetryableTelegramFailure:
            job.status = 'pending' if job.attempts < 3 else 'review'
            job.next_attempt = timezone.now() + timedelta(minutes=5 ** job.attempts)
        except Exception as exc:
            logger.warning("Registration notification requires review: %s", type(exc).__name__)
            job.status = 'review'
        job.save(update_fields=['status', 'next_attempt', 'updated_at'])
        processed += 1
    return processed
