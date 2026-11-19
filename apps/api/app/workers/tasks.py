"""Celery background tasks with automatic Redis check and local thread fallback."""

from concurrent.futures import ThreadPoolExecutor
import socket
from urllib.parse import urlparse

from app.core.config import settings
from app.services.intelligence_pipeline import process_batch_sync
from app.workers.celery_app import celery_app

_LOCAL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ldi-worker")


def _is_redis_reachable() -> bool:
    if settings.CELERY_ALWAYS_EAGER:
        return False
    try:
        parsed = urlparse(settings.CELERY_BROKER_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        with socket.create_connection((host, port), timeout=0.6):
            return True
    except OSError:
        return False


@celery_app.task(name="ldi.process_upload_batch", bind=True, max_retries=3)
def process_upload_batch_task(
    self,
    batch_id: str,
    naming_convention_override: str | None = None,
) -> dict:
    """Celery task entry point for asynchronous batch document intelligence."""
    return process_batch_sync(
        batch_id, naming_convention_override=naming_convention_override
    )


def dispatch_batch_processing(
    batch_id: str,
    naming_convention_override: str | None = None,
    sync: bool = False,
) -> str:
    """Dispatch batch processing to Celery/Redis when reachable, or background thread pool locally."""
    if sync or settings.CELERY_ALWAYS_EAGER:
        process_batch_sync(batch_id, naming_convention_override=naming_convention_override)
        return "sync-eager"

    if _is_redis_reachable():
        async_res = process_upload_batch_task.delay(
            batch_id, naming_convention_override=naming_convention_override
        )
        return str(async_res.id)

    # Local standalone async fallback when Redis isn't running on host
    _LOCAL_EXECUTOR.submit(
        process_batch_sync,
        batch_id,
        naming_convention_override,
    )
    return f"local-thread-{batch_id}"
