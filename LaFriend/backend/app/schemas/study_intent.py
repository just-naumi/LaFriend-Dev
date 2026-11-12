from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator
from app.schemas.course import CourseResponse

class AvailabilityBase(BaseModel):
    day_or_date: str
    start_time: str # HH:MM
    end_time: str   # HH:MM
    priority_rank: int = 1

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v: str, info) -> str:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError(f"Waktu selesai ({v}) harus lebih besar daripada waktu mulai ({start})")
        return v

class AvailabilityCreate(AvailabilityBase):
    pass

class AvailabilityResponse(AvailabilityBase):
    availability_id: str
    intent_id: str

    model_config = ConfigDict(from_attributes=True)


class StudyIntentCreate(BaseModel):
    course_id: str
    topics: str
    learning_goal: str # UNDERSTAND, PRACTICE, EXAM_PREP, ASSIGNMENT, DISCUSSION
    collaboration_style: str # DISCUSSION, PRACTICE, TEACHING, FOCUS_STUDY
    learning_mode: str = "OFFLINE" # OFFLINE, ONLINE, HYBRID
    earliest_date: str # YYYY-MM-DD
    latest_date: str   # YYYY-MM-DD
    min_group_size: int = 2
    max_group_size: int = 4
    availabilities: List[AvailabilityCreate]

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("Materi atau topik belajar tidak boleh kosong")
        return v_clean

    @field_validator("latest_date")
    @classmethod
    def validate_date_range(cls, v: str, info) -> str:
        earliest = info.data.get("earliest_date")
        if earliest and v < earliest:
            raise ValueError(f"Batas tanggal akhir ({v}) tidak boleh mendahului tanggal awal ({earliest})")
        return v

    @field_validator("max_group_size")
    @classmethod
    def validate_group_size(cls, v: int, info) -> int:
        min_size = info.data.get("min_group_size", 2)
        if v < min_size:
            raise ValueError(f"Kapasitas maksimum ({v}) tidak boleh lebih kecil dari minimum ({min_size})")
        return v

    @field_validator("availabilities")
    @classmethod
    def validate_availabilities_not_empty(cls, v: List[AvailabilityCreate]) -> List[AvailabilityCreate]:
        if not v or len(v) == 0:
            raise ValueError("Minimal harus menyertakan 1 slot waktu ketersediaan belajar")
        return v


class StudyIntentUpdate(BaseModel):
    topics: Optional[str] = None
    learning_goal: Optional[str] = None
    collaboration_style: Optional[str] = None
    learning_mode: Optional[str] = None
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    min_group_size: Optional[int] = None
    max_group_size: Optional[int] = None


class StudyIntentResponse(BaseModel):
    intent_id: str
    student_id: str
    course_id: str
    topics: str
    learning_goal: str
    collaboration_style: str
    learning_mode: str
    earliest_date: str
    latest_date: str
    min_group_size: int
    max_group_size: int
    status: str
    created_at: datetime
    
    course: Optional[CourseResponse] = None
    availabilities: List[AvailabilityResponse] = []

    model_config = ConfigDict(from_attributes=True)

