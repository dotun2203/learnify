"""The channel layer. Today: the web portal's in-app notifications.

Everything that wants to reach a student calls notify(). When WhatsApp and
email arrive they become extra branches here, and no caller changes.
"""
from .models import Notification


def notify(*, user, kind, title, body="", link=""):
    return Notification.objects.create(
        user=user, kind=kind, title=title, body=body, link=link
    )


def notify_lesson_released(*, enrollment, lesson):
    course = enrollment.course
    return notify(
        user=enrollment.student,
        kind=Notification.Kind.LESSON_RELEASED,
        title=f"New lesson: {lesson.title}",
        body=f"Your next lesson in {course.title} is ready.",
        link=f"/learn/{enrollment.id}/lessons/{lesson.id}",
    )


def notify_enrolled(*, enrollment):
    return notify(
        user=enrollment.student,
        kind=Notification.Kind.ENROLLED,
        title=f"Welcome to {enrollment.course.title}",
        body="Your first lesson is on the way.",
        link=f"/learn/{enrollment.id}",
    )


def notify_course_completed(*, enrollment):
    return notify(
        user=enrollment.student,
        kind=Notification.Kind.COURSE_COMPLETED,
        title=f"You finished {enrollment.course.title}",
        body="Well done!",
        link=f"/learn/{enrollment.id}",
    )