import ipaddress
from collections import defaultdict
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.models import Device, Faculty, ITPersonnel, Student, VLAN

DEPT_VLAN_MAP = {"CSE": 10, "IT": 20, "ECE": 30}
VALID_ENROLLMENT_STATUSES = {"ACTIVE", "PROBATION", "GRADUATED", "SUSPENDED"}
VALID_PERSONNEL_STATUSES = {"ACTIVE", "ON_LEAVE", "SABBATICAL", "ON_CALL", "INACTIVE"}


class InventoryValidationEngine:
    """
    Read-only Campus Personnel & Asset Assignment Validation Engine.
    Detects missing records, duplicate IDs/emails, unassigned or shared endpoints,
    department/VLAN/IP mismatches, and invalid status values.
    """

    @staticmethod
    def validate_inventory(db: Session) -> Dict[str, Any]:
        issues: List[Dict[str, Any]] = []
        total_checks = 15
        failed_checks = set()

        students = db.query(Student).all()
        faculty = db.query(Faculty).all()
        it_staff = db.query(ITPersonnel).all()
        devices = db.query(Device).all()
        vlans = db.query(VLAN).all()

        device_by_id = {d.id: d for d in devices}
        vlan_by_id = {v.vlan_id: v for v in vlans}
        parsed_nets = {}
        for v in vlans:
            try:
                parsed_nets[v.vlan_id] = ipaddress.ip_network(v.subnet, strict=False)
            except ValueError:
                pass

        # 1. Missing student records (expect 250)
        if len(students) < 250:
            failed_checks.add("MISSING_STUDENTS")
            issues.append({
                "severity": "WARNING",
                "code": "MISSING_STUDENTS",
                "message": f"Expected 250 student records, found {len(students)}.",
                "resource": "students",
            })

        # 2-4. Duplicate IDs
        sid_counts: Dict[str, int] = defaultdict(int)
        for s in students:
            sid_counts[s.student_id] += 1
        for sid, cnt in sid_counts.items():
            if cnt > 1:
                failed_checks.add("DUPLICATE_STUDENT_ID")
                issues.append({"severity": "CRITICAL", "code": "DUPLICATE_STUDENT_ID", "message": f"Duplicate student_id '{sid}'", "resource": sid})

        fid_counts: Dict[str, int] = defaultdict(int)
        for f in faculty:
            fid_counts[f.faculty_id] += 1
        for fid, cnt in fid_counts.items():
            if cnt > 1:
                failed_checks.add("DUPLICATE_FACULTY_ID")
                issues.append({"severity": "CRITICAL", "code": "DUPLICATE_FACULTY_ID", "message": f"Duplicate faculty_id '{fid}'", "resource": fid})

        eid_counts: Dict[str, int] = defaultdict(int)
        for e in it_staff:
            eid_counts[e.employee_id] += 1
        for eid, cnt in eid_counts.items():
            if cnt > 1:
                failed_checks.add("DUPLICATE_EMPLOYEE_ID")
                issues.append({"severity": "CRITICAL", "code": "DUPLICATE_EMPLOYEE_ID", "message": f"Duplicate employee_id '{eid}'", "resource": eid})

        # 5. Duplicate synthetic emails across personnel
        email_owners: Dict[str, List[str]] = defaultdict(list)
        for s in students:
            email_owners[s.email.lower()].append(s.student_id)
        for f in faculty:
            email_owners[f.email.lower()].append(f.faculty_id)
        for e in it_staff:
            email_owners[e.email.lower()].append(e.employee_id)
        for em, owners in email_owners.items():
            if len(owners) > 1:
                failed_checks.add("DUPLICATE_EMAIL")
                issues.append({"severity": "CRITICAL", "code": "DUPLICATE_EMAIL", "message": f"Duplicate email '{em}' across {owners}", "resource": em})

        # 6-14. Student-to-endpoint & consistency checks
        device_assignments: Dict[str, List[str]] = defaultdict(list)
        for s in students:
            if s.enrollment_status not in VALID_ENROLLMENT_STATUSES:
                failed_checks.add("INVALID_ENROLLMENT_STATUS")
                issues.append({"severity": "CRITICAL", "code": "INVALID_ENROLLMENT_STATUS", "message": f"Student {s.student_id} has invalid status '{s.enrollment_status}'", "resource": s.student_id})

            if not s.device_id:
                failed_checks.add("UNASSIGNED_STUDENT_ENDPOINT")
                issues.append({"severity": "CRITICAL", "code": "UNASSIGNED_STUDENT_ENDPOINT", "message": f"Student {s.student_id} has no assigned endpoint.", "resource": s.student_id})
                continue

            device_assignments[s.device_id].append(s.student_id)
            dev = device_by_id.get(s.device_id)
            if not dev:
                failed_checks.add("INVALID_DEVICE_REFERENCE")
                issues.append({"severity": "CRITICAL", "code": "INVALID_DEVICE_REFERENCE", "message": f"Student {s.student_id} references nonexistent device '{s.device_id}'.", "resource": s.student_id})
                continue

            if dev.department != s.department:
                failed_checks.add("DEPARTMENT_MISMATCH")
                issues.append({"severity": "CRITICAL", "code": "DEPARTMENT_MISMATCH", "message": f"Student {s.student_id} ({s.department}) assigned to {dev.hostname} ({dev.department}).", "resource": s.student_id})

            expected_vlan = DEPT_VLAN_MAP.get(s.department)
            if dev.vlan_id not in vlan_by_id:
                failed_checks.add("INVALID_VLAN_REFERENCE")
                issues.append({"severity": "CRITICAL", "code": "INVALID_VLAN_REFERENCE", "message": f"Device {dev.hostname} references invalid VLAN {dev.vlan_id}.", "resource": dev.hostname})
            elif expected_vlan and dev.vlan_id != expected_vlan:
                failed_checks.add("VLAN_MISMATCH")
                issues.append({"severity": "CRITICAL", "code": "VLAN_MISMATCH", "message": f"Student {s.student_id} ({s.department}) expects VLAN {expected_vlan}, got {dev.vlan_id}.", "resource": s.student_id})

            if dev.vlan_id in parsed_nets and dev.management_ip:
                try:
                    if ipaddress.ip_address(dev.management_ip) not in parsed_nets[dev.vlan_id]:
                        failed_checks.add("INCONSISTENT_IP_ASSIGNMENT")
                        issues.append({"severity": "CRITICAL", "code": "INCONSISTENT_IP_ASSIGNMENT", "message": f"Device {dev.hostname} IP {dev.management_ip} outside VLAN {dev.vlan_id} subnet.", "resource": dev.hostname})
                except ValueError:
                    failed_checks.add("INCONSISTENT_IP_ASSIGNMENT")
                    issues.append({"severity": "CRITICAL", "code": "INCONSISTENT_IP_ASSIGNMENT", "message": f"Device {dev.hostname} has invalid IP '{dev.management_ip}'.", "resource": dev.hostname})

        for did, sids in device_assignments.items():
            if len(sids) > 1:
                failed_checks.add("DUPLICATE_ENDPOINT_ASSIGNMENT")
                issues.append({"severity": "CRITICAL", "code": "DUPLICATE_ENDPOINT_ASSIGNMENT", "message": f"Endpoint '{did}' assigned to multiple students: {sids}.", "resource": did})

        # 10. Missing endpoint devices check
        student_eps = [d for d in devices if d.asset_category == "student_endpoint"]
        if len(student_eps) < 250:
            failed_checks.add("MISSING_ENDPOINT_DEVICES")
            issues.append({"severity": "WARNING", "code": "MISSING_ENDPOINT_DEVICES", "message": f"Expected 250 student endpoints, found {len(student_eps)}.", "resource": "devices"})

        # 15. Personnel status checks
        for f in faculty:
            if f.employment_status not in VALID_PERSONNEL_STATUSES:
                failed_checks.add("INVALID_PERSONNEL_STATUS")
                issues.append({"severity": "CRITICAL", "code": "INVALID_PERSONNEL_STATUS", "message": f"Faculty {f.faculty_id} has invalid status '{f.employment_status}'", "resource": f.faculty_id})
        for e in it_staff:
            if e.employment_status not in VALID_PERSONNEL_STATUSES:
                failed_checks.add("INVALID_PERSONNEL_STATUS")
                issues.append({"severity": "CRITICAL", "code": "INVALID_PERSONNEL_STATUS", "message": f"IT employee {e.employee_id} has invalid status '{e.employment_status}'", "resource": e.employee_id})

        critical_errors = sum(1 for i in issues if i["severity"] == "CRITICAL")
        warnings = sum(1 for i in issues if i["severity"] == "WARNING")
        failed_count = len(failed_checks)

        return {
            "valid": critical_errors == 0 and warnings == 0,
            "total_checks": total_checks,
            "passed_checks": max(0, total_checks - failed_count),
            "failed_checks": failed_count,
            "critical_errors": critical_errors,
            "warnings": warnings,
            "issues": issues,
        }
