"""Write operations for enrollments and the drip engine."""
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import DomainError
from apps.courses.models import Course, Lesson
from apps.delivery import services as delivery

from .models import Enrollment, LessonProgress, LessonRelease
from .selectors import lesson_availability

logger = logging.getLogger(__name__)


# ---------- enrolling ----------

@transaction.atomic
def create_enrollment(*, course, student, source=Enrollment.Source.FREE):
    """The single door into a course. Checkout, free sign-up and the creator's
    manual add all come through here, so the rules live in one place.
    """
    if course.status != Course.Status.PUBLISHED and source != Enrollment.Source.MANUAL:
        raise DomainError("This course isn't available yet.", code="course_not_published")

    existing = Enrollment.objects.filter(course=course, student=student).first()
    if existing:
        if existing.status == Enrollment.Status.CANCELLED:
            existing.status = Enrollment.Status.ACTIVE
            existing.cancelled_at = None
            existing.save(update_fields=["status", "cancelled_at", "updated_at"])
            return existing
        raise DomainError("You're already enrolled in this course.",
                          code="already_enrolled")

    enrollment = Enrollment.objects.create(
        academy=course.academy, course=course, student=student, source=source,
        timezone=student.timezone or course.timezone,
    )
    build_release_plan(enrollment)
    # In-app notifications are plain rows in this same transaction, so they need
    # no on_commit. Channels that call outside (email, WhatsApp) will enqueue
    # their own tasks inside apps.delivery.
    delivery.notify_enrolled(enrollment=enrollment)
    return enrollment


@transaction.atomic
def cancel_enrollment(*, enrollment, reason=""):
    """Refunds and removals. Pending releases stop; history is kept."""
    enrollment.status = Enrollment.Status.CANCELLED
    enrollment.cancelled_at = timezone.now()
    enrollment.save(update_fields=["status", "cancelled_at", "updated_at"])
    enrollment.releases.filter(status=LessonRelease.Status.PENDING).delete()
    return enrollment


# ---------- the schedule ----------

def _lessons_in_order(course):
    return list(
        Lesson.objects.filter(module__course=course)
        .select_related("module")
        .order_by("module__position", "position", "created_at")
    )


def compute_release_times(course, *, start=None, student_timezone=None, count=0):
    """When each lesson should arrive.

    immediate -> everything now
    daily/weekly/custom -> lesson 1 now, then at the course's delivery_time
    in the student's own timezone, every N days.
    """
    start = start or timezone.now()
    if course.schedule_type == Course.ScheduleType.IMMEDIATE:
        return [start] * count

    interval = {
        Course.ScheduleType.DAILY: 1,
        Course.ScheduleType.WEEKLY: 7,
    }.get(course.schedule_type, max(course.drip_interval_days, 1))

    delivery_time = course.delivery_time
    if isinstance(delivery_time, str):  # unsaved instance still holding the default
        delivery_time = time.fromisoformat(delivery_time)

    tz = ZoneInfo(student_timezone or course.timezone)
    local_start = start.astimezone(tz)
    times = [start]  # the first lesson always arrives straight away
    for index in range(1, count):
        day = (local_start + timedelta(days=interval * index)).date()
        local = datetime.combine(day, delivery_time, tzinfo=tz)
        times.append(local.astimezone(timezone.get_current_timezone()))
    return times


@transaction.atomic
def build_release_plan(enrollment, *, start=None):
    """Create every LessonRelease up front, so the whole plan is visible
    and editable instead of hidden inside a queue."""
    lessons = _lessons_in_order(enrollment.course)
    times = compute_release_times(
        enrollment.course, start=start,
        student_timezone=enrollment.timezone, count=len(lessons),
    )
    LessonRelease.objects.bulk_create([
        LessonRelease(enrollment=enrollment, lesson=lesson, position=index,
                      release_at=times[index])
        for index, lesson in enumerate(lessons)
    ])
    return enrollment.releases.all()


@transaction.atomic
def sync_release_plan(enrollment):
    """Called when a creator adds lessons to a course students are already taking.

    Existing rows keep their dates; new lessons are appended to the end.
    """
    have = set(enrollment.releases.values_list("lesson_id", flat=True))
    lessons = [lesson for lesson in _lessons_in_order(enrollment.course)
               if lesson.id not in have]
    if not lessons:
        return enrollment

    last = enrollment.releases.order_by("-position").first()
    start = last.release_at if last else timezone.now()
    offset = (last.position + 1) if last else 0
    times = compute_release_times(
        enrollment.course, start=start, student_timezone=enrollment.timezone,
        count=len(lessons) + 1,
    )[1:]  # skip the "now" slot: these come after the last existing lesson
    LessonRelease.objects.bulk_create([
        LessonRelease(enrollment=enrollment, lesson=lesson, position=offset + index,
                      release_at=times[index])
        for index, lesson in enumerate(lessons)
    ])
    return enrollment


# ---------- dispatch ----------

def dispatch_release(release_id):
    """Deliver one lesson. Idempotent: a second run is a no-op."""
    release = (
        LessonRelease.objects.select_related("enrollment", "enrollment__student", "lesson")
        .filter(pk=release_id).first()
    )
    if release is None or release.status == LessonRelease.Status.SENT:
        return None
    if not release.enrollment.is_active:
        return None

    delivery.notify_lesson_released(enrollment=release.enrollment, lesson=release.lesson)
    release.status = LessonRelease.Status.SENT
    release.sent_at = timezone.now()
    release.attempts += 1
    release.save(update_fields=["status", "sent_at", "attempts", "updated_at"])
    return release


# ---------- progress ----------

@transaction.atomic
def open_lesson(*, enrollment, lesson):
    available, reason = lesson_availability(enrollment, lesson)
    if not available:
        raise DomainError("This lesson isn't available yet.", code=reason, status_code=403)
    progress, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    if progress.opened_at is None:
        progress.opened_at = timezone.now()
        progress.save(update_fields=["opened_at", "updated_at"])
    return progress


@transaction.atomic
def complete_lesson(*, enrollment, lesson):
    progress = open_lesson(enrollment=enrollment, lesson=lesson)
    if progress.completed_at is None:
        progress.completed_at = timezone.now()
        progress.save(update_fields=["completed_at", "updated_at"])
    check_course_completion(enrollment)
    return progress


@transaction.atomic
def check_course_completion(enrollment):
    """Completed once every lesson in the plan is done."""
    if enrollment.status != Enrollment.Status.ACTIVE:
        return enrollment
    total = enrollment.releases.count()
    done = enrollment.progress.filter(completed_at__isnull=False).count()
    if total and done >= total:
        enrollment.status = Enrollment.Status.COMPLETED
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["status", "completed_at", "updated_at"])
        delivery.notify_course_completed(enrollment=enrollment)
        # TODO: certificates module hooks in here
    return enrollment