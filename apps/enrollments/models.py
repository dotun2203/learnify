from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, TenantScopedModel


class Enrollment(TenantScopedModel):
    """One student's access to one course."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Source(models.TextChoices):
        FREE = "free", "Free course"
        PAID = "paid", "Paid"
        MANUAL = "manual", "Added by creator"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="enrollments")
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE,
                               related_name="enrollments")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.FREE)
    # Snapshot: the student's clock when they enrolled, so release times don't
    # shift if they later change their profile timezone.
    timezone = models.CharField(max_length=50, default="Africa/Lagos")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["course", "student"],
                                    name="uniq_enrollment_per_course"),
        ]

    def __str__(self):
        return f"{self.student} -> {self.course}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class LessonRelease(BaseModel):
    """The drip schedule: one row per lesson per enrollment.

    A database table, not scheduled Celery tasks: it can be queried, edited
    when a creator changes the schedule, and survives a broker restart.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE,
                                   related_name="releases")
    lesson = models.ForeignKey("courses.Lesson", on_delete=models.CASCADE,
                               related_name="releases")
    position = models.PositiveIntegerField(default=0, help_text="Order within the course")
    release_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "release_at"]
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "lesson"],
                                    name="uniq_release_per_lesson"),
        ]
        indexes = [models.Index(fields=["status", "release_at"])]

    def __str__(self):
        return f"{self.lesson} @ {self.release_at:%Y-%m-%d %H:%M}"

    @property
    def is_due(self):
        from django.utils import timezone as dj_tz
        return self.release_at <= dj_tz.now()


class LessonProgress(BaseModel):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE,
                                   related_name="progress")
    lesson = models.ForeignKey("courses.Lesson", on_delete=models.CASCADE,
                               related_name="progress")
    opened_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "lesson"],
                                    name="uniq_progress_per_lesson"),
        ]

    def __str__(self):
        return f"{self.lesson} ({'done' if self.completed_at else 'open'})"

    @property
    def is_complete(self):
        return self.completed_at is not None