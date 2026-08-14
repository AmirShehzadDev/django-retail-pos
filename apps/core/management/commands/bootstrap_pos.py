import os
from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import DocumentSequence, Shop, Terminal


class Command(BaseCommand):
    help = "Create the initial shop, terminal, and owner account."

    def add_arguments(self, parser):
        parser.add_argument("--shop-name", default=settings.POS_SHOP_NAME)
        parser.add_argument("--terminal-code", default=settings.POS_TERMINAL_CODE)
        parser.add_argument("--terminal-name", default=settings.POS_TERMINAL_NAME)
        parser.add_argument("--owner-username")
        parser.add_argument(
            "--owner-password-env",
            help="Read the initial owner password from this environment variable.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        shop_name = options["shop_name"].strip()
        terminal_code = options["terminal_code"].strip().upper()
        terminal_name = options["terminal_name"].strip()
        owner_username = options["owner_username"]

        if not shop_name or not terminal_code or not terminal_name:
            raise CommandError("Shop and terminal names/codes cannot be empty.")

        owner_username = (owner_username or input("Owner username: ")).strip()
        if not owner_username:
            raise CommandError("Owner username cannot be empty.")

        shop, shop_created = self._get_shop(shop_name)
        sequences_created = []
        for document_type in DocumentSequence.DocumentType.values:
            _sequence, created = DocumentSequence.objects.get_or_create(
                shop=shop,
                document_type=document_type,
                defaults={"next_number": 1},
            )
            if created:
                sequences_created.append(document_type.lower())
        terminal, terminal_created = self._get_terminal(shop, terminal_code, terminal_name)
        owner, owner_created = self._get_owner(
            shop,
            owner_username,
            password_env=options["owner_password_env"],
        )

        actions = []
        if shop_created:
            actions.append(f"created shop {shop.name}")
        if terminal_created:
            actions.append(f"created terminal {terminal.code}")
        if sequences_created:
            actions.append(f"created {'/'.join(sequences_created)} sequence(s)")
        if owner_created:
            actions.append(f"created owner {owner.username}")

        if actions:
            message = "POS bootstrap complete: " + ", ".join(actions) + "."
            self.stdout.write(self.style.SUCCESS(message))
        else:
            self.stdout.write(
                self.style.SUCCESS("POS bootstrap already complete; no changes made.")
            )

    def _get_shop(self, shop_name):
        shops = list(Shop.objects.select_for_update().all())
        if len(shops) > 1:
            raise CommandError(
                "Bootstrap requires a single shop, but multiple shops already exist."
            )

        if shops:
            shop = shops[0]
            expected = (shop_name, Shop.Currency.PKR, Shop.Timezone.ASIA_KARACHI, True)
            actual = (shop.name, shop.currency, shop.timezone, shop.is_active)
            if actual != expected:
                raise CommandError(
                    "Existing shop conflicts with the requested bootstrap configuration."
                )
            return shop, False

        return (
            Shop.objects.create(
                name=shop_name,
                currency=Shop.Currency.PKR,
                timezone=Shop.Timezone.ASIA_KARACHI,
            ),
            True,
        )

    def _get_terminal(self, shop, terminal_code, terminal_name):
        terminals = list(Terminal.objects.select_for_update().filter(shop=shop))
        matching = [terminal for terminal in terminals if terminal.code == terminal_code]

        if matching:
            terminal = matching[0]
            if len(terminals) != 1 or terminal.name != terminal_name or not terminal.is_active:
                raise CommandError(
                    "Existing terminal conflicts with the requested bootstrap configuration."
                )
            return terminal, False

        if terminals:
            raise CommandError(
                "A different terminal already exists; bootstrap will not create an ambiguous setup."
            )

        return Terminal.objects.create(shop=shop, code=terminal_code, name=terminal_name), True

    def _get_owner(self, shop, owner_username, *, password_env=None):
        user_model = get_user_model()
        owners = list(user_model.objects.select_for_update().filter(role=user_model.Role.OWNER))
        matching_user = (
            user_model.objects.select_for_update().filter(username=owner_username).first()
        )

        if matching_user:
            expected = (
                shop.pk,
                user_model.Role.OWNER,
                True,
                True,
                True,
            )
            actual = (
                matching_user.shop_id,
                matching_user.role,
                matching_user.is_active,
                matching_user.is_staff,
                matching_user.is_superuser,
            )
            if actual != expected or any(owner.pk != matching_user.pk for owner in owners):
                raise CommandError(
                    "Existing user conflicts with the requested owner bootstrap configuration."
                )
            return matching_user, False

        if owners:
            raise CommandError(
                "A different owner already exists; bootstrap will not create another."
            )

        if password_env:
            password = os.getenv(password_env)
            if not password:
                raise CommandError(
                    f"Owner password environment variable {password_env} is not set."
                )
            confirmation = password
        else:
            password = getpass("Owner password: ")
            confirmation = getpass("Confirm owner password: ")
        if password != confirmation:
            raise CommandError("Owner passwords do not match.")

        owner = user_model(
            username=owner_username,
            shop=shop,
            role=user_model.Role.OWNER,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        try:
            validate_password(password, user=owner)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        owner.set_password(password)
        owner.full_clean(exclude=["created_by"])
        owner.save()
        return owner, True
