from django.contrib import admin

from .models import (
    AIProjectBudget,
    AIUsageEvent,
    CandidateDocument,
    CandidateFact,
    CandidateProfile,
    Conversation,
    GuestChatSession,
    GuestOrigin,
    Message,
)


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "status", "publication_status", "updated_at")
    list_filter = ("status", "publication_status")
    search_fields = ("name", "user__username", "user__email")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CandidateDocument)
class CandidateDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "candidate",
        "original_filename",
        "processing_status",
        "size_bytes",
        "uploaded_at",
    )
    list_filter = ("document_type", "processing_status")
    readonly_fields = (
        "original_filename",
        "detected_content_type",
        "size_bytes",
        "processing_status",
        "extracted_text",
        "uploaded_at",
        "processed_at",
    )


@admin.register(CandidateFact)
class CandidateFactAdmin(admin.ModelAdmin):
    list_display = (
        "candidate",
        "import_key",
        "fact_type",
        "verification_status",
        "is_public",
        "updated_at",
    )
    list_filter = ("fact_type", "verification_status", "is_public")
    search_fields = ("candidate__name", "content", "import_key")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "recruiter", "guest_session", "updated_at")
    search_fields = ("candidate__name", "recruiter__username")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("content",)


@admin.register(AIUsageEvent)
class AIUsageEventAdmin(admin.ModelAdmin):
    list_display = (
        "operation",
        "candidate",
        "initiated_by",
        "model",
        "status",
        "reserved_micro_usd",
        "actual_micro_usd",
        "created_at",
    )
    list_filter = ("operation", "status", "provider", "model")
    readonly_fields = (
        "initiated_by",
        "guest_session",
        "guest_origin",
        "candidate",
        "operation",
        "provider",
        "model",
        "status",
        "input_tokens",
        "output_tokens",
        "provider_request_id",
        "idempotency_key",
        "reserved_micro_usd",
        "actual_micro_usd",
        "settled_at",
        "error_code",
        "created_at",
        "completed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AIProjectBudget)
class AIProjectBudgetAdmin(admin.ModelAdmin):
    list_display = (
        "daily_window",
        "monthly_window",
        "daily_reserved_micro_usd",
        "monthly_reserved_micro_usd",
    )
    readonly_fields = list_display

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GuestChatSession)
class GuestChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "created_at", "expires_at")
    readonly_fields = ("id", "candidate", "origin", "created_at", "expires_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GuestOrigin)
class GuestOriginAdmin(admin.ModelAdmin):
    list_display = ("created_at",)
    readonly_fields = ("digest", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
