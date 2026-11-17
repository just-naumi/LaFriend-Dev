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
import json
import math
import jwt
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student, Course, StudyIntent, IntentAvailability, MatchResult, StudySession
from app.schemas import (
    StudentRegister, StudentLogin, StudentResponse, TokenResponse,
    CourseResponse, StudyIntentCreate, StudyIntentResponse,
    ChatExtractionRequest, ChatExtractionResponse,
    RecommendationRequest, RecommendationResponse, MatchResultResponse,
    GroupProposalPreviewRequest, GroupProposalPreviewResponse,
    GroupProposalCreateRequest, GroupProposalResponse, GroupProposalCancelRequest,
    InvitationRespondRequest, InvitationResponse
)
from app.extraction import process_chat_for_study_intent
from app.matching import run_matching_pipeline, calculate_session_occupied_capacity
from app.group_formation import preview_group_formation_pipeline
from app.group_proposal_service import (
    create_group_proposal_service,
    get_group_proposal_detail_service,
    finalize_group_proposal_service,
    cancel_group_proposal_service,
    respond_invitation_service,
    get_student_inbox_service,
    get_student_sent_service
)

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
# 6. ENDPOINT MATCHING & RECOMMENDATIONS (DAY 16)
# ==============================================================================

@api_router.post("/matching/recommendations", response_model=RecommendationResponse, tags=["Matching Engine"])
def get_recommendations_post(
    req: RecommendationRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Menjalankan Matching Pipeline Orchestrator (Day 16) untuk menemukan rekomendasi
    sesi belajar (StudySession) atau rekan belajar (StudyIntent).

    Prinsip Session-First:
    1. Memprioritaskan Study Session terlebih dahulu.
    2. Jika ditemukan sesi yang lolos filter dan memenuhi min_score, rekomendasi sesi
       dikembalikan (Partner Matching tidak dieksekusi).
    3. Jika tidak ada sesi yang memenuhi syarat, otomatis fallback ke Partner Matching.
    4. Seluruh kandidat rekomendasi disimpan secara atomik ke tabel MatchResult.
    """
    # 1. Validasi keberadaan Study Intent
    intent = db.query(StudyIntent).filter(StudyIntent.intent_id == req.intent_id).first()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study Intent dengan ID '{req.intent_id}' tidak ditemukan."
        )

    # 2. Validasi kepemilikan intent (Otorisasi)
    if intent.student_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu hanya berhak meminta rekomendasi untuk Study Intent milikmu sendiri."
        )

    # 3. Validasi status akun mahasiswa peminta
    if (current_student.account_status or "").upper() != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu sedang ditangguhkan atau tidak aktif."
        )
    if (current_student.verification_status or "").upper() != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu belum berstatus VERIFIED."
        )

    # 4. Validasi status siklus hidup Study Intent
    if (intent.status or "").upper() != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Study Intent tidak aktif (status saat ini: {intent.status}). Hanya intent berstatus ACTIVE yang dapat dicocokkan."
        )

    # 5. Eksekusi Matching Pipeline Orchestrator
    try:
        pipeline_output = run_matching_pipeline(
            intent=intent,
            db=db,
            min_score=req.min_score,
            limit=req.limit,
            persist=True
        )
        return pipeline_output
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat memproses rekomendasi: {str(e)}"
        )


@api_router.get("/study-intents/{intent_id}/recommendations", response_model=RecommendationResponse, tags=["Matching Engine"])
def get_recommendations_get(
    intent_id: str,
    min_score: float = 60.0,
    limit: Optional[int] = 5,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Endpoint Read-Only (Idempotent) untuk membaca hasil rekomendasi yang sudah tersimpan
    di database (tabel MatchResult) untuk suatu Study Intent.
    TIDAK melakukan perubahan state server (tidak menghapus, menghitung ulang, atau menulis ke database).
    Untuk menghasilkan/memperbarui rekomendasi baru, gunakan POST /matching/recommendations.
    """
    # 1. Validasi parameter input
    if min_score is None or isinstance(min_score, bool):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_score harus numerik non-boolean")
    try:
        min_score_val = float(min_score)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_score harus berupa angka numerik valid")
    if math.isnan(min_score_val) or math.isinf(min_score_val):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_score harus berupa angka berhingga")
    if not (0.0 <= min_score_val <= 100.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"min_score ({min_score_val}) harus dalam rentang [0.0, 100.0]")

    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit harus berupa integer positif atau None")
        if limit < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"limit ({limit}) harus bernilai minimal 1")

    # 2. Validasi keberadaan Study Intent
    intent = db.query(StudyIntent).filter(StudyIntent.intent_id == intent_id).first()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study Intent dengan ID '{intent_id}' tidak ditemukan."
        )

    # 3. Validasi kepemilikan intent (Otorisasi)
    if intent.student_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu hanya berhak melihat rekomendasi untuk Study Intent milikmu sendiri."
        )

    # 4. Validasi status akun mahasiswa peminta
    if (current_student.account_status or "").upper() != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu sedang ditangguhkan atau tidak aktif."
        )
    if (current_student.verification_status or "").upper() != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu belum berstatus VERIFIED."
        )

    # 5. Baca data rekomendasi tersimpan secara read-only dari tabel match_results
    query = (
        db.query(MatchResult)
        .filter(MatchResult.intent_id == intent_id)
        .order_by(MatchResult.compatibility_score.desc())
    )
    if min_score_val > 0.0:
        query = query.filter(MatchResult.compatibility_score >= min_score_val)

    stored_matches = query.all()
    if limit is not None and limit >= 1:
        stored_matches = stored_matches[:limit]

    formatted_recs = []
    match_type = "NONE"
    if stored_matches:
        match_type = stored_matches[0].candidate_type

    for idx, match in enumerate(stored_matches):
        try:
            breakdown_dict = json.loads(match.breakdown_json)
        except Exception:
            breakdown_dict = {
                "topic_similarity": 0.0,
                "goal_compatibility": 0.0,
                "style_compatibility": 0.0,
                "date_preference": 0.0,
                "mode_compatibility": 0.0,
            }

        session_details = None
        partner_details = None

        if match.candidate_type == "SESSION" and match.candidate_session_id:
            sess = db.query(StudySession).filter(StudySession.session_id == match.candidate_session_id).first()
            if sess:
                occupied = calculate_session_occupied_capacity(sess)
                host_name = sess.host.full_name if getattr(sess, "host", None) else None
                course_title = sess.course.course_name if getattr(sess, "course", None) else None
                session_details = {
                    "session_id": sess.session_id,
                    "title": sess.title,
                    "description": sess.description,
                    "host_id": sess.host_id,
                    "host_name": host_name,
                    "course_id": sess.course_id,
                    "course_name": course_title,
                    "learning_goal": sess.learning_goal,
                    "collaboration_style": sess.collaboration_style,
                    "learning_mode": sess.learning_mode,
                    "location": sess.location,
                    "occupied_seats": occupied,
                    "max_group_size": sess.max_group_size,
                }
        elif match.candidate_type == "PARTNER" and match.target_intent_id:
            part = db.query(StudyIntent).filter(StudyIntent.intent_id == match.target_intent_id).first()
            if part:
                st = getattr(part, "student", None)
                partner_details = {
                    "target_intent_id": part.intent_id,
                    "student_id": part.student_id,
                    "student_name": st.full_name if st else None,
                    "study_program": st.study_program if st else None,
                    "academic_year": st.academic_year if st else None,
                    "topics": part.topics,
                    "learning_goal": part.learning_goal,
                    "collaboration_style": part.collaboration_style,
                    "learning_mode": part.learning_mode,
                    "min_group_size": part.min_group_size,
                    "max_group_size": part.max_group_size,
                }

        selected_schedule = None
        if getattr(match, "selected_schedule_json", None):
            try:
                selected_schedule = json.loads(match.selected_schedule_json)
            except Exception:
                selected_schedule = None

        formatted_recs.append({
            "match_id": match.match_id,
            "rank": idx + 1,
            "candidate_type": match.candidate_type,
            "candidate_session_id": match.candidate_session_id,
            "target_intent_id": match.target_intent_id,
            "compatibility_score": round(float(match.compatibility_score), 2),
            "breakdown": breakdown_dict,
            "explanation": match.explanation or "",
            "selected_schedule": selected_schedule,
            "session_details": session_details,
            "partner_details": partner_details,
        })

    if match_type == "SESSION":
        msg = f"Menampilkan {len(formatted_recs)} rekomendasi Study Session tersimpan."
    elif match_type == "PARTNER":
        msg = f"Menampilkan {len(formatted_recs)} rekomendasi Partner tersimpan."
    else:
        msg = "Belum ada rekomendasi tersimpan untuk Study Intent ini. Silakan jalankan POST /matching/recommendations."

    course_name = intent.course.course_name if getattr(intent, "course", None) else None

    return {
        "intent_id": str(intent.intent_id),
        "course_id": str(intent.course_id),
        "course_name": course_name,
        "match_type": match_type,
        "total_candidates": len(formatted_recs),
        "recommendations": formatted_recs,
        "message": msg,
    }


@api_router.get("/matching/results/{intent_id}", response_model=List[MatchResultResponse], tags=["Matching Engine"])
def get_persisted_match_results(
    intent_id: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Mengambil daftar hasil pencocokan (MatchResult) yang tersimpan di database
    untuk Study Intent yang dimiliki mahasiswa.
    """
    # 1. Validasi keberadaan Study Intent
    intent = db.query(StudyIntent).filter(StudyIntent.intent_id == intent_id).first()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study Intent dengan ID '{intent_id}' tidak ditemukan."
        )

    # 2. Validasi otorisasi kepemilikan
    if intent.student_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu hanya berhak melihat hasil pencocokan untuk Study Intent milikmu sendiri."
        )

    # 3. Validasi status akun dan status verifikasi mahasiswa
    if (current_student.account_status or "").upper() != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu sedang ditangguhkan atau tidak aktif."
        )
    if (current_student.verification_status or "").upper() != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu belum berstatus VERIFIED."
        )

    results = (
        db.query(MatchResult)
        .filter(MatchResult.intent_id == intent_id)
        .order_by(MatchResult.compatibility_score.desc())
        .all()
    )
    return results


@api_router.post(
    "/matching/group-proposals/preview",
    response_model=GroupProposalPreviewResponse,
    tags=["Matching Engine"]
)
def preview_group_proposal_endpoint(
    req: GroupProposalPreviewRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Day 17: Menghasilkan pratinjau (preview) calon kelompok belajar terpadu
    berdasarkan hasil Partner Matching yang saling cocok (Pairwise Compatibility & GQ Score).
    Operasi ini bersifat murni READ-ONLY (tidak menulis atau mengubah database apa pun).
    """
    # 1. Validasi status akun dan verifikasi mahasiswa
    if (current_student.account_status or "").upper() != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu sedang ditangguhkan atau tidak aktif."
        )
    if (current_student.verification_status or "").upper() != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu belum berstatus VERIFIED."
        )

    # 2. Validasi keberadaan Study Intent
    intent = db.query(StudyIntent).filter(StudyIntent.intent_id == req.host_intent_id).first()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study Intent dengan ID '{req.host_intent_id}' tidak ditemukan."
        )

    # 3. Validasi kepemilikan intent (Otorisasi)
    if intent.student_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu hanya berhak membuat usulan kelompok untuk Study Intent milikmu sendiri."
        )

    # 4. Validasi status intent
    if intent.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Study Intent ini berstatus '{intent.status}'. Usulan kelompok hanya dapat dibuat untuk intent ACTIVE."
        )

    try:
        result = preview_group_formation_pipeline(
            host_intent_id=req.host_intent_id,
            db=db,
            min_score=req.min_score,
            target_group_size=req.target_group_size,
            max_candidate_pool=req.max_candidate_pool
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


# ==============================================================================
# 9. ENDPOINTS GROUP PROPOSAL & AGREEMENT LAYER (DAY 20)
# ==============================================================================

@api_router.post(
    "/matching/group-proposals",
    response_model=GroupProposalResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Group Proposals"]
)
def create_group_proposal_endpoint(
    req: GroupProposalCreateRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Day 20.2: Host membuat usulan kelompok belajar (GroupProposal) resmi
    berdasarkan hasil rekomendasi matching engine dan menyebarkan undangan ke calon anggota.
    """
    return create_group_proposal_service(db=db, host_student=current_student, req=req)


@api_router.get(
    "/matching/group-proposals/{proposal_id}",
    response_model=GroupProposalResponse,
    tags=["Group Proposals"]
)
def get_group_proposal_endpoint(
    proposal_id: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Day 20.3: Mengambil detail proposal kelompok beserta status respons undangan dan kuorum.
    """
    return get_group_proposal_detail_service(db=db, proposal_id=proposal_id, current_student=current_student)


@api_router.post(
    "/matching/group-proposals/{proposal_id}/finalize",
    response_model=GroupProposalResponse,
    tags=["Group Proposals"]
)
def finalize_group_proposal_endpoint(
    proposal_id: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Day 20.5: Host memfinalisasi proposal yang sudah memenuhi kuorum (QUORUM_REACHED)
    menjadi READY_FOR_SESSION.
    """
    return finalize_group_proposal_service(db=db, proposal_id=proposal_id, host_student=current_student)


@api_router.post(
    "/matching/group-proposals/{proposal_id}/cancel",
    response_model=GroupProposalResponse,
    tags=["Group Proposals"]
)
def cancel_group_proposal_endpoint(
    proposal_id: str,
    req: Optional[GroupProposalCancelRequest] = None,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Day 20.5: Host membatalkan proposal kelompok (status menjadi CANCELLED).
    """
    reason = req.reason if req else None
    return cancel_group_proposal_service(db=db, proposal_id=proposal_id, host_student=current_student, reason=reason)


@api_router.get(
    "/invitations/inbox",
    response_model=List[InvitationResponse],
    tags=["Invitations"]
)
def get_invitations_inbox_endpoint(
    status: Optional[str] = None,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Day 20.3: Mengambil daftar undangan masuk (received invitations) untuk mahasiswa saat ini.
    """
    return get_student_inbox_service(db=db, student=current_student, status_filter=status)


@api_router.get(
    "/invitations/sent",
    response_model=List[InvitationResponse],
    tags=["Invitations"]
)
def get_invitations_sent_endpoint(
    status: Optional[str] = None,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Day 20.3: Mengambil daftar undangan terkirim (sent invitations) oleh mahasiswa saat ini.
    """
    return get_student_sent_service(db=db, student=current_student, status_filter=status)


@api_router.post(
    "/invitations/{invitation_id}/respond",
    response_model=InvitationResponse,
    tags=["Invitations"]
)
def respond_invitation_endpoint(
    invitation_id: str,
    req: InvitationRespondRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Day 20.4: Calon anggota merespons undangan (ACCEPT / DECLINE) dan memicu
    perhitungan kuorum dinamis pada proposal.
    """
    return respond_invitation_service(
        db=db,
        invitation_id=invitation_id,
        decision=req.decision,
        current_student=current_student,
        reason=req.reason
    )



