import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = os.getenv("POS_ENV_FILE", str(BASE_DIR / ".env"))

if ENV_FILE:
    load_dotenv(ENV_FILE, override=False)


def env(name, default=None, *, required=False):
    value = os.getenv(name, default)
    if required and (value is None or str(value).strip() == ""):
        raise ImproperlyConfigured(f"Required environment variable {name} is not set.")
    return value


def env_bool(name, default=False):
    value = str(env(name, str(default))).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean value.")


def env_list(name, default=""):
    value = env(name, default)
    return [item.strip() for item in str(value).split(",") if item.strip()]


def env_path(name, default):
    value = Path(env(name, default))
    return value if value.is_absolute() else BASE_DIR / value
