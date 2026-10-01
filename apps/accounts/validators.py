import phonenumbers
from django.core.exceptions import ValidationError


def normalize_phone(value, default_region="NG"):
    """Return E.164 (+2348012345678) or raise ValidationError."""
    try:
        parsed = phonenumbers.parse(str(value), default_region)
    except phonenumbers.NumberParseException as exc:
        raise ValidationError("Enter a valid phone number.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError("Enter a valid phone number.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
