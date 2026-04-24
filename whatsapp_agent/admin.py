from django.contrib import admin

from .models import WhatsAppAgentEvent, WhatsAppLead, WhatsAppMessage, WhatsAppReceipt


@admin.register(WhatsAppLead)
class WhatsAppLeadAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "first_name",
        "language_preference",
        "status",
        "handoff_needed",
        "existing_user_linked",
        "paid_access_granted",
        "message_count",
        "last_user_message_at",
        "updated_at",
    )
    list_filter = ("status", "language_preference", "handoff_needed", "paid_access_granted", "existing_user_linked")
    search_fields = ("phone_number", "first_name", "metadata")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = (
        "lead",
        "direction",
        "message_type",
        "meta_message_id",
        "short_text",
        "delivered",
        "read",
        "failed",
        "created_at",
    )
    list_filter = ("direction", "message_type", "delivered", "read", "failed")
    search_fields = ("meta_message_id", "text_content", "lead__phone_number")
    readonly_fields = ("created_at",)

    def short_text(self, obj):
        return (obj.text_content or "")[:80]


@admin.register(WhatsAppReceipt)
class WhatsAppReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lead",
        "file_type",
        "amount_detected",
        "receiver_phone_detected",
        "validation_confidence",
        "is_validated",
        "timestamp_detected",
        "created_at",
    )
    list_filter = ("file_type", "is_validated")
    search_fields = ("lead__phone_number", "receiver_phone_detected", "receiver_name_detected", "validation_notes")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WhatsAppAgentEvent)
class WhatsAppAgentEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "lead", "created_at")
    list_filter = ("event_type",)
    search_fields = ("event_type", "lead__phone_number")
    readonly_fields = ("created_at",)

