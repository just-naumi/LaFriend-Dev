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
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
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

