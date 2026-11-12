from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.student import Student
from app.schemas.student import (
    StudentRegister, StudentLogin, StudentUpdate,
    StudentResponse, TokenResponse
)
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["Authentication & Student Profile"])

def get_current_student(authorization: str = Header(None), db: Session = Depends(get_db)) -> Student:
    """Helper dependency to extract and authenticate current student via Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token otentikasi tidak valid atau tidak disediakan"
        )
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token kedaluwarsa atau tidak valid"
        )
    student_id = payload["sub"]
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pengguna mahasiswa tidak ditemukan"
        )
    if student.account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa dibatasi atau tidak aktif"
        )
    return student

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_student(data: StudentRegister, db: Session = Depends(get_db)):
    """Mendaftarkan akun mahasiswa baru."""
    # Cek duplikasi email
    if db.query(Student).filter(Student.email == data.email.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email kampus sudah terdaftar"
        )
    # Cek duplikasi NIM
    if db.query(Student).filter(Student.student_number == data.student_number).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NIM mahasiswa sudah terdaftar"
        )

    student = Student(
        full_name=data.full_name,
        email=data.email.lower(),
        student_number=data.student_number,
        study_program=data.study_program,
        academic_year=data.academic_year,
        password_hash=hash_password(data.password),
        verification_status="VERIFIED",
        account_status="ACTIVE",
        is_discoverable=data.is_discoverable
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    token = create_access_token(data={"sub": student.student_id, "email": student.email})
    return TokenResponse(
        access_token=token,
        student=StudentResponse.model_validate(student)
    )

@router.post("/login", response_model=TokenResponse)
def login_student(data: StudentLogin, db: Session = Depends(get_db)):
    """Autentikasi login mahasiswa."""
    student = db.query(Student).filter(Student.email == data.email.lower()).first()
    if not student or not verify_password(data.password, student.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email kampus atau password salah"
        )

    if student.account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun dibatasi atau tidak aktif. Hubungi administrator."
        )

    token = create_access_token(data={"sub": student.student_id, "email": student.email})
    return TokenResponse(
        access_token=token,
        student=StudentResponse.model_validate(student)
    )

@router.get("/me", response_model=StudentResponse)
def get_current_user_profile(current_student: Student = Depends(get_current_student)):
    """Mengambil informasi profil mahasiswa aktif."""
    return current_student

@router.put("/profile", response_model=StudentResponse)
def update_profile(
    data: StudentUpdate,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Memperbarui informasi profil mahasiswa."""
    if data.full_name is not None:
        current_student.full_name = data.full_name
    if data.study_program is not None:
        current_student.study_program = data.study_program
    if data.academic_year is not None:
        current_student.academic_year = data.academic_year
    if data.is_discoverable is not None:
        current_student.is_discoverable = data.is_discoverable

    db.commit()
    db.refresh(current_student)
    return current_student

