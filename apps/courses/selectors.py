"""Read/query helpers for this app live here."""
from apps.academies.models import Academy

from .models import Course, Lesson, Module


def courses_for_academy(academy):
    return Course.objects.filter(academy=academy).select_related("academy")


def course_detail_qs(academy):
    return courses_for_academy(academy).prefetch_related("modules__lessons__assets")


def published_courses(academy_slug=None):
    """Public catalogue: only published courses of active academies."""
    qs = (
        Course.objects.filter(status=Course.Status.PUBLISHED,
                              academy__status=Academy.Status.ACTIVE)
        .select_related("academy")
    )
    if academy_slug:
        qs = qs.filter(academy__slug=academy_slug)
    return qs


def modules_for_academy(academy):
    return Module.objects.filter(course__academy=academy).select_related("course")


def lessons_for_academy(academy):
    return Lesson.objects.filter(module__course__academy=academy).select_related(
        "module", "module__course"
    )


def publish_blockers(course):
    """Human-readable reasons a course can't go live yet. Empty list = ready."""
    problems = []
    if not course.title:
        problems.append("Add a title.")
    if not course.description:
        problems.append("Add a description.")
    if not course.cover:
        problems.append("Upload a cover image.")
    if not course.academy.is_active:
        problems.append("Finish your academy onboarding first.")

    modules = list(course.modules.prefetch_related("lessons"))
    if not modules:
        problems.append("Add at least one module.")
    elif not any(m.lessons.exists() for m in modules):
        problems.append("Add at least one lesson.")
    else:
        empty = [m.title for m in modules if not m.lessons.exists()]
        if empty:
            problems.append(f"These modules have no lessons: {', '.join(empty)}.")
    return problems
