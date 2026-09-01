"""Hermetic settings for the Phase 0 characterization test suite."""

import os

os.environ.setdefault('OPENAI_API_KEY', 'test-key-not-used')

from .settings import *  # noqa: E402,F403


SECRET_KEY = 'test-only-secret-key'
DEBUG = False
INSTALLED_APPS = [
    app for app in INSTALLED_APPS  # noqa: F405
    if app != 'django_extensions'
]
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
