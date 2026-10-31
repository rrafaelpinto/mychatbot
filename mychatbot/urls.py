from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import Http404
from django.urls import include, path


def disabled_password_reset(request):
    """Reject unconfigured public password-reset requests."""
    raise Http404("Password reset is not configured.")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("chatbot.urls")),
]

if not settings.PASSWORD_RESET_ENABLED:
    urlpatterns.insert(1, path("accounts/password_reset/", disabled_password_reset))

if settings.PUBLIC_REGISTRATION_ENABLED:
    urlpatterns.insert(
        1,
        path("accounts/", include("django_registration.backends.activation.urls")),
    )

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
