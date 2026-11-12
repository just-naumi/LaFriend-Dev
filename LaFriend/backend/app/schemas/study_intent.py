from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.course import CourseResponse

LearningGoal = Literal["UNDERSTAND", "PRACTICE", "EXAM_PREP", "ASSIGNMENT", "DISCUSSION"]
CollaborationStyle = Literal["DISCUSSION", "PRACTICE", "TEACHING", "FOCUS_STUDY"]
LearningMode = Literal["OFFLINE", "ONLINE", "HYBRID"]
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"  # HH:MM dua digit, supaya urutan teks sama dengan urutan jam

# Nama hari ke nomor hari (Senin = 0), dipakai juga oleh Fitur 1 untuk mencari tanggalnya
WEEKDAYS = {
    "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3, "jumat": 4, "sabtu": 5, "minggu": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}


def _iso_date(v: str) -> str:
    try:
        return date.fromisoformat(v.strip()).isoformat()
    except ValueError:
        raise ValueError(f"Tanggal ({v}) harus berformat YYYY-MM-DD")

class AvailabilityBase(BaseModel):
    day_or_date: str
    start_time: str = Field(pattern=TIME_PATTERN) # HH:MM
    end_time: str = Field(pattern=TIME_PATTERN)   # HH:MM
    priority_rank: int = Field(default=1, ge=1)

    @field_validator("day_or_date")
    @classmethod
    def validate_day_or_date(cls, v: str) -> str:
        v_clean = v.strip()
        if v_clean.casefold() in WEEKDAYS:
            return v_clean
        try:
            return _iso_date(v_clean)
        except ValueError:
            raise ValueError(f"Hari ({v}) harus nama hari atau tanggal berformat YYYY-MM-DD")

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
    learning_goal: LearningGoal
    collaboration_style: CollaborationStyle
    learning_mode: LearningMode = "OFFLINE"
    earliest_date: str # YYYY-MM-DD
    latest_date: str   # YYYY-MM-DD
    min_group_size: int = Field(default=2, ge=2, le=4)
    max_group_size: int = Field(default=4, ge=2, le=4)
    availabilities: List[AvailabilityCreate]

    @field_validator("earliest_date", "latest_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        return _iso_date(v)

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
    learning_goal: Optional[LearningGoal] = None
    collaboration_style: Optional[CollaborationStyle] = None
    learning_mode: Optional[LearningMode] = None
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    min_group_size: Optional[int] = Field(default=None, ge=2, le=4)
    max_group_size: Optional[int] = Field(default=None, ge=2, le=4)

    @field_validator("earliest_date", "latest_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        return _iso_date(v) if v is not None else None


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

