import os

from celery import Celery
from kombu import Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("learnify")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.task_queues = (
    Queue("default"),
    Queue("webhooks"),
    Queue("delivery"),
    Queue("ai"),
    Queue("documents"),
)
app.conf.task_default_queue = "default"
app.conf.task_routes = {
    "apps.payments.tasks.*": {"queue": "webhooks"},
    "apps.delivery.tasks.*": {"queue": "delivery"},
    "apps.ai_builder.tasks.*": {"queue": "ai"},
    "apps.tutor.tasks.*": {"queue": "ai"},
    "apps.certificates.tasks.*": {"queue": "documents"},
    "apps.enrollments.tasks.*": {"queue": "delivery"},
}

app.autodiscover_tasks()
