from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.services.reporting import (
    ReportBureauRequired,
    generate_csv_report,
    generate_pdf_report,
)

router = APIRouter(prefix="/reports", tags=["Reports & Export"])
admin_or_official = require_permission("report.export")


@router.get("/export/csv")
def export_csv(
    bureau_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_official),
):
    """Export grievance records to CSV."""
    try:
        content, filename = generate_csv_report(
            db,
            current_user,
            bureau_id=bureau_id,
            status=status,
            priority=priority,
        )
    except ReportBureauRequired as exc:
        raise HTTPException(
            status_code=403,
            detail="Official account is not assigned to a bureau",
        ) from exc
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/pdf")
def export_pdf(
    bureau_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_official),
):
    """Generate an executive grievance audit summary in PDF format."""
    try:
        buffer, filename = generate_pdf_report(
            db,
            current_user,
            bureau_id=bureau_id,
            status=status,
        )
    except ReportBureauRequired as exc:
        raise HTTPException(
            status_code=403,
            detail="Official account is not assigned to a bureau",
        ) from exc
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
