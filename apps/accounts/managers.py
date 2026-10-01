from django.contrib.auth.base_user import BaseUserManager

from .validators import normalize_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, phone, password, **extra):
        if not email and not phone:
            raise ValueError("An email or phone number is required")
        email = self.normalize_email(email).lower() if email else None
        phone = normalize_phone(phone) if phone else None
        user = self.model(email=email, phone=phone, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, phone=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, phone, password, **extra)

    def create_superuser(self, email, password=None, phone=None, **extra):
        if not email:
            raise ValueError("Superusers need an email address")
        extra.update(is_staff=True, is_superuser=True, is_email_verified=True)
        return self._create_user(email, phone, password, **extra)
