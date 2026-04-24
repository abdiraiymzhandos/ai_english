import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services import log_agent_event, process_webhook_payload


logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge", "")
        if mode == "subscribe" and verify_token == getattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", ""):
            return HttpResponse(challenge)
        return HttpResponse(status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.exception("Malformed WhatsApp webhook payload")
        log_agent_event(
            "webhook_parse_failed",
            payload={"error": str(exc), "raw_body": request.body.decode("utf-8", errors="ignore")},
        )
        return JsonResponse({"status": "ignored"}, status=200)

    process_webhook_payload(payload)
    return JsonResponse({"status": "ok"})

