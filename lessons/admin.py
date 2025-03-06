from django.contrib import admin
from .models import Lesson


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "content")
    list_filter = ("created_at",)
