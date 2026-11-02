from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponseGone
from django.shortcuts import redirect
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny


def legacy_account(request, remaining=""):
    if request.method != "GET":
        return HttpResponseGone("Use the React application.")
    return redirect(settings.FRONTEND_URL + "/#/owner")


urlpatterns = [
    path("accounts/login/", legacy_account, name="login"),
    path("accounts/logout/", legacy_account, name="logout"),
    path("api/v1/", include("chatbot.api.urls")),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="api-schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="api-schema", permission_classes=[AllowAny]
        ),
        name="api-docs",
    ),
    path("admin/", admin.site.urls),
    path("accounts/", legacy_account),
    path("accounts/<path:remaining>", legacy_account),
    path("", include("chatbot.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
