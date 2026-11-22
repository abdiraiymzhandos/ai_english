import logging
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.cache import patch_vary_headers, patch_cache_control

from .models import Event, PendingEvent, Visit, Visitor
from .taxonomy import PAGES, PAGE_EVENTS

log = logging.getLogger(__name__)
COOKIE = 'oqy_visitor'
IDLE = timedelta(minutes=30)


def enabled(request):
    return settings.PRODUCT_ANALYTICS and request.headers.get('DNT') != '1' and request.headers.get('Sec-GPC') != '1'


def visitor_id(request):
    if not hasattr(request, '_analytics_visitor'):
        try:
            value = uuid.UUID(request.get_signed_cookie(COOKIE, default='', salt=COOKIE))
        except ValueError:
            value = uuid.uuid4()
        request._analytics_visitor = value
    return request._analytics_visitor


class VisitorCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        match = request.resolver_match
        if match and match.url_name in PAGES:
            patch_vary_headers(response, ('Cookie', 'DNT', 'Sec-GPC'))
            if not enabled(request) and COOKIE in request.COOKIES:
                response.delete_cookie(COOKIE)
        if match and match.url_name == 'logout' and request.method == 'POST':
            response.delete_cookie(COOKIE)
        elif match and match.url_name in PAGES and enabled(request) and (response.status_code == 200 or (request.method == 'POST' and response.status_code == 302)):
            value = str(visitor_id(request))
            if value != request.get_signed_cookie(COOKIE, default='', salt=COOKIE):
                patch_cache_control(response, private=True)
                response.set_signed_cookie(COOKIE, value, salt=COOKIE, max_age=settings.ANALYTICS_RETENTION_DAYS * 86400,
                                           secure=request.is_secure(), httponly=True, samesite='Lax')
        return response


def campaign_values(values):
    result = {}
    for key in ('source', 'medium', 'campaign', 'content'):
        value = values.get('utm_' + key, '')
        if isinstance(value, str) and re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,47}', value) and not re.search(r'\d{6}', value):
            result[key] = value.lower()
    return result


def event_key(*parts):
    return uuid.uuid5(uuid.NAMESPACE_URL, 'oqyai/events/' + '/'.join(map(str, parts)))


@transaction.atomic
def record(request, kind, *, page, path, lesson=None, track='', key=None, origin='server',
           attribution=None, platform='unknown', context=None):
    if not enabled(request):
        return
    return save_event(visitor_id(request), request.user.pk if request.user.is_authenticated else None,
                      timezone.now(), kind, page, path, lesson, track, key, origin, attribution, platform, context)


class RateLimited(Exception):
    pass


def save_event(visitor_pk, user_id, now, kind, page, path, lesson, track, key, origin, attribution=None, platform='unknown', context=None):
    attribution = attribution or {}
    visitor, _ = Visitor.objects.select_for_update().get_or_create(
        pk=visitor_pk, defaults={'first_source': attribution.get('source', 'unknown'),
                                 'first_campaign': attribution.get('campaign', '')})
    if origin == 'client':
        if visitor.rate_window is None or visitor.rate_window <= now-timedelta(minutes=1):
            visitor.rate_window, visitor.client_events = now, 0
        if visitor.client_events >= 90:
            raise RateLimited
        visitor.client_events += 1
        visitor.save(update_fields=['rate_window','client_events'])
    if key and Event.objects.filter(pk=key).exists():
        return
    # A delayed outbox entry belongs to the most recent visit already started at its timestamp.
    visits = Visit.objects.filter(visitor=visitor, last_seen__gte=now-IDLE)
    visit = visits.filter(started__lte=now).order_by('-started', '-last_seen').first()
    if visit is None and origin == 'server':
        visit = visits.filter(started__gt=now, started__lte=now+IDLE, user_id=user_id).order_by('started').first()
    if visit and visit.user_id != user_id:
        if visit.user_id is None and user_id:
            visit.user_id = user_id
            visit.save(update_fields=['user'])
            Event.objects.filter(visit=visit, user=None).update(user_id=user_id)
        else:
            visit = None
    if visit and attribution and any(getattr(visit, k) != v for k,v in attribution.items()):
        visit = None
    if visit is None:
        visit = Visit.objects.create(visitor=visitor, user_id=user_id, started=now, last_seen=now, landing=path, platform=platform,
                                    **(attribution or {}))
        Event.objects.create(visit=visit, user_id=user_id, at=now, kind='session_started', origin='server', page=page, path=path)
    else:
        visit.last_seen = max(visit.last_seen, now)
        visit.started = min(visit.started, now)
        if visit.platform == 'unknown':
            visit.platform = platform
        visit.save(update_fields=['last_seen', 'started', 'platform'])
    data = dict(at=now, visit=visit, user_id=user_id, origin=origin, page=page, path=path, lesson=lesson,
                track=('ru' if lesson > 250 else 'kk') if lesson else track)
    event, created = Event.objects.get_or_create(pk=key or uuid.uuid4(), defaults=dict(kind=kind, context=context or {}, **data))
    if created and kind == 'page_view' and page in PAGE_EVENTS:
        Event.objects.create(kind=PAGE_EVENTS[page], **data)


def schedule_event(request, kind, *, page, path, lesson=None, track='', key=None, subject=None):
    if not enabled(request):
        return
    user = subject if subject is not None else request.user
    try:
        with transaction.atomic():
            PendingEvent.objects.get_or_create(pk=key or uuid.uuid4(), defaults=dict(
                visitor=visitor_id(request), user_id=user.pk if user.is_authenticated else None,
                kind=kind, page=page, path=path, lesson=lesson, track=track))
    except DatabaseError:
        log.warning('Analytics enqueue failed for %s', kind)


def drain(limit=100, visitor=None, *, stop_requested=None):
    processed = 0
    pending = PendingEvent.objects.all()
    if visitor is not None:
        pending = pending.filter(visitor=visitor)
    for pk in pending.order_by('at','pk').values_list('pk',flat=True)[:limit]:
        if stop_requested and stop_requested():
            break
        with transaction.atomic():
            row = PendingEvent.objects.select_for_update().filter(pk=pk).first()
            if row is None:
                continue
            if row.visitor:
                save_event(row.visitor,row.user_id,row.at,row.kind,row.page,row.path,row.lesson,row.track,row.pk,'server')
            else:
                Event.objects.get_or_create(pk=row.pk, defaults=dict(user_id=row.user_id, at=row.at, kind=row.kind,
                                                                     origin='staff',page=row.page,path=row.path))
            row.delete()
            processed += 1
    return processed


def document_actor(request):
    user = request.user
    identity = f'{user.pk}/{request.session.session_key}' if user.is_authenticated else 'anonymous'
    return salted_hmac('analytics-document', f'{visitor_id(request)}/{identity}').hexdigest()


def template_context(request):
    match = request.resolver_match
    collect = bool(match and match.url_name in PAGES and enabled(request))
    return {'collect_product_analytics': collect, 'analytics_actor': document_actor(request) if collect else ''}


def quiz_event(request, kind, lesson, token):
    schedule_event(request, kind, page='quiz', path=f'/lesson/{lesson}/', lesson=lesson,
                 key=event_key(kind, token, lesson))
