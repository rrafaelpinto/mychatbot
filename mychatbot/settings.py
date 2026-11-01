"""Django settings for ResumeBot.

Development is the default environment. Production settings fail closed when required
secrets or hosts are absent and enable HTTPS protections without breaking local HTTP.
"""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [
        item.strip()
        for item in os.environ.get(name, default).split(",")
        if item.strip()
    ]


ENVIRONMENT = os.environ.get("RESUMEBOT_ENV", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production")
    SECRET_KEY = "django-insecure-resumebot-development-only"

DEBUG = env_bool("DJANGO_DEBUG", default=not IS_PRODUCTION)
if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false in production")

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1" if not IS_PRODUCTION else "",
)
if IS_PRODUCTION and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required in production")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env_list("API_CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (*default_headers, "idempotency-key")
CORS_URLS_REGEX = r"^/(api/|chat/)"
if any("*" in origin for origin in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured("CORS origins must be explicit, never wildcard.")
if IS_PRODUCTION and any(
    not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS
):
    raise ImproperlyConfigured("Production CORS origins must use HTTPS.")
if IS_PRODUCTION and any(
    origin not in CSRF_TRUSTED_ORIGINS for origin in CORS_ALLOWED_ORIGINS
):
    raise ImproperlyConfigured(
        "Allowed frontend origins must also be in DJANGO_CSRF_TRUSTED_ORIGINS."
    )

JWT_REFRESH_COOKIE_NAME = "resumebot_refresh"
JWT_REFRESH_COOKIE_PATH = "/api/v1/auth/"
JWT_REFRESH_COOKIE_SECURE = IS_PRODUCTION
JWT_REFRESH_COOKIE_SAMESITE = os.environ.get("JWT_REFRESH_COOKIE_SAMESITE", "Lax")
if JWT_REFRESH_COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
    raise ImproperlyConfigured("Invalid JWT refresh SameSite policy.")
if JWT_REFRESH_COOKIE_SAMESITE == "None" and not IS_PRODUCTION:
    raise ImproperlyConfigured("SameSite=None requires a secure production cookie.")
CSRF_COOKIE_SAMESITE = JWT_REFRESH_COOKIE_SAMESITE
if IS_PRODUCTION and JWT_REFRESH_COOKIE_SAMESITE == "None":
    CSRF_COOKIE_SECURE = True

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": os.environ.get("JWT_SIGNING_KEY") or SECRET_KEY,
    "UPDATE_LAST_LOGIN": False,
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "django_registration",
    "crispy_forms",
    "crispy_bootstrap4",
    "chatbot.apps.ChatbotConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if IS_PRODUCTION:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": "5/min",
        "auth_refresh": "20/min",
        "auth_csrf": "60/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ResumeBot API",
    "DESCRIPTION": "Versioned candidate profile API with explicit privacy boundaries.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

ROOT_URLCONF = "mychatbot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "chatbot.context_processors.release_flags",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mychatbot.wsgi.application"
ASGI_APPLICATION = "mychatbot.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "resumebot"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "0")),
    }
}
if os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.parse(
        os.environ["DATABASE_URL"],
        conn_max_age=int(os.environ.get("POSTGRES_CONN_MAX_AGE", "0")),
        conn_health_checks=True,
    )

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        )
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

CANDIDATE_UPLOADS_ENABLED = env_bool(
    "CANDIDATE_UPLOADS_ENABLED", default=not IS_PRODUCTION
)

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "deploy" / "static"
STATICFILES_DIRS = [BASE_DIR / "mychatbot" / "static"]
if IS_PRODUCTION:
    STORAGES = {
        "default": {
            "BACKEND": (
                "django.core.files.storage.FileSystemStorage"
                if CANDIDATE_UPLOADS_ENABLED
                else "chatbot.storage.DisabledPublicUploadStorage"
            ),
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    WHITENOISE_KEEP_ONLY_HASHED_FILES = True

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("PUBLIC_MEDIA_ROOT") or BASE_DIR / "deploy" / "media")
PUBLIC_REGISTRATION_ENABLED = env_bool(
    "PUBLIC_REGISTRATION_ENABLED", default=not IS_PRODUCTION
)
PASSWORD_RESET_ENABLED = env_bool("PASSWORD_RESET_ENABLED", default=not IS_PRODUCTION)
if (
    IS_PRODUCTION
    and CANDIDATE_UPLOADS_ENABLED
    and (
        not os.environ.get("PRIVATE_MEDIA_ROOT")
        or not os.environ.get("PUBLIC_MEDIA_ROOT")
        or (
            Path(os.environ["PRIVATE_MEDIA_ROOT"]).resolve()
            == Path(os.environ["PUBLIC_MEDIA_ROOT"]).resolve()
        )
    )
):
    raise ImproperlyConfigured(
        "Production uploads require distinct persistent public/private media roots."
    )
PRIVATE_MEDIA_ROOT = Path(
    os.environ.get("PRIVATE_MEDIA_ROOT") or BASE_DIR / "private_media"
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

ACCOUNT_ACTIVATION_DAYS = 3
LOGIN_REDIRECT_URL = "about"
LOGOUT_REDIRECT_URL = "about"

default_email_backend = (
    "django.core.mail.backends.smtp.EmailBackend"
    if IS_PRODUCTION
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", default_email_backend)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@localhost")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT_SECONDS = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30"))

AI_DAILY_BUDGET_USD = os.environ.get(
    "AI_DAILY_BUDGET_USD", "0" if IS_PRODUCTION else "10"
)
AI_MONTHLY_BUDGET_USD = os.environ.get(
    "AI_MONTHLY_BUDGET_USD", "0" if IS_PRODUCTION else "100"
)
AI_INPUT_USD_PER_MILLION = os.environ.get("AI_INPUT_USD_PER_MILLION", "0.15")
AI_OUTPUT_USD_PER_MILLION = os.environ.get("AI_OUTPUT_USD_PER_MILLION", "0.60")
AI_MAX_INPUT_TOKENS = int(os.environ.get("AI_MAX_INPUT_TOKENS", "8192"))
AI_MAX_OUTPUT_TOKENS = int(os.environ.get("AI_MAX_OUTPUT_TOKENS", "500"))
AI_EMBEDDING_MODEL = "text-embedding-3-small"
AI_EMBEDDING_DIMENSIONS = 256
AI_EMBEDDING_MAX_INPUT_BYTES = 2048
AI_EMBEDDING_MAX_INPUT_TOKENS = 2048
AI_EMBEDDING_INPUT_USD_PER_MILLION = os.environ.get(
    "AI_EMBEDDING_INPUT_USD_PER_MILLION", "0.02"
)
AI_SEMANTIC_INDEX_ENABLED = env_bool("AI_SEMANTIC_INDEX_ENABLED", default=False)
AI_SEMANTIC_QUERY_ENABLED = env_bool("AI_SEMANTIC_QUERY_ENABLED", default=False)
AI_CHAT_CONTEXT_QUESTIONS = 4
AI_CHAT_CONTEXT_QUESTION_CHARS = 500
AI_CHAT_INPUT_OVERHEAD_BYTES = 1600

AI_EXTRACTION_MAX_SOURCE_BYTES = 6000
AI_EXTRACTION_MAX_FACTS = 5
AI_KNOWLEDGE_EXTRACTION_ENABLED = env_bool(
    "AI_KNOWLEDGE_EXTRACTION_ENABLED", default=False
)

GUEST_CHAT_ENABLED = env_bool("GUEST_CHAT_ENABLED", default=False)
GUEST_TURNSTILE_SITE_KEY = os.environ.get("GUEST_TURNSTILE_SITE_KEY", "")
GUEST_TURNSTILE_SECRET_KEY = os.environ.get("GUEST_TURNSTILE_SECRET_KEY", "")
GUEST_TURNSTILE_TIMEOUT = float(os.environ.get("GUEST_TURNSTILE_TIMEOUT", "3"))
GUEST_IP_HASH_SECRET = os.environ.get("GUEST_IP_HASH_SECRET", "")
GUEST_TRUSTED_PROXY_IPS = env_list("GUEST_TRUSTED_PROXY_IPS")
GUEST_SESSION_HOURS = 24
GUEST_SESSION_QUESTION_LIMIT = 10
GUEST_SESSIONS_PER_ORIGIN_PER_DAY = 4
GUEST_ORIGIN_PER_MINUTE = 2
GUEST_ORIGIN_PER_DAY = 20
GUEST_GLOBAL_PER_DAY = 50
GUEST_CONVERSATION_RETENTION_DAYS = 7

GUEST_CLEANUP_SCHEDULED = env_bool("GUEST_CLEANUP_SCHEDULED", default=False)
if IS_PRODUCTION and GUEST_CHAT_ENABLED and not GUEST_CLEANUP_SCHEDULED:
    raise ImproperlyConfigured(
        "Guest chat requires an active guest session cleanup schedule."
    )

if GUEST_CHAT_ENABLED and (
    not GUEST_TURNSTILE_SITE_KEY
    or not GUEST_TURNSTILE_SECRET_KEY
    or not GUEST_IP_HASH_SECRET
):
    raise ImproperlyConfigured(
        "Guest chat requires Turnstile site/secret keys and an IP hash secret."
    )

AI_ENABLED = env_bool("AI_ENABLED", default=not IS_PRODUCTION)
AI_EVALUATION_PAID_ENABLED = env_bool("AI_EVALUATION_PAID_ENABLED", default=False)
AI_USAGE_LIMITS = {
    "candidate_chat": {
        "identity_per_minute": int(os.environ.get("AI_CHAT_IDENTITY_PER_MINUTE", "5")),
        "identity_per_day": int(os.environ.get("AI_CHAT_IDENTITY_PER_DAY", "100")),
        "candidate_per_day": int(os.environ.get("AI_CHAT_CANDIDATE_PER_DAY", "500")),
    },
    "knowledge_extraction": {
        "identity_per_minute": 1,
        "identity_per_day": 5,
        "candidate_per_day": 5,
    },
    "embedding_index": {
        "identity_per_minute": 30,
        "identity_per_day": 200,
        "candidate_per_day": 200,
    },
    "embedding_query": {
        "identity_per_minute": 5,
        "identity_per_day": 30,
        "candidate_per_day": 60,
    },
}

AI_OPERATION_POLICIES = {
    "candidate_chat": env_bool("AI_CANDIDATE_CHAT_ENABLED", default=True),
    "knowledge_extraction": AI_KNOWLEDGE_EXTRACTION_ENABLED,
    "embedding_index": AI_SEMANTIC_INDEX_ENABLED,
    "embedding_query": AI_SEMANTIC_QUERY_ENABLED,
}

if IS_PRODUCTION:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
    )
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
    if env_bool("DJANGO_TRUST_X_FORWARDED_PROTO", default=False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
