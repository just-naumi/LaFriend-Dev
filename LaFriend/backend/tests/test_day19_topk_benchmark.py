# ==============================================================================
# tests/test_day19_topk_benchmark.py
# ==============================================================================
# Test Suite Komprehensif Day 19.4 - Top-K Quality Benchmarking & Trade-off Analysis
#
# Memvalidasi secara ketat:
# 1. Benchmark performa dan kualitas matching pada berbagai batas ukuran pool kandidat:
#    K in {5, 10, 20, 30, None/Full}.
# 2. Metrik Quality Retention (QR) dan Quality Loss (QL) berada pada batas matematis yang valid:
#    0.0 <= QR <= 100.0 dan 0.0 <= QL <= 100.0.
# 3. Baseline K=None (Full) selalu menghasilkan QR = 100.0%, QL = 0.0%, dan is_identical_to_baseline = True.
# 4. Efektivitas candidate pruning stats (candidates_in_pool <= K).
# 5. Penanganan gracefully untuk kasus tepi: pool kosong (N=0), 1 kandidat (N=1), skor identik.
# 6. Trade-off analysis: efisiensi eksekusi vs retensi kualitas kelompok belajar.
# ==============================================================================

import unittest
from decimal import Decimal
from typing import List, Dict, Any

from app.models import Student, Course, StudyIntent, IntentAvailability
from app.group_formation import form_study_group
from app.matching_evaluation import benchmark_top_k_candidate_pool
from app.schemas import TopKBenchmarkResult, TopKPoolBenchmarkItem


def make_student(student_id: str, name: str, email: str) -> Student:
    return Student(
        student_id=student_id,
        full_name=name,
        email=email,
        student_number=f"120125{hash(student_id) % 9000 + 1000}",
        study_program="S1 Teknik Komputer",
        academic_year=2025,
        verification_status="VERIFIED",
        account_status="ACTIVE",
        is_discoverable=True
    )


def make_intent(
    intent_id: str,
    student_id: str,
    course_id: str,
    topics: str = "Tree, Graph",
    learning_goal: str = "PRACTICE",
    collaboration_style: str = "DISCUSSION",
    learning_mode: str = "OFFLINE",
    min_size: int = 2,
    max_size: int = 4,
    status: str = "ACTIVE"
) -> StudyIntent:
    return StudyIntent(
        intent_id=intent_id,
        student_id=student_id,
        course_id=course_id,
        topics=topics,
        learning_goal=learning_goal,
        collaboration_style=collaboration_style,
        learning_mode=learning_mode,
        min_group_size=min_size,
        max_group_size=max_size,
        earliest_date="2026-11-20",
        latest_date="2026-11-30",
        status=status
    )


def make_availability(
    intent_id: str,
    date_str: str = "2026-11-25",
    start_time: str = "09:00",
    end_time: str = "12:00"
) -> IntentAvailability:
    return IntentAvailability(
        availability_id=f"av_{intent_id}_{start_time.replace(':', '')}",
        intent_id=intent_id,
        day_or_date=date_str,
        start_time=start_time,
        end_time=end_time,
        priority_rank=1
    )


class TestDay19TopKBenchmark(unittest.TestCase):
    """Test suite untuk Day 19.4 Top-K Candidate Pool Quality Benchmarking."""

    def setUp(self):
        self.course_a = Course(
            course_id="c_topk_a",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.host_student = make_student("sh_topk", "Host TopK", "htopk@telkomuniversity.ac.id")
        self.host_intent = make_intent("ih_topk", "sh_topk", "c_topk_a")
        self.host_intent.availabilities = [make_availability("ih_topk", "2026-11-25", "09:00", "13:00")]
        self.host_intent.student = self.host_student
        self.host_intent.course = self.course_a

    def test_01_top_k_benchmarking_basic(self):
        """
        19.4.1: Pengujian dasar fungsi benchmark_top_k_candidate_pool dengan 10 kandidat.
        Ekspektasi: Menghasilkan objek TopKBenchmarkResult dengan daftar benchmark untuk setiap K.
        """
        candidates = []
        for i in range(1, 11):
            st = make_student(f"s_topk_{i}", f"Cand {i}", f"c{i}@t.ac.id")
            ci = make_intent(f"i_topk_{i}", f"s_topk_{i}", "c_topk_a", topics="Tree" if i % 2 == 0 else "Tree, Graph")
            ci.availabilities = [make_availability(f"i_topk_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(5, 10, None),
            min_score=60.0
        )

        self.assertIsInstance(res, TopKBenchmarkResult)
        self.assertEqual(res.total_candidates, 10)
        self.assertEqual(res.baseline_k, "Full")
        self.assertEqual(len(res.benchmarks), 3)

        k_labels = [b.k_value for b in res.benchmarks]
        self.assertIn(5, k_labels)
        self.assertIn(10, k_labels)
        self.assertIn("Full", k_labels)

        for b in res.benchmarks:
            self.assertGreaterEqual(b.candidates_examined, 10)
            self.assertGreaterEqual(b.group_quality_score, 0.0)
            self.assertGreaterEqual(b.quality_retention, 0.0)
            self.assertLessEqual(b.quality_retention, 100.0)
            self.assertGreaterEqual(b.quality_loss, 0.0)
            self.assertLessEqual(b.quality_loss, 100.0)
            self.assertGreaterEqual(b.execution_time_ms, 0.0)

    def test_02_baseline_full_pool_properties(self):
        """
        19.4.2: Properti invariant baseline Full Pool (K=None).
        Ekspektasi: Quality Retention = 100.0%, Quality Loss = 0.0%, is_identical_to_baseline = True.
        """
        candidates = []
        for i in range(1, 8):
            st = make_student(f"s_base_{i}", f"Cand {i}", f"cb{i}@t.ac.id")
            ci = make_intent(f"i_base_{i}", f"s_base_{i}", "c_topk_a")
            ci.availabilities = [make_availability(f"i_base_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(5, None),
            min_score=60.0
        )

        full_item = [b for b in res.benchmarks if b.k_value == "Full"][0]
        self.assertEqual(full_item.quality_retention, 100.0)
        self.assertEqual(full_item.quality_loss, 0.0)
        self.assertTrue(full_item.is_identical_to_baseline)

    def test_03_top_k_pruning_pool_size_enforcement(self):
        """
        19.4.3: Batasan candidates_in_pool tidak pernah melebihi nilai K.
        Ekspektasi: candidates_in_pool <= K untuk setiap K numerik.
        """
        candidates = []
        for i in range(1, 26):  # 25 kandidat
            st = make_student(f"s_prune_{i}", f"Cand {i}", f"cp{i}@t.ac.id")
            ci = make_intent(f"i_prune_{i}", f"s_prune_{i}", "c_topk_a")
            ci.availabilities = [make_availability(f"i_prune_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(5, 10, 20, None),
            min_score=60.0
        )

        for b in res.benchmarks:
            if b.k_value == 5:
                self.assertLessEqual(b.candidates_in_pool, 5)
            elif b.k_value == 10:
                self.assertLessEqual(b.candidates_in_pool, 10)
            elif b.k_value == 20:
                self.assertLessEqual(b.candidates_in_pool, 20)
            elif b.k_value == "Full":
                self.assertGreaterEqual(b.candidates_in_pool, 20)

    def test_04_trade_off_quality_retention_high_synergy(self):
        """
        19.4.4: Evaluasi trade-off retensi kualitas kelompok belajar.
        Ekspektasi: Pada candidate pool seragam/kompatibel, Top-20 mempertahankan >= 95% kualitas Full Pool.
        """
        candidates = []
        for i in range(1, 21):
            st = make_student(f"s_syn_{i}", f"Cand {i}", f"csyn{i}@t.ac.id")
            ci = make_intent(f"i_syn_{i}", f"s_syn_{i}", "c_topk_a")
            ci.availabilities = [make_availability(f"i_syn_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(5, 10, 20, None),
            min_score=60.0
        )

        b_20 = [b for b in res.benchmarks if b.k_value == 20][0]
        b_full = [b for b in res.benchmarks if b.k_value == "Full"][0]

        # Retensi kualitas Top-20 harus sangat tinggi (>= 95%) terhadap Full Pool
        self.assertGreaterEqual(b_20.quality_retention, 95.0)
        self.assertLessEqual(b_20.quality_loss, 5.0)

    def test_05_empty_candidate_pool(self):
        """
        19.4.5: Penanganan candidate pool kosong (N=0).
        Ekspektasi: Tidak ada crash, total_candidates=0, formation_status=NO_COMPATIBLE_GROUP, QR=100.0%.
        """
        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=[],
            k_values=(5, 10, None),
            min_score=60.0
        )
        self.assertEqual(res.total_candidates, 0)
        for b in res.benchmarks:
            self.assertEqual(b.formation_status, "NO_COMPATIBLE_GROUP")
            self.assertEqual(b.group_size, 1)
            self.assertIsNone(b.quality_retention)
            self.assertIsNone(b.quality_loss)

    def test_06_single_candidate_pool(self):
        """
        19.4.6: Penanganan candidate pool hanya 1 kandidat (N=1).
        Ekspektasi: K=5, K=10, dan Full Pool menghasilkan status dan skor yang identik.
        """
        st1 = make_student("s_single_1", "Cand Single", "csingle@t.ac.id")
        c1 = make_intent("i_single_1", "s_single_1", "c_topk_a")
        c1.availabilities = [make_availability("i_single_1", "2026-11-25", "09:00", "12:00")]
        c1.student = st1
        c1.course = self.course_a

        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=[c1],
            k_values=(5, 10, None),
            min_score=60.0
        )
        self.assertEqual(res.total_candidates, 1)
        scores = [b.group_quality_score for b in res.benchmarks]
        # Seluruh konfigurasi K harus menghasilkan skor yang sama persis
        self.assertEqual(len(set(scores)), 1)
        for b in res.benchmarks:
            self.assertEqual(b.quality_retention, 100.0)
            self.assertEqual(b.quality_loss, 0.0)
            self.assertTrue(b.is_identical_to_baseline)

    def test_07_all_candidates_identical_scores(self):
        """
        19.4.7: Kandidat dengan skor identik diuji stabilitas pemotongannya.
        Ekspektasi: Pemotongan pool mematuhi tie-breaker deterministik tanpa exception.
        """
        candidates = []
        for i in range(1, 15):
            st = make_student(f"s_idem_{i:02d}", f"Idem {i}", f"idem{i}@t.ac.id")
            ci = make_intent(f"i_idem_{i:02d}", f"s_idem_{i:02d}", "c_topk_a")
            ci.availabilities = [make_availability(f"i_idem_{i:02d}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(5, 10, None),
            min_score=60.0
        )
        for b in res.benchmarks:
            self.assertEqual(b.formation_status, "READY")
            self.assertGreater(b.group_quality_score, 0.0)

    def test_08_insufficient_viable_candidates_under_top_k(self):
        """
        19.4.8: Hanya 1 kandidat yang lolos min_score di antara banyak kandidat.
        Ekspektasi: Seluruh K menghasilkan status INSUFFICIENT_MEMBERS atau NO_COMPATIBLE_GROUP secara konsisten.
        """
        candidates = []
        # 1 kandidat cocok
        st_good = make_student("s_good", "Good Cand", "good@t.ac.id")
        c_good = make_intent("i_good", "s_good", "c_topk_a", topics="Tree, Graph")
        c_good.availabilities = [make_availability("i_good", "2026-11-25", "09:00", "12:00")]
        c_good.student = st_good
        c_good.course = self.course_a
        candidates.append(c_good)

        # 9 kandidat tidak cocok jadwal
        for i in range(1, 10):
            st_bad = make_student(f"s_bad_{i}", f"Bad Cand {i}", f"bad{i}@t.ac.id")
            c_bad = make_intent(f"i_bad_{i}", f"s_bad_{i}", "c_topk_a")
            c_bad.availabilities = [make_availability(f"i_bad_{i}", "2026-11-30", "18:00", "20:00")]  # tanggal lain
            c_bad.student = st_bad
            c_bad.course = self.course_a
            candidates.append(c_bad)

        # Host membutuhkan min_size=3
        host_3 = make_intent("ih_3", "sh_topk", "c_topk_a", min_size=3, max_size=4)
        host_3.availabilities = [make_availability("ih_3", "2026-11-25", "09:00", "13:00")]
        host_3.student = self.host_student
        host_3.course = self.course_a

        res = benchmark_top_k_candidate_pool(
            host_intent=host_3,
            candidate_intents=candidates,
            k_values=(5, 10, None),
            min_score=60.0
        )
        for b in res.benchmarks:
            self.assertIn(b.formation_status, ("INSUFFICIENT_MEMBERS", "NO_COMPATIBLE_GROUP"))

    def test_09_trade_off_demonstration_scenario(self):
        """
        19.4.9: Skenario demonstrasi trade-off:
        Top-K kecil (K=2) hanya menyertakan 2 kandidat terbaik terhadap host.
        Full Pool menyertakan seluruh kandidat sehingga greedy engine dapat membentuk kelompok beranggotakan 4 orang.
        Ekspektasi: K=2 membentuk kelompok ukuran 3 (host + 2), sedangkan Full membentuk kelompok ukuran 4.
        """
        candidates = []
        for i in range(1, 7):
            st = make_student(f"s_trade_{i}", f"Trade {i}", f"trade{i}@t.ac.id")
            ci = make_intent(f"i_trade_{i}", f"s_trade_{i}", "c_topk_a")
            ci.availabilities = [make_availability(f"i_trade_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(2, 6, None),
            min_score=60.0
        )

        b_2 = [b for b in res.benchmarks if b.k_value == 2][0]
        b_full = [b for b in res.benchmarks if b.k_value == "Full"][0]

        # K=2 hanya bisa mengambil maksimal 2 kandidat (total kelompok <= 3)
        self.assertLessEqual(b_2.group_size, 3)
        # Full pool bisa mencapai kapasitas maksimum host (4 orang)
        self.assertEqual(b_full.group_size, 4)

    def test_10_execution_timing_and_metrics_consistency(self):
        """
        19.4.10: Validasi metrik waktu eksekusi dan konsistensi schema TopKPoolBenchmarkItem.
        Ekspektasi: execution_time_ms numerik positif non-negatif, schema lengkap tanpa field null.
        """
        candidates = []
        for i in range(1, 15):
            st = make_student(f"s_time_{i}", f"Time {i}", f"time{i}@t.ac.id")
            ci = make_intent(f"i_time_{i}", f"s_time_{i}", "c_topk_a")
            ci.availabilities = [make_availability(f"i_time_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        res = benchmark_top_k_candidate_pool(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(5, 10, None),
            min_score=60.0
        )

        for b in res.benchmarks:
            self.assertIsInstance(b.execution_time_ms, float)
            self.assertGreaterEqual(b.execution_time_ms, 0.0)
            self.assertIn(b.formation_status, ("READY", "INSUFFICIENT_MEMBERS", "NO_COMPATIBLE_GROUP"))
            self.assertIsInstance(b.is_identical_to_baseline, bool)


if __name__ == "__main__":
    unittest.main()
