"""Main FastAPI application for Leaders Document Intelligence (LDI)."""

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
    reports,
    requirements,
    settings as settings_route,
    users,
)
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.services.seed_service import seed_initial_data


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize database schema (if standalone) and ensure baseline seed records exist."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
    yield


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
app.include_router(audit.router, prefix=prefix)
app.include_router(settings_route.router, prefix=prefix)
