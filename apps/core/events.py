"""Tiny in-process event bus.

Usage:
    @subscribe("enrollment.created")
    def build_release_plan(enrollment_id): ...

    emit("enrollment.created", enrollment_id=str(enrollment.id))

Handlers run after the surrounding DB transaction commits; handlers that do
slow work should just enqueue a Celery task.
"""
from collections import defaultdict

from django.db import transaction

_handlers = defaultdict(list)


def subscribe(event_name):
    def decorator(fn):
        _handlers[event_name].append(fn)
        return fn

    return decorator


def emit(event_name, **payload):
    for handler in _handlers[event_name]:
        transaction.on_commit(lambda h=handler: h(**payload))
