# ==============================================================================
# models.py - Definisi Tabel Database (SQLAlchemy ORM)
# ==============================================================================
# File ini bertugas untuk mendefinisikan struktur 4 tabel utama:
# 1. students: Menyimpan data akun mahasiswa (NIM, Nama, Email, Password).
# 2. courses: Menyimpan daftar resmi mata kuliah yang ada di kampus.
# 3. study_intents: Menyimpan kebutuhan belajar mahasiswa untuk suatu mata kuliah.
# 4. intent_availabilities: Menyimpan jadwal waktu ketersediaan belajar mahasiswa.
# ==============================================================================

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


# ==============================================================================
# 1. TABEL MAHASISWA (students)
# ==============================================================================
class Student(Base):
    __tablename__ = "students"

    # student_id: ID unik untuk setiap mahasiswa (menggunakan format UUID)
    student_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # full_name: Nama lengkap mahasiswa (contoh: "Andi Pratama")
    full_name = Column(String(100), nullable=False)

    # email: Email kampus Telkom University, harus unik tidak boleh kembar
    email = Column(String(150), unique=True, index=True, nullable=False)

    # student_number: Nomor Induk Mahasiswa (NIM), juga harus unik
    student_number = Column(String(20), unique=True, index=True, nullable=False)

    # study_program: Program studi mahasiswa (contoh: "S1 Teknik Komputer")
    study_program = Column(String(100), nullable=False, default="S1 Teknik Komputer")

    # academic_year: Tahun angkatan mahasiswa (contoh: 2025)
    academic_year = Column(Integer, nullable=False, default=2025)

    # password_hash: Password yang sudah dienkripsi (demi keamanan, jangan simpan teks biasa)
    password_hash = Column(String(255), nullable=False)

    # verification_status: Status verifikasi akun mahasiswa ('VERIFIED' atau 'PENDING')
    verification_status = Column(String(20), default="VERIFIED", nullable=False)

    # account_status: Status aktif akun ('ACTIVE' atau 'RESTRICTED')
    account_status = Column(String(20), default="ACTIVE", nullable=False)

    # is_discoverable: Apakah profil mahasiswa ini boleh dilihat mahasiswa lain
    is_discoverable = Column(Boolean, default=True, nullable=False)

    # created_at: Waktu saat mahasiswa mendaftar
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relasi: 1 mahasiswa bisa memiliki banyak Study Intent
    study_intents = relationship("StudyIntent", back_populates="student", cascade="all, delete-orphan")


# ==============================================================================
# 2. TABEL KATALOG MATA KULIAH (courses)
# ==============================================================================
class Course(Base):
    __tablename__ = "courses"

    # course_id: ID unik untuk setiap mata kuliah
    course_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # course_code: Kode resmi mata kuliah (contoh: "TC2043")
    course_code = Column(String(20), unique=True, index=True, nullable=False)

    # course_name: Nama mata kuliah (contoh: "Struktur Data")
    course_name = Column(String(100), nullable=False)

    # study_program: Program studi pemilik mata kuliah
    study_program = Column(String(100), nullable=False, default="S1 Teknik Komputer")

    # Relasi: 1 mata kuliah bisa dipakai oleh banyak Study Intent
    study_intents = relationship("StudyIntent", back_populates="course")


# ==============================================================================
# 3. TABEL STUDY INTENT (study_intents)
# ==============================================================================
# Menyimpan satu permohonan / niat belajar mahasiswa untuk topik tertentu
class StudyIntent(Base):
    __tablename__ = "study_intents"

    # intent_id: ID unik untuk setiap Study Intent
    intent_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # student_id: Mahasiswa yang membuat Study Intent ini (Foreign Key ke tabel students)
    student_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)

    # course_id: Mata kuliah yang ingin dipelajari (Foreign Key ke tabel courses)
    course_id = Column(String(36), ForeignKey("courses.course_id", ondelete="RESTRICT"), nullable=False)

    # topics: Topik atau materi spesifik yang ingin dibahas (contoh: "Binary Search Tree, AVL Tree")
    topics = Column(Text, nullable=False)

    # learning_goal: Tujuan belajar ('UNDERSTAND', 'PRACTICE', 'EXAM_PREP', 'ASSIGNMENT', 'DISCUSSION')
    learning_goal = Column(String(50), nullable=False, default="UNDERSTAND")

    # collaboration_style: Gaya interaksi ('DISCUSSION', 'PRACTICE', 'TEACHING', 'FOCUS_STUDY')
    collaboration_style = Column(String(50), nullable=False, default="DISCUSSION")

    # learning_mode: Mode pertemuan ('OFFLINE', 'ONLINE', 'HYBRID')
    learning_mode = Column(String(20), nullable=False, default="OFFLINE")

    # earliest_date: Tanggal terawal mahasiswa siap memulai sesi belajar (format: YYYY-MM-DD)
    earliest_date = Column(String(20), nullable=False)

    # latest_date: Batas tanggal terakhir sesi belajar harus selesai (format: YYYY-MM-DD)
    latest_date = Column(String(20), nullable=False)

    # min_group_size: Jumlah anggota grup minimal (default 2 orang)
    min_group_size = Column(Integer, nullable=False, default=2)

    # max_group_size: Jumlah anggota grup maksimal (default 4 orang)
    max_group_size = Column(Integer, nullable=False, default=4)

    # status: Status sesi ('ACTIVE', 'MATCHED', 'CANCELLED', 'EXPIRED')
    status = Column(String(20), nullable=False, default="ACTIVE")

    # created_at: Waktu pembuatan Study Intent
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relasi ke tabel students dan courses
    student = relationship("Student", back_populates="study_intents")
    course = relationship("Course", back_populates="study_intents")

    # Relasi: 1 Study Intent memiliki banyak slot waktu ketersediaan
    # cascade="all, delete-orphan" memastikan jika intent dihapus, slot waktunya juga terhapus
    availabilities = relationship("IntentAvailability", back_populates="intent", cascade="all, delete-orphan")


# ==============================================================================
# 4. TABEL SLOT KETERSEDIAAN WAKTU (intent_availabilities)
# ==============================================================================
# Menyimpan hari dan jam berapa saja mahasiswa luang untuk belajar
class IntentAvailability(Base):
    __tablename__ = "intent_availabilities"

    # availability_id: ID unik untuk setiap baris slot waktu
    availability_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # intent_id: Menghubungkan slot waktu ini dengan Study Intent tertentu
    intent_id = Column(String(36), ForeignKey("study_intents.intent_id", ondelete="CASCADE"), nullable=False)

    # day_or_date: Hari atau tanggal ketersediaan (contoh: "Rabu" atau "2026-11-18")
    day_or_date = Column(String(50), nullable=False)

    # start_time: Jam mulai ketersediaan (contoh: "09:00")
    start_time = Column(String(10), nullable=False)

    # end_time: Jam selesai ketersediaan (contoh: "12:00")
    end_time = Column(String(10), nullable=False)

    # priority_rank: Skala prioritas waktu (1 = Utama/Paling Prioritas, 2 = Cadangan, 3 = Fleksibel)
    priority_rank = Column(Integer, nullable=False, default=1)

    # Relasi kembali ke StudyIntent
    intent = relationship("StudyIntent", back_populates="availabilities")


# ==============================================================================
# 5-8. TABEL OUTCOME (Fitur 3): riwayat matching, hasil sesi, feedback, bobot
# ==============================================================================
class MatchingEvent(Base):
    """Catatan riwayat aktivitas matching (Day 9 bagian 6). Bukan sumber status sesi."""
    __tablename__ = "matching_events"

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    match_id = Column(String(36), nullable=True, index=True)    # rekomendasi terkait (Fitur 1)
    session_id = Column(String(36), nullable=True, index=True)  # sesi terkait (Fitur 2)
    event_type = Column(String(40), nullable=False, index=True)
    event_status = Column(String(30), nullable=True)
    reason_code = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SessionOutcome(Base):
    """Hasil pembentukan dan pelaksanaan satu sesi, diisi oleh Fitur 2 lewat OutcomeService."""
    # shortcut: ringkasan sesi milik Fitur 3, ganti dengan tabel study_sessions saat Fitur 2 sudah ada
    __tablename__ = "session_outcomes"

    session_id = Column(String(36), primary_key=True)
    host_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    member_ids = Column(Text, nullable=True)  # ID anggota termasuk host, dipisah koma, diisi saat CONFIRMED
    status = Column(String(20), nullable=False, default="FORMING")  # FORMING, CONFIRMED, FAILED, CANCELLED
    reason_code = Column(String(30), nullable=True)  # wajib bila FAILED
    confirmed_at = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)  # UTC, waktu sesi berakhir

    # Skor saat rekomendasi diberikan, disimpan untuk evaluasi bobot (Day 9 bagian 8)
    score_total = Column(Float, nullable=True)
    score_t = Column(Float, nullable=True)
    score_g = Column(Float, nullable=True)
    score_s = Column(Float, nullable=True)
    score_d = Column(Float, nullable=True)
    score_m = Column(Float, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Feedback(Base):
    """Recommendation Feedback dan Session Feedback (Day 9 bagian 2 dan 6). Kolom kosong berarti tidak dijawab."""
    __tablename__ = "feedbacks"
    # Satu feedback per mahasiswa per rekomendasi dan per sesi. Baris dengan NULL tidak saling bentrok.
    __table_args__ = (
        UniqueConstraint("student_id", "match_id", name="uq_feedback_student_match"),
        UniqueConstraint("student_id", "session_id", name="uq_feedback_student_session"),
    )

    feedback_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    match_id = Column(String(36), nullable=True, index=True)
    session_id = Column(String(36), nullable=True, index=True)
    feedback_type = Column(String(20), nullable=False)  # RECOMMENDATION, SESSION

    # Recommendation Feedback
    relevance_rating = Column(String(20), nullable=True)
    explanation_rating = Column(String(20), nullable=True)
    interest_level = Column(String(20), nullable=True)

    # Session Feedback
    session_held = Column(Boolean, nullable=True)
    participation_rating = Column(Integer, nullable=True)     # 1-5
    style_fit_rating = Column(Integer, nullable=True)         # 1-5
    learning_benefit_rating = Column(Integer, nullable=True)  # 1-5
    overall_satisfaction = Column(Integer, nullable=True)     # 1-5
    repeat_intention = Column(Boolean, nullable=True)

    reason_code = Column(String(30), nullable=True)
    comments = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=True)


class WeightVersion(Base):
    """Riwayat bobot rumus CS. Versi terbaru yang dipakai Fitur 1. Hanya ditambah secara manual."""
    __tablename__ = "weight_versions"

    version_id = Column(Integer, primary_key=True, autoincrement=True)
    w_t = Column(Float, nullable=False)
    w_g = Column(Float, nullable=False)
    w_s = Column(Float, nullable=False)
    w_d = Column(Float, nullable=False)
    w_m = Column(Float, nullable=False)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
