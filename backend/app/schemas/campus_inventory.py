from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_DEPARTMENTS = {"CSE", "IT", "ECE"}
VALID_ENROLLMENT_STATUSES = {"ACTIVE", "PROBATION", "GRADUATED", "SUSPENDED"}
VALID_PERSONNEL_STATUSES = {"ACTIVE", "ON_LEAVE", "SABBATICAL", "ON_CALL", "INACTIVE"}


class StudentBase(BaseModel):
    student_id: str = Field(..., min_length=3, max_length=32)
    full_name: str = Field(..., min_length=2, max_length=120)
    department: str
    academic_year: int = Field(default=1, ge=1, le=5)
    semester: int = Field(default=1, ge=1, le=10)
    enrollment_status: str = "ACTIVE"
    email: str = Field(..., min_length=5, max_length=150)
    device_id: Optional[str] = None

    @field_validator("department")
    @classmethod
    def check_department(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in VALID_DEPARTMENTS:
            raise ValueError(f"Department must be one of {sorted(VALID_DEPARTMENTS)}")
        return val

    @field_validator("enrollment_status")
    @classmethod
    def check_status(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in VALID_ENROLLMENT_STATUSES:
            raise ValueError(f"Enrollment status must be one of {sorted(VALID_ENROLLMENT_STATUSES)}")
        return val

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        val = v.strip().lower()
        if "@" not in val or "." not in val.split("@")[-1]:
            raise ValueError("Invalid email address format")
        return val


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    academic_year: Optional[int] = Field(default=None, ge=1, le=5)
    semester: Optional[int] = Field(default=None, ge=1, le=10)
    enrollment_status: Optional[str] = None
    device_id: Optional[str] = None

    @field_validator("enrollment_status")
    @classmethod
    def check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        val = v.strip().upper()
        if val not in VALID_ENROLLMENT_STATUSES:
            raise ValueError(f"Enrollment status must be one of {sorted(VALID_ENROLLMENT_STATUSES)}")
        return val


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_id: str
    full_name: str
    department: str
    academic_year: int
    semester: int
    enrollment_status: str
    email: str
    device_id: Optional[str] = None
    assigned_device: Optional[str] = None
    assigned_vlan: Optional[int] = None
    assigned_ip: Optional[str] = None
    enrollment_date: datetime
    created_at: datetime
    updated_at: datetime


class StudentNetworkResponse(BaseModel):
    student_id: str
    full_name: str
    department: str
    enrollment_status: str
    endpoint_hostname: str
    mac_address: Optional[str] = None
    ip_address: str
    vlan_id: Optional[int] = None
    connected_switch: Optional[str] = None
    connected_interface: Optional[str] = None
    operational_status: str
    status_source: str = "SIMULATED_INVENTORY"
    link_name: Optional[str] = None
    link_status: Optional[str] = None
    link_speed_mbps: Optional[int] = None


class FacultyBase(BaseModel):
    faculty_id: str = Field(..., min_length=3, max_length=32)
    full_name: str = Field(..., min_length=2, max_length=120)
    department: str
    designation: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., min_length=5, max_length=150)
    employment_status: str = "ACTIVE"
    office_location: str = Field(..., min_length=2, max_length=100)

    @field_validator("department")
    @classmethod
    def check_department(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in VALID_DEPARTMENTS:
            raise ValueError(f"Department must be one of {sorted(VALID_DEPARTMENTS)}")
        return val

    @field_validator("employment_status")
    @classmethod
    def check_status(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in VALID_PERSONNEL_STATUSES:
            raise ValueError(f"Employment status must be one of {sorted(VALID_PERSONNEL_STATUSES)}")
        return val


class FacultyCreate(FacultyBase):
    pass


class FacultyUpdate(BaseModel):
    full_name: Optional[str] = None
    designation: Optional[str] = None
    employment_status: Optional[str] = None
    office_location: Optional[str] = None


class FacultyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    faculty_id: str
    full_name: str
    department: str
    designation: str
    email: str
    employment_status: str
    office_location: str
    created_at: datetime
    updated_at: datetime


class ITPersonnelBase(BaseModel):
    employee_id: str = Field(..., min_length=3, max_length=32)
    full_name: str = Field(..., min_length=2, max_length=120)
    job_title: str = Field(..., min_length=2, max_length=80)
    team: str = Field(..., min_length=2, max_length=60)
    access_classification: str = Field(..., min_length=2, max_length=40)
    employment_status: str = "ACTIVE"
    email: str = Field(..., min_length=5, max_length=150)


class ITPersonnelCreate(ITPersonnelBase):
    pass


class ITPersonnelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    employee_id: str
    full_name: str
    job_title: str
    team: str
    access_classification: str
    employment_status: str
    email: str
    created_at: datetime
    updated_at: datetime


class InventoryOverviewResponse(BaseModel):
    total_students: int
    students_by_department: Dict[str, int]
    total_faculty: int
    faculty_by_department: Dict[str, int]
    total_it_personnel: int
    assigned_endpoints: int
    unassigned_students: int
    invalid_associations: int
    assignment_coverage_pct: float
    inventory_health: str
    validation_valid: bool


class InventoryValidationResponse(BaseModel):
    valid: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    critical_errors: int
    warnings: int
    issues: List[Dict[str, Any]]


class AssetAssignmentRow(BaseModel):
    student_id: str
    student_name: str
    department: str
    endpoint_hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    access_switch: Optional[str] = None
    switch_interface: Optional[str] = None
    vlan_id: Optional[int] = None
    assignment_status: Literal["ASSIGNED", "UNASSIGNED", "INVALID_ASSIGNMENT", "DEPARTMENT_MISMATCH"]
