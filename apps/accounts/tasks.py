"""Celery tasks for accounts."""
import logging

from celery import shared_task
from django.conf import settings

from apps.core.emails import send_templated_email

logger = logging.getLogger(__name__)

MESSAGES = {
    "verify_phone": "Your Learnify verification code is {code}. It expires in {minutes} minutes.",
    "verify_email": "Your Learnify email verification code is {code}. "
                    "It expires in {minutes} minutes.",
    "login": "Your Learnify login code is {code}. It expires in {minutes} minutes. "
             "Never share it.",
    "reset_password": "Your Learnify password reset code is {code}. "
                      "It expires in {minutes} minutes.",
}

# Copy for templates/emails/otp_code.*, one entry per purpose
EMAIL_COPY = {
    "verify_email": {
        "subject": "Verify your Learnify email",
        "heading": "Verify your email",
        "intro": "Welcome to Learnify! Enter this code to confirm your email address.",
        "warning": "Never share this code with anyone.",
    },
    "verify_phone": {
        "subject": "Verify your Learnify phone number",
        "heading": "Verify your phone number",
        "intro": "Enter this code to confirm your phone number.",
        "warning": "Never share this code with anyone.",
    },
    "login": {
        "subject": "Your Learnify login code",
        "heading": "Your login code",
        "intro": "Use this code to log in to your Learnify account.",
        "warning": "Never share this code. Learnify staff will never ask you for it.",
    },
    "reset_password": {
        "subject": "Reset your Learnify password",
        "heading": "Reset your password",
        "intro": "We received a request to reset your password. "
                 "Enter this code to choose a new one.",
        "warning": "Never share this code. Learnify staff will never ask you for it.",
    },
}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_otp(self, channel, target, code, purpose):
    # The raw code passes through the broker briefly; it is never logged or stored.
    minutes = settings.OTP_TTL_SECONDS // 60

    if channel == "email":
        copy = EMAIL_COPY[purpose]
        send_templated_email(
            to=target, subject=copy["subject"], template="otp_code",
            context={**copy, "code": code, "minutes": minutes},
        )
    elif channel == "sms":
        body = MESSAGES[purpose].format(code=code, minutes=minutes)
        if settings.DEBUG:
            logger.warning("[DEV SMS] to %s: %s", target, body)
        else:
            # TODO: plug in an SMS provider (e.g. Termii) via apps.delivery
            raise NotImplementedError("SMS provider not configured")
    else:
        raise ValueError(f"Unsupported channel {channel}")