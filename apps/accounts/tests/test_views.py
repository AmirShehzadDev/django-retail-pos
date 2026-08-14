from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Shop


class AccountManagementViewTests(TestCase):
    password = "StrongPass!2026"

    def setUp(self):
        self.shop = Shop.objects.create(name="Test Shop")
        self.owner = self.make_user("owner", User.Role.OWNER)
        self.admin = self.make_user("admin", User.Role.ADMIN, creator=self.owner)
        self.cashier = self.make_user("cashier", User.Role.CASHIER, creator=self.admin)
        self.inactive_cashier = self.make_user(
            "oldcashier", User.Role.CASHIER, creator=self.owner, active=False
        )
        other_shop = Shop.objects.create(name="Other Shop")
        self.other_owner = User.objects.create_user(
            username="otherowner",
            password=self.password,
            shop=other_shop,
            role=User.Role.OWNER,
        )

    def make_user(self, username, role, *, creator=None, active=True):
        return User.objects.create_user(
            username=username,
            password=self.password,
            shop=self.shop,
            role=role,
            created_by=creator,
            is_active=active,
        )

    def test_anonymous_user_list_redirects_to_login(self):
        response = self.client.get(reverse("accounts:user_list"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:user_list')}",
        )

    def test_cashier_cannot_access_user_management(self):
        self.client.force_login(self.cashier)

        self.assertEqual(self.client.get(reverse("accounts:user_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:user_create")).status_code, 403)

    def test_owner_list_includes_all_same_shop_roles_only(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("accounts:user_list"))

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(
            response.context["users"],
            [self.admin, self.cashier, self.inactive_cashier, self.owner],
            ordered=False,
        )
        self.assertNotContains(response, self.other_owner.username)

    def test_admin_list_and_filters_never_expand_beyond_cashiers(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("accounts:user_list"),
            {"role": User.Role.ADMIN, "status": "inactive", "q": "cashier"},
        )

        self.assertQuerySetEqual(response.context["users"], [self.inactive_cashier])
        self.assertEqual(response.context["selected_role"], "")

    def test_cross_shop_and_admin_targeting_admin_return_not_found(self):
        self.client.force_login(self.owner)
        cross_shop = self.client.get(reverse("accounts:user_detail", args=[self.other_owner.pk]))
        self.client.force_login(self.admin)
        hidden_admin = self.client.get(reverse("accounts:user_detail", args=[self.admin.pk]))

        self.assertEqual(cross_shop.status_code, 404)
        self.assertEqual(hidden_admin.status_code, 404)

    def test_owner_account_detail_is_read_only(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("accounts:user_detail", args=[self.owner.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_edit"])
        self.assertFalse(response.context["can_reset_password"])
        self.assertFalse(response.context["can_change_active_state"])

    def test_admin_create_ignores_crafted_role_and_protected_fields(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "newcashier",
                "first_name": "New",
                "last_name": "Cashier",
                "role": User.Role.ADMIN,
                "password1": "AnotherStrongPass!2026",
                "password2": "AnotherStrongPass!2026",
                "shop": self.other_owner.shop_id,
                "is_superuser": "on",
                "is_staff": "on",
            },
        )

        created = User.objects.get(username="newcashier")
        self.assertRedirects(response, reverse("accounts:user_detail", args=[created.pk]))
        self.assertEqual(created.role, User.Role.CASHIER)
        self.assertEqual(created.shop, self.shop)
        self.assertEqual(created.created_by, self.admin)
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)

    def test_admin_edit_ignores_crafted_role_and_security_fields(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("accounts:user_edit", args=[self.cashier.pk]),
            {
                "username": "renamedcashier",
                "first_name": "Renamed",
                "last_name": "Cashier",
                "role": User.Role.ADMIN,
                "shop": self.other_owner.shop_id,
                "is_superuser": "on",
            },
        )

        self.assertRedirects(response, reverse("accounts:user_detail", args=[self.cashier.pk]))
        self.cashier.refresh_from_db()
        self.assertEqual(self.cashier.username, "renamedcashier")
        self.assertEqual(self.cashier.role, User.Role.CASHIER)
        self.assertEqual(self.cashier.shop, self.shop)
        self.assertFalse(self.cashier.is_superuser)

    def test_status_mutations_are_post_only_and_admin_cannot_target_admin(self):
        self.client.force_login(self.admin)

        get_response = self.client.get(reverse("accounts:user_deactivate", args=[self.cashier.pk]))
        hidden_response = self.client.post(
            reverse("accounts:user_deactivate", args=[self.admin.pk])
        )
        post_response = self.client.post(
            reverse("accounts:user_deactivate", args=[self.cashier.pk])
        )

        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(hidden_response.status_code, 404)
        self.assertRedirects(post_response, reverse("accounts:user_detail", args=[self.cashier.pk]))
        self.cashier.refresh_from_db()
        self.assertFalse(self.cashier.is_active)
