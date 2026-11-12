import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base

class Course(Base):
    __tablename__ = "courses"

    course_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_code = Column(String(20), unique=True, nullable=False, index=True)
    course_name = Column(String(100), nullable=False, index=True)
    study_program = Column(String(100), nullable=False, default="S1 Teknik Komputer")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    intents = relationship("StudyIntent", back_populates="course")

    def __repr__(self):
        return f"<Course {self.course_code} - {self.course_name}>"
