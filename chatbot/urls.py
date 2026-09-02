from django.urls import path

from . import views

urlpatterns = [
    path("", views.about, name="about"),
    path("about/", views.about, name="about"),
    path("candidate/", views.manager_candidate, name="manager_candidate"),
    path("candidates/", views.candidates, name="candidates"),
    path("u/<slug:slug>/", views.public_profile, name="public_profile"),
    path("profile/", views.profile, name="profile"),
    path("chat/<slug:slug>/", views.chat, name="chat"),
    path("conversations/", views.conversations, name="conversations"),
    path(
        "conversations/<int:conversation_id>/",
        views.conversation_detail,
        name="conversation_detail",
    ),
]
