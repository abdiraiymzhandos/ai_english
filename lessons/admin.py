from django.contrib import admin
from .models import Lesson, UserProfile, UserDevice, Lead


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "content")
    list_filter = ("created_at",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'is_paid', 'lock_until', 'date_joined')
    list_filter = ('is_paid',)
    search_fields = ('user__username', 'phone')
    actions = ['unlock_accounts', 'mark_as_paid']

    def unlock_accounts(self, request, queryset):
        for profile in queryset:
            profile.unlock()
        self.message_user(request, "Таңдалған аккаунттар құлтаудан шығарылды.")
    unlock_accounts.short_description = "Таңдалған аккаунттарды құлтаудан шығару"

    def mark_as_paid(self, request, queryset):
        updated = queryset.update(is_paid=True)
        self.message_user(request, f"{updated} аккаунт ақылы ретінде белгіленді.")
    mark_as_paid.short_description = "Таңдалғандарды ақылы қолданушы ету"

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