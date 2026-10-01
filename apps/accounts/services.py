"""Write operations for accounts. Views call these; these never touch `request`."""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions import DomainError

from . import otp, tasks
from .models import OTPCode
from .selectors import get_user_by_identifier, normalize_identifier

logger = logging.getLogger(__name__)

User = get_user_model()


# ---------- tokens ----------

def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    User.objects.filter(pk=user.pk).update(last_login=timezone.now())
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def logout(refresh_token):
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError as exc:
        raise DomainError("Invalid or expired refresh token.", code="invalid_token") from exc


# ---------- registration ----------

@transaction.atomic
def register_user(*, phone, email, first_name, last_name, password):
    """Public sign-up. Always has a password; phone gets verified by OTP."""
    user = User.objects.create_user(
        email=email, phone=phone, password=password,
        first_name=first_name, last_name=last_name,
    )
    request_otp(user=user, purpose=OTPCode.Purpose.VERIFY_EMAIL)
    return user


@transaction.atomic
def _enqueue_send(channel, target, code, purpose):
    """Hand the code to Celery. A broker outage must not break the request:
    the row is already saved, so the user can just ask for another code."""
    try:
        tasks.send_otp.delay(channel, target, code, purpose)
    except Exception:  # noqa: BLE001 - broker unreachable
        logger.exception("Could not queue %s OTP to %s", purpose, channel)


@transaction.atomic
def get_or_create_learner(*, phone, first_name="", last_name="", email=None):
    """Find or create a student by phone. Called by checkout (and WhatsApp later).

    - Phone is the identity: an existing account is reused, never duplicated.
    - Existing names/emails are never overwritten by what a buyer typed.
    - An email already owned by *another* account is ignored, not attached.
    - New learners get no password; they log in with an OTP.
    Returns (user, created).
    """
    from .validators import normalize_phone

    phone = normalize_phone(phone)
    email = email.strip().lower() if email else None

    user = User.objects.select_for_update().filter(phone=phone).first()
    if user:
        changed = []
        if not user.first_name and first_name:
            user.first_name, user.last_name = first_name, last_name
            changed += ["first_name", "last_name"]
        if not user.email and email and not User.objects.filter(email=email).exists():
            user.email = email
            changed.append("email")
        if changed:
            user.save(update_fields=changed)
        return user, False

    if email and User.objects.filter(email=email).exists():
        email = None
    user = User.objects.create_user(
        phone=phone, email=email, password=None,
        first_name=first_name, last_name=last_name,
    )
    return user, True


# ---------- OTP ----------

PURPOSE_CHANNEL = {
    OTPCode.Purpose.VERIFY_PHONE: OTPCode.Channel.SMS,
    OTPCode.Purpose.VERIFY_EMAIL: OTPCode.Channel.EMAIL,
}


def _pick_channel(user, purpose, identifier_field=None):
    if purpose in PURPOSE_CHANNEL:
        return PURPOSE_CHANNEL[purpose]
    # login / reset: send to whatever the user typed, else prefer phone
    if identifier_field == "email" or (identifier_field is None and not user.phone):
        return OTPCode.Channel.EMAIL
    return OTPCode.Channel.SMS


def request_otp(*, user, purpose, identifier_field=None):
    channel = _pick_channel(user, purpose, identifier_field)
    target = user.email if channel == OTPCode.Channel.EMAIL else user.phone
    if not target:
        raise DomainError(f"This account has no {channel} on file.", code="no_target")

    last = OTPCode.objects.filter(user=user, purpose=purpose).first()
    cooldown = timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
    if last and last.created_at > timezone.now() - cooldown:
        raise DomainError("Please wait before requesting another code.",
                          code="otp_cooldown", status_code=status.HTTP_429_TOO_MANY_REQUESTS)

    # A new code invalidates any older unused ones
    OTPCode.objects.filter(user=user, purpose=purpose, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )
    code = otp.generate_code()
    record = OTPCode.objects.create(
        user=user, purpose=purpose, channel=channel, target=target,
        code_hash=otp.hash_code(code),
        expires_at=timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    transaction.on_commit(lambda: _enqueue_send(channel, target, code, purpose))
    return record


def _enqueue_send(channel, target, code, purpose):
    """Hand the code to Celery. A broker outage must not break the request:
    the row is already saved, so the user can just ask for another code."""
    try:
        tasks.send_otp.delay(channel, target, code, purpose)
    except Exception:  # noqa: BLE001 - broker unreachable
        logger.exception("Could not queue %s OTP to %s", purpose, channel)


def request_otp_for_identifier(*, identifier, purpose):
    """Public entry point. Silently does nothing for unknown accounts
    (so the endpoint can't be used to discover who is registered)."""
    user = get_user_by_identifier(identifier)
    if user is None or not user.is_active:
        return None
    field, _ = normalize_identifier(identifier)
    return request_otp(user=user, purpose=purpose, identifier_field=field)


INVALID_CODE = "Invalid or expired code."


def consume_otp(*, identifier, purpose, code):
    """Check a code and mark it used. Returns (user, record) or raises DomainError.

    The failed-attempt counter must be saved even when we reject the code,
    so the error is raised *after* the transaction block has committed.
    """
    user = get_user_by_identifier(identifier)
    if user is None:
        raise DomainError(INVALID_CODE, code="invalid_otp")

    error = None
    with transaction.atomic():
        record = (
            OTPCode.objects.select_for_update()
            .filter(user=user, purpose=purpose, consumed_at__isnull=True)
            .first()
        )
        if record is None or not record.is_usable:
            error = DomainError(INVALID_CODE, code="invalid_otp")
        elif record.attempts >= settings.OTP_MAX_ATTEMPTS:
            error = DomainError("Too many attempts. Request a new code.", code="otp_locked",
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        elif not otp.codes_match(code, record.code_hash):
            record.attempts += 1
            record.save(update_fields=["attempts"])
            error = DomainError(INVALID_CODE, code="invalid_otp")
        else:
            record.consumed_at = timezone.now()
            record.save(update_fields=["consumed_at"])

    if error:
        raise error
    return user, record


def verify_contact(*, identifier, purpose, code):
    user, record = consume_otp(identifier=identifier, purpose=purpose, code=code)
    if purpose == OTPCode.Purpose.VERIFY_PHONE:
        user.is_phone_verified = True
        user.save(update_fields=["is_phone_verified"])
    elif purpose == OTPCode.Purpose.VERIFY_EMAIL:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
    return user


def login_with_otp(*, identifier, code):
    user, record = consume_otp(identifier=identifier, purpose=OTPCode.Purpose.LOGIN, code=code)
    if not user.is_active:
        raise DomainError(INVALID_CODE, code="invalid_otp")
    # Receiving the code proves ownership of that channel
    field = "is_email_verified" if record.channel == OTPCode.Channel.EMAIL else "is_phone_verified"
    if not getattr(user, field):
        setattr(user, field, True)
        user.save(update_fields=[field])
    return user


# ---------- passwords ----------

def change_password(*, user, new_password, current_password=""):
    """Change a password, or set the first one for OTP-only accounts."""
    if user.has_usable_password() and not user.check_password(current_password or ""):
        raise DomainError("Current password is incorrect.", code="wrong_password")
    _set_password(user, new_password)


def reset_password(*, identifier, code, new_password):
    user, _ = consume_otp(
        identifier=identifier, purpose=OTPCode.Purpose.RESET_PASSWORD, code=code
    )
    _set_password(user, new_password)
    return user


def _set_password(user, new_password):
    try:
        validate_password(new_password, user)
    except ValidationError as exc:
        raise DomainError({"new_password": exc.messages}, code="invalid_password") from exc
    user.set_password(new_password)
    user.save(update_fields=["password"])
    _revoke_all_refresh_tokens(user)


def _revoke_all_refresh_tokens(user):
    """Log the user out everywhere after a password change."""
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)