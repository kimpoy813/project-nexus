"""Create or update a superuser/admin account non-interactively.

Render's free web-service tier has no shell access, so `createsuperuser`
can't be run interactively after deploy. This command is meant to be added
to the build step instead. It is idempotent and driven entirely by
environment variables, so it is safe to run on every deploy:

- If none of the DJANGO_SUPERUSER_* variables are set, it does nothing.
- If the named user doesn't exist yet, it creates it as a superuser/staff
  account and gives it the Profile ADMIN role used by this app's dashboard
  routing.
- If the user already exists, by default it leaves it alone. Pass
  --update-existing (or set DJANGO_SUPERUSER_UPDATE_EXISTING=True) to also
  reset its password/flags/role on subsequent deploys.

Required env vars to actually create an account:
    DJANGO_SUPERUSER_USERNAME
    DJANGO_SUPERUSER_EMAIL
    DJANGO_SUPERUSER_PASSWORD

Optional:
    DJANGO_SUPERUSER_UPDATE_EXISTING=True
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "Create or update an admin account from DJANGO_SUPERUSER_* environment variables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-existing",
            action="store_true",
            default=None,
            help="If the user already exists, reset its password/flags/role too.",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not (username and email and password):
            self.stdout.write(
                "DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD not fully set; skipping admin bootstrap."
            )
            return

        update_existing = options.get("update_existing")
        if update_existing is None:
            update_existing = _env_bool("DJANGO_SUPERUSER_UPDATE_EXISTING", False)

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )

            if not created and not update_existing:
                self.stdout.write(
                    f"User {username!r} already exists; leaving it unchanged "
                    "(pass --update-existing to reset it)."
                )
                return

            user.email = email
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()

            Profile.objects.update_or_create(
                user=user,
                defaults={
                    "full_name": user.get_full_name() or username,
                    "role": Profile.ROLE_ADMIN,
                    "email_verified": True,
                },
            )

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} admin account {username!r}."))
