"""Write operations (business logic) for this app live here."""
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core.exceptions import DomainError

from .models import Asset, Course, Lesson, Module
from .selectors import publish_blockers


def _unique_slug(academy, title, instance=None):
    base = slugify(title)[:70] or "course"
    slug, n = base, 2
    qs = Course.objects.filter(academy=academy)
    if instance:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


@transaction.atomic
def create_course(*, academy, created_by, title, **fields):
    return Course.objects.create(
        academy=academy, created_by=created_by, title=title,
        slug=_unique_slug(academy, title), **fields,
    )


@transaction.atomic
def update_course(*, course, **fields):
    if "title" in fields and course.status == Course.Status.DRAFT:
        # Published slugs are frozen: public links and certificates point at them.
        course.slug = _unique_slug(course.academy, fields["title"], instance=course)
    for field, value in fields.items():
        setattr(course, field, value)
    course.save()
    return course


@transaction.atomic
def publish_course(*, course):
    problems = publish_blockers(course)
    if problems:
        raise DomainError({"blockers": problems}, code="course_not_publishable")
    course.status = Course.Status.PUBLISHED
    course.published_at = course.published_at or timezone.now()
    course.save(update_fields=["status", "published_at", "updated_at"])
    return course


@transaction.atomic
def unpublish_course(*, course):
    """Back to draft. Existing students keep their access; it just leaves the catalogue."""
    course.status = Course.Status.DRAFT
    course.save(update_fields=["status", "updated_at"])
    return course


@transaction.atomic
def archive_course(*, course):
    course.status = Course.Status.ARCHIVED
    course.save(update_fields=["status", "updated_at"])
    return course


# ---------- structure ----------

def _next_position(queryset):
    last = queryset.order_by("-position").first()
    return (last.position + 1) if last else 0


@transaction.atomic
def add_module(*, course, title, summary=""):
    return Module.objects.create(
        course=course, title=title, summary=summary,
        position=_next_position(course.modules),
    )


@transaction.atomic
def add_lesson(*, module, title, body="", estimated_minutes=5, is_preview=False):
    return Lesson.objects.create(
        module=module, title=title, body=body, estimated_minutes=estimated_minutes,
        is_preview=is_preview, position=_next_position(module.lessons),
    )


@transaction.atomic
def add_asset(*, lesson, file, kind=Asset.Kind.DOCUMENT):
    return Asset.objects.create(
        lesson=lesson, file=file, kind=kind,
        original_name=getattr(file, "name", "")[:255],
        size_bytes=getattr(file, "size", 0) or 0,
        position=_next_position(lesson.assets),
    )


@transaction.atomic
def reorder_course(*, course, modules):
    """One request for a whole drag-and-drop rearrange.

    modules = [{"id": <module id>, "lessons": [<lesson id>, ...]}, ...]
    Every id must belong to this course, or nothing is saved.
    """
    course_modules = {str(m.id): m for m in course.modules.all()}
    course_lessons = {str(lesson.id): lesson
                      for m in course_modules.values() for lesson in m.lessons.all()}

    to_save_modules, to_save_lessons = [], []
    for m_index, entry in enumerate(modules):
        module = course_modules.get(str(entry.get("id")))
        if module is None:
            raise DomainError("That module is not part of this course.",
                              code="invalid_module")
        module.position = m_index
        to_save_modules.append(module)

        for l_index, lesson_id in enumerate(entry.get("lessons", [])):
            lesson = course_lessons.get(str(lesson_id))
            if lesson is None:
                raise DomainError("That lesson is not part of this course.",
                                  code="invalid_lesson")
            lesson.position = l_index
            lesson.module = module  # supports dragging a lesson between modules
            to_save_lessons.append(lesson)

    Module.objects.bulk_update(to_save_modules, ["position"])
    Lesson.objects.bulk_update(to_save_lessons, ["position", "module"])
    return course