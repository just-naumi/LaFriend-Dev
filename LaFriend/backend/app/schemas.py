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
from pydantic import BaseModel, ConfigDict, field_validator



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

    # Validasi: tanggal awal dan akhir harus diisi
    @field_validator("earliest_date", "latest_date")
    @classmethod
    def validate_dates(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Rentang tanggal sesi belajar wajib ditentukan")
        return value.strip()

    # Validasi: minimal harus ada 1 slot waktu ketersediaan
    @field_validator("availabilities")
    @classmethod
    def validate_availabilities(cls, value: List[AvailabilityCreate]) -> List[AvailabilityCreate]:
        if not value or len(value) == 0:
            raise ValueError("Minimal harus menyertakan 1 slot waktu ketersediaan")
        return value


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


