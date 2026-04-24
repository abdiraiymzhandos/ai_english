import json

from django.core.management.base import BaseCommand, CommandError

from whatsapp_agent.services import send_whatsapp_template, send_whatsapp_text


class Command(BaseCommand):
    help = "Send a test WhatsApp text or template message through the Cloud API"

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Destination phone number")
        parser.add_argument("--text", help="Message body for a plain text send")
        parser.add_argument(
            "--template",
            help="Template name for a template send. Useful for Meta API Setup test sends.",
        )
        parser.add_argument(
            "--language-code",
            default="en_US",
            help="Template language code. Defaults to en_US.",
        )

    def handle(self, *args, **options):
        text = options.get("text")
        template_name = options.get("template")

        if bool(text) == bool(template_name):
            raise CommandError("Provide exactly one of --text or --template.")

        try:
            if template_name:
                response = send_whatsapp_template(
                    options["to"],
                    template_name=template_name,
                    language_code=options["language_code"],
                )
            else:
                response = send_whatsapp_text(options["to"], text)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(json.dumps(response, ensure_ascii=False, default=str)))
