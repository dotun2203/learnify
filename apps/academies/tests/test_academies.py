import pytest
from django.urls import reverse

from apps.academies.models import Academy, AcademyMembership
from apps.academies.services import create_academy, update_academy

pytestmark = pytest.mark.django_db


def test_create_academy_makes_owner_membership(auth_client, user):
    res = auth_client.post(reverse("academy-list"),
                           {"name": "Grace Bible School", "slug": "grace"}, format="json")
    assert res.status_code == 201, res.data
    assert res.data["role"] == "owner"
    assert res.data["status"] == "onboarding"
    assert AcademyMembership.objects.filter(user=user, role="owner").count() == 1


def test_user_only_sees_own_academies(auth_client, user, django_user_model):
    other = django_user_model.objects.create_user(phone="08099990000", password="x")
    create_academy(owner=user, name="Mine", slug="mine")
    create_academy(owner=other, name="Theirs", slug="theirs")
    res = auth_client.get(reverse("academy-list"))
    assert [a["slug"] for a in res.data["results"]] == ["mine"]


@pytest.mark.parametrize("slug,ok", [
    ("grace", True), ("grace-bible-2", True),
    ("ab", False), ("www", False), ("admin", False),
    ("Grace", True),  # normalised to "grace"
    ("grace--x", False), ("-grace", False),
])
def test_slug_rules(auth_client, slug, ok):
    res = auth_client.get(reverse("academy-slug-available"), {"slug": slug})
    assert res.data["available"] is ok
    if ok:
        assert res.data["slug"] == slug.lower()  # the wizard shows the cleaned slug


def test_slug_taken(auth_client, user):
    create_academy(owner=user, name="Mine", slug="mine")
    assert auth_client.get(reverse("academy-slug-available"),
                           {"slug": "mine"}).data["available"] is False


def test_onboarding_checklist_then_auto_activate(auth_client, user, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile
    academy = create_academy(owner=user, name="Grace", slug="grace")

    res = auth_client.get(reverse("academy-onboarding", kwargs={"slug": "grace"}))
    assert res.data["status"] == "onboarding"
    assert res.data["complete"] is False
    assert {s["key"] for s in res.data["steps"]} == {"profile", "branding", "contact", "payouts"}

    update_academy(academy=academy, tagline="Bible study for busy people",
                   description="Weekly lessons", support_email="hi@grace.ng")
    academy.refresh_from_db()
    assert academy.status == "onboarding"  # still needs a logo

    gif = (b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00"
           b"\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    update_academy(academy=academy, logo=SimpleUploadedFile("l.gif", gif, "image/gif"))
    academy.refresh_from_db()
    assert academy.status == Academy.Status.ACTIVE
    assert academy.activated_at is not None


def test_suspended_academy_disappears(auth_client, user):
    from apps.academies.services import suspend_academy
    academy = create_academy(owner=user, name="Old", slug="old")
    suspend_academy(academy=academy, reason="spam")
    assert auth_client.get(reverse("academy-list")).data["results"] == []
    assert auth_client.get(reverse("auth-me")).data["academies"] == []