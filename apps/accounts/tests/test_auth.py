import pytest
from django.urls import reverse

from apps.accounts.models import OTPCode
from apps.core.testing import PASSWORD

pytestmark = pytest.mark.django_db


def register(client, **overrides):
    payload = {"email": "New@Example.com", "phone": "0803 111 2222",
               "first_name": "Tolu", "last_name": "Ade", "password": PASSWORD, **overrides}
    return client.post(reverse("auth-register"), payload, format="json")


# ---------- 1. register ----------

def test_register_creates_account_but_does_not_log_in(api_client, sent_codes,
                                                      django_user_model,
                                                      django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        res = register(api_client)
    assert res.status_code == 201, res.data
    assert res.data["next"] == "verify_email"
    assert "access" not in res.data and "refresh" not in res.data

    user = django_user_model.objects.get(email="new@example.com")
    assert user.phone == "+2348031112222"
    assert user.is_email_verified is False
    assert sent_codes[0] == {"channel": "email", "target": "new@example.com",
                             "code": sent_codes[0]["code"], "purpose": "verify_email"}


def test_unverified_user_cannot_log_in(api_client, sent_codes,
                                       django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        register(api_client)
    res = api_client.post(reverse("auth-login"),
                          {"identifier": "new@example.com", "password": PASSWORD},
                          format="json")
    assert res.status_code == 403
    assert res.data["error"]["code"] == "email_not_verified"


def test_verifying_email_logs_the_user_in(api_client, sent_codes,
                                          django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        register(api_client)
    res = api_client.post(reverse("auth-otp-verify"),
                          {"identifier": "new@example.com", "purpose": "verify_email",
                           "code": sent_codes[-1]["code"]}, format="json")
    assert res.status_code == 200, res.data
    assert res.data["access"] and res.data["refresh"]
    assert res.data["user"]["is_email_verified"] is True

    # and now the password login works
    ok = api_client.post(reverse("auth-login"),
                         {"identifier": "new@example.com", "password": PASSWORD},
                         format="json")
    assert ok.status_code == 200


def test_signup_survives_a_broker_outage(api_client, monkeypatch, django_user_model,
                                         django_capture_on_commit_callbacks):
    """A dead Redis must not lose the account: the row is saved, the code is not sent."""
    def boom(*args, **kwargs):
        raise ConnectionError("redis is down")

    monkeypatch.setattr("apps.accounts.tasks.send_otp.delay", boom)
    with django_capture_on_commit_callbacks(execute=True):
        res = register(api_client)
    assert res.status_code == 201
    assert django_user_model.objects.filter(email="new@example.com").exists()


def test_register_rejects_duplicates(api_client, user):
    res = register(api_client, email="CREATOR@example.com", phone="+2348031234567")
    assert res.status_code == 400
    assert set(res.data["error"]["details"]) == {"email", "phone"}


def test_register_rejects_weak_password(api_client):
    res = register(api_client, password="12345")
    assert res.status_code == 400
    assert "password" in res.data["error"]["details"]


def test_error_shape(api_client):
    res = api_client.post(reverse("auth-register"), {"phone": "123"}, format="json")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "validation_error"
    assert "phone" in res.data["error"]["details"]


# ---------- 2. login ----------

@pytest.mark.parametrize("identifier", ["creator@example.com", "CREATOR@example.com",
                                        "08031234567", "+2348031234567"])
def test_login_with_email_or_phone(api_client, user, identifier):
    res = api_client.post(reverse("auth-login"),
                          {"identifier": identifier, "password": PASSWORD}, format="json")
    assert res.status_code == 200, res.data
    assert res.data["user"]["id"] == str(user.id)
    assert res.data["user"]["phone"] == "+2348031234567"


def test_login_wrong_password(api_client, user):
    res = api_client.post(reverse("auth-login"),
                          {"identifier": "creator@example.com", "password": "nope"},
                          format="json")
    assert res.status_code == 401
    assert res.data["error"]["code"] == "invalid_credentials"


def test_login_inactive_user(api_client, user):
    user.is_active = False
    user.save()
    res = api_client.post(reverse("auth-login"),
                          {"identifier": "creator@example.com", "password": PASSWORD},
                          format="json")
    assert res.status_code == 401


# ---------- 3 & 4. refresh + logout ----------

def login(api_client):
    return api_client.post(reverse("auth-login"),
                           {"identifier": "creator@example.com", "password": PASSWORD},
                           format="json").data


def test_refresh_rotates_and_logout_blacklists(api_client, user):
    tokens = login(api_client)
    res = api_client.post(reverse("auth-refresh"), {"refresh": tokens["refresh"]},
                          format="json")
    assert res.status_code == 200
    new_refresh = res.data["refresh"]

    # old refresh token was blacklisted on rotation
    again = api_client.post(reverse("auth-refresh"), {"refresh": tokens["refresh"]},
                            format="json")
    assert again.status_code == 401

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
    out = api_client.post(reverse("auth-logout"), {"refresh": new_refresh}, format="json")
    assert out.status_code == 204
    after = api_client.post(reverse("auth-refresh"), {"refresh": new_refresh}, format="json")
    assert after.status_code == 401


# ---------- 5. me ----------

def test_me_requires_auth(api_client):
    res = api_client.get(reverse("auth-me"))
    assert res.status_code == 401
    assert res.data["error"]["code"] == "not_authenticated"


def test_me_get_and_patch(auth_client):
    assert auth_client.get(reverse("auth-me")).data["user"]["first_name"] == "Ada"
    res = auth_client.patch(reverse("auth-me"),
                            {"first_name": "Adaeze", "email": "hacker@x.com"}, format="json")
    assert res.status_code == 200
    assert res.data["user"]["first_name"] == "Adaeze"
    assert res.data["user"]["email"] == "creator@example.com"  # not editable here


# ---------- 6 & 7. OTP request + verify ----------

def request_code(client, identifier, purpose):
    return client.post(reverse("auth-otp-request"),
                       {"identifier": identifier, "purpose": purpose}, format="json")


def test_verify_phone_flow(api_client, user, sent_codes, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        res = request_code(api_client, "08031234567", "verify_phone")
    assert res.status_code == 202
    code = sent_codes[-1]["code"]
    assert sent_codes[-1]["channel"] == "sms"

    res = api_client.post(reverse("auth-otp-verify"),
                          {"identifier": "08031234567", "purpose": "verify_phone",
                           "code": code}, format="json")
    assert res.status_code == 200, res.data
    assert res.data["user"]["is_phone_verified"] is True

    # a code can only be used once
    res = api_client.post(reverse("auth-otp-verify"),
                          {"identifier": "08031234567", "purpose": "verify_phone",
                           "code": code}, format="json")
    assert res.status_code == 400


def test_otp_request_unknown_account_looks_identical(api_client, sent_codes, db):
    res = request_code(api_client, "ghost@example.com", "login")
    assert res.status_code == 202
    assert sent_codes == []


def test_otp_cooldown(api_client, user, sent_codes):
    assert request_code(api_client, "08031234567", "login").status_code == 202
    res = request_code(api_client, "08031234567", "login")
    assert res.status_code == 429
    assert res.data["error"]["code"] == "otp_cooldown"


def test_otp_stored_hashed_and_locks_after_max_attempts(api_client, user, sent_codes,
                                                        django_capture_on_commit_callbacks,
                                                        settings):
    with django_capture_on_commit_callbacks(execute=True):
        request_code(api_client, "08031234567", "verify_phone")
    code = sent_codes[-1]["code"]
    record = OTPCode.objects.get(user=user)
    assert code not in record.code_hash

    wrong = "000000" if code != "000000" else "111111"
    body = {"identifier": "08031234567", "purpose": "verify_phone", "code": wrong}
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        assert api_client.post(reverse("auth-otp-verify"), body, format="json").status_code == 400
    record.refresh_from_db()
    assert record.attempts == settings.OTP_MAX_ATTEMPTS

    body["code"] = code  # even the right code is now refused
    res = api_client.post(reverse("auth-otp-verify"), body, format="json")
    assert res.status_code == 429
    assert res.data["error"]["code"] == "otp_locked"


def test_expired_code_rejected(api_client, user, sent_codes,
                               django_capture_on_commit_callbacks):
    from django.utils import timezone
    with django_capture_on_commit_callbacks(execute=True):
        request_code(api_client, "08031234567", "verify_phone")
    OTPCode.objects.update(expires_at=timezone.now())
    res = api_client.post(reverse("auth-otp-verify"),
                          {"identifier": "08031234567", "purpose": "verify_phone",
                           "code": sent_codes[-1]["code"]}, format="json")
    assert res.status_code == 400


# ---------- 8. OTP login ----------

def test_otp_login_by_email(api_client, user, sent_codes, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        request_code(api_client, "creator@example.com", "login")
    assert sent_codes[-1]["channel"] == "email"
    res = api_client.post(reverse("auth-otp-login"),
                          {"identifier": "creator@example.com",
                           "code": sent_codes[-1]["code"]}, format="json")
    assert res.status_code == 200, res.data
    assert res.data["access"]
    assert res.data["user"]["is_email_verified"] is True


# ---------- 9. change password ----------

def test_change_password(api_client, user):
    tokens = login(api_client)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    bad = api_client.post(reverse("auth-password-change"),
                          {"current_password": "wrong", "new_password": "An0ther-pass!"},
                          format="json")
    assert bad.status_code == 400
    assert bad.data["error"]["code"] == "wrong_password"

    ok = api_client.post(reverse("auth-password-change"),
                         {"current_password": PASSWORD, "new_password": "An0ther-pass!"},
                         format="json")
    assert ok.status_code == 204
    user.refresh_from_db()
    assert user.check_password("An0ther-pass!")
    #