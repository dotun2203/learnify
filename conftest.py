import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.testing import PASSWORD


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(
        email="creator@example.com", phone="08031234567", password=PASSWORD,
        first_name="Ada", last_name="Obi", is_email_verified=True,
    )


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def sent_codes(monkeypatch):
    """Capture OTP codes instead of sending them. Returns a list of dicts."""
    captured = []

    def fake_delay(channel, target, code, purpose):
        captured.append({"channel": channel, "target": target, "code": code,
                         "purpose": purpose})

    monkeypatch.setattr("apps.accounts.tasks.send_otp.delay", fake_delay)
    return captured
