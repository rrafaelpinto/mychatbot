from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("chatbot.urls")),
]

if settings.PUBLIC_REGISTRATION_ENABLED:
    urlpatterns.insert(
        1,
        path("accounts/", include("django_registration.backends.activation.urls")),
    )

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
