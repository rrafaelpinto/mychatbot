"""Hermetic defaults for tests, with opt-in PostgreSQL integration in CI."""

import os

from .settings import *  # noqa: F403

SECRET_KEY = "test-only-secret-key-with-sufficient-length-for-django-checks"
DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PRIVATE_MEDIA_ROOT = BASE_DIR / ".test-private-media"  # noqa: F405
MEDIA_ROOT = BASE_DIR / ".test-public-media"  # noqa: F405

if os.environ.get("TEST_WITH_POSTGRES", "").lower() not in {"1", "true", "yes"}:
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
