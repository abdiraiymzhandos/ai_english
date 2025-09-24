from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from lessons.models import UserProfile


class Command(BaseCommand):
    help = 'Grant voice lesson access to users'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username to grant access to')
        parser.add_argument('--user-id', type=int, help='User ID to grant access to')
        parser.add_argument('--days', type=int, default=30, help='Number of days to grant access for (default: 30)')
        parser.add_argument('--all-paid', action='store_true', help='Grant access to all paid users')

    def handle(self, *args, **options):
        username = options.get('username')
        user_id = options.get('user_id')
        days = options.get('days')
        all_paid = options.get('all_paid')

        if all_paid:
            # Grant access to all paid users
            profiles = UserProfile.objects.filter(is_paid=True)
            count = 0
            for profile in profiles:
                profile.grant_voice_access(days=days)
                count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Granted voice access to {profile.user.username} for {days} days')
                )
            self.stdout.write(
                self.style.SUCCESS(f'🎉 Total: {count} users granted voice access for {days} days')
            )
            return

        # Find user by username or user_id
        user = None
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ User with username "{username}" not found')
                )
                return
        elif user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ User with ID {user_id} not found')
                )
                return
        else:
            self.stdout.write(
                self.style.ERROR('❌ Please provide either --username or --user-id')
            )
            return

        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        if created:
            self.stdout.write(
                self.style.WARNING(f'📝 Created new profile for {user.username}')
            )

        # Grant voice access
        profile.grant_voice_access(days=days)

        self.stdout.write(
            self.style.SUCCESS(f'✅ Granted voice access to {user.username} for {days} days')
        )
        self.stdout.write(
            self.style.SUCCESS(f'📅 Access expires: {profile.voice_access_until.strftime("%Y-%m-%d %H:%M")}')
        )