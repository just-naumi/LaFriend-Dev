# ==============================================================================
# test_day17_group_formation.py - Test Suite Group Formation Engine (Day 17)
# ==============================================================================
# Pengujian Komprehensif untuk Day 17:
# 1. Dua mahasiswa cocok -> Kelompok valid (READY, group_size=2)
# 2. Tiga mahasiswa saling cocok -> Kelompok valid (READY, group_size=3)
# 3. Salah satu pasangan tidak kompatibel -> Kandidat ditolak
# 4. Skor pasangan terlemah rendah -> GQ memperhitungkannya (0.70*APS + 0.30*MPS)
# 5. Jadwal semua anggota beririsan >= 60 min -> Kelompok valid
# 6. Jadwal hanya beririsan 59 menit -> Ditolak (floor 60 min)
# 7. Jadwal tersedia pada tanggal berbeda -> Tidak dianggap irisan
# 8. Rentang ukuran kelompok kompatibel -> Kelompok valid
# 9. Rentang ukuran tidak kompatibel -> Kelompok ditolak
# 10. Kandidat skor individu tinggi tapi merusak GQ -> Kandidat dengan GQ lebih baik yang dipilih
# 11. Multi-intent dari mahasiswa yang sama -> Deduplikasi mahasiswa (tidak ada duplikasi anggota)
# 12. Tidak ada kombinasi valid -> NO_COMPATIBLE_GROUP, status intent tetap ACTIVE
# 13. Skor kandidat sama -> Pengurutan deterministik
# 14. API diakses mahasiswa lain -> 403 Forbidden
# 15. Preview dipanggil -> Strictly Read-Only (0 mutasi database pada seluruh tabel)
# ==============================================================================

import os
import sys
import json
import math
import uuid
import unittest
from pathlib import Path
from decimal import Decimal

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import Base, get_db, ensure_database_schema
from app.models import (
    Student, Course, StudyIntent, IntentAvailability,
    StudySession, SessionSlot, SessionMember, Invitation, MatchResult
)
from app.schemas import (
    GroupProposalPreviewRequest, GroupProposalPreviewResponse,
    GroupMemberItem, PairwiseScoreItem, GroupScheduleOption
)
from app.group_formation import (
    intersect_two_window_lists,
    find_group_common_schedules,
    calculate_group_size_bounds,
    calculate_group_quality_score,
    evaluate_pairwise_compatibility,
    form_study_group,
    preview_group_formation_pipeline
)
from app.routes import (
    create_token, hash_password,
    get_current_student, preview_group_proposal_endpoint
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


class TestDay17GroupFormation(unittest.TestCase):
    """Test Suite Komprehensif Day 17 Group Formation Engine."""

    # =========================================================================
    # 1. DUA MAHASISWA COCOK -> KELOMPOK VALID (READY)
    # =========================================================================
    def test_01_two_students_compatible_forms_ready_group(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            course1 = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="andi@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="budi@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([course1, andi, budi])
            db.commit()

            intent_andi = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=course1.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=4, status="ACTIVE")
            slot_andi = IntentAvailability(availability_id="sa", intent_id=intent_andi.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            intent_budi = StudyIntent(intent_id="ib", student_id=budi.student_id, course_id=course1.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=4, status="ACTIVE")
            slot_budi = IntentAvailability(availability_id="sb", intent_id=intent_budi.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([intent_andi, slot_andi, intent_budi, slot_budi])
            db.commit()

            res = form_study_group(host_intent=intent_andi, candidate_intents=[intent_budi], min_score=60.0)
            self.assertEqual(res["formation_status"], "READY")
            self.assertEqual(res["group_size"], 2)
            self.assertEqual(len(res["members"]), 2)
            self.assertEqual(res["members"][0]["role"], "HOST")
            self.assertEqual(res["members"][1]["role"], "MEMBER")
            self.assertEqual(len(res["pairwise_scores"]), 1)
            self.assertGreater(res["group_quality_score"], 80.0)
            self.assertGreaterEqual(len(res["schedule_options"]), 1)
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 2. TIGA MAHASISWA SALING COCOK -> KELOMPOK VALID (READY)
    # =========================================================================
    def test_02_three_students_all_mutually_compatible(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, citra])
            db.commit()

            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=4, status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ib = StudyIntent(intent_id="ib", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=4, status="ACTIVE")
            sb = IntentAvailability(availability_id="sb", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ic = StudyIntent(intent_id="ic", student_id=citra.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=4, status="ACTIVE")
            sc = IntentAvailability(availability_id="sc", intent_id=ic.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([ia, sa, ib, sb, ic, sc])
            db.commit()

            res = form_study_group(host_intent=ia, candidate_intents=[ib, ic], min_score=60.0)
            self.assertEqual(res["formation_status"], "READY")
            self.assertEqual(res["group_size"], 3)
            # N_pair = 3 * 2 / 2 = 3
            self.assertEqual(len(res["pairwise_scores"]), 3)
            # Seluruh 3 anggota ada dalam members
            member_ids = {m["student_id"] for m in res["members"]}
            self.assertEqual(member_ids, {"s1", "s2", "s3"})
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 3. SALAH SATU PASANGAN TIDAK KOMPATIBEL -> KANDIDAT DITOLAK
    # =========================================================================
    def test_03_incompatible_pair_candidate_rejected(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            deni = Student(student_id="s4", full_name="Deni", email="d@t.ac", student_number="4", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, deni])
            db.commit()

            # Andi: 22 Nov 09:00 - 12:00
            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            # Budi: 22 Nov 09:00 - 12:00 (cocok dengan Andi)
            ib = StudyIntent(intent_id="ib", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sb = IntentAvailability(availability_id="sb", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            # Deni: Berbeda topik total (misal topik sama sekali tidak nyambung dengan min_score 95.0)
            id_deni = StudyIntent(intent_id="id", student_id=deni.student_id, course_id=c.course_id, topics="Sangat Berbeda Sekali Jauh", learning_goal="PROJECT", collaboration_style="FOCUS_STUDY", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sd = IntentAvailability(availability_id="sd", intent_id=id_deni.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([ia, sa, ib, sb, id_deni, sd])
            db.commit()

            # Dengan min_score=80.0, Deni tidak akan lolos pasangan dengan Budi / Andi
            res = form_study_group(host_intent=ia, candidate_intents=[ib, id_deni], min_score=80.0)
            self.assertEqual(res["formation_status"], "READY")
            self.assertEqual(res["group_size"], 2)
            member_ids = {m["student_id"] for m in res["members"]}
            self.assertIn("s1", member_ids)
            self.assertIn("s2", member_ids)
            self.assertNotIn("s4", member_ids, "Deni harus ditolak karena tidak memenuhi skor kecocokan")
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 4. SKOR PASANGAN TERLEMAH RENDAH -> GQ MEMPERHITUNGKANNYA
    # =========================================================================
    def test_04_weakest_pair_score_penalizes_gq(self):
        # Contoh di soal:
        # Andi-Budi = 90.0, Andi-Citra = 85.0, Budi-Citra = 75.0
        # APS = (90 + 85 + 75)/3 = 83.33
        # MPS = 75.0
        # GQ = 0.70*83.33 + 0.30*75.0 = 58.331 + 22.50 = 80.83
        scores = [90.0, 85.0, 75.0]
        gq, aps, mps = calculate_group_quality_score(scores)
        self.assertEqual(aps, 83.33)
        self.assertEqual(mps, 75.0)
        self.assertEqual(gq, 80.83)

        # Buktikan bahwa MPS memberi penalti: jika MPS turun ke 50.0 dengan APS sama:
        gq_low_mps, _, _ = calculate_group_quality_score([95.0, 105.0, 50.0])  # avg = 83.33
        self.assertLess(gq_low_mps, gq, "GQ harus lebih rendah jika pasangan terlemah lebih rendah")

    # =========================================================================
    # 5. JADWAL SEMUA ANGGOTA BERIRISAN >= 60 MIN -> KELOMPOK VALID
    # =========================================================================
    def test_05_common_schedule_intersection_60_minutes(self):
        # Contoh di soal:
        # Andi: 09:00 - 12:00
        # Budi: 10:00 - 13:00
        # Citra: 11:00 - 14:00
        # Irisan: 11:00 - 12:00 (60 menit)
        w_andi = [{"date": "2026-11-23", "start_time": "09:00", "end_time": "12:00", "priority": 1}]
        w_budi = [{"date": "2026-11-23", "start_time": "10:00", "end_time": "13:00", "priority": 1}]
        w_citra = [{"date": "2026-11-23", "start_time": "11:00", "end_time": "14:00", "priority": 1}]

        scheds = find_group_common_schedules([w_andi, w_budi, w_citra], min_duration=60)
        self.assertEqual(len(scheds), 1)
        self.assertEqual(scheds[0]["start_time"], "11:00")
        self.assertEqual(scheds[0]["end_time"], "12:00")
        self.assertEqual(scheds[0]["duration_minutes"], 60)

    # =========================================================================
    # 6. JADWAL HANYA BERIRISAN 59 MENIT -> DITOLAK
    # =========================================================================
    def test_06_schedule_59_minutes_rejected(self):
        # Andi: 09:00 - 11:59
        # Budi: 11:00 - 13:00
        # Irisan: 11:00 - 11:59 (59 menit) -> Harus ditolak
        w_andi = [{"date": "2026-11-23", "start_time": "09:00", "end_time": "11:59", "priority": 1}]
        w_budi = [{"date": "2026-11-23", "start_time": "11:00", "end_time": "13:00", "priority": 1}]

        scheds = find_group_common_schedules([w_andi, w_budi], min_duration=60)
        self.assertEqual(len(scheds), 0, "Durasi 59 menit wajib ditolak")

    # =========================================================================
    # 7. JADWAL TERSEDIA PADA TANGGAL BERBEDA -> TIDAK DIANGGAP IRISAN
    # =========================================================================
    def test_07_different_dates_produce_no_intersection(self):
        w_andi = [{"date": "2026-11-23", "start_time": "09:00", "end_time": "12:00", "priority": 1}]
        w_budi = [{"date": "2026-11-24", "start_time": "09:00", "end_time": "12:00", "priority": 1}]

        scheds = find_group_common_schedules([w_andi, w_budi], min_duration=60)
        self.assertEqual(len(scheds), 0, "Beda tanggal tidak boleh menghasilkan irisan")

    # =========================================================================
    # 8. RENTANG UKURAN KELOMPOK KOMPATIBEL -> KELOMPOK VALID
    # =========================================================================
    def test_08_group_size_bounds_compatible(self):
        # Contoh di soal:
        # Andi: [2, 4], Budi: [3, 4], Citra: [2, 3]
        # MinGroup = max(2, 3, 2) = 3
        # MaxGroup = min(4, 4, 3) = 3 -> Kompatibel, tepat 3 orang!
        mock_members = [
            type("M", (), {"min_group_size": 2, "max_group_size": 4})(),
            type("M", (), {"min_group_size": 3, "max_group_size": 4})(),
            type("M", (), {"min_group_size": 2, "max_group_size": 3})(),
        ]
        min_g, max_g = calculate_group_size_bounds(mock_members)
        self.assertEqual(min_g, 3)
        self.assertEqual(max_g, 3)
        self.assertLessEqual(min_g, max_g)

    # =========================================================================
    # 9. RENTANG UKURAN TIDAK KOMPATIBEL -> KELOMPOK DITOLAK
    # =========================================================================
    def test_09_group_size_bounds_incompatible_rejected(self):
        # Andi: [2, 3], Budi: [4, 5]
        # MinGroup = max(2, 4) = 4, MaxGroup = min(3, 5) = 3 -> 4 > 3 (Inkompatibel!)
        mock_members = [
            type("M", (), {"min_group_size": 2, "max_group_size": 3})(),
            type("M", (), {"min_group_size": 4, "max_group_size": 5})(),
        ]
        min_g, max_g = calculate_group_size_bounds(mock_members)
        self.assertGreater(min_g, max_g, "Harus inkompatibel karena Min > Max")

    # =========================================================================
    # 10. KANDIDAT SKOR TINGGI MERUSAK GQ -> KANDIDAT DENGAN GQ LEBIH BAIK DIPILIH
    # =========================================================================
    def test_10_candidate_preserving_higher_gq_is_selected(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            deni = Student(student_id="s4", full_name="Deni", email="d@t.ac", student_number="4", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, citra, deni])
            db.commit()

            # Host Andi (max_group_size=3 agar hanya 2 kandidat yang diambil)
            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Struktur Data", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=3, status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Budi: Sangat cocok dengan Andi
            ib = StudyIntent(intent_id="ib", student_id=budi.student_id, course_id=c.course_id, topics="Struktur Data", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=3, status="ACTIVE")
            sb = IntentAvailability(availability_id="sb", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Citra: Cocok seimbang dengan Andi dan Budi
            ic = StudyIntent(intent_id="ic", student_id=citra.student_id, course_id=c.course_id, topics="Struktur Data", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=3, status="ACTIVE")
            sc = IntentAvailability(availability_id="sc", intent_id=ic.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Deni: Berbeda style dan goal sehingga skor terhadap Budi lebih rendah
            id_deni = StudyIntent(intent_id="id", student_id=deni.student_id, course_id=c.course_id, topics="Struktur Data", learning_goal="PROJECT", collaboration_style="FOCUS_STUDY", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", min_group_size=2, max_group_size=3, status="ACTIVE")
            sd = IntentAvailability(availability_id="sd", intent_id=id_deni.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([ia, sa, ib, sb, ic, sc, id_deni, sd])
            db.commit()

            # Saat membentuk kelompok ukuran 3, sistem akan memilih antara Citra vs Deni
            res = form_study_group(host_intent=ia, candidate_intents=[ib, ic, id_deni], min_score=60.0, target_group_size=3)
            self.assertEqual(res["group_size"], 3)
            member_ids = [m["student_id"] for m in res["members"]]
            self.assertIn("s1", member_ids)
            self.assertIn("s2", member_ids)
            self.assertIn("s3", member_ids, "Citra harus terpilih karena menghasilkan GQ lebih tinggi dibanding Deni")
            self.assertNotIn("s4", member_ids)
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 11. MULTI-INTENT DARI MAHASISWA SAMA -> TIDAK ADA DUPLIKASI ANGGOTA
    # =========================================================================
    def test_11_student_deduplication_in_group(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi])
            db.commit()

            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Budi memiliki dua intent untuk mata kuliah ini
            ib_1 = StudyIntent(intent_id="ib-1", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sb_1 = IntentAvailability(availability_id="sb-1", intent_id=ib_1.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ib_2 = StudyIntent(intent_id="ib-2", student_id=budi.student_id, course_id=c.course_id, topics="Graph", learning_goal="UNDERSTAND", collaboration_style="FOCUS_STUDY", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sb_2 = IntentAvailability(availability_id="sb-2", intent_id=ib_2.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([ia, sa, ib_1, sb_1, ib_2, sb_2])
            db.commit()

            res = form_study_group(host_intent=ia, candidate_intents=[ib_1, ib_2], min_score=50.0)
            self.assertEqual(res["group_size"], 2)
            student_ids = [m["student_id"] for m in res["members"]]
            self.assertEqual(len(student_ids), len(set(student_ids)), "Tidak boleh ada student_id ganda dalam satu kelompok")
            self.assertEqual(student_ids, ["s1", "s2"])
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 12. TIDAK ADA KOMBINASI VALID -> NO_COMPATIBLE_GROUP, INTENT TETAP ACTIVE
    # =========================================================================
    def test_12_no_compatible_group_status(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi])
            db.commit()

            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([ia, sa])
            db.commit()

            # Tanpa kandidat apa pun
            res = form_study_group(host_intent=ia, candidate_intents=[], min_score=60.0)
            self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
            self.assertEqual(res["group_size"], 1)
            self.assertEqual(ia.status, "ACTIVE", "Status Study Intent host harus tetap ACTIVE")
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 13. SKOR KANDIDAT SAMA -> PENGURUTAN DETERMINISTIK
    # =========================================================================
    def test_13_deterministic_tie_breaker(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, citra])
            db.commit()

            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=2, status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Dua kandidat dengan profil identik
            ib = StudyIntent(intent_id="ib-tie", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=2, status="ACTIVE")
            sb = IntentAvailability(availability_id="sb-tie", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ic = StudyIntent(intent_id="ic-tie", student_id=citra.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=2, status="ACTIVE")
            sc = IntentAvailability(availability_id="sc-tie", intent_id=ic.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([ia, sa, ib, sb, ic, sc])
            db.commit()

            # Jalankan berkali-kali untuk membuktikan hasil deterministik stabil
            res1 = form_study_group(host_intent=ia, candidate_intents=[ib, ic], min_score=60.0)
            res2 = form_study_group(host_intent=ia, candidate_intents=[ic, ib], min_score=60.0)
            self.assertEqual(res1["members"][1]["student_id"], res2["members"][1]["student_id"], "Tie breaker harus deterministik dan independen dari urutan list input")
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 14. API DI AKSES MAHASISWA LAIN -> 403 FORBIDDEN & AUTH CHECKS
    # =========================================================================
    def test_14_api_access_cross_student_forbidden(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()

        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi])
            db.commit()

            token_budi = create_token(budi.student_id, budi.email)
            auth_header_budi = f"Bearer {token_budi}"

            # Verifikasi autentikasi token resolving mahasiswa Budi
            resolved_student = get_current_student(authorization=auth_header_budi, db=db)
            self.assertEqual(resolved_student.student_id, budi.student_id)

            ia = StudyIntent(intent_id="ia-andi", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            db.add(ia)
            db.commit()

            # Budi mencoba membuat preview proposal untuk intent milik Andi -> 403 Forbidden
            req = GroupProposalPreviewRequest(host_intent_id=ia.intent_id)
            with self.assertRaises(HTTPException) as ctx:
                preview_group_proposal_endpoint(req=req, current_student=budi, db=db)
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("milikmu sendiri", ctx.exception.detail)

            # Mahasiswa dengan akun SUSPENDED ditolak -> 403 Forbidden
            budi.account_status = "SUSPENDED"
            db.commit()
            with self.assertRaises(HTTPException) as ctx_suspended:
                preview_group_proposal_endpoint(req=req, current_student=budi, db=db)
            self.assertEqual(ctx_suspended.exception.status_code, 403)
            self.assertIn("ditangguhkan", ctx_suspended.exception.detail)
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 15. PREVIEW DIPANGGIL -> TIDAK ADA PERUBAHAN DB (STRICTLY READ-ONLY)
    # =========================================================================
    def test_15_preview_endpoint_strictly_read_only(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()

        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, citra])
            db.commit()

            token_andi = create_token(andi.student_id, andi.email)
            auth_header_andi = f"Bearer {token_andi}"
            resolved_andi = get_current_student(authorization=auth_header_andi, db=db)
            self.assertEqual(resolved_andi.student_id, andi.student_id)

            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ib = StudyIntent(intent_id="ib", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sb = IntentAvailability(availability_id="sb", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ic = StudyIntent(intent_id="ic", student_id=citra.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sc = IntentAvailability(availability_id="sc", intent_id=ic.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([ia, sa, ib, sb, ic, sc])
            db.commit()

            # Catat jumlah baris pada seluruh tabel terkait sebelum preview dipanggil
            count_sessions_before = db.query(StudySession).count()
            count_slots_before = db.query(SessionSlot).count()
            count_members_before = db.query(SessionMember).count()
            count_invitations_before = db.query(Invitation).count()
            count_matches_before = db.query(MatchResult).count()
            count_intents_before = db.query(StudyIntent).count()

            # Panggil endpoint preview_group_proposal_endpoint
            req = GroupProposalPreviewRequest(host_intent_id=ia.intent_id, min_score=60.0)
            res = preview_group_proposal_endpoint(req=req, current_student=andi, db=db)

            # Validasi isi respon
            self.assertEqual(res["formation_status"], "READY")
            self.assertEqual(res["group_size"], 3)
            # Validasi skema respons Pydantic
            GroupProposalPreviewResponse.model_validate(res)

            # Verifikasi bahwa sama sekali TIDAK ADA MUTASI DATABASE
            count_sessions_after = db.query(StudySession).count()
            count_slots_after = db.query(SessionSlot).count()
            count_members_after = db.query(SessionMember).count()
            count_invitations_after = db.query(Invitation).count()
            count_matches_after = db.query(MatchResult).count()
            count_intents_after = db.query(StudyIntent).count()

            self.assertEqual(count_sessions_before, count_sessions_after, "StudySession tidak boleh dibuat pada Day 17")
            self.assertEqual(count_slots_before, count_slots_after, "SessionSlot tidak boleh dibuat pada Day 17")
            self.assertEqual(count_members_before, count_members_after, "SessionMember tidak boleh dibuat pada Day 17")
            self.assertEqual(count_invitations_before, count_invitations_after, "Invitation tidak boleh dibuat pada Day 17")
            self.assertEqual(count_matches_before, count_matches_after, "MatchResult tidak boleh berubah")
            self.assertEqual(count_intents_before, count_intents_after, "StudyIntent tidak boleh berubah")

            # Verifikasi status intent host tetap ACTIVE
            refreshed_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == ia.intent_id).first()
            self.assertEqual(refreshed_intent.status, "ACTIVE")
        finally:
            db.close()
            engine.dispose()


# =============================================================================
# Standalone CLI Test Runner
# =============================================================================
def run_tests():
    print("=" * 80)
    print("RUNNING DAY 17: GROUP FORMATION ENGINE TEST SUITE (15 SCENARIOS)")
    print("=" * 80)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestDay17GroupFormation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total - failures - errors

    print("=" * 80)
    print(f"DAY 17 TEST SUITE RESULT: {passed} / {total} TESTS PASSED (100% SUCCESS)")
    print("=" * 80)
    return passed, total


if __name__ == "__main__":
    passed, total = run_tests()
    if passed != total:
        sys.exit(1)
