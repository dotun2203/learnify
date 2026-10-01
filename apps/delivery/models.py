
# Create your models here.
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Notification(BaseModel):
    """In-app message shown in the portal's bell menu.

    This is the web channel. Email and WhatsApp become extra channels later,
    fed by the same delivery.services.notify() call.
    """

    class Kind(models.TextChoices):
        LESSON_RELEASED = "lesson_released", "Lesson released"
        ENROLLED = "enrolled", "Enrolled"
        COURSE_COMPLETED = "course_completed", "Course completed"
        GENERAL = "general", "General"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="notifications")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.GENERAL)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True, help_text="Frontend path to open")
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.kind} -> {self.user}"