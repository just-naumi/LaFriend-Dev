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
from datetime import datetime
from typing import List, Optional, Any, Union
from pydantic import BaseModel, ConfigDict, field_validator, model_validator



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
    start_time: str           # Contoh: "09:00"
    end_time: str             # Contoh: "12:00"
    priority_rank: int = 1    # 1 = Utama, 2 = Cadangan, 3 = Fleksibel

    @field_validator("day_or_date")
    @classmethod
    def validate_day_or_date(cls, value: str) -> str:
        clean = (value or "").strip()
        if not clean:
            raise ValueError("Hari atau tanggal ketersediaan tidak boleh kosong")
        return clean

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, value: str) -> str:
        clean = (value or "").strip()
        if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", clean):
            raise ValueError(f"Format jam '{value}' tidak valid. Gunakan format JJ:MM (contoh: 09:00 atau 14:00)")
        return clean

    @field_validator("priority_rank")
    @classmethod
    def validate_priority_rank(cls, value: int) -> int:
        if value not in (1, 2, 3):
            return 1
        return value

    # Validasi relasi: jam selesai harus lebih besar daripada jam mulai
    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValueError(f"Jam selesai ({self.end_time}) harus lebih besar daripada jam mulai ({self.start_time})")
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
    min_group_size: int = 2
    max_group_size: int = 4
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

    # Validasi: tanggal awal dan akhir harus diisi dan berformat YYYY-MM-DD kalender valid
    @field_validator("earliest_date", "latest_date")
    @classmethod
    def validate_dates(cls, value: str) -> str:
        clean = (value or "").strip()
        if not clean:
            raise ValueError("Rentang tanggal sesi belajar wajib ditentukan")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", clean):
            raise ValueError(f"Format tanggal '{value}' tidak valid. Gunakan format YYYY-MM-DD")
        try:
            datetime.strptime(clean, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Tanggal '{value}' tidak valid dalam kalender")
        return clean

    # Validasi: minimal harus ada 1 slot waktu ketersediaan
    @field_validator("availabilities")
    @classmethod
    def validate_availabilities(cls, value: List[AvailabilityCreate]) -> List[AvailabilityCreate]:
        if not value or len(value) == 0:
            raise ValueError("Minimal harus menyertakan 1 slot waktu ketersediaan")
        return value

    # Validasi relasi antar kolom (Cross-Field):
    # 1. earliest_date <= latest_date
    # 2. 2 <= min_group_size <= max_group_size <= 10
    @model_validator(mode="after")
    def validate_intent_cross_fields(self):
        # 1. Validasi rentang tanggal
        if self.earliest_date and self.latest_date:
            d_start = datetime.strptime(self.earliest_date, "%Y-%m-%d")
            d_end = datetime.strptime(self.latest_date, "%Y-%m-%d")
            if d_start > d_end:
                raise ValueError(f"Tanggal awal ({self.earliest_date}) tidak boleh melewati tanggal akhir ({self.latest_date})")

        # 2. Validasi ukuran kelompok
        if self.min_group_size < 2:
            raise ValueError("Ukuran kelompok minimal adalah 2 orang")
        if self.max_group_size < self.min_group_size:
            raise ValueError(f"Ukuran kelompok minimal ({self.min_group_size}) tidak boleh melebihi ukuran maksimal ({self.max_group_size})")

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
# 5. SKEMA UNTUK MATCHING ENGINE & STUDY SESSION (DAY 13)
# ==============================================================================

# --- A. SKEMA JADWAL SESI (SessionSlot) ---
class SessionSlotCreate(BaseModel):
    session_date: str          # Format: YYYY-MM-DD
    start_time: str            # Format: HH:MM
    end_time: str              # Format: HH:MM
    status: str = "PROPOSED"   # PROPOSED, APPROVED, REJECTED, SUPERSEDED

    @field_validator("session_date")
    @classmethod
    def validate_slot_date(cls, value: str) -> str:
        clean = (value or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", clean):
            raise ValueError(f"Format tanggal '{value}' tidak valid. Gunakan YYYY-MM-DD")
        try:
            datetime.strptime(clean, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Tanggal '{value}' tidak valid dalam kalender")
        return clean

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_slot_time(cls, value: str) -> str:
        clean = (value or "").strip()
        if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", clean):
            raise ValueError(f"Format jam '{value}' tidak valid. Gunakan format JJ:MM")
        return clean

    @field_validator("status")
    @classmethod
    def validate_slot_status(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        valid_statuses = {"PROPOSED", "APPROVED", "REJECTED", "SUPERSEDED"}
        if clean not in valid_statuses:
            raise ValueError(f"Status slot '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_statuses))}")
        return clean

    @model_validator(mode="after")
    def validate_slot_time_range(self):
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValueError(f"Jam selesai ({self.end_time}) harus lebih besar daripada jam mulai ({self.start_time})")
        return self


class SessionSlotResponse(BaseModel):
    slot_id: str
    session_id: str
    session_date: str
    start_time: str
    end_time: str
    status: str

    model_config = ConfigDict(from_attributes=True)


# --- B. SKEMA ANGGOTA SESI (SessionMember) ---
class SessionMemberCreate(BaseModel):
    student_id: str
    role: str = "MEMBER"       # HOST, MEMBER
    status: str = "INVITED"    # INVITED, ACCEPTED, CONFIRMED, DECLINED, WITHDRAWN, REMOVED

    @field_validator("role")
    @classmethod
    def validate_member_role(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        if clean not in {"HOST", "MEMBER"}:
            raise ValueError("Role anggota harus 'HOST' atau 'MEMBER'")
        return clean

    @field_validator("status")
    @classmethod
    def validate_member_status(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        valid_statuses = {"INVITED", "ACCEPTED", "CONFIRMED", "DECLINED", "WITHDRAWN", "REMOVED"}
        if clean not in valid_statuses:
            raise ValueError(f"Status anggota '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_statuses))}")
        return clean


class SessionMemberResponse(BaseModel):
    member_id: str
    session_id: str
    student_id: str
    role: str
    status: str
    joined_at: datetime
    student: Optional[StudentResponse] = None

    model_config = ConfigDict(from_attributes=True)


# --- C. SKEMA SESI BELAJAR (StudySession) ---
class StudySessionCreate(BaseModel):
    course_id: str
    title: str
    description: Optional[str] = None
    learning_goal: str = "UNDERSTAND"
    collaboration_style: str = "DISCUSSION"
    learning_mode: str = "OFFLINE"
    location: Optional[str] = None
    min_group_size: int = 2
    max_group_size: int = 4
    status: str = "DRAFT"
    slots: List[SessionSlotCreate] = []

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        clean = (value or "").strip()
        if not clean:
            raise ValueError("Judul sesi belajar tidak boleh kosong")
        return clean

    @field_validator("learning_goal")
    @classmethod
    def validate_session_goal(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        valid_goals = {"UNDERSTAND", "PRACTICE", "EXAM_PREP", "ASSIGNMENT", "DISCUSSION", "KNOWLEDGE_SHARING"}
        if clean not in valid_goals:
            raise ValueError(f"learning_goal '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_goals))}")
        return clean

    @field_validator("collaboration_style")
    @classmethod
    def validate_session_style(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        valid_styles = {"DISCUSSION", "PRACTICE", "TEACHING", "FOCUS_STUDY"}
        if clean not in valid_styles:
            raise ValueError(f"collaboration_style '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_styles))}")
        return clean

    @field_validator("learning_mode")
    @classmethod
    def validate_session_mode(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        valid_modes = {"OFFLINE", "ONLINE", "HYBRID"}
        if clean not in valid_modes:
            raise ValueError(f"learning_mode '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_modes))}")
        return clean

    @field_validator("status")
    @classmethod
    def validate_session_status(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        valid_statuses = {"DRAFT", "OPEN", "CONFIRMATION_PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "EXPIRED"}
        if clean not in valid_statuses:
            raise ValueError(f"status sesi '{value}' tidak valid. Pilihan: {', '.join(sorted(valid_statuses))}")
        return clean

    @model_validator(mode="after")
    def validate_session_group_size(self):
        if self.min_group_size < 2:
            raise ValueError("Ukuran kelompok minimal adalah 2 orang")
        if self.max_group_size < self.min_group_size:
            raise ValueError(f"Ukuran kelompok minimal ({self.min_group_size}) tidak boleh melebihi maksimal ({self.max_group_size})")
        return self


class StudySessionResponse(BaseModel):
    session_id: str
    host_id: str
    course_id: str
    title: str
    description: Optional[str] = None
    learning_goal: str
    collaboration_style: str
    learning_mode: str
    location: Optional[str] = None
    min_group_size: int
    max_group_size: int
    status: str
    created_at: datetime
    updated_at: datetime
    course: Optional[CourseResponse] = None
    slots: List[SessionSlotResponse] = []
    members: List[SessionMemberResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- D. SKEMA UNDANGAN & PERMINTAAN (Invitation) ---
class InvitationCreate(BaseModel):
    invitation_type: str       # JOIN_SESSION, PARTNER_INVITE
    recipient_id: str
    session_id: Optional[str] = None
    target_intent_id: Optional[str] = None
    message: Optional[str] = None

    @field_validator("invitation_type")
    @classmethod
    def validate_invite_type(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        if clean not in {"JOIN_SESSION", "PARTNER_INVITE"}:
            raise ValueError("invitation_type harus 'JOIN_SESSION' atau 'PARTNER_INVITE'")
        return clean

    @model_validator(mode="after")
    def validate_invite_target(self):
        if self.invitation_type == "JOIN_SESSION" and not self.session_id:
            raise ValueError("Undangan tipe 'JOIN_SESSION' wajib menyertakan session_id")
        if self.invitation_type == "PARTNER_INVITE" and not self.target_intent_id:
            raise ValueError("Undangan tipe 'PARTNER_INVITE' wajib menyertakan target_intent_id")
        return self


class InvitationResponse(BaseModel):
    invitation_id: str
    invitation_type: str
    sender_id: str
    recipient_id: str
    session_id: Optional[str] = None
    target_intent_id: Optional[str] = None
    status: str
    message: Optional[str] = None
    created_at: datetime
    responded_at: Optional[datetime] = None
    sender: Optional[StudentResponse] = None
    recipient: Optional[StudentResponse] = None

    model_config = ConfigDict(from_attributes=True)


# --- E. SKEMA HASIL PENCOCOKAN (MatchResult) ---
class MatchBreakdown(BaseModel):
    topic_similarity: float
    goal_compatibility: float
    style_compatibility: float
    date_preference: float
    mode_compatibility: float


class MatchResultCreate(BaseModel):
    intent_id: str
    candidate_type: str       # SESSION, PARTNER
    candidate_session_id: Optional[str] = None
    target_intent_id: Optional[str] = None
    compatibility_score: float
    breakdown: MatchBreakdown
    explanation: Optional[str] = None

    @field_validator("candidate_type")
    @classmethod
    def validate_candidate_type(cls, value: str) -> str:
        clean = (value or "").strip().upper()
        if clean not in {"SESSION", "PARTNER"}:
            raise ValueError("candidate_type harus 'SESSION' atau 'PARTNER'")
        return clean

    @field_validator("compatibility_score")
    @classmethod
    def validate_score(cls, value: float) -> float:
        if not (0.0 <= value <= 100.0):
            raise ValueError(f"compatibility_score ({value}) harus berada di rentang 0.0 sampai 100.0")
        return value

    @model_validator(mode="after")
    def validate_single_target(self):
        if self.candidate_type == "SESSION":
            if not self.candidate_session_id:
                raise ValueError("Untuk candidate_type 'SESSION', candidate_session_id wajib diisi")
            if self.target_intent_id:
                raise ValueError("Untuk candidate_type 'SESSION', target_intent_id tidak boleh diisi")
        elif self.candidate_type == "PARTNER":
            if not self.target_intent_id:
                raise ValueError("Untuk candidate_type 'PARTNER', target_intent_id wajib diisi")
            if self.candidate_session_id:
                raise ValueError("Untuk candidate_type 'PARTNER', candidate_session_id tidak boleh diisi")
        return self


class MatchResultResponse(BaseModel):
    match_id: str
    intent_id: str
    candidate_type: str
    candidate_session_id: Optional[str] = None
    target_intent_id: Optional[str] = None
    compatibility_score: float
    breakdown_json: str
    explanation: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


