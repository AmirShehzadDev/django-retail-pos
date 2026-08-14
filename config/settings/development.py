from .base import *  # noqa: F403
from .environment import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Development and tests must not require collectstatic or a manifest.
MIDDLEWARE.remove("whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}
