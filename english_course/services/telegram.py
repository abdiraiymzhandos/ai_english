import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


def _bounded_timeout(timeout):
    try:
        timeout_value = int(timeout)
    except (TypeError, ValueError):
        return 15
    return max(1, min(timeout_value, 15))


def send_telegram_message(text: str, *, timeout: int = 15) -> bool:
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = (getattr(settings, "TELEGRAM_CHAT_ID", "") or "").strip()
    if not token or not chat_id:
        logger.warning("Telegram message skipped because configuration is missing.")
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=_bounded_timeout(timeout),
        )
    except requests.RequestException as exc:
        logger.warning("Telegram message request failed: %s", type(exc).__name__)
        return False

    if not 200 <= response.status_code < 300:
        logger.warning("Telegram message request returned HTTP %s.", response.status_code)
        return False

    return True
