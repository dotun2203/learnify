"""One User model; roles are derived from memberships, enrollments and is_staff."""
import pytest
from django.urls import reverse

from apps.academies.services import create_academy
from apps.accounts import services
from apps.core.testing import PASSWORD

pytestmark = pytest.mark.django_db


# ---------- the /me and login payload ----------

def test_new_user_has_no_roles(auth_client):
    data = auth_client.get(reverse("auth-me")).data
    assert data["academies"] == []
    assert data["is_student"] is False
    assert data["is_platform_admin"] is False
    assert data["user"]["has_password"] is True


def test_creating_an_academy_makes_you_a_creator(auth_client, user):
    create_academy(owner=user, name="Grace Bible School", slug="grace")
    data = auth_client.get(reverse("auth-me")).data
    assert data["academies"] == [
        {"id": str(user.owned_academies.get().id), "slug": "grace",
         "name": "Grace Bible School", "role": "owner"},
    ]


def test_login_response_includes_roles(api_client, user):
    create_academy(owner=user, name="Grace", slug="grace")
    res = api_client.post(reverse("auth-login"),
                          {"identifier": "creator@example.com", "password": PASSWORD},
                          format="json")
    assert res.status_code == 200
    assert set(res.data) == {"access", "refresh", "user", "academies", "is_student",
                             "is_platform_admin"}
    assert res.data["academies"][0]["role"] == "owner"


def test_staff_flag(api_client, django_user_model):
    admin = django_user_model.objects.create_superuser(email="boss@learnify.test",
                                                       password="Adm1n-pass!")
    api_client.force_authenticate(admin)
    assert api_client.get(reverse("auth-me")).data["is_platform_admin"] is True


# ---------- students created at checkout ----------

def test_get_or_create_learner_creates_otp_only_account():
    learner, created = services.get_or_create_learner(
        phone="0809 000 1111", first_name="Chiamaka", email="Chi@Example.com")
    assert created is True
    assert learner.phone == "+2348090001111"
    assert learner.email == "chi@example.com"
    assert learner.has_usable_password() is False


def test_get_or_create_learner_reuses_existing_account(user):
    learner, created = services.get_or_create_learner(
        phone="+2348031234567", first_name="Someone Else", email="other@example.com")
    assert created is False
    assert learner == user
    user.refresh_from_db()
    assert user.first_name == "Ada"                      # not overwritten
    assert user.email == "creator@example.com"           # not overwritten


def test_get_or_create_learner_ignores_email_owned_by_someone_else(user):
    learner, created = services.get_or_create_learner(
        phone="08070000000", first_name="Bola", email="creator@example.com")
    assert created is True
    assert learner.email is None


def test_existing_creator_buying_a_course_is_the_same_account(user):
    """A pastor who owns an academy and buys a course keeps one login."""
    create_academy(owner=user, name="Grace", slug="grace")
    learner, _ = services.get_or_create_learner(phone="08031234567", first_name="Ada")
    assert learner.pk == user.pk
    assert learner.academy_memberships.count() == 1


# ---------- OTP-only users can set a first password ----------

def test_otp_only_user_sets_password_without_current(api_client):
    learner, _ = services.get_or_create_learner(phone="08090001111", first_name="Chi")
    api_client.force_authenticate(learner)
    assert api_client.get(reverse("auth-me")).data["user"]["has_password"] is False

    res = api_client.post(reverse("auth-password-change"),
                          {"new_password": "First-pass-123"}, format="json")
    assert res.status_code == 204
    learner.refresh_from_db()
    assert learner.check_password("First-pass-123")


def test_user_with_password_must_give_current(auth_client):
    res = auth_client.post(reverse("auth-password-change"),
                           {"new_password": "An0ther-pass!"}, format="json")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "wrong_password"

def test_suspended_academy_hidden(auth_client, user):
    academy = create_academy(owner=user, name="Old", slug="old")
    academy.status = "suspended"
    academy.save()
    assert auth_client.get(reverse("auth-me")).data["academies"] == []