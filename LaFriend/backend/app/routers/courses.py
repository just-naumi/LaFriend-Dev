from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.course import Course
from app.schemas.course import CourseResponse

router = APIRouter(prefix="/courses", tags=["Courses"])

@router.get("", response_model=List[CourseResponse])
def get_courses(db: Session = Depends(get_db)):
    """Mengambil daftar seluruh mata kuliah resmi."""
    return db.query(Course).order_by(Course.course_code.asc()).all()

@router.get("/{course_id}", response_model=CourseResponse)
def get_course_detail(course_id: str, db: Session = Depends(get_db)):
    """Mengambil detail satu mata kuliah."""
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Mata kuliah tidak ditemukan")
    return course

