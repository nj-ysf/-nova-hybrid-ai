"""Hermetic portable tests; set TEST_POSTGRES=true for the real database suite."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-for-deployment-7c15b18b")
os.environ.setdefault("DJANGO_DEBUG", "true")
from .settings import *  # noqa: E402,F403

if os.getenv("TEST_POSTGRES", "false").lower() != "true":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMBEDDING_BACKEND = "knowledge.embeddings.HashEmbeddings"
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
ALLOWED_HOSTS = ["testserver", "localhost"]
FRONTEND_URL = ""
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
JEV_ROUTER_KEY = ""
