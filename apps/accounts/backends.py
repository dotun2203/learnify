from django.contrib.auth.backends import ModelBackend

from .selectors import get_user_by_identifier


class EmailOrPhoneBackend(ModelBackend):
    """Authenticate with email OR phone + password (admin and API)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get("email") or kwargs.get("phone")
        if not identifier or not password:
            return None
        user = get_user_by_identifier(identifier)
        if user is None:
            # Run the hasher anyway so response time doesn't reveal unknown accounts
            self.user_model().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None