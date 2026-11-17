# ==============================================================================
# tests/test_day19_integrity_hardening.py
# ==============================================================================
# Test Suite Khusus Day 19.6.1 & 19.6.2 - Evaluation Integrity Hardening &
# Independent Evaluator Closure
#
# Memvalidasi secara ketat temuan audit D19.6.1-01 s/d D19.6.1-05:
# 1. D19.6.1-01: Candidate & Host Integrity (status aktif, profil student, candidate_lookup wajib jika non-host).
# 2. D19.6.1-02: Pairwise Identity & Completeness (himpunan pasangan unordered, no duplicate/missing/foreign, numeric & finite score).
# 3. D19.6.1-03: Schedule Integrity Fail-Open Closure (tahan error malformed duration/date, end > start, durasi valid).
# 4. D19.6.1-04: Top-K Benchmark Availability Sentinel (None jika benchmark numerik tidak dijalankan -> status WARNING).
# 5. D19.6.1-05: Direct Testing of Production Functions (pengujian langsung generate_comprehensive_evaluation_report).
# ==============================================================================

import math
import unittest
from unittest.mock import patch
from typing import List, Dict, Any
from decimal import Decimal

from app.models import Student, Course, StudyIntent, IntentAvailability
from app.matching_evaluation import (
    check_hard_constraint_violations,
    generate_comprehensive_evaluation_report,
    evaluate_group_quality,
    evaluate_matching_robustness
)
from app.schemas import (
    ComprehensiveEvaluationReport,
    ComprehensiveEvaluationSummary,
    TopKPoolBenchmarkItem,
    TopKBenchmarkResult
)


def make_student(
    student_id: str,
    name: str,
    email: str,
    acct: str = "ACTIVE",
    verif: str = "VERIFIED",
    discoverable: bool = True
) -> Student:
    return Student(
        student_id=student_id,
        full_name=name,
        email=email,
        student_number=f"120125{abs(hash(student_id)) % 9000 + 1000}",
        study_program="S1 Teknik Komputer",
        academic_year=2025,
        verification_status=verif,
        account_status=acct,
        is_discoverable=discoverable
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


class TestDay19IntegrityHardening(unittest.TestCase):
    """Test suite Day 19.6.1 & 19.6.2 - Evaluation Integrity Hardening & Evaluator Closure."""

    def setUp(self):
        self.course_a = Course(
            course_id="c_hard_a",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.host_student = make_student("sh_hard", "Host Hard", "hhard@telkomuniversity.ac.id")
        self.host_intent = make_intent("ih_hard", "sh_hard", "c_hard_a")
        self.host_intent.availabilities = [make_availability("ih_hard", "2026-11-25", "09:00", "13:00")]
        self.host_intent.student = self.host_student
        self.host_intent.course = self.course_a

    # =========================================================================
    # 1. Formation & Hard Constraint Integrity
    # =========================================================================

    def test_01_insufficient_members_valid_state_is_not_violation(self):
        """
        Skenario 1: Status INSUFFICIENT_MEMBERS dengan group_size=3 dan min_group_size_bound=4.
        Ekspektasi: Tidak dianggap violation (valid state saat kuorum belum tercapai).
        """
        self.host_intent.max_group_size = 5
        st1 = make_student("s1", "Cand 1", "c1@t.ac.id")
        c1 = make_intent("i1", "s1", "c_hard_a", min_size=4, max_size=5)
        c1.student = st1

        st2 = make_student("s2", "Cand 2", "c2@t.ac.id")
        c2 = make_intent("i2", "s2", "c_hard_a", min_size=2, max_size=5)
        c2.student = st2

        lookup = {"i1": c1, "i2": c2, "ih_hard": self.host_intent}

        res = {
            "formation_status": "INSUFFICIENT_MEMBERS",
            "group_size": 3,
            "min_group_size_bound": 4,
            "max_group_size_bound": 5,
            "members": [
                {"intent_id": "ih_hard"},
                {"intent_id": "i1"},
                {"intent_id": "i2"}
            ]
        }

        violations = check_hard_constraint_violations(self.host_intent, res, lookup)
        self.assertEqual(len(violations), 0)

    def test_02_no_compatible_group_with_size_2_is_violation(self):
        """
        Skenario 2: Status NO_COMPATIBLE_GROUP tetapi group_size=2.
        Ekspektasi: Dianggap violation karena status NO_COMPATIBLE_GROUP harus memiliki group_size == 1.
        """
        res = {
            "formation_status": "NO_COMPATIBLE_GROUP",
            "group_size": 2,
            "members": [
                {"intent_id": "ih_hard"},
                {"intent_id": "i_cand"}
            ]
        }
        violations = check_hard_constraint_violations(self.host_intent, res)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("group_size (2) != 1" in msg for msg in violations))

    def test_03_candidate_with_inactive_intent_status_is_violation(self):
        """
        Skenario 3: Kandidat dalam hasil kelompok berstatus intent selain 'ACTIVE' (misal 'CANCELLED').
        Ekspektasi: Dianggap violation karena hanya intent aktif yang boleh masuk kelompok.
        """
        st1 = make_student("s_inact", "Inactive Cand", "inact@t.ac.id")
        c_inact = make_intent("i_inact", "s_inact", "c_hard_a", status="CANCELLED")
        c_inact.student = st1
        c_inact.availabilities = [make_availability("i_inact", "2026-11-25", "09:00", "12:00")]

        lookup = {"i_inact": c_inact, "ih_hard": self.host_intent}

        res = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [
                {"intent_id": "ih_hard"},
                {"intent_id": "i_inact"}
            ],
            "selected_schedule": {
                "date": "2026-11-25",
                "start_time": "09:00",
                "end_time": "11:00",
                "duration_minutes": 120
            },
            "pairwise_scores": [
                {"intent_a_id": "ih_hard", "intent_b_id": "i_inact", "compatibility_score": 85.0}
            ]
        }

        violations = check_hard_constraint_violations(self.host_intent, res, lookup)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("status intent tidak aktif" in msg for msg in violations))

    def test_04_invalid_capacity_bounds_in_ready_group_is_violation(self):
        """
        Skenario 4: Batas kapasitas kelompok READY tidak valid (min_bound > max_bound atau ukuran out-of-bounds).
        Ekspektasi: Dianggap violation.
        """
        st1 = make_student("s_cap", "Cap Cand", "cap@t.ac.id")
        c1 = make_intent("i_cap", "s_cap", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i_cap", "2026-11-25", "09:00", "12:00")]

        lookup = {"i_cap": c1, "ih_hard": self.host_intent}

        # Kasus A: min_bound (5) > max_bound (4)
        res_a = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 5,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_cap"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_cap", "compatibility_score": 80.0}]
        }
        v_a = check_hard_constraint_violations(self.host_intent, res_a, lookup)
        self.assertTrue(any("rentang kapasitas tidak valid" in msg for msg in v_a))

        # Kasus B: group_size (2) < min_bound (3)
        res_b = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 3,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_cap"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_cap", "compatibility_score": 80.0}]
        }
        v_b = check_hard_constraint_violations(self.host_intent, res_b, lookup)
        self.assertTrue(any("di luar batas kapasitas" in msg for msg in v_b))

    def test_05_pairwise_score_below_min_score_is_violation(self):
        """
        Skenario 5: Satu pasangan pada kelompok READY memiliki Compatibility Score < min_score (misal 55.0 < 60.0).
        Ekspektasi: Dianggap violation.
        """
        st1 = make_student("s_low", "Low Cand", "low@t.ac.id")
        c1 = make_intent("i_low", "s_low", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i_low", "2026-11-25", "09:00", "12:00")]

        lookup = {"i_low": c1, "ih_hard": self.host_intent}

        res = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_low"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [
                {"intent_a_id": "ih_hard", "intent_b_id": "i_low", "compatibility_score": 55.0}
            ]
        }
        violations = check_hard_constraint_violations(self.host_intent, res, lookup, min_score=60.0)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("Compatibility Score (55.0) < min_score" in msg for msg in violations))

    def test_06_pairwise_score_count_mismatch_is_violation(self):
        """
        Skenario 6: Jumlah elemen pairwise_scores tidak sama dengan N*(N-1)/2.
        Untuk group_size=3, seharusnya ada 3*(3-1)/2 = 3 pasang skor. Jika hanya ada 2 pasang, dianggap violation.
        Ekspektasi: Dianggap violation.
        """
        st1 = make_student("s_m1", "M1", "m1@t.ac.id")
        c1 = make_intent("i_m1", "s_m1", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i_m1", "2026-11-25", "09:00", "12:00")]

        st2 = make_student("s_m2", "M2", "m2@t.ac.id")
        c2 = make_intent("i_m2", "s_m2", "c_hard_a")
        c2.student = st2
        c2.availabilities = [make_availability("i_m2", "2026-11-25", "09:00", "12:00")]

        lookup = {"i_m1": c1, "i_m2": c2, "ih_hard": self.host_intent}

        res = {
            "formation_status": "READY",
            "group_size": 3,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_m1"}, {"intent_id": "i_m2"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [
                {"intent_a_id": "ih_hard", "intent_b_id": "i_m1", "compatibility_score": 80.0},
                {"intent_a_id": "ih_hard", "intent_b_id": "i_m2", "compatibility_score": 85.0}
            ]
        }
        violations = check_hard_constraint_violations(self.host_intent, res, lookup, min_score=60.0)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("tidak sesuai dengan formula N*(N-1)/2" in msg for msg in violations))

    def test_07_selected_schedule_not_covering_all_members_is_violation(self):
        """
        Skenario 7: Selected schedule di luar ketersediaan salah satu anggota.
        Host tersedia 09:00-13:00, Kandidat C1 hanya tersedia 14:00-17:00.
        Jika selected_schedule diklaim 09:00-11:00, evaluator independen harus mendeteksi pelanggaran ketersediaan C1.
        Ekspektasi: Dianggap violation.
        """
        st_disjoint = make_student("s_disj", "Disjoint Cand", "disj@t.ac.id")
        c_disjoint = make_intent("i_disj", "s_disj", "c_hard_a")
        c_disjoint.student = st_disjoint
        c_disjoint.availabilities = [make_availability("i_disj", "2026-11-25", "14:00", "17:00")]

        lookup = {"i_disj": c_disjoint, "ih_hard": self.host_intent}

        res = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_disj"}],
            "selected_schedule": {
                "date": "2026-11-25",
                "start_time": "09:00",
                "end_time": "11:00",
                "duration_minutes": 120
            },
            "pairwise_scores": [
                {"intent_a_id": "ih_hard", "intent_b_id": "i_disj", "compatibility_score": 80.0}
            ]
        }

        violations = check_hard_constraint_violations(self.host_intent, res, lookup, min_score=60.0)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("tidak tercakup dalam ketersediaan anggota i_disj" in msg for msg in violations))

    def test_08_comprehensive_report_metrics_semantic_consistency(self):
        """
        Skenario 8: Validasi konsistensi ketiga metrik ringkasan pada ComprehensiveEvaluationSummary:
        - group_quality_score == GQ
        - average_pair_score == APS
        - quality_score_mean == GQ (alias backwards-compatible)
        Ekspektasi: Ketiga nilai tepat sesuai nilai perhitungan quality_evaluation.
        """
        st1 = make_student("s_m8", "M8", "m8@t.ac.id")
        c1 = make_intent("i_m8", "s_m8", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i_m8", "2026-11-25", "09:00", "12:00")]

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=[c1],
            stability_permutations=5,
            min_score=60.0
        )

        sum_obj = report.summary
        qual_obj = report.quality_evaluation

        self.assertEqual(sum_obj.group_quality_score, qual_obj.group_quality_score)
        self.assertEqual(sum_obj.average_pair_score, qual_obj.average_pair_score)
        self.assertEqual(sum_obj.quality_score_mean, qual_obj.group_quality_score)

    # =========================================================================
    # 2. D19.6.1-01: Candidate & Host Integrity
    # =========================================================================

    def test_09_host_integrity_inactive_or_unverified_or_none_student_is_violation(self):
        """
        D19.6.1-01: Validasi independen terhadap integritas Host Intent & Profil Mahasiswa.
        Ekspektasi: Pelanggaran dicatat jika intent inaktif, profil None, akun non-aktif,
        belum terverifikasi, atau is_discoverable=False.
        """
        # A. Host intent status inaktif
        bad_host_intent = make_intent("ih_bad", "sh_hard", "c_hard_a", status="CANCELLED")
        bad_host_intent.student = self.host_student
        res_ok = {
            "formation_status": "NO_COMPATIBLE_GROUP",
            "group_size": 1,
            "members": [{"intent_id": "ih_bad"}]
        }
        v_a = check_hard_constraint_violations(bad_host_intent, res_ok)
        self.assertTrue(any("status intent tidak aktif" in msg for msg in v_a))

        # B. Host student profile None
        no_st_host = make_intent("ih_nost", "sh_hard", "c_hard_a")
        no_st_host.student = None
        v_b = check_hard_constraint_violations(no_st_host, res_ok)
        self.assertTrue(any("Data profil mahasiswa untuk host" in msg for msg in v_b))

        # C. Host student account suspended / unverified / hidden
        st_unverif = make_student("sh_unv", "Unv", "unv@t.ac.id", acct="SUSPENDED", verif="UNVERIFIED", discoverable=False)
        host_unverif = make_intent("ih_unv", "sh_unv", "c_hard_a")
        host_unverif.student = st_unverif
        v_c = check_hard_constraint_violations(host_unverif, res_ok)
        self.assertTrue(any("akun mahasiswa tidak aktif" in msg for msg in v_c))
        self.assertTrue(any("belum terverifikasi" in msg for msg in v_c))
        self.assertTrue(any("is_discoverable=False" in msg for msg in v_c))

        # D. Host student is_discoverable=None (D19.6.2-R1 strict discoverability)
        st_none_disc = make_student("sh_ndisc", "NDisc", "ndisc@t.ac.id", discoverable=True)
        st_none_disc.is_discoverable = None
        host_none_disc = make_intent("ih_ndisc", "sh_ndisc", "c_hard_a")
        host_none_disc.student = st_none_disc
        v_d = check_hard_constraint_violations(host_none_disc, res_ok)
        self.assertTrue(any("tidak discoverable" in msg for msg in v_d))

    def test_10_non_host_members_without_candidate_lookup_is_violation(self):
        """
        D19.6.1-01: Jika kelompok memiliki anggota non-host tetapi candidate_lookup = None,
        evaluator independen WAJIB menandai violation.
        """
        res_ready = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_cand_1"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_cand_1", "compatibility_score": 80.0}]
        }

        # Jalankan tanpa candidate_lookup (None)
        v = check_hard_constraint_violations(self.host_intent, res_ready, candidate_lookup=None)
        self.assertTrue(any("candidate_lookup wajib disediakan" in msg for msg in v))

    def test_11_candidate_profile_missing_or_unverified_or_course_mismatch_is_violation(self):
        """
        D19.6.1-01: Validasi terhadap anggota non-host: profil None, akun suspend, course beda,
        duplikasi student, atau konflik mode ONLINE vs OFFLINE.
        """
        # A. Candidate profile None
        c_no_prof = make_intent("i_noprof", "s_noprof", "c_hard_a")
        c_no_prof.student = None
        c_no_prof.availabilities = [make_availability("i_noprof")]

        # B. Candidate course mismatch
        c_diff_course = make_intent("i_diff", "s_diff", "c_other_course")
        c_diff_course.student = make_student("s_diff", "Diff", "diff@t.ac.id")
        c_diff_course.availabilities = [make_availability("i_diff")]

        # C. Mode konflik ONLINE vs OFFLINE (Host OFFLINE)
        c_online = make_intent("i_onl", "s_onl", "c_hard_a", learning_mode="ONLINE")
        c_online.student = make_student("s_onl", "Onl", "onl@t.ac.id")
        c_online.availabilities = [make_availability("i_onl")]

        # D. Duplikasi student_id (Student ID sama dengan Host)
        c_dup_st = make_intent("i_dup", "sh_hard", "c_hard_a")
        c_dup_st.student = self.host_student
        c_dup_st.availabilities = [make_availability("i_dup")]

        lookup = {
            "i_noprof": c_no_prof,
            "i_diff": c_diff_course,
            "i_onl": c_online,
            "i_dup": c_dup_st,
            "ih_hard": self.host_intent
        }

        # Test A
        res_a = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_noprof"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_noprof", "compatibility_score": 80.0}]
        }
        v_a = check_hard_constraint_violations(self.host_intent, res_a, lookup)
        self.assertTrue(any("Data profil mahasiswa untuk intent i_noprof tidak tersedia" in msg for msg in v_a))

        # Test B
        res_b = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_diff"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_diff", "compatibility_score": 80.0}]
        }
        v_b = check_hard_constraint_violations(self.host_intent, res_b, lookup)
        self.assertTrue(any("course_id berbeda" in msg for msg in v_b))

        # Test C
        res_c = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_onl"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_onl", "compatibility_score": 80.0}]
        }
        v_c = check_hard_constraint_violations(self.host_intent, res_c, lookup)
        self.assertTrue(any("ONLINE dan OFFLINE sekaligus" in msg for msg in v_c))

        # Test D
        res_d = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_dup"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_dup", "compatibility_score": 80.0}]
        }
        v_d = check_hard_constraint_violations(self.host_intent, res_d, lookup)
        self.assertTrue(any("duplikasi mahasiswa" in msg for msg in v_d))

        # E. Candidate student is_discoverable=None (D19.6.2-R1 strict discoverability)
        c_none_disc = make_intent("i_ndisc", "s_ndisc", "c_hard_a")
        c_none_disc.student = make_student("s_ndisc", "NDisc", "ndisc@t.ac.id")
        c_none_disc.student.is_discoverable = None
        c_none_disc.availabilities = [make_availability("i_ndisc")]

        # F. Candidate lookup mis-mapped identity (D19.6.2-R2 lookup object identity)
        c_mismap = make_intent("i_real_id", "s_real", "c_hard_a")
        c_mismap.student = make_student("s_real", "Real", "real@t.ac.id")
        c_mismap.availabilities = [make_availability("i_real_id")]

        lookup["i_ndisc"] = c_none_disc
        lookup["i_mapped"] = c_mismap

        # Test E
        res_e = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_ndisc"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_ndisc", "compatibility_score": 80.0}]
        }
        v_e = check_hard_constraint_violations(self.host_intent, res_e, lookup)
        self.assertTrue(any("tidak discoverable" in msg for msg in v_e))

        # Test F
        res_f = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i_mapped"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i_mapped", "compatibility_score": 80.0}]
        }
        v_f = check_hard_constraint_violations(self.host_intent, res_f, lookup)
        self.assertTrue(any("memetakan ke objek dengan intent_id berbeda" in msg for msg in v_f))

    # =========================================================================
    # 3. D19.6.1-02: Pairwise Identity & Completeness
    # =========================================================================

    def test_12_pairwise_identity_duplicate_missing_extraneous_pairs_is_violation(self):
        """
        D19.6.1-02: Verifikasi pasangan unordered pair:
        - Pasangan duplikat terdeteksi meskipun total jumlah elemen sama.
        - Pasangan yang hilang terdeteksi.
        - Pasangan asing (foreign intent) terdeteksi.
        """
        st1 = make_student("s12_1", "S12 1", "s121@t.ac.id")
        c1 = make_intent("i12_1", "s12_1", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i12_1")]

        st2 = make_student("s12_2", "S12 2", "s122@t.ac.id")
        c2 = make_intent("i12_2", "s12_2", "c_hard_a")
        c2.student = st2
        c2.availabilities = [make_availability("i12_2")]

        lookup = {"i12_1": c1, "i12_2": c2, "ih_hard": self.host_intent}

        # Kelompok n=3 (ih_hard, i12_1, i12_2).
        # Pasangan yang diharapkan: (ih_hard, i12_1), (ih_hard, i12_2), (i12_1, i12_2).
        # Kasus A: 3 elemen pairwise, tetapi ada duplikat (ih_hard, i12_1) dua kali dan (i12_1, i12_2) hilang!
        res_dup = {
            "formation_status": "READY", "group_size": 3, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i12_1"}, {"intent_id": "i12_2"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [
                {"intent_a_id": "ih_hard", "intent_b_id": "i12_1", "compatibility_score": 80.0},
                {"intent_a_id": "i12_1", "intent_b_id": "ih_hard", "compatibility_score": 80.0},  # Duplikat (reversed)
                {"intent_a_id": "ih_hard", "intent_b_id": "i12_2", "compatibility_score": 85.0}
            ]
        }
        v_dup = check_hard_constraint_violations(self.host_intent, res_dup, lookup)
        self.assertTrue(any("pasangan duplikat" in msg for msg in v_dup))
        self.assertTrue(any("pasangan yang hilang" in msg for msg in v_dup))

        # Kasus B: Pasangan asing (memuat intent_id i_stranger yang bukan anggota)
        res_ext = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i12_1"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [
                {"intent_a_id": "ih_hard", "intent_b_id": "i_stranger", "compatibility_score": 80.0}
            ]
        }
        lookup["i_stranger"] = c2
        v_ext = check_hard_constraint_violations(self.host_intent, res_ext, lookup)
        self.assertTrue(any("pasangan asing" in msg for msg in v_ext))

    def test_13_pairwise_compatibility_score_non_numeric_nan_inf_bool_is_violation(self):
        """
        D19.6.1-02: Nilai compatibility_score wajib numerik, finite, dan non-boolean.
        Ekspektasi: Boolean (True/False), NaN, Inf, atau string bernilai invalid dicatat sebagai pelanggaran.
        """
        st1 = make_student("s13", "S13", "s13@t.ac.id")
        c1 = make_intent("i13", "s13", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i13")]
        lookup = {"i13": c1, "ih_hard": self.host_intent}

        test_scores = [
            True,               # boolean
            "85.0",             # string
            None,               # None
            float("nan"),       # NaN
            float("inf"),       # Inf
        ]

        for bad_score in test_scores:
            res = {
                "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
                "members": [{"intent_id": "ih_hard"}, {"intent_id": "i13"}],
                "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
                "pairwise_scores": [
                    {"intent_a_id": "ih_hard", "intent_b_id": "i13", "compatibility_score": bad_score}
                ]
            }
            v = check_hard_constraint_violations(self.host_intent, res, lookup)
            self.assertTrue(
                any(("tidak bernilai numerik valid" in msg or "bernilai NaN atau Inf" in msg) for msg in v),
                f"Gagal mendeteksi bad score: {bad_score}"
            )

    # =========================================================================
    # 4. D19.6.1-03: Schedule Integrity Fail-Open Closure
    # =========================================================================

    def test_14_schedule_fail_open_closure_malformed_duration_and_date_is_violation_not_crash(self):
        """
        D19.6.1-03: Penanganan aman malformed duration_minutes dan invalid date format.
        Tidak boleh crash / raise Unhandled Exception, melainkan mencatat violation secara elegan.
        """
        st1 = make_student("s14", "S14", "s14@t.ac.id")
        c1 = make_intent("i14", "s14", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i14")]
        lookup = {"i14": c1, "ih_hard": self.host_intent}

        # A. duration_minutes bertipe string "abc" atau boolean True
        res_malformed_dur = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i14"}],
            "selected_schedule": {
                "date": "2026-11-25",
                "start_time": "09:00",
                "end_time": "11:00",
                "duration_minutes": "abc"  # Malformed string
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i14", "compatibility_score": 80.0}]
        }
        v_dur = check_hard_constraint_violations(self.host_intent, res_malformed_dur, lookup)
        self.assertTrue(any("duration_minutes (abc) harus numerik valid" in msg for msg in v_dur))

        # B. Format tanggal bukan YYYY-MM-DD
        res_bad_date = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i14"}],
            "selected_schedule": {
                "date": "25/11/2026",  # Format salah
                "start_time": "09:00",
                "end_time": "11:00",
                "duration_minutes": 120
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i14", "compatibility_score": 80.0}]
        }
        v_date = check_hard_constraint_violations(self.host_intent, res_bad_date, lookup)
        self.assertTrue(any("Format tanggal selected_schedule '25/11/2026' tidak valid" in msg for msg in v_date))

        # C. Tanggal hilang / kosong (missing date)
        res_missing_date = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i14"}],
            "selected_schedule": {
                "date": "",  # Kosong
                "start_time": "09:00",
                "end_time": "11:00",
                "duration_minutes": 120
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i14", "compatibility_score": 80.0}]
        }
        v_mis_date = check_hard_constraint_violations(self.host_intent, res_missing_date, lookup)
        self.assertTrue(any("Field jadwal 'date' pada selected_schedule tidak boleh kosong" in msg for msg in v_mis_date))

        # D. Waktu malformed (malformed time string '25:00' atau 'abc')
        res_bad_time = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i14"}],
            "selected_schedule": {
                "date": "2026-11-25",
                "start_time": "25:00",  # Jam invalid
                "end_time": "11:00",
                "duration_minutes": 120
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i14", "compatibility_score": 80.0}]
        }
        v_bad_time = check_hard_constraint_violations(self.host_intent, res_bad_time, lookup)
        self.assertTrue(any("Format waktu selected_schedule tidak valid" in msg for msg in v_bad_time))

        # E. Tanggal kalender fiktif / tidak ada (D19.6.2-R3 calendar date check)
        res_fake_date = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i14"}],
            "selected_schedule": {
                "date": "2026-99-99",  # Kalender fiktif
                "start_time": "09:00",
                "end_time": "11:00",
                "duration_minutes": 120
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i14", "compatibility_score": 80.0}]
        }
        v_fake_date = check_hard_constraint_violations(self.host_intent, res_fake_date, lookup)
        self.assertTrue(any("bukan tanggal kalender yang valid" in msg for msg in v_fake_date))

        # F. duration_minutes bertipe desimal pecahan (D19.6.2-R4 non-integer duration)
        res_decimal_dur = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i14"}],
            "selected_schedule": {
                "date": "2026-11-25",
                "start_time": "09:00",
                "end_time": "11:00",
                "duration_minutes": 60.9  # Desimal pecahan, tidak boleh di-truncate ke 60
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i14", "compatibility_score": 80.0}]
        }
        v_dec_dur = check_hard_constraint_violations(self.host_intent, res_decimal_dur, lookup)
        self.assertTrue(any("bukan desimal pecahan" in msg for msg in v_dec_dur))

    def test_15_schedule_end_before_start_and_duration_mismatch_is_violation(self):
        """
        D19.6.1-03: Waktu selesai harus lebih besar dari waktu mulai, durasi minimal 60 menit,
        dan durasi yang dilaporkan harus konsisten dengan selisih waktu.
        """
        st1 = make_student("s15", "S15", "s15@t.ac.id")
        c1 = make_intent("i15", "s15", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i15")]
        lookup = {"i15": c1, "ih_hard": self.host_intent}

        # A. end_time <= start_time
        res_end_before_start = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i15"}],
            "selected_schedule": {
                "date": "2026-11-25",
                "start_time": "11:00",
                "end_time": "09:00",
                "duration_minutes": 120
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i15", "compatibility_score": 80.0}]
        }
        v_a = check_hard_constraint_violations(self.host_intent, res_end_before_start, lookup)
        self.assertTrue(any("harus lebih besar dari waktu mulai" in msg for msg in v_a))

        # B. Durasi kurang dari 60 menit
        res_short = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i15"}],
            "selected_schedule": {
                "date": "2026-11-25",
                "start_time": "09:00",
                "end_time": "09:45",
                "duration_minutes": 45
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i15", "compatibility_score": 80.0}]
        }
        v_b = check_hard_constraint_violations(self.host_intent, res_short, lookup)
        self.assertTrue(any("kurang dari 60 menit" in msg for msg in v_b))

        # C. Durasi reported (180m) != selisih waktu (120m)
        res_mismatch = {
            "formation_status": "READY", "group_size": 2, "min_group_size_bound": 2, "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i15"}],
            "selected_schedule": {
                "date": "2026-11-25",
                "start_time": "09:00",
                "end_time": "11:00",
                "duration_minutes": 180  # Harusnya 120
            },
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i15", "compatibility_score": 80.0}]
        }
        v_c = check_hard_constraint_violations(self.host_intent, res_mismatch, lookup)
        self.assertTrue(any("tidak sesuai selisih waktu" in msg for msg in v_c))

    # =========================================================================
    # 5. D19.6.1-04 & D19.6.1-05: Direct Production Testing & Top-K Sentinel
    # =========================================================================

    def test_16_direct_comprehensive_report_topk_89_99_percent_yields_warning(self):
        """
        D19.6.1-04 & D19.6.1-05: Pengujian langsung fungsi produksi generate_comprehensive_evaluation_report
        pada nilai Top-K retention ambang batas ketat 89.99%.
        Ekspektasi: summary.topk_quality_retention == 89.99, overall_status == "WARNING",
        dan rekomendasi memuat 'Top-K retention 89.99% < 90.0%'.
        """
        candidates = []
        for i in range(1, 4):
            st = make_student(f"s16_{i}", f"Cand 16_{i}", f"c16_{i}@t.ac.id")
            ci = make_intent(f"i16_{i}", f"s16_{i}", "c_hard_a")
            ci.student = st
            ci.availabilities = [make_availability(f"i16_{i}", "2026-11-25", "09:00", "12:00")]
            candidates.append(ci)

        mock_topk_result = TopKBenchmarkResult(
            total_candidates=len(candidates),
            baseline_k="Full",
            benchmarks=[
                TopKPoolBenchmarkItem(
                    k_value=20,
                    candidates_in_pool=20,
                    candidates_examined=len(candidates),
                    formation_status="READY",
                    group_size=2,
                    group_quality_score=71.99,
                    average_pair_score=71.99,
                    minimum_pair_score=71.99,
                    quality_loss=10.01,
                    quality_retention=89.99,
                    execution_time_ms=1.5,
                    is_identical_to_baseline=False
                )
            ]
        )

        with patch("app.matching_evaluation.benchmark_top_k_candidate_pool", return_value=mock_topk_result):
            report = generate_comprehensive_evaluation_report(
                host_intent=self.host_intent,
                candidate_intents=candidates,
                stability_permutations=2,
                min_score=60.0
            )

        self.assertIsInstance(report, ComprehensiveEvaluationReport)
        self.assertEqual(report.summary.topk_quality_retention, 89.99)
        self.assertEqual(report.summary.overall_status, "WARNING")
        self.assertIn("Top-K retention 89.99% < 90.0%", report.summary.recommendation)

    def test_17_direct_comprehensive_report_topk_90_00_and_95_00_percent_passes(self):
        """
        D19.6.1-04 & D19.6.1-05: Pengujian langsung fungsi produksi generate_comprehensive_evaluation_report
        pada nilai Top-K retention 90.00% (ambang tepat) dan 95.00%.
        Ekspektasi: overall_status == "PASSED".
        """
        candidates = []
        for i in range(1, 4):
            st = make_student(f"s17_{i}", f"Cand 17_{i}", f"c17_{i}@t.ac.id")
            ci = make_intent(f"i17_{i}", f"s17_{i}", "c_hard_a")
            ci.student = st
            ci.availabilities = [make_availability(f"i17_{i}", "2026-11-25", "09:00", "12:00")]
            candidates.append(ci)

        for ret_val in (90.00, 95.00):
            mock_item = TopKBenchmarkResult(
                total_candidates=len(candidates),
                baseline_k="Full",
                benchmarks=[
                    TopKPoolBenchmarkItem(
                        k_value=20,
                        candidates_in_pool=20,
                        candidates_examined=len(candidates),
                        formation_status="READY",
                        group_size=2,
                        group_quality_score=80.0,
                        average_pair_score=80.0,
                        minimum_pair_score=80.0,
                        quality_loss=100.0 - ret_val,
                        quality_retention=ret_val,
                        execution_time_ms=1.5,
                        is_identical_to_baseline=True
                    )
                ]
            )

            with patch("app.matching_evaluation.benchmark_top_k_candidate_pool", return_value=mock_item):
                report = generate_comprehensive_evaluation_report(
                    host_intent=self.host_intent,
                    candidate_intents=candidates,
                    stability_permutations=2,
                    min_score=60.0
                )

            self.assertEqual(report.summary.topk_quality_retention, ret_val)
            self.assertEqual(report.summary.overall_status, "PASSED")
            self.assertIn("LOLOS pengujian komprehensif Day 19", report.summary.recommendation)

    def test_18_direct_comprehensive_report_unbenchmarked_topk_none_yields_warning_sentinel(self):
        """
        D19.6.1-04: Jika benchmark Top-K numerik tidak dijalankan (k_values=(None,)),
        topk_quality_retention bernilai None dan overall_status menjadi WARNING
        dengan alasan 'Benchmark Top-K numerik tidak dijalankan'.
        """
        candidates = []
        for i in range(1, 4):
            st = make_student(f"s18_{i}", f"Cand 18_{i}", f"c18_{i}@t.ac.id")
            ci = make_intent(f"i18_{i}", f"s18_{i}", "c_hard_a")
            ci.student = st
            ci.availabilities = [make_availability(f"i18_{i}", "2026-11-25", "09:00", "12:00")]
            candidates.append(ci)

        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            k_values=(None,),
            stability_permutations=2,
            min_score=60.0
        )

        self.assertIsNone(report.summary.topk_quality_retention)
        self.assertEqual(report.summary.overall_status, "WARNING")
        self.assertIn("Benchmark Top-K numerik tidak dijalankan", report.summary.recommendation)

    # =========================================================================
    # Day 19.6.4: Final Independent Evaluator Trust & Report Integrity Tests
    # =========================================================================

    def test_19_host_missing_from_members_is_violation(self):
        """D19.6.4-01: Host tidak terdapat dalam daftar members memicu violation."""
        st1 = make_student("s19_1", "Cand 19_1", "c19_1@t.ac.id")
        c1 = make_intent("i19_1", "s19_1", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i19_1", "2026-11-25", "09:00", "12:00")]

        st2 = make_student("s19_2", "Cand 19_2", "c19_2@t.ac.id")
        c2 = make_intent("i19_2", "s19_2", "c_hard_a")
        c2.student = st2
        c2.availabilities = [make_availability("i19_2", "2026-11-25", "09:00", "12:00")]

        lookup = {"i19_1": c1, "i19_2": c2, "ih_hard": self.host_intent}
        res = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "i19_1"}, {"intent_id": "i19_2"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "i19_1", "intent_b_id": "i19_2", "compatibility_score": 80.0}]
        }
        violations = check_hard_constraint_violations(self.host_intent, res, lookup)
        self.assertTrue(any("tidak terdapat dalam daftar members" in v for v in violations))

    def test_20_host_duplicated_in_members_is_violation(self):
        """D19.6.4-01: Host muncul dua kali dalam daftar members memicu violation."""
        lookup = {"ih_hard": self.host_intent}
        res = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "ih_hard"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "ih_hard", "compatibility_score": 80.0}]
        }
        violations = check_hard_constraint_violations(self.host_intent, res, lookup)
        self.assertTrue(any("muncul lebih dari satu kali" in v for v in violations))
        self.assertTrue(any("duplikasi anggota" in v for v in violations))

    def test_21_formation_result_host_intent_id_mismatch_is_violation(self):
        """D19.6.4-01: formation_result.host_intent_id berbeda dari host_intent memicu violation."""
        st1 = make_student("s21_1", "Cand 21_1", "c21_1@t.ac.id")
        c1 = make_intent("i21_1", "s21_1", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i21_1", "2026-11-25", "09:00", "12:00")]

        lookup = {"i21_1": c1, "ih_hard": self.host_intent}
        res = {
            "host_intent_id": "some_other_host",
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i21_1"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i21_1", "compatibility_score": 80.0}]
        }
        violations = check_hard_constraint_violations(self.host_intent, res, lookup)
        self.assertTrue(any("host_intent_id pada formation_result" in v and "tidak cocok" in v for v in violations))

    def test_22_reported_capacity_differs_from_recomputed_is_violation(self):
        """D19.6.4-02: Batas kapasitas yang dilaporkan berbeda dari perhitungan ulang objek intent."""
        # Host: min 2, max 4. Cand: min 2, max 4. Recomputed: [2, 4].
        st1 = make_student("s22_1", "Cand 22_1", "c22_1@t.ac.id")
        c1 = make_intent("i22_1", "s22_1", "c_hard_a", min_size=2, max_size=4)
        c1.student = st1
        c1.availabilities = [make_availability("i22_1", "2026-11-25", "09:00", "12:00")]

        lookup = {"i22_1": c1, "ih_hard": self.host_intent}
        # Metadata dimanipulasi: min_bound=3 (seharusnya 2)
        res = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 3,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i22_1"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i22_1", "compatibility_score": 80.0}]
        }
        violations = check_hard_constraint_violations(self.host_intent, res, lookup)
        self.assertTrue(any("Metadata min_group_size_bound" in v and "tidak cocok" in v for v in violations))

    def test_23_strict_integer_group_size_validation(self):
        """D19.6.4-03: group_size bertipe float (2.9), string ('2'), atau bool (True) ditolak."""
        lookup = {"ih_hard": self.host_intent}

        for bad_size in (2.9, "2", True):
            res = {
                "formation_status": "READY",
                "group_size": bad_size,
                "min_group_size_bound": 2,
                "max_group_size_bound": 4,
                "members": [{"intent_id": "ih_hard"}],
                "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
                "pairwise_scores": []
            }
            v = check_hard_constraint_violations(self.host_intent, res, lookup)
            self.assertTrue(any("harus berupa integer numerik murni" in msg for msg in v), f"Gagal menolak group_size={bad_size}")

    def test_24_unknown_learning_modes_are_violations(self):
        """D19.6.4-04: Mode belajar non-domain (REMOTE, UNKNOWN, None) ditolak."""
        st1 = make_student("s24_1", "Cand 24_1", "c24_1@t.ac.id")

        for bad_mode in ("REMOTE", "UNKNOWN", None):
            c1 = make_intent("i24_1", "s24_1", "c_hard_a", learning_mode=bad_mode)
            c1.student = st1
            c1.availabilities = [make_availability("i24_1", "2026-11-25", "09:00", "12:00")]
            lookup = {"i24_1": c1, "ih_hard": self.host_intent}

            res = {
                "formation_status": "READY",
                "group_size": 2,
                "min_group_size_bound": 2,
                "max_group_size_bound": 4,
                "members": [{"intent_id": "ih_hard"}, {"intent_id": "i24_1"}],
                "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
                "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i24_1", "compatibility_score": 80.0}]
            }
            violations = check_hard_constraint_violations(self.host_intent, res, lookup)
            self.assertTrue(any("learning_mode tidak valid" in msg for msg in violations), f"Gagal menolak mode={bad_mode}")

    def test_25_pairwise_score_out_of_bounds_0_to_100_or_non_finite(self):
        """D19.6.4-05: Compatibility Score < 0, > 100, NaN, atau Inf ditolak."""
        st1 = make_student("s25_1", "Cand 25_1", "c25_1@t.ac.id")
        c1 = make_intent("i25_1", "s25_1", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i25_1", "2026-11-25", "09:00", "12:00")]
        lookup = {"i25_1": c1, "ih_hard": self.host_intent}

        for bad_score in (-1.0, 100.01, 150.0, float("nan"), float("inf")):
            res = {
                "formation_status": "READY",
                "group_size": 2,
                "min_group_size_bound": 2,
                "max_group_size_bound": 4,
                "members": [{"intent_id": "ih_hard"}, {"intent_id": "i25_1"}],
                "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
                "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i25_1", "compatibility_score": bad_score}]
            }
            v = check_hard_constraint_violations(self.host_intent, res, lookup)
            self.assertTrue(any("di luar rentang valid [0.0, 100.0]" in msg or "bernilai NaN atau Inf" in msg for msg in v), f"Gagal menolak score={bad_score}")

    def test_26_min_score_parameter_strict_validation(self):
        """D19.6.4-06: min_score NaN, Inf, boolean, atau di luar rentang ditolak."""
        st1 = make_student("s26_1", "Cand 26_1", "c26_1@t.ac.id")
        c1 = make_intent("i26_1", "s26_1", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i26_1", "2026-11-25", "09:00", "12:00")]
        lookup = {"i26_1": c1, "ih_hard": self.host_intent}

        res = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i26_1"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i26_1", "compatibility_score": 80.0}]
        }

        for bad_min in (float("nan"), float("inf"), True, -5.0, 105.0):
            v = check_hard_constraint_violations(self.host_intent, res, lookup, min_score=bad_min)
            self.assertTrue(any("Parameter min_score" in msg and "tidak valid" in msg for msg in v), f"Gagal menolak min_score={bad_min}")

    def test_27_availability_contains_none_or_malformed_fail_closed(self):
        """D19.6.4-06 (Resolver): Availability berisi None atau malformed menghasilkan violation tanpa crash."""
        st1 = make_student("s27_1", "Cand 27_1", "c27_1@t.ac.id")
        c1 = make_intent("i27_1", "s27_1", "c_hard_a")
        c1.student = st1
        # Set availabilities memuat None
        c1.availabilities = [None]
        lookup = {"i27_1": c1, "ih_hard": self.host_intent}

        res = {
            "formation_status": "READY",
            "group_size": 2,
            "min_group_size_bound": 2,
            "max_group_size_bound": 4,
            "members": [{"intent_id": "ih_hard"}, {"intent_id": "i27_1"}],
            "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
            "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i27_1", "compatibility_score": 80.0}]
        }
        # Wajib tidak raise exception dan mencatat violation ketersediaan
        violations = check_hard_constraint_violations(self.host_intent, res, lookup)
        self.assertTrue(any("Ketersediaan anggota" in msg and ("tidak valid" in msg or "resolver" in msg or "tidak tercakup" in msg) for msg in violations))

    def test_28_duration_minutes_decimal_infinity_and_nan_fail_closed(self):
        """D19.6.4-07: duration_minutes Decimal('Infinity'), Decimal('-Infinity'), Decimal('NaN') ditolak tanpa crash."""
        st1 = make_student("s28_1", "Cand 28_1", "c28_1@t.ac.id")
        c1 = make_intent("i28_1", "s28_1", "c_hard_a")
        c1.student = st1
        c1.availabilities = [make_availability("i28_1", "2026-11-25", "09:00", "12:00")]
        lookup = {"i28_1": c1, "ih_hard": self.host_intent}

        for dec_val in (Decimal("Infinity"), Decimal("-Infinity"), Decimal("NaN"), Decimal("sNaN")):
            res = {
                "formation_status": "READY",
                "group_size": 2,
                "min_group_size_bound": 2,
                "max_group_size_bound": 4,
                "members": [{"intent_id": "ih_hard"}, {"intent_id": "i28_1"}],
                "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": dec_val},
                "pairwise_scores": [{"intent_a_id": "ih_hard", "intent_b_id": "i28_1", "compatibility_score": 80.0}]
            }
            v = check_hard_constraint_violations(self.host_intent, res, lookup)
            self.assertTrue(any("non-finite / NaN / Inf" in msg or "Decimal tidak valid" in msg for msg in v), f"Gagal menolak {dec_val}")

    def test_29_missing_breakdown_in_pairwise_yields_breakdown_inconsistent(self):
        """D19.6.4-10: Item pairwise tanpa key breakdown menghasilkan is_breakdown_consistent=False."""
        payload = {
            "group_quality_score": 80.0,
            "average_pair_score": 80.0,
            "minimum_pair_score": 80.0,
            "group_size": 2,
            "pairwise_scores": [
                {
                    "student_a_id": "sh_hard",
                    "student_b_id": "s29_1",
                    "intent_a_id": "ih_hard",
                    "intent_b_id": "i29_1",
                    "compatibility_score": 80.0
                    # breakdown sengaja dihilangkan
                }
            ]
        }
        res = evaluate_group_quality(payload)
        self.assertFalse(res.is_breakdown_consistent)

    def test_30_formula_gq_inconsistency_yields_warning_report(self):
        """D19.6.4-09: Jika formula GQ tidak konsisten terhadap APS/MPS, report berstatus WARNING."""
        candidates = []
        for i in range(1, 4):
            st = make_student(f"s30_{i}", f"Cand 30_{i}", f"c30_{i}@t.ac.id")
            ci = make_intent(f"i30_{i}", f"s30_{i}", "c_hard_a")
            ci.student = st
            ci.availabilities = [make_availability(f"i30_{i}", "2026-11-25", "09:00", "12:00")]
            candidates.append(ci)

        # Mock evaluate_group_quality agar formula consistency tidak valid
        real_quality_eval = evaluate_group_quality
        def mock_quality(data):
            res = real_quality_eval(data)
            # Pasang formula_consistency is_valid = False
            object.__setattr__(res.formula_consistency, "is_valid", False)
            object.__setattr__(res.formula_consistency, "discrepancy", 10.0)
            return res

        with patch("app.matching_evaluation.evaluate_group_quality", side_effect=mock_quality):
            report = generate_comprehensive_evaluation_report(
                host_intent=self.host_intent,
                candidate_intents=candidates,
                stability_permutations=2,
                min_score=60.0
            )

        self.assertEqual(report.summary.overall_status, "WARNING")
        self.assertIn("Inkonsistensi formula GQ", report.summary.recommendation)

    def test_31_baseline_formation_violations_yield_failed_report(self):
        """D19.6.4-08: Jika baseline formation melanggar hard constraint, report berstatus FAILED."""
        candidates = []
        for i in range(1, 4):
            st = make_student(f"s31_{i}", f"Cand 31_{i}", f"c31_{i}@t.ac.id")
            ci = make_intent(f"i31_{i}", f"s31_{i}", "c_hard_a")
            ci.student = st
            ci.availabilities = [make_availability(f"i31_{i}", "2026-11-25", "09:00", "12:00")]
            candidates.append(ci)

        # Mock form_study_group agar menghasilkan output baseline yang rusak (misal host hilang dari members)
        def mock_form(*args, **kwargs):
            return {
                "formation_status": "READY",
                "group_size": 2,
                "min_group_size_bound": 2,
                "max_group_size_bound": 4,
                "group_quality_score": 80.0,
                "average_pair_score": 80.0,
                "minimum_pair_score": 80.0,
                "members": [{"intent_id": "i31_1"}, {"intent_id": "i31_2"}],  # Host hilang!
                "selected_schedule": {"date": "2026-11-25", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120},
                "pairwise_scores": [{"intent_a_id": "i31_1", "intent_b_id": "i31_2", "compatibility_score": 80.0}]
            }

        with patch("app.matching_evaluation.form_study_group", side_effect=mock_form):
            report = generate_comprehensive_evaluation_report(
                host_intent=self.host_intent,
                candidate_intents=candidates,
                stability_permutations=2,
                min_score=60.0
            )

        self.assertEqual(report.summary.overall_status, "FAILED")
        self.assertIn("pelanggaran hard constraints pada baseline formation", report.summary.recommendation)

    def test_32_empty_robustness_scenarios_yields_warning_report(self):
        """D19.6.4-11: Jika skenario robustness kosong ([]), all_constraints_preserved=False dan report WARNING."""
        candidates = []
        for i in range(1, 4):
            st = make_student(f"s32_{i}", f"Cand 32_{i}", f"c32_{i}@t.ac.id")
            ci = make_intent(f"i32_{i}", f"s32_{i}", "c_hard_a")
            ci.student = st
            ci.availabilities = [make_availability(f"i32_{i}", "2026-11-25", "09:00", "12:00")]
            candidates.append(ci)

        # Panggil evaluate_matching_robustness langsung dengan scenarios=[]
        rob_res = evaluate_matching_robustness(self.host_intent, [])
        self.assertFalse(rob_res.all_constraints_preserved)
        self.assertEqual(rob_res.total_scenarios_tested, 0)

        # Panggil report dengan candidate_scenarios=[]
        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=candidates,
            candidate_scenarios=[],
            stability_permutations=2,
            min_score=60.0
        )
        self.assertEqual(report.summary.overall_status, "WARNING")
        self.assertIn("Tidak ada skenario robustness yang diuji", report.summary.recommendation)

    def test_33_no_group_formed_in_baseline_yields_none_topk_retention_and_passed(self):
        """D19.6.4-12: Full pool dengan candidate_intents=[] menghasilkan status baseline NO_COMPATIBLE_GROUP, topk_quality_retention=None, dan overall_status=PASSED."""
        report = generate_comprehensive_evaluation_report(
            host_intent=self.host_intent,
            candidate_intents=[],
            stability_permutations=2,
            min_score=60.0
        )
        self.assertIsNone(report.summary.topk_quality_retention)
        self.assertEqual(report.summary.overall_status, "PASSED")
        self.assertIn("kondisi tanpa kelompok", report.summary.recommendation)


if __name__ == "__main__":
    unittest.main()
