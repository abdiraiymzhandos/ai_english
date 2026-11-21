from django.db import transaction
from django.db import DatabaseError
import logging
from .models import PendingEvent, Purchase
from .tracking import event_key


@transaction.atomic
def confirm_course_payment(actor, queryset):
    """This staff action attests payment. Generic access grants have no payment meaning."""
    if not actor.is_active or not actor.is_staff or not actor.has_perm('lessons.change_userprofile'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    count=0
    for profile in queryset.select_for_update().order_by('pk'):
        if profile.is_paid:
            continue
        profile.is_paid=True
        profile.save(update_fields=['is_paid'])
        purchase, created = Purchase.objects.get_or_create(user_id=profile.user_id, defaults={'confirmed_by':actor})
        if created:
            try:
                with transaction.atomic():
                    PendingEvent.objects.create(id=event_key('purchase',purchase.pk),user_id=profile.user_id,
                        at=purchase.confirmed_at,kind='purchase_completed',path='',page='payment')
            except DatabaseError:
                logging.getLogger(__name__).warning('Payment confirmed, timeline event unavailable')
            count+=1
    return count
