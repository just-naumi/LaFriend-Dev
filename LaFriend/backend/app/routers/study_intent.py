from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.student import Student
from app.schemas.study_intent import (
    StudyIntentCreate, StudyIntentUpdate, StudyIntentResponse
)
from app.services.study_intent import StudyIntentService
from app.api.v1.auth import get_current_student

router = APIRouter(prefix="/study-intents", tags=["Study Intents"])

@router.post("", response_model=StudyIntentResponse, status_code=status.HTTP_201_CREATED)
def create_study_intent(
    data: StudyIntentCreate,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Membuat Study Intent baru lengkap dengan slot ketersediaan waktu."""
    return StudyIntentService.create_intent(db, current_student.student_id, data)

@router.get("", response_model=List[StudyIntentResponse])
def get_my_study_intents(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Melihat seluruh daftar Study Intent milik pengguna yang sedang login."""
    return StudyIntentService.get_student_intents(db, current_student.student_id)

@router.get("/{intent_id}", response_model=StudyIntentResponse)
def get_study_intent_detail(
    intent_id: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Melihat detail satu Study Intent."""
    return StudyIntentService.get_intent_by_id(db, intent_id)

@router.patch("/{intent_id}", response_model=StudyIntentResponse)
def update_study_intent(
    intent_id: str,
    data: StudyIntentUpdate,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Mengubah informasi kebutuhan belajar pada Study Intent."""
    return StudyIntentService.update_intent(db, intent_id, current_student.student_id, data)

@router.patch("/{intent_id}/cancel", response_model=StudyIntentResponse)
def cancel_study_intent(
    intent_id: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Membatalkan Study Intent."""
    return StudyIntentService.cancel_intent(db, intent_id, current_student.student_id)

