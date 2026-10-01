"""Read/query helpers for accounts."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .validators import normalize_phone

User = get_user_model()


def normalize_identifier(identifier):
    """Return ("email", value) or ("phone", value). Raises ValidationError."""
    identifier = (identifier or "").strip()
    if "@" in identifier:
        return "email", identifier.lower()
    return "phone", normalize_phone(identifier)


def get_user_context(user):
    """Everything the frontend needs to decide where to send a user.

    Roles are derived, never stored on User:
      creator         -> has an AcademyMembership
      student         -> has an Enrollment
      platform admin  -> is_staff
    """
    # Imported here so accounts doesn't depend on other apps at import time
    from apps.academies.selectors import memberships_for_user
    from apps.enrollments.selectors import user_has_enrollments

    return {
        "user": user,
        "academies": [
            {"id": m.academy.id, "slug": m.academy.slug, "name": m.academy.name,
             "role": m.role}
            for m in memberships_for_user(user)
        ],
        "is_student": user_has_enrollments(user),
        "is_platform_admin": user.is_staff,
    }


def get_user_by_identifier(identifier):
    """Find a user by email or phone. Returns None if not found or invalid."""
    try:
        field, value = normalize_identifier(identifier)
    except ValidationError:
        return None
    return User.objects.filter(**{field: value}).first()