from django.core.management.base import BaseCommand, CommandError
from insights.tracking import drain


class Command(BaseCommand):
    help = 'Materialize committed server milestones in timestamp order.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=5000)

    def handle(self, *args, **options):
        if options['limit'] <= 0:
            raise CommandError('Choose a positive limit')
        self.stdout.write(str(drain(options['limit'])))
