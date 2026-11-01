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

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email")
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
