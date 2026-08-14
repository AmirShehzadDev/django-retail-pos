from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Shop


class AuthenticationViewTests(TestCase):
    password = "StrongPass!2026"

    def setUp(self):
        self.shop = Shop.objects.create(name="Test Shop")
        self.owner = User.objects.create_user(
            username="StoreOwner",
            password=self.password,
            shop=self.shop,
            role=User.Role.OWNER,
        )

    def test_login_canonicalizes_trimmed_username_case_insensitively(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "  storeowner  ", "password": self.password},
        )

        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.owner.pk)

    def test_invalid_and_inactive_credentials_use_same_generic_error(self):
        invalid = self.client.post(
            reverse("accounts:login"),
            {"username": "missing", "password": "wrong"},
        )
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        inactive = self.client.post(
            reverse("accounts:login"),
            {"username": self.owner.username, "password": self.password},
        )

        invalid_errors = invalid.context["form"].non_field_errors()
        inactive_errors = inactive.context["form"].non_field_errors()
        self.assertEqual(invalid_errors, inactive_errors)
        self.assertContains(invalid, "Invalid username or password.")

    def test_login_rotates_existing_session_key(self):
        session = self.client.session
        session["anonymous-state"] = True
        session.save()
        previous_key = session.session_key

        self.client.post(
            reverse("accounts:login"),
            {"username": self.owner.username, "password": self.password},
        )

        self.assertNotEqual(self.client.session.session_key, previous_key)

    def test_safe_next_is_honored_and_external_next_is_rejected(self):
        safe_response = self.client.post(
            f"{reverse('accounts:login')}?next={reverse('accounts:password_change')}",
            {"username": self.owner.username, "password": self.password},
        )
        self.assertRedirects(safe_response, reverse("accounts:password_change"))

        self.client.post(reverse("accounts:logout"))
        external_response = self.client.post(
            f"{reverse('accounts:login')}?next=https://example.com/steal",
            {"username": self.owner.username, "password": self.password},
        )
        self.assertRedirects(external_response, reverse("core:home"))

    def test_authenticated_login_request_redirects_home(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("accounts:login"))

        self.assertRedirects(response, reverse("core:home"))

    def test_logout_is_post_only_and_flushes_session(self):
        self.client.force_login(self.owner)

        get_response = self.client.get(reverse("accounts:logout"))
        post_response = self.client.post(reverse("accounts:logout"))

        self.assertEqual(get_response.status_code, 405)
        self.assertRedirects(post_response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)

        response = csrf_client.post(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 403)

    def test_sessions_expire_when_the_browser_closes(self):
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)

    def test_deactivated_user_loses_existing_session_on_next_request(self):
        self.client.force_login(self.owner)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('core:home')}",
        )

    def test_own_password_change_preserves_current_session_only(self):
        other_client = Client()
        self.client.force_login(self.owner)
        other_client.force_login(self.owner)

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": self.password,
                "new_password1": "A-New-Strong-Pass!2026",
                "new_password2": "A-New-Strong-Pass!2026",
            },
        )

        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)
        self.assertRedirects(
            other_client.get(reverse("core:home")),
            f"{reverse('accounts:login')}?next={reverse('core:home')}",
        )

    def test_manager_password_reset_invalidates_target_session(self):
        cashier = User.objects.create_user(
            username="cashier",
            password=self.password,
            shop=self.shop,
            role=User.Role.CASHIER,
            created_by=self.owner,
        )
        cashier_client = Client()
        cashier_client.force_login(cashier)
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("accounts:user_password_reset", args=[cashier.pk]),
            {
                "password1": "Reset-Strong-Pass!2026",
                "password2": "Reset-Strong-Pass!2026",
            },
        )

        self.assertRedirects(response, reverse("accounts:user_detail", args=[cashier.pk]))
        self.assertRedirects(
            cashier_client.get(reverse("core:home")),
            f"{reverse('accounts:login')}?next={reverse('core:home')}",
        )

    def test_protected_and_login_responses_are_not_cached(self):
        login_response = self.client.get(reverse("accounts:login"))
        self.client.force_login(self.owner)
        home_response = self.client.get(reverse("core:home"))

        self.assertIn("no-store", login_response.headers["Cache-Control"])
        self.assertIn("no-store", home_response.headers["Cache-Control"])


class ProductionAdminBoundaryTests(SimpleTestCase):
    def test_admin_route_is_not_mounted_when_debug_is_false(self):
        from importlib import reload

        from django.urls import clear_url_caches

        import config.urls

        with self.settings(DEBUG=False):
            reload(config.urls)
            clear_url_caches()
            response = self.client.get("/admin/")

        reload(config.urls)
        clear_url_caches()
        self.assertEqual(response.status_code, 404)
