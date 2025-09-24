from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from lessons.models import UserProfile


class Command(BaseCommand):
    help = 'Revoke voice lesson access from users'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username to revoke access from')
        parser.add_argument('--user-id', type=int, help='User ID to revoke access from')
        parser.add_argument('--all', action='store_true', help='Revoke access from all users with voice access')

    def handle(self, *args, **options):
        username = options.get('username')
        user_id = options.get('user_id')
        revoke_all = options.get('all')

        if revoke_all:
            # Revoke access from all users with voice access
            profiles = UserProfile.objects.filter(has_voice_access=True)
            count = 0
            for profile in profiles:
                profile.revoke_voice_access()
                count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'❌ Revoked voice access from {profile.user.username}')
                )
            self.stdout.write(
                self.style.SUCCESS(f'🎉 Total: {count} users had voice access revoked')
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

        # Get user profile
        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Profile for {user.username} not found')
            )
            return

        # Check if user has voice access
        if not profile.has_voice_access:
            self.stdout.write(
                self.style.WARNING(f'⚠️ {user.username} does not have voice access')
            )
            return

        # Revoke voice access
        profile.revoke_voice_access()

        self.stdout.write(
            self.style.SUCCESS(f'❌ Revoked voice access from {user.username}')
        )