from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import engine, get_db, setup_audit_triggers
from app.core.logging import logger
from app.core.permissions import require_permission, validate_production_security
from app.api import api_v1_router
from app.services.sla import start_sla_scheduler, shutdown_sla_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_security()
    # Schema creation and upgrades are managed by Alembic before the app starts.
    logger.info("Installing database audit safeguards...")
    with engine.connect() as conn:
        setup_audit_triggers(conn)
    logger.info("Database audit safeguards installed.")

    # Start APScheduler for SLA Escalations
    start_sla_scheduler()
    
    yield

    # Shutdown
    shutdown_sla_scheduler()
    logger.info("Drishti AICTE backend shutdown complete.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="All India Council for Technical Education - Intelligent Grievance Redressal & Cross-Bureau Correlation System",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware locked to frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Versioned API Routes (/api/v1)
app.include_router(api_v1_router, prefix="/api")


@app.middleware("http")
async def apply_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.get("/health", tags=["Health & Monitoring"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint verifying application and database connectivity."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check could not reach the database")
        db_status = "unhealthy"
        
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": db_status
    }

@app.get("/metrics", tags=["Health & Monitoring"])
def get_system_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("admin.manage")),
):
    """Basic Prometheus-compatible system metrics endpoint."""
    from app.models.complaint import Complaint, ComplaintStatus
    from app.models.user import User
    
    total_complaints = db.query(Complaint).count()
    overdue_complaints = db.query(Complaint).filter(Complaint.is_overdue == True).count()
    closed_complaints = db.query(Complaint).filter(Complaint.status == ComplaintStatus.CLOSED).count()
    total_users = db.query(User).count()

    return {
        "drishti_complaints_total": total_complaints,
        "drishti_complaints_overdue": overdue_complaints,
        "drishti_complaints_closed": closed_complaints,
        "drishti_users_total": total_users,
    }
