from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.study_intent import StudyIntent, IntentAvailability
from app.models.course import Course
from app.models.student import Student
from app.schemas.study_intent import StudyIntentCreate, StudyIntentUpdate

class StudyIntentService:

    @staticmethod
    def create_intent(db: Session, student_id: str, data: StudyIntentCreate) -> StudyIntent:
        # 1. Pastikan mahasiswa terdaftar dan aktif
        student = db.query(Student).filter(Student.student_id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mahasiswa tidak ditemukan"
            )
        if student.account_status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun mahasiswa dibatasi, tidak dapat membuat Study Intent"
            )

        # 2. Pastikan mata kuliah terdaftar
        course = db.query(Course).filter(Course.course_id == data.course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mata kuliah tidak ditemukan di katalog resmi"
            )

        # 3. Buat StudyIntent
        new_intent = StudyIntent(
            student_id=student_id,
            course_id=data.course_id,
            topics=data.topics.strip(),
            learning_goal=data.learning_goal,
            collaboration_style=data.collaboration_style,
            learning_mode=data.learning_mode,
            earliest_date=data.earliest_date,
            latest_date=data.latest_date,
            min_group_size=data.min_group_size,
            max_group_size=data.max_group_size,
            status="ACTIVE"
        )
        db.add(new_intent)
        db.flush() # Mendapatkan new_intent.intent_id

        # 4. Tambahkan slot ketersediaan (availabilities)
        for slot in data.availabilities:
            avail = IntentAvailability(
                intent_id=new_intent.intent_id,
                day_or_date=slot.day_or_date,
                start_time=slot.start_time,
                end_time=slot.end_time,
                priority_rank=slot.priority_rank
            )
            db.add(avail)

        db.commit()
        db.refresh(new_intent)
        return new_intent

    @staticmethod
    def get_student_intents(db: Session, student_id: str) -> List[StudyIntent]:
        return (
            db.query(StudyIntent)
            .filter(StudyIntent.student_id == student_id)
            .order_by(StudyIntent.created_at.desc())
            .all()
        )

    @staticmethod
    def get_intent_by_id(db: Session, intent_id: str) -> StudyIntent:
        intent = db.query(StudyIntent).filter(StudyIntent.intent_id == intent_id).first()
        if not intent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Study Intent tidak ditemukan"
            )
        return intent

    @staticmethod
    def update_intent(db: Session, intent_id: str, student_id: str, data: StudyIntentUpdate) -> StudyIntent:
        intent = StudyIntentService.get_intent_by_id(db, intent_id)
        if intent.student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak memiliki hak untuk mengubah Study Intent ini"
            )
        if intent.status in ["CONVERTED", "CANCELLED", "EXPIRED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Study Intent dengan status {intent.status} tidak dapat diubah"
            )

        update_dict = data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            if val is not None:
                setattr(intent, key, val)

        db.commit()
        db.refresh(intent)
        return intent

    @staticmethod
    def cancel_intent(db: Session, intent_id: str, student_id: str) -> StudyIntent:
        intent = StudyIntentService.get_intent_by_id(db, intent_id)
        if intent.student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak memiliki hak untuk membatalkan Study Intent ini"
            )
        if intent.status in ["CONVERTED", "CANCELLED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Study Intent sudah {intent.status}"
            )

        intent.status = "CANCELLED"
        db.commit()
        db.refresh(intent)
        return intent

