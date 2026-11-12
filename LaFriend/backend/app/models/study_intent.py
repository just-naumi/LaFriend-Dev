import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Date, Time
from sqlalchemy.orm import relationship
from app.database import Base

class StudyIntent(Base):
    __tablename__ = "study_intents"

    intent_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(String(36), ForeignKey("courses.course_id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Kebutuhan materi & tujuan (Day 3 specification)
    topics = Column(String(255), nullable=False) # e.g. "Binary Tree, BST, AVL Tree"
    learning_goal = Column(String(50), nullable=False) # UNDERSTAND, PRACTICE, EXAM_PREP, ASSIGNMENT, DISCUSSION
    collaboration_style = Column(String(50), nullable=False) # DISCUSSION, PRACTICE, TEACHING, FOCUS_STUDY
    learning_mode = Column(String(30), nullable=False, default="OFFLINE") # OFFLINE, ONLINE, HYBRID
    
    # Rentang tanggal
    earliest_date = Column(String(10), nullable=False) # YYYY-MM-DD
    latest_date = Column(String(10), nullable=False)   # YYYY-MM-DD
    
    # Ukuran kelompok
    min_group_size = Column(Integer, nullable=False, default=2)
    max_group_size = Column(Integer, nullable=False, default=4)
    
    # Lifecycle status
    status = Column(String(30), nullable=False, default="ACTIVE") # ACTIVE, GROUP_FORMING, JOIN_PENDING, CONVERTED, CANCELLED, EXPIRED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    student = relationship("Student", back_populates="intents")
    course = relationship("Course", back_populates="intents")
    availabilities = relationship("IntentAvailability", back_populates="intent", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StudyIntent {self.intent_id} - Course {self.course_id} - Status {self.status}>"


class IntentAvailability(Base):
    __tablename__ = "intent_availabilities"

    availability_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    intent_id = Column(String(36), ForeignKey("study_intents.intent_id", ondelete="CASCADE"), nullable=False, index=True)
    
    day_or_date = Column(String(30), nullable=False) # e.g. "Wednesday" or "2026-11-18"
    start_time = Column(String(10), nullable=False)  # e.g. "09:00"
    end_time = Column(String(10), nullable=False)    # e.g. "12:00"
    priority_rank = Column(Integer, nullable=False, default=1) # 1, 2, 3...

    intent = relationship("StudyIntent", back_populates="availabilities")

    def __repr__(self):
        return f"<IntentAvailability {self.day_or_date} {self.start_time}-{self.end_time} (P{self.priority_rank})>"

