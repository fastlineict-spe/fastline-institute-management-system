import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Securely bootstrap the central administrator on hosted PostgreSQL."

    def handle(self, *args, **options):
        if connections["default"].vendor != "postgresql":
            raise CommandError("Refusing to modify a non-PostgreSQL database.")

        username = os.environ.get("FIMS_BOOTSTRAP_ADMIN_USERNAME", "").strip()
        password = os.environ.get("FIMS_BOOTSTRAP_ADMIN_PASSWORD", "")

        if not username or not password:
            raise CommandError("Bootstrap username or password environment variable is missing.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"role": "ADMINISTRATOR"},
        )

        user.role = "ADMINISTRATOR"
        user.is_central_admin = True
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.campus = None
        user.set_password(password)
        user.save()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(
            f"Central administrator account '{username}' successfully {action}."
        ))
