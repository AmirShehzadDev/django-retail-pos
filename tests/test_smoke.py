import os
import subprocess
import sys

from django.conf import settings
from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.db import DatabaseError
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class FoundationSmokeTests(SimpleTestCase):
    def test_notifications_are_fixed_dismissible_toasts_with_safe_timeouts(self):
        rendered = render_to_string(
            "partials/messages.html",
            {
                "messages": [
                    Message(constants.SUCCESS, "Saved successfully."),
                    Message(constants.ERROR, "Could not save."),
                ]
            },
        )

        self.assertIn("fixed right-4 top-4", rendered)
        self.assertEqual(rendered.count("data-toast>"), 1)
        self.assertEqual(rendered.count("data-toast "), 1)
        self.assertEqual(rendered.count("data-toast-dismiss"), 2)
        self.assertIn('data-toast-timeout="5000"', rendered)
        self.assertNotIn('role="alert" data-toast data-toast-timeout', rendered)

    def test_foundation_settings(self):
        database = settings.DATABASES["default"]

        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertEqual(settings.TIME_ZONE, "Asia/Karachi")
        self.assertTrue(settings.USE_TZ)
        self.assertEqual(settings.POS_CURRENCY, "PKR")

    def test_login_page_uses_only_local_assets(self):
        response = self.client.get(reverse("accounts:login"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in to Retail POS")
        self.assertIn("/static/css/app.css", content)
        self.assertIn("/static/js/app.js", content)
        self.assertNotIn("https://", content)
        self.assertNotIn("http://", content)

    def test_production_settings_reject_missing_configuration(self):
        environment = os.environ.copy()
        for key in (
            "DJANGO_SECRET_KEY",
            "DJANGO_ALLOWED_HOSTS",
            "POS_DB_NAME",
            "POS_DB_USER",
            "POS_DB_PASSWORD",
        ):
            environment.pop(key, None)
        environment["POS_ENV_FILE"] = ""
        environment["DJANGO_SETTINGS_MODULE"] = "config.settings.production"

        result = subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            cwd=settings.BASE_DIR,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_production_settings_reject_example_secret(self):
        environment = os.environ.copy()
        environment["POS_ENV_FILE"] = ""
        environment["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
        environment["DJANGO_SECRET_KEY"] = "replace-with-a-long-random-value"
        environment["DJANGO_ALLOWED_HOSTS"] = "127.0.0.1"
        environment["POS_DB_NAME"] = "pos_codex"
        environment["POS_DB_USER"] = "pos_app"
        environment["POS_DB_PASSWORD"] = "not-used-during-settings-check"

        result = subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            cwd=settings.BASE_DIR,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("development DJANGO_SECRET_KEY", result.stderr)


class HealthTests(TestCase):
    def test_health_endpoint_checks_database_and_reports_version(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "version": settings.POS_APP_VERSION},
        )
        self.assertEqual(
            response["Cache-Control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

    def test_health_endpoint_returns_503_when_database_is_unavailable(self):
        from unittest.mock import patch

        with patch("apps.core.views.connection.cursor", side_effect=DatabaseError):
            response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_health_endpoint_rejects_post(self):
        self.assertEqual(self.client.post(reverse("core:health")).status_code, 405)
