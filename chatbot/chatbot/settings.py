"""Deployment settings. Provider credentials are loaded only from the environment."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in the environment or root .env.")
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("replace-", "django-insecure-"))):
    raise ImproperlyConfigured(
        "Production requires a newly generated DJANGO_SECRET_KEY of at least 50 characters."
    )
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = list(filter(None, os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")))
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "projects",
    "providers",
    "knowledge",
    "usage",
    "audit",
    "chat",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "chatbot.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "chatbot.wsgi.application"
ASGI_APPLICATION = "chatbot.asgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "chatbot"),
        "USER": os.getenv("POSTGRES_USER", "chatbot"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
if os.getenv("CHATBOT_SQLITE", "false").lower() == "true":
    if not DEBUG:
        raise ImproperlyConfigured("SQLite is permitted only with DJANGO_DEBUG=true.")
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{name}"}
    for name in (
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    )
]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "chat.errors.exception_handler",
}
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = FRONTEND_URL or "/"
LOGOUT_REDIRECT_URL = f"{FRONTEND_URL}/login/" if FRONTEND_URL else "/login/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true" and not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 300_000
# Trusted deployment-only endpoints. Project admins select aliases, never URLs or keys.
LLM_CONNECTIONS = {
    "local": {
        "mode": "local",
        "backend": "ollama",
        "url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "key": "",
    },
    "external": {
        "mode": "external",
        "backend": "gemini",
        # Google AI Studio keys use the Gemini Developer API, not Vertex AI.
        "key": os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", "")),
    },
}
EMBEDDING_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_DIMENSIONS = 768
EMBEDDING_BACKEND = "knowledge.embeddings.OllamaEmbeddings"
PROVIDER_TIMEOUT = 60
# Jev is used only for mode=auto and receives the sanitized current message.
JEV_ROUTER_URL = os.getenv("JEV_ROUTER_URL", "https://openrouter.ai/api/alpha/decisions")
JEV_ROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
JEV_ROUTER_MODEL = os.getenv("JEV_ROUTER_MODEL", "typesafe/jev-1.13")
JEV_ROUTER_TIMEOUT = float(os.getenv("JEV_ROUTER_TIMEOUT", "8"))
JEV_ROUTER_MIN_CONFIDENCE = float(os.getenv("JEV_ROUTER_MIN_CONFIDENCE", "0.7"))
ALLOW_SQLITE_RETRIEVAL = DEBUG
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {name: {"handlers": ["null"], "propagate": False} for name in ("httpx", "httpcore")},
}
