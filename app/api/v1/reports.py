import io
import csv
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, Role
from app.models.complaint import Complaint, ComplaintStatus
from app.models.bureau import Bureau
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

router = APIRouter(prefix="/reports", tags=["Reports & Export"])

admin_or_official = require_roles([Role.ADMIN, Role.OFFICIAL])

@router.get("/export/csv")
def export_csv(
    bureau_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_official)
):
    """Export grievance records to CSV."""
    query = db.query(Complaint)
    if current_user.role == Role.OFFICIAL and current_user.bureau_id:
        query = query.filter(Complaint.bureau_id == current_user.bureau_id)
    elif bureau_id:
        query = query.filter(Complaint.bureau_id == bureau_id)

    if status and status != "All":
        query = query.filter(Complaint.status == status)
    if priority and priority != "All":
        query = query.filter(Complaint.priority == priority)

    complaints = query.order_by(Complaint.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Receipt ID", "Institution", "State", "City", "Category", 
        "Priority", "Subject", "Status", "Bureau", "Assigned Official", 
        "SLA Due Date", "Overdue", "Determination", "Created At", "Closed At"
    ])

    for c in complaints:
        writer.writerow([
            c.receipt_id,
            c.institution_name,
            c.institution_state,
            c.institution_city,
            c.category,
            c.priority.value,
            c.subject,
            c.status.value,
            c.bureau.name if c.bureau else "Unallocated",
            c.assigned_official.full_name if c.assigned_official else "Unassigned",
            c.sla_due_at.strftime("%Y-%m-%d %H:%M") if c.sla_due_at else "",
            "Yes" if c.is_overdue else "No",
            c.determination.value,
            c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
            c.closed_at.strftime("%Y-%m-%d %H:%M") if c.closed_at else ""
        ])

    csv_data = output.getvalue()
    filename = f"drishti_aicte_grievances_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/pdf")
def export_pdf(
    bureau_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_official)
):
    """Generate executive AICTE grievance audit summary in PDF format."""
    query = db.query(Complaint)
    if current_user.role == Role.OFFICIAL and current_user.bureau_id:
        query = query.filter(Complaint.bureau_id == current_user.bureau_id)
    elif bureau_id:
        query = query.filter(Complaint.bureau_id == bureau_id)

    if status and status != "All":
        query = query.filter(Complaint.status == status)

    complaints = query.order_by(Complaint.created_at.desc()).limit(100).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    # Header title
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#0F2537"),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "SubTitleStyle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=15
    )

    story.append(Paragraph("DRISHTI AICTE - Executive Grievance Redressal Audit Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now(timezone.utc).strftime('%d %B %Y %H:%M UTC')} | Authorized by: {current_user.full_name} ({current_user.role.value})", subtitle_style))
    story.append(Spacer(1, 10))

    # Summary Statistics
    total_c = len(complaints)
    closed_c = sum(1 for c in complaints if c.status == ComplaintStatus.CLOSED)
    overdue_c = sum(1 for c in complaints if c.is_overdue)
    active_c = total_c - closed_c

    kpi_data = [
        ["Total Complaints Audited", "Active In-Pipeline", "Resolved / Closed", "SLA Overdue Escalated"],
        [str(total_c), str(active_c), str(closed_c), str(overdue_c)]
    ]
    kpi_table = Table(kpi_data, colWidths=[180, 180, 180, 180])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F2537")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F3F4F6")),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 14),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor("#E87722")),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#D1D5DB")),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 20))

    # Complaints List Table
    table_headers = ["Receipt ID", "Institution", "Category", "Priority", "Status", "Bureau", "Assigned Official", "SLA Status"]
    table_rows = [table_headers]

    for c in complaints[:40]:  # Up to 40 for clean PDF layout
        table_rows.append([
            c.receipt_id,
            c.institution_name[:24],
            c.category[:18],
            c.priority.value,
            c.status.value,
            c.bureau.code if c.bureau else "GEN",
            c.assigned_official.full_name[:16] if c.assigned_official else "Unassigned",
            "OVERDUE" if c.is_overdue else "In SLA"
        ])

    cases_table = Table(table_rows, colWidths=[95, 150, 110, 65, 85, 65, 105, 75])
    cases_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E87722")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
    ]))
    story.append(cases_table)

    doc.build(story)
    buffer.seek(0)
    filename = f"drishti_aicte_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
