from django.core.management.base import BaseCommand, CommandError
from lessons.services.registration_notifications import process_registration_notifications


class Command(BaseCommand):
    help = 'Send pending registration alerts and leave uncertain deliveries for manual review.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        if options['limit'] < 1:
            raise CommandError('Choose a positive limit')
        self.stdout.write(str(process_registration_notifications(options['limit'])))
