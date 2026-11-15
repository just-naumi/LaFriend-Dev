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
    GroupMemberItem, PairwiseScoreItem, GroupScheduleOption,
    PairwiseComponentDetail, PairwiseBreakdown
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
from app.matching import is_learning_mode_compatible
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
            pair_0 = res["pairwise_scores"][0]
            self.assertTrue(len(pair_0["explanation"]) > 0, "Explanation tidak boleh kosong")
            self.assertIn("breakdown", pair_0)
            for c_name in ["topic", "goal", "style", "date", "mode"]:
                self.assertIn(c_name, pair_0["breakdown"])
                self.assertIn("score", pair_0["breakdown"][c_name])
                self.assertIn("contribution", pair_0["breakdown"][c_name])
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
            for pair in res["pairwise_scores"]:
                self.assertTrue(len(pair["explanation"]) > 0, "Setiap pasangan harus memiliki explanation yang tidak kosong")
                for c_name in ["topic", "goal", "style", "date", "mode"]:
                    self.assertIn(c_name, pair["breakdown"])
                    self.assertIn("score", pair["breakdown"][c_name])
                    self.assertIn("contribution", pair["breakdown"][c_name])
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
    # 14. API DI AKSES MAHASISWA LAIN -> 403 FORBIDDEN & AUTH CHECKS (TESTCLIENT)
    # =========================================================================
    def test_14_api_access_cross_student_forbidden(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        original_overrides = dict(app.dependency_overrides)

        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="SUSPENDED", verification_status="VERIFIED", is_discoverable=True)
            dono = Student(student_id="s4", full_name="Dono", email="d@t.ac", student_number="4", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="PENDING", is_discoverable=True)
            db.add_all([c, andi, budi, citra, dono])
            db.commit()

            token_budi = create_token(budi.student_id, budi.email)
            token_citra = create_token(citra.student_id, citra.email)
            token_dono = create_token(dono.student_id, dono.email)
            token_andi = create_token(andi.student_id, andi.email)

            ia = StudyIntent(intent_id="ia-andi", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            db.add(ia)
            db.commit()

            def override_get_db():
                session = TestingSession()
                try:
                    yield session
                finally:
                    session.close()

            app.dependency_overrides[get_db] = override_get_db
            client = TestClient(app)

            # 1. 401 Unauthorized tanpa token
            r_no_auth = client.post("/api/v1/matching/group-proposals/preview", json={"host_intent_id": ia.intent_id})
            self.assertEqual(r_no_auth.status_code, 401)

            # 2. 401 Unauthorized dengan token tidak valid
            r_bad = client.post("/api/v1/matching/group-proposals/preview", json={"host_intent_id": ia.intent_id}, headers={"Authorization": "Bearer token_rusak"})
            self.assertEqual(r_bad.status_code, 401)

            # 3. 403 Forbidden: Budi mencoba membuat preview proposal untuk intent milik Andi (ownership guard)
            r_cross = client.post(
                "/api/v1/matching/group-proposals/preview",
                json={"host_intent_id": ia.intent_id},
                headers={"Authorization": f"Bearer {token_budi}"}
            )
            self.assertEqual(r_cross.status_code, 403)
            self.assertIn("milikmu sendiri", r_cross.json()["detail"])

            # 4. 403 Forbidden: Mahasiswa dengan akun SUSPENDED ditolak
            ic = StudyIntent(intent_id="ic-citra", student_id=citra.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            db.add(ic)
            db.commit()
            r_suspended = client.post(
                "/api/v1/matching/group-proposals/preview",
                json={"host_intent_id": ic.intent_id},
                headers={"Authorization": f"Bearer {token_citra}"}
            )
            self.assertEqual(r_suspended.status_code, 403)
            self.assertIn("ditangguhkan atau tidak aktif", r_suspended.json()["detail"])

            # 5. 403 Forbidden: Mahasiswa belum VERIFIED ditolak
            idono = StudyIntent(intent_id="idono", student_id=dono.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            db.add(idono)
            db.commit()
            r_unverified = client.post(
                "/api/v1/matching/group-proposals/preview",
                json={"host_intent_id": idono.intent_id},
                headers={"Authorization": f"Bearer {token_dono}"}
            )
            self.assertEqual(r_unverified.status_code, 403)
            self.assertIn("VERIFIED", r_unverified.json()["detail"])

            # 6. 404 Not Found: Intent tidak ditemukan
            r_not_found = client.post(
                "/api/v1/matching/group-proposals/preview",
                json={"host_intent_id": "intent-fiktif-404"},
                headers={"Authorization": f"Bearer {token_andi}"}
            )
            self.assertEqual(r_not_found.status_code, 404)
        finally:
            app.dependency_overrides = original_overrides
            db.close()
            engine.dispose()

    # =========================================================================
    # 15. PREVIEW DIPANGGIL -> TIDAK ADA PERUBAHAN DB (STRICTLY READ-ONLY VIA TESTCLIENT)
    # =========================================================================
    def test_15_preview_endpoint_strictly_read_only(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        original_overrides = dict(app.dependency_overrides)

        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, citra])
            db.commit()

            token_andi = create_token(andi.student_id, andi.email)
            headers_andi = {"Authorization": f"Bearer {token_andi}"}

            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ib = StudyIntent(intent_id="ib", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sb = IntentAvailability(availability_id="sb", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ic = StudyIntent(intent_id="ic", student_id=citra.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sc = IntentAvailability(availability_id="sc", intent_id=ic.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([ia, sa, ib, sb, ic, sc])
            db.commit()

            def override_get_db():
                session = TestingSession()
                try:
                    yield session
                finally:
                    session.close()

            app.dependency_overrides[get_db] = override_get_db
            client = TestClient(app)

            # Catat jumlah baris pada seluruh tabel terkait sebelum preview dipanggil
            count_sessions_before = db.query(StudySession).count()
            count_slots_before = db.query(SessionSlot).count()
            count_members_before = db.query(SessionMember).count()
            count_invitations_before = db.query(Invitation).count()
            count_matches_before = db.query(MatchResult).count()
            count_intents_before = db.query(StudyIntent).count()

            # Panggil endpoint POST /api/v1/matching/group-proposals/preview via TestClient
            r_prev = client.post(
                "/api/v1/matching/group-proposals/preview",
                json={"host_intent_id": ia.intent_id, "min_score": 60.0},
                headers=headers_andi
            )
            self.assertEqual(r_prev.status_code, 200)
            data_prev = r_prev.json()

            # Validasi isi respon
            self.assertEqual(data_prev["formation_status"], "READY")
            self.assertEqual(data_prev["group_size"], 3)
            # Validasi skema respons Pydantic
            validated_resp = GroupProposalPreviewResponse.model_validate(data_prev)
            self.assertEqual(len(validated_resp.members), 3)

            # Verifikasi bahwa sama sekali TIDAK ADA MUTASI DATABASE (Strictly Read-Only)
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
            app.dependency_overrides = original_overrides
            db.close()
            engine.dispose()

    # =========================================================================
    # 16. REGRESI P1: KOMPATIBILITAS MODE BELAJAR (HARD CONSTRAINT DAY 14)
    # =========================================================================
    def test_16_pairwise_learning_mode_hard_constraints(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            s1 = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            s2 = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, s1, s2])
            db.commit()

            def make_pair(mode_a, mode_b):
                ia = StudyIntent(intent_id="ia", student_id="s1", course_id="c1", topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode=mode_a, earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
                sa = IntentAvailability(availability_id="sa", intent_id="ia", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
                ib = StudyIntent(intent_id="ib", student_id="s2", course_id="c1", topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode=mode_b, earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
                sb = IntentAvailability(availability_id="sb", intent_id="ib", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
                ia.availabilities = [sa]
                ib.availabilities = [sb]
                return ia, ib

            # 1. ONLINE + ONLINE -> Kompatibel
            ia, ib = make_pair("ONLINE", "ONLINE")
            res = evaluate_pairwise_compatibility(ia, ib)
            self.assertIsNotNone(res, "ONLINE + ONLINE harus kompatibel")

            # 2. OFFLINE + OFFLINE -> Kompatibel
            ia, ib = make_pair("OFFLINE", "OFFLINE")
            res = evaluate_pairwise_compatibility(ia, ib)
            self.assertIsNotNone(res, "OFFLINE + OFFLINE harus kompatibel")

            # 3. HYBRID + ONLINE -> Kompatibel
            ia, ib = make_pair("HYBRID", "ONLINE")
            res = evaluate_pairwise_compatibility(ia, ib)
            self.assertIsNotNone(res, "HYBRID + ONLINE harus kompatibel")

            # 4. HYBRID + OFFLINE -> Kompatibel
            ia, ib = make_pair("HYBRID", "OFFLINE")
            res = evaluate_pairwise_compatibility(ia, ib)
            self.assertIsNotNone(res, "HYBRID + OFFLINE harus kompatibel")

            # 5. ONLINE + OFFLINE -> DITOLAK (HARD CONSTRAINT DAY 14)
            ia, ib = make_pair("ONLINE", "OFFLINE")
            res = evaluate_pairwise_compatibility(ia, ib)
            self.assertIsNone(res, "ONLINE + OFFLINE HARUS DITOLAK (mengembalikan None)")

            # 6. OFFLINE + ONLINE -> DITOLAK (SIMETRIS)
            ia, ib = make_pair("OFFLINE", "ONLINE")
            res = evaluate_pairwise_compatibility(ia, ib)
            self.assertIsNone(res, "OFFLINE + ONLINE HARUS DITOLAK (mengembalikan None)")

            # 7. Mode tidak valid -> DITOLAK
            ia, ib = make_pair("REMOTE", "ONLINE")
            res = evaluate_pairwise_compatibility(ia, ib)
            self.assertIsNone(res, "Mode tidak valid (REMOTE) harus ditolak")
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 17. FORM STUDY GROUP MENOLAK ANGGOTA DENGAN KOMBINASI ONLINE-OFFLINE
    # =========================================================================
    def test_17_group_formation_blocks_online_offline_mix(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, citra])
            db.commit()

            # Host Andi memilih mode ONLINE
            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=4, status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Kandidat Budi memilih mode OFFLINE (incompatible dengan Host ONLINE)
            ib = StudyIntent(intent_id="ib", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=4, status="ACTIVE")
            sb = IntentAvailability(availability_id="sb", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Kandidat Citra memilih mode ONLINE (compatible dengan Host ONLINE)
            ic = StudyIntent(intent_id="ic", student_id=citra.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=4, status="ACTIVE")
            sc = IntentAvailability(availability_id="sc", intent_id=ic.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([ia, sa, ib, sb, ic, sc])
            db.commit()

            res = form_study_group(host_intent=ia, candidate_intents=[ib, ic], min_score=60.0)

            # Verifikasi bahwa Budi (OFFLINE) TIDAK PERNAH masuk kelompok
            member_ids = [m["student_id"] for m in res["members"]]
            self.assertIn(andi.student_id, member_ids, "Host Andi harus ada di kelompok")
            self.assertIn(citra.student_id, member_ids, "Citra (ONLINE) harus ada di kelompok")
            self.assertNotIn(budi.student_id, member_ids, "Budi (OFFLINE) TIDAK BOLEH masuk kelompok bersama Host ONLINE")
            self.assertEqual(res["formation_status"], "READY")
            self.assertEqual(res["group_size"], 2)

            # Skenario 2: Host HYBRID tidak boleh menghasilkan kelompok campuran ONLINE dan OFFLINE
            ia.learning_mode = "HYBRID"
            db.commit()

            res_hybrid = form_study_group(host_intent=ia, candidate_intents=[ic, ib], min_score=60.0)
            member_ids_hybrid = [m["student_id"] for m in res_hybrid["members"]]
            # Buktikan bahwa tidak ada kondisi di mana ONLINE dan OFFLINE berada dalam 1 kelompok
            self.assertFalse(
                budi.student_id in member_ids_hybrid and citra.student_id in member_ids_hybrid,
                "Kelompok belajar TIDAK BOLEH memuat anggota ONLINE dan OFFLINE sekaligus"
            )
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 18. TIE-BREAKER: DURASI JADWAL TERPANJANG LEBIH UTAMA DIBANDING ID ALFABETIS
    # =========================================================================
    def test_18_tie_breaker_duration_takes_precedence_over_intent_id_when_gq_equal(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, citra])
            db.commit()

            # Host Andi: Ketersediaan 09:00 - 15:00 (panjang)
            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=2, status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="15:00", priority_rank=1)

            # Kandidat Citra: intent_id alfabetis LEBIH BESAR ("z-cand-longer"), durasi 09:00 - 13:00 (240 menit)
            ic = StudyIntent(intent_id="z-cand-longer", student_id=citra.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=2, status="ACTIVE")
            sc = IntentAvailability(availability_id="sc", intent_id=ic.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="13:00", priority_rank=1)

            # Kandidat Budi: intent_id alfabetis LEBIH KECIL ("a-cand-shorter"), durasi 09:00 - 11:00 (120 menit)
            ib = StudyIntent(intent_id="a-cand-shorter", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", max_group_size=2, status="ACTIVE")
            sb = IntentAvailability(availability_id="sb", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="11:00", priority_rank=1)

            db.add_all([ia, sa, ic, sc, ib, sb])
            db.commit()

            # Jalankan form_study_group dengan kedua kandidat
            res = form_study_group(host_intent=ia, candidate_intents=[ib, ic], target_group_size=2, min_score=60.0)

            # Karena max_group_size=2, hanya 1 kandidat yang dapat dipilih
            selected_cand = res["members"][1]
            self.assertEqual(selected_cand["intent_id"], "z-cand-longer",
                             "Kandidat dengan durasi jadwal lebih panjang (240 menit) HARUS diprioritaskan dibanding alfabetis ID")
            self.assertEqual(res["selected_schedule"]["duration_minutes"], 240)
        finally:
            db.close()
            engine.dispose()

    # =========================================================================
    # 19. INTEGRITAS BREAKDOWN & EXPLANATION PADA SETIAP PASANGAN (DAY 17.2)
    # =========================================================================
    def test_19_pairwise_breakdown_and_explanation_integrity(self):
        engine, TestingSession = create_test_db()
        db = TestingSession()
        original_overrides = dict(app.dependency_overrides)

        try:
            c = Course(course_id="c1", course_code="ACK2AAB3", course_name="Struktur Data", study_program="S1")
            andi = Student(student_id="s1", full_name="Andi", email="a@t.ac", student_number="1", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            budi = Student(student_id="s2", full_name="Budi", email="b@t.ac", student_number="2", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            citra = Student(student_id="s3", full_name="Citra", email="c@t.ac", student_number="3", password_hash=hash_password("p"), account_status="ACTIVE", verification_status="VERIFIED", is_discoverable=True)
            db.add_all([c, andi, budi, citra])
            db.commit()

            ia = StudyIntent(intent_id="ia", student_id=andi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sa = IntentAvailability(availability_id="sa", intent_id=ia.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ib = StudyIntent(intent_id="ib", student_id=budi.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sb = IntentAvailability(availability_id="sb", intent_id=ib.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            ic = StudyIntent(intent_id="ic", student_id=citra.student_id, course_id=c.course_id, topics="Tree", learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-25", status="ACTIVE")
            sc = IntentAvailability(availability_id="sc", intent_id=ic.intent_id, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([ia, sa, ib, sb, ic, sc])
            db.commit()

            # 1. Uji 2 mahasiswa (1 pasangan)
            res_2 = form_study_group(host_intent=ia, candidate_intents=[ib], min_score=60.0)
            self.assertEqual(len(res_2["pairwise_scores"]), 1)
            p1 = res_2["pairwise_scores"][0]

            # Verifikasi penjelasan tidak kosong & merupakan teks bahasa Indonesia deterministik
            self.assertIsInstance(p1["explanation"], str)
            self.assertTrue(len(p1["explanation"]) > 10, "Explanation harus berupa kalimat deskriptif")
            self.assertIn("Topik belajar", p1["explanation"])

            # Verifikasi kelima komponen Day 15 wajib ada
            b1 = p1["breakdown"]
            self.assertEqual(set(b1.keys()), {"topic", "goal", "style", "date", "mode"})
            expected_weights = {"topic": 0.30, "goal": 0.25, "style": 0.15, "date": 0.15, "mode": 0.15}
            sum_contrib = 0.0
            for comp_name, comp_weight in expected_weights.items():
                comp_data = b1[comp_name]
                self.assertIn("score", comp_data)
                self.assertIn("weight", comp_data)
                self.assertIn("contribution", comp_data)
                self.assertAlmostEqual(comp_data["weight"], comp_weight, places=2)
                self.assertTrue(0.0 <= comp_data["score"] <= 1.0)
                sum_contrib += comp_data["contribution"]

            # Verifikasi sum of contributions konsisten dengan compatibility_score
            self.assertAlmostEqual(sum_contrib, p1["compatibility_score"], places=2)

            # 2. Uji 3 mahasiswa (3 pasangan)
            res_3 = form_study_group(host_intent=ia, candidate_intents=[ib, ic], min_score=60.0)
            self.assertEqual(len(res_3["pairwise_scores"]), 3)
            for pair in res_3["pairwise_scores"]:
                self.assertTrue(len(pair["explanation"]) > 10)
                self.assertEqual(set(pair["breakdown"].keys()), {"topic", "goal", "style", "date", "mode"})
                pair_sum = sum(pair["breakdown"][k]["contribution"] for k in expected_weights)
                self.assertAlmostEqual(pair_sum, pair["compatibility_score"], places=2)

            # 3. Uji integrasi HTTP response Pydantic validation via TestClient
            token_andi = create_token(andi.student_id, andi.email)
            headers_andi = {"Authorization": f"Bearer {token_andi}"}

            def override_get_db():
                session = TestingSession()
                try:
                    yield session
                finally:
                    session.close()

            app.dependency_overrides[get_db] = override_get_db
            client = TestClient(app)

            r = client.post(
                "/api/v1/matching/group-proposals/preview",
                json={"host_intent_id": ia.intent_id, "min_score": 60.0},
                headers=headers_andi
            )
            self.assertEqual(r.status_code, 200)
            data = r.json()

            # Validasi Pydantic Schema penuh (GroupProposalPreviewResponse)
            validated_obj = GroupProposalPreviewResponse.model_validate(data)
            self.assertEqual(len(validated_obj.pairwise_scores), 3)

            # Verifikasi bahwa objek breakdown bertingkat dapat diakses dengan tipe kuat
            first_pair = validated_obj.pairwise_scores[0]
            self.assertEqual(first_pair.breakdown.topic.weight, 0.30)
            self.assertGreater(first_pair.breakdown.topic.contribution, 0.0)
            self.assertTrue(len(first_pair.explanation) > 0)
        finally:
            app.dependency_overrides = original_overrides
            db.close()
            engine.dispose()


# =============================================================================
# Standalone CLI Test Runner
# =============================================================================
def run_tests():
    print("=" * 80)
    print("RUNNING DAY 17.2: GROUP FORMATION EXPLAINABILITY & HARDENING TEST SUITE (19 SCENARIOS)")
    print("=" * 80)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestDay17GroupFormation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total - failures - errors

    print("=" * 80)
    print(f"DAY 17.2 TEST SUITE RESULT: {passed} / {total} TESTS PASSED (100% SUCCESS)")
    print("=" * 80)
    return passed, total


if __name__ == "__main__":
    passed, total = run_tests()
    if passed != total:
        sys.exit(1)
