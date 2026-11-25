import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import CampusService, Device, Incident, User, VLAN
from app.services.service_intelligence import ServiceIntelligenceEngine
from app.core.dependencies import require_viewer

router = APIRouter(prefix="/reports", tags=["NOC Reports"])


def _build_minimal_pdf(title: str, lines: List[str]) -> bytes:
    """Generate a valid single-page PDF 1.4 document with zero external dependencies."""
    safe_lines = [title, "Source: SIMULATION / DEMONSTRATION DATA", "-" * 60] + lines[:42]
    text_cmds = ["BT", "/F1 10 Tf", "40 760 Td", "14 TL"]
    for idx, line in enumerate(safe_lines):
        esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:95]
        if idx == 0:
            text_cmds.append(f"({esc}) Tj")
        else:
            text_cmds.append(f"T* ({esc}) Tj")
    text_cmds.append("ET")
    stream = "\n".join(text_cmds).encode("latin-1", errors="replace")

    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for o in objs:
        offsets.append(len(pdf))
        pdf.extend(o)
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1"))
    return bytes(pdf)


def _generate_report_data(db: Session, report_type: str) -> Dict[str, Any]:
    rtype = report_type.strip().lower()
    now = datetime.now(timezone.utc)

    if rtype in {"daily_incidents", "weekly_incidents", "critical_incidents"}:
        hours = 24 if rtype == "daily_incidents" else 168
        cutoff = now - timedelta(hours=hours)
        q = db.query(Incident).filter(Incident.created_at >= cutoff)
        if rtype == "critical_incidents":
            q = db.query(Incident).filter(Incident.severity.ilike("critical"))
        rows = q.order_by(Incident.created_at.desc()).limit(200).all()
        return {
            "title": f"NetGuardian {rtype.replace('_', ' ').title()}",
            "data_source": "SIMULATION",
            "generated_at": now.isoformat(),
            "columns": ["incident_number", "title", "severity", "priority", "lifecycle_state", "assigned_to", "created_at"],
            "rows": [
                {
                    "incident_number": r.incident_number,
                    "title": r.title,
                    "severity": r.severity,
                    "priority": r.priority or "P2",
                    "lifecycle_state": r.lifecycle_state or "NEW",
                    "assigned_to": r.assigned_to or "Unassigned",
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ],
        }

    if rtype == "monthly_sla":
        services = db.query(CampusService).all()
        if not services:
            ServiceIntelligenceEngine.seed_campus_services(db)
            services = db.query(CampusService).all()
        slas = [ServiceIntelligenceEngine.calculate_service_sla(db, s, window_hours=720) for s in services]
        return {
            "title": "NetGuardian Monthly Service SLA Report (SIMULATION)",
            "data_source": "SIMULATION_DEMONSTRATION",
            "generated_at": now.isoformat(),
            "columns": ["name", "current_status", "sla_target_pct", "availability_pct", "sla_compliant", "downtime_minutes"],
            "rows": [
                {
                    "name": s["name"],
                    "current_status": s["current_status"],
                    "sla_target_pct": s["sla_target_pct"],
                    "availability_pct": s["availability_pct"],
                    "sla_compliant": s["sla_compliant"],
                    "downtime_minutes": s["downtime_minutes"],
                }
                for s in slas
            ],
        }

    if rtype == "department_health":
        vlans = db.query(VLAN).order_by(VLAN.vlan_id.asc()).all()
        devs = db.query(Device).all()
        rows = []
        for v in vlans:
            eps = [d for d in devs if d.vlan_id == v.vlan_id and d.asset_category == "student_endpoint"]
            online = sum(1 for d in eps if d.status != "offline")
            rows.append({
                "department": v.department or v.name,
                "vlan_id": v.vlan_id,
                "subnet": v.subnet,
                "total_endpoints": len(eps),
                "online_endpoints": online,
                "availability_pct": round((online / max(1, len(eps))) * 100.0, 2),
            })
        return {
            "title": "NetGuardian Department Network Health Report (SIMULATION)",
            "data_source": "SIMULATION",
            "generated_at": now.isoformat(),
            "columns": ["department", "vlan_id", "subnet", "total_endpoints", "online_endpoints", "availability_pct"],
            "rows": rows,
        }

    if rtype == "engineer_workload":
        incs = db.query(Incident).all()
        counts: Dict[str, Dict[str, int]] = {}
        for i in incs:
            owner = i.assigned_to or "Unassigned"
            entry = counts.setdefault(owner, {"assigned_total": 0, "open_count": 0, "resolved_count": 0})
            entry["assigned_total"] += 1
            if i.status in {"RESOLVED", "CLOSED"}:
                entry["resolved_count"] += 1
            else:
                entry["open_count"] += 1
        return {
            "title": "NetGuardian Engineer Workload Summary",
            "data_source": "SIMULATION",
            "generated_at": now.isoformat(),
            "columns": ["engineer", "assigned_total", "open_count", "resolved_count"],
            "rows": [{"engineer": k, **v} for k, v in counts.items()],
        }

    raise HTTPException(status_code=400, detail=f"Unsupported report type '{report_type}'.")


@router.get("/{report_type}")
def get_report(
    report_type: str,
    format: str = Query(default="json"),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    data = _generate_report_data(db, report_type)
    fmt = format.strip().lower()

    if fmt == "json":
        return data

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=data["columns"])
        writer.writeheader()
        for row in data["rows"]:
            writer.writerow(row)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="netguardian_{report_type}.csv"'},
        )

    if fmt == "pdf":
        lines = [" | ".join(str(r.get(c, "")) for c in data["columns"]) for r in data["rows"]]
        if not lines:
            lines = ["No records matched the requested report window."]
        pdf_bytes = _build_minimal_pdf(data["title"], lines)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="netguardian_{report_type}.pdf"'},
        )

    raise HTTPException(status_code=400, detail="Format must be 'json', 'csv', or 'pdf'.")
