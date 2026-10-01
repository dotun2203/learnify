"""Studio course CRUD, publish rules, reordering and tenant isolation."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.academies.services import create_academy, update_academy
from apps.courses.models import Course
from apps.courses.services import add_lesson, add_module, create_course

pytestmark = pytest.mark.django_db

GIF = (b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00"
       b"\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")


def cover():
    return SimpleUploadedFile("c.gif", GIF, "image/gif")


@pytest.fixture
def academy(user):
    """An academy that has finished onboarding, so it can publish."""
    a = create_academy(owner=user, name="Grace", slug="grace")
    return update_academy(academy=a, tagline="Bible study", description="Weekly lessons",
                          support_email="hi@grace.ng", logo=cover())


@pytest.fixture
def studio(auth_client, academy):
    auth_client.credentials(HTTP_X_ACADEMY=academy.slug)
    return auth_client


@pytest.fixture
def course(academy, user):
    return create_course(academy=academy, created_by=user, title="Prayer 101",
                         description="A 7-day journey", cover=cover(), price_kobo=500000)


# ---------- create / update ----------

def test_create_course_slugifies_and_scopes(studio, academy):
    res = studio.post(reverse("course-list"),
                      {"title": "Prayer & Fasting 101", "price_kobo": 500000},
                      format="json")
    assert res.status_code == 201, res.data
    assert res.data["slug"] == "prayer-fasting-101"
    assert res.data["status"] == "draft"
    assert res.data["price_naira"] == 5000.0
    assert Course.objects.get(id=res.data["id"]).academy == academy


def test_duplicate_titles_get_distinct_slugs(studio):
    first = studio.post(reverse("course-list"), {"title": "Prayer"}, format="json")
    second = studio.post(reverse("course-list"), {"title": "Prayer"}, format="json")
    assert first.data["slug"] == "prayer"
    assert second.data["slug"] == "prayer-2"


def test_price_floor(studio):
    res = studio.post(reverse("course-list"), {"title": "Cheap", "price_kobo": 500},
                      format="json")
    assert res.status_code == 400
    assert "price_kobo" in res.data["error"]["details"]


def test_free_course_allowed(studio):
    res = studio.post(reverse("course-list"), {"title": "Free intro", "price_kobo": 0},
                      format="json")
    assert res.status_code == 201
    assert Course.objects.get(id=res.data["id"]).is_free


# ---------- tenant isolation ----------

def test_another_academy_cannot_see_or_touch_the_course(api_client, django_user_model,
                                                        course):
    intruder = django_user_model.objects.create_user(
        email="rival@example.com", phone="08055550000", password="Str0ng-pass!",
        is_email_verified=True)
    rival = create_academy(owner=intruder, name="Rival", slug="rival")
    api_client.force_authenticate(intruder)
    api_client.credentials(HTTP_X_ACADEMY=rival.slug)

    assert api_client.get(reverse("course-list")).data["results"] == []
    detail = reverse("course-detail", kwargs={"pk": course.id})
    assert api_client.get(detail).status_code == 404
    assert api_client.patch(detail, {"title": "Stolen"}, format="json").status_code == 404


def test_cannot_borrow_another_academys_header(api_client, django_user_model, academy):
    outsider = django_user_model.objects.create_user(
        email="nobody@example.com", phone="08066660000", password="Str0ng-pass!",
        is_email_verified=True)
    api_client.force_authenticate(outsider)
    api_client.credentials(HTTP_X_ACADEMY=academy.slug)
    assert api_client.get(reverse("course-list")).status_code == 403


def test_studio_requires_the_header(auth_client):
    assert auth_client.get(reverse("course-list")).status_code == 403


# ---------- structure + reorder ----------

def test_modules_and_lessons(studio, course):
    res = studio.post(reverse("course-modules", kwargs={"pk": course.id}),
                      {"title": "Week 1"}, format="json")
    assert res.status_code == 201
    module_id = res.data["id"]

    res = studio.post(reverse("module-lessons", kwargs={"pk": module_id}),
                      {"title": "Day 1", "body": "# Hello\n\nPray."}, format="json")
    assert res.status_code == 201
    assert res.data["position"] == 0

    res = studio.post(reverse("module-lessons", kwargs={"pk": module_id}),
                      {"title": "Day 2"}, format="json")
    assert res.data["position"] == 1


def test_reorder_moves_lessons_between_modules(studio, course):
    week1 = add_module(course=course, title="Week 1")
    week2 = add_module(course=course, title="Week 2")
    a = add_lesson(module=week1, title="A")
    b = add_lesson(module=week1, title="B")

    res = studio.post(reverse("course-reorder", kwargs={"pk": course.id}), {
        "modules": [
            {"id": str(week2.id), "lessons": [str(b.id)]},
            {"id": str(week1.id), "lessons": [str(a.id)]},
        ]}, format="json")
    assert res.status_code == 200, res.data
    assert [m["title"] for m in res.data["modules"]] == ["Week 2", "Week 1"]
    b.refresh_from_db()
    assert b.module_id == week2.id


def test_reorder_rejects_foreign_ids(studio, course, academy, user):
    other = create_course(academy=academy, created_by=user, title="Other")
    foreign = add_module(course=other, title="Not yours")
    res = studio.post(reverse("course-reorder", kwargs={"pk": course.id}),
                      {"modules": [{"id": str(foreign.id), "lessons": []}]}, format="json")
    assert res.status_code == 400
    assert res.data["error"]["code"] == "invalid_module"


# ---------- publishing ----------

def test_publish_blocked_until_ready(studio, academy, user):
    bare = create_course(academy=academy, created_by=user, title="Empty")
    res = studio.get(reverse("course-publish-check", kwargs={"pk": bare.id}))
    assert "Add a description." in res.data["blockers"]
    assert "Add at least one module." in res.data["blockers"]

    res = studio.post(reverse("course-publish", kwargs={"pk": bare.id}))
    assert res.status_code == 400
    assert res.data["error"]["code"] == "course_not_publishable"


def test_publish_and_unpublish(studio, course):
    module = add_module(course=course, title="Week 1")
    add_lesson(module=module, title="Day 1", body="Pray")
    assert studio.get(reverse("course-publish-check",
                              kwargs={"pk": course.id})).data["blockers"] == []

    res = studio.post(reverse("course-publish", kwargs={"pk": course.id}))
    assert res.status_code == 200, res.data
    assert res.data["status"] == "published"
    assert res.data["published_at"]

    res = studio.post(reverse("course-unpublish", kwargs={"pk": course.id}))
    assert res.data["status"] == "draft"


def test_academy_still_onboarding_cannot_publish(auth_client, user):
    raw = create_academy(owner=user, name="New", slug="new-academy")
    auth_client.credentials(HTTP_X_ACADEMY=raw.slug)
    c = create_course(academy=raw, created_by=user, title="Course", description="d",
                      cover=cover())
    module = add_module(course=c, title="M")
    add_lesson(module=module, title="L")
    res = auth_client.post(reverse("course-publish", kwargs={"pk": c.id}))
    assert res.status_code == 400
    blockers = res.data["error"]["details"]["blockers"]
    assert "Finish your academy onboarding first." in blockers


# ---------- public catalogue ----------

def test_public_pages_show_only_published_courses(api_client, academy, course):
    module = add_module(course=course, title="Week 1")
    add_lesson(module=module, title="Day 1", body="secret body")

    list_url = reverse("public-course-list", kwargs={"academy_slug": academy.slug})
    assert api_client.get(list_url).data["results"] == []

    from apps.courses.services import publish_course
    publish_course(course=course)

    res = api_client.get(list_url)
    assert [c["slug"] for c in res.data["results"]] == [course.slug]

    detail = api_client.get(reverse("public-course-detail", kwargs={
        "academy_slug": academy.slug, "course_slug": course.slug}))
    assert detail.status_code == 200
    lesson = detail.data["modules"][0]["lessons"][0]
    assert lesson["title"] == "Day 1"
    assert "body" not in lesson  # outline is public, content is not


def test_public_academy_hidden_until_active(api_client, user):
    create_academy(owner=user, name="New", slug="fresh")
    assert api_client.get(reverse("public-academy",
                                  kwargs={"slug": "fresh"})).status_code == 404
