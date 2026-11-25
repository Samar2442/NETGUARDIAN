from datetime import datetime, timezone
from typing import Dict, List
from sqlalchemy.orm import Session
from app.models import Device, Student, Faculty, ITPersonnel

# Deterministic fictional name pools (synthetic only, never real PII)
_FIRST_NAMES = [
    "Aarav", "Ananya", "Vihaan", "Diya", "Aditya", "Ishita", "Rohan", "Kavya",
    "Arjun", "Meera", "Kabir", "Neha", "Siddharth", "Priya", "Karan", "Riya",
    "Nikhil", "Sanya", "Varun", "Pooja", "Dev", "Tanvi", "Rahul", "Shreya",
    "Pranav", "Aditi", "Vivaan", "Nandini", "Harsh", "Aishwarya",
]
_LAST_NAMES = [
    "Sen", "Sharma", "Patel", "Nair", "Verma", "Iyer", "Mehta", "Reddy",
    "Kulkarni", "Das", "Gupta", "Joshi", "Rao", "Kapoor", "Menon", "Bhat",
    "Chauhan", "Malhotra", "Desai", "Sinha", "Bose", "Agarwal", "Kaur", "Mishra",
]


def _synthetic_name(seed_index: int) -> str:
    first = _FIRST_NAMES[seed_index % len(_FIRST_NAMES)]
    last = _LAST_NAMES[(seed_index // len(_FIRST_NAMES)) % len(_LAST_NAMES)]
    return f"{first} {last}"


def seed_campus_inventory(db: Session) -> Dict[str, int]:
    """
    Deterministic, idempotent Campus Personnel & Asset Assignment seeder.
    - Creates 250 synthetic students (80 CSE, 100 IT, 70 ECE) mapped 1-to-1 to existing endpoints.
    - Creates 16 synthetic faculty members (5 CSE, 6 IT, 5 ECE).
    - Creates 6 synthetic IT & Network personnel (not application login accounts).
    - Never duplicates or overwrites existing modified records.
    """
    devices_by_hostname: Dict[str, Device] = {
        d.hostname: d for d in db.query(Device).filter(Device.asset_category == "student_endpoint").all()
    }

    existing_students = {s.student_id for s in db.query(Student).all()}
    existing_faculty = {f.faculty_id for f in db.query(Faculty).all()}
    existing_it = {e.employee_id for e in db.query(ITPersonnel).all()}

    dept_specs = [
        ("CSE", 80, 0),
        ("IT", 100, 100),
        ("ECE", 70, 200),
    ]

    new_students: List[Student] = []
    missing_endpoints = 0
    now = datetime.now(timezone.utc)

    for dept, count, name_offset in dept_specs:
        for idx in range(1, count + 1):
            sid = f"{dept}2026{idx:03d}"
            if sid in existing_students:
                continue

            ep_hostname = f"{dept}-PC-{idx:03d}"
            ep = devices_by_hostname.get(ep_hostname)
            if not ep:
                missing_endpoints += 1

            year = ((idx - 1) % 4) + 1
            semester = (year - 1) * 2 + 1
            new_students.append(
                Student(
                    student_id=sid,
                    full_name=_synthetic_name(name_offset + idx),
                    department=dept,
                    academic_year=year,
                    semester=semester,
                    enrollment_status="ACTIVE",
                    email=f"{sid.lower()}@campus.example.invalid",
                    device_id=ep.id if ep else None,
                    enrollment_date=now,
                )
            )

    if new_students:
        db.add_all(new_students)
        db.commit()

    # 2. Seed 16 Faculty Members (5 CSE, 6 IT, 5 ECE)
    faculty_specs = [
        ("CSE", 5, "Block-A"),
        ("IT", 6, "Block-B"),
        ("ECE", 5, "Block-C"),
    ]
    designations = ["Professor", "Associate Professor", "Assistant Professor"]
    new_faculty: List[Faculty] = []
    fac_seq = 500
    for dept, count, block in faculty_specs:
        for idx in range(1, count + 1):
            fid = f"FAC-{dept}-{idx:03d}"
            if fid in existing_faculty:
                continue
            fac_seq += 1
            new_faculty.append(
                Faculty(
                    faculty_id=fid,
                    full_name=f"Dr. {_synthetic_name(fac_seq)}",
                    department=dept,
                    designation=designations[(idx - 1) % len(designations)],
                    email=f"{fid.lower()}@faculty.example.invalid",
                    employment_status="ACTIVE",
                    office_location=f"{block} Room {200 + idx}",
                )
            )

    if new_faculty:
        db.add_all(new_faculty)
        db.commit()

    # 3. Seed 6 IT & Network Personnel
    it_specs = [
        ("IT-EMP-001", "Vikramaditya Rao", "Network Administrator", "Core Infrastructure", "TIER-1-PRIVILEGED"),
        ("IT-EMP-002", "Nandini Kulkarni", "Network Engineer", "Campus Switching & Routing", "TIER-2-OPERATIONS"),
        ("IT-EMP-003", "Siddharth Menon", "Security Analyst", "Cyber Defense & IAM", "SECURITY-AUDIT"),
        ("IT-EMP-004", "Ananya Deshmukh", "System Administrator", "Compute & Directory Services", "TIER-2-OPERATIONS"),
        ("IT-EMP-005", "Rohan Chatterjee", "NOC Engineer", "24x7 Network Operations", "TIER-2-OPERATIONS"),
        ("IT-EMP-006", "Kavya Subramanian", "IT Support Engineer", "Departmental Endpoint Support", "SUPPORT"),
    ]
    new_it: List[ITPersonnel] = []
    for emp_id, name, title, team, cls in it_specs:
        if emp_id in existing_it:
            continue
        new_it.append(
            ITPersonnel(
                employee_id=emp_id,
                full_name=name,
                job_title=title,
                team=team,
                access_classification=cls,
                employment_status="ACTIVE",
                email=f"{emp_id.lower()}@noc.example.invalid",
            )
        )

    if new_it:
        db.add_all(new_it)
        db.commit()

    return {
        "students": db.query(Student).count(),
        "faculty": db.query(Faculty).count(),
        "it_personnel": db.query(ITPersonnel).count(),
        "missing_endpoints": missing_endpoints,
    }
