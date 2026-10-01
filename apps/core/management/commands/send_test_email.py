"""Check outgoing email end to end: `python manage.py send_test_email you@example.com`"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.tasks import EMAIL_COPY
from apps.core.emails import send_templated_email


class Command(BaseCommand):
    help = "Send a sample OTP email synchronously, bypassing Celery, to check SMTP settings."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Address to send the test email to")
        parser.add_argument("--purpose", choices=sorted(EMAIL_COPY), default="verify_email")

    def handle(self, *args, to, purpose, **options):
        self.stdout.write(
            f"Backend: {settings.EMAIL_BACKEND}\n"
            f"Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT} "
            f"(TLS={settings.EMAIL_USE_TLS}, SSL={settings.EMAIL_USE_SSL})\n"
            f"From: {settings.DEFAULT_FROM_EMAIL}"
        )
        copy = EMAIL_COPY[purpose]
        try:
            send_templated_email(
                to=to, subject=f"[Test] {copy['subject']}", template="otp_code",
                context={**copy, "code": "123456", "minutes": settings.OTP_TTL_SECONDS // 60},
            )
        except Exception as exc:  # noqa: BLE001 - show the SMTP error to the operator
            raise CommandError(f"Sending failed: {exc!r}") from exc
        self.stdout.write(self.style.SUCCESS(f"Sent test email to {to}"))
