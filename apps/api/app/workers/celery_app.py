"""Celery application configured for Redis broker & result backend."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ldi_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=settings.CELERY_ALWAYS_EAGER,
    broker_connection_retry_on_startup=True,
)
