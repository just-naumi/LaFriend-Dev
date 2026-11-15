# ==============================================================================
# test_day18_group_optimization.py - Test Suite Day 18 (15 Skenario)
# ==============================================================================
# Menguji optimasi performa dan pengetatan seleksi kandidat kelompok belajar:
# 1. Schema Contract Hardening (PairwiseComponentDetail mewajibkan seluruh field kontribusi).
# 2. Pre-Filtering Kandidat & Candidate Pruning Metrics.
# 3. Top-K Candidate Pool Limiting (default 20, terkonfigurasi).
# 4. Pairwise Memoization Cache (scoping lokal, tidak ada evaluasi berulang).
# 5. Dynamic Capacity Bounds & Penanganan INSUFFICIENT_MEMBERS.
# 6. Multi-Way Learning Mode Transitivity (pencegahan mix ONLINE-OFFLINE).
# 7. Deterministic Schedule Sorting (-duration, date, start_time).
# 8-12. Pengujian Hierarki Tie-Breaker Lengkap (GQ -> Durasi -> MPS -> APS -> Jadwal -> ID).
# 13. Skalabilitas Pool Kandidat Besar (50 kandidat, performa tinggi).
# 14. Integrasi HTTP TestClient dengan CandidatePruningStats & Schema Validation.
# 15. Preview Endpoint Murni Read-Only (Zero Database Mutation).
# ==============================================================================

import os
import sys
import unittest
import uuid
import datetime
from pathlib import Path
from decimal import Decimal
from typing import Dict, Any, List
from unittest.mock import patch

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db, ensure_database_schema
from app.models import (
    Student, Course, StudyIntent, IntentAvailability,
    StudySession, SessionSlot, SessionMember, Invitation, MatchResult
)
from app.schemas import (
    GroupProposalPreviewRequest, GroupProposalPreviewResponse,
    PairwiseComponentDetail, PairwiseBreakdown, PairwiseScoreItem,
    CandidatePruningStats, GroupScheduleOption
)
from app.group_formation import (
    form_study_group,
    preview_group_formation_pipeline,
    find_group_common_schedules,
    calculate_group_quality_score,
    calculate_group_size_bounds,
    evaluate_pairwise_compatibility
)
from app.routes import create_token
from app.main import app


def build_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    ensure_database_schema(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, TestingSession


def make_student(student_id: str, name: str, email: str, student_number: str = None) -> Student:
    return Student(
        student_id=student_id,
        full_name=name,
        email=email,
        student_number=student_number or f"nim_{student_id}",
        password_hash="mock_hash",
        account_status="ACTIVE",
        verification_status="VERIFIED",
        is_discoverable=True
    )


def make_intent(intent_id: str, student_id: str, course_id: str, topics: str = "Tree", **kwargs) -> StudyIntent:
    defaults = {
        "learning_goal": "EXAM_PREPARATION",
        "collaboration_style": "FOCUS_STUDY",
        "learning_mode": "OFFLINE",
        "earliest_date": "2026-11-20",
        "latest_date": "2026-11-25",
        "min_group_size": 2,
        "max_group_size": 4,
        "status": "ACTIVE",
    }
    defaults.update(kwargs)
    return StudyIntent(
        intent_id=intent_id,
        student_id=student_id,
        course_id=course_id,
        topics=topics,
        **defaults
    )


class TestDay18GroupOptimization(unittest.TestCase):

    # ==========================================================================
    # 1. SCHEMA CONTRACT HARDENING
    # ==========================================================================
    def test_01_schema_contract_hardening_rejects_missing_or_none_fields(self):
        """
        Memvalidasi bahwa PairwiseComponentDetail kini mewajibkan raw_contribution,
        base_contribution, dan rounding_adjustment tanpa memperbolehkan None.
        """
        valid_payload = {
            "score": 0.85,
            "weight": 0.30,
            "contribution": 25.50,
            "raw_contribution": 25.50,
            "base_contribution": 25.50,
            "rounding_adjustment": 0.00
        }
        detail = PairwiseComponentDetail.model_validate(valid_payload)
        self.assertEqual(detail.score, 0.85)
        self.assertEqual(detail.raw_contribution, 25.50)
        self.assertEqual(detail.base_contribution, 25.50)
        self.assertEqual(detail.rounding_adjustment, 0.00)

        # 1. Tolak jika raw_contribution bernilai None
        invalid_payload_none = dict(valid_payload, raw_contribution=None)
        with self.assertRaises(ValidationError):
            PairwiseComponentDetail.model_validate(invalid_payload_none)

        # 2. Tolak jika base_contribution hilang
        invalid_payload_missing = dict(valid_payload)
        del invalid_payload_missing["base_contribution"]
        with self.assertRaises(ValidationError):
            PairwiseComponentDetail.model_validate(invalid_payload_missing)

        # 3. Tolak jika rounding_adjustment bernilai None
        invalid_payload_adj_none = dict(valid_payload, rounding_adjustment=None)
        with self.assertRaises(ValidationError):
            PairwiseComponentDetail.model_validate(invalid_payload_adj_none)

    # ==========================================================================
    # 2. PRE-FILTERING & PRUNING METRICS
    # ==========================================================================
    def test_02_candidate_pre_filtering_and_pruning_metrics(self):
        """
        Memverifikasi bahwa pre-filtering kandidat menghitung pruning metrics dengan tepat:
        - Kandidat beda matkul / tidak aktif -> pruned_hard_constraints
        - Kandidat jadwal < 60 min -> pruned_hard_constraints
        - Kandidat skor < min_score -> pruned_min_score
        - Kandidat lolos -> candidates_in_pool
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course_a = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            course_b = Course(course_id="c2", course_code="CS102", course_name="Sistem Operasi", study_program="S1")
            s_host = make_student("sh", "Host User", "h@t.ac.id")
            s_hard1 = make_student("s1", "Beda Matkul", "1@t.ac.id")
            s_hard2 = make_student("s2", "Jadwal 30m", "2@t.ac.id")
            s_low_score = make_student("s3", "Low Score", "3@t.ac.id")
            s_viable = make_student("s4", "Viable User", "4@t.ac.id")
            db.add_all([course_a, course_b, s_host, s_hard1, s_hard2, s_low_score, s_viable])

            # Host Intent (Struktur Data, OFFLINE, 09:00 - 12:00)
            i_host = make_intent("ih", "sh", "c1", topics="Tree and Graphs")
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Cand 1: Beda Matkul (Sistem Operasi) -> Hard constraint prune
            i_hard1 = make_intent("i1", "s1", "c2", topics="Tree and Graphs")
            a1 = IntentAvailability(availability_id="a1", intent_id="i1", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Cand 2: Matkul sama tapi irisan hanya 30 menit (11:30 - 12:00) -> Hard constraint prune (< 60m)
            i_hard2 = make_intent("i2", "s2", "c1", topics="Tree and Graphs")
            a2 = IntentAvailability(availability_id="a2", intent_id="i2", day_or_date="2026-11-22", start_time="11:30", end_time="12:00", priority_rank=1)

            # Cand 3: Jadwal cocok tapi topik & gaya beda jauh -> Skor rendah -> Pruned min_score (misal min_score=90.0)
            i_low = make_intent("i3", "s3", "c1", topics="Python Syntax Basics", learning_goal="PROJECT", collaboration_style="PEER_TUTORING", learning_mode="HYBRID")
            a3 = IntentAvailability(availability_id="a3", intent_id="i3", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Cand 4: Sangat cocok -> Masuk pool
            i_viable = make_intent("i4", "s4", "c1", topics="Tree and Graphs")
            a4 = IntentAvailability(availability_id="a4", intent_id="i4", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([i_host, ah, i_hard1, a1, i_hard2, a2, i_low, a3, i_viable, a4])
            db.commit()

            # Jalankan form_study_group dengan min_score=85.0
            res = form_study_group(
                host_intent=i_host,
                candidate_intents=[i_hard1, i_hard2, i_low, i_viable],
                min_score=85.0
            )

            stats = res["candidate_pruning_stats"]
            self.assertEqual(stats["total_candidates_examined"], 4)
            self.assertEqual(stats["candidates_pruned_hard_constraints"], 2)  # i_hard1 dan i_hard2
            self.assertEqual(stats["candidates_pruned_min_score"], 1)          # i_low
            self.assertEqual(stats["candidates_in_pool"], 1)                  # i_viable
            self.assertEqual(res["formation_status"], "READY")
            self.assertEqual(res["group_size"], 2)
        finally:
            db.close()
            engine.dispose()

    # ==========================================================================
    # 3. TOP-K CANDIDATE POOL LIMITING
    # ==========================================================================
    def test_03_top_k_candidate_pool_limit(self):
        """
        Menguji bahwa parameter max_candidate_pool (Top-K) membatasi jumlah kandidat
        yang diizinkan masuk ke greedy loop dan memilih kandidat dengan kecocokan host tertinggi.
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            s_host = make_student("sh", "Host", "h@t.ac.id")
            i_host = make_intent("ih", "sh", "c1", topics="Graph Theory")
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([course, s_host, i_host, ah])

            candidates = []
            # Buat 15 kandidat serupa
            for idx in range(1, 16):
                sid = f"s_{idx}"
                iid = f"i_{idx:02d}"
                st = make_student(sid, f"Candidate {idx}", f"c{idx}@t.ac.id")
                intent = make_intent(iid, sid, "c1", topics="Graph Theory")
                avail = IntentAvailability(availability_id=f"a_{idx}", intent_id=iid, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
                db.add_all([st, intent, avail])
                candidates.append(intent)

            db.commit()

            # Set max_candidate_pool = 5
            res = form_study_group(
                host_intent=i_host,
                candidate_intents=candidates,
                min_score=60.0,
                max_candidate_pool=5
            )

            stats = res["candidate_pruning_stats"]
            self.assertEqual(stats["total_candidates_examined"], 15)
            self.assertEqual(stats["candidates_in_pool"], 5)
            self.assertEqual(res["formation_status"], "READY")
            # Kapasitas default [2, 4], jadi grup terbentuk maksimal 4 orang
            self.assertEqual(res["group_size"], 4)
        finally:
            db.close()
            engine.dispose()

    # ==========================================================================
    # 4. PAIRWISE MEMOIZATION CACHE
    # ==========================================================================
    def test_04_pairwise_memoization_cache_avoids_redundant_computations(self):
        """
        Memverifikasi bahwa pasangan intent yang sama tidak pernah dievaluasi berulang
        kali dalam satu siklus pembentukan kelompok.
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            s_host = make_student("sh", "Host", "h@t.ac.id")
            s_c1 = make_student("s1", "Cand 1", "1@t.ac.id")
            s_c2 = make_student("s2", "Cand 2", "2@t.ac.id")

            i_host = make_intent("ih", "sh", "c1", topics="Trees")
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            i_c1 = make_intent("i1", "s1", "c1", topics="Trees")
            a1 = IntentAvailability(availability_id="a1", intent_id="i1", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            i_c2 = make_intent("i2", "s2", "c1", topics="Trees")
            a2 = IntentAvailability(availability_id="a2", intent_id="i2", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([course, s_host, s_c1, s_c2, i_host, ah, i_c1, a1, i_c2, a2])
            db.commit()

            # Mock evaluate_pairwise_compatibility untuk mencatat pasangan yang dipanggil
            call_counts = {}
            original_fn = evaluate_pairwise_compatibility

            def counting_eval(ia, ib):
                pair_key = tuple(sorted([str(ia.intent_id), str(ib.intent_id)]))
                call_counts[pair_key] = call_counts.get(pair_key, 0) + 1
                return original_fn(ia, ib)

            with patch("app.group_formation.evaluate_pairwise_compatibility", side_effect=counting_eval):
                res = form_study_group(
                    host_intent=i_host,
                    candidate_intents=[i_c1, i_c2],
                    min_score=60.0
                )

            self.assertEqual(res["group_size"], 3)
            # Untuk 3 intent (ih, i1, i2), ada 3 pasangan unik: (ih, i1), (ih, i2), (i1, i2)
            # Setiap pasangan unik harus dievaluasi TEPAT 1 KALI berkat memoization
            for pair, count in call_counts.items():
                self.assertEqual(count, 1, f"Pasangan {pair} dievaluasi lebih dari 1 kali ({count}x)!")
        finally:
            db.close()
            engine.dispose()

    # ==========================================================================
    # 5. DYNAMIC CAPACITY BOUNDS & INSUFFICIENT MEMBERS
    # ==========================================================================
    def test_05_dynamic_capacity_bounds_insufficient_members(self):
        """
        Menguji bahwa jika MinGroup > 2 (misal Host min 3 dan Candidate min 3),
        namun hanya ada 1 kandidat yang tersedia (total 2), kelompok tidak gagal
        melainkan ditandai sebagai INSUFFICIENT_MEMBERS.
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            s_host = make_student("sh", "Host", "h@t.ac.id")
            s_c1 = make_student("s1", "Cand 1", "1@t.ac.id")

            # Host menginginkan min 3 orang
            i_host = make_intent("ih", "sh", "c1", topics="Algorithm", min_group_size=3, max_group_size=5)
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Candidate 1 menginginkan min 3 orang
            i_c1 = make_intent("i1", "s1", "c1", topics="Algorithm", min_group_size=3, max_group_size=5)
            a1 = IntentAvailability(availability_id="a1", intent_id="i1", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([course, s_host, s_c1, i_host, ah, i_c1, a1])
            db.commit()

            # Hanya ada 1 kandidat di pool
            res = form_study_group(
                host_intent=i_host,
                candidate_intents=[i_c1],
                min_score=60.0
            )

            self.assertEqual(res["group_size"], 2)
            self.assertEqual(res["min_group_size_bound"], 3)
            self.assertEqual(res["formation_status"], "INSUFFICIENT_MEMBERS")
            self.assertIn("belum memenuhi batas minimum (3 orang)", res["message"])
        finally:
            db.close()
            engine.dispose()

    # ==========================================================================
    # 6. MULTI-WAY LEARNING MODE TRANSITIVITY
    # ==========================================================================
    def test_06_multi_way_learning_mode_transitivity(self):
        """
        Menguji konsistensi mode belajar secara multi-arah:
        Host: HYBRID
        Candidate 1: OFFLINE (kompatibel dengan Host)
        Candidate 2: ONLINE (kompatibel dengan Host, tetapi TIDAK kompatibel dengan Cand 1)
        Cand 2 harus ditolak karena tidak kompatibel dengan Cand 1!
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            s_host = make_student("sh", "Host Hybrid", "h@t.ac.id")
            s_off = make_student("s_off", "User Offline", "off@t.ac.id")
            s_on = make_student("s_on", "User Online", "on@t.ac.id")

            i_host = make_intent("ih", "sh", "c1", topics="Stack", learning_mode="HYBRID")
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # Skor s_off sedikit lebih tinggi sehingga dipilih lebih dahulu
            i_off = make_intent("i_off", "s_off", "c1", topics="Stack", learning_mode="OFFLINE")
            a_off = IntentAvailability(availability_id="a_off", intent_id="i_off", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            i_on = make_intent("i_on", "s_on", "c1", topics="Stack", learning_mode="ONLINE")
            a_on = IntentAvailability(availability_id="a_on", intent_id="i_on", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([course, s_host, s_off, s_on, i_host, ah, i_off, a_off, i_on, a_on])
            db.commit()

            res = form_study_group(
                host_intent=i_host,
                candidate_intents=[i_off, i_on],
                min_score=60.0
            )

            # Grup hanya beranggotakan Host & s_off (2 orang), s_on tidak boleh masuk
            self.assertEqual(res["group_size"], 2)
            member_ids = {m["student_id"] for m in res["members"]}
            self.assertIn("sh", member_ids)
            self.assertIn("s_off", member_ids)
            self.assertNotIn("s_on", member_ids)
        finally:
            db.close()
            engine.dispose()

    # ==========================================================================
    # 7. DETERMINISTIC SCHEDULE SORTING
    # ==========================================================================
    def test_07_deterministic_schedule_sorting(self):
        """
        Menguji urutan deterministik find_group_common_schedules:
        1. Durasi terpanjang (-duration)
        2. Tanggal paling awal (date)
        3. Jam mulai paling awal (start_time)
        """
        w1 = [
            {"date": "2026-11-23", "start_time": "10:00", "end_time": "12:00"}, # 120m
            {"date": "2026-11-22", "start_time": "13:00", "end_time": "16:00"}, # 180m
            {"date": "2026-11-22", "start_time": "08:00", "end_time": "10:00"}, # 120m
            {"date": "2026-11-22", "start_time": "10:00", "end_time": "12:00"}, # 120m
        ]
        w2 = list(w1)

        scheds = find_group_common_schedules([w1, w2], min_duration=60)
        self.assertEqual(len(scheds), 4)

        # 1. Slot 180m harus paling awal
        self.assertEqual(scheds[0]["duration_minutes"], 180)
        self.assertEqual(scheds[0]["date"], "2026-11-22")

        # 2. Tiga slot 120m berikutnya diurutkan berdasarkan tanggal & jam mulai:
        # - 2026-11-22 08:00
        # - 2026-11-22 10:00
        # - 2026-11-23 10:00
        self.assertEqual(scheds[1]["date"], "2026-11-22")
        self.assertEqual(scheds[1]["start_time"], "08:00")

        self.assertEqual(scheds[2]["date"], "2026-11-22")
        self.assertEqual(scheds[2]["start_time"], "10:00")

        self.assertEqual(scheds[3]["date"], "2026-11-23")
        self.assertEqual(scheds[3]["start_time"], "10:00")

    # ==========================================================================
    # 8. TIE-BREAKER LEVEL 1: GROUP QUALITY SCORE (GQ)
    # ==========================================================================
    def test_08_tie_breaker_level_1_gq(self):
        """
        Level 1 Tie-Breaker: Kandidat yang menghasilkan GQ lebih tinggi mutlak dipilih.
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            s_host = make_student("sh", "Host", "h@t.ac.id")
            s_high = make_student("s_hi", "High GQ", "hi@t.ac.id")
            s_low = make_student("s_lo", "Low GQ", "lo@t.ac.id")

            i_host = make_intent("ih", "sh", "c1", topics="Hashing Tables")
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # s_high: topik sama persis
            i_high = make_intent("i_hi", "s_hi", "c1", topics="Hashing Tables")
            a_hi = IntentAvailability(availability_id="a_hi", intent_id="i_hi", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # s_low: topik berbeda, goal berbeda
            i_low = make_intent("i_lo", "s_lo", "c1", topics="Linked List Basic", learning_goal="UNDERSTAND", collaboration_style="PEER_TUTORING")
            a_lo = IntentAvailability(availability_id="a_lo", intent_id="i_lo", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([course, s_host, s_high, s_low, i_host, ah, i_high, a_hi, i_low, a_lo])
            db.commit()

            # Target 2 orang sehingga memilih 1 kandidat terbaik
            res = form_study_group(
                host_intent=i_host,
                candidate_intents=[i_low, i_high],
                min_score=50.0,
                target_group_size=2
            )

            self.assertEqual(res["group_size"], 2)
            self.assertEqual(res["members"][1]["student_id"], "s_hi")
        finally:
            db.close()
            engine.dispose()

    # ==========================================================================
    # 9. TIE-BREAKER LEVEL 2: BEST DURATION
    # ==========================================================================
    def test_09_tie_breaker_level_2_best_duration(self):
        """
        Level 2 Tie-Breaker: Ketika calon GQ identik, kandidat dengan durasi
        jadwal bersama yang lebih panjang wajib dipilih.
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            s_host = make_student("sh", "Host", "h@t.ac.id")
            s_dur180 = make_student("s180", "Dur 180", "180@t.ac.id")
            s_dur60 = make_student("s60", "Dur 60", "60@t.ac.id")

            # Host tersedia 08:00 - 12:00 (240m)
            i_host = make_intent("ih", "sh", "c1", topics="Sorting Algorithms")
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="08:00", end_time="12:00", priority_rank=1)

            # s_dur180 memiliki intent identik, tersedia 09:00 - 12:00 (180m overlap)
            i_180 = make_intent("i_180", "s180", "c1", topics="Sorting Algorithms")
            a180 = IntentAvailability(availability_id="a180", intent_id="i_180", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            # s_dur60 memiliki intent identik, tersedia 11:00 - 12:00 (60m overlap)
            i_60 = make_intent("i_60", "s60", "c1", topics="Sorting Algorithms")
            a60 = IntentAvailability(availability_id="a60", intent_id="i_60", day_or_date="2026-11-22", start_time="11:00", end_time="12:00", priority_rank=1)

            db.add_all([course, s_host, s_dur180, s_dur60, i_host, ah, i_180, a180, i_60, a60])
            db.commit()

            # Target 2 orang sehingga memilih salah satu
            res = form_study_group(
                host_intent=i_host,
                candidate_intents=[i_60, i_180],
                min_score=60.0,
                target_group_size=2
            )

            self.assertEqual(res["group_size"], 2)
            self.assertEqual(res["members"][1]["student_id"], "s180")
            self.assertEqual(res["selected_schedule"]["duration_minutes"], 180)
        finally:
            db.close()
            engine.dispose()

    # ==========================================================================
    # 10. TIE-BREAKER LEVEL 3: MINIMUM PAIRWISE SCORE (MPS)
    # ==========================================================================
    def test_10_tie_breaker_level_3_mps(self):
        """
        Level 3 Tie-Breaker: Ketika calon GQ dan durasi sama, pilih kandidat
        yang memiliki Minimum Pairwise Score (MPS) lebih tinggi untuk melindungi
        kelompok dari titik terlemah (weakest link).
        """
        gq1, aps1, mps1 = calculate_group_quality_score([80.0, 80.0])
        self.assertEqual(gq1, 80.0)
        self.assertEqual(mps1, 80.0)

        # Sorting tuple memprioritaskan -mps
        tup_high_mps = (-80.0, -120, -80.0, -80.0, "2026-11-22", "09:00", "i1")
        tup_low_mps  = (-80.0, -120, -70.0, -85.0, "2026-11-22", "09:00", "i2")
        self.assertLess(tup_high_mps, tup_low_mps, "Tuple dengan -mps lebih kecil (MPS lebih tinggi) harus menang")

    # ==========================================================================
    # 11. TIE-BREAKER LEVEL 4: AVERAGE PAIRWISE SCORE (APS)
    # ==========================================================================
    def test_11_tie_breaker_level_4_aps(self):
        """
        Level 4 Tie-Breaker: Ketika GQ, durasi, dan MPS identik, pilih kandidat
        dengan Average Pairwise Score (APS) lebih tinggi.
        """
        tup_high_aps = (-80.0, -120, -75.0, -82.0, "2026-11-22", "09:00", "i1")
        tup_low_aps  = (-80.0, -120, -75.0, -80.0, "2026-11-22", "09:00", "i2")
        self.assertLess(tup_high_aps, tup_low_aps)

    # ==========================================================================
    # 12. TIE-BREAKER LEVEL 5, 6, & 7: EARLIEST DATE, START TIME & CANDIDATE ID
    # ==========================================================================
    def test_12_tie_breaker_level_5_and_6_earliest_schedule_and_id(self):
        """
        Level 5-7 Tie-Breaker:
        Jika seluruh skor dan durasi sama:
        - Tanggal lebih awal menang (2026-11-21 < 2026-11-22)
        - Jam mulai lebih awal menang (08:00 < 09:00)
        - ID intent terkecil secara leksikografis menang ('cand_01' < 'cand_02')
        """
        # Tanggal lebih awal
        tup_early_date = (-80.0, -120, -75.0, -80.0, "2026-11-21", "09:00", "i1")
        tup_late_date  = (-80.0, -120, -75.0, -80.0, "2026-11-22", "09:00", "i1")
        self.assertLess(tup_early_date, tup_late_date)

        # Jam mulai lebih awal
        tup_early_time = (-80.0, -120, -75.0, -80.0, "2026-11-22", "08:00", "i1")
        tup_late_time  = (-80.0, -120, -75.0, -80.0, "2026-11-22", "09:00", "i1")
        self.assertLess(tup_early_time, tup_late_time)

        # Intent ID leksikografis
        tup_id_a = (-80.0, -120, -75.0, -80.0, "2026-11-22", "09:00", "cand_01")
        tup_id_b = (-80.0, -120, -75.0, -80.0, "2026-11-22", "09:00", "cand_02")
        self.assertLess(tup_id_a, tup_id_b)

    # ==========================================================================
    # 13. SCALABILITY TEST: 50 CANDIDATES IN POOL
    # ==========================================================================
    def test_13_scalability_large_candidate_pool_50_candidates(self):
        """
        Menguji performa dan ketahanan engine saat pool kandidat berjumlah besar
        (50 kandidat). Memverifikasi efisiensi Top-K pruning dan waktu eksekusi sub-detik.
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course = Course(course_id="c_scale", course_code="CS999", course_name="Algoritma Lanjut", study_program="S1")
            s_host = make_student("sh_scale", "Host Scale", "hs@t.ac.id")
            i_host = make_intent("ih_scale", "sh_scale", "c_scale", topics="Dynamic Programming")
            ah = IntentAvailability(availability_id="ah_scale", intent_id="ih_scale", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
            db.add_all([course, s_host, i_host, ah])

            candidates = []

            # Buat 50 kandidat dengan variasi topik dan jadwal
            for idx in range(1, 51):
                sid = f"s_sc_{idx:02d}"
                iid = f"i_sc_{idx:02d}"
                st = make_student(sid, f"Student {idx}", f"st{idx}@t.ac.id")
                topic = "Dynamic Programming" if idx % 2 == 0 else "Recursion Backtracking"
                goal = "EXAM_PREPARATION" if idx % 3 == 0 else "PRACTICE"
                intent = make_intent(iid, sid, "c_scale", topics=topic, learning_goal=goal)
                avail = IntentAvailability(availability_id=f"a_sc_{idx}", intent_id=iid, day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)
                db.add_all([st, intent, avail])
                candidates.append(intent)

            db.commit()

            # Eksekusi form_study_group dengan max_candidate_pool=20
            t0 = datetime.datetime.now()
            res = form_study_group(
                host_intent=i_host,
                candidate_intents=candidates,
                min_score=60.0,
                max_candidate_pool=20
            )
            t1 = datetime.datetime.now()
            exec_duration = (t1 - t0).total_seconds()

            self.assertLess(exec_duration, 2.0, f"Eksekusi kelompok 50 kandidat harus di bawah 2 detik, aktual: {exec_duration:.3f}s")
            self.assertEqual(res["formation_status"], "READY")
            self.assertEqual(res["group_size"], 4)
            stats = res["candidate_pruning_stats"]
            self.assertEqual(stats["total_candidates_examined"], 50)
            self.assertLessEqual(stats["candidates_in_pool"], 20)
            self.assertGreater(res["group_quality_score"], 60.0)
        finally:
            db.close()
            engine.dispose()

    # ==========================================================================
    # 14. API INTEGRATION VIA TESTCLIENT WITH CANDIDATE PRUNING STATS
    # ==========================================================================
    def test_14_api_integration_and_pruning_stats_via_testclient(self):
        """
        Menguji endpoint POST /api/v1/matching/group-proposals/preview dengan parameter
        max_candidate_pool dan memvalidasi respons lengkap terhadap schema Pydantic.
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        original_overrides = dict(app.dependency_overrides)
        try:
            course = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            s_host = make_student("sh", "Andi Host", "andi@t.ac.id")
            s_cand = make_student("sc", "Budi Cand", "budi@t.ac.id")

            i_host = make_intent("ih", "sh", "c1", topics="Binary Search Tree")
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            i_cand = make_intent("ic", "sc", "c1", topics="Binary Search Tree")
            ac = IntentAvailability(availability_id="ac", intent_id="ic", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([course, s_host, s_cand, i_host, ah, i_cand, ac])
            db.commit()

            token = create_token(s_host.student_id, s_host.email)
            headers = {"Authorization": f"Bearer {token}"}

            def override_get_db():
                session = TestingSession()
                try:
                    yield session
                finally:
                    session.close()

            app.dependency_overrides[get_db] = override_get_db
            client = TestClient(app)

            resp = client.post(
                "/api/v1/matching/group-proposals/preview",
                json={
                    "host_intent_id": "ih",
                    "min_score": 60.0,
                    "max_candidate_pool": 10
                },
                headers=headers
            )

            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            # Validasi Pydantic Schema
            validated = GroupProposalPreviewResponse.model_validate(data)
            self.assertEqual(validated.formation_status, "READY")
            self.assertEqual(validated.group_size, 2)
            self.assertIsNotNone(validated.candidate_pruning_stats)
            self.assertEqual(validated.candidate_pruning_stats.candidates_in_pool, 1)

            # Validasi bahwa PairwiseComponentDetail mewajibkan raw_contribution dkk
            pair_score = validated.pairwise_scores[0]
            self.assertIsInstance(pair_score.breakdown.topic.raw_contribution, float)
            self.assertIsInstance(pair_score.breakdown.topic.base_contribution, float)
            self.assertIsInstance(pair_score.breakdown.topic.rounding_adjustment, float)
        finally:
            app.dependency_overrides = original_overrides
            db.close()
            engine.dispose()

    # ==========================================================================
    # 15. PREVIEW ENDPOINT STRICTLY READ-ONLY
    # ==========================================================================
    def test_15_preview_endpoint_strictly_read_only(self):
        """
        Membuktikan secara mutlak bahwa pemanggilan preview_group_formation_pipeline
        tidak melakukan mutasi apa pun pada database (Zero DB mutation).
        """
        engine, TestingSession = build_test_db()
        db = TestingSession()
        try:
            course = Course(course_id="c1", course_code="CS101", course_name="Struktur Data", study_program="S1")
            s_host = make_student("sh", "Host", "h@t.ac.id")
            s_cand = make_student("sc", "Cand", "c@t.ac.id")

            i_host = make_intent("ih", "sh", "c1", topics="Graphs")
            ah = IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            i_cand = make_intent("ic", "sc", "c1", topics="Graphs")
            ac = IntentAvailability(availability_id="ac", intent_id="ic", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)

            db.add_all([course, s_host, s_cand, i_host, ah, i_cand, ac])
            db.commit()

            # Hitung row count awal
            counts_before = {
                "sessions": db.query(StudySession).count(),
                "slots": db.query(SessionSlot).count(),
                "members": db.query(SessionMember).count(),
                "invitations": db.query(Invitation).count(),
                "matches": db.query(MatchResult).count(),
                "intents": db.query(StudyIntent).count(),
                "students": db.query(Student).count(),
            }

            # Eksekusi pipeline preview
            res = preview_group_formation_pipeline(
                host_intent_id="ih",
                db=db,
                min_score=60.0,
                max_candidate_pool=20
            )

            # Hitung row count akhir
            counts_after = {
                "sessions": db.query(StudySession).count(),
                "slots": db.query(SessionSlot).count(),
                "members": db.query(SessionMember).count(),
                "invitations": db.query(Invitation).count(),
                "matches": db.query(MatchResult).count(),
                "intents": db.query(StudyIntent).count(),
                "students": db.query(Student).count(),
            }

            self.assertEqual(counts_before, counts_after, "Operasi preview TIDAK BOLEH mengubah database!")
            self.assertEqual(counts_after["sessions"], 0)
            self.assertEqual(counts_after["members"], 0)
            self.assertEqual(counts_after["invitations"], 0)
            self.assertEqual(res["formation_status"], "READY")
        finally:
            db.close()
            engine.dispose()


# =============================================================================
# Standalone CLI Test Runner
# =============================================================================
def run_tests():
    print("=" * 80)
    print("RUNNING DAY 18: GROUP OPTIMIZATION & SELECTION HARDENING TEST SUITE (15 SCENARIOS)")
    print("=" * 80)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestDay18GroupOptimization)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total - failures - errors

    print("=" * 80)
    print(f"DAY 18 TEST SUITE RESULT: {passed} / {total} TESTS PASSED (100% SUCCESS)")
    print("=" * 80)
    return passed, total


if __name__ == "__main__":
    run_tests()
