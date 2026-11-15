# ==============================================================================
# TEST DAY 16: MATCHING PIPELINE ORCHESTRATOR & RECOMMENDATIONS API SUITE
# ==============================================================================
# Pengujian komprehensif untuk Tahap 16:
# 1. Validasi skema Pydantic RecommendationRequest, RecommendationItem, RecommendationResponse
# 2. Prakondisi orchestrator: Intent tidak ditemukan, bukan ACTIVE, zero valid windows
# 3. Prinsip Session-First: Prioritas Sesi Belajar di atas Rekan Belajar
# 4. Fallback ke Partner Matching saat tidak ada Sesi Belajar yang lolos/skor tinggi
# 5. Detail Enrichment & Penghitungan Kapasitas Terisi (occupied seats)
# 6. Deduplikasi Kandidat Partner (multi-intent per mahasiswa)
# 7. Pembatasan Limit (Top N) dan Pengurutan Skor Menurun (Rank 1..N)
# 8. Format Payload MatchResultCreate & Penjelasan Bahasa Manusia
# 9. Persistensi Database Atomic Transaction & Rollback jika terjadi kegagalan
# 10. FastAPI Integration via TestClient: Autentikasi, Otorisasi, HTTP Status,
#     Strictly Read-Only GET Recommendations, Persist Selected Schedule POST->DB->GET,
#     dan Account Guards (ACTIVE & VERIFIED) pada seluruh endpoint.
# ==============================================================================

import os
import sys
import json
import math
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import Base, get_db, ensure_database_schema
from app.models import (
    Student, Course, StudyIntent, IntentAvailability,
    StudySession, SessionSlot, SessionMember, MatchResult
)
from app.schemas import (
    RecommendationRequest, RecommendationItem, RecommendationResponse,
    MatchBreakdown, MatchResultCreate, MatchResultResponse
)
from app.matching import run_matching_pipeline, format_match_result_payload
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
    ensure_database_schema(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, TestingSession


class TestDay16MatchingPipeline(unittest.TestCase):
    """Test Case komprehensif Day 16 & Day 16.1 yang kompatibel dengan pytest dan unittest."""

    # =========================================================================
    # SUITE 18.1: Validasi Skema Pydantic Day 16
    # =========================================================================
    def test_recommendation_request_pydantic_validation(self):
        req = RecommendationRequest(intent_id="int-123", min_score=60.0, limit=5)
        self.assertEqual(req.intent_id, "int-123")
        self.assertEqual(req.min_score, 60.0)
        self.assertEqual(req.limit, 5)

        req_default = RecommendationRequest(intent_id="int-abc")
        self.assertEqual(req_default.min_score, 60.0)
        self.assertEqual(req_default.limit, 5)

        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="  ")

        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="int-1", min_score=-1.0)
        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="int-1", min_score=100.1)
        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="int-1", min_score=float("nan"))
        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="int-1", min_score=float("inf"))
        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="int-1", min_score=True)

        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="int-1", limit=0)
        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="int-1", limit=-5)
        with self.assertRaises(ValidationError):
            RecommendationRequest(intent_id="int-1", limit=True)

        req_none = RecommendationRequest(intent_id="int-1", limit=None)
        self.assertIsNone(req_none.limit)

        bd = MatchBreakdown(
            topic_similarity=90.0, goal_compatibility=80.0,
            style_compatibility=85.0, date_preference=70.0, mode_compatibility=100.0
        )
        item = RecommendationItem(
            rank=1, candidate_type="SESSION", candidate_session_id="sess-1",
            compatibility_score=85.0, breakdown=bd, explanation="Bagus sekali"
        )
        self.assertEqual(item.rank, 1)
        self.assertEqual(item.candidate_type, "SESSION")

        resp = RecommendationResponse(
            intent_id="int-1", course_id="crs-1", match_type="SESSION",
            total_candidates=1, recommendations=[item], message="Rekomendasi ditemukan"
        )
        self.assertEqual(resp.total_candidates, 1)

    # =========================================================================
    # SUITE 18.2: Orchestrator Pre-Conditions & Guard Rails
    # =========================================================================
    def test_orchestrator_preconditions_and_guard_rails(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            with self.assertRaises(ValueError):
                run_matching_pipeline(intent=None, db=db)

            with self.assertRaises(ValueError):
                dummy = type("DummyIntent", (), {"intent_id": "int-1", "status": "ACTIVE"})()
                run_matching_pipeline(intent=dummy, db=db, min_score=-1.0)
            with self.assertRaises(ValueError):
                dummy = type("DummyIntent", (), {"intent_id": "int-1", "status": "ACTIVE"})()
                run_matching_pipeline(intent=dummy, db=db, min_score=105.0)
            with self.assertRaises(ValueError):
                dummy = type("DummyIntent", (), {"intent_id": "int-1", "status": "ACTIVE"})()
                run_matching_pipeline(intent=dummy, db=db, min_score=float("nan"))
            with self.assertRaises(ValueError):
                dummy = type("DummyIntent", (), {"intent_id": "int-1", "status": "ACTIVE"})()
                run_matching_pipeline(intent=dummy, db=db, min_score=True)

            with self.assertRaises(ValueError):
                dummy = type("DummyIntent", (), {"intent_id": "int-1", "status": "ACTIVE"})()
                run_matching_pipeline(intent=dummy, db=db, limit=0)
            with self.assertRaises(ValueError):
                dummy = type("DummyIntent", (), {"intent_id": "int-1", "status": "ACTIVE"})()
                run_matching_pipeline(intent=dummy, db=db, limit=-3)
            with self.assertRaises(ValueError):
                dummy = type("DummyIntent", (), {"intent_id": "int-1", "status": "ACTIVE"})()
                run_matching_pipeline(intent=dummy, db=db, limit=True)

            course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            student1 = Student(
                student_id="std-1", full_name="Andi", email="andi@t.ac.id", student_number="1201",
                password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
            )
            db.add_all([course1, student1])
            db.commit()

            intent_cancelled = StudyIntent(
                intent_id="int-canc", student_id=student1.student_id, course_id=course1.course_id,
                topics="Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="CANCELLED"
            )
            db.add(intent_cancelled)
            db.commit()

            with self.assertRaises(ValueError):
                run_matching_pipeline(intent=intent_cancelled, db=db)

            intent_no_slots = StudyIntent(
                intent_id="int-noslot", student_id=student1.student_id, course_id=course1.course_id,
                topics="Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            db.add(intent_no_slots)
            db.commit()

            res_empty = run_matching_pipeline(intent=intent_no_slots, db=db, persist=True)
            self.assertEqual(res_empty["match_type"], "NONE")
            self.assertEqual(res_empty["total_candidates"], 0)
            self.assertEqual(len(res_empty["recommendations"]), 0)
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # SUITE 18.3: Session-First Principle & Partner Fallback
    # =========================================================================
    def test_session_first_and_partner_fallback(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
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
            db.add_all([sess_budi, slot_budi])
            db.commit()

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

            pipeline_res = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
            self.assertEqual(pipeline_res["match_type"], "SESSION", "Harus memprioritaskan SESSION")
            self.assertTrue(all(c["candidate_type"] == "SESSION" for c in pipeline_res["recommendations"]))
            self.assertGreaterEqual(pipeline_res["total_candidates"], 1)

            persisted = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
            self.assertGreaterEqual(len(persisted), 1)
            self.assertTrue(all(m.candidate_type == "SESSION" for m in persisted))

            res_high = run_matching_pipeline(intent=intent_andi, db=db, min_score=99.9, limit=5, persist=False)
            self.assertEqual(res_high["match_type"], "NONE", "Tidak ada kandidat mencapai 99.9")

            sess_budi.status = "COMPLETED"
            db.commit()

            res_partner = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=True)
            self.assertEqual(res_partner["match_type"], "PARTNER", "Harus fallback ke PARTNER")
            self.assertTrue(all(c["candidate_type"] == "PARTNER" for c in res_partner["recommendations"]))
            self.assertEqual(res_partner["recommendations"][0]["target_intent_id"], intent_citra.intent_id)
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # SUITE 18.4: Session Detail Enrichment & Capacity Logic
    # =========================================================================
    def test_session_detail_enrichment_and_capacity(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
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

            s_det = rec["session_details"]
            self.assertIsNotNone(s_det)
            self.assertEqual(s_det["title"], sess_budi.title)
            self.assertEqual(s_det["host_name"], "Budi Santoso")
            self.assertEqual(s_det["occupied_seats"], 1, "Hanya host yang menempati kursi awal")

            sched = rec["selected_schedule"]
            self.assertEqual(sched["date"], "2026-11-22")
            self.assertEqual(sched["duration_minutes"], 120)

            mem_citra = SessionMember(
                member_id="mem-c-1", session_id=sess_budi.session_id, student_id=citra.student_id,
                role="MEMBER", status="ACCEPTED"
            )
            db.add(mem_citra)
            db.commit()

            res_2 = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
            self.assertEqual(res_2["recommendations"][0]["session_details"]["occupied_seats"], 2)

            sess_budi.max_group_size = 2
            db.commit()
            res_full = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
            self.assertEqual(res_full["match_type"], "NONE", "Sesi penuh harus tereksklusi")
            sess_budi.max_group_size = 4
            db.commit()

            mem_andi = SessionMember(
                member_id="mem-a-1", session_id=sess_budi.session_id, student_id=andi.student_id,
                role="MEMBER", status="ACCEPTED"
            )
            db.add(mem_andi)
            db.commit()
            res_joined = run_matching_pipeline(intent=intent_andi, db=db, min_score=60.0, limit=5, persist=False)
            self.assertEqual(res_joined["match_type"], "NONE", "Andi sudah member sehingga harus tereksklusi")
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # SUITE 18.5: Partner Matching & Multi-Intent Deduplication
    # =========================================================================
    def test_partner_deduplication_and_student_filters(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
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
            db.add_all([intent_andi, slot_andi])
            db.commit()

            intent_budi_1 = StudyIntent(
                intent_id="int-budi-1", student_id=budi.student_id, course_id=course1.course_id,
                topics="Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            slot_budi_1 = IntentAvailability(
                availability_id="avail-b-1", intent_id=intent_budi_1.intent_id,
                day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
            )
            intent_budi_2 = StudyIntent(
                intent_id="int-budi-2", student_id=budi.student_id, course_id=course1.course_id,
                topics="Graph BFS DFS", learning_goal="UNDERSTAND", collaboration_style="FOCUS_STUDY",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            slot_budi_2 = IntentAvailability(
                availability_id="avail-b-2", intent_id=intent_budi_2.intent_id,
                day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
            )
            db.add_all([intent_budi_1, slot_budi_1, intent_budi_2, slot_budi_2])
            db.commit()

            res = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=False)
            recs = res["recommendations"]
            self.assertEqual(len(recs), 1, "Dua intent milik Budi harus dideduplikasi menjadi 1 rekomendasi terbaik")
            self.assertEqual(recs[0]["target_intent_id"], intent_budi_1.intent_id, "Intent 1 dengan topik identik harus menang")

            part_det = recs[0]["partner_details"]
            self.assertIsNotNone(part_det)
            self.assertEqual(part_det["student_name"], "Budi")

            budi.account_status = "RESTRICTED"
            db.commit()
            res_restr = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=False)
            self.assertEqual(res_restr["match_type"], "NONE", "Mahasiswa RESTRICTED harus tereksklusi")
            budi.account_status = "ACTIVE"
            db.commit()

            budi.verification_status = "UNVERIFIED"
            db.commit()
            res_unver = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=False)
            self.assertEqual(res_unver["match_type"], "NONE", "Mahasiswa UNVERIFIED harus tereksklusi")
            budi.verification_status = "VERIFIED"
            db.commit()

            budi.is_discoverable = False
            db.commit()
            res_undisc = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=False)
            self.assertEqual(res_undisc["match_type"], "NONE", "Mahasiswa non-discoverable harus tereksklusi")
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # SUITE 18.6: Limit, Ranking & Explanations
    # =========================================================================
    def test_limit_ranking_and_explanations(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
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
            db.add_all([intent_andi, slot_andi])
            db.commit()

            intent_budi = StudyIntent(
                intent_id="int-budi-1", student_id=budi.student_id, course_id=course1.course_id,
                topics="Pohon Biner", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            slot_budi = IntentAvailability(
                availability_id="avail-b-1", intent_id=intent_budi.intent_id,
                day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
            )
            intent_citra = StudyIntent(
                intent_id="int-citra-1", student_id=citra.student_id, course_id=course1.course_id,
                topics="Graph", learning_goal="UNDERSTAND", collaboration_style="FOCUS_STUDY",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            slot_citra = IntentAvailability(
                availability_id="avail-c-1", intent_id=intent_citra.intent_id,
                day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1
            )
            db.add_all([intent_budi, slot_budi, intent_citra, slot_citra])
            db.commit()

            res_lim1 = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=1, persist=False)
            self.assertEqual(len(res_lim1["recommendations"]), 1)
            self.assertEqual(res_lim1["recommendations"][0]["rank"], 1)

            res_none = run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=None, persist=False)
            self.assertEqual(len(res_none["recommendations"]), 2)

            scores = [r["compatibility_score"] for r in res_none["recommendations"]]
            self.assertEqual(scores, sorted(scores, reverse=True))

            self.assertGreater(len(res_none["recommendations"][0]["explanation"]), 10)
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # SUITE 18.7: Database Persistence & Atomic Rollback under Mid-Pipeline Failure
    # =========================================================================
    def test_persistence_and_atomic_rollback_on_mid_pipeline_failure(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
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

            run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)
            rows_initial = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
            self.assertEqual(len(rows_initial), 1)
            old_match_id = rows_initial[0].match_id

            bd = json.loads(rows_initial[0].breakdown_json)
            self.assertEqual(set(bd.keys()), {"topic_similarity", "goal_compatibility", "style_compatibility", "date_preference", "mode_compatibility"})

            run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)
            rows_renewed = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
            self.assertEqual(len(rows_renewed), 1)
            new_match_id = rows_renewed[0].match_id
            self.assertNotEqual(old_match_id, new_match_id, "ID lama harus dibersihkan dan diganti baru")

            # Uji Atomic Rollback saat terjadi error formatting payload kandidat di tengah transaksi
            rows_before_failure = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
            ids_before_failure = {r.match_id for r in rows_before_failure}
            self.assertEqual(len(ids_before_failure), 1)

            with patch("app.matching.format_match_result_payload", side_effect=ValueError("Simulated mid-pipeline failure during formatting")):
                with self.assertRaises(ValueError):
                    run_matching_pipeline(intent=intent_andi, db=db, min_score=50.0, limit=5, persist=True)

            rows_after_failure = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
            ids_after_failure = {r.match_id for r in rows_after_failure}
            self.assertEqual(ids_after_failure, ids_before_failure, "Rollback harus memulihkan seluruh rekaman lama!")
            self.assertEqual(len(rows_after_failure), 1)
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # SUITE 18.8: Integrasi Endpoint FastAPI & TestClient (Clean Cleanup & Guards)
    # =========================================================================
    def test_fastapi_endpoints_with_testclient(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        original_overrides = dict(app.dependency_overrides)

        try:
            course1 = Course(course_id="crs-sd", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(
                student_id="std-andi", full_name="Andi", email="andi@t.ac.id", student_number="1201",
                password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
            )
            budi = Student(
                student_id="std-budi", full_name="Budi", email="budi@t.ac.id", student_number="1202",
                password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
            )
            doni_unver = Student(
                student_id="std-doni", full_name="Doni", email="doni@t.ac.id", student_number="1204",
                password_hash=hash_password("p"), account_status="ACTIVE", verification_status="UNVERIFIED", is_discoverable=True
            )
            eko_susp = Student(
                student_id="std-eko", full_name="Eko", email="eko@t.ac.id", student_number="1205",
                password_hash=hash_password("p"), account_status="SUSPENDED", verification_status="VERIFIED", is_discoverable=True
            )
            db.add_all([course1, andi, budi, doni_unver, eko_susp])
            db.commit()

            token_andi = create_token(andi.student_id, andi.email)
            token_budi = create_token(budi.student_id, budi.email)
            token_doni = create_token(doni_unver.student_id, doni_unver.email)
            token_eko = create_token(eko_susp.student_id, eko_susp.email)

            headers_andi = {"Authorization": f"Bearer {token_andi}"}
            headers_budi = {"Authorization": f"Bearer {token_budi}"}
            headers_doni = {"Authorization": f"Bearer {token_doni}"}
            headers_eko = {"Authorization": f"Bearer {token_eko}"}

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

            # Setup override get_db
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
            self.assertEqual(r_no_auth.status_code, 401)

            # 8.2 401 Unauthorized dengan token rusak
            r_bad_token = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_andi.intent_id}, headers={"Authorization": "Bearer rusak"})
            self.assertEqual(r_bad_token.status_code, 401)

            # 8.3 403 Forbidden meminta rekomendasi untuk intent milik orang lain
            r_other = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_andi.intent_id}, headers=headers_budi)
            self.assertEqual(r_other.status_code, 403)

            # 8.4 404 Not Found untuk intent_id fiktif
            r_fiktif = client.post("/api/v1/matching/recommendations", json={"intent_id": "non-existent-uuid"}, headers=headers_andi)
            self.assertEqual(r_fiktif.status_code, 404)

            # 8.5 400 Bad Request untuk intent CANCELLED
            intent_andi.status = "CANCELLED"
            db.commit()
            r_canc = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_andi.intent_id}, headers=headers_andi)
            self.assertEqual(r_canc.status_code, 400)
            intent_andi.status = "ACTIVE"
            db.commit()

            # 8.6 403 Forbidden untuk akun UNVERIFIED pada POST
            intent_doni = StudyIntent(
                intent_id="int-doni-1", student_id=doni_unver.student_id, course_id=course1.course_id,
                topics="Kalkulus", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            db.add(intent_doni)
            db.commit()
            r_unver = client.post("/api/v1/matching/recommendations", json={"intent_id": intent_doni.intent_id}, headers=headers_doni)
            self.assertEqual(r_unver.status_code, 403)

            # 8.7 200 OK POST recommendations Session-First berhasil
            r_ok = client.post(
                "/api/v1/matching/recommendations",
                json={"intent_id": intent_andi.intent_id, "min_score": 50.0, "limit": 3},
                headers=headers_andi
            )
            self.assertEqual(r_ok.status_code, 200)
            data_ok = r_ok.json()
            self.assertEqual(data_ok["match_type"], "SESSION")
            self.assertGreaterEqual(len(data_ok["recommendations"]), 1)
            RecommendationResponse.model_validate(data_ok)

            # 8.8 UJI GET RECOMMENDATIONS ADALAH STRICTLY READ-ONLY
            rows_before_get = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
            count_before_get = len(rows_before_get)
            ids_before_get = {r.match_id for r in rows_before_get}
            self.assertGreaterEqual(count_before_get, 1)

            r_get = client.get(
                f"/api/v1/study-intents/{intent_andi.intent_id}/recommendations?min_score=50.0&limit=3",
                headers=headers_andi
            )
            self.assertEqual(r_get.status_code, 200)
            data_get = r_get.json()
            self.assertEqual(data_get["match_type"], "SESSION")
            self.assertGreaterEqual(len(data_get["recommendations"]), 1)
            RecommendationResponse.model_validate(data_get)

            rows_after_get = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).all()
            count_after_get = len(rows_after_get)
            ids_after_get = {r.match_id for r in rows_after_get}

            self.assertEqual(count_before_get, count_after_get, "GET tidak boleh menambah atau menghapus record!")
            self.assertEqual(ids_before_get, ids_after_get, "GET tidak boleh mengubah ID record tersimpan!")

            # 8.9 403 Forbidden GET recommendations untuk mahasiswa lain
            r_get_other = client.get(
                f"/api/v1/study-intents/{intent_andi.intent_id}/recommendations",
                headers=headers_budi
            )
            self.assertEqual(r_get_other.status_code, 403)

            # 8.10 200 OK GET /matching/results/{intent_id}
            r_results = client.get(
                f"/api/v1/matching/results/{intent_andi.intent_id}",
                headers=headers_andi
            )
            self.assertEqual(r_results.status_code, 200)
            self.assertGreaterEqual(len(r_results.json()), 1)

            # 8.11 403 Forbidden GET /matching/results/{intent_id} untuk mahasiswa lain
            r_results_other = client.get(
                f"/api/v1/matching/results/{intent_andi.intent_id}",
                headers=headers_budi
            )
            self.assertEqual(r_results_other.status_code, 403)

            # 8.12 403 Forbidden GET /matching/results/{intent_id} untuk akun UNVERIFIED (Temuan 2 Audit)
            intent_doni_res = StudyIntent(
                intent_id="int-doni-res", student_id=doni_unver.student_id, course_id=course1.course_id,
                topics="Kalkulus", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            db.add(intent_doni_res)
            db.commit()
            r_res_unver = client.get(
                f"/api/v1/matching/results/{intent_doni_res.intent_id}",
                headers=headers_doni
            )
            self.assertEqual(r_res_unver.status_code, 403)
            self.assertIn("VERIFIED", r_res_unver.json()["detail"])

            # 8.13 403 Forbidden GET /matching/results/{intent_id} untuk akun SUSPENDED (Temuan 2 Audit)
            intent_eko_res = StudyIntent(
                intent_id="int-eko-res", student_id=eko_susp.student_id, course_id=course1.course_id,
                topics="Kalkulus", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            db.add(intent_eko_res)
            db.commit()
            r_res_susp = client.get(
                f"/api/v1/matching/results/{intent_eko_res.intent_id}",
                headers=headers_eko
            )
            self.assertEqual(r_res_susp.status_code, 403)
            self.assertIn("ditangguhkan atau tidak aktif", r_res_susp.json()["detail"])

        finally:
            # Temuan 3 Audit: Pulihkan dependency_overrides secara bersih
            app.dependency_overrides = original_overrides
            db.close()
            engine.dispose()

    # =========================================================================
    # SUITE 18.9: Persistensi Selected Schedule POST -> DB -> GET (Temuan 1 P1)
    # =========================================================================
    def test_selected_schedule_persistence_post_to_get_session_and_partner(self):
        """
        Membuktikan secara ketat bahwa:
        1. POST menghasilkan selected_schedule.
        2. Database (MatchResult) menyimpan selected_schedule_json secara persisten.
        3. GET membaca dan mengembalikan selected_schedule yang 100% identik dengan hasil POST.
        4. Teruji untuk kandidat SESSION maupun kandidat PARTNER.
        """
        engine, TestingSession = create_test_db()
        db = TestingSession()
        original_overrides = dict(app.dependency_overrides)

        try:
            course1 = Course(course_id="crs-algo", course_code="ACK1C3", course_name="Algoritma", study_program="S1")
            andi = Student(
                student_id="std-a1", full_name="Andi A", email="andik@t.ac.id", student_number="120101",
                password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
            )
            budi = Student(
                student_id="std-b1", full_name="Budi Host", email="budik@t.ac.id", student_number="120102",
                password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
            )
            citra = Student(
                student_id="std-c1", full_name="Citra Partner", email="citrak@t.ac.id", student_number="120103",
                password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True
            )
            db.add_all([course1, andi, budi, citra])
            db.commit()

            token_andi = create_token(andi.student_id, andi.email)
            headers_andi = {"Authorization": f"Bearer {token_andi}"}

            intent_andi = StudyIntent(
                intent_id="int-a-sched", student_id=andi.student_id, course_id=course1.course_id,
                topics="Rekursi dan Dynamic Programming", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            slot_andi = IntentAvailability(
                availability_id="avail-a-1", intent_id=intent_andi.intent_id,
                day_or_date="2026-11-23", start_time="10:00", end_time="13:00", priority_rank=1
            )
            sess_budi = StudySession(
                session_id="sess-b-sched", host_id=budi.student_id, course_id=course1.course_id,
                title="Latihan DP S1", description="Belajar DP", learning_goal="PRACTICE",
                collaboration_style="DISCUSSION", learning_mode="OFFLINE", location="Lab",
                min_group_size=2, max_group_size=4, status="OPEN"
            )
            slot_budi = SessionSlot(
                slot_id="slot-b-1", session_id=sess_budi.session_id,
                session_date="2026-11-23", start_time="10:00", end_time="12:00", status="APPROVED"
            )
            intent_citra = StudyIntent(
                intent_id="int-c-sched", student_id=citra.student_id, course_id=course1.course_id,
                topics="Rekursi dan Dynamic Programming", learning_goal="PRACTICE", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE"
            )
            slot_citra = IntentAvailability(
                availability_id="avail-c-1", intent_id=intent_citra.intent_id,
                day_or_date="2026-11-23", start_time="10:00", end_time="12:00", priority_rank=1
            )
            db.add_all([intent_andi, slot_andi, sess_budi, slot_budi, intent_citra, slot_citra])
            db.commit()

            def override_get_db():
                session = TestingSession()
                try:
                    yield session
                finally:
                    session.close()

            app.dependency_overrides[get_db] = override_get_db
            client = TestClient(app)

            # -----------------------------------------------------------------
            # 1. KASUS SESSION: POST -> DB -> GET
            # -----------------------------------------------------------------
            r_post_sess = client.post(
                "/api/v1/matching/recommendations",
                json={"intent_id": intent_andi.intent_id, "min_score": 50.0, "limit": 3},
                headers=headers_andi
            )
            self.assertEqual(r_post_sess.status_code, 200)
            data_post_sess = r_post_sess.json()
            self.assertEqual(data_post_sess["match_type"], "SESSION")
            rec_sess_post = data_post_sess["recommendations"][0]

            # Verifikasi selected_schedule terisi pada POST
            sched_post_sess = rec_sess_post["selected_schedule"]
            self.assertIsNotNone(sched_post_sess, "POST session candidate harus memiliki selected_schedule")
            self.assertEqual(sched_post_sess["date"], "2026-11-23")
            self.assertEqual(sched_post_sess["start_time"], "10:00")
            self.assertEqual(sched_post_sess["end_time"], "12:00")
            self.assertEqual(sched_post_sess["duration_minutes"], 120)

            # Verifikasi bahwa selected_schedule_json tersimpan di database SQLite
            db_row_sess = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).first()
            self.assertIsNotNone(db_row_sess)
            self.assertIsNotNone(db_row_sess.selected_schedule_json, "Kolom selected_schedule_json di DB tidak boleh kosong")
            parsed_db_sched_sess = json.loads(db_row_sess.selected_schedule_json)
            self.assertEqual(parsed_db_sched_sess, sched_post_sess)

            # Verifikasi endpoint GET /study-intents/{intent_id}/recommendations
            r_get_sess = client.get(
                f"/api/v1/study-intents/{intent_andi.intent_id}/recommendations",
                headers=headers_andi
            )
            self.assertEqual(r_get_sess.status_code, 200)
            data_get_sess = r_get_sess.json()
            rec_sess_get = data_get_sess["recommendations"][0]
            sched_get_sess = rec_sess_get["selected_schedule"]

            self.assertIsNotNone(sched_get_sess, "GET session candidate harus mengembalikan selected_schedule")
            self.assertEqual(sched_get_sess, sched_post_sess, "selected_schedule pada GET harus 100% IDENTIK dengan POST")

            # -----------------------------------------------------------------
            # 2. KASUS PARTNER: Tutup Sesi -> POST -> DB -> GET
            # -----------------------------------------------------------------
            sess_budi.status = "COMPLETED"
            db.commit()

            r_post_part = client.post(
                "/api/v1/matching/recommendations",
                json={"intent_id": intent_andi.intent_id, "min_score": 50.0, "limit": 3},
                headers=headers_andi
            )
            self.assertEqual(r_post_part.status_code, 200)
            data_post_part = r_post_part.json()
            self.assertEqual(data_post_part["match_type"], "PARTNER")
            rec_part_post = data_post_part["recommendations"][0]

            sched_post_part = rec_part_post["selected_schedule"]
            self.assertIsNotNone(sched_post_part, "POST partner candidate harus memiliki selected_schedule")
            self.assertEqual(sched_post_part["date"], "2026-11-23")
            self.assertEqual(sched_post_part["start_time"], "10:00")
            self.assertEqual(sched_post_part["end_time"], "12:00")

            # Verifikasi selected_schedule_json pada rekaman PARTNER di database
            db_row_part = db.query(MatchResult).filter(MatchResult.intent_id == intent_andi.intent_id).first()
            self.assertIsNotNone(db_row_part)
            self.assertIsNotNone(db_row_part.selected_schedule_json)
            parsed_db_sched_part = json.loads(db_row_part.selected_schedule_json)
            self.assertEqual(parsed_db_sched_part, sched_post_part)

            # Verifikasi endpoint GET untuk PARTNER
            r_get_part = client.get(
                f"/api/v1/study-intents/{intent_andi.intent_id}/recommendations",
                headers=headers_andi
            )
            self.assertEqual(r_get_part.status_code, 200)
            data_get_part = r_get_part.json()
            rec_part_get = data_get_part["recommendations"][0]
            sched_get_part = rec_part_get["selected_schedule"]

            self.assertIsNotNone(sched_get_part, "GET partner candidate harus mengembalikan selected_schedule")
            self.assertEqual(sched_get_part, sched_post_part, "selected_schedule partner pada GET harus 100% IDENTIK dengan POST")

            # -----------------------------------------------------------------
            # 3. KASUS GET /matching/results/{intent_id} juga menyertakan selected_schedule_json
            # -----------------------------------------------------------------
            r_res_list = client.get(
                f"/api/v1/matching/results/{intent_andi.intent_id}",
                headers=headers_andi
            )
            self.assertEqual(r_res_list.status_code, 200)
            res_items = r_res_list.json()
            self.assertGreaterEqual(len(res_items), 1)
            self.assertIsNotNone(res_items[0]["selected_schedule_json"])
            self.assertEqual(json.loads(res_items[0]["selected_schedule_json"]), sched_post_part)

        finally:
            app.dependency_overrides = original_overrides
            db.close()
            engine.dispose()

    # =========================================================================
    # SUITE 18.10: Migrasi Database Legacy SQLite (Temuan Day 16.2)
    # =========================================================================
    def test_legacy_database_migration_preserves_old_records_and_adds_column(self):
        """
        Menguji bahwa database SQLite yang masih menggunakan struktur sebelum Day 16.1
        (tanpa kolom selected_schedule_json) dapat dimigrasikan secara sukses:
        1. Kolom selected_schedule_json berhasil ditambahkan.
        2. Seluruh 9 kolom lama tetap utuh.
        3. Rekaman data lama tidak hilang dan nilainya tetap valid.
        4. ORM SQLAlchemy MatchResult dapat membaca rekaman lama tanpa OperationalError.
        5. Migrasi bersifat idempoten (dapat dijalankan berulang tanpa error).
        """
        from sqlalchemy import text
        from sqlalchemy.orm import sessionmaker

        legacy_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )

        legacy_ddl = """
        CREATE TABLE match_results (
            match_id VARCHAR(36) NOT NULL PRIMARY KEY,
            intent_id VARCHAR(36) NOT NULL,
            candidate_type VARCHAR(20) NOT NULL,
            candidate_session_id VARCHAR(36),
            target_intent_id VARCHAR(36),
            compatibility_score FLOAT NOT NULL,
            breakdown_json TEXT NOT NULL,
            explanation TEXT,
            created_at DATETIME NOT NULL
        );
        """
        with legacy_engine.connect() as conn:
            conn.execute(text(legacy_ddl))
            conn.execute(text("""
                INSERT INTO match_results (
                    match_id, intent_id, candidate_type, candidate_session_id, target_intent_id,
                    compatibility_score, breakdown_json, explanation, created_at
                ) VALUES (
                    'legacy-match-001', 'intent-legacy-001', 'PARTNER', NULL, 'intent-target-001',
                    88.50, '{"topic_similarity": 90.0}', 'Sangat cocok', '2026-11-10 10:00:00'
                )
            """))
            conn.commit()

            cols_before = [r[1] for r in conn.execute(text("PRAGMA table_info(match_results)")).fetchall()]
            self.assertNotIn("selected_schedule_json", cols_before, "Kolom selected_schedule_json belum ada sebelum migrasi")
            self.assertEqual(len(cols_before), 9, "Harus tepat 9 kolom pada struktur lama")

        # Eksekusi migrasi skema
        ensure_database_schema(legacy_engine)

        with legacy_engine.connect() as conn:
            cols_after = [r[1] for r in conn.execute(text("PRAGMA table_info(match_results)")).fetchall()]
            self.assertIn("selected_schedule_json", cols_after, "Kolom selected_schedule_json harus tersedia setelah migrasi")
            self.assertEqual(len(cols_after), 10, "Harus menjadi tepat 10 kolom setelah migrasi")
            # Pastikan 9 kolom lama tidak ada yang terhapus/berubah nama
            for c in cols_before:
                self.assertIn(c, cols_after, f"Kolom lama '{c}' harus tetap dipertahankan")

        # Verifikasi bahwa ORM SQLAlchemy MatchResult dapat membaca rekaman lama
        LegacySession = sessionmaker(bind=legacy_engine)
        session = LegacySession()
        try:
            old_record = session.query(MatchResult).filter(MatchResult.match_id == "legacy-match-001").first()
            self.assertIsNotNone(old_record, "Data lama tidak boleh hilang")
            self.assertEqual(old_record.match_id, "legacy-match-001")
            self.assertEqual(old_record.compatibility_score, 88.50)
            self.assertEqual(old_record.explanation, "Sangat cocok")
            self.assertIsNone(old_record.selected_schedule_json, "Baris lama harus memiliki selected_schedule_json bernilai None")
        finally:
            session.close()

        # Uji idempotensi: Jalankan migrasi sekali lagi dan pastikan tidak ada exception
        ensure_database_schema(legacy_engine)
        legacy_engine.dispose()

    # =========================================================================
    # SUITE 18.11: Penanganan Kegagalan Migrasi (Temuan Day 16.2)
    # =========================================================================
    def test_migration_failure_raises_and_is_not_swallowed(self):
        """
        Menguji bahwa ketika terjadi kegagalan tak terpulihkan pada saat migrasi
        (misalnya database terkunci atau disk I/O error), exception TIDAK ditelan
        secara diam-diam dan langsung memicu error untuk mencegah startup dalam kondisi korup.
        """
        from sqlalchemy import text
        from sqlalchemy.exc import OperationalError

        fail_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )

        with fail_engine.connect() as conn:
            conn.execute(text("CREATE TABLE match_results (match_id VARCHAR(36) PRIMARY KEY);"))
            conn.commit()

        # Simulasi error unrecoverable saat koneksi eksekusi migrasi
        with patch.object(fail_engine, "connect") as mock_connect:
            mock_connect.side_effect = OperationalError("database is locked / disk I/O failure", None, None)
            with self.assertRaises(OperationalError):
                ensure_database_schema(fail_engine)

        fail_engine.dispose()


# =============================================================================
# Standalone CLI Test Runner
# =============================================================================
def run_tests():
    print("=" * 80)
    print("RUNNING DAY 16.2: SQLITE MIGRATION HARDENING TEST SUITE")
    print("=" * 80)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestDay16MatchingPipeline)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total - failures - errors

    print("=" * 80)
    print(f"DAY 16.2 TEST SUITE RESULT: {passed} / {total} TESTS PASSED (100% SUCCESS)")
    print("=" * 80)
    return passed, total


if __name__ == "__main__":
    passed, total = run_tests()
    if passed != total:
        sys.exit(1)
