# ==============================================================================
# schemas.py - Skema Validasi Data API (Pydantic)
# ==============================================================================
# File ini bertugas untuk:
# 1. Memvalidasi data yang dikirimkan oleh browser (Frontend) ke server.
# 2. Mengatur format data balasan (Response) yang dikirimkan server ke Frontend.
# Jika ada data yang tidak sesuai (misalnya email salah format atau kolom kosong),
# Pydantic otomatis menolak dan memberikan pesan error yang jelas.
# ==============================================================================

import re
from datetime import date, datetime
from typing import Dict, List, Literal, Optional, Any, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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



# ==============================================================================
# 1. SKEMA UNTUK AUTENTIKASI & MAHASISWA
# ==============================================================================

# Data yang harus dikirim saat mahasiswa baru mendaftar
class StudentRegister(BaseModel):
    full_name: str
    email: str
    student_number: str
    study_program: str = "S1 Teknik Komputer"
    academic_year: int = 2025
    password: str
    is_discoverable: bool = True

    # Validasi sederhana: pastikan email menggunakan format email yang wajar
    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        clean_email = value.strip().lower()
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", clean_email):
            raise ValueError("Format email tidak valid. Gunakan format nama@domain.com")
        return clean_email

    # Validasi password: minimal 6 karakter agar aman
    @field_validator("password")
    @classmethod
    def validate_password_length(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("Password minimal terdiri dari 6 karakter")
        return value


# Data yang harus dikirim saat mahasiswa login
class StudentLogin(BaseModel):
    email: str
    password: str


# Format data profil mahasiswa yang boleh dilihat oleh Frontend (tanpa password!)
class StudentResponse(BaseModel):
    student_id: str
    full_name: str
    email: str
    student_number: str
    study_program: str
    academic_year: int
    verification_status: str
    account_status: str
    is_discoverable: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Format balasan saat login / register berhasil (mengembalikan token akses)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student: StudentResponse


# ==============================================================================
# 2. SKEMA UNTUK MATA KULIAH
# ==============================================================================

# Format data balasan untuk daftar mata kuliah resmi
class CourseResponse(BaseModel):
    course_id: str
    course_code: str
    course_name: str
    study_program: str

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. SKEMA UNTUK STUDY INTENT & JADWAL KETERSEDIAAN
# ==============================================================================

# Data satu baris slot waktu ketersediaan yang dikirim dari form Frontend
class AvailabilityCreate(BaseModel):
    day_or_date: str          # Contoh: "Rabu" atau "2026-11-18"
    start_time: str = Field(pattern=TIME_PATTERN)  # Contoh: "09:00"
    end_time: str = Field(pattern=TIME_PATTERN)    # Contoh: "12:00"
    priority_rank: int = Field(default=1, ge=1)    # 1 = Utama, 2 = Cadangan, 3 = Fleksibel

    # Validasi (Fitur 1): hari harus nama hari atau tanggal, jam selesai harus setelah jam mulai
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

    @model_validator(mode="after")
    def validate_time_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("Jam selesai harus setelah jam mulai")
        return self


# Format balasan data slot waktu ketersediaan yang tersimpan di database
class AvailabilityResponse(BaseModel):
    availability_id: str
    day_or_date: str
    start_time: str
    end_time: str
    priority_rank: int

    model_config = ConfigDict(from_attributes=True)


# Data lengkap yang dikirim mahasiswa saat menekan tombol "Create Study Intent"
# CATATAN DAY 11.1: Tidak ada default palsu pada proses penyimpanan!
# Semua field wajib (goal, style, mode, dates) harus eksplisit dipilih/dikonfirmasi oleh pengguna.
class StudyIntentCreate(BaseModel):
    course_id: str
    topics: str
    learning_goal: str          # Wajib dipilih pengguna (UNDERSTAND, PRACTICE, EXAM_PREP, ASSIGNMENT, DISCUSSION, KNOWLEDGE_SHARING)
    collaboration_style: str    # Wajib dipilih pengguna (DISCUSSION, PRACTICE, TEACHING, FOCUS_STUDY)
    learning_mode: str          # Wajib dipilih pengguna (OFFLINE, ONLINE, HYBRID)
    earliest_date: str          # Wajib ditentukan pengguna (YYYY-MM-DD)
    latest_date: str            # Wajib ditentukan pengguna (YYYY-MM-DD)
    min_group_size: int = Field(default=2, ge=2, le=4)
    max_group_size: int = Field(default=4, ge=2, le=4)
    availabilities: List[AvailabilityCreate]

    # Validasi: course_id tidak boleh kosong
    @field_validator("course_id")
    @classmethod
    def validate_course_id(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Mata kuliah wajib dipilih")
        return value.strip()

    # Validasi: topik tidak boleh kosong
    @field_validator("topics")
    @classmethod
    def validate_topics_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Topik yang ingin dipelajari tidak boleh kosong")
        return value.strip()

    # Validasi: learning_goal wajib bernilai valid
    @field_validator("learning_goal")
    @classmethod
    def validate_learning_goal(cls, value: str) -> str:
        valid_goals = {"UNDERSTAND", "PRACTICE", "EXAM_PREP", "ASSIGNMENT", "DISCUSSION", "KNOWLEDGE_SHARING"}
        clean = (value or "").strip().upper()
        if clean not in valid_goals:
            raise ValueError(f"learning_goal '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_goals))}")
        return clean

    # Validasi: collaboration_style wajib bernilai valid
    @field_validator("collaboration_style")
    @classmethod
    def validate_collaboration_style(cls, value: str) -> str:
        valid_styles = {"DISCUSSION", "PRACTICE", "TEACHING", "FOCUS_STUDY"}
        clean = (value or "").strip().upper()
        if clean not in valid_styles:
            raise ValueError(f"collaboration_style '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_styles))}")
        return clean

    # Validasi: learning_mode wajib bernilai valid (OFFLINE, ONLINE, HYBRID)
    @field_validator("learning_mode")
    @classmethod
    def validate_learning_mode(cls, value: str) -> str:
        valid_modes = {"OFFLINE", "ONLINE", "HYBRID"}
        clean = (value or "").strip().upper()
        if clean not in valid_modes:
            raise ValueError(f"learning_mode '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_modes))}")
        return clean

    # Validasi: tanggal awal dan akhir harus diisi
    @field_validator("earliest_date", "latest_date")
    @classmethod
    def validate_dates(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Rentang tanggal sesi belajar wajib ditentukan")
        return _iso_date(value)

    # Validasi: minimal harus ada 1 slot waktu ketersediaan
    @field_validator("availabilities")
    @classmethod
    def validate_availabilities(cls, value: List[AvailabilityCreate]) -> List[AvailabilityCreate]:
        if not value or len(value) == 0:
            raise ValueError("Minimal harus menyertakan 1 slot waktu ketersediaan")
        return value

    # Validasi (Fitur 1): urutan tanggal dan ukuran kelompok
    @model_validator(mode="after")
    def validate_order(self):
        if self.earliest_date > self.latest_date:
            raise ValueError("Tanggal awal tidak boleh melewati tanggal akhir")
        if self.min_group_size > self.max_group_size:
            raise ValueError("Ukuran minimum tidak boleh melebihi maksimum")
        return self


# Format balasan data Study Intent yang dikembalikan ke Frontend
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


# ==============================================================================
# 4. SKEMA UNTUK AI STUDY INTENT EXTRACTION (ONE-SHOT NLP)
# ==============================================================================

# Data pesan chat yang dikirim mahasiswa ke AI
class ChatExtractionRequest(BaseModel):
    raw_text: str

# Data balasan AI yang berisi parameter yang berhasil diekstrak
class ChatExtractionResponse(BaseModel):
    status: str
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    topics: Optional[str] = None
    learning_goal: Optional[str] = None
    collaboration_style: Optional[str] = None
    learning_mode: Optional[Any] = None
    preferred_location: Optional[str] = None
    physical_location: Optional[str] = None
    online_platform: Optional[str] = None
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    min_group_size: Optional[int] = None
    max_group_size: Optional[int] = None
    availabilities: List[dict] = []
    extraction_status: dict = {}
    extracted_parameters: dict = {}
    source_text: Optional[str] = None
    ai_model: Optional[str] = None
    ai_raw_entities: Optional[List[dict]] = None
    message: str = "Informasi berhasil diproses dengan aman"


# ==============================================================================
# 5. SKEMA OUTCOME DAN FEEDBACK (Fitur 3)
# ==============================================================================
ReasonCode = Literal[
    "SCHEDULE_MISMATCH", "TOPIC_MISMATCH", "GOAL_MISMATCH", "STYLE_MISMATCH",
    "GROUP_SIZE", "NO_RESPONSE", "USER_WITHDRAWAL", "OTHER",
]


class RecommendationViewed(BaseModel):
    match_id: str = Field(min_length=1, max_length=36)


class RecommendationFeedbackIn(BaseModel):
    relevance_rating: Optional[Literal["VERY_RELEVANT", "RELEVANT", "NEUTRAL", "NOT_RELEVANT"]] = None
    explanation_rating: Optional[Literal["VERY_CLEAR", "CLEAR", "UNCLEAR", "NOT_CLEAR"]] = None
    interest_level: Optional[Literal["INTERESTED", "UNSURE", "NOT_INTERESTED"]] = None
    comments: Optional[str] = Field(default=None, max_length=500)


class SessionFeedbackIn(BaseModel):
    session_held: bool
    participation_rating: Optional[int] = Field(default=None, ge=1, le=5)
    style_fit_rating: Optional[int] = Field(default=None, ge=1, le=5)
    learning_benefit_rating: Optional[int] = Field(default=None, ge=1, le=5)
    overall_satisfaction: Optional[int] = Field(default=None, ge=1, le=5)
    repeat_intention: Optional[bool] = None
    reason_code: Optional[ReasonCode] = None
    comments: Optional[str] = Field(default=None, max_length=500)


class FeedbackResponse(BaseModel):
    feedback_id: str
    student_id: str
    match_id: Optional[str] = None
    session_id: Optional[str] = None
    feedback_type: str
    relevance_rating: Optional[str] = None
    explanation_rating: Optional[str] = None
    interest_level: Optional[str] = None
    session_held: Optional[bool] = None
    participation_rating: Optional[int] = None
    style_fit_rating: Optional[int] = None
    learning_benefit_rating: Optional[int] = None
    overall_satisfaction: Optional[int] = None
    repeat_intention: Optional[bool] = None
    reason_code: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Metric(BaseModel):
    value: Optional[float] = None  # None berarti belum ada data, bukan nol
    numerator: float
    denominator: int


class MetricsResponse(BaseModel):
    rar: Metric
    gfr: Metric
    scr: Metric
    mss: Metric
    rsi: Metric
    failure_reasons: Dict[str, int]
    recommendation_feedback: Dict[str, Dict[str, int]]
    sessions_not_due: int
    sessions_disputed: int
    completed_with_feedback: int
    min_completed_for_weight_test: int
    data_sufficient: bool


class ScoreBand(BaseModel):
    score_from: int
    score_to: int
    sessions_due: int
    sessions_completed: int
    mean_satisfaction: Optional[float] = None


class Weights(BaseModel):
    t: float = Field(ge=0, le=1)
    g: float = Field(ge=0, le=1)
    s: float = Field(ge=0, le=1)
    d: float = Field(ge=0, le=1)
    m: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_total(self):
        if abs(self.t + self.g + self.s + self.d + self.m - 1.0) > 1e-6:
            raise ValueError("Jumlah kelima bobot harus 1,00")
        return self


class WeightEvaluateIn(BaseModel):
    candidate: Weights
    test_from: datetime  # hanya sesi yang berakhir sejak waktu ini yang dipakai sebagai data uji


class WeightResult(BaseModel):
    weights: Weights
    correlation: Optional[float] = None


class WeightEvaluateResponse(BaseModel):
    data_sufficient: bool
    completed_with_feedback: int
    test_sessions: int
    current: WeightResult
    candidate: WeightResult
    candidate_better: Optional[bool] = None


AnalysisResponse = List[ScoreBand]
