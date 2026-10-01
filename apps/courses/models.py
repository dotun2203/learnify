
# Create your models here.
from django.conf import settings
from django.db import models
from datetime import time

from apps.core.models import BaseModel, TenantScopedModel


class Course(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class ScheduleType(models.TextChoices):
        IMMEDIATE = "immediate", "All lessons at once"
        DAILY = "daily", "One lesson a day"
        WEEKLY = "weekly", "One lesson a week"
        CUSTOM = "custom", "Every N days"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80)
    subtitle = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    cover = models.ImageField(upload_to="courses/covers/", blank=True, null=True)

    # Money is stored as an integer in kobo: 5000 NGN -> 500000. Never floats.
    price_kobo = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="NGN")

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    # Drip settings — the enrollment engine reads these to build a release plan
    schedule_type = models.CharField(max_length=12, choices=ScheduleType.choices,
                                     default=ScheduleType.DAILY)
    drip_interval_days = models.PositiveSmallIntegerField(default=1)
    delivery_time = models.TimeField(default="08:00")
    timezone = models.CharField(max_length=50, default="Africa/Lagos")
    require_sequential = models.BooleanField(
        default=False,
        help_text="Also require the previous lesson to be completed before unlocking",
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name="created_courses")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["academy", "slug"],
                                    name="uniq_course_slug_per_academy"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_free(self):
        return self.price_kobo == 0

    @property
    def price_naira(self):
        return self.price_kobo / 100


class Module(BaseModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.title


class Lesson(BaseModel):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    # Markdown: renders on the web and converts cleanly to WhatsApp text later.
    body = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    estimated_minutes = models.PositiveSmallIntegerField(default=5)
    is_preview = models.BooleanField(default=False, help_text="Visible before buying")

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.title

    @property
    def course_id(self):
        return self.module.course_id


class Asset(BaseModel):
    class Kind(models.TextChoices):
        DOCUMENT = "document", "Document"
        IMAGE = "image", "Image"
        AUDIO = "audio", "Audio"
        VIDEO = "video", "Video"

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="assets")
    file = models.FileField(upload_to="courses/assets/%Y/%m/")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.DOCUMENT)
    original_name = models.CharField(max_length=255, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.original_name or str(self.file)