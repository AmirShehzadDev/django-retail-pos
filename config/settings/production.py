from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .environment import env_bool, env_path

DEBUG = False

UNSAFE_SECRET_KEYS = {
    "pos-codex-local-development-key-change-before-deployment",
    "replace-with-a-long-random-value",
}

if SECRET_KEY in UNSAFE_SECRET_KEYS:  # noqa: F405
    raise ImproperlyConfigured("The development DJANGO_SECRET_KEY cannot be used in production.")

if len(SECRET_KEY) < 32:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be at least 32 characters in production.")

SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)

LOG_DIR = env_path("APP_LOG_DIR", "var/log")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING["handlers"]["file"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": LOG_DIR / "pos.log",
    "formatter": "standard",
    "maxBytes": 5 * 1024 * 1024,
    "backupCount": 5,
}
LOGGING["root"]["handlers"] = ["console", "file"]  # noqa: F405
