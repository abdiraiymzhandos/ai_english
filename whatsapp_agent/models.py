from django.db import models


class WhatsAppLead(models.Model):
    LANGUAGE_CHOICES = [
        ("kk", "Kazakh"),
        ("ru", "Russian"),
        ("unknown", "Unknown"),
    ]
    STATUS_CHOICES = [
        ("new", "New"),
        ("engaged", "Engaged"),
        ("warm", "Warm"),
        ("payment_intent", "Payment intent"),
        ("receipt_received", "Receipt received"),
        ("customer", "Customer"),
        ("handed_off", "Handed off"),
        ("lost", "Lost"),
    ]

    phone_number = models.CharField(max_length=32, unique=True, db_index=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    language_preference = models.CharField(
        max_length=16,
        choices=LANGUAGE_CHOICES,
        default="unknown",
    )
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="new")
    source = models.CharField(max_length=64, default="whatsapp")
    handoff_needed = models.BooleanField(default=False)
    existing_user_linked = models.BooleanField(default=False)
    paid_access_granted = models.BooleanField(default=False)
    last_user_message_at = models.DateTimeField(blank=True, null=True)
    last_bot_message_at = models.DateTimeField(blank=True, null=True)
    last_intent = models.CharField(max_length=64, blank=True, null=True)
    message_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.phone_number} ({self.status})"


class WhatsAppMessage(models.Model):
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("system", "System"),
    ]
    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("document", "Document"),
        ("audio", "Audio"),
        ("interactive", "Interactive"),
        ("unknown", "Unknown"),
    ]

    lead = models.ForeignKey(
        WhatsAppLead,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    meta_message_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=16, choices=MESSAGE_TYPE_CHOICES, default="unknown")
    text_content = models.TextField(blank=True)
    media_id = models.CharField(max_length=255, blank=True)
    media_mime_type = models.CharField(max_length=255, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    delivered = models.BooleanField(default=False)
    read = models.BooleanField(default=False)
    failed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.direction} {self.message_type} {self.meta_message_id or self.pk}"


class WhatsAppAgentEvent(models.Model):
    lead = models.ForeignKey(
        WhatsAppLead,
        on_delete=models.SET_NULL,
        related_name="events",
        blank=True,
        null=True,
    )
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.event_type


class WhatsAppReceipt(models.Model):
    FILE_TYPE_CHOICES = [
        ("pdf", "PDF"),
        ("image", "Image"),
        ("unknown", "Unknown"),
    ]

    lead = models.ForeignKey(
        WhatsAppLead,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    message = models.ForeignKey(
        WhatsAppMessage,
        on_delete=models.SET_NULL,
        related_name="receipts",
        blank=True,
        null=True,
    )
    file_type = models.CharField(max_length=16, choices=FILE_TYPE_CHOICES, default="unknown")
    file = models.FileField(upload_to="whatsapp_receipts/%Y/%m/%d/", blank=True, null=True)
    extracted_text = models.TextField(blank=True)
    amount_detected = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    receiver_phone_detected = models.CharField(max_length=32, blank=True)
    receiver_name_detected = models.CharField(max_length=255, blank=True)
    timestamp_detected = models.DateTimeField(blank=True, null=True)
    validation_confidence = models.FloatField(default=0)
    is_validated = models.BooleanField(default=False)
    validation_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Receipt {self.pk} for {self.lead.phone_number}"

