import json
import re

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Register the configured WhatsApp Cloud API phone number with Meta using "
        "the /{phone-number-id}/register endpoint."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--pin",
            required=True,
            help=(
                "6-digit registration PIN. For first-time registration this becomes "
                "the two-step verification PIN. If the number already has two-step "
                "verification enabled, pass the existing PIN."
            ),
        )

    def handle(self, *args, **options):
        access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
        graph_version = getattr(settings, "WHATSAPP_GRAPH_API_VERSION", "v23.0")
        pin = (options.get("pin") or "").strip()

        if not access_token:
            raise CommandError("WHATSAPP_ACCESS_TOKEN is missing in settings/env.")
        if not phone_number_id:
            raise CommandError("WHATSAPP_PHONE_NUMBER_ID is missing in settings/env.")
        if not re.fullmatch(r"\d{6}", pin):
            raise CommandError("--pin must be exactly 6 digits.")

        url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/register"
        payload = {
            "messaging_product": "whatsapp",
            "pin": pin,
        }

        self.stdout.write(f"POST {url}")
        self.stdout.write(f"Phone Number ID: {phone_number_id}")
        self.stdout.write("Payload:")
        self.stdout.write(str(payload))

        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise CommandError(f"Meta registration request failed: {exc}") from exc

        body_text = (response.text or "").strip() or "<empty>"
        parsed_json = None
        parsed_error = None
        try:
            parsed_json = response.json()
        except ValueError:
            parsed_json = None
        if isinstance(parsed_json, dict):
            parsed_error = parsed_json.get("error")
        elif parsed_json is not None:
            parsed_error = parsed_json

        self.stdout.write(f"HTTP {response.status_code}")
        self.stdout.write("Meta response body:")
        self.stdout.write(body_text)
        if parsed_error is not None:
            self.stdout.write("Parsed JSON error:")
            self.stdout.write(json.dumps(parsed_error, ensure_ascii=False, default=str))

        if response.status_code >= 400:
            message = f"Meta registration failed with HTTP {response.status_code}. response.text={body_text}"
            if parsed_error is not None:
                message += f" parsed_json_error={json.dumps(parsed_error, ensure_ascii=False, default=str)}"
            raise CommandError(message)

        self.stdout.write(self.style.SUCCESS("Phone registration request completed successfully."))
