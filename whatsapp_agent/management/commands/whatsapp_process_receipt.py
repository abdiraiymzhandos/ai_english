from django.core.management.base import BaseCommand, CommandError

from whatsapp_agent.models import WhatsAppLead
from whatsapp_agent.services import reprocess_receipt


class Command(BaseCommand):
    help = "Re-run receipt extraction and validation for the latest receipt on a lead"

    def add_arguments(self, parser):
        parser.add_argument("--lead", required=True, type=int, help="WhatsAppLead ID")

    def handle(self, *args, **options):
        lead = WhatsAppLead.objects.filter(pk=options["lead"]).prefetch_related("receipts").first()
        if not lead:
            raise CommandError(f"Lead {options['lead']} not found")
        receipt = lead.receipts.order_by("-created_at").first()
        if not receipt:
            raise CommandError(f"Lead {lead.pk} has no receipts")

        result = reprocess_receipt(receipt, notify_user=False)
        self.stdout.write(self.style.SUCCESS(str(result)))

