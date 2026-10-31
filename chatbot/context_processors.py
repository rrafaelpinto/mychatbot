from django.conf import settings


def release_flags(request):
    """Expose safe feature availability to public navigation templates."""
    del request
    return {"public_registration_enabled": settings.PUBLIC_REGISTRATION_ENABLED}
