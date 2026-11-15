# ==============================================================================
# test_day19_quality_evaluation.py - Test Suite Evaluasi Kualitas Matching (Day 19.1 & 19.1.1)
# ==============================================================================
# Rangkaian pengujian untuk memvalidasi:
# 1. Metrik Kualitas Kelompok: APS, MPS, GQ sesuai spesifikasi Day 7 & Day 19.
# 2. Distribusi Skor Pairwise: Mean, Median, Min, Max, Disparitas, Variansi, Std Dev.
# 3. Konsistensi Pembulatan Decimal ROUND_HALF_UP (D19.1-01: Paritas distribution.mean == APS).
# 4. Validasi Ketat Kelengkapan 5 Komponen Breakdown (D19.1-02: Topic, Goal, Style, Date, Mode).
# 5. Identifikasi Weakest Link (Pasangan Terlemah / Bottleneck) & Strongest Link.
# 6. Validasi Konsistensi Formula Matematis (0.70 * APS + 0.30 * MPS).
# 7. Benchmark Kelompok A vs Kelompok B (Pembuktian Penalti 30% MPS).
# 8. Integrasi Evaluator dengan Output Engine Group Formation Aktual.
# ==============================================================================

import unittest
import math
from decimal import Decimal
from pathlib import Path
import sys

# Pastikan folder backend masuk ke sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models import Student, Course, StudyIntent, IntentAvailability
from app.group_formation import form_study_group, calculate_group_quality_score
from app.matching_evaluation import (
    calculate_pairwise_distribution,
    verify_gq_consistency,
    verify_pairwise_breakdown_consistency,
    identify_weakest_and_strongest_links,
    determine_quality_tier,
    generate_quality_notes,
    evaluate_group_quality,
    validate_benchmark_cases,
)
from app.schemas import (
    PairwiseScoreDistribution,
    WeakestLinkDetail,
    StrongestLinkDetail,
    FormulaConsistencyCheck,
    GroupQualityEvaluationResult,
)


def make_student(student_id: str, name: str, email: str, student_number: str = None) -> Student:
    return Student(
        student_id=student_id,
        full_name=name,
        email=email,
        student_number=student_number or f"120125{student_id}",
        study_program="S1 Teknik Komputer",
        academic_year=2025,
        password_hash="test_password_hash",
        verification_status="VERIFIED",
        account_status="ACTIVE",
        is_discoverable=True
    )


def make_intent(
    intent_id: str,
    student_id: str,
    course_id: str,
    topics: str = "Struktur Data",
    goal: str = "UNDERSTAND",
    style: str = "DISCUSSION",
    mode: str = "OFFLINE",
    min_size: int = 2,
    max_size: int = 4,
    earliest_date: str = "2026-11-20",
    latest_date: str = "2026-11-30"
) -> StudyIntent:
    return StudyIntent(
        intent_id=intent_id,
        student_id=student_id,
        course_id=course_id,
        topics=topics,
        learning_goal=goal,
        collaboration_style=style,
        learning_mode=mode,
        earliest_date=earliest_date,
        latest_date=latest_date,
        min_group_size=min_size,
        max_group_size=max_size,
        status="ACTIVE"
    )


class TestDay19QualityEvaluation(unittest.TestCase):
    """Test suite komprehensif Day 19.1 & 19.1.1: Quality Evaluation."""

    def test_01_pairwise_score_distribution_calculation(self):
        """
        Menguji perhitungan statistik sebaran skor pairwise:
        mean (APS), median, min (MPS), max, disparitas, variansi, dan standar deviasi.
        """
        # Kasus 1: 3 pasangan (ganjil)
        scores_1 = [90.0, 85.0, 80.0]
        dist_1 = calculate_pairwise_distribution(scores_1)
        self.assertEqual(dist_1.count, 3)
        self.assertEqual(dist_1.mean, 85.0)
        self.assertEqual(dist_1.median, 85.0)
        self.assertEqual(dist_1.min_score, 80.0)
        self.assertEqual(dist_1.max_score, 90.0)
        self.assertEqual(dist_1.score_spread, 10.0)
        # Populasi: mean=85, selisih=[-5, 0, 5], sum_sq=50, var=50/3 ≈ 16.67, std ≈ 4.08
        self.assertAlmostEqual(dist_1.variance, 16.67, places=2)
        self.assertAlmostEqual(dist_1.std_dev, 4.08, places=2)

        # Kasus 2: 4 pasangan (genap)
        scores_2 = [70.0, 80.0, 90.0, 100.0]
        dist_2 = calculate_pairwise_distribution(scores_2)
        self.assertEqual(dist_2.count, 4)
        self.assertEqual(dist_2.mean, 85.0)
        self.assertEqual(dist_2.median, 85.0)  # (80 + 90) / 2
        self.assertEqual(dist_2.min_score, 70.0)
        self.assertEqual(dist_2.max_score, 100.0)
        self.assertEqual(dist_2.score_spread, 30.0)

        # Kasus 3: Pasangan tunggal (N=1)
        scores_single = [88.5]
        dist_single = calculate_pairwise_distribution(scores_single)
        self.assertEqual(dist_single.count, 1)
        self.assertEqual(dist_single.mean, 88.5)
        self.assertEqual(dist_single.score_spread, 0.0)
        self.assertEqual(dist_single.variance, 0.0)
        self.assertEqual(dist_single.std_dev, 0.0)

        # Kasus 4: List kosong
        dist_empty = calculate_pairwise_distribution([])
        self.assertEqual(dist_empty.count, 0)
        self.assertEqual(dist_empty.mean, 0.0)

    def test_01b_decimal_round_half_up_boundary_consistency_with_gq_engine(self):
        """
        D19.1-01 Hardening:
        Menguji paritas 100% konsisten antara distribution.mean dengan average_pair_score
        dari calculate_group_quality_score() menggunakan Decimal ROUND_HALF_UP.
        Menguji kasus kritis [1.00, 1.01] (di mana float round menghasilkan 1.00 tetapi ROUND_HALF_UP menghasilkan 1.01).
        """
        boundary_cases = [
            [1.00, 1.01],         # sum=2.01, mean=1.005 -> ROUND_HALF_UP = 1.01
            [0.00, 0.01],         # sum=0.01, mean=0.005 -> ROUND_HALF_UP = 0.01
            [99.99, 100.00],      # sum=199.99, mean=99.995 -> ROUND_HALF_UP = 100.00
            [80.00, 80.01, 80.02],# sum=240.03, mean=80.01 -> 80.01
            [75.555, 75.555],     # exact parity
            [60.05, 60.04, 60.06],# sum=180.15, mean=60.05 -> 60.05
        ]

        for case in boundary_cases:
            gq, aps, mps = calculate_group_quality_score(case)
            dist = calculate_pairwise_distribution(case)

            # Memvalidasi distribution.mean identik tanpa selisih terhadap aps
            self.assertEqual(
                dist.mean, aps,
                f"Gagal pada case {case}: dist.mean ({dist.mean}) != engine aps ({aps})"
            )
            # Memvalidasi min_score identik dengan mps
            self.assertEqual(
                dist.min_score, mps,
                f"Gagal pada case {case}: dist.min_score ({dist.min_score}) != engine mps ({mps})"
            )

    def test_02_formula_consistency_verification(self):
        """
        Menguji validasi konsistensi formula matematis:
        GQ = 0.70 * APS + 0.30 * MPS
        Memastikan verifikasi mendeteksi jika terjadi deviasi atau inkonsistensi.
        """
        # Konsisten
        aps = 85.00
        mps = 80.00
        expected_gq = 83.50  # 0.7*85 + 0.3*80 = 59.5 + 24.0 = 83.5
        check_ok = verify_gq_consistency(expected_gq, aps, mps)
        self.assertTrue(check_ok.is_valid)
        self.assertEqual(check_ok.discrepancy, 0.0)
        self.assertEqual(check_ok.expected_gq, 83.50)
        self.assertEqual(check_ok.actual_gq, 83.50)
        self.assertIn("0.70 * 85.00 + 0.30 * 80.00 = 83.50", check_ok.formula_expression)

        # Tidak konsisten (terjadi manipulasi/bug pada nilai GQ)
        corrupted_gq = 95.00
        check_bad = verify_gq_consistency(corrupted_gq, aps, mps)
        self.assertFalse(check_bad.is_valid)
        self.assertEqual(check_bad.expected_gq, 83.50)
        self.assertEqual(check_bad.actual_gq, 95.00)
        self.assertAlmostEqual(check_bad.discrepancy, 11.50, places=2)

    def test_03_pairwise_breakdown_consistency(self):
        """
        Menguji verifikasi apakah skor pasangan konsisten dengan penjumlahan
        seluruh kontribusi sub-komponen Day 15 (Topic, Goal, Style, Schedule, Mode).
        """
        # Breakdown konsisten lengkap 5 komponen
        valid_pair = {
            "compatibility_score": 85.00,
            "breakdown": {
                "topic": {"score": 90.0, "weight": 0.30, "contribution": 27.00},
                "goal": {"score": 80.0, "weight": 0.20, "contribution": 16.00},
                "style": {"score": 85.0, "weight": 0.15, "contribution": 12.75},
                "date": {"score": 85.0, "weight": 0.25, "contribution": 21.25},
                "mode": {"score": 80.0, "weight": 0.10, "contribution": 8.00},
            }
        }
        res_valid = verify_pairwise_breakdown_consistency(valid_pair)
        self.assertTrue(res_valid["is_consistent"])
        self.assertEqual(res_valid["sum_of_contributions"], 85.00)
        self.assertEqual(res_valid["discrepancy"], 0.0)

        # Breakdown tidak konsisten (total_score != sum_contributions)
        corrupted_pair = {
            "compatibility_score": 95.00,
            "breakdown": {
                "topic": {"contribution": 20.00},
                "goal": {"contribution": 15.00},
                "style": {"contribution": 10.00},
                "date": {"contribution": 15.00},
                "mode": {"contribution": 10.00},
            }
        }
        res_corrupt = verify_pairwise_breakdown_consistency(corrupted_pair)
        self.assertFalse(res_corrupt["is_consistent"])
        self.assertEqual(res_corrupt["sum_of_contributions"], 70.00)
        self.assertEqual(res_corrupt["compatibility_score"], 95.00)
        self.assertEqual(res_corrupt["discrepancy"], 25.00)

    def test_03b_breakdown_validation_rejects_incomplete_or_invalid_components(self):
        """
        D19.1-02 Hardening:
        Memastikan validator menolak (is_consistent = False) apabila:
        1. Ada satu atau lebih dari kelima komponen wajib (topic, goal, style, date, mode) yang hilang.
        2. Breakdown kosong atau None.
        3. Komponen bernilai non-numeric, None, boolean, atau NaN.
        4. Compatibility Score bernilai boolean, NaN, atau hilang.
        """
        # Kasus 1: Komponen 'mode' hilang meskipun jumlah 4 komponen lain kebetulan sama dengan CS
        pair_missing_mode = {
            "compatibility_score": 80.00,
            "breakdown": {
                "topic": {"contribution": 30.00},
                "goal": {"contribution": 20.00},
                "style": {"contribution": 15.00},
                "date": {"contribution": 15.00},
                # 'mode' sengaja dihilangkan
            }
        }
        res_m1 = verify_pairwise_breakdown_consistency(pair_missing_mode)
        self.assertFalse(res_m1["is_consistent"])
        self.assertIn("mode", res_m1["missing_components"])
        self.assertIn("Komponen wajib tidak lengkap", res_m1["error"])

        # Kasus 2: Komponen 'topic' dan 'goal' hilang
        pair_missing_two = {
            "compatibility_score": 30.00,
            "breakdown": {
                "style": {"contribution": 10.00},
                "date": {"contribution": 10.00},
                "mode": {"contribution": 10.00},
            }
        }
        res_m2 = verify_pairwise_breakdown_consistency(pair_missing_two)
        self.assertFalse(res_m2["is_consistent"])
        self.assertIn("topic", res_m2["missing_components"])
        self.assertIn("goal", res_m2["missing_components"])

        # Kasus 3: Breakdown kosong / None
        res_empty = verify_pairwise_breakdown_consistency({"compatibility_score": 80.0, "breakdown": {}})
        self.assertFalse(res_empty["is_consistent"])
        self.assertEqual(len(res_empty["missing_components"]), 5)

        res_none = verify_pairwise_breakdown_consistency({"compatibility_score": 80.0, "breakdown": None})
        self.assertFalse(res_none["is_consistent"])

        # Kasus 4: Komponen memiliki contribution bernilai tidak valid (string, boolean, None, NaN)
        pair_invalid_contrib = {
            "compatibility_score": 75.00,
            "breakdown": {
                "topic": {"contribution": "invalid_string"},
                "goal": {"contribution": None},
                "style": {"contribution": True},  # Boolean bukan float valid
                "date": {"contribution": float("nan")},
                "mode": {"contribution": 10.00},
            }
        }
        res_inv = verify_pairwise_breakdown_consistency(pair_invalid_contrib)
        self.assertFalse(res_inv["is_consistent"])
        self.assertGreater(len(res_inv["invalid_components"]), 0)

        # Kasus 4b: Komponen bertipe string numerik (misal "20.00") harus ditolak ketat
        pair_numeric_str = {
            "compatibility_score": 75.00,
            "breakdown": {
                "topic": {"contribution": "20.00"},  # String numerik harus ditolak
                "goal": {"contribution": 15.00},
                "style": {"contribution": 15.00},
                "date": {"contribution": 15.00},
                "mode": {"contribution": 10.00},
            }
        }
        res_num_str = verify_pairwise_breakdown_consistency(pair_numeric_str)
        self.assertFalse(res_num_str["is_consistent"])
        self.assertIn("topic", res_num_str["invalid_components"])

        # Kasus 5: Compatibility Score tidak valid (None, boolean, NaN)
        pair_bad_cs = {
            "compatibility_score": True,
            "breakdown": {
                "topic": {"contribution": 20.0}, "goal": {"contribution": 20.0},
                "style": {"contribution": 15.0}, "date": {"contribution": 15.0},
                "mode": {"contribution": 10.0}
            }
        }
        res_bad_cs = verify_pairwise_breakdown_consistency(pair_bad_cs)
        self.assertFalse(res_bad_cs["is_consistent"])

    def test_04_weakest_and_strongest_links_identification(self):
        """
        Menguji identifikasi pasangan terlemah (bottleneck MPS) dan pasangan terkuat
        beserta informasi anggota dan sub-komponennya.
        """
        pairs = [
            {
                "student_a_id": "s1", "student_b_id": "s2",
                "intent_a_id": "i1", "intent_b_id": "i2",
                "compatibility_score": 92.5,
                "explanation": "Kecocokan sangat tinggi pada topik dan jadwal.",
                "breakdown": {"topic": {"score": 100.0, "contribution": 30.0}}
            },
            {
                "student_a_id": "s1", "student_b_id": "s3",
                "intent_a_id": "i1", "intent_b_id": "i3",
                "compatibility_score": 68.0,
                "explanation": "Terdapat perbedaan gaya belajar dan tujuan.",
                "breakdown": {"topic": {"score": 70.0, "contribution": 21.0}}
            },
            {
                "student_a_id": "s2", "student_b_id": "s3",
                "intent_a_id": "i2", "intent_b_id": "i3",
                "compatibility_score": 84.0,
                "explanation": "Kecocokan baik secara keseluruhan.",
                "breakdown": {"topic": {"score": 85.0, "contribution": 25.5}}
            },
        ]

        weak, strong = identify_weakest_and_strongest_links(pairs)

        self.assertIsNotNone(weak)
        self.assertIsNotNone(strong)
        # Weakest link harus pasangan s1-s3 dengan skor 68.0
        self.assertEqual(weak.student_a_id, "s1")
        self.assertEqual(weak.student_b_id, "s3")
        self.assertEqual(weak.score, 68.0)
        self.assertIn("perbedaan gaya belajar", weak.explanation)

        # Strongest link harus pasangan s1-s2 dengan skor 92.5
        self.assertEqual(strong.student_a_id, "s1")
        self.assertEqual(strong.student_b_id, "s2")
        self.assertEqual(strong.score, 92.5)

    def test_05_benchmark_case_kelompok_a_vs_kelompok_b(self):
        """
        Validasi matematis Benchmark Standar:
        Kelompok A: [90.0, 85.0, 80.0] -> APS=85.0, MPS=80.0, GQ=83.50
        Kelompok B: [100.0, 100.0, 40.0] -> APS=80.0, MPS=40.0, GQ=68.00

        Membuktikan bahwa Kelompok A lebih unggul daripada Kelompok B
        karena bobot 30% MPS mencegah kelompok yang memiliki satu pasangan bermasalah.
        """
        benchmarks = validate_benchmark_cases()
        eval_a = benchmarks["kelompok_a"]
        eval_b = benchmarks["kelompok_b"]

        # Validasi Kelompok A
        self.assertEqual(eval_a.average_pair_score, 85.00)
        self.assertEqual(eval_a.minimum_pair_score, 80.00)
        self.assertEqual(eval_a.group_quality_score, 83.50)
        self.assertEqual(eval_a.quality_tier, "GOOD")
        self.assertTrue(eval_a.formula_consistency.is_valid)

        # Validasi Kelompok B
        self.assertEqual(eval_b.average_pair_score, 80.00)
        self.assertEqual(eval_b.minimum_pair_score, 40.00)
        self.assertEqual(eval_b.group_quality_score, 68.00)
        self.assertEqual(eval_b.quality_tier, "SATISFACTORY")
        self.assertTrue(eval_b.formula_consistency.is_valid)

        # Pembuktian keunggulan Kelompok A
        self.assertGreater(eval_a.group_quality_score, eval_b.group_quality_score)
        self.assertEqual(round(eval_a.group_quality_score - eval_b.group_quality_score, 2), 15.50)

        # Validasi disparitas pada Kelompok B
        self.assertEqual(eval_b.distribution.score_spread, 60.00)
        self.assertEqual(eval_a.distribution.score_spread, 10.00)

    def test_06_quality_tier_boundaries(self):
        """
        Menguji batasan kategori tier kualitas:
        EXCELLENT (>= 85), GOOD (75 - 84.99), SATISFACTORY (65 - 74.99), NEEDS_IMPROVEMENT (< 65).
        """
        self.assertEqual(determine_quality_tier(92.0), "EXCELLENT")
        self.assertEqual(determine_quality_tier(85.0), "EXCELLENT")
        self.assertEqual(determine_quality_tier(84.99), "GOOD")
        self.assertEqual(determine_quality_tier(75.0), "GOOD")
        self.assertEqual(determine_quality_tier(74.99), "SATISFACTORY")
        self.assertEqual(determine_quality_tier(65.0), "SATISFACTORY")
        self.assertEqual(determine_quality_tier(64.99), "NEEDS_IMPROVEMENT")
        self.assertEqual(determine_quality_tier(50.0), "NEEDS_IMPROVEMENT")

    def test_07_quality_notes_generation(self):
        """
        Menguji pembuatan catatan diagnostik evaluasi yang transparan,
        termasuk analisis penalti MPS, disparitas, dan faktor pembatas weakest link.
        """
        dist = PairwiseScoreDistribution(
            count=3, mean=85.0, median=85.0, std_dev=12.5, variance=156.25,
            min_score=70.0, max_score=95.0, score_spread=25.0
        )
        weakest = WeakestLinkDetail(
            student_a_id="A", student_b_id="B", score=70.0,
            breakdown={"topic": {"score": 50.0}, "goal": {"score": 80.0}}
        )

        notes = generate_quality_notes(80.5, 85.0, 70.0, dist, weakest)
        self.assertTrue(any("kategori 'GOOD'" in n for n in notes))
        self.assertTrue(any("Penalti kecocokan minimum" in n for n in notes))
        self.assertTrue(any("variasi kecocokan signifikan" in n for n in notes))
        self.assertTrue(any("Faktor pembatas utama" in n and "topic" in n for n in notes))

    def test_08_evaluate_group_quality_from_raw_scores(self):
        """
        Menguji evaluate_group_quality saat menerima list skor numerik pasangan.
        Memvalidasi Pydantic model GroupQualityEvaluationResult.
        """
        raw_scores = [88.0, 82.0, 76.0]
        result = evaluate_group_quality(raw_scores)

        self.assertIsInstance(result, GroupQualityEvaluationResult)
        self.assertEqual(result.average_pair_score, 82.00)
        self.assertEqual(result.minimum_pair_score, 76.00)
        # GQ = 0.70 * 82.0 + 0.30 * 76.0 = 57.4 + 22.8 = 80.20
        self.assertEqual(result.group_quality_score, 80.20)
        self.assertEqual(result.quality_tier, "GOOD")
        self.assertTrue(result.formula_consistency.is_valid)
        self.assertEqual(result.all_pairwise_scores, [88.0, 82.0, 76.0])

    def test_09_evaluate_group_quality_from_formation_engine_output(self):
        """
        Menguji integrasi langsung evaluate_group_quality dengan output dictionary aktual
        yang dihasilkan oleh form_study_group (Day 17/18 engine).
        """
        course = Course(course_id="c_d19", course_code="CS202", course_name="Algoritma Lanjut", study_program="S1")

        s1 = make_student("s1", "Host Alpha", "alpha@t.ac.id")
        s2 = make_student("s2", "Member Beta", "beta@t.ac.id")
        s3 = make_student("s3", "Member Gamma", "gamma@t.ac.id")

        i1 = make_intent("i1", "s1", "c_d19", topics="Dynamic Programming", min_size=3, max_size=4)
        a1 = IntentAvailability(availability_id="a1", intent_id="i1", day_or_date="2026-11-25", start_time="10:00", end_time="13:00", priority_rank=1)
        i1.availabilities = [a1]
        i1.student = s1
        i1.course = course

        i2 = make_intent("i2", "s2", "c_d19", topics="Dynamic Programming", min_size=3, max_size=4)
        a2 = IntentAvailability(availability_id="a2", intent_id="i2", day_or_date="2026-11-25", start_time="10:00", end_time="13:00", priority_rank=1)
        i2.availabilities = [a2]
        i2.student = s2
        i2.course = course

        i3 = make_intent("i3", "s3", "c_d19", topics="Dynamic Programming", min_size=3, max_size=4)
        a3 = IntentAvailability(availability_id="a3", intent_id="i3", day_or_date="2026-11-25", start_time="10:00", end_time="13:00", priority_rank=1)
        i3.availabilities = [a3]
        i3.student = s3
        i3.course = course

        # Jalankan form_study_group aktual
        formation_output = form_study_group(
            host_intent=i1,
            candidate_intents=[i2, i3],
            min_score=60.0
        )

        self.assertEqual(formation_output["formation_status"], "READY")
        self.assertEqual(formation_output["group_size"], 3)
        self.assertEqual(len(formation_output["pairwise_scores"]), 3)

        # Evaluasi dengan modul matching_evaluation
        eval_result = evaluate_group_quality(formation_output)

        self.assertIsInstance(eval_result, GroupQualityEvaluationResult)
        self.assertEqual(eval_result.group_quality_score, formation_output["group_quality_score"])
        self.assertEqual(eval_result.average_pair_score, formation_output["average_pair_score"])
        self.assertEqual(eval_result.minimum_pair_score, formation_output["minimum_pair_score"])
        self.assertTrue(eval_result.formula_consistency.is_valid)

        # Verifikasi weakest & strongest link terisi lengkap
        self.assertIsNotNone(eval_result.weakest_link)
        self.assertIsNotNone(eval_result.strongest_link)
        self.assertEqual(eval_result.weakest_link.score, formation_output["minimum_pair_score"])
        self.assertGreaterEqual(eval_result.strongest_link.score, eval_result.weakest_link.score)

        # Verifikasi breakdown sub-komponen pada setiap pasangan konsisten
        for p_item in formation_output["pairwise_scores"]:
            bd_check = verify_pairwise_breakdown_consistency(p_item)
            self.assertTrue(bd_check["is_consistent"])

    def test_10_mathematical_precision_rounding_half_up(self):
        """
        Menguji presisi pembulatan matematis Decimal ROUND_HALF_UP pada pecahan tak hingga
        (contoh: 3 pasangan dengan rata-rata berulang) untuk menjamin tidak ada IEEE-754 drift.
        """
        # Skor dengan nilai desimal berulang: 100/3 ≈ 33.3333333333...
        # Misal: [73.33, 73.33, 73.34] -> sum = 220.0, APS = 73.333333...
        scores = [73.33, 73.33, 73.34]
        result = evaluate_group_quality(scores)

        # APS = 220 / 3 = 73.3333... dibulatkan ROUND_HALF_UP = 73.33
        # MPS = 73.33
        # GQ = 0.70 * 73.33 + 0.30 * 73.33 = 73.33
        self.assertEqual(result.average_pair_score, 73.33)
        self.assertEqual(result.minimum_pair_score, 73.33)
        self.assertEqual(result.group_quality_score, 73.33)
        self.assertTrue(result.formula_consistency.is_valid)
        self.assertEqual(result.formula_consistency.discrepancy, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
