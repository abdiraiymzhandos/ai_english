from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from lessons.models import UserDevice, UserProfile
from lessons.services.device_access import expire_profile


class Command(BaseCommand):
    help = 'Count registry overages and expired locks. Pass --apply to clear only expired locks.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--dry-run', action='store_true', help='Preview counts (default).')
        mode.add_argument('--apply', action='store_true', help='Clear expired locks after rechecking each account.')

    def handle(self, *args, **options):
        cutoff = timezone.now()
        expired = UserProfile.objects.filter(lock_until__lte=cutoff)
        sizes = UserDevice.objects.values('user_id').annotate(n=Count('pk'))
        self.stdout.write(f"limit={settings.MAX_ACCOUNT_DEVICES} accounts_over_two={sizes.filter(n__gt=2).count()} "
                          f"accounts_over_limit={sizes.filter(n__gt=settings.MAX_ACCOUNT_DEVICES).count()}")
        self.stdout.write(f"active={UserProfile.objects.filter(lock_until__gt=cutoff).count()} "
                          f"expired={expired.count()} "
                          f"devices_on_expired={UserDevice.objects.filter(user__profile__lock_until__lte=cutoff).count()}")
        if options['apply']:
            cleared = removed = 0
            # Release the read cursor before changing its rows, including on SQLite.
            candidates = list(expired.order_by('pk').values_list('pk', 'lock_until'))
            for pk, deadline in candidates:
                count = expire_profile(pk, expected_deadline=deadline)
                if count is not None:
                    cleared += 1
                    removed += count
            self.stdout.write(f'cleared={cleared} removed={removed}')
        else:
            self.stdout.write('Dry run. No records changed.')
