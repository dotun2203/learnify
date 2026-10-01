import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone as dj_timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Phone number (E.164) is the identity — it will be the WhatsApp identity later.

    Email is optional (students) but required for creators at the service layer.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)

    is_phone_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    preferred_language = models.CharField(max_length=10, default="en")
    timezone = models.CharField(max_length=50, default="Africa/Lagos")
    whatsapp_opt_in = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=dj_timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]
        constraints = [
            models.CheckConstraint(
                condition=Q(phone__isnull=False) | Q(is_staff=True),
                name="non_staff_users_need_phone",
            ),
            models.CheckConstraint(
                condition=Q(phone__isnull=False) | Q(email__isnull=False),
                name="user_has_email_or_phone",
            ),
        ]

    def __str__(self):
        return self.get_full_name() or self.email or self.phone or str(self.id)

    def save(self, *args, **kwargs):
        self.phone = self.phone or None
        self.email = self.email.lower() if self.email else None
        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name or self.email or self.phone

class OTPCode(models.Model):
    """
    One time code sent to a phone or email. store only code hash, not code
    """

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify email"
        VERIFY_PHONE = "verify_phone", "Verify phone"
        RESET_PASSWORD = "reset_password", "Reset password"
        LOGIN = "login", "Passwordless login"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"

    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_codes")
    code_hash = models.CharField(max_length=128)
    channel = models.CharField(max_length=30, choices=Channel.choices)
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    target = models.CharField(max_length=254)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "purpose", "target", "created_at"])]

    def __str__(self):
        return f"{self.purpose} ({self.channel}) -> {self.target}"
    
    @property
    def is_usable(self):
        return self.consumed_at is None and self.expires_at > dj_timezone.now()
        


