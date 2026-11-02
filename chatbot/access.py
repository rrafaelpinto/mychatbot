from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication

from chatbot.models import AccountAccess, CandidateProfile


def access_state(user):
    if not user.is_authenticated or not user.is_active:
        return "unavailable"
    if user.is_superuser:
        return "active"
    access = AccountAccess.objects.filter(user=user).first()
    if access is None:
        return "unavailable"
    if not access.email_verified_at:
        return "email_unverified"
    if access and access.role == AccountAccess.Role.RECRUITER:
        return "active"
    profile = CandidateProfile.objects.filter(user=user).first()
    if profile:
        return profile.status
    return (
        "pending_approval"
        if access.role == AccountAccess.Role.CANDIDATE
        else "unavailable"
    )


def is_candidate(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    access = AccountAccess.objects.filter(user=user).first()
    return (
        access.role == AccountAccess.Role.CANDIDATE
        if access
        else CandidateProfile.objects.filter(user=user).exists()
    )


class CandidateAccess(BasePermission):
    message = "An approved candidate account is required."

    def has_permission(self, request, view):
        return access_state(request.user) == "active" and is_candidate(request.user)


class AccountAccessMiddleware:
    """Block restricted accounts across API and legacy application routes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        exempt = path.startswith(("/admin/", "/api/v1/auth/", "/static/")) or path in {
            "/api/v1/me/",
            "/healthz/",
        }
        if not exempt:
            user = request.user
            if path.startswith("/api/"):
                try:
                    result = JWTAuthentication().authenticate(request)
                    if result:
                        user = result[0]
                except AuthenticationFailed:
                    pass
            if user.is_authenticated and access_state(user) != "active":
                return JsonResponse(
                    {
                        "detail": "Your account is awaiting approval or is unavailable.",
                        "account_status": access_state(user),
                    },
                    status=403,
                )
        response = self.get_response(request)
        if path.startswith("/api/v1/me/"):
            response["Cache-Control"] = "no-store"
        return response
