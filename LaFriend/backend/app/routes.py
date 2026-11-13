# ==============================================================================
# routes.py - Kumpulan Seluruh Endpoint API LaFriend
# ==============================================================================
# File ini bertugas untuk:
# 1. Menangani permintaan (Request) dari browser/frontend.
# 2. Menjalankan logika bisnis (validasi, simpan data ke database).
# 3. Mengembalikan respon JSON kembali ke frontend.
#
# Seluruh endpoint digabungkan di sini agar mudah dibaca dan dipahami alurnya
# dalam satu tempat tanpa perlu melompat-lompat antar folder.
# ==============================================================================

import hashlib
import jwt
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student, Course, StudyIntent, IntentAvailability
from app.schemas import (
    StudentRegister, StudentLogin, StudentResponse, TokenResponse,
    CourseResponse, StudyIntentCreate, StudyIntentResponse,
    ChatExtractionRequest, ChatExtractionResponse,
    RecommendationViewed, RecommendationFeedbackIn, SessionFeedbackIn, FeedbackResponse,
    MetricsResponse, AnalysisResponse, WeightEvaluateIn, WeightEvaluateResponse
)
from app.extraction import process_chat_for_study_intent
from app.outcome import OutcomeService

# Status intent yang masih berjalan (belum selesai, batal, atau kedaluwarsa)
RUNNING_STATUSES = ["ACTIVE", "GROUP_FORMING", "JOIN_PENDING"]

# Buat router utama API v1
api_router = APIRouter(prefix="/api/v1")

# Kunci rahasia untuk membuat JWT token (sederhana & aman)
SECRET_KEY = "lafriend_secret_key_telkom_university_2026"
ALGORITHM = "HS256"


# ==============================================================================
# FUNGSI HELPER KEAMANAN (Password Hash & Token)
# ==============================================================================

# Mengubah password teks biasa menjadi hash SHA-256 yang aman
def hash_password(password: str) -> str:
    # Menggunakan salt sederhana agar hash lebih unik
    salt = "lafriend_salt_2026"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

# Mengecek apakah password yang dimasukkan cocok dengan hash di database
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

# Membuat token JWT yang berlaku selama 7 hari
def create_token(student_id: str, email: str) -> str:
    expire_time = datetime.utcnow() + timedelta(days=7)
    payload = {
        "sub": student_id,
        "email": email,
        "exp": expire_time
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# Dependency untuk membaca token dari Header Authorization: Bearer <token>
# dan mengambil data mahasiswa yang sedang login dari database
def get_current_student(authorization: str = Header(None), db: Session = Depends(get_db)) -> Student:
    # 1. Pastikan header Authorization dikirimkan
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token otentikasi tidak ditemukan. Silakan login terlebih dahulu."
        )

    token = authorization.split(" ")[1]

    # 2. Dekode token JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        student_id = payload.get("sub")
        if not student_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token tidak valid")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesi login sudah habis, silakan login kembali")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token tidak valid atau rusak")

    # 3. Cari data mahasiswa di tabel students
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data mahasiswa tidak ditemukan")

    return student


# ==============================================================================
# 1. ENDPOINT KESEHATAN SISTEM (HEALTH CHECK)
# ==============================================================================
@api_router.get("/health", tags=["Health"])
def health_check():
    """Cek apakah server backend dan database berjalan normal."""
    return {
        "status": "online",
        "app": "LaFriend API",
        "database": "SQLite (database/lafriend.db)"
    }


# ==============================================================================
# 2. ENDPOINT AUTENTIKASI MAHASISWA
# ==============================================================================

@api_router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register_student(data: StudentRegister, db: Session = Depends(get_db)):
    """Mendaftarkan akun mahasiswa baru ke dalam sistem."""

    # 1. Cek apakah email kampus sudah pernah terdaftar
    existing_email = db.query(Student).filter(Student.email == data.email.lower()).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email kampus ini sudah terdaftar. Silakan gunakan email lain atau langsung login."
        )

    # 2. Cek apakah NIM sudah pernah terdaftar
    existing_nim = db.query(Student).filter(Student.student_number == data.student_number).first()
    if existing_nim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NIM mahasiswa ini sudah terdaftar."
        )

    # 3. Buat objek data mahasiswa baru
    new_student = Student(
        full_name=data.full_name.strip(),
        email=data.email.strip().lower(),
        student_number=data.student_number.strip(),
        study_program=data.study_program,
        academic_year=data.academic_year,
        password_hash=hash_password(data.password),
        verification_status="VERIFIED",
        account_status="ACTIVE",
        is_discoverable=data.is_discoverable
    )

    # 4. Simpan ke database SQLite
    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    # 5. Buatkan token login otomatis agar mahasiswa langsung bisa masuk
    token = create_token(new_student.student_id, new_student.email)

    return TokenResponse(
        access_token=token,
        student=StudentResponse.model_validate(new_student)
    )


@api_router.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login_student(data: StudentLogin, db: Session = Depends(get_db)):
    """Memverifikasi email dan password mahasiswa untuk login."""

    # 1. Cari mahasiswa berdasarkan email
    student = db.query(Student).filter(Student.email == data.email.strip().lower()).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email kampus atau password salah."
        )

    # 2. Periksa apakah password cocok
    if not verify_password(data.password, student.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email kampus atau password salah."
        )

    # 3. Buat token akses baru
    token = create_token(student.student_id, student.email)

    return TokenResponse(
        access_token=token,
        student=StudentResponse.model_validate(student)
    )


@api_router.get("/auth/me", response_model=StudentResponse, tags=["Auth"])
def get_my_profile(current_student: Student = Depends(get_current_student)):
    """Mengambil informasi profil mahasiswa yang saat ini sedang login."""
    return current_student


# ==============================================================================
# 3. ENDPOINT KATALOG MATA KULIAH
# ==============================================================================

@api_router.get("/courses", response_model=List[CourseResponse], tags=["Courses"])
def get_all_courses(db: Session = Depends(get_db)):
    """Mengambil seluruh daftar mata kuliah resmi dari database."""
    courses = db.query(Course).order_by(Course.course_code.asc()).all()
    return courses


@api_router.get("/courses/{course_id}", response_model=CourseResponse, tags=["Courses"])
def get_course_detail(course_id: str, db: Session = Depends(get_db)):
    """Melihat detail satu mata kuliah berdasarkan ID-nya."""
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mata kuliah tidak ditemukan")
    return course


# ==============================================================================
# 4. ENDPOINT STUDY INTENT (INTI TAHAP 1)
# ==============================================================================

@api_router.post("/study-intents", response_model=StudyIntentResponse, status_code=status.HTTP_201_CREATED, tags=["Study Intents"])
def create_study_intent(
    data: StudyIntentCreate,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Membuat Study Intent baru beserta slot-slot ketersediaan waktunya.
    Data langsung disimpan secara terstruktur ke dalam database SQLite.
    """

    # 1. Pastikan mata kuliah yang dipilih valid dan ada di database
    course = db.query(Course).filter(Course.course_id == data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mata kuliah yang dipilih tidak ditemukan di katalog resmi."
        )

    # 1b. Satu mahasiswa hanya punya satu intent yang masih berjalan per mata kuliah
    running = db.query(StudyIntent).filter(
        StudyIntent.student_id == current_student.student_id, StudyIntent.course_id == data.course_id,
        StudyIntent.status.in_(RUNNING_STATUSES)).first()
    if running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kamu masih punya Study Intent yang berjalan untuk mata kuliah ini."
        )

    # 2. Buat objek data StudyIntent
    new_intent = StudyIntent(
        student_id=current_student.student_id,
        course_id=data.course_id,
        topics=data.topics.strip(),
        learning_goal=data.learning_goal,
        collaboration_style=data.collaboration_style,
        learning_mode=data.learning_mode,
        earliest_date=data.earliest_date,
        latest_date=data.latest_date,
        min_group_size=data.min_group_size,
        max_group_size=data.max_group_size,
        status="ACTIVE"
    )

    db.add(new_intent)
    db.flush()  # Dapatkan new_intent.intent_id sebelum menyimpan slot waktu

    # 3. Simpan setiap slot waktu ketersediaan ke tabel intent_availabilities
    for slot in data.availabilities:
        availability_record = IntentAvailability(
            intent_id=new_intent.intent_id,
            day_or_date=slot.day_or_date.strip(),
            start_time=slot.start_time.strip(),
            end_time=slot.end_time.strip(),
            priority_rank=slot.priority_rank
        )
        db.add(availability_record)

    # 4. Simpan seluruh perubahan secara permanen (commit)
    db.commit()
    db.refresh(new_intent)

    return new_intent


@api_router.get("/study-intents", response_model=List[StudyIntentResponse], tags=["Study Intents"])
def get_my_study_intents(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Mengambil seluruh daftar Study Intent milik mahasiswa yang sedang login."""
    my_intents = (
        db.query(StudyIntent)
        .filter(StudyIntent.student_id == current_student.student_id)
        .order_by(StudyIntent.created_at.desc())
        .all()
    )
    return my_intents


@api_router.get("/study-intents/{intent_id}", response_model=StudyIntentResponse, tags=["Study Intents"])
def get_study_intent_detail(
    intent_id: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Melihat detail lengkap satu Study Intent berdasarkan ID-nya."""
    intent = db.query(StudyIntent).filter(StudyIntent.intent_id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study Intent tidak ditemukan")
    return intent


@api_router.patch("/study-intents/{intent_id}/cancel", response_model=StudyIntentResponse, tags=["Study Intents"])
def cancel_study_intent(
    intent_id: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Membatalkan Study Intent (mengubah status menjadi CANCELLED)."""

    # 1. Cari Study Intent
    intent = db.query(StudyIntent).filter(StudyIntent.intent_id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study Intent tidak ditemukan")

    # 2. Pastikan yang membatalkan adalah pemiliknya sendiri
    if intent.student_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu hanya boleh membatalkan Study Intent milikmu sendiri."
        )

    # 3. Ubah status menjadi CANCELLED dan simpan
    intent.status = "CANCELLED"
    db.commit()
    db.refresh(intent)

    return intent


# ==============================================================================
# 5. ENDPOINT AI-ASSISTED STUDY INTENT GENERATOR (ONE-SHOT NLP)
# ==============================================================================

@api_router.post("/study-intents/extract-ai", response_model=ChatExtractionResponse, tags=["Study Intents AI"])
def extract_study_intent_from_chat(
    data: ChatExtractionRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Mengekstrak parameter kebutuhan belajar dari satu pesan teks bebas mahasiswa.
    Hasil ekstraksi dikembalikan ke Frontend untuk otomatis mengisi kolom-kolom
    formulir Study Intent, sehingga mahasiswa tinggal memverifikasi ulang.
    """
    return process_chat_for_study_intent(data.raw_text, db)


# ==============================================================================
# 6. ENDPOINT OUTCOME DAN FEEDBACK (Fitur 3)
# ==============================================================================

@api_router.post("/outcomes/events/viewed", status_code=status.HTTP_201_CREATED, tags=["Outcome & Feedback"])
def record_recommendation_viewed(
    data: RecommendationViewed,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Mencatat bahwa sebuah rekomendasi ditampilkan kepada mahasiswa yang sedang login."""
    event = OutcomeService.record_viewed(db, current_student.student_id, data.match_id)
    return {"event_id": event.event_id}

@api_router.put("/outcomes/matches/{match_id}/feedback", response_model=FeedbackResponse, tags=["Outcome & Feedback"])
def save_recommendation_feedback(
    match_id: str,
    data: RecommendationFeedbackIn,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Menyimpan atau memperbarui Recommendation Feedback untuk satu rekomendasi."""
    return OutcomeService.save_recommendation_feedback(db, current_student.student_id, match_id, data)

@api_router.put("/outcomes/sessions/{session_id}/feedback", response_model=FeedbackResponse, tags=["Outcome & Feedback"])
def save_session_feedback(
    session_id: str,
    data: SessionFeedbackIn,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Menyimpan atau memperbarui Session Feedback, termasuk konfirmasi sesi terlaksana."""
    return OutcomeService.save_session_feedback(db, current_student.student_id, session_id, data)

@api_router.get("/outcomes/metrics", response_model=MetricsResponse, tags=["Outcome & Feedback"])
def get_metrics(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Lima metrik evaluasi: RAR, GFR, SCR, MSS, dan RSI."""
    return OutcomeService.compute_metrics(db)

@api_router.get("/outcomes/analysis", response_model=AnalysisResponse, tags=["Outcome & Feedback"])
def get_score_analysis(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Hasil sesi dan kepuasan per rentang skor kecocokan."""
    return OutcomeService.score_analysis(db)

@api_router.post("/outcomes/weights/evaluate", response_model=WeightEvaluateResponse, tags=["Outcome & Feedback"])
def evaluate_weights(
    data: WeightEvaluateIn,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Membandingkan bobot calon dengan bobot berlaku pada data uji. Tidak mengubah bobot."""
    return OutcomeService.evaluate_weights(db, data.candidate, data.test_from)
