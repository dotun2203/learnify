from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from .models import Academy, AcademyMembership

ACADEMY_HEADER = "HTTP_X_ACADEMY"


def resolve_academy(request):
    """Resolve the active academy from the X-Academy header (id or slug)."""
    if hasattr(request, "_academy"):
        return request._academy
    ref = request.META.get(ACADEMY_HEADER)
    if not ref:
        raise PermissionDenied("X-Academy header is required.")
    lookup = {"slug": ref}
    if len(ref) == 36 and ref.count("-") == 4:
        lookup = {"id": ref}
    try:
        academy = Academy.objects.exclude(status=Academy.Status.SUSPENDED).get(**lookup)
    except Academy.DoesNotExist as exc:
        raise NotFound("Academy not found.") from exc
    request._academy = academy
    return academy


class IsAcademyMember(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        academy = resolve_academy(request)
        request.membership = AcademyMembership.objects.filter(
            academy=academy, user=request.user
        ).first()
        return request.membership is not None

class IsAcademyOwnerObject(BasePermission):
    """Object-level check for /academies/{slug}/ routes (no X-Academy header)."""

    def has_object_permission(self, request, view, obj):
        return obj.memberships.filter(
            user=request.user, role=AcademyMembership.Role.OWNER
        ).exists()


class IsAcademyOwner(IsAcademyMember):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.membership.role == AcademyMembership.Role.OWNER
        )
