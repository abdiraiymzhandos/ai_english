from django.core.management.base import BaseCommand, CommandError

from whatsapp_agent.models import WhatsAppLead
from whatsapp_agent.utils import normalize_phone_number


class Command(BaseCommand):
    help = "Print lead, message, and receipt details for a WhatsApp phone number"

    def add_arguments(self, parser):
        parser.add_argument("--phone", required=True, help="WhatsApp phone number")

    def handle(self, *args, **options):
        phone_number = normalize_phone_number(options["phone"])
        lead = WhatsAppLead.objects.filter(phone_number=phone_number).prefetch_related("messages", "receipts").first()
        if not lead:
            raise CommandError(f"No WhatsAppLead found for {phone_number}")

        self.stdout.write(f"Lead #{lead.pk}: {lead.phone_number}")
        self.stdout.write(f"Status: {lead.status}")
        self.stdout.write(f"Language: {lead.language_preference}")
        self.stdout.write(f"Existing user linked: {lead.existing_user_linked}")
        self.stdout.write(f"Paid access granted: {lead.paid_access_granted}")
        self.stdout.write(f"Message count: {lead.message_count}")
        self.stdout.write("Messages:")
        for message in lead.messages.all():
            preview = (message.text_content or "")[:120]
            self.stdout.write(f"  - [{message.direction}/{message.message_type}] {message.meta_message_id or '-'} {preview}")
        self.stdout.write("Receipts:")
        for receipt in lead.receipts.all():
            self.stdout.write(
                f"  - Receipt #{receipt.pk} type={receipt.file_type} validated={receipt.is_validated} confidence={receipt.validation_confidence:.2f}"
            )

