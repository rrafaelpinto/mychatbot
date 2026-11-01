from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status, views
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken


class CredentialsSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class AccessTokenSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    token_type = serializers.CharField(read_only=True)
    expires_in = serializers.IntegerField(read_only=True)


class CSRFTokenSerializer(serializers.Serializer):
    csrf_token = serializers.CharField(read_only=True)


def _no_store(response):
    response["Cache-Control"] = "no-store"
    return response


def _set_refresh_cookie(response, token):
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.JWT_REFRESH_COOKIE_PATH,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )
    return _no_store(response)


def _clear_refresh_cookie(response):
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )
    return _no_store(response)


def _response_for_access(access):
    return Response(
        {
            "access": str(access),
            "token_type": "Bearer",
            "expires_in": int(
                settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()
            ),
        }
    )


@method_decorator(ensure_csrf_cookie, name="dispatch")
@extend_schema(tags=["Authentication"])
class CSRFTokenView(views.APIView):
    """Bootstrap a CSRF token for the independently hosted frontend."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_csrf"

    @extend_schema(responses=CSRFTokenSerializer)
    def get(self, request):
        return _no_store(Response({"csrf_token": get_token(request._request)}))


class PublicTokenView(views.APIView):
    """Preserve HTTP 401 for auth requests with no bearer header."""

    authentication_classes = []

    def get_authenticate_header(self, request):
        """Provide the API authentication challenge for invalid credentials."""
        return "Bearer"


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(tags=["Authentication"])
class TokenLoginView(PublicTokenView):
    """Exchange credentials for an in-memory access token and protected cookie."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    @extend_schema(request=CredentialsSerializer, responses={200: AccessTokenSerializer})
    def post(self, request):
        serializer = CredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request._request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            raise AuthenticationFailed("Invalid credentials.")
        refresh = RefreshToken.for_user(user)
        return _set_refresh_cookie(
            _response_for_access(refresh.access_token),
            str(refresh),
        )


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(tags=["Authentication"])
class TokenRefreshView(PublicTokenView):
    """Rotate a cookie-held refresh token with row-locked replay prevention."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"

    @extend_schema(request=None, responses={200: AccessTokenSerializer})
    def post(self, request):
        raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not raw:
            raise AuthenticationFailed("Refresh token is missing.")
        try:
            with transaction.atomic():
                old = RefreshToken(raw)
                outstanding = OutstandingToken.objects.select_for_update().filter(
                    jti=old["jti"]
                ).first()
                if outstanding is None:
                    raise AuthenticationFailed("Refresh token is invalid.")
                serializer = TokenRefreshSerializer(data={"refresh": raw})
                serializer.is_valid(raise_exception=True)
                rotated = serializer.validated_data
        except TokenError as exc:
            raise AuthenticationFailed("Refresh token is invalid.") from exc
        # Never return a refresh token through JSON or browser-readable storage.
        return _set_refresh_cookie(
            _response_for_access(rotated["access"]),
            rotated["refresh"],
        )


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(tags=["Authentication"])
class TokenLogoutView(PublicTokenView):
    """Revoke only the presented refresh credential; leave Django admin alone."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if raw:
            try:
                with transaction.atomic():
                    RefreshToken(raw).blacklist()
            except TokenError:
                pass
        return _clear_refresh_cookie(Response(status=status.HTTP_204_NO_CONTENT))
