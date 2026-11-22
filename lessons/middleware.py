import uuid

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import redirect
from django.utils.crypto import salted_hmac
from django.utils.deprecation import MiddlewareMixin

from .models import UserDevice
from .services.device_access import admit_device

LOCK_NOTICE = 'device_lock_notice'


class DeviceLockMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match.namespace == 'admin' or request.path_info == '/favicon.ico':
            return
        if match.url_name in {'account_locked', 'logout', 'service_worker', 'pwa_manifest', 'privacy_policy'}:
            return
        if not request.user.is_authenticated:
            request.check_device_after_login = match.url_name in ('login', 'register')
            if (request.check_device_after_login and request.method == 'GET'
                    and not request.COOKIES.get('device_id')):
                request.new_device_id = str(uuid.uuid4())
            return
        return self.enforce(request)

    def enforce(self, request):
        user = request.user
        if user.is_active and (user.is_staff or user.is_superuser):
            return
        cookie = request.COOKIES.get('device_id')
        try:
            identity = str(uuid.UUID(cookie or ''))
        except ValueError:
            # Parallel requests sharing a newly authenticated session derive the same opaque UUID.
            if request.session.session_key:
                digest = salted_hmac('oqyai-device-bootstrap', request.session.session_key).digest()
                identity = str(uuid.UUID(bytes=digest[:16], version=4))
            else:
                identity = str(uuid.uuid4())
        if (cookie and len(cookie) <= 255 and cookie != identity and
                UserDevice.objects.filter(user_id=user.pk, device_id=cookie).exists()):
            # Preserve previously registered opaque cookie values during rollout.
            identity = cookie
        profile = admit_device(user.pk, identity)
        request.user.profile = profile
        if profile.lock_until is not None:
            logout(request)
            request.session[LOCK_NOTICE] = [profile.pk, profile.lock_until.isoformat()]
            return redirect('account_locked')
        if cookie != identity or getattr(request, 'check_device_after_login', False):
            request.new_device_id = identity

    def process_response(self, request, response):
        if (getattr(request, 'check_device_after_login', False) and request.user.is_authenticated
                and response.status_code < 400):
            request.session.pop(LOCK_NOTICE, None)
            denied = self.enforce(request)
            if denied is not None:
                return denied
        if getattr(request, 'new_device_id', None) and response.status_code < 400:
            response.set_cookie('device_id', request.new_device_id, max_age=365 * 86400,
                                secure=request.is_secure() or settings.SESSION_COOKIE_SECURE,
                                httponly=True, samesite='Lax')
        return response


class WwwRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if host == "oqyai.kz":
            return HttpResponsePermanentRedirect(f"https://www.oqyai.kz{request.get_full_path()}")
        return self.get_response(request)
