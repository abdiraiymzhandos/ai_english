from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import path
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib import admin
from django.utils.timezone import localtime
from .models import Lesson, UserProfile, UserDevice, Lead


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "content")
    list_filter = ("created_at",)


class DeviceOverflowFilter(admin.SimpleListFilter):
    title = "Құрылғы саны"
    parameter_name = "over_device_limit"

    def lookups(self, request, model_admin):
        return [('1', 'Шектен көп')]

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.annotate(device_total=Count('user__devices')).filter(
                device_total__gt=settings.MAX_ACCOUNT_DEVICES)
        return queryset


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'is_paid', 'has_voice_access', 'voice_access_status', 'translator_access_status', 'current_lesson', 'highest_lesson_reached', 'lock_until', 'date_joined')
    list_filter = ('is_paid', 'has_voice_access', 'has_translator_access', DeviceOverflowFilter)
    change_form_template = 'admin/lessons/userprofile/change_form.html'
    readonly_fields = ('lock_until',)
    search_fields = ('user__username', 'phone')
    actions = ['unlock_accounts', 'mark_as_paid', 'grant_voice_access_30_days', 'grant_voice_access_90_days', 'revoke_voice_access', 'grant_translator_access_30_days', 'grant_translator_access_90_days', 'revoke_translator_access']

    def has_unlock_permission(self, request):
        return self.admin_site.has_permission(request) and request.user.is_superuser

    def get_urls(self):
        return [path('<int:object_id>/unlock/', self.unlock_view, name='lessons_userprofile_unlock')] + super().get_urls()

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj is not None:
            context.update(can_unlock=self.has_unlock_permission(request),
                           device_total=UserDevice.objects.filter(user_id=obj.user_id).count(),
                           locked=obj.is_locked())
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_model(self, request, obj, form, change):
        if change:
            # A concurrent device decision must survive an ordinary profile edit.
            obj.save(update_fields=[f.name for f in obj._meta.fields if f.name in form.changed_data
                                    and f.name != 'lock_until'])
        else:
            super().save_model(request, obj, form, change)

    def unlock_and_log(self, request, profile):
        with transaction.atomic():
            removed = profile.unlock()
            self.log_change(request, profile, f"Аккаунт құлпы ашылды. Тазаланған құрылғылар: {removed}.")
        return removed

    @method_decorator([never_cache, require_POST, csrf_protect])
    def unlock_view(self, request, object_id):
        if not self.has_unlock_permission(request):
            raise PermissionDenied
        profile = get_object_or_404(UserProfile, pk=object_id)
        removed = self.unlock_and_log(request, profile)
        self.message_user(request, f"Аккаунт ашылды. Тазаланған құрылғылар саны: {removed}.")
        return redirect('admin:lessons_userprofile_change', object_id)

    def changelist_view(self, request, extra_context=None):
        if request.POST.get('action') == 'unlock_accounts' and not self.has_unlock_permission(request):
            raise PermissionDenied
        return super().changelist_view(request, extra_context)

    @admin.action(permissions=['unlock'], description="Таңдалған аккаунттардың құлпын ашу")
    def unlock_accounts(self, request, queryset):
        if not self.has_unlock_permission(request):
            raise PermissionDenied
        removed = sum(self.unlock_and_log(request, profile) for profile in queryset.order_by('pk'))
        self.message_user(request, f"Таңдалған аккаунттар ашылды. Тазаланған құрылғылар саны: {removed}.")

    @admin.action(permissions=['change'], description="Тексерілген курс төлемін растау және ақылы қолжетімділік беру")
    def mark_as_paid(self, request, queryset):
        from insights.purchases import confirm_course_payment
        count = confirm_course_payment(request.user, queryset)
        self.message_user(request, f"Расталған жаңа төлемдер: {count}")

    def grant_voice_access_30_days(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.grant_voice_access(days=30)
            count += 1
        self.message_user(request, f"{count} қолданушыға 30 күнге дауыс сабағына қол жеткізу берілді.")
    grant_voice_access_30_days.short_description = "30 күнге дауыс сабағына қол жеткізу беру"

    def grant_voice_access_90_days(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.grant_voice_access(days=90)
            count += 1
        self.message_user(request, f"{count} қолданушыға 90 күнге дауыс сабағына қол жеткізу берілді.")
    grant_voice_access_90_days.short_description = "90 күнге дауыс сабағына қол жеткізу беру"

    def revoke_voice_access(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.revoke_voice_access()
            count += 1
        self.message_user(request, f"{count} қолданушыдан дауыс сабағына қол жеткізу алынып тасталды.")
    revoke_voice_access.short_description = "Дауыс сабағына қол жеткізуді алып тастау"

    def voice_access_status(self, obj):
        if not obj.has_voice_access:
            return "❌ Жоқ"
        if obj.has_active_voice_access():
            if obj.voice_access_until:
                return f"✅ Белсенді ({localtime(obj.voice_access_until).strftime('%d.%m.%Y')} дейін)"
            else:
                return "✅ Белсенді (мерзімсіз)"
        else:
            return f"⏰ Мерзімі бітті ({localtime(obj.voice_access_until).strftime('%d.%m.%Y')})"
    voice_access_status.short_description = "Дауыс сабағы"

    def grant_translator_access_30_days(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.grant_translator_access(days=30)
            count += 1
        self.message_user(request, f"{count} қолданушыға 30 күнге аудармашы көмекшісіне қол жеткізу берілді.")
    grant_translator_access_30_days.short_description = "30 күнге аудармашы көмекшісіне қол жеткізу беру"

    def grant_translator_access_90_days(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.grant_translator_access(days=90)
            count += 1
        self.message_user(request, f"{count} қолданушыға 90 күнге аудармашы көмекшісіне қол жеткізу берілді.")
    grant_translator_access_90_days.short_description = "90 күнге аудармашы көмекшісіне қол жеткізу беру"

    def revoke_translator_access(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.revoke_translator_access()
            count += 1
        self.message_user(request, f"{count} қолданушыдан аудармашы көмекшісіне қол жеткізу алынып тасталды.")
    revoke_translator_access.short_description = "Аудармашы көмекшісіне қол жеткізуді алып тастау"

    def translator_access_status(self, obj):
        if not obj.has_translator_access:
            return "❌ Жоқ"
        if obj.has_active_translator_access():
            if obj.translator_access_until:
                return f"✅ Белсенді ({localtime(obj.translator_access_until).strftime('%d.%m.%Y')} дейін)"
            else:
                return "✅ Белсенді (мерзімсіз)"
        else:
            return f"⏰ Мерзімі бітті ({localtime(obj.translator_access_until).strftime('%d.%m.%Y')})"
    translator_access_status.short_description = "Аудармашы көмекшісі"

    def highest_lesson_reached(self, obj):
        return obj.get_highest_lesson_reached()
    highest_lesson_reached.short_description = "Ең жоғары өткен сабақ"

    def date_joined(self, obj):
        return localtime(obj.user.date_joined).strftime("%Y-%m-%d %H:%M")
    date_joined.short_description = "Тіркелген уақыты"


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_id', 'last_seen')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display  = ("name", "phone", "created_at")
    search_fields = ("name", "phone")
    ordering      = ("-created_at",)