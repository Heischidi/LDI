"""Main FastAPI application for Leaders Document Intelligence (LDI)."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import (
    applicants,
    audit,
    auth,
    dashboard,
    documents,
    exports,
    processing,
    reminders,
    reports,
    requirements,
    settings as settings_route,
    users,
)
from app.api.routes.reminders import process_due_personal_reminders
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.services.seed_service import seed_initial_data


async def _reminder_scheduler_loop() -> None:
    """Periodically dispatch due twice-daily personal/CEO email reminders."""
    while True:
        try:
            await asyncio.sleep(60)
            db = SessionLocal()
            try:
                process_due_personal_reminders(db)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize database schema (if standalone) and ensure baseline seed records exist."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
        process_due_personal_reminders(db)
    finally:
        db.close()
    reminder_task = asyncio.create_task(_reminder_scheduler_loop())
    try:
        yield
    finally:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass


limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Enterprise document intelligence, classification, validation, and folder organization platform for Leaders Edu Tour Ltd.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "ai_provider": settings.AI_PROVIDER,
        "storage_backend": settings.STORAGE_BACKEND,
    }


prefix = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=prefix)
app.include_router(dashboard.router, prefix=prefix)
app.include_router(applicants.router, prefix=prefix)
app.include_router(requirements.router, prefix=prefix)
app.include_router(documents.router, prefix=prefix)
app.include_router(processing.router, prefix=prefix)
app.include_router(exports.router, prefix=prefix)
app.include_router(reports.router, prefix=prefix)
app.include_router(users.router, prefix=prefix)
app.include_router(reminders.router, prefix=prefix)
app.include_router(audit.router, prefix=prefix)
app.include_router(settings_route.router, prefix=prefix)
