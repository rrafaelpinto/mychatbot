from django.contrib import admin

from .models import (
    AIUsageEvent,
    CandidateDocument,
    CandidateFact,
    CandidateProfile,
    Conversation,
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
    list_display = ("candidate", "fact_type", "verification_status", "updated_at")
    list_filter = ("fact_type", "verification_status")
    search_fields = ("candidate__name", "content")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "recruiter", "updated_at")
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
        "created_at",
    )
    list_filter = ("operation", "status", "provider", "model")
    readonly_fields = (
        "initiated_by",
        "candidate",
        "operation",
        "provider",
        "model",
        "status",
        "input_tokens",
        "output_tokens",
        "provider_request_id",
        "error_code",
        "created_at",
        "completed_at",
    )
