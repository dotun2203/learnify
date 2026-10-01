from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    """For /platform/... endpoints used by the Learnify team."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)