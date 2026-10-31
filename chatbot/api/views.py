from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, views
from rest_framework.response import Response

from chatbot.api.serializers import (
    AccountSerializer,
    OwnerCandidateSerializer,
    OwnerFactSerializer,
    PublicCandidateDetailSerializer,
    PublicCandidateSerializer,
)
from chatbot.models import CandidateFact, CandidateProfile


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

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OwnerCandidateSerializer

    def get_object(self):
        obj = get_object_or_404(CandidateProfile, user=self.request.user)
        self.check_object_permissions(self.request, obj)
        return obj


@extend_schema(tags=["Current account"])
class OwnerFactListView(generics.ListAPIView):
    """List only the current user's facts, including their review state."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OwnerFactSerializer

    def get_queryset(self):
        return CandidateFact.objects.filter(
            candidate__user=self.request.user
        ).order_by("pk")
