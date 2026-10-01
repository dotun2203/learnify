import re

from django.core.exceptions import ValidationError

RESERVED_SLUGS = {
    "www", "api", "admin", "app", "studio", "learn", "public", "platform",
    "docs", "help", "support", "mail", "email", "blog", "static", "media",
    "assets", "cdn", "dashboard", "login", "signup", "auth", "learnify",
}

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")

def validate_academy_slug(value):
    value = (value or "").strip().lower()
    if not SLUG_RE.match(value):
        raise ValidationError(
            "Use 3-40 characters: lowercase letters, numbers and hyphens, "
            "starting and ending with a letter or number."
        )
    if "--" in value:
        raise ValidationError("Hyphens cannot be repeated.")
    if value in RESERVED_SLUGS:
        raise ValidationError("This name is reserved. Please choose another.")
    return value


