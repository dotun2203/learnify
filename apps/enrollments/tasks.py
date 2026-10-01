"""Celery tasks for enrollments — the drip engine."""
import logging

from celery import shared_task
from django.db import transaction

from .models import LessonRelease
from .selectors import due_releases
from .services import dispatch_release

logger = logging.getLogger(__name__)


@shared_task
def dispatch_due_lesson_releases(batch_size=500):
    """Beat runs this every minute.

    Rows are claimed with SELECT ... FOR UPDATE SKIP LOCKED and flipped to
    'queued' before any sending, so two workers never deliver the same lesson.
    """
    with transaction.atomic():
        ids = list(
            LessonRelease.objects.select_for_update(skip_locked=True)
            .filter(pk__in=[r.pk for r in due_releases(batch_size)])
            .values_list("pk", flat=True)
        )
        LessonRelease.objects.filter(pk__in=ids).update(
            status=LessonRelease.Status.QUEUED
        )

    for release_id in ids:
        send_lesson_release.delay(str(release_id))
    return len(ids)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_lesson_release(self, release_id):
    return bool(dispatch_release(release_id))