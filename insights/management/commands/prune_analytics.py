from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from insights.models import Event, PendingEvent, Visit, Visitor


class Command(BaseCommand):
    help = 'Preview expired raw analytics. Pass --apply to delete in batches.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if settings.ANALYTICS_RETENTION_DAYS < 1 or (options['apply'] and options['dry_run']):
            raise CommandError('Invalid retention or conflicting options')
        cutoff=timezone.now()-timedelta(days=settings.ANALYTICS_RETENTION_DAYS)
        for qs in (PendingEvent.objects.filter(at__lt=cutoff), Event.objects.filter(at__lt=cutoff),Visit.objects.filter(last_seen__lt=cutoff),
                   Visitor.objects.exclude(visit__last_seen__gte=cutoff)):
            self.stdout.write(f'{qs.model.__name__}: {qs.count()}')
            if options['apply']:
                while ids:=list(qs.values_list('pk',flat=True)[:500]):
                    qs.filter(pk__in=ids).delete()
