from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import AuditLog, Device, Faculty, ITPersonnel, NetworkLink, Student, User
from app.schemas.campus_inventory import (
    AssetAssignmentRow,
    FacultyCreate,
    FacultyResponse,
    FacultyUpdate,
    InventoryOverviewResponse,
    InventoryValidationResponse,
    ITPersonnelCreate,
    ITPersonnelResponse,
    StudentCreate,
    StudentNetworkResponse,
    StudentResponse,
    StudentUpdate,
)
from app.engines.inventory.validation_engine import DEPT_VLAN_MAP, InventoryValidationEngine
from app.seeders.campus_inventory_seed import seed_campus_inventory
from app.core.dependencies import require_admin, require_engineer, require_viewer

router = APIRouter(prefix="/campus", tags=["Campus Inventory"])


def _to_student_response(s: Student) -> StudentResponse:
    dev = s.device
    return StudentResponse(
        id=s.id,
        student_id=s.student_id,
        full_name=s.full_name,
        department=s.department,
        academic_year=s.academic_year,
        semester=s.semester,
        enrollment_status=s.enrollment_status,
        email=s.email,
        device_id=s.device_id,
        assigned_device=dev.hostname if dev else None,
        assigned_vlan=dev.vlan_id if dev else None,
        assigned_ip=dev.management_ip if dev else None,
        enrollment_date=s.enrollment_date,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _validate_student_device_binding(
    db: Session, department: str, device_id: Optional[str], current_student_id: Optional[str] = None
) -> Optional[Device]:
    if not device_id:
        return None
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=400, detail="Assigned endpoint device not found")
    if dev.department != department:
        raise HTTPException(
            status_code=400,
            detail=f"Department mismatch: student ({department}) cannot be assigned to {dev.department} device",
        )
    expected_vlan = DEPT_VLAN_MAP.get(department)
    if expected_vlan and dev.vlan_id != expected_vlan:
        raise HTTPException(
            status_code=400,
            detail=f"VLAN mismatch: {department} requires VLAN {expected_vlan}, device has VLAN {dev.vlan_id}",
        )
    existing_owner = db.query(Student).filter(Student.device_id == device_id).first()
    if existing_owner and existing_owner.student_id != current_student_id:
        raise HTTPException(
            status_code=400,
            detail=f"Endpoint '{dev.hostname}' is already assigned to another student",
        )
    return dev


# ==============================================================================
# STUDENT INVENTORY
# ==============================================================================

@router.get("/students/summary")
def get_students_summary(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    students = db.query(Student).all()
    by_dept: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for s in students:
        by_dept[s.department] = by_dept.get(s.department, 0) + 1
        by_status[s.enrollment_status] = by_status.get(s.enrollment_status, 0) + 1
    return {
        "total_students": len(students),
        "by_department": by_dept,
        "by_enrollment_status": by_status,
        "assigned_count": sum(1 for s in students if s.device_id is not None),
    }


@router.get("/students", response_model=List[StudentResponse])
def list_students(
    department: Optional[str] = None,
    vlan_id: Optional[int] = None,
    academic_year: Optional[int] = None,
    semester: Optional[int] = None,
    enrollment_status: Optional[str] = None,
    device_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    query = db.query(Student)
    if department:
        query = query.filter(Student.department == department.strip().upper())
    if academic_year is not None:
        query = query.filter(Student.academic_year == academic_year)
    if semester is not None:
        query = query.filter(Student.semester == semester)
    if enrollment_status:
        query = query.filter(Student.enrollment_status == enrollment_status.strip().upper())
    if device_id:
        query = query.filter(Student.device_id == device_id)
    if vlan_id is not None:
        query = query.join(Device, Student.device_id == Device.id).filter(Device.vlan_id == vlan_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Student.student_id.ilike(term), Student.full_name.ilike(term)))

    rows = query.order_by(Student.student_id.asc()).offset(offset).limit(limit).all()
    return [_to_student_response(s) for s in rows]


@router.get("/students/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    s = db.query(Student).filter(Student.student_id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Student record not found")
    return _to_student_response(s)


@router.get("/students/{student_id}/network", response_model=StudentNetworkResponse)
def get_student_network_assignment(
    student_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    s = db.query(Student).filter(Student.student_id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Student record not found")
    if not s.device:
        raise HTTPException(status_code=404, detail="Student has no assigned network endpoint")

    dev = s.device
    sw = db.query(Device).filter(Device.id == dev.connected_switch_id).first() if dev.connected_switch_id else None
    link = db.query(NetworkLink).filter(
        (NetworkLink.target_device_id == dev.id) | (NetworkLink.source_device_id == dev.id)
    ).first()

    return StudentNetworkResponse(
        student_id=s.student_id,
        full_name=s.full_name,
        department=s.department,
        enrollment_status=s.enrollment_status,
        endpoint_hostname=dev.hostname,
        mac_address=dev.mac_address,
        ip_address=dev.management_ip,
        vlan_id=dev.vlan_id,
        connected_switch=sw.hostname if sw else None,
        connected_interface=dev.connected_interface,
        operational_status=dev.status,
        status_source="SIMULATED_INVENTORY",
        link_name=link.name if link else None,
        link_status=link.status if link else None,
        link_speed_mbps=link.bandwidth_mbps if link else None,
    )


@router.post("/students", response_model=StudentResponse, status_code=201)
def create_student(
    payload: StudentCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(Student).filter(Student.student_id == payload.student_id).first():
        raise HTTPException(status_code=400, detail="Student ID already exists")
    if (
        db.query(Student).filter(Student.email == payload.email).first()
        or db.query(Faculty).filter(Faculty.email == payload.email).first()
        or db.query(ITPersonnel).filter(ITPersonnel.email == payload.email).first()
    ):
        raise HTTPException(status_code=400, detail="Email address already exists")

    _validate_student_device_binding(db, payload.department, payload.device_id)

    s = Student(
        student_id=payload.student_id,
        full_name=payload.full_name,
        department=payload.department,
        academic_year=payload.academic_year,
        semester=payload.semester,
        enrollment_status=payload.enrollment_status,
        email=payload.email,
        device_id=payload.device_id,
    )
    db.add(s)
    db.add(AuditLog(
        username=current_user.username,
        action="STUDENT_CREATED",
        resource_type="CAMPUS_INVENTORY",
        resource_id=payload.student_id,
        details={"department": payload.department, "device_id": payload.device_id},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(s)
    return _to_student_response(s)


@router.put("/students/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: str,
    payload: StudentUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    s = db.query(Student).filter(Student.student_id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Student record not found")

    updates = payload.model_dump(exclude_unset=True)
    if "device_id" in updates:
        _validate_student_device_binding(db, s.department, updates["device_id"], current_student_id=s.student_id)

    for k, v in updates.items():
        setattr(s, k, v)
    s.updated_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        username=current_user.username,
        action="STUDENT_UPDATED",
        resource_type="CAMPUS_INVENTORY",
        resource_id=s.student_id,
        details={"updated_fields": sorted(updates.keys())},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(s)
    return _to_student_response(s)


@router.delete("/students/{student_id}")
def delete_student(
    student_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    s = db.query(Student).filter(Student.student_id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Student record not found")
    db.delete(s)
    db.add(AuditLog(
        username=current_user.username,
        action="STUDENT_DELETED",
        resource_type="CAMPUS_INVENTORY",
        resource_id=student_id,
        details={},
        status="SUCCESS",
    ))
    db.commit()
    return {"message": "Student record deleted"}


# ==============================================================================
# FACULTY INVENTORY
# ==============================================================================

@router.get("/faculty/summary")
def get_faculty_summary(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = db.query(Faculty).all()
    by_dept: Dict[str, int] = {}
    for f in rows:
        by_dept[f.department] = by_dept.get(f.department, 0) + 1
    return {"total_faculty": len(rows), "by_department": by_dept}


@router.get("/faculty", response_model=List[FacultyResponse])
def list_faculty(
    department: Optional[str] = None,
    employment_status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    query = db.query(Faculty)
    if department:
        query = query.filter(Faculty.department == department.strip().upper())
    if employment_status:
        query = query.filter(Faculty.employment_status == employment_status.strip().upper())
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Faculty.faculty_id.ilike(term), Faculty.full_name.ilike(term)))
    return query.order_by(Faculty.faculty_id.asc()).offset(offset).limit(limit).all()


@router.get("/faculty/{faculty_id}", response_model=FacultyResponse)
def get_faculty(
    faculty_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    f = db.query(Faculty).filter(Faculty.faculty_id == faculty_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Faculty record not found")
    return f


@router.post("/faculty", response_model=FacultyResponse, status_code=201)
def create_faculty(
    payload: FacultyCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(Faculty).filter(Faculty.faculty_id == payload.faculty_id).first():
        raise HTTPException(status_code=400, detail="Faculty ID already exists")
    if db.query(Faculty).filter(Faculty.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email address already exists")

    f = Faculty(
        faculty_id=payload.faculty_id,
        full_name=payload.full_name,
        department=payload.department,
        designation=payload.designation,
        email=payload.email.lower(),
        employment_status=payload.employment_status,
        office_location=payload.office_location,
    )
    db.add(f)
    db.add(AuditLog(
        username=current_user.username,
        action="FACULTY_CREATED",
        resource_type="CAMPUS_INVENTORY",
        resource_id=payload.faculty_id,
        details={"department": payload.department},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(f)
    return f


# ==============================================================================
# IT PERSONNEL INVENTORY
# ==============================================================================

@router.get("/it-personnel/summary")
def get_it_summary(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = db.query(ITPersonnel).all()
    by_team: Dict[str, int] = {}
    for e in rows:
        by_team[e.team] = by_team.get(e.team, 0) + 1
    return {"total_it_personnel": len(rows), "by_team": by_team}


@router.get("/it-personnel", response_model=List[ITPersonnelResponse])
def list_it_personnel(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    return db.query(ITPersonnel).order_by(ITPersonnel.employee_id.asc()).offset(offset).limit(limit).all()


@router.get("/it-personnel/{employee_id}", response_model=ITPersonnelResponse)
def get_it_employee(
    employee_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    e = db.query(ITPersonnel).filter(ITPersonnel.employee_id == employee_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="IT personnel record not found")
    return e


@router.post("/it-personnel", response_model=ITPersonnelResponse, status_code=201)
def create_it_personnel(
    payload: ITPersonnelCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(ITPersonnel).filter(ITPersonnel.employee_id == payload.employee_id).first():
        raise HTTPException(status_code=400, detail="Employee ID already exists")
    e = ITPersonnel(
        employee_id=payload.employee_id,
        full_name=payload.full_name,
        job_title=payload.job_title,
        team=payload.team,
        access_classification=payload.access_classification,
        employment_status=payload.employment_status,
        email=payload.email.lower(),
    )
    db.add(e)
    db.add(AuditLog(
        username=current_user.username,
        action="IT_PERSONNEL_CREATED",
        resource_type="CAMPUS_INVENTORY",
        resource_id=payload.employee_id,
        details={"job_title": payload.job_title},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(e)
    return e


# ==============================================================================
# OVERVIEW, VALIDATION, ASSIGNMENTS & SEEDER
# ==============================================================================

@router.get("/inventory/overview", response_model=InventoryOverviewResponse)
def get_inventory_overview(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    students = db.query(Student).all()
    faculty = db.query(Faculty).all()
    it_staff = db.query(ITPersonnel).all()
    val = InventoryValidationEngine.validate_inventory(db)

    stu_by_dept: Dict[str, int] = {}
    assigned = 0
    unassigned = 0
    for s in students:
        stu_by_dept[s.department] = stu_by_dept.get(s.department, 0) + 1
        if s.device_id:
            assigned += 1
        else:
            unassigned += 1

    fac_by_dept: Dict[str, int] = {}
    for f in faculty:
        fac_by_dept[f.department] = fac_by_dept.get(f.department, 0) + 1

    coverage = round((assigned / len(students) * 100.0), 2) if students else 0.0
    return InventoryOverviewResponse(
        total_students=len(students),
        students_by_department=stu_by_dept,
        total_faculty=len(faculty),
        faculty_by_department=fac_by_dept,
        total_it_personnel=len(it_staff),
        assigned_endpoints=assigned,
        unassigned_students=unassigned,
        invalid_associations=val["critical_errors"],
        assignment_coverage_pct=coverage,
        inventory_health="HEALTHY" if val["valid"] else "DEGRADED",
        validation_valid=val["valid"],
    )


@router.get("/inventory/validate", response_model=InventoryValidationResponse)
def validate_campus_inventory(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    return InventoryValidationEngine.validate_inventory(db)


@router.get("/inventory/assignments", response_model=List[AssetAssignmentRow])
def list_asset_assignments(
    department: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    query = db.query(Student)
    if department:
        query = query.filter(Student.department == department.strip().upper())
    students = query.order_by(Student.student_id.asc()).offset(offset).limit(limit).all()

    switches = {d.id: d.hostname for d in db.query(Device).filter(Device.device_type == "access_switch").all()}
    rows: List[AssetAssignmentRow] = []
    for s in students:
        dev = s.device
        if not dev:
            status = "UNASSIGNED"
        elif dev.department != s.department:
            status = "DEPARTMENT_MISMATCH"
        elif DEPT_VLAN_MAP.get(s.department) != dev.vlan_id:
            status = "INVALID_ASSIGNMENT"
        else:
            status = "ASSIGNED"

        rows.append(AssetAssignmentRow(
            student_id=s.student_id,
            student_name=s.full_name,
            department=s.department,
            endpoint_hostname=dev.hostname if dev else None,
            ip_address=dev.management_ip if dev else None,
            mac_address=dev.mac_address if dev else None,
            access_switch=switches.get(dev.connected_switch_id) if dev and dev.connected_switch_id else None,
            switch_interface=dev.connected_interface if dev else None,
            vlan_id=dev.vlan_id if dev else None,
            assignment_status=status,
        ))
    return rows


@router.post("/inventory/seed")
def run_inventory_seeder(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    summary = seed_campus_inventory(db)
    db.add(AuditLog(
        username=current_user.username,
        action="CAMPUS_INVENTORY_SEEDED",
        resource_type="CAMPUS_INVENTORY",
        resource_id="SEEDER",
        details=summary,
        status="SUCCESS",
    ))
    db.commit()
    return {"status": "seeded", **summary}
