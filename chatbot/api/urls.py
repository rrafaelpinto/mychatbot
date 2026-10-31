from django.urls import path

from . import views

urlpatterns = [
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
