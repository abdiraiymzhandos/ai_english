import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Visitor(models.Model):
    """Random first-party ID, separate from login/session credentials."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_source = models.CharField(max_length=48, default='unknown')
    first_campaign = models.CharField(max_length=48, blank=True)
    rate_window = models.DateTimeField(null=True)
    client_events = models.PositiveSmallIntegerField(default=0)


class Visit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    started = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)
    landing = models.CharField(max_length=100)
    source = models.CharField(max_length=48, default='unknown')
    medium = models.CharField(max_length=48, blank=True)
    campaign = models.CharField(max_length=48, blank=True)
    content = models.CharField(max_length=48, blank=True)
    platform = models.CharField(max_length=20, default='unknown')

    class Meta:
        verbose_name = 'Сатылым аналитикасы'
        verbose_name_plural = 'Сатылым аналитикасы'
        permissions = [
            ('view_customer_contacts', 'View current analytics customer identities'),
            ('export_customer_contacts', 'Export current analytics customer identities'),
            ('include_internal_accounts', 'Include internal accounts in commercial reports'),
        ]
        indexes = [models.Index(fields=['visitor', '-last_seen'])]


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.ForeignKey(Visit, null=True, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    at = models.DateTimeField(default=timezone.now, db_index=True)
    kind = models.CharField(max_length=36)
    origin = models.CharField(max_length=8)
    path = models.CharField(max_length=100)
    page = models.CharField(max_length=32)
    lesson = models.PositiveIntegerField(null=True)
    track = models.CharField(max_length=2, blank=True)

    context = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=['kind', 'at']), models.Index(fields=['user', 'at'])]


class Purchase(models.Model):
    """First explicitly confirmed course activation, independent of raw-event retention."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    confirmed_at = models.DateTimeField(default=timezone.now, db_index=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                     related_name='confirmed_course_purchases')


class PendingEvent(models.Model):
    """Small transactional outbox. No network or visit locks on learning requests."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor = models.UUIDField(null=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    at = models.DateTimeField(default=timezone.now, db_index=True)
    kind = models.CharField(max_length=36)
    page = models.CharField(max_length=32)
    path = models.CharField(max_length=100)
    lesson = models.PositiveIntegerField(null=True)
    track = models.CharField(max_length=2, blank=True)
