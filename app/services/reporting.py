import csv
import io
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import Role, User
from app.repositories.reports import list_report_complaints
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class ReportBureauRequired(Exception):
    pass


def _report_complaints(
    db: Session,
    actor: User,
    *,
    bureau_id: Optional[int],
    status: Optional[str],
    priority: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[Complaint]:
    if actor.role == Role.OFFICIAL and actor.bureau_id is None:
        raise ReportBureauRequired
    return list_report_complaints(
        db,
        actor,
        bureau_id=bureau_id,
        status=status,
        priority=priority,
        limit=limit,
    )


def generate_csv_report(
    db: Session,
    actor: User,
    *,
    bureau_id: Optional[int],
    status: Optional[str],
    priority: Optional[str],
) -> tuple[str, str]:
    complaints = _report_complaints(
        db,
        actor,
        bureau_id=bureau_id,
        status=status,
        priority=priority,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Receipt ID",
            "Institution",
            "State",
            "City",
            "Category",
            "Priority",
            "Subject",
            "Status",
            "Bureau",
            "Assigned Official",
            "SLA Due Date",
            "Overdue",
            "Determination",
            "Created At",
            "Closed At",
        ]
    )
    for complaint in complaints:
        writer.writerow(
            [
                complaint.receipt_id,
                complaint.institution_name,
                complaint.institution_state,
                complaint.institution_city,
                complaint.category,
                complaint.priority.value,
                complaint.subject,
                complaint.status.value,
                complaint.bureau.name if complaint.bureau else "Unallocated",
                (
                    complaint.assigned_official.full_name
                    if complaint.assigned_official
                    else "Unassigned"
                ),
                (
                    complaint.sla_due_at.strftime("%Y-%m-%d %H:%M")
                    if complaint.sla_due_at
                    else ""
                ),
                "Yes" if complaint.is_overdue else "No",
                complaint.determination.value,
                (
                    complaint.created_at.strftime("%Y-%m-%d %H:%M")
                    if complaint.created_at
                    else ""
                ),
                (
                    complaint.closed_at.strftime("%Y-%m-%d %H:%M")
                    if complaint.closed_at
                    else ""
                ),
            ]
        )
    filename = f"drishti_aicte_grievances_{datetime.now():%Y%m%d_%H%M%S}.csv"
    return output.getvalue(), filename


def generate_pdf_report(
    db: Session,
    actor: User,
    *,
    bureau_id: Optional[int],
    status: Optional[str],
) -> tuple[io.BytesIO, str]:
    complaints = _report_complaints(
        db,
        actor,
        bureau_id=bureau_id,
        status=status,
        limit=100,
    )
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#0F2537"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "SubTitleStyle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=15,
    )
    story.append(
        Paragraph(
            "DRISHTI AICTE - Executive Grievance Redressal Audit Report",
            title_style,
        )
    )
    story.append(
        Paragraph(
            f"Generated on {datetime.now(timezone.utc):%d %B %Y %H:%M UTC} | "
            f"Authorized by: {actor.full_name} ({actor.role.value})",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 10))

    total_complaints = len(complaints)
    closed_complaints = sum(
        complaint.status == ComplaintStatus.CLOSED for complaint in complaints
    )
    overdue_complaints = sum(complaint.is_overdue for complaint in complaints)
    kpi_data = [
        [
            "Total Complaints Audited",
            "Active In-Pipeline",
            "Resolved / Closed",
            "SLA Overdue Escalated",
        ],
        [
            str(total_complaints),
            str(total_complaints - closed_complaints),
            str(closed_complaints),
            str(overdue_complaints),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[180, 180, 180, 180])
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2537")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 14),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#E87722")),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#D1D5DB")),
            ]
        )
    )
    story.extend([kpi_table, Spacer(1, 20)])

    table_rows = [
        [
            "Receipt ID",
            "Institution",
            "Category",
            "Priority",
            "Status",
            "Bureau",
            "Assigned Official",
            "SLA Status",
        ]
    ]
    for complaint in complaints[:40]:
        table_rows.append(
            [
                complaint.receipt_id,
                complaint.institution_name[:24],
                complaint.category[:18],
                complaint.priority.value,
                complaint.status.value,
                complaint.bureau.code if complaint.bureau else "GEN",
                (
                    complaint.assigned_official.full_name[:16]
                    if complaint.assigned_official
                    else "Unassigned"
                ),
                "OVERDUE" if complaint.is_overdue else "In SLA",
            ]
        )
    cases_table = Table(
        table_rows, colWidths=[95, 150, 110, 65, 85, 65, 105, 75]
    )
    cases_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E87722")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F9FAFB")],
                ),
            ]
        )
    )
    story.append(cases_table)
    doc.build(story)
    buffer.seek(0)
    filename = f"drishti_aicte_report_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    return buffer, filename
