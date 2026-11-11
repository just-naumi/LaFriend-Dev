import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base

class Student(Base):
    __tablename__ = "students"

    student_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    student_number = Column(String(30), unique=True, nullable=False, index=True) # NIM
    study_program = Column(String(100), nullable=False, default="S1 Teknik Komputer")
    academic_year = Column(Integer, nullable=False, default=2025)
    password_hash = Column(String(255), nullable=False)
    
    verification_status = Column(String(20), nullable=False, default="VERIFIED") # VERIFIED, PENDING
    account_status = Column(String(20), nullable=False, default="ACTIVE")        # ACTIVE, RESTRICTED
    is_discoverable = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    intents = relationship("StudyIntent", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student {self.student_number} - {self.full_name}>"
