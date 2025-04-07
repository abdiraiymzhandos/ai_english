import uuid
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib.auth import logout
from django.utils import timezone
from .models import UserProfile, UserDevice
from django.http import HttpResponsePermanentRedirect

class DeviceLockMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Тек аутентификацияланған пайдаланушыларға тексеру жүргіземіз.
        if request.user.is_authenticated:
            # Профиль бар-жоғын тексеріп, болмаса жасаймыз.
            profile, created = UserProfile.objects.get_or_create(user=request.user)

            # Егер аккаунт құлтаулы болса, шығарып, арнайы бетке бағыттаймыз.
            if profile.is_locked():
                logout(request)
                return redirect('/account-locked/')  # /account-locked/ URL-іне сәйкес бет жасаңыз.

            # Cookie-ден құрылғы идентификаторын алу.
            device_id = request.COOKIES.get('device_id')
            if not device_id:
                # Егер cookie жоқ болса, жаңа идентификатор генерациялап, оны request-ке сақтаймыз.
                device_id = str(uuid.uuid4())
                request.new_device_id = device_id
            else:
                request.new_device_id = None

            # Егер құрылғы тіркелмесе, тіркеу.
            if not UserDevice.objects.filter(user=request.user, device_id=device_id).exists():
                UserDevice.objects.create(user=request.user, device_id=device_id)

            # Тіркелген құрылғылар санын тексеру.
            device_count = UserDevice.objects.filter(user=request.user).count()
            if device_count > 3:
                # 3-тен көп құрылғы болған жағдайда аккаунтты 5 күнге құлтау.
                profile.lock(days=5)
                logout(request)
                return redirect('/account-locked/')

    def process_response(self, request, response):
        # Егер жаңа құрылғы идентификаторы генерацияланған болса, оны cookie-ге жазамыз.
        if hasattr(request, 'new_device_id') and request.new_device_id:
            response.set_cookie('device_id', request.new_device_id, max_age=60*60*24*365)  # 1 жылға
        return response


class WwwRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if host == "oqyai.kz":
            return HttpResponsePermanentRedirect(f"https://www.oqyai.kz{request.get_full_path()}")
        return self.get_response(request)