"""Celery tasks for accounts."""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

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


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_otp(self, channel, target, code, purpose):
    # The raw code passes through the broker briefly; it is never logged or stored.
    minutes = settings.OTP_TTL_SECONDS // 60
    body = MESSAGES[purpose].format(code=code, minutes=minutes)

    if channel == "email":
        send_mail("Your Learnify code", body, settings.DEFAULT_FROM_EMAIL, [target])
    elif channel == "sms":
        if settings.DEBUG:
            logger.warning("[DEV SMS] to %s: %s", target, body)
        else:
            # TODO: plug in an SMS provider (e.g. Termii) via apps.delivery
            raise NotImplementedError("SMS provider not configured")
    else:
        raise ValueError(f"Unsupported channel {channel}")