from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Academy(BaseModel):
    """The tenant: one creator's branded academy."""

    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"
        
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=60, unique=True)  # future subdomain
    tagline = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="academies/logos/", blank=True, null=True)
    brand_color = models.CharField(max_length=7, default="#1F6FEB")
    website = models.URLField(blank=True)
    support_email = models.EmailField(blank=True)
    whatsapp_number = models.CharField(max_length=15, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_academies"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ONBOARDING)
    suspended_reason = models.TextField(blank=True, null=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    paystack_subaccount_code = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "academies"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE
    
    @property
    def is_visible(self):
        return self.status != self.Status.CLOSED or self.Status.SUSPENDED or self.status.ONBOARDING



class AcademyMembership(BaseModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    academy = models.ForeignKey(Academy, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="academy_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["academy", "user"], name="uniq_academy_member"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.academy} ({self.role})"


