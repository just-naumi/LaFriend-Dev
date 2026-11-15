"""
test_day16_matching_pipeline.py - Day 16 Test Suite (Suite 18)
==============================================================================
Pengujian Komprehensif Matching Pipeline Orchestrator & Recommendations API (Day 16)
Dapat dijalankan secara independen melalui:
1. `pytest tests/test_day16_matching_pipeline.py`
2. `py tests/test_day16_matching_pipeline.py`

Mencakup:
1. Validasi Skema Pydantic Day 16 (RecommendationRequest, Item, Response)
2. Validasi Pra-Kondisi & Guard Rails Orchestrator (Intent status, User status, min_score, limit)
3. Prinsip Session-First (Session Priority, Threshold Fallback, Absence Fallback, Zero Candidates)
4. Detail Enrichment & Kapasitas Sesi Belajar (Occupied Seats, Schedule, Host/Member Exclusion)
5. Fallback ke Partner Matching (Deduplikasi Multi-Intent per Mahasiswa, Filter Akun & Discoverability)
6. Limit, Peringkat & Penjelasan (Top-N, None, Descending Score, Explanation)
7. Persistensi Database & Atomisitas Transaksi (MatchResult, Breakdown JSON, Purge Stale, Mid-Pipeline Failure Rollback)
8. Integrasi Endpoint FastAPI Sebenarnya via TestClient & Otorisasi HTTP (POST recommendations, GET read-only, GET results)
==============================================================================
"""

import sys
import json
import math
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

# Setup path agar modul backend terbaca
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import Base, get_db
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
from app.main import app


def create_test_db():
    """Membuat database in-memory terisolasi yang dapat diakses bersama oleh seluruh thread TestClient."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, TestingSession


# =============================================================================
# SUITE 18.1: Validasi Skema Pydantic Day 16
# =============================================================================
def test_recommendation_request_pydantic_validation():
    # 1.1 Request valid dengan default
    req = RecommendationRequest(intent_id="intent-123")
    assert req.min_score == 60.0 and req.limit == 5, "Default min_score dan limit harus 60.0 dan 5"

    # 1.2 Tolak intent_id kosong
    try:
        RecommendationRequest(intent_id="   ")
        assert False, "Harus menolak intent_id kosong"
    except ValidationError:
        pass

    # 1.3 Tolak boolean pada min_score
    try:
        RecommendationRequest(intent_id="int-1", min_score=True)
        assert False, "Harus menolak min_score boolean"
    except ValidationError:
        pass

    # 1.4 Tolak NaN / Inf pada min_score
    try:
        RecommendationRequest(intent_id="int-1", min_score=float("nan"))
        assert False, "Harus menolak min_score NaN"
    except ValidationError:
        pass

    # 1.5 Tolak out-of-range min_score (<0 atau >100)
    try:
        RecommendationRequest(intent_id="int-1", min_score=105.0)
        assert False, "Harus menolak min_score > 100"
    except ValidationError:
        pass

    try:
        RecommendationRequest(intent_id="int-1", min_score=-5.0)
        assert False, "Harus menolak min_score < 0"
    except ValidationError:
        pass

    # 1.6 Tolak boolean pada limit
    try:
        RecommendationRequest(intent_id="int-1", limit=False)
        assert False, "Harus menolak limit boolean"
    except ValidationError:
        pass

    # 1.7 Tolak limit < 1
    try:
        RecommendationRequest(intent_id="int-1", limit=0)
        assert False, "Harus menolak limit 0"
    except ValidationError:
        pass

    # 1.8 Terima limit = None
    req_nolimit = RecommendationRequest(intent_id="int-1", limit=None)
    assert req_nolimit.limit is None, "Harus menerima limit = None"

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
    assert resp.total_candidates == 1 and resp.match_type == "SESSION", "Serialisasi response harus valid"


# =============================================================================
# SUITE 18.2: Validasi Pra-Kondisi & Guard Rails Orchestrator
# =============================================================================
def test_orchestrator_preconditions_and_guard_rails():
    _, TestingSession = create_test_db()
    db = TestingSession()

    c1 = Course(course_id="crs-1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
    andi = Student(
        student_id="std-andi", full_name="Andi", email="andi@t.ac.id", student_number="1201",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    eka = Student(
        student_id="std-eka", full_name="Eka", email="eka@t.ac.id", student_number="1202",
        password_hash=hash_password("p"), account_status="SUSPENDED", verification_status="VERIFIED", is_discoverable=True
    )
    doni = Student(
        student_id="std-doni", full_name="Doni", email="doni@t.ac.id", student_number="1203",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="UNVERIFIED", is_discoverable=True
    )
    db.add_all([c1, andi, eka, doni])
    db.commit()

    intent_andi = StudyIntent(
        intent_id="int-andi-1", student_id=andi.student_id, course_id=c1.course_id,
        topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    db.add(intent_andi)
    db.commit()

    # 2.1 intent is None
    try:
        run_matching_pipeline(intent=None, db=db)
        assert False
    except ValueError:
        pass

    # 2.2 Non-existent intent_id
    try:
        run_matching_pipeline(intent="non-existent-id", db=db)
        assert False
    except ValueError:
        pass

    # 2.3 Empty string intent_id
    try:
        run_matching_pipeline(intent="  ", db=db)
        assert False
    except ValueError:
        pass

    # 2.4 Intent status CANCELLED
    intent_andi.status = "CANCELLED"
    db.commit()
    try:
        run_matching_pipeline(intent=intent_andi, db=db)
        assert False
    except ValueError:
        pass

    # 2.5 Intent status MATCHED
    intent_andi.status = "MATCHED"
    db.commit()
    try:
        run_matching_pipeline(intent=intent_andi, db=db)
        assert False
    except ValueError:
        pass

    intent_andi.status = "ACTIVE"
    db.commit()

    # 2.6 Mahasiswa pembuat intent akunnya SUSPENDED
    intent_eka = StudyIntent(
        intent_id="int-eka-1", student_id=eka.student_id, course_id=c1.course_id,
        topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    db.add(intent_eka)
    db.commit()
    try:
        run_matching_pipeline(intent=intent_eka, db=db)
        assert False
    except ValueError:
        pass

    # 2.7 Mahasiswa pembuat intent akunnya UNVERIFIED
    intent_doni = StudyIntent(
        intent_id="int-doni-1", student_id=doni.student_id, course_id=c1.course_id,
        topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    db.add(intent_doni)
    db.commit()
    try:
        run_matching_pipeline(intent=intent_doni, db=db)
        assert False
    except ValueError:
        pass

    # 2.8 Intent tanpa course_id
    intent_no_course = StudyIntent(
        intent_id="int-no-course", student_id=andi.student_id, course_id="",
        topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    try:
        run_matching_pipeline(intent=intent_no_course, db=db)
        assert False
    except ValueError:
        pass

    # 2.9 Tolak min_score boolean
    try:
        run_matching_pipeline(intent=intent_andi, db=db, min_score=True)
        assert False
    except ValueError:
        pass

    # 2.10 Tolak min_score infinity
    try:
        run_matching_pipeline(intent=intent_andi, db=db, min_score=float("inf"))
        assert False
    except ValueError:
        pass

    # 2.11 Tolak min_score out-of-range (150.0)
    try:
        run_matching_pipeline(intent=intent_andi, db=db, min_score=150.0)
        assert False
    except ValueError:
        pass

    # 2.12 Tolak limit boolean
    try:
        run_matching_pipeline(intent=intent_andi, db=db, limit=True)
        assert False
    except ValueError:
        pass

    # 2.13 Tolak limit 0
    try:
        run_matching_pipeline(intent=intent_andi, db=db, limit=0)
        assert False
    except ValueError:
        pass

    # 2.14 Intent tanpa jadwal menghasilkan match_type NONE
    res_no_sched = run_matching_pipeline(intent=intent_andi, db=db, persist=False)
    assert res_no_sched["match_type"] == "NONE" and res_no_sched["total_candidates"] == 0
    db.close()


# =============================================================================
# SUITE 18.3: Prinsip Session-First & Fallback Logic
# =============================================================================
def test_session_first_and_partner_fallback():
    _, TestingSession = create_test_db()
    db = TestingSession()

    course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
    andi = Student(
        student_id="std-andi", full_name="Andi", email="andi@t.ac.id", student_number="1201",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    budi = Student(
        student_id="std-budi", full_name="Budi", email="budi@t.ac.id", student_number="1202",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    citra = Student(
        student_id="std-citra", full_name="Citra", email="citra@t.ac.id", student_number="1203",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    db.add_all([course1, andi, budi, citra])
    db.commit()

    intent_andi = StudyIntent(
        intent_id="int-andi-1", student_id=andi.student_id, course_id=course1.course_id,
        topics="Pohon Biner, Binary Search Tree, AVL Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=4, status="ACTIVE"
    )
    slot_andi = IntentAvailability(
        availability_id="avail-andi-1", intent_id=intent_andi.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    db.add_all([intent_andi, slot_andi])
    db.commit()

    # Sesi Budi (Course 1, Offline, Approved Slot 22 Nov)
    sess_budi = StudySession(
        session_id="sess-budi-1", host_id=budi.student_id, course_id=course1.course_id,
        title="Latihan Pohon Biner & AVL", description="Latihan soal",
        learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE",
        location="Lab Komputer", min_group_size=2, max_group_size=4, status="OPEN"
    )
    slot_budi = SessionSlot(
        slot_id="slot-budi-1", session_id=sess_budi.session_id,
        session_date="2026-11-22", start_time="09:00", end_time="11:00", status="APPROVED"
    )
    db.add_all([sess_budi, slot_budi])

    # Intent Citra (Course 1, Offline, Slot 22 Nov)
    intent_citra = StudyIntent(
        intent_id="int-citra-1", student_id=citra.student_id, course_id=course1.course_id,
        topics="Struktur Data Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=4, status="ACTIVE"
    )
    slot_citra = IntentAvailability(
        availability_id="avail-citra-1", intent_id=intent_citra.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    db.add_all([intent_citra, slot_citra])
    db.commit()

    # 3.1 & 3.2: Keduanya ada -> Wajib kembalikan SESSION
    pipeline_res = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
    assert pipeline_res["match_type"] == "SESSION", "Harus memprioritaskan SESSION"
    assert all(c["candidate_type"] == "SESSION" for c in pipeline_res["recommendations"]), "Semua kandidat harus SESSION"
    assert pipeline_res["total_candidates"] >= 1, "Kandidat sesi harus ditemukan"

    # 3.4 Persistensi DB hanya memuat SESSION
    persisted = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    assert len(persisted) >= 1 and all(m.candidate_type == "SESSION" for m in persisted)

    # 3.5 Fallback Threshold saat skor di bawah 99.9
    res_high = run_matching_pipeline(intent=intent_andi, db=db, min_score=99.9, limit=5, persist=False)
    assert res_high["match_type"] == "NONE", "Tidak ada kandidat mencapai 99.9"

    # 3.6 Fallback saat Sesi Ditutup (COMPLETED)
    sess_budi.status = "COMPLETED"
    db.commit()

    res_partner = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
    assert res_partner["match_type"] == "PARTNER", "Harus fallback ke PARTNER"
    assert all(c["candidate_type"] == "PARTNER" for c in res_partner["recommendations"])
    assert res_partner["recommendations"][0]["target_intent_id"] == intent_citra.intent_id
    db.close()


# =============================================================================
# SUITE 18.4: Session Matching Detail Enrichment & Capacity Logic
# =============================================================================
def test_session_detail_enrichment_and_capacity():
    _, TestingSession = create_test_db()
    db = TestingSession()

    course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
    andi = Student(
        student_id="std-andi", full_name="Andi", email="andi@t.ac.id", student_number="1201",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    budi = Student(
        student_id="std-budi", full_name="Budi Santoso", email="budi@t.ac.id", student_number="1202",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    citra = Student(
        student_id="std-citra", full_name="Citra", email="citra@t.ac.id", student_number="1203",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    db.add_all([course1, andi, budi, citra])
    db.commit()

    intent_andi = StudyIntent(
        intent_id="int-andi-1", student_id=andi.student_id, course_id=course1.course_id,
        topics="Pohon Biner, AVL Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=4, status="ACTIVE"
    )
    slot_andi = IntentAvailability(
        availability_id="avail-andi-1", intent_id=intent_andi.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    sess_budi = StudySession(
        session_id="sess-budi-1", host_id=budi.student_id, course_id=course1.course_id,
        title="Latihan Pohon Biner", description="Diskusi dan koding",
        learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE",
        location="Lab Komputer TULT", min_group_size=2, max_group_size=4, status="OPEN"
    )
    slot_budi = SessionSlot(
        slot_id="slot-budi-1", session_id=sess_budi.session_id,
        session_date="2026-11-22", start_time="09:00", end_time="11:00", status="APPROVED"
    )
    db.add_all([intent_andi, slot_andi, sess_budi, slot_budi])
    db.commit()

    res = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
    rec = res["recommendations"][0]

    # 4.1 session_details populated
    s_det = rec["session_details"]
    assert s_det is not None
    assert s_det["title"] == sess_budi.title
    assert s_det["host_name"] == "Budi Santoso"
    assert s_det["occupied_seats"] == 1, "Hanya host yang menempati kursi awal"

    # 4.5 selected_schedule populated
    sched = rec["selected_schedule"]
    assert sched["date"] == "2026-11-22" and sched["duration_minutes"] == 120

    # 4.6 Kapasitas: Tambahkan Citra sebagai anggota ACCEPTED
    mem_citra = SessionMember(
        member_id="mem-c-1", session_id=sess_budi.session_id, student_id=citra.student_id,
        role="MEMBER", status="ACCEPTED"
    )
    db.add(mem_citra)
    db.commit()

    res_2 = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
    assert res_2["recommendations"][0]["session_details"]["occupied_seats"] == 2

    # 4.7 Sesi Penuh (max_group_size=2, occupied=2) -> Harus tereksklusi
    sess_budi.max_group_size = 2
    db.commit()
    res_full = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
    assert res_full["match_type"] == "NONE", "Sesi penuh harus tereksklusi"
    sess_budi.max_group_size = 4
    db.commit()

    # 4.8 Andi sudah jadi member di sesi budi -> Harus tereksklusi
    mem_andi = SessionMember(
        member_id="mem-a-1", session_id=sess_budi.session_id, student_id=andi.student_id,
        role="MEMBER", status="ACCEPTED"
    )
    db.add(mem_andi)
    db.commit()
    res_mem = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
    assert res_mem["match_type"] == "NONE", "Sesi di mana mahasiswa sudah bergabung harus tereksklusi"
    db.close()


# =============================================================================
# SUITE 18.5: Partner Matching Fallback & Deduplikasi Multi-Intent
# =============================================================================
def test_partner_deduplication_and_student_filters():
    _, TestingSession = create_test_db()
    db = TestingSession()

    course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
    andi = Student(
        student_id="std-andi", full_name="Andi", email="andi@t.ac.id", student_number="1201",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    citra = Student(
        student_id="std-citra", full_name="Citra Dewi", email="citra@t.ac.id", student_number="1203",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    doni = Student(
        student_id="std-doni", full_name="Doni", email="doni@t.ac.id", student_number="1204",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="UNVERIFIED", is_discoverable=True
    )
    db.add_all([course1, andi, citra, doni])
    db.commit()

    intent_andi = StudyIntent(
        intent_id="int-andi-1", student_id=andi.student_id, course_id=course1.course_id,
        topics="Pohon Biner, Binary Search Tree, AVL Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    slot_andi = IntentAvailability(
        availability_id="avail-andi-1", intent_id=intent_andi.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    db.add_all([intent_andi, slot_andi])
    db.commit()

    # Citra memiliki 2 intent pada Course yang sama (Topik berbeda)
    intent_citra_1 = StudyIntent(
        intent_id="int-citra-low", student_id=citra.student_id, course_id=course1.course_id,
        topics="Pengenalan Graph", learning_goal="UNDERSTAND", collaboration_style="PEER_TUTORING",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    slot_c1 = IntentAvailability(
        availability_id="avail-c1", intent_id=intent_citra_1.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    intent_citra_2 = StudyIntent(
        intent_id="int-citra-high", student_id=citra.student_id, course_id=course1.course_id,
        topics="Pohon Biner, Binary Search Tree, AVL Tree, Red-Black Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    slot_c2 = IntentAvailability(
        availability_id="avail-c2", intent_id=intent_citra_2.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    db.add_all([intent_citra_1, slot_c1, intent_citra_2, slot_c2])
    db.commit()

    # Jalankan matching
    res = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)
    assert res["match_type"] == "PARTNER"

    # 5.2 Deduplikasi multi-intent: Hanya 1 rekomendasi untuk Citra
    recs_citra = [r for r in res["recommendations"] if r.get("partner_details", {}).get("student_id") == citra.student_id]
    assert len(recs_citra) == 1, "Harus dideduplikasi menjadi tepat 1 per mahasiswa"
    assert recs_citra[0]["target_intent_id"] == "int-citra-high", "Harus mempertahankan intent terbaik"

    # 5.4 Detail enrichment partner
    p_det = recs_citra[0]["partner_details"]
    assert p_det["student_name"] == "Citra Dewi"

    # 5.6 Doni (UNVERIFIED) tidak boleh lolos
    intent_doni = StudyIntent(
        intent_id="int-doni-1", student_id=doni.student_id, course_id=course1.course_id,
        topics="Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    slot_d = IntentAvailability(
        availability_id="avail-d1", intent_id=intent_doni.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    db.add_all([intent_doni, slot_d])
    db.commit()

    res_unver = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=False)
    assert not any(r.get("partner_details", {}).get("student_id") == doni.student_id for r in res_unver["recommendations"])

    # 5.7 Citra non-discoverable tidak boleh lolos
    citra.is_discoverable = False
    db.commit()
    res_nodisc = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=False)
    assert not any(r.get("partner_details", {}).get("student_id") == citra.student_id for r in res_nodisc["recommendations"])
    db.close()


# =============================================================================
# SUITE 18.6: Limit, Ranking & Explanations
# =============================================================================
def test_limit_ranking_and_explanations():
    _, TestingSession = create_test_db()
    db = TestingSession()

    course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
    andi = Student(
        student_id="std-andi", full_name="Andi", email="andi@t.ac.id", student_number="1201",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    budi = Student(
        student_id="std-budi", full_name="Budi", email="budi@t.ac.id", student_number="1202",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    citra = Student(
        student_id="std-citra", full_name="Citra", email="citra@t.ac.id", student_number="1203",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    db.add_all([course1, andi, budi, citra])
    db.commit()

    intent_andi = StudyIntent(
        intent_id="int-andi-1", student_id=andi.student_id, course_id=course1.course_id,
        topics="Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    slot_andi = IntentAvailability(
        availability_id="avail-andi-1", intent_id=intent_andi.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    # Sesi 1 Budi
    s1 = StudySession(
        session_id="s1", host_id=budi.student_id, course_id=course1.course_id,
        title="Latihan Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", min_group_size=2, max_group_size=4, status="OPEN"
    )
    slot1 = SessionSlot(slot_id="slot1", session_id="s1", session_date="2026-11-22", start_time="09:00", end_time="11:00", status="APPROVED")
    # Sesi 2 Citra
    s2 = StudySession(
        session_id="s2", host_id=citra.student_id, course_id=course1.course_id,
        title="Teori Pohon Biner", learning_goal="UNDERSTAND", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", min_group_size=2, max_group_size=4, status="OPEN"
    )
    slot2 = SessionSlot(slot_id="slot2", session_id="s2", session_date="2026-11-22", start_time="09:00", end_time="11:00", status="APPROVED")
    db.add_all([intent_andi, slot_andi, s1, slot1, s2, slot2])
    db.commit()

    # 6.1 limit=1 menghasilkan tepat 1 rekomendasi berperingkat 1
    res_lim1 = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=1, persist=False)
    assert len(res_lim1["recommendations"]) == 1
    assert res_lim1["recommendations"][0]["rank"] == 1

    # 6.3 limit=None mengembalikan seluruh kandidat
    res_none = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=None, persist=False)
    assert len(res_none["recommendations"]) == 2

    # 6.4 Diurutkan menurun berdasarkan compatibility_score
    scores = [r["compatibility_score"] for r in res_none["recommendations"]]
    assert scores == sorted(scores, reverse=True)

    # 6.5 Explanation tersedia dan informatif
    assert len(res_none["recommendations"][0]["explanation"]) > 10
    db.close()


# =============================================================================
# SUITE 18.7: Database Persistence & Atomic Rollback under Mid-Pipeline Failure
# =============================================================================
def test_persistence_and_atomic_rollback_on_mid_pipeline_failure():
    _, TestingSession = create_test_db()
    db = TestingSession()

    course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
    andi = Student(
        student_id="std-andi", full_name="Andi", email="andi@t.ac.id", student_number="1201",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    budi = Student(
        student_id="std-budi", full_name="Budi", email="budi@t.ac.id", student_number="1202",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    db.add_all([course1, andi, budi])
    db.commit()

    intent_andi = StudyIntent(
        intent_id="int-andi-1", student_id=andi.student_id, course_id=course1.course_id,
        topics="Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    slot_andi = IntentAvailability(
        availability_id="avail-andi-1", intent_id=intent_andi.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    sess_budi = StudySession(
        session_id="sess-budi-1", host_id=budi.student_id, course_id=course1.course_id,
        title="Latihan Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", min_group_size=2, max_group_size=4, status="OPEN"
    )
    slot_budi = SessionSlot(
        slot_id="slot-budi-1", session_id=sess_budi.session_id,
        session_date="2026-11-22", start_time="09:00", end_time="11:00", status="APPROVED"
    )
    db.add_all([intent_andi, slot_andi, sess_budi, slot_budi])
    db.commit()

    # 7.1 Persistensi normal
    run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)
    rows_initial = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    assert len(rows_initial) == 1
    old_match_id = rows_initial[0].match_id

    # 7.2 Breakdown JSON tersimpan dengan 5 komponen
    bd = json.loads(rows_initial[0].breakdown_json)
    assert set(bd.keys()) == {"topic_similarity", "goal_compatibility", "style_compatibility", "date_preference", "mode_compatibility"}

    # 7.3 Pembersihan rekaman lama saat matching ulang berhasil
    run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)
    rows_renewed = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    assert len(rows_renewed) == 1
    new_match_id = rows_renewed[0].match_id
    assert old_match_id != new_match_id, "ID lama harus dibersihkan dan diganti baru"

    # =========================================================================
    # 7.5 UJI ATOMIC ROLLBACK SAAT TERJADI KEGAGALAN DI TENGAH TRANSAKSI (P1 BLOCKER)
    # =========================================================================
    # Simpan state rekaman sebelum kegagalan
    rows_before_failure = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    ids_before_failure = {r.match_id for r in rows_before_failure}
    assert len(ids_before_failure) == 1

    # Injeksi kegagalan simulasi pada tahap validasi payload kandidat setelah DELETE dijalankan
    with patch("app.matching.format_match_result_payload", side_effect=ValueError("Simulated mid-pipeline failure during formatting")):
        try:
            run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)
            assert False, "Harus memicu ValueError dari kegagalan simulasi"
        except ValueError as exc:
            assert "Simulated mid-pipeline failure" in str(exc)

    # Verifikasi bahwa rollback transaksi bekerja 100%:
    # 1. Rekaman lama TIDAK hilang terhapus oleh query DELETE
    # 2. Tidak ada rekaman baru yang tersimpan secara parsial
    rows_after_failure = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    ids_after_failure = {r.match_id for r in rows_after_failure}
    assert ids_after_failure == ids_before_failure, "Rollback harus memulihkan seluruh rekaman lama!"
    assert len(rows_after_failure) == 1, "Jumlah rekaman harus persis sama sebelum kegagalan"

    db.close()


# =============================================================================
# SUITE 18.8: Integrasi Endpoint FastAPI & TestClient (P2)
# =============================================================================
def test_fastapi_endpoints_with_testclient():
    engine, TestingSession = create_test_db()
    db = TestingSession()

    course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
    andi = Student(
        student_id="std-andi", full_name="Andi", email="andi@t.ac.id", student_number="1201",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    budi = Student(
        student_id="std-budi", full_name="Budi", email="budi@t.ac.id", student_number="1202",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
    )
    doni = Student(
        student_id="std-doni", full_name="Doni", email="doni@t.ac.id", student_number="1204",
        password_hash=hash_password("p"), account_status="ACTIVE", verification_status="UNVERIFIED", is_discoverable=True
    )
    db.add_all([course1, andi, budi, doni])
    db.commit()

    token_andi = create_token(andi.student_id, andi.email)
    token_budi = create_token(budi.student_id, budi.email)
    token_doni = create_token(doni.student_id, doni.email)

    headers_andi = {"Authorization": f"Bearer {token_andi}"}
    headers_budi = {"Authorization": f"Bearer {token_budi}"}
    headers_doni = {"Authorization": f"Bearer {token_doni}"}

    intent_andi = StudyIntent(
        intent_id="int-andi-1", student_id=andi.student_id, course_id=course1.course_id,
        topics="Pohon Biner, AVL Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    slot_andi = IntentAvailability(
        availability_id="avail-andi-1", intent_id=intent_andi.intent_id,
        day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
    )
    sess_budi = StudySession(
        session_id="sess-budi-1", host_id=budi.student_id, course_id=course1.course_id,
        title="Latihan Pohon Biner", description="Diskusi", learning_goal="PRACTICE",
        collaboration_style="DISCUSSION", learning_mode="OFFLINE", location="Lab",
        min_group_size=2, max_group_size=4, status="OPEN"
    )
    slot_budi = SessionSlot(
        slot_id="slot-budi-1", session_id=sess_budi.session_id,
        session_date="2026-11-22", start_time="09:00", end_time="11:00", status="APPROVED"
    )
    db.add_all([intent_andi, slot_andi, sess_budi, slot_budi])
    db.commit()

    # Setup TestClient dengan in-memory session override
    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # 8.1 401 Unauthorized tanpa token
    r_no_auth = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_andi.intent_id})
    assert r_no_auth.status_code == 401, f"Expected 401, got {r_no_auth.status_code}"

    # 8.2 401 Unauthorized dengan token rusak
    r_bad_token = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_andi.intent_id}, headers={"Authorization": "Bearer token_rusak"})
    assert r_bad_token.status_code == 401

    # 8.3 403 Forbidden meminta rekomendasi untuk intent milik mahasiswa lain
    r_other = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_andi.intent_id}, headers=headers_budi)
    assert r_other.status_code == 403

    # 8.4 404 Not Found untuk intent_id fiktif
    r_fiktif = client.post("/api/v1/matching/recommendations", json={"intent_id": "non-existent-uuid"}, headers=headers_andi)
    assert r_fiktif.status_code == 404

    # 8.5 400 Bad Request untuk intent CANCELLED
    intent_andi.status = "CANCELLED"
    db.commit()
    r_canc = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_andi.intent_id}, headers=headers_andi)
    assert r_canc.status_code == 400
    intent_andi.status = "ACTIVE"
    db.commit()

    # 8.6 403 Forbidden untuk akun UNVERIFIED
    intent_doni = StudyIntent(
        intent_id="int-doni-1", student_id=doni.student_id, course_id=course1.course_id,
        topics="Kalkulus", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
        learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
    )
    db.add(intent_doni)
    db.commit()
    r_unver = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_doni.intent_id}, headers=headers_doni)
    assert r_unver.status_code == 403

    # 8.7 200 OK POST recommendations Session-First berhasil
    r_ok = client.post(
        "/api/v1/matching/recommendations",
        json={"intent_id": intent_andi.intent_id, "min_score": 50.0, "limit": 3},
        headers=headers_andi
    )
    assert r_ok.status_code == 200
    data_ok = r_ok.json()
    assert data_ok["match_type"] == "SESSION"
    assert len(data_ok["recommendations"]) >= 1

    # Validasi bahwa response sesuai dengan skema RecommendationResponse
    validated_resp = RecommendationResponse.model_validate(data_ok)
    assert validated_resp.match_type == "SESSION"

    # =========================================================================
    # 8.8 UJI GET RECOMMENDATIONS ADALAH STRICTLY READ-ONLY (P1 BLOCKER)
    # =========================================================================
    # Catat keadaan database sebelum GET
    rows_before_get = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    count_before_get = len(rows_before_get)
    ids_before_get = {r.match_id for r in rows_before_get}
    assert count_before_get >= 1

    # Panggil GET /study-intents/{intent_id}/recommendations
    r_get = client.get(
        f"/api/v1/study-intents/{intent_andi.intent_id}/recommendations?min_score=50.0&limit=3",
        headers=headers_andi
    )
    assert r_get.status_code == 200
    data_get = r_get.json()
    assert data_get["match_type"] == "SESSION"
    assert len(data_get["recommendations"]) >= 1
    # Validasi skema
    RecommendationResponse.model_validate(data_get)

    # Verifikasi bahwa GET SAMA SEKALI TIDAK MENGUBAH DATABASE
    rows_after_get = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
    count_after_get = len(rows_after_get)
    ids_after_get = {r.match_id for r in rows_after_get}

    assert count_before_get == count_after_get, "GET tidak boleh menambah atau menghapus record!"
    assert ids_before_get == ids_after_get, "GET tidak boleh mengubah ID record tersimpan!"

    # 8.9 403 Forbidden GET recommendations untuk mahasiswa lain
    r_get_other = client.get(
        f"/api/v1/study-intents/{intent_andi.intent_id}/recommendations",
        headers=headers_budi
    )
    assert r_get_other.status_code == 403

    # 8.10 200 OK GET /matching/results/{intent_id}
    r_results = client.get(
        f"/api/v1/matching/results/{intent_andi.intent_id}",
        headers=headers_andi
    )
    assert r_results.status_code == 200
    assert len(r_results.json()) >= 1

    # 8.11 403 Forbidden GET /matching/results/{intent_id} untuk mahasiswa lain
    r_results_other = client.get(
        f"/api/v1/matching/results/{intent_andi.intent_id}",
        headers=headers_budi
    )
    assert r_results_other.status_code == 403

    db.close()


# =============================================================================
# Standalone CLI Test Runner
# =============================================================================
def run_tests():
    print("=" * 80)
    print("RUNNING DAY 16: MATCHING PIPELINE ORCHESTRATOR & RECOMMENDATIONS API SUITE")
    print("=" * 80)

    test_functions = [
        ("Suite 18.1: Pydantic Validation for Day 16 Schemas", test_recommendation_request_pydantic_validation),
        ("Suite 18.2: Orchestrator Pre-Conditions & Guard Rails", test_orchestrator_preconditions_and_guard_rails),
        ("Suite 18.3: Session-First Principle & Fallback Logic", test_session_first_and_partner_fallback),
        ("Suite 18.4: Session Detail Enrichment & Capacity", test_session_detail_enrichment_and_capacity),
        ("Suite 18.5: Partner Matching & Multi-Intent Deduplication", test_partner_deduplication_and_student_filters),
        ("Suite 18.6: Limit, Ranking & Explanations", test_limit_ranking_and_explanations),
        ("Suite 18.7: Database Persistence & Atomic Rollback under Mid-Pipeline Failure", test_persistence_and_atomic_rollback_on_mid_pipeline_failure),
        ("Suite 18.8: FastAPI Endpoints via TestClient (HTTP Integration & Read-Only GET)", test_fastapi_endpoints_with_testclient),
    ]

    passed_count = 0
    total_count = len(test_functions)

    for name, test_fn in test_functions:
        try:
            test_fn()
            passed_count += 1
            print(f"  [PASS] {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            raise e

    print("=" * 80)
    print(f"DAY 16 TEST SUITE RESULT: {passed_count} / {total_count} SUITES PASSED (100%)")
    print("=" * 80)
    return passed_count, total_count


if __name__ == "__main__":
    passed, total = run_tests()
    if passed != total:
        sys.exit(1)
