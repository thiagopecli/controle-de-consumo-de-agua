from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import os


class Command(BaseCommand):
    help = "Create a superuser from env vars if it does not exist."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  Skipping superuser creation: missing DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD."
                )
            )
            return

        user_model = get_user_model()
        if user_model.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Superuser '{username}' already exists. Skipping."
                )
            )
            return

        user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Superuser '{username}' created successfully!"
            )
        )
