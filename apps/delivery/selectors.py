"""Read helpers for delivery."""
from .models import Notification


def notifications_for(user, unread_only=False):
    qs = Notification.objects.filter(user=user)
    return qs.filter(read_at__isnull=True) if unread_only else qs