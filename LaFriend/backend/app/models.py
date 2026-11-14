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
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Float
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

    # Day 13: Relasi ke Sesi Belajar, Keanggotaan Sesi, dan Undangan
    hosted_sessions = relationship("StudySession", back_populates="host", foreign_keys="StudySession.host_id", cascade="all, delete-orphan")
    session_memberships = relationship("SessionMember", back_populates="student", cascade="all, delete-orphan")
    sent_invitations = relationship("Invitation", foreign_keys="Invitation.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_invitations = relationship("Invitation", foreign_keys="Invitation.recipient_id", back_populates="recipient", cascade="all, delete-orphan")


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

    # Relasi: 1 mata kuliah bisa dipakai oleh banyak Study Intent & Study Session
    study_intents = relationship("StudyIntent", back_populates="course")
    study_sessions = relationship("StudySession", back_populates="course")


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

    # Day 13: Relasi hasil rekomendasi & skor pencocokan (MatchResult)
    match_results = relationship("MatchResult", foreign_keys="MatchResult.intent_id", back_populates="intent", cascade="all, delete-orphan")


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
# 5. TABEL SESI BELAJAR (study_sessions) - DAY 13
# ==============================================================================
# Menyimpan informasi kelompok / sesi belajar baik dalam proses pembentukan
# maupun yang sudah terkonfirmasi.
class StudySession(Base):
    __tablename__ = "study_sessions"

    # session_id: ID unik untuk setiap sesi belajar
    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # host_id: Mahasiswa inisiator/pemilik sesi belajar (FK ke students)
    host_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)

    # course_id: Mata kuliah yang dipelajari dalam sesi ini (FK ke courses)
    course_id = Column(String(36), ForeignKey("courses.course_id", ondelete="RESTRICT"), nullable=False)

    # title: Judul sesi belajar (contoh: "Bedah Soal UTS Kalkulus 1 Bab Integral")
    title = Column(String(150), nullable=False)

    # description: Penjelasan atau agenda sesi belajar
    description = Column(Text, nullable=True)

    # learning_goal: Tujuan belajar ('UNDERSTAND', 'PRACTICE', 'EXAM_PREP', 'ASSIGNMENT', 'DISCUSSION')
    learning_goal = Column(String(50), nullable=False, default="UNDERSTAND")

    # collaboration_style: Gaya interaksi ('DISCUSSION', 'PRACTICE', 'TEACHING', 'FOCUS_STUDY')
    collaboration_style = Column(String(50), nullable=False, default="DISCUSSION")

    # learning_mode: Mode pelaksanaan ('OFFLINE', 'ONLINE', 'HYBRID')
    learning_mode = Column(String(20), nullable=False, default="OFFLINE")

    # location: Tempat fisik atau tautan platform meeting
    location = Column(String(100), nullable=True)

    # min_group_size: Batas minimum anggota untuk memulai sesi (default 2)
    min_group_size = Column(Integer, nullable=False, default=2)

    # max_group_size: Kapasitas maksimum anggota sesi (default 4)
    max_group_size = Column(Integer, nullable=False, default=4)

    # status: Siklus hidup sesi:
    # DRAFT -> OPEN -> CONFIRMATION_PENDING -> CONFIRMED -> COMPLETED / CANCELLED / EXPIRED
    status = Column(String(30), nullable=False, default="DRAFT")

    # created_at & updated_at: Jejak waktu pembuatan dan modifikasi sesi
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relasi
    host = relationship("Student", back_populates="hosted_sessions", foreign_keys=[host_id])
    course = relationship("Course", back_populates="study_sessions")
    slots = relationship("SessionSlot", back_populates="session", cascade="all, delete-orphan")
    members = relationship("SessionMember", back_populates="session", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="session", cascade="all, delete-orphan")


# ==============================================================================
# 6. TABEL JADWAL SESI BELAJAR (session_slots) - DAY 13
# ==============================================================================
# Menyimpan tanggal dan jam spesifik pelaksanaan sesi belajar beserta status persetujuannya
class SessionSlot(Base):
    __tablename__ = "session_slots"

    slot_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("study_sessions.session_id", ondelete="CASCADE"), nullable=False)

    # session_date: Tanggal spesifik pelaksanaan (format: YYYY-MM-DD, contoh: "2026-11-20")
    session_date = Column(String(20), nullable=False)

    # start_time & end_time: Waktu mulai dan selesai (format: HH:MM, contoh: "09:00", "11:00")
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)

    # status: Status slot jadwal:
    # PROPOSED (Diajukan) -> APPROVED (Disetujui bersama) -> REJECTED (Ditolak) -> SUPERSEDED (Digantikan slot baru)
    status = Column(String(20), nullable=False, default="PROPOSED")

    # Relasi kembali ke StudySession
    session = relationship("StudySession", back_populates="slots")


# ==============================================================================
# 7. TABEL ANGGOTA SESI BELAJAR (session_members) - DAY 13
# ==============================================================================
# Mencatat mahasiswa yang tergabung dalam suatu sesi belajar beserta role dan status keanggotaannya
class SessionMember(Base):
    __tablename__ = "session_members"

    member_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("study_sessions.session_id", ondelete="CASCADE"), nullable=False)
    student_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)

    # role: 'HOST' (Pembuat sesi) atau 'MEMBER' (Anggota biasa)
    role = Column(String(20), nullable=False, default="MEMBER")

    # status: Status keanggotaan:
    # INVITED -> ACCEPTED -> CONFIRMED -> DECLINED / WITHDRAWN / REMOVED
    status = Column(String(20), nullable=False, default="INVITED")

    # joined_at: Waktu saat mahasiswa bergabung/diundang ke sesi
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relasi ke StudySession dan Student
    session = relationship("StudySession", back_populates="members")
    student = relationship("Student", back_populates="session_memberships")


# ==============================================================================
# 8. TABEL UNDANGAN & PERMINTAAN BERGABUNG (invitations) - DAY 13
# ==============================================================================
# Mengelola dua jenis proses:
# 1. JOIN_SESSION: Mahasiswa meminta bergabung ke sesi belajar yang sudah ada
# 2. PARTNER_INVITE: Mahasiswa mengundang kandidat untuk membentuk kelompok baru berdasarkan Study Intent
class Invitation(Base):
    __tablename__ = "invitations"

    invitation_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # invitation_type: 'JOIN_SESSION' atau 'PARTNER_INVITE'
    invitation_type = Column(String(30), nullable=False)

    # sender_id & recipient_id: Pengirim dan penerima undangan (FK ke students)
    sender_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    recipient_id = Column(String(36), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)

    # session_id: Terisi jika tipe JOIN_SESSION (nullable jika PARTNER_INVITE)
    session_id = Column(String(36), ForeignKey("study_sessions.session_id", ondelete="CASCADE"), nullable=True)

    # target_intent_id: Terisi jika tipe PARTNER_INVITE (nullable jika JOIN_SESSION)
    target_intent_id = Column(String(36), ForeignKey("study_intents.intent_id", ondelete="SET NULL"), nullable=True)

    # status: 'PENDING', 'ACCEPTED', 'REJECTED', 'WITHDRAWN', 'EXPIRED'
    status = Column(String(20), nullable=False, default="PENDING")

    # message: Pesan pengantar personal dari pengirim
    message = Column(Text, nullable=True)

    # created_at & responded_at: Waktu pengiriman dan respons
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at = Column(DateTime, nullable=True)

    # Relasi
    sender = relationship("Student", foreign_keys=[sender_id], back_populates="sent_invitations")
    recipient = relationship("Student", foreign_keys=[recipient_id], back_populates="received_invitations")
    session = relationship("StudySession", back_populates="invitations")
    target_intent = relationship("StudyIntent")


# ==============================================================================
# 9. TABEL HASIL PENCOCOKAN & SKOR KOMPATIBILITAS (match_results) - DAY 13
# ==============================================================================
# Menyimpan hasil kalkulasi algoritma matching (Session Matching maupun Partner Matching)
class MatchResult(Base):
    __tablename__ = "match_results"

    match_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # intent_id: Study Intent pencari/inisiator yang sedang dicocokkan
    intent_id = Column(String(36), ForeignKey("study_intents.intent_id", ondelete="CASCADE"), nullable=False)

    # candidate_type: 'SESSION' (rekomendasi sesi ada) atau 'PARTNER' (rekomendasi rekan belajar)
    candidate_type = Column(String(20), nullable=False)

    # candidate_session_id: Terisi jika candidate_type == 'SESSION'
    candidate_session_id = Column(String(36), ForeignKey("study_sessions.session_id", ondelete="CASCADE"), nullable=True)

    # target_intent_id: Terisi jika candidate_type == 'PARTNER' (menunjuk Study Intent kandidat)
    target_intent_id = Column(String(36), ForeignKey("study_intents.intent_id", ondelete="CASCADE"), nullable=True)

    # compatibility_score: Skor kecocokan 0.0 - 100.0 (CS = 0.30T + 0.25G + 0.15S + 0.15D + 0.15M)
    compatibility_score = Column(Float, nullable=False)

    # breakdown_json: Rincian skor dalam format JSON string
    # {"topic_similarity": 90, "goal_compatibility": 100, "style_compatibility": 80, ...}
    breakdown_json = Column(Text, nullable=False)

    # explanation: Kalimat penjelasan alasan rekomendasi yang mudah dipahami mahasiswa
    explanation = Column(Text, nullable=True)

    # created_at: Waktu komputasi skor dilakukan
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relasi
    intent = relationship("StudyIntent", foreign_keys=[intent_id], back_populates="match_results")
    candidate_session = relationship("StudySession")
    target_intent = relationship("StudyIntent", foreign_keys=[target_intent_id])

