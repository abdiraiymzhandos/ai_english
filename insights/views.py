import json
import logging
import uuid
import time
from urllib.parse import urlsplit

from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.utils.crypto import constant_time_compare, salted_hmac
from django.urls import Resolver404, resolve, reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import tracking
from .taxonomy import CLIENT


log = logging.getLogger(__name__)
AUDIO_VALUES = {'section': {'vocabulary','dialogue','grammar','content','unknown'},
                'phase': {'preload','playback'}, 'error': {'source','unsupported','network','decode','aborted','unknown'}}


def database_failure_reason(exc, vendor):
    cause = exc.__cause__ or exc
    if vendor == 'sqlite' and ('locked' in str(cause).lower() or 'busy' in str(cause).lower()):
        return 'lock'
    if vendor == 'mysql' and cause.args and cause.args[0] in (1205,1213):
        return 'lock'
    return 'database'


@require_POST
@never_cache
def ingest(request):
    if not tracking.enabled(request):
        return HttpResponse(status=204)
    if request.content_type != 'application/json' or not (request.META.get('CONTENT_LENGTH') or '0').isdigit():
        return HttpResponse(status=400)
    if int(request.META.get('CONTENT_LENGTH') or 0) > 2048:
        return HttpResponse(status=413)
    origin = request.headers.get('Origin')
    if origin and origin != request.build_absolute_uri('/').rstrip('/'):
        return HttpResponse(status=403)
    try:
        raw = request.read(2049)
        if len(raw) > 2048:
            return HttpResponse(status=413)
        data = json.loads(raw)
        if not isinstance(data, dict) or data.keys() - {'id','type','path','campaign','platform','track','context'}:
            raise ValueError
        key = uuid.UUID(data['id'])
        if key.version != 4:
            raise ValueError
        kind, path = data['type'], data['path']
        if kind not in CLIENT or not isinstance(path, str) or len(path) > 100 or urlsplit(path).path != path:
            raise ValueError
        match = resolve(path)
        if match.kwargs.get('lesson_id', 0) > 2147483647:
            raise ValueError
        if match.url_name not in CLIENT[kind] or reverse(match.url_name, kwargs=match.kwargs) != path:
            raise ValueError
        context = data.get('context', {})
        if not isinstance(context, dict) or (context and (
                kind != 'audio_error' or context.keys() != AUDIO_VALUES.keys() or
                any(v not in AUDIO_VALUES[k] for k,v in context.items()))):
            raise ValueError
        campaign = data.get('campaign', {})
        if not isinstance(campaign, dict) or campaign.keys() - {'utm_source','utm_medium','utm_campaign','utm_content'}:
            raise ValueError
        if kind != 'page_view' and campaign:
            raise ValueError
        platform, track = data.get('platform', 'unknown'), data.get('track', '')
        if track and match.url_name != 'advertisement':
            raise ValueError
        if platform not in ('browser','pwa','android_webview','ios_webview','unknown') or track not in ('','kk','ru'):
            raise ValueError
    except (ValueError, RecursionError, KeyError, TypeError, Resolver404, UnicodeError):
        return HttpResponse(status=400)
    if not request.get_signed_cookie(tracking.COOKIE, default='', salt=tracking.COOKIE):
        return HttpResponse(status=403)
    if not constant_time_compare(request.headers.get('X-Analytics-Actor', ''), tracking.document_actor(request)):
        return HttpResponse(status=403)
    # Coarse per-worker burst guard against repeated fresh cookies. No IP enters storage or logs.
    address = salted_hmac('analytics-burst', request.META.get('REMOTE_ADDR', '')).hexdigest()
    burst_key = f'analytics:burst:{address}:{int(time.time()) // 60}'
    if not cache.add(burst_key, 1, 120):
        try:
            if cache.incr(burst_key) > 1800:
                return HttpResponse(status=429)
        except ValueError:
            pass  # Cache eviction. The database still enforces the per-visitor limit.
    try:
        if kind == 'page_view':
            tracking.drain(limit=10, visitor=tracking.visitor_id(request))
        tracking.record(request, kind, key=key, origin='client', page=match.url_name, path=path,
                        lesson=match.kwargs.get('lesson_id'), platform=platform, track=track,
                        attribution=tracking.campaign_values(campaign), context=context)
    except tracking.RateLimited:
        return HttpResponse(status=429)
    except DatabaseError as exc:
        reason = database_failure_reason(exc, connection.vendor)
        log.warning('Analytics ingest vendor=%s reason=%s error=%s', connection.vendor, reason, type(exc).__name__)
        return HttpResponse(status=503 if reason == 'lock' else 500)
    return HttpResponse(status=204)
