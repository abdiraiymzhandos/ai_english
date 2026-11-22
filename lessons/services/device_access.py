"""Account device transitions. Serialize changes on the single profile for the learner."""
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Exists, F, OuterRef
from django.utils import timezone

from lessons.models import UserDevice, UserProfile


def locked_profiles(**lookup):
    """Call inside atomic(). SQLite needs a writer reservation before its first read."""
    profiles = UserProfile.objects.filter(**lookup)
    if connection.vendor == 'sqlite':
        profiles.update(lock_until=F('lock_until'))
    return profiles.select_for_update()


def clear_registry(profile):
    """The caller holds the profile lock."""
    removed, _ = UserDevice.objects.filter(user_id=profile.user_id).delete()
    if profile.lock_until is not None:
        profile.lock_until = None
        profile.save(update_fields=['lock_until'])
    return removed


@transaction.atomic
def unlock_profile(pk):
    return clear_registry(locked_profiles(pk=pk).get())


@transaction.atomic
def expire_profile(pk, expected_deadline=None):
    profile = locked_profiles(pk=pk).first()
    if profile is None or profile.lock_until is None or profile.lock_until > timezone.now():
        return None
    if expected_deadline is not None and profile.lock_until != expected_deadline:
        return None
    return clear_registry(profile)


def admit_device(user_id, identity):
    devices = UserDevice.objects.filter(user_id=user_id)
    profile = UserProfile.objects.filter(user_id=user_id).annotate(
        known_device=Exists(UserDevice.objects.filter(user_id=OuterRef('user_id'), device_id=identity))
    ).first()
    if profile and (profile.is_locked() or (profile.lock_until is None and profile.known_device)):
        return profile

    with transaction.atomic():
        profile, _ = locked_profiles(user_id=user_id).get_or_create(user_id=user_id)
        if profile.is_locked():
            return profile
        if profile.lock_until is not None:
            clear_registry(profile)
        # Known legacy identities are grandfathered until the owner reconciles this account.
        if not devices.filter(device_id=identity).exists():
            if devices.count() >= settings.MAX_ACCOUNT_DEVICES:
                profile.lock()
            else:
                devices.create(user_id=user_id, device_id=identity)
        return profile
