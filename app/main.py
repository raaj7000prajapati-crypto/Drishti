import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import Base, engine, get_db, setup_audit_triggers
from app.core.logging import logger
from app.api import api_v1_router
from app.services.sla import start_sla_scheduler, shutdown_sla_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and triggers
    logger.info("Initializing Drishti AICTE database schemas...")
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        setup_audit_triggers(conn)
    logger.info("Database initialized successfully.")

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

# Static file serving for evidence attachments
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.STORAGE_DIR), name="uploads")

# Include Versioned API Routes (/api/v1)
app.include_router(api_v1_router, prefix="/api")

@app.get("/health", tags=["Health & Monitoring"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint verifying application and database connectivity."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e}"
        
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": db_status
    }

@app.get("/metrics", tags=["Health & Monitoring"])
def get_system_metrics(db: Session = Depends(get_db)):
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
