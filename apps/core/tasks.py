from celery import shared_task


@shared_task
def ping():
    """Smoke-test task: `from apps.core.tasks import ping; ping.delay()`."""
    return "pong"
