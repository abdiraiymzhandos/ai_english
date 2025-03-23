from django.contrib import admin
from .models import Lesson, UserProfile, UserDevice


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "content")
    list_filter = ("created_at",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'lock_until')
    actions = ['unlock_accounts']

    def unlock_accounts(self, request, queryset):
        for profile in queryset:
            profile.unlock()
        self.message_user(request, "Таңдалған аккаунттар құлтаудан шығарылды.")
    unlock_accounts.short_description = "Таңдалған аккаунттарды құлтаудан шығару"


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_id', 'last_seen')
