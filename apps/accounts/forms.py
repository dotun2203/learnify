from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError

from .models import User
from .validators import normalize_phone


class PhoneCleanMixin:
    """Normalise phone to E.164 and store blanks as NULL."""

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if not phone:
            return None
        try:
            return normalize_phone(phone)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc

    def clean_email(self):
        email = self.cleaned_data.get("email")
        return email.lower() if email else None


class UserCreationAdminForm(PhoneCleanMixin, AdminUserCreationForm):
    class Meta:
        model = User
        # is_staff is included so the "non-staff users need a phone" rule
        # is validated as a form error instead of a database crash.
        fields = ("email", "phone", "is_staff")


class UserChangeAdminForm(PhoneCleanMixin, UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
