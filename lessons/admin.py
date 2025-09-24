from django.contrib import admin
from .models import Lesson, UserProfile, UserDevice, Lead


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "content")
    list_filter = ("created_at",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'is_paid', 'has_voice_access', 'voice_access_status', 'current_lesson', 'highest_lesson_reached', 'lock_until', 'date_joined')
    list_filter = ('is_paid', 'has_voice_access')
    search_fields = ('user__username', 'phone')
    actions = ['unlock_accounts', 'mark_as_paid', 'grant_voice_access_30_days', 'grant_voice_access_90_days', 'revoke_voice_access']

    def unlock_accounts(self, request, queryset):
        for profile in queryset:
            profile.unlock()
        self.message_user(request, "Таңдалған аккаунттар құлтаудан шығарылды.")
    unlock_accounts.short_description = "Таңдалған аккаунттарды құлтаудан шығару"

    def mark_as_paid(self, request, queryset):
        updated = queryset.update(is_paid=True)
        self.message_user(request, f"{updated} аккаунт ақылы ретінде белгіленді.")
    mark_as_paid.short_description = "Таңдалғандарды ақылы қолданушы ету"

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
                return f"✅ Белсенді ({obj.voice_access_until.strftime('%d.%m.%Y')} дейін)"
            else:
                return "✅ Белсенді (мерзімсіз)"
        else:
            return f"⏰ Мерзімі бітті ({obj.voice_access_until.strftime('%d.%m.%Y')})"
    voice_access_status.short_description = "Дауыс сабағы"

    def highest_lesson_reached(self, obj):
        return obj.get_highest_lesson_reached()
    highest_lesson_reached.short_description = "Ең жоғары өткен сабақ"

    def date_joined(self, obj):
        return obj.user.date_joined.strftime("%Y-%m-%d %H:%M")
    date_joined.short_description = "Тіркелген уақыты"


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_id', 'last_seen')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display  = ("name", "phone", "created_at")
    search_fields = ("name", "phone")
    ordering      = ("-created_at",)