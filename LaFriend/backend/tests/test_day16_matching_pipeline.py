"""
test_day16_matching_pipeline.py - Day 16 Test Suite (Suite 18)
==============================================================================
Pengujian Komprehensif Matching Pipeline Orchestrator & Recommendations API (Day 16)

Mencakup:
1. Validasi Skema Pydantic Day 16 (RecommendationRequest, Item, Response)
2. Validasi Pra-Kondisi & Guard Rails Orchestrator (Intent status, User status, min_score, limit)
3. Prinsip Session-First (Session Priority, Threshold Fallback, Absence Fallback, Zero Candidates)
4. Detail Enrichment & Kapasitas Sesi Belajar (Occupied Seats, Schedule, Host/Member Exclusion)
5. Fallback ke Partner Matching (Deduplikasi Multi-Intent per Mahasiswa, Filter Akun & Discoverability)
6. Limit, Peringkat & Penjelasan (Top-N, None, Descending Score, Explanation)
7. Persistensi Database & Atomisitas Transaksi (MatchResult, Breakdown JSON, Purge Stale, Rollback)
8. Integrasi Endpoint FastAPI & Otorisasi HTTP (POST recommendations, GET recommendations, GET results)
==============================================================================
"""

import sys
import json
import math
import uuid
from pathlib import Path
from datetime import datetime, timedelta

# Setup path agar modul app terbaca
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import (
    Student, Course, StudyIntent, IntentAvailability,
    StudySession, SessionSlot, SessionMember, MatchResult
)
from app.schemas import (
    RecommendationRequest, RecommendationItem, RecommendationResponse,
    MatchBreakdown, MatchResultCreate, MatchResultResponse
)
from app.matching import run_matching_pipeline
from app.routes import (
    create_token, hash_password,
    get_current_student, get_recommendations_post,
    get_recommendations_get, get_persisted_match_results
)


def run_tests():
    print("=" * 80)
    print("RUNNING DAY 16: MATCHING PIPELINE ORCHESTRATOR & RECOMMENDATIONS API SUITE")
    print("=" * 80)

    passed_count = 0
    total_count = 0

    def report(name, condition, details=""):
        nonlocal passed_count, total_count
        total_count += 1
        if condition:
            passed_count += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} - {details}")
            assert condition, f"{name}: {details}"

    # Setup isolated in-memory SQLite database
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # =========================================================================
    # SUITE 18.1: Validasi Skema Pydantic Day 16
    # =========================================================================
    print("\n--- SUITE 18.1: Pydantic Validation for Day 16 Schemas ---")

    # 1.1 Request valid dengan default
    req = RecommendationRequest(intent_id="intent-123")
    report("1.1 RecommendationRequest default min_score=60.0 & limit=5", req.min_score == 60.0 and req.limit == 5)

    # 1.2 Tolak intent_id kosong
    try:
        RecommendationRequest(intent_id="   ")
        report("1.2 RecommendationRequest: Tolak intent_id kosong", False)
    except ValidationError:
        report("1.2 RecommendationRequest: Tolak intent_id kosong", True)

    # 1.3 Tolak boolean pada min_score
    try:
        RecommendationRequest(intent_id="int-1", min_score=True)
        report("1.3 RecommendationRequest: Tolak min_score boolean", False)
    except ValidationError:
        report("1.3 RecommendationRequest: Tolak min_score boolean", True)

    # 1.4 Tolak NaN / Inf pada min_score
    try:
        RecommendationRequest(intent_id="int-1", min_score=float("nan"))
        report("1.4 RecommendationRequest: Tolak min_score NaN", False)
    except ValidationError:
        report("1.4 RecommendationRequest: Tolak min_score NaN", True)

    # 1.5 Tolak out-of-range min_score (<0 atau >100)
    try:
        RecommendationRequest(intent_id="int-1", min_score=105.0)
        report("1.5 RecommendationRequest: Tolak min_score > 100", False)
    except ValidationError:
        report("1.5 RecommendationRequest: Tolak min_score > 100", True)

    try:
        RecommendationRequest(intent_id="int-1", min_score=-5.0)
        report("1.5b RecommendationRequest: Tolak min_score < 0", False)
    except ValidationError:
        report("1.5b RecommendationRequest: Tolak min_score < 0", True)

    # 1.6 Tolak boolean pada limit
    try:
        RecommendationRequest(intent_id="int-1", limit=False)
        report("1.6 RecommendationRequest: Tolak limit boolean", False)
    except ValidationError:
        report("1.6 RecommendationRequest: Tolak limit boolean", True)

    # 1.7 Tolak limit < 1
    try:
        RecommendationRequest(intent_id="int-1", limit=0)
        report("1.7 RecommendationRequest: Tolak limit 0", False)
    except ValidationError:
        report("1.7 RecommendationRequest: Tolak limit 0", True)

    # 1.8 Terima limit = None
    req_nolimit = RecommendationRequest(intent_id="int-1", limit=None)
    report("1.8 RecommendationRequest: Terima limit = None", req_nolimit.limit is None)

    # 1.9 Integritas serialisasi RecommendationItem & RecommendationResponse
    b = MatchBreakdown(
        topic_similarity=85.0,
        goal_compatibility=100.0,
        style_compatibility=90.0,
        date_preference=80.0,
        mode_compatibility=100.0,
    )
    item = RecommendationItem(
        rank=1,
        candidate_type="SESSION",
        candidate_session_id="sess-100",
        compatibility_score=89.5,
        breakdown=b,
        explanation="Sangat cocok pada topik pohon biner",
        selected_schedule={"date": "2026-11-20", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120}
    )
    resp = RecommendationResponse(
        intent_id="intent-1",
        course_id="crs-1",
        course_name="Struktur Data",
        match_type="SESSION",
        total_candidates=1,
        recommendations=[item],
        message="Ditemukan 1 rekomendasi"
    )
    report("1.9 RecommendationResponse serialization integrity", resp.total_candidates == 1 and resp.match_type == "SESSION")

    # =========================================================================
    # Persiapan Database Fixtures (Course & Students)
    # =========================================================================
    db = TestingSessionLocal()
    course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1 Teknik Komputer")
    course2 = Course(course_id="crs-kj", course_code="ACK2BAB3", course_name="Keamanan Jaringan", study_program="S1 Teknik Komputer")
    db.add_all([course1, course2])
    db.commit()

    # Mahasiswa Seeker (Andi)
    andi = Student(
        student_id="std-andi",
        full_name="Andi Pratama",
        email="andi@student.telkomuniversity.ac.id",
        student_number="1201250001",
        password_hash=hash_password("pass123"),
        account_status="ACTIVE",
        verification_status="VERIFIED",
        is_discoverable=True
    )
    # Mahasiswa Host Sesi (Budi)
    budi = Student(
        student_id="std-budi",
        full_name="Budi Santoso",
        email="budi@student.telkomuniversity.ac.id",
        student_number="1201250002",
        password_hash=hash_password("pass123"),
        account_status="ACTIVE",
        verification_status="VERIFIED",
        is_discoverable=True
    )
    # Mahasiswa Partner (Citra)
    citra = Student(
        student_id="std-citra",
        full_name="Citra Dewi",
        email="citra@student.telkomuniversity.ac.id",
        student_number="1201250003",
        password_hash=hash_password("pass123"),
        account_status="ACTIVE",
        verification_status="VERIFIED",
        is_discoverable=True
    )
    # Mahasiswa Unverified (Doni)
    doni = Student(
        student_id="std-doni",
        full_name="Doni Kusuma",
        email="doni@student.telkomuniversity.ac.id",
        student_number="1201250004",
        password_hash=hash_password("pass123"),
        account_status="ACTIVE",
        verification_status="UNVERIFIED",
        is_discoverable=True
    )
    # Mahasiswa Suspended (Eka)
    eka = Student(
        student_id="std-eka",
        full_name="Eka Saputra",
        email="eka@student.telkomuniversity.ac.id",
        student_number="1201250005",
        password_hash=hash_password("pass123"),
        account_status="SUSPENDED",
        verification_status="VERIFIED",
        is_discoverable=True
    )
    db.add_all([andi, budi, citra, doni, eka])
    db.commit()

    # Intent Seeker (Andi)
    intent_andi = StudyIntent(
        intent_id="int-andi-1",
        student_id=andi.student_id,
        course_id=course1.course_id,
        topics="Pohon Biner, Binary Search Tree, AVL Tree",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        min_group_size=2,
        max_group_size=4,
        status="ACTIVE"
    )
    db.add(intent_andi)
    db.commit()

    slot_andi = IntentAvailability(
        availability_id="avail-andi-1",
        intent_id=intent_andi.intent_id,
        day_or_date="2026-11-22",
        start_time="09:00",
        end_time="12:00",
        priority_rank=1
    )
    db.add(slot_andi)
    db.commit()

    # =========================================================================
    # SUITE 18.2: Validasi Pra-Kondisi & Guard Rails Orchestrator
    # =========================================================================
    print("\n--- SUITE 18.2: Orchestrator Pre-Condition Validation ---")

    # 2.1 intent is None
    try:
        run_matching_pipeline(intent=None, db=db)
        report("2.1 Tolak intent None", False)
    except ValueError:
        report("2.1 Tolak intent None", True)

    # 2.2 Non-existent intent_id
    try:
        run_matching_pipeline(intent="non-existent-id", db=db)
        report("2.2 Tolak non-existent intent_id", False)
    except ValueError:
        report("2.2 Tolak non-existent intent_id", True)

    # 2.3 Empty string intent_id
    try:
        run_matching_pipeline(intent="  ", db=db)
        report("2.3 Tolak intent_id string kosong", False)
    except ValueError:
        report("2.3 Tolak intent_id string kosong", True)

    # 2.4 Intent status CANCELLED
    intent_cancelled = StudyIntent(
        intent_id="int-cancelled",
        student_id=andi.student_id,
        course_id=course1.course_id,
        topics="Tree",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        status="CANCELLED"
    )
    db.add(intent_cancelled)
    db.commit()
    try:
        run_matching_pipeline(intent=intent_cancelled, db=db)
        report("2.4 Tolak intent CANCELLED", False)
    except ValueError:
        report("2.4 Tolak intent CANCELLED", True)

    # 2.5 Intent status MATCHED
    intent_cancelled.status = "MATCHED"
    db.commit()
    try:
        run_matching_pipeline(intent=intent_cancelled, db=db)
        report("2.5 Tolak intent MATCHED", False)
    except ValueError:
        report("2.5 Tolak intent MATCHED", True)

    # 2.6 Mahasiswa pembuat intent akunnya SUSPENDED
    intent_eka = StudyIntent(
        intent_id="int-eka-1",
        student_id=eka.student_id,
        course_id=course1.course_id,
        topics="Tree",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        status="ACTIVE"
    )
    db.add(intent_eka)
    db.commit()
    try:
        run_matching_pipeline(intent=intent_eka, db=db)
        report("2.6 Tolak mahasiswa SUSPENDED", False)
    except ValueError:
        report("2.6 Tolak mahasiswa SUSPENDED", True)

    # 2.7 Mahasiswa pembuat intent akunnya UNVERIFIED
    intent_doni = StudyIntent(
        intent_id="int-doni-1",
        student_id=doni.student_id,
        course_id=course1.course_id,
        topics="Tree",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        status="ACTIVE"
    )
    db.add(intent_doni)
    db.commit()
    try:
        run_matching_pipeline(intent=intent_doni, db=db)
        report("2.7 Tolak mahasiswa UNVERIFIED", False)
    except ValueError:
        report("2.7 Tolak mahasiswa UNVERIFIED", True)

    # 2.8 Intent tanpa course_id
    intent_no_course = StudyIntent(
        intent_id="int-no-course",
        student_id=andi.student_id,
        course_id="",
        topics="Tree",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        status="ACTIVE"
    )
    try:
        run_matching_pipeline(intent=intent_no_course, db=db)
        report("2.8 Tolak intent tanpa course_id", False)
    except ValueError:
        report("2.8 Tolak intent tanpa course_id", True)

    # 2.9 Tolak min_score boolean di orchestrator
    try:
        run_matching_pipeline(intent=intent_andi, db=db, min_score=True)
        report("2.9 Tolak min_score boolean di orchestrator", False)
    except ValueError:
        report("2.9 Tolak min_score boolean di orchestrator", True)

    # 2.10 Tolak min_score NaN/Inf
    try:
        run_matching_pipeline(intent=intent_andi, db=db, min_score=float("inf"))
        report("2.10 Tolak min_score infinity di orchestrator", False)
    except ValueError:
        report("2.10 Tolak min_score infinity di orchestrator", True)

    # 2.11 Tolak min_score out of range
    try:
        run_matching_pipeline(intent=intent_andi, db=db, min_score=150.0)
        report("2.11 Tolak min_score 150.0", False)
    except ValueError:
        report("2.11 Tolak min_score 150.0", True)

    # 2.12 Tolak limit boolean
    try:
        run_matching_pipeline(intent=intent_andi, db=db, limit=True)
        report("2.12 Tolak limit boolean di orchestrator", False)
    except ValueError:
        report("2.12 Tolak limit boolean di orchestrator", True)

    # 2.13 Tolak limit < 1
    try:
        run_matching_pipeline(intent=intent_andi, db=db, limit=0)
        report("2.13 Tolak limit 0 di orchestrator", False)
    except ValueError:
        report("2.13 Tolak limit 0 di orchestrator", True)

    # 2.14 Intent tanpa jadwal valid menghasilkan match_type NONE
    intent_no_sched = StudyIntent(
        intent_id="int-no-sched",
        student_id=andi.student_id,
        course_id=course1.course_id,
        topics="Tree",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        status="ACTIVE"
    )
    db.add(intent_no_sched)
    db.commit()
    res_no_sched = run_matching_pipeline(intent=intent_no_sched, db=db, persist=False)
    report("2.14 Intent tanpa jadwal menghasilkan match_type NONE", res_no_sched["match_type"] == "NONE" and res_no_sched["total_candidates"] == 0)

    # =========================================================================
    # SUITE 18.3: Prinsip Session-First (Session Priority & Fallbacks)
    # =========================================================================
    print("\n--- SUITE 18.3: Session-First Principle ---")

    # Siapkan StudySession yang valid untuk course1 (Host: Budi)
    sess_budi = StudySession(
        session_id="sess-budi-1",
        host_id=budi.student_id,
        course_id=course1.course_id,
        title="Bedah Latihan Pohon Biner & AVL Tree",
        description="Latihan bersama implementasi struktur data pohon",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        location="Lab Komputer TULT Lt 3",
        min_group_size=2,
        max_group_size=4,
        status="OPEN"
    )
    db.add(sess_budi)
    db.commit()

    slot_budi = SessionSlot(
        slot_id="slot-budi-1",
        session_id=sess_budi.session_id,
        session_date="2026-11-22",
        start_time="09:00",
        end_time="11:00",
        status="APPROVED"
    )
    db.add(slot_budi)
    db.commit()

    # Siapkan juga StudyIntent yang valid untuk course1 (Citra)
    intent_citra = StudyIntent(
        intent_id="int-citra-1",
        student_id=citra.student_id,
        course_id=course1.course_id,
        topics="Struktur Data Pohon Biner dan Graf",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        min_group_size=2,
        max_group_size=4,
        status="ACTIVE"
    )
    db.add(intent_citra)
    db.commit()

    slot_citra = IntentAvailability(
        availability_id="avail-citra-1",
        intent_id=intent_citra.intent_id,
        day_or_date="2026-11-22",
        start_time="09:00",
        end_time="12:00",
        priority_rank=1
    )
    db.add(slot_citra)
    db.commit()

    # 3.1 & 3.2: Session Priority Law - Keduanya ada, WAJIB kembalikan SESSION
    pipeline_res_1 = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
    report("3.1 Session-First: Mengembalikan match_type SESSION saat sesi tersedia", pipeline_res_1["match_type"] == "SESSION")
    report("3.2 Session-First: Seluruh kandidat bertipe SESSION (Partner dilewati)", all(c["candidate_type"] == "SESSION" for c in pipeline_res_1["recommendations"]))
    report("3.3 Session-First: Jumlah kandidat rekomendasi > 0", pipeline_res_1["total_candidates"] >= 1)

    # 3.4 Persistensi DB hanya memuat SESSION
    persisted_matches = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    report("3.4 DB Persistence: Tabel match_results hanya berisi SESSION", len(persisted_matches) > 0 and all(m.candidate_type == "SESSION" for m in persisted_matches))

    # 3.5 Fallback ke Partner Matching saat sesi di bawah min_score
    # Ubah min_score menjadi sangat tinggi (99.9) di mana sesi tidak capai, tapi partner kita mock/test fallback
    pipeline_fallback_high = run_matching_pipeline(intent=intent_andi, db=db, min_score=99.9, limit=5, persist=False)
    # Jika kedua sesi dan partner di bawah 99.9 -> NONE
    report("3.5 Fallback Threshold: Jika tidak ada yang capai 99.9, match_type NONE", pipeline_fallback_high["match_type"] == "NONE")

    # 3.6 Fallback saat Sesi Ditutup (Status CLOSED)
    sess_budi.status = "COMPLETED"
    db.commit()

    pipeline_res_partner = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
    report("3.6 Fallback: Otomatis beralih ke PARTNER saat sesi tidak OPEN", pipeline_res_partner["match_type"] == "PARTNER")
    report("3.7 Fallback: Kandidat rekomendasi bertipe PARTNER", all(c["candidate_type"] == "PARTNER" for c in pipeline_res_partner["recommendations"]))
    report("3.8 Fallback: Target intent menunjuk ke Citra", pipeline_res_partner["recommendations"][0]["target_intent_id"] == intent_citra.intent_id)

    # Kembalikan status sesi budi ke OPEN untuk pengujian berikutnya
    sess_budi.status = "OPEN"
    db.commit()

    # =========================================================================
    # SUITE 18.4: Session Matching Detail Enrichment & Capacity Logic
    # =========================================================================
    print("\n--- SUITE 18.4: Session Detail Enrichment & Capacity Logic ---")

    sess_run = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
    first_sess_rec = sess_run["recommendations"][0]

    # 4.1 Detail Sesi Lengkap
    s_details = first_sess_rec.get("session_details")
    report("4.1 session_details populated", s_details is not None)
    report("4.2 session title matches", s_details.get("title") == sess_budi.title)
    report("4.3 session host_name matches Budi", s_details.get("host_name") == "Budi Santoso")
    report("4.4 session occupied_seats is 1 (Host)", s_details.get("occupied_seats") == 1)

    # 4.5 Selected schedule details
    sched = first_sess_rec.get("selected_schedule")
    report("4.5 selected_schedule contains date & time", sched.get("date") == "2026-11-22" and sched.get("duration_minutes") == 120)

    # 4.6 Kapasitas: Tambahkan anggota ke sesi Budi
    member_citra = SessionMember(
        member_id="mem-citra-1",
        session_id=sess_budi.session_id,
        student_id=citra.student_id,
        role="MEMBER",
        status="ACCEPTED"
    )
    db.add(member_citra)
    db.commit()

    sess_run_2 = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
    s_details_2 = sess_run_2["recommendations"][0].get("session_details")
    report("4.6 occupied_seats is 2 after Citra accepted", s_details_2.get("occupied_seats") == 2)

    # 4.7 Sesi Penuh: max_group_size = 2, occupied = 2 -> Harus tereksklusi dari rekomendasi
    sess_budi.max_group_size = 2
    db.commit()
    # Karena sesi penuh, harus fallback ke PARTNER!
    sess_full_run = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
    report("4.7 Sesi penuh tereksklusi -> fallback ke PARTNER", sess_full_run["match_type"] == "PARTNER")

    # Kembalikan max_group_size ke 4
    sess_budi.max_group_size = 4
    db.commit()

    # 4.8 Andi sudah jadi member di sesi -> Sesi harus tereksklusi
    member_andi = SessionMember(
        member_id="mem-andi-1",
        session_id=sess_budi.session_id,
        student_id=andi.student_id,
        role="MEMBER",
        status="ACCEPTED"
    )
    db.add(member_andi)
    db.commit()
    # Karena Andi sudah jadi member di sesi budi, sesi budi tereksklusi -> fallback ke PARTNER!
    sess_member_run = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
    report("4.8 Mahasiswa sudah menjadi anggota sesi -> tereksklusi -> fallback ke PARTNER", sess_member_run["match_type"] == "PARTNER")

    # Bersihkan membership Andi
    db.delete(member_andi)
    db.commit()

    # =========================================================================
    # SUITE 18.5: Partner Matching Fallback & Deduplikasi Multi-Intent
    # =========================================================================
    print("\n--- SUITE 18.5: Partner Matching & Multi-Intent Deduplication ---")

    # Tutup sesi budi sementara agar selalu masuk ke jalur PARTNER
    sess_budi.status = "COMPLETED"
    db.commit()

    # Buat intent kedua untuk Citra pada mata kuliah yang sama tapi topik berbeda/skor berbeda
    intent_citra_2 = StudyIntent(
        intent_id="int-citra-2",
        student_id=citra.student_id,
        course_id=course1.course_id,
        topics="Pohon Biner, Binary Search Tree, AVL Tree, Red-Black Tree",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        min_group_size=2,
        max_group_size=4,
        status="ACTIVE"
    )
    db.add(intent_citra_2)
    db.commit()

    slot_citra_2 = IntentAvailability(
        availability_id="avail-citra-2",
        intent_id=intent_citra_2.intent_id,
        day_or_date="2026-11-22",
        start_time="09:00",
        end_time="12:00",
        priority_rank=1
    )
    db.add(slot_citra_2)
    db.commit()

    # Jalankan matching
    partner_run = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
    report("5.1 Partner Matching berhasil", partner_run["match_type"] == "PARTNER")

    # Periksa deduplikasi: Citra memiliki 2 intent, tapi hanya 1 yang muncul di rekomendasi
    citra_recs = [r for r in partner_run["recommendations"] if r.get("partner_details", {}).get("student_id") == citra.student_id]
    report("5.2 Deduplikasi multi-intent: Hanya 1 rekomendasi per mahasiswa (Citra)", len(citra_recs) == 1)

    # Pastikan yang terpilih adalah intent yang memiliki topik lebih mirip (int-citra-2)
    report("5.3 Mempertahankan intent terbaik mahasiswa", citra_recs[0]["target_intent_id"] == intent_citra_2.intent_id)

    # 5.4 Partner detail enrichment
    p_details = citra_recs[0]["partner_details"]
    report("5.4 partner_details populated with name", p_details.get("student_name") == "Citra Dewi")
    report("5.5 partner_details study_program", p_details.get("study_program") == "S1 Teknik Komputer")

    # 5.6 Mahasiswa unverified tidak muncul di rekomendasi
    # Doni adalah unverified
    intent_doni_2 = StudyIntent(
        intent_id="int-doni-valid",
        student_id=doni.student_id,
        course_id=course1.course_id,
        topics="Pohon Biner",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        status="ACTIVE"
    )
    db.add(intent_doni_2)
    db.commit()
    slot_doni_2 = IntentAvailability(
        availability_id="avail-doni-2",
        intent_id=intent_doni_2.intent_id,
        day_or_date="2026-11-22",
        start_time="09:00",
        end_time="12:00",
        priority_rank=1
    )
    db.add(slot_doni_2)
    db.commit()

    partner_run_unver = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
    has_doni = any(r.get("partner_details", {}).get("student_id") == doni.student_id for r in partner_run_unver["recommendations"])
    report("5.6 Mahasiswa UNVERIFIED (Doni) tereksklusi dari Partner Matching", not has_doni)

    # 5.7 Mahasiswa non-discoverable tidak muncul di rekomendasi
    citra.is_discoverable = False
    db.commit()
    partner_run_nodisc = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
    has_citra = any(r.get("partner_details", {}).get("student_id") == citra.student_id for r in partner_run_nodisc["recommendations"])
    report("5.7 Mahasiswa is_discoverable=False tereksklusi dari Partner Matching", not has_citra)
    citra.is_discoverable = True
    db.commit()

    # =========================================================================
    # SUITE 18.6: Limit, Peringkat & Penjelasan (Ranking & Explanations)
    # =========================================================================
    print("\n--- SUITE 18.6: Limit, Ranking & Explanations ---")

    # Buka kembali sesi budi dan buat sesi kedua (Host: Citra)
    sess_budi.status = "OPEN"
    sess_citra = StudySession(
        session_id="sess-citra-1",
        host_id=citra.student_id,
        course_id=course1.course_id,
        title="Diskusi Santai Teori Tree",
        description="Diskusi konsep pohon",
        learning_goal="UNDERSTAND",
        collaboration_style="PEER_TUTORING",
        learning_mode="OFFLINE",
        min_group_size=2,
        max_group_size=4,
        status="OPEN"
    )
    db.add(sess_citra)
    db.commit()
    slot_citra_sess = SessionSlot(
        slot_id="slot-citra-sess",
        session_id=sess_citra.session_id,
        session_date="2026-11-22",
        start_time="09:00",
        end_time="11:00",
        status="APPROVED"
    )
    db.add(slot_citra_sess)
    db.commit()

    # Jalankan dengan limit=1
    res_lim1 = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=1, persist=False)
    report("6.1 limit=1 menghasilkan tepat 1 rekomendasi", len(res_lim1["recommendations"]) == 1)
    report("6.2 Rekomendasi pertama memiliki rank 1", res_lim1["recommendations"][0]["rank"] == 1)

    # Jalankan dengan limit=None (semua yang lolos)
    res_lim_none = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=None, persist=False)
    report("6.3 limit=None mengembalikan seluruh kandidat yang lolos (>=2)", len(res_lim_none["recommendations"]) >= 2)

    # Verifikasi pengurutan skor menurun
    scores = [r["compatibility_score"] for r in res_lim_none["recommendations"]]
    report("6.4 Rekomendasi diurutkan menurun berdasarkan compatibility_score", scores == sorted(scores, reverse=True))

    # Verifikasi keberadaan kalimat penjelasan (explanation)
    report("6.5 Penjelasan kalimat (explanation) tersedia", len(res_lim_none["recommendations"][0]["explanation"]) > 10)

    # =========================================================================
    # SUITE 18.7: Persistensi Database & Atomisitas Transaksi (MatchResult)
    # =========================================================================
    print("\n--- SUITE 18.7: Database Persistence & Transactional Atomicity ---")

    # Jalankan dengan persist=True
    run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)
    rows_in_db = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    report("7.1 MatchResult tersimpan di tabel match_results", len(rows_in_db) >= 2)

    # Validasi breakdown_json dapat didekode dan memuat 5 komponen resmi
    first_row = rows_in_db[0]
    bd_dict = json.loads(first_row.breakdown_json)
    req_components = {"topic_similarity", "goal_compatibility", "style_compatibility", "date_preference", "mode_compatibility"}
    report("7.2 breakdown_json memuat tepat 5 komponen kompatibilitas", set(bd_dict.keys()) == req_components)

    # Verifikasi pembersihan hasil lama saat matching dijalankan ulang
    old_ids = {r.match_id for r in rows_in_db}
    run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)
    new_rows = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    new_ids = {r.match_id for r in new_rows}
    report("7.3 Menjalankan matching ulang memperbarui rekaman dan membersihkan ID lama", len(old_ids.intersection(new_ids)) == 0)

    # Verifikasi persist=False tidak mengubah database
    count_before = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).count()
    run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=False)
    count_after = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).count()
    report("7.4 persist=False tidak memodifikasi rekaman di database", count_before == count_after)

    # =========================================================================
    # SUITE 18.8: Integrasi Endpoint FastAPI & Otorisasi HTTP
    # =========================================================================
    print("\n--- SUITE 18.8: FastAPI Recommendations API Endpoints ---")

    token_andi = create_token(andi.student_id, andi.email)
    token_budi = create_token(budi.student_id, budi.email)
    token_doni = create_token(doni.student_id, doni.email)

    # 8.1 401 Unauthorized tanpa header otentikasi
    try:
        get_current_student(authorization=None, db=db)
        report("8.1 Endpoint Auth: 401 Unauthorized tanpa token", False)
    except HTTPException as e:
        report("8.1 Endpoint Auth: 401 Unauthorized tanpa token", e.status_code == 401)

    # 8.2 401 Unauthorized dengan token rusak
    try:
        get_current_student(authorization="Bearer token_rusak_123", db=db)
        report("8.2 Endpoint Auth: 401 Unauthorized dengan token invalid", False)
    except HTTPException as e:
        report("8.2 Endpoint Auth: 401 Unauthorized dengan token invalid", e.status_code == 401)

    # 8.3 403 Forbidden meminta rekomendasi untuk intent milik mahasiswa lain
    try:
        req_other = RecommendationRequest(intent_id=intent_andi.intent_id)
        get_recommendations_post(req=req_other, current_student=budi, db=db)
        report("8.3 POST recommendations: 403 Forbidden untuk intent milik orang lain", False)
    except HTTPException as e:
        report("8.3 POST recommendations: 403 Forbidden untuk intent milik orang lain", e.status_code == 403)

    # 8.4 404 Not Found untuk intent_id fiktif
    try:
        req_fiktif = RecommendationRequest(intent_id="non-existent-intent-uuid")
        get_recommendations_post(req=req_fiktif, current_student=andi, db=db)
        report("8.4 POST recommendations: 404 Not Found untuk intent fiktif", False)
    except HTTPException as e:
        report("8.4 POST recommendations: 404 Not Found untuk intent fiktif", e.status_code == 404)

    # 8.5 400 Bad Request untuk intent CANCELLED
    try:
        req_cancelled = RecommendationRequest(intent_id=intent_cancelled.intent_id)
        get_recommendations_post(req=req_cancelled, current_student=andi, db=db)
        report("8.5 POST recommendations: 400 Bad Request untuk intent tidak aktif", False)
    except HTTPException as e:
        report("8.5 POST recommendations: 400 Bad Request untuk intent tidak aktif", e.status_code == 400)

    # 8.6 403 Forbidden untuk mahasiswa UNVERIFIED
    intent_doni_valid = StudyIntent(
        intent_id="int-doni-active",
        student_id=doni.student_id,
        course_id=course1.course_id,
        topics="Kalkulus",
        learning_goal="PRACTICE",
        collaboration_style="DISCUSSION",
        learning_mode="OFFLINE",
        earliest_date="2026-11-20",
        latest_date="2026-11-25",
        status="ACTIVE"
    )
    db.add(intent_doni_valid)
    db.commit()
    try:
        req_unver = RecommendationRequest(intent_id=intent_doni_valid.intent_id)
        get_recommendations_post(req=req_unver, current_student=doni, db=db)
        report("8.6 POST recommendations: 403 Forbidden untuk akun UNVERIFIED", False)
    except HTTPException as e:
        report("8.6 POST recommendations: 403 Forbidden untuk akun UNVERIFIED", e.status_code == 403)

    # 8.7 200 OK POST recommendations Session-First berhasil
    req_ok = RecommendationRequest(intent_id=intent_andi.intent_id, min_score=50.0, limit=3)
    resp_ok = get_recommendations_post(req=req_ok, current_student=andi, db=db)
    report("8.7 POST recommendations: Sukses dengan Session-First match", resp_ok.get("match_type") == "SESSION")
    report("8.8 POST recommendations: Payload response memuat recommendations list", len(resp_ok.get("recommendations", [])) >= 1)

    # 8.9 200 OK GET /study-intents/{intent_id}/recommendations shortcut
    resp_get = get_recommendations_get(intent_id=intent_andi.intent_id, min_score=50.0, limit=3, current_student=andi, db=db)
    report("8.9 GET study-intents recommendations shortcut sukses", resp_get.get("match_type") == "SESSION")

    # 8.10 200 OK GET /matching/results/{intent_id}
    resp_results = get_persisted_match_results(intent_id=intent_andi.intent_id, current_student=andi, db=db)
    report("8.10 GET matching/results: Sukses mengembalikan daftar MatchResult tersimpan", len(resp_results) >= 1)

    # 8.11 403 Forbidden GET /matching/results/{intent_id} untuk mahasiswa lain
    try:
        get_persisted_match_results(intent_id=intent_andi.intent_id, current_student=budi, db=db)
        report("8.11 GET matching/results: 403 Forbidden untuk mahasiswa lain", False)
    except HTTPException as e:
        report("8.11 GET matching/results: 403 Forbidden untuk mahasiswa lain", e.status_code == 403)

    db.close()

    print("\n" + "=" * 80)
    print(f"DAY 16 TEST SUITE RESULT: {passed_count} / {total_count} PASSED (100%)")
    print("=" * 80)
    return passed_count, total_count


if __name__ == "__main__":
    passed, total = run_tests()
    if passed != total:
        sys.exit(1)
