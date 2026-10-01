from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import DomainError

from .models import Academy, AcademyMembership
from .selectors import onboarding_checklist
from .validators import validate_academy_slug


@transaction.atomic
def create_academy(*, owner, name, slug, **fields):
    slug = validate_academy_slug(slug)
    if Academy.objects.filter(slug=slug).exists():
        raise DomainError("That academy address is already taken.", code="slug_taken")
    academy = Academy.objects.create(owner=owner, name=name, slug=slug, **fields)
    AcademyMembership.objects.create(
        academy=academy, user=owner, role=AcademyMembership.Role.OWNER
    )
    return academy


@transaction.atomic
def update_academy(*, academy, **fields):
    """Updates profile/branding, then re-checks whether onboarding is complete."""
    for field, value in fields.items():
        setattr(academy, field, value)
    academy.save()
    refresh_status(academy)
    return academy


def refresh_status(academy):
    """Onboarding -> active as soon as the blocking steps are done.

    Suspended academies are left alone: only an admin lifts a suspension.
    """
    if academy.status == Academy.Status.SUSPENDED:
        return academy
    complete = onboarding_checklist(academy)["complete"]
    new_status = Academy.Status.ACTIVE if complete else Academy.Status.ONBOARDING
    if new_status != academy.status:
        academy.status = new_status
        academy.activated_at = timezone.now() if complete else None
        academy.save(update_fields=["status", "activated_at", "updated_at"])
    return academy


def suspend_academy(*, academy, reason=""):
    academy.status = Academy.Status.SUSPENDED
    academy.suspended_reason = reason
    academy.save(update_fields=["status", "suspended_reason", "updated_at"])
    return academy