import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .storage import PrivateDocumentStorage
from .validators import validate_candidate_document


def candidate_document_path(instance, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"candidate-documents/{instance.candidate_id}/{uuid.uuid4().hex}{suffix}"


class CandidateProfileQuerySet(models.QuerySet):
    def publicly_viewable(self):
        return self.filter(
            status=CandidateProfile.Status.ACTIVE,
            publication_status=CandidateProfile.PublicationStatus.PUBLISHED,
        )


class CandidateProfile(models.Model):
    class Status(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", "Pending approval"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    class PublicationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    professional_summary = models.TextField(blank=True)
    image = models.ImageField(upload_to="candidate-images/", blank=True)
    linkedin = models.URLField(blank=True)
    show_linkedin = models.BooleanField(default=False)
    contact_email = models.EmailField(blank=True)
    show_contact_email = models.BooleanField(default=False)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_APPROVAL,
    )
    publication_status = models.CharField(
        max_length=16,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CandidateProfileQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(publication_status="draft") | models.Q(status="active")
                ),
                name="published_candidate_must_be_active",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            base_slug = slugify(self.name) or "candidate"
            slug = base_slug
            while (
                CandidateProfile.objects.exclude(pk=self.pk).filter(slug=slug).exists()
            ):
                slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
            self.slug = slug
        super().save(*args, **kwargs)

    def publish(self) -> None:
        if self.status != self.Status.ACTIVE:
            raise ValidationError("Only active candidates can be published.")
        self.publication_status = self.PublicationStatus.PUBLISHED

    def suspend(self) -> None:
        self.status = self.Status.SUSPENDED
        self.publication_status = self.PublicationStatus.DRAFT

    @property
    def image_url(self) -> str:
        if self.image:
            return self.image.url
        return "/static/img/DefaultAvatar.png"


class CandidateDocument(models.Model):
    class DocumentType(models.TextChoices):
        RESUME = "resume", "Resume"

    class ProcessingStatus(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file = models.FileField(
        storage=PrivateDocumentStorage(),
        upload_to=candidate_document_path,
        validators=[validate_candidate_document],
    )
    document_type = models.CharField(
        max_length=16,
        choices=DocumentType.choices,
        default=DocumentType.RESUME,
    )
    original_filename = models.CharField(max_length=255)
    detected_content_type = models.CharField(max_length=127)
    size_bytes = models.PositiveIntegerField()
    processing_status = models.CharField(
        max_length=16,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.UPLOADED,
    )
    extracted_text = models.TextField(blank=True, editable=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.candidate} - {self.original_filename}"

    def mark_processed(self, extracted_text: str) -> None:
        self.extracted_text = extracted_text
        self.processing_status = self.ProcessingStatus.PROCESSED
        self.processed_at = timezone.now()

    def mark_failed(self) -> None:
        self.extracted_text = ""
        self.processing_status = self.ProcessingStatus.FAILED
        self.processed_at = timezone.now()


class CandidateFact(models.Model):
    class FactType(models.TextChoices):
        SUMMARY = "summary", "Summary"
        EXPERIENCE = "experience", "Experience"
        EDUCATION = "education", "Education"
        SKILL = "skill", "Skill"
        PROJECT = "project", "Project"
        OTHER = "other", "Other"

    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="facts",
    )
    fact_type = models.CharField(max_length=16, choices=FactType.choices)
    content = models.TextField()
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    source_document = models.ForeignKey(
        CandidateDocument,
        on_delete=models.SET_NULL,
        related_name="facts",
        null=True,
        blank=True,
    )
    source_reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fact_type", "id"]

    def clean(self) -> None:
        super().clean()
        if (
            self.source_document_id
            and self.candidate_id
            and self.source_document.candidate_id != self.candidate_id
        ):
            raise ValidationError(
                {"source_document": "Evidence must belong to the same candidate."}
            )


class Conversation(models.Model):
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "recruiter"],
                name="one_conversation_per_recruiter_candidate",
            )
        ]

    def __str__(self) -> str:
        return f"{self.recruiter} and {self.candidate}"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class AIUsageEvent(models.Model):
    class Operation(models.TextChoices):
        CANDIDATE_CHAT = "candidate_chat", "Candidate chat"

    class Status(models.TextChoices):
        STARTED = "started", "Started"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ai_usage_events",
    )
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.PROTECT,
        related_name="ai_usage_events",
    )
    operation = models.CharField(max_length=32, choices=Operation.choices)
    provider = models.CharField(max_length=32, default="openai")
    model = models.CharField(max_length=127)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.STARTED,
    )
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    reserved_micro_usd = models.PositiveBigIntegerField(default=0)
    actual_micro_usd = models.PositiveBigIntegerField(null=True, blank=True)
    input_price_per_million = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )
    output_price_per_million = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)
    provider_request_id = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["initiated_by", "candidate", "operation", "idempotency_key"],
                name="unique_ai_request_idempotency_key",
            ),
        ]


class AIProjectBudget(models.Model):
    """Project-wide monetary reservation counters for current UTC windows."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    daily_window = models.DateField()
    monthly_window = models.DateField()
    daily_reserved_micro_usd = models.PositiveBigIntegerField(default=0)
    monthly_reserved_micro_usd = models.PositiveBigIntegerField(default=0)
