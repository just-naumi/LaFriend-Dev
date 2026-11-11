import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

class StudentBase(BaseModel):
    full_name: str
    email: str
    student_number: str
    study_program: str = "S1 Teknik Komputer"
    academic_year: int = 2025
    is_discoverable: bool = True

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if not EMAIL_REGEX.match(v_clean):
            raise ValueError("Format email tidak valid")
        return v_clean

class StudentRegister(StudentBase):
    password: str

class StudentLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        return v.strip().lower()

class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    study_program: Optional[str] = None
    academic_year: Optional[int] = None
    is_discoverable: Optional[bool] = None

class StudentResponse(StudentBase):
    student_id: str
    verification_status: str
    account_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student: StudentResponse
