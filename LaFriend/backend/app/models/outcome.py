import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from app.database import Base


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
