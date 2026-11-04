from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import AsyncSessionLocal
from app.routers import auth, users, reports, audit_logs, agencies, pipeline, analytics, ml_analytics, chunks
from app.services.auth_service import seed_roles_and_admin

# Import all models so Alembic can discover them
from app.models import user, report, audit  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: seed admin user and roles on startup."""
    logger.info("Starting application...")
    try:
        async with AsyncSessionLocal() as session:
            await seed_roles_and_admin(session)
            logger.info("Database seeded successfully")
    except Exception as e:
        logger.error(f"Failed to seed database: {e}")
    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title="Cybersecurity Audit Report Management System",
    description="Phase 1 - Report management with RBAC, file upload, and audit logging",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(audit_logs.router)
app.include_router(agencies.router)
app.include_router(pipeline.router)
app.include_router(analytics.router)
app.include_router(ml_analytics.router)
app.include_router(chunks.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "cyber-audit-backend"}
