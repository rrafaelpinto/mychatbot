from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from chatbot.models import CandidateFact, CandidateProfile


class PublicCandidateSerializer(serializers.ModelSerializer):
    """Expose only public candidate profile fields and consented contact data."""

    image_url = serializers.CharField(read_only=True)
    linkedin = serializers.SerializerMethodField()
    contact_email = serializers.SerializerMethodField()

    class Meta:
        model = CandidateProfile
        fields = (
            "slug",
            "name",
            "professional_summary",
            "image_url",
            "linkedin",
            "contact_email",
        )
        read_only_fields = fields

    @staticmethod
    def get_linkedin(obj) -> str | None:
        return obj.linkedin if obj.show_linkedin and obj.linkedin else None

    @staticmethod
    def get_contact_email(obj) -> str | None:
        return (
            obj.contact_email if obj.show_contact_email and obj.contact_email else None
        )


class PublicFactSerializer(serializers.ModelSerializer):
    """Expose public, verified professional claims without private provenance."""

    class Meta:
        model = CandidateFact
        fields = ("id", "fact_type", "content")
        read_only_fields = fields


class PublicCandidateDetailSerializer(PublicCandidateSerializer):
    facts = serializers.SerializerMethodField()

    class Meta(PublicCandidateSerializer.Meta):
        fields = (*PublicCandidateSerializer.Meta.fields, "facts")

    @extend_schema_field(PublicFactSerializer(many=True))
    def get_facts(self, obj) -> list[dict]:
        facts = CandidateFact.objects.filter(
            candidate=obj,
            verification_status=CandidateFact.VerificationStatus.VERIFIED,
            is_public=True,
        ).order_by("fact_type", "id")
        return PublicFactSerializer(facts, many=True).data


class AccountSerializer(serializers.ModelSerializer):
    """Serialize only the authenticated account's basic identity."""

    role = serializers.SerializerMethodField()
    account_status = serializers.SerializerMethodField()
    can_manage_candidate = serializers.SerializerMethodField()
    is_superuser = serializers.BooleanField(read_only=True)
    uploads_enabled = serializers.SerializerMethodField()

    def get_role(self, obj) -> str:
        from chatbot.models import AccountAccess

        if obj.is_superuser:
            return "superuser"
        access = AccountAccess.objects.filter(user=obj).first()
        return (
            access.role
            if access
            else (
                "candidate"
                if CandidateProfile.objects.filter(user=obj).exists()
                else "recruiter"
            )
        )

    def get_account_status(self, obj) -> str:
        from chatbot.access import access_state

        return access_state(obj)

    def get_can_manage_candidate(self, obj) -> bool:
        from chatbot.access import access_state, is_candidate

        return access_state(obj) == "active" and is_candidate(obj)

    def get_uploads_enabled(self, obj) -> bool:
        from django.conf import settings

        return settings.CANDIDATE_UPLOADS_ENABLED

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "email",
            "role",
            "account_status",
            "can_manage_candidate",
            "is_superuser",
            "uploads_enabled",
        )
        read_only_fields = fields


class OwnerCandidateSerializer(serializers.ModelSerializer):
    """Expose owned profile controls without raw document data."""

    class Meta:
        model = CandidateProfile
        fields = (
            "slug",
            "name",
            "professional_summary",
            "image_url",
            "linkedin",
            "show_linkedin",
            "contact_email",
            "show_contact_email",
            "phone",
            "status",
            "publication_status",
        )
        read_only_fields = fields


class OwnerFactSerializer(serializers.ModelSerializer):
    """Expose owner-review status but never document provenance or raw uploads."""

    class Meta:
        model = CandidateFact
        fields = (
            "id",
            "fact_type",
            "content",
            "verification_status",
            "is_public",
            "updated_at",
        )
        read_only_fields = fields


class OwnerProfileUpdateSerializer(serializers.ModelSerializer):
    """Allow only owner-editable profile text and contact visibility."""

    class Meta:
        model = CandidateProfile
        fields = (
            "name",
            "professional_summary",
            "linkedin",
            "show_linkedin",
            "contact_email",
            "show_contact_email",
            "phone",
        )

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {key: ["This field is not editable."] for key in sorted(unknown)}
            )
        return super().to_internal_value(data)


class FactReviewInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=("approve", "reject", "reopen", "publish", "unpublish")
    )
    version = serializers.DateTimeField()


class CandidateChatInputSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000, trim_whitespace=True)


class CandidateChatOutputSerializer(serializers.Serializer):
    response = serializers.CharField(read_only=True)
    evidence = PublicFactSerializer(many=True, read_only=True)


class CandidateChatHistorySerializer(serializers.Serializer):
    role = serializers.CharField(read_only=True)
    content = serializers.CharField(read_only=True)
    evidence = PublicFactSerializer(many=True, read_only=True)


class OwnerDocumentSerializer(serializers.ModelSerializer):
    extraction_status = serializers.SerializerMethodField()

    class Meta:
        from chatbot.models import CandidateDocument

        model = CandidateDocument
        fields = (
            "id",
            "original_filename",
            "size_bytes",
            "processing_status",
            "uploaded_at",
            "extraction_status",
        )
        read_only_fields = fields

    def get_extraction_status(self, obj) -> str:
        from chatbot.models import CandidateExtractionRun

        run = CandidateExtractionRun.objects.filter(document=obj).first()
        return run.status if run else "not_started"


class DocumentUploadSerializer(serializers.Serializer):
    document = serializers.FileField()

    def validate_document(self, value):
        from chatbot.validators import validate_candidate_document

        validate_candidate_document(value)
        return value


class ProfilePublicationSerializer(serializers.Serializer):
    published = serializers.BooleanField()


class ExtractionResultSerializer(serializers.Serializer):
    proposed_count = serializers.IntegerField(read_only=True)
    already_completed = serializers.BooleanField(read_only=True)


class FactEditSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000)
    version = serializers.DateTimeField()
