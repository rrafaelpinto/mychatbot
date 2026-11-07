from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, views
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from chatbot.access import CandidateAccess
from chatbot.api.serializers import (
    AccountSerializer,
    CandidateChatHistorySerializer,
    CandidateChatInputSerializer,
    CandidateChatOutputSerializer,
    DocumentUploadSerializer,
    ExtractionResultSerializer,
    FactEditSerializer,
    FactReviewInputSerializer,
    OwnerCandidateSerializer,
    OwnerDocumentSerializer,
    OwnerFactSerializer,
    OwnerProfileUpdateSerializer,
    ProfilePublicationSerializer,
    PublicCandidateDetailSerializer,
    PublicCandidateSerializer,
)
from chatbot.models import (
    CandidateDocument,
    CandidateFact,
    CandidateFactReviewEvent,
    CandidateProfile,
    Conversation,
    Message,
)
from chatbot.services.ai import (
    AILimitExceeded,
    AINotAuthorized,
    AIRequestAlreadySubmitted,
    AIServiceError,
    AIUnavailable,
    ask_candidate,
    public_evidence,
)
from chatbot.services.documents import (
    DocumentProcessingError,
    create_candidate_document,
    process_candidate_document,
)
from chatbot.services.fact_review import fact_review_action_error
from chatbot.services.knowledge_extraction import (
    ExtractionUnavailable,
    KnowledgeExtractionError,
    extract_candidate_facts,
)


@extend_schema(tags=["Public candidates"])
class PublicCandidateListView(generics.ListAPIView):
    """List only profiles approved for public access."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PublicCandidateSerializer
    queryset = CandidateProfile.objects.publicly_viewable().order_by("pk")


@extend_schema(tags=["Public candidates"])
class PublicCandidateDetailView(generics.RetrieveAPIView):
    """Fetch an approved profile with only currently public, verified facts."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PublicCandidateDetailSerializer
    lookup_field = "slug"
    queryset = CandidateProfile.objects.publicly_viewable()


@extend_schema(tags=["Current account"])
class AccountView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=AccountSerializer)
    def get(self, request):
        """Return the authenticated account without any cross-user lookup."""
        return Response(AccountSerializer(request.user).data)


@extend_schema(tags=["Current account"])
class OwnerProfileView(generics.RetrieveAPIView):
    """Return only the authenticated account's candidate profile."""

    permission_classes = [permissions.IsAuthenticated, CandidateAccess]
    serializer_class = OwnerCandidateSerializer

    @extend_schema(
        request=OwnerProfileUpdateSerializer, responses={201: OwnerCandidateSerializer}
    )
    def post(self, request):
        from django.contrib.auth import get_user_model

        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if CandidateProfile.objects.filter(user=request.user).exists():
                return Response({"detail": "A profile already exists."}, status=409)
            serializer = OwnerProfileUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            candidate = serializer.save(
                user=request.user, status=CandidateProfile.Status.ACTIVE
            )
        return Response(OwnerCandidateSerializer(candidate).data, status=201)

    def get_object(self):
        obj = get_object_or_404(CandidateProfile, user=self.request.user)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(
        request=OwnerProfileUpdateSerializer, responses=OwnerCandidateSerializer
    )
    def patch(self, request):
        """Update only safe owner-controlled profile fields."""
        candidate = self.get_object()
        serializer = OwnerProfileUpdateSerializer(
            candidate, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OwnerCandidateSerializer(candidate).data)


@extend_schema(tags=["Current account"])
class OwnerFactListView(generics.ListAPIView):
    """List only the current user's facts, including their review state."""

    permission_classes = [permissions.IsAuthenticated, CandidateAccess]
    serializer_class = OwnerFactSerializer

    def get_queryset(self):
        return CandidateFact.objects.filter(candidate__user=self.request.user).order_by(
            "pk"
        )


@extend_schema(tags=["Current account"])
class OwnerFactReviewView(views.APIView):
    """Apply audited fact review decisions with version-based concurrency control."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CandidateAccess]

    @extend_schema(request=FactReviewInputSerializer, responses=OwnerFactSerializer)
    def post(self, request, fact_id):
        serializer = FactReviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        with transaction.atomic():
            fact = get_object_or_404(
                CandidateFact.objects.select_for_update(),
                pk=fact_id,
                candidate__user=request.user,
            )
            if fact.updated_at != serializer.validated_data["version"]:
                return Response(
                    {"detail": "Fact changed. Reload before reviewing."}, status=409
                )
            previous_status = fact.verification_status
            previous_public = fact.is_public
            error = fact_review_action_error(
                action=action,
                changed=False,
                status=previous_status,
                is_public=previous_public,
            )
            if error:
                return Response({"detail": error}, status=409)
            if action == "approve":
                fact.verification_status = CandidateFact.VerificationStatus.VERIFIED
                fact.is_public = False
            elif action == "reject":
                fact.verification_status = CandidateFact.VerificationStatus.REJECTED
                fact.is_public = False
            elif action == "reopen":
                fact.verification_status = CandidateFact.VerificationStatus.PENDING
                fact.is_public = False
            elif action == "publish":
                fact.is_public = True
            else:
                fact.is_public = False
            try:
                fact.full_clean()
            except ValidationError as exc:
                raise APIValidationError(exc.message_dict) from exc
            fact.save(update_fields=["verification_status", "is_public", "updated_at"])
            CandidateFactReviewEvent.objects.create(
                fact=fact,
                reviewed_by=request.user,
                action={
                    "approve": CandidateFactReviewEvent.Action.APPROVED,
                    "reject": CandidateFactReviewEvent.Action.REJECTED,
                    "reopen": CandidateFactReviewEvent.Action.REOPENED,
                    "publish": CandidateFactReviewEvent.Action.PUBLISHED,
                    "unpublish": CandidateFactReviewEvent.Action.UNPUBLISHED,
                }[action],
                previous_status=previous_status,
                new_status=fact.verification_status,
                previous_public=previous_public,
                new_public=fact.is_public,
            )
        return Response(OwnerFactSerializer(fact).data)


@extend_schema(tags=["Authenticated Candidate Agent"])
class AuthenticatedCandidateChatView(views.APIView):
    """Use the existing Candidate Agent admission and citation security boundary."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _candidate(slug):
        return get_object_or_404(
            CandidateProfile.objects.publicly_viewable(), slug=slug
        )

    @extend_schema(responses=CandidateChatHistorySerializer(many=True))
    def get(self, request, slug):
        """Return only this recruiter's messages with still-valid public evidence."""
        candidate = self._candidate(slug)
        conversation = Conversation.objects.filter(
            candidate=candidate, recruiter=request.user
        ).first()
        history = []
        if conversation:
            for message in conversation.messages.all():
                evidence = ()
                content = message.content
                if message.role == Message.Role.ASSISTANT and message.evidence_fact_ids:
                    evidence = public_evidence(candidate, message.evidence_fact_ids)
                    if evidence is None:
                        content = "This answer is no longer available because its evidence changed."
                        evidence = ()
                history.append(
                    {
                        "role": message.role,
                        "content": content,
                        "evidence": evidence,
                    }
                )
        return Response(history)

    @extend_schema(
        request=CandidateChatInputSerializer,
        responses={200: CandidateChatOutputSerializer},
    )
    def post(self, request, slug):
        """Ask a bounded paid question and persist only after provider success."""
        candidate = self._candidate(slug)
        serializer = CandidateChatInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key")
        if key is None or (
            not 1 <= len(key) <= 128 or not key.isascii() or not key.isprintable()
        ):
            raise APIValidationError({"idempotency_key": "Invalid idempotency key."})
        question = serializer.validated_data["question"]
        try:
            answer = ask_candidate(
                candidate=candidate,
                initiated_by=request.user,
                question=question,
                idempotency_key=key,
            )
        except AINotAuthorized:
            return Response({"detail": "Not found."}, status=404)
        except AIRequestAlreadySubmitted as exc:
            return Response({"detail": str(exc)}, status=409)
        except AILimitExceeded as exc:
            return Response({"detail": str(exc)}, status=429)
        except AIUnavailable:
            return Response(
                {"detail": "The Candidate Agent is temporarily unavailable."},
                status=503,
            )
        except AIServiceError as exc:
            return Response({"detail": str(exc)}, status=409)
        conversation, _ = Conversation.objects.get_or_create(
            candidate=candidate, recruiter=request.user
        )
        Message.objects.bulk_create(
            [
                Message(
                    conversation=conversation, role=Message.Role.USER, content=question
                ),
                Message(
                    conversation=conversation,
                    role=Message.Role.ASSISTANT,
                    content=answer.content,
                    evidence_fact_ids=list(answer.cited_fact_ids),
                ),
            ]
        )
        conversation.save(update_fields=["updated_at"])
        return Response({"response": answer.content, "evidence": answer.evidence})


@extend_schema(tags=["Current account"])
class OwnerDocumentListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, CandidateAccess]
    serializer_class = OwnerDocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return CandidateDocument.objects.filter(
            candidate__user=self.request.user
        ).order_by("-pk")

    @extend_schema(
        request=DocumentUploadSerializer, responses={201: OwnerDocumentSerializer}
    )
    def post(self, request):
        if not settings.CANDIDATE_UPLOADS_ENABLED:
            return Response(
                {"detail": "Uploads are currently unavailable."}, status=503
            )
        candidate = get_object_or_404(CandidateProfile, user=request.user)
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = create_candidate_document(
                candidate, serializer.validated_data["document"]
            )
        except ValidationError as exc:
            raise APIValidationError({"document": exc.messages}) from exc
        try:
            process_candidate_document(document)
        except DocumentProcessingError:
            pass
        return Response(OwnerDocumentSerializer(document).data, status=201)


@extend_schema(tags=["Current account"])
class OwnerDocumentDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, CandidateAccess]
    serializer_class = OwnerDocumentSerializer

    def get_queryset(self):
        return CandidateDocument.objects.filter(candidate__user=self.request.user)


@extend_schema(tags=["Current account"])
class OwnerDocumentExtractView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, CandidateAccess]

    @extend_schema(request=None, responses=ExtractionResultSerializer)
    def post(self, request, pk):
        document = get_object_or_404(
            CandidateDocument.objects.select_related("candidate"),
            pk=pk,
            candidate__user=request.user,
        )
        try:
            result = extract_candidate_facts(
                document=document,
                candidate=document.candidate,
                initiated_by=request.user,
            )
        except ExtractionUnavailable as exc:
            return Response({"detail": str(exc)}, status=503)
        except KnowledgeExtractionError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(
            {
                "proposed_count": result.proposed_count,
                "already_completed": result.already_completed,
            }
        )


@extend_schema(tags=["Current account"])
class OwnerPublicationView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, CandidateAccess]

    @extend_schema(
        request=ProfilePublicationSerializer, responses=OwnerCandidateSerializer
    )
    def post(self, request):
        serializer = ProfilePublicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            candidate = get_object_or_404(
                CandidateProfile.objects.select_for_update(), user=request.user
            )
            if serializer.validated_data["published"]:
                try:
                    candidate.publish()
                except ValidationError as exc:
                    raise APIValidationError(exc.messages) from exc
            else:
                candidate.publication_status = CandidateProfile.PublicationStatus.DRAFT
            candidate.save(update_fields=["publication_status", "updated_at"])
        return Response(OwnerCandidateSerializer(candidate).data)


@extend_schema(tags=["Current account"])
class OwnerFactEditView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, CandidateAccess]

    @extend_schema(request=FactEditSerializer, responses=OwnerFactSerializer)
    def patch(self, request, fact_id):
        serializer = FactEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            fact = get_object_or_404(
                CandidateFact.objects.select_for_update(),
                pk=fact_id,
                candidate__user=request.user,
            )
            if fact.updated_at != serializer.validated_data["version"]:
                return Response(
                    {"detail": "Fact changed. Reload before editing."}, status=409
                )
            if fact.content != serializer.validated_data["content"]:
                old_status, old_public = fact.verification_status, fact.is_public
                fact.content = serializer.validated_data["content"]
                fact.verification_status = CandidateFact.VerificationStatus.PENDING
                fact.is_public = False
                fact.save(
                    update_fields=[
                        "content",
                        "verification_status",
                        "is_public",
                        "updated_at",
                    ]
                )
                CandidateFactReviewEvent.objects.create(
                    fact=fact,
                    reviewed_by=request.user,
                    action=CandidateFactReviewEvent.Action.EDITED,
                    previous_status=old_status,
                    new_status=fact.verification_status,
                    previous_public=old_public,
                    new_public=False,
                )
        return Response(OwnerFactSerializer(fact).data)
