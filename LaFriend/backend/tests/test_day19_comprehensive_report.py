# ==============================================================================
# tests/test_day19_comprehensive_report.py
# ==============================================================================
# Test Suite Komprehensif Day 19.5 & 19.6 - Performance Metrics, Aggregated Report,
# and End-to-End System Verification
#
# Memvalidasi secara ketat:
# 1. Agregasi 4 pilar pengujian dalam ComprehensiveEvaluationReport:
#    - Group Quality Evaluation (Day 19.1 & 19.1.1)
#    - Matching Stability & Order Invariance (Day 19.2)
#    - Robustness & CVR 0% (Day 19.3)
#    - Top-K Candidate Pool Benchmarking (Day 19.4)
# 2. Ringkasan metrik (overall_status, quality_score_mean, DR, CVR, Top-K retention).
# 3. Serialisasi Pydantic model_dump() dan model_dump_json().
# 4. Penanganan graceful untuk skenario data tidak ideal dan candidate pool kosong.
# 5. Regresi end-to-end tanpa merusak fungsi Day 13 s/d 18.
# ==============================================================================

import unittest
from decimal import Decimal
from typing import List, Dict, Any

from app.models import Student, Course, StudyIntent, IntentAvailability
from app.group_formation import form_study_group
from app.matching_evaluation import (
    generate_comprehensive_evaluation_report,
    build_default_robustness_scenarios
)
from app.schemas import (
    ComprehensiveEvaluationReport,
    ComprehensiveEvaluationSummary,
    GroupQualityEvaluationResult,
    MatchingStabilityResult,
    RobustnessEvaluationResult,
    TopKBenchmarkResult
)


def make_student(student_id: str, name: str, email: str, acct: str = "ACTIVE", verif: str = "VERIFIED") -> Student:
    return Student(
        student_id=student_id,
        full_name=name,
        email=email,
        student_number=f"120125{hash(student_id) % 9000 + 1000}",
        study_program="S1 Teknik Komputer",
        academic_year=2025,
        verification_status=verif,
        account_status=acct,
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


class TestDay19ComprehensiveReport(unittest.TestCase):
    """Test suite untuk Day 19.5 & 19.6 Comprehensive Evaluation Report Generator."""

    def setUp(self):
        self.course_a = Course(
            course_id="c_agg_a",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.host_student = make_student("sh_agg", "Host Agg", "hagg@telkomuniversity.ac.id")
        self.host_intent = make_intent("ih_agg", "sh_agg", "c_agg_a")
        self.host_intent.availabilities = [make_availability("ih_agg", "2026-11-25", "09:00", "13:00")]
        self.host_intent.student = self.host_student
        self.host_intent.course = self.course_a

    def test_01_comprehensive_report_generation_default_scenarios(self):
        """
        19.5.1: Pembuatan laporan agregat komprehensif menggunakan default scenarios.
        Ekspektasi: Menghasilkan objek ComprehensiveEvaluationReport dengan status PASSED,
        DR = 100.0%, CVR = 0.0%, dan ke-4 pilar terisi lengkap.
        """
        candidates = []
        for i in range(1, 7):
            st = make_student(f"s_agg_{i}", f"Cand {i}", f"ca{i}@t.ac.id")
            ci = make_intent(f"i_agg_{i}", f"s_agg_{i}", "c_agg_a")
            ci.availabilities = [make_availability(f"i_agg_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            stability_permutations=10,
            min_score=60.0
        )

        self.assertIsInstance(report, ComprehensiveEvaluationReport)
        self.assertTrue(report.report_id.startswith("eval_report_"))
        self.assertEqual(report.host_intent_id, "ih_agg")

        # Validasi Summary
        summary = report.summary
        self.assertIsInstance(summary, ComprehensiveEvaluationSummary)
        self.assertEqual(summary.overall_status, "PASSED")
        self.assertEqual(summary.order_determinism_rate, 100.0)
        self.assertEqual(summary.constraint_violation_rate, 0.0)
        self.assertGreater(summary.quality_score_mean, 0.0)
        self.assertGreaterEqual(summary.topk_quality_retention, 90.0)
        self.assertGreater(summary.total_evaluation_time_ms, 0.0)
        self.assertIn("LOLOS pengujian komprehensif", summary.recommendation)

        # Validasi 4 Pilar
        self.assertIsInstance(report.quality_evaluation, GroupQualityEvaluationResult)
        self.assertIsInstance(report.stability_evaluation, MatchingStabilityResult)
        self.assertIsInstance(report.robustness_evaluation, RobustnessEvaluationResult)
        self.assertIsInstance(report.top_k_benchmark, TopKBenchmarkResult)

        # Validasi Sub-Komponen
        self.assertEqual(report.stability_evaluation.determinism_rate, 100.0)
        self.assertTrue(report.stability_evaluation.is_order_invariant)
        self.assertEqual(report.robustness_evaluation.constraint_violation_rate, 0.0)
        self.assertTrue(report.robustness_evaluation.all_constraints_preserved)

    def test_02_comprehensive_report_with_custom_robustness_scenarios(self):
        """
        19.5.2: Pembuatan laporan dengan skenario robustness kustom.
        Ekspektasi: Laporan mengevaluasi skenario kustom yang diberikan.
        """
        st_bad = make_student("s_cust_bad", "Bad Cand", "badc@t.ac.id")
        c_bad = make_intent("i_cust_bad", "s_cust_bad", "c_other_course")
        c_bad.availabilities = [make_availability("i_cust_bad")]
        c_bad.student = st_bad
        c_bad.course = Course(course_id="c_other_course", course_code="OTH", course_name="Other", study_program="S1")

        custom_scenarios = [
            {
                "scenario_name": "Custom 1: Course Mismatch",
                "description": "Kandidat berbeda course",
                "expected_status": "NO_COMPATIBLE_GROUP",
                "candidates": [c_bad],
            }
        ]

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=[],
            candidate_scenarios=custom_scenarios,
            stability_permutations=5,
            min_score=60.0
        )

        self.assertEqual(report.robustness_evaluation.total_scenarios_tested, 1)
        self.assertEqual(report.robustness_evaluation.passed_scenarios, 1)
        self.assertEqual(report.robustness_evaluation.constraint_violation_rate, 0.0)

    def test_03_warning_or_failed_status_handling(self):
        """
        19.5.3: Penanganan deteksi kegagalan constraint violation (CVR > 0).
        Ekspektasi: Jika ada skenario yang melanggar batasan, overall_status = FAILED.
        """
        # Buat skenario yang memicu mismatch status ekspektasi
        sc_fail = [
            {
                "scenario_name": "Fail Test: Expect READY but candidate empty",
                "description": "Memaksa ketidaksesuaian status ekspektasi",
                "expected_status": "READY",  # Harusnya NO_COMPATIBLE_GROUP
                "candidates": [],
            }
        ]

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=[],
            candidate_scenarios=sc_fail,
            stability_permutations=5,
            min_score=60.0
        )

        self.assertEqual(report.robustness_evaluation.failed_scenarios, 1)
        # Karena passed_scenarios != total_tested, all_constraints_preserved menjadi False
        self.assertIn(report.summary.overall_status, ("WARNING", "FAILED"))

    def test_04_top_k_retention_extraction_accuracy(self):
        """
        19.5.4: Akurasi ekstraksi Top-K retention dalam summary.
        Ekspektasi: Nilai topk_quality_retention sama dengan benchmark item K=20 (atau K terbesar).
        """
        candidates = []
        for i in range(1, 12):
            st = make_student(f"s_ret_{i}", f"Cand {i}", f"cr{i}@t.ac.id")
            ci = make_intent(f"i_ret_{i}", f"s_ret_{i}", "c_agg_a")
            ci.availabilities = [make_availability(f"i_ret_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(5, 10, None),
            stability_permutations=5,
            min_score=60.0
        )

        b_10 = [b for b in report.top_k_benchmark.benchmarks if b.k_value == 10][0]
        self.assertEqual(report.summary.topk_quality_retention, b_10.quality_retention)

    def test_05_execution_time_tracking(self):
        """
        19.5.5: Pelacakan waktu eksekusi total evaluasi.
        Ekspektasi: total_evaluation_time_ms bertipe float, positif, dan terukur.
        """
        candidates = []
        for i in range(1, 5):
            st = make_student(f"s_tim_{i}", f"Cand {i}", f"ct{i}@t.ac.id")
            ci = make_intent(f"i_tim_{i}", f"s_tim_{i}", "c_agg_a")
            ci.availabilities = [make_availability(f"i_tim_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            stability_permutations=5,
            min_score=60.0
        )

        self.assertGreater(report.summary.total_evaluation_time_ms, 0.0)
        self.assertLess(report.summary.total_evaluation_time_ms, 5000.0)

    def test_06_report_serialization_to_dict_and_json(self):
        """
        19.5.6: Validasi serialisasi Pydantic model_dump() dan model_dump_json().
        Ekspektasi: Serialisasi berjalan mulus tanpa TypeError atau Pydantic SerializationError.
        """
        st1 = make_student("s_ser_1", "Cand Ser", "cser@t.ac.id")
        c1 = make_intent("i_ser_1", "s_ser_1", "c_agg_a")
        c1.availabilities = [make_availability("i_ser_1", "2026-11-25", "09:00", "12:00")]
        c1.student = st1
        c1.course = self.course_a

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=[c1],
            stability_permutations=5,
            min_score=60.0
        )

        # 1. model_dump()
        d = report.model_dump()
        self.assertIsInstance(d, dict)
        self.assertIn("report_id", d)
        self.assertIn("summary", d)
        self.assertIn("quality_evaluation", d)
        self.assertIn("stability_evaluation", d)
        self.assertIn("robustness_evaluation", d)
        self.assertIn("top_k_benchmark", d)

        # 2. model_dump_json()
        j = report.model_dump_json()
        self.assertIsInstance(j, str)
        self.assertIn("overall_status", j)
        self.assertIn("PASSED", j)

    def test_07_empty_candidate_pool_comprehensive_report(self):
        """
        19.5.7: Penanganan candidate pool kosong secara komprehensif.
        Ekspektasi: Tidak ada crash, menghasilkan laporan berstatus PASSED dengan status NO_COMPATIBLE_GROUP.
        """
        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=[],
            stability_permutations=5,
            min_score=60.0
        )

        self.assertEqual(report.summary.overall_status, "PASSED")
        self.assertEqual(report.stability_evaluation.determinism_rate, 100.0)
        self.assertEqual(report.robustness_evaluation.constraint_violation_rate, 0.0)

    def test_08_end_to_end_regression_day13_through_day19(self):
        """
        19.6.1: Regresi sistem end-to-end Day 13 s/d Day 19.
        Ekspektasi:
        - StudyIntent & Availability tersusun valid (Day 13)
        - Hard constraints (mode, schedule, active) divalidasi (Day 14)
        - Compatibility Score Day 15 dihitung akurat
        - Greedy Stepwise Group Formation Day 17/18 membentuk grup READY
        - Group Quality, Stabilitas DR=100%, Ketahanan CVR=0%, dan Top-K retention >= 95%
        seluruhnya lolos tanpa cela.
        """
        candidates = []
        for i in range(1, 9):
            st = make_student(f"s_e2e_{i}", f"E2E Cand {i}", f"e2e_{i}@t.ac.id")
            ci = make_intent(
                f"i_e2e_{i}", f"s_e2e_{i}", "c_agg_a",
                topics="Tree, Graph",
                learning_goal="PRACTICE",
                collaboration_style="DISCUSSION",
                learning_mode="OFFLINE"
            )
            ci.availabilities = [make_availability(f"i_e2e_{i}", "2026-11-25", "09:00", "12:00")]
            ci.student = st
            ci.course = self.course_a
            candidates.append(ci)

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(5, 10, 20, None),
            stability_permutations=10,
            min_score=60.0
        )

        # Validasi status komprehensif
        self.assertEqual(report.summary.overall_status, "PASSED")
        self.assertEqual(report.summary.order_determinism_rate, 100.0)
        self.assertEqual(report.summary.constraint_violation_rate, 0.0)
        self.assertGreaterEqual(report.summary.quality_score_mean, 80.0)
        self.assertGreaterEqual(report.summary.topk_quality_retention, 95.0)

        # Validasi struktur kelompok yang terbentuk
        self.assertEqual(report.quality_evaluation.group_size, 4)
        self.assertTrue(report.quality_evaluation.is_breakdown_consistent)
        self.assertIsNotNone(report.quality_evaluation.strongest_link)
        self.assertGreaterEqual(report.quality_evaluation.strongest_link.score, 80.0)


if __name__ == "__main__":
    unittest.main()
