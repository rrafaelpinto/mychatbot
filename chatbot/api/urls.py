from django.urls import path

from . import views
from .auth import (
    CSRFTokenView,
    EmailCodeRequestView,
    EmailCodeVerifyView,
    TokenLoginView,
    TokenLogoutView,
    TokenRefreshView,
)
from .guest import GuestCandidateChatView

urlpatterns = [
    path(
        "me/documents/", views.OwnerDocumentListView.as_view(), name="api-me-documents"
    ),
    path(
        "me/documents/<int:pk>/",
        views.OwnerDocumentDetailView.as_view(),
        name="api-me-document",
    ),
    path(
        "me/documents/<int:pk>/extract/",
        views.OwnerDocumentExtractView.as_view(),
        name="api-me-document-extract",
    ),
    path(
        "me/profile/publication/",
        views.OwnerPublicationView.as_view(),
        name="api-me-publication",
    ),
    path(
        "me/facts/<int:fact_id>/",
        views.OwnerFactEditView.as_view(),
        name="api-me-fact-edit",
    ),
    path("auth/code/request/", EmailCodeRequestView.as_view(), name="api-code-request"),
    path("auth/code/verify/", EmailCodeVerifyView.as_view(), name="api-code-verify"),
    path("auth/csrf/", CSRFTokenView.as_view(), name="api-auth-csrf"),
    path("auth/token/", TokenLoginView.as_view(), name="api-auth-token"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-auth-refresh"),
    path("auth/logout/", TokenLogoutView.as_view(), name="api-auth-logout"),
    path(
        "me/facts/<int:fact_id>/review/",
        views.OwnerFactReviewView.as_view(),
        name="api-me-fact-review",
    ),
    path(
        "candidates/<slug:slug>/chat/",
        views.AuthenticatedCandidateChatView.as_view(),
        name="api-candidate-chat",
    ),
    path(
        "candidates/<slug:slug>/guest-chat/",
        GuestCandidateChatView.as_view(),
        name="api-candidate-guest-chat",
    ),
    path("candidates/", views.PublicCandidateListView.as_view(), name="api-candidates"),
    path(
        "candidates/<slug:slug>/",
        views.PublicCandidateDetailView.as_view(),
        name="api-candidate-detail",
    ),
    path("me/", views.AccountView.as_view(), name="api-me"),
    path("me/profile/", views.OwnerProfileView.as_view(), name="api-me-profile"),
    path("me/facts/", views.OwnerFactListView.as_view(), name="api-me-facts"),
]
