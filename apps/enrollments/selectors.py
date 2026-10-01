"""Read/query helpers for enrollments."""
from django.db.models import Count, Q
from django.utils import timezone

from .models import Enrollment, LessonProgress, LessonRelease


def user_has_enrollments(user):
    """True if the user is a student anywhere. Used by /auth/me/."""
    return Enrollment.objects.filter(
        student=user, status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED]
    ).exists()


def enrollments_for_student(user):
    return (
        Enrollment.objects.filter(student=user)
        .exclude(status=Enrollment.Status.CANCELLED)
        .select_related("course", "academy")
    )


def enrollments_for_course(course):
    return (
        Enrollment.objects.filter(course=course)
        .select_related("student")
        .annotate(
            lessons_completed=Count("progress", filter=Q(progress__completed_at__isnull=False)),
        )
        .order_by("-created_at")
    )


def released_lessons(enrollment):
    """Releases whose time has passed, newest schedule order first."""
    return (
        LessonRelease.objects.filter(enrollment=enrollment, release_at__lte=timezone.now())
        .select_related("lesson", "lesson__module")
        .order_by("position")
    )


def progress_map(enrollment):
    return {p.lesson_id: p for p in LessonProgress.objects.filter(enrollment=enrollment)}


def lesson_availability(enrollment, lesson):
    """Why a lesson is or isn't open. Returns (available, reason).

    Two gates:
      1. the schedule  — its release time has passed
      2. sequential    — if the course requires it, the previous lesson is done
    """
    if not enrollment.is_active:
        return False, "enrollment_inactive"

    release = LessonRelease.objects.filter(enrollment=enrollment, lesson=lesson).first()
    if release is None:
        return False, "not_in_course"
    if release.release_at > timezone.now():
        return False, "not_released_yet"

    if enrollment.course.require_sequential and release.position > 0:
        previous = (
            LessonRelease.objects.filter(enrollment=enrollment,
                                         position=release.position - 1)
            .values_list("lesson_id", flat=True)
            .first()
        )
        done = LessonProgress.objects.filter(
            enrollment=enrollment, lesson_id=previous, completed_at__isnull=False
        ).exists()
        if not done:
            return False, "previous_lesson_incomplete"

    return True, ""


def course_progress(enrollment):
    total = LessonRelease.objects.filter(enrollment=enrollment).count()
    done = LessonProgress.objects.filter(
        enrollment=enrollment, completed_at__isnull=False
    ).count()
    released = LessonRelease.objects.filter(
        enrollment=enrollment, release_at__lte=timezone.now()
    ).count()
    return {
        "total_lessons": total,
        "released_lessons": released,
        "completed_lessons": done,
        "percent_complete": round(done / total * 100) if total else 0,
    }


def due_releases(limit=500):
    """Pending rows whose time has come. Used by the beat sweeper."""
    return (
        LessonRelease.objects.filter(status=LessonRelease.Status.PENDING,
                                     release_at__lte=timezone.now(),
                                     enrollment__status=Enrollment.Status.ACTIVE)
        .order_by("release_at")[:limit]
    )