# ==============================================================================
# test_day19_robustness.py - Test Suite Robustness & Edge Cases (Day 19.3)
# ==============================================================================
# Rangkaian pengujian untuk memvalidasi ketahanan Matching Engine saat menerima
# data tidak ideal, sparse, atau adversarial:
# 1. 19.3.1: Empty Candidate Pool (kandidat kosong -> NO_COMPATIBLE_GROUP)
# 2. 19.3.2: Zero Schedule Overlap (tidak ada irisan jadwal -> NO_COMPATIBLE_GROUP)
# 3. 19.3.3: Course Mismatch (mata kuliah berbeda -> kandidat ditolak)
# 4. 19.3.4: Insufficient Members (< MinGroup -> INSUFFICIENT_MEMBERS)
# 5. 19.3.5: Restricted / Unverified / Non-Discoverable Accounts (kandidat ditolak)
# 6. 19.3.6: Incompatible Learning Mode (ONLINE + OFFLINE -> ditolak)
# 7. 19.3.7: Capacity Bounds Disjoint ([2, 3] vs [4, 5] -> ditolak)
# 8. 19.3.8: Sub-60-Minute Schedule Boundary (irisan 59 menit -> ditolak)
# 9. 19.3.9: Candidate Score Below Min Score (CS < 60.0 -> ditolak)
# 10. 19.3.10: Multi-Violation Adversarial Pool (kombinasi seluruh pelanggaran -> CVR = 0%)
# 11. 19.3.11: Evaluator check_hard_constraint_violations() mendeteksi manipulasi
# 12. 19.3.12: Validasi formula matematis CVR = 0.0% dan all_constraints_preserved = True
# ==============================================================================

import unittest
from pathlib import Path
import sys

# Pastikan folder backend masuk ke sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models import Student, Course, StudyIntent, IntentAvailability
from app.group_formation import form_study_group
from app.matching_evaluation import (
    check_hard_constraint_violations,
    evaluate_matching_robustness,
)
from app.schemas import RobustnessEvaluationResult, RobustnessScenarioResult


def make_student(student_id: str, name: str, email: str, student_number: str = None, status: str = "ACTIVE", verified: str = "VERIFIED", discoverable: bool = True) -> Student:
    return Student(
        student_id=student_id,
        full_name=name,
        email=email,
        student_number=student_number or f"120125{student_id}",
        study_program="S1 Teknik Komputer",
        academic_year=2025,
        password_hash="test_password_hash",
        verification_status=verified,
        account_status=status,
        is_discoverable=discoverable
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


def make_availability(intent_id: str, day_or_date: str = "2026-11-25", start_time: str = "09:00", end_time: str = "12:00", prio: int = 1) -> IntentAvailability:
    return IntentAvailability(
        availability_id=f"avail_{intent_id}",
        intent_id=intent_id,
        day_or_date=day_or_date,
        start_time=start_time,
        end_time=end_time,
        priority_rank=prio
    )


class TestDay19Robustness(unittest.TestCase):
    """Test suite komprehensif Day 19.3: Robustness & Adversarial Data."""

    def setUp(self):
        self.course_a = Course(
            course_id="c_rob_a",
            course_code="CS101",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.course_b = Course(
            course_id="c_rob_b",
            course_code="CS102",
            course_name="Arsitektur Komputer",
            study_program="S1 Teknik Komputer"
        )

        self.host_student = make_student("sh_rob", "Host Robust", "host_rob@t.ac.id")
        self.host = make_intent("ih_rob", "sh_rob", "c_rob_a", topics="Tree", mode="OFFLINE", min_size=2, max_size=4)
        self.host.availabilities = [make_availability("ih_rob")]
        self.host.student = self.host_student
        self.host.course = self.course_a

    def test_01_empty_candidate_pool(self):
        """
        19.3.1: Candidate pool kosong (candidate_intents = []).
        Ekspektasi: Sistem tidak membentuk kelompok, status NO_COMPATIBLE_GROUP,
        ukuran kelompok 1 (hanya host), 0 pelanggaran constraint.
        """
        res = form_study_group(self.host, [])
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        self.assertEqual(res["group_size"], 1)
        self.assertEqual(len(res["members"]), 1)
        self.assertEqual(res["members"][0]["intent_id"], "ih_rob")

        violations = check_hard_constraint_violations(self.host, res)
        self.assertEqual(len(violations), 0)

    def test_02_zero_schedule_overlap(self):
        """
        19.3.2: Tidak ada jadwal yang beririsan (beda hari atau jam saling lepas).
        Ekspektasi: Kandidat ditolak oleh pre-filtering jadwal >= 60m, status NO_COMPATIBLE_GROUP.
        """
        cand_student = make_student("sc_zero", "Cand Zero Overlap", "czero@t.ac.id")
        cand = make_intent("ic_zero", "sc_zero", "c_rob_a", topics="Tree", mode="OFFLINE")
        # Jadwal kandidat beda hari: 2026-11-26 (host 2026-11-25)
        cand.availabilities = [make_availability("ic_zero", day_or_date="2026-11-26")]
        cand.student = cand_student
        cand.course = self.course_a

        res = form_study_group(self.host, [cand])
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        self.assertEqual(res["candidate_pruning_stats"]["candidates_pruned_hard_constraints"], 1)

        violations = check_hard_constraint_violations(self.host, res, {"ic_zero": cand})
        self.assertEqual(len(violations), 0)

    def test_03_course_mismatch(self):
        """
        19.3.3: Kandidat mengambil mata kuliah berbeda (course_id mismatch).
        Ekspektasi: Kandidat dipangkas oleh hard constraint course, status NO_COMPATIBLE_GROUP.
        """
        cand_student = make_student("sc_diff", "Cand Diff Course", "cdiff@t.ac.id")
        cand = make_intent("ic_diff", "sc_diff", "c_rob_b", topics="Tree", mode="OFFLINE")
        cand.availabilities = [make_availability("ic_diff")]
        cand.student = cand_student
        cand.course = self.course_b

        res = form_study_group(self.host, [cand])
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        self.assertEqual(res["candidate_pruning_stats"]["candidates_pruned_hard_constraints"], 1)

        violations = check_hard_constraint_violations(self.host, res, {"ic_diff": cand})
        self.assertEqual(len(violations), 0)

    def test_04_insufficient_members_below_min_group(self):
        """
        19.3.4: Jumlah kandidat yang lolos kurang dari MinGroup (host min_size = 4, kandidat kompatibel = 2).
        Ekspektasi: Kelompok tidak dinyatakan READY, melainkan INSUFFICIENT_MEMBERS (size 3 < min 4).
        """
        host_large = make_intent("ih_large", "sh_rob", "c_rob_a", topics="Tree", mode="OFFLINE", min_size=4, max_size=5)
        host_large.availabilities = [make_availability("ih_large")]
        host_large.student = self.host_student
        host_large.course = self.course_a

        # Buat 2 kandidat kompatibel
        c1 = make_intent("c1", "s1", "c_rob_a", topics="Tree", mode="OFFLINE", min_size=4, max_size=5)
        c1.availabilities = [make_availability("c1")]
        c1.student = make_student("s1", "C1", "c1@t.ac.id")
        c1.course = self.course_a

        c2 = make_intent("c2", "s2", "c_rob_a", topics="Tree", mode="OFFLINE", min_size=4, max_size=5)
        c2.availabilities = [make_availability("c2")]
        c2.student = make_student("s2", "C2", "c2@t.ac.id")
        c2.course = self.course_a

        res = form_study_group(host_large, [c1, c2])
        self.assertEqual(res["formation_status"], "INSUFFICIENT_MEMBERS")
        self.assertEqual(res["group_size"], 3)
        self.assertEqual(res["min_group_size_bound"], 4)

        violations = check_hard_constraint_violations(host_large, res, {"c1": c1, "c2": c2})
        self.assertEqual(len(violations), 0)

    def test_05_restricted_or_unverified_accounts(self):
        """
        19.3.5: Kandidat dengan status akun RESTRICTED, UNVERIFIED, atau is_discoverable=False.
        Ekspektasi: Seluruh kandidat tersebut ditolak oleh filter Day 14.
        """
        # Kandidat 1: RESTRICTED
        s_restr = make_student("s_restr", "Restricted", "r@t.ac.id", status="RESTRICTED")
        c_restr = make_intent("c_restr", "s_restr", "c_rob_a")
        c_restr.availabilities = [make_availability("c_restr")]
        c_restr.student = s_restr
        c_restr.course = self.course_a

        # Kandidat 2: UNVERIFIED
        s_unver = make_student("s_unver", "Unverified", "u@t.ac.id", verified="UNVERIFIED")
        c_unver = make_intent("c_unver", "s_unver", "c_rob_a")
        c_unver.availabilities = [make_availability("c_unver")]
        c_unver.student = s_unver
        c_unver.course = self.course_a

        # Kandidat 3: is_discoverable = False
        s_undisc = make_student("s_undisc", "Undiscoverable", "d@t.ac.id", discoverable=False)
        c_undisc = make_intent("c_undisc", "s_undisc", "c_rob_a")
        c_undisc.availabilities = [make_availability("c_undisc")]
        c_undisc.student = s_undisc
        c_undisc.course = self.course_a

        res = form_study_group(self.host, [c_restr, c_unver, c_undisc])
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        self.assertEqual(res["candidate_pruning_stats"]["candidates_pruned_hard_constraints"], 3)

        cand_lookup = {"c_restr": c_restr, "c_unver": c_unver, "c_undisc": c_undisc}
        violations = check_hard_constraint_violations(self.host, res, cand_lookup)
        self.assertEqual(len(violations), 0)

    def test_06_incompatible_learning_mode_offline_vs_online(self):
        """
        19.3.6: Host OFFLINE vs Kandidat ONLINE.
        Ekspektasi: Ditolak oleh hard constraint kompatibilitas mode.
        """
        s_on = make_student("s_on", "Online Cand", "on@t.ac.id")
        c_on = make_intent("c_on", "s_on", "c_rob_a", mode="ONLINE")
        c_on.availabilities = [make_availability("c_on")]
        c_on.student = s_on
        c_on.course = self.course_a

        res = form_study_group(self.host, [c_on])
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        self.assertEqual(res["candidate_pruning_stats"]["candidates_pruned_hard_constraints"], 1)

        violations = check_hard_constraint_violations(self.host, res, {"c_on": c_on})
        self.assertEqual(len(violations), 0)

    def test_07_disjoint_capacity_bounds(self):
        """
        19.3.7: Rentang kapasitas tidak beririsan (Host [2, 3] vs Kandidat [4, 5]).
        Ekspektasi: Ditolak oleh hard constraint kapasitas beririsan.
        """
        s_cap = make_student("s_cap", "Cap Cand", "cap@t.ac.id")
        c_cap = make_intent("c_cap", "s_cap", "c_rob_a", min_size=4, max_size=5)
        c_cap.availabilities = [make_availability("c_cap")]
        c_cap.student = s_cap
        c_cap.course = self.course_a

        host_small = make_intent("ih_small", "sh_rob", "c_rob_a", min_size=2, max_size=3)
        host_small.availabilities = [make_availability("ih_small")]
        host_small.student = self.host_student
        host_small.course = self.course_a

        res = form_study_group(host_small, [c_cap])
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        self.assertEqual(res["group_size"], 1)
        # Kandidat masuk pool pra-syarat tetapi ditolak pada multi-way capacity constraint check
        self.assertEqual(res["candidate_pruning_stats"]["candidates_in_pool"], 1)

        violations = check_hard_constraint_violations(host_small, res, {"c_cap": c_cap})
        self.assertEqual(len(violations), 0)

    def test_08_sub_60_minute_schedule_boundary_59_minutes(self):
        """
        19.3.8: Irisan jadwal hanya 59 menit (09:00 - 09:59).
        Ekspektasi: Ditolak oleh batas keras minimum irisan 60 menit.
        """
        s_59 = make_student("s_59", "Cand 59m", "c59@t.ac.id")
        c_59 = make_intent("c_59", "s_59", "c_rob_a")
        # Overlap dengan host (09:00 - 12:00) hanya 09:00 - 09:59 (59 menit)
        c_59.availabilities = [
            IntentAvailability(availability_id="a_59", intent_id="c_59", day_or_date="2026-11-25", start_time="09:00", end_time="09:59", priority_rank=1)
        ]
        c_59.student = s_59
        c_59.course = self.course_a

        res = form_study_group(self.host, [c_59])
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        self.assertEqual(res["candidate_pruning_stats"]["candidates_pruned_hard_constraints"], 1)

        violations = check_hard_constraint_violations(self.host, res, {"c_59": c_59})
        self.assertEqual(len(violations), 0)

    def test_09_candidate_below_min_score_threshold(self):
        """
        19.3.9: Skor kecocokan kandidat di bawah min_score (misal CS = 45 < 80).
        Ekspektasi: Kandidat lolos hard constraint tetapi dipangkas oleh min_score pruning,
        status NO_COMPATIBLE_GROUP.
        """
        s_low = make_student("s_low", "Cand Low Score", "low@t.ac.id")
        # Topik sangat beda dan gaya/tujuan beda sehingga CS rendah
        c_low = make_intent("c_low", "s_low", "c_rob_a", topics="Compiler Optimization", goal="PROJECT", style="FOCUS_STUDY")
        c_low.availabilities = [make_availability("c_low")]
        c_low.student = s_low
        c_low.course = self.course_a

        res = form_study_group(self.host, [c_low], min_score=85.0)
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        # Harus lolos hard constraints tapi terfilter di candidates_pruned_min_score
        self.assertEqual(res["candidate_pruning_stats"]["candidates_pruned_hard_constraints"], 0)
        self.assertEqual(res["candidate_pruning_stats"]["candidates_pruned_min_score"], 1)

        violations = check_hard_constraint_violations(self.host, res, {"c_low": c_low})
        self.assertEqual(len(violations), 0)

    def test_10_multi_violation_adversarial_pool(self):
        """
        19.3.10: Pool berisi campuran 8 kandidat adversarial:
        (course mismatch, disjoint schedule, restricted, unverified, undiscoverable,
        mode online vs offline, capacity disjoint, 59m overlap).
        Ekspektasi: Tidak ada satu pun kandidat cacat yang lolos ke kelompok, CVR = 0%.
        """
        # 1. Course mismatch
        c1 = make_intent("adv_1", "s1", "c_rob_b")
        c1.availabilities = [make_availability("adv_1")]
        c1.student = make_student("s1", "Adv1", "adv1@t.ac.id")
        c1.course = self.course_b

        # 2. Zero schedule overlap
        c2 = make_intent("adv_2", "s2", "c_rob_a")
        c2.availabilities = [make_availability("adv_2", day_or_date="2026-11-30")]
        c2.student = make_student("s2", "Adv2", "adv2@t.ac.id")
        c2.course = self.course_a

        # 3. Restricted
        c3 = make_intent("adv_3", "s3", "c_rob_a")
        c3.availabilities = [make_availability("adv_3")]
        c3.student = make_student("s3", "Adv3", "adv3@t.ac.id", status="RESTRICTED")
        c3.course = self.course_a

        # 4. Unverified
        c4 = make_intent("adv_4", "s4", "c_rob_a")
        c4.availabilities = [make_availability("adv_4")]
        c4.student = make_student("s4", "Adv4", "adv4@t.ac.id", verified="UNVERIFIED")
        c4.course = self.course_a

        # 5. Non-discoverable
        c5 = make_intent("adv_5", "s5", "c_rob_a")
        c5.availabilities = [make_availability("adv_5")]
        c5.student = make_student("s5", "Adv5", "adv5@t.ac.id", discoverable=False)
        c5.course = self.course_a

        # 6. Mode ONLINE (Host OFFLINE)
        c6 = make_intent("adv_6", "s6", "c_rob_a", mode="ONLINE")
        c6.availabilities = [make_availability("adv_6")]
        c6.student = make_student("s6", "Adv6", "adv6@t.ac.id")
        c6.course = self.course_a

        # 7. Capacity disjoint [5, 6] (Host [2, 4])
        c7 = make_intent("adv_7", "s7", "c_rob_a", min_size=5, max_size=6)
        c7.availabilities = [make_availability("adv_7")]
        c7.student = make_student("s7", "Adv7", "adv7@t.ac.id")
        c7.course = self.course_a

        # 8. 59-minute overlap
        c8 = make_intent("adv_8", "s8", "c_rob_a")
        c8.availabilities = [
            IntentAvailability(availability_id="a8", intent_id="adv_8", day_or_date="2026-11-25", start_time="09:00", end_time="09:59", priority_rank=1)
        ]
        c8.student = make_student("s8", "Adv8", "adv8@t.ac.id")
        c8.course = self.course_a

        adversarial_pool = [c1, c2, c3, c4, c5, c6, c7, c8]
        cand_lookup = {str(c.intent_id): c for c in adversarial_pool}

        res = form_study_group(self.host, adversarial_pool)
        self.assertEqual(res["formation_status"], "NO_COMPATIBLE_GROUP")
        self.assertEqual(res["group_size"], 1)

        violations = check_hard_constraint_violations(self.host, res, cand_lookup)
        self.assertEqual(len(violations), 0)

    def test_11_check_hard_constraint_violations_detects_artificial_flaws(self):
        """
        19.3.11: Menguji bahwa check_hard_constraint_violations() secara akurat
        mendeteksi kelompok yang melanggar aturan jika terjadi kecacatan buatan.
        """
        # Cacat 1: Status READY tapi anggota hanya 1
        flaw_1 = {"formation_status": "READY", "group_size": 1, "members": [{"intent_id": "i1"}]}
        v1 = check_hard_constraint_violations(self.host, flaw_1)
        self.assertGreater(len(v1), 0)
        self.assertTrue(any("kurang dari batas minimum absolut" in msg for msg in v1))

        # Cacat 2: Status READY tapi durasi jadwal bersama < 60m
        flaw_2 = {
            "formation_status": "READY", "group_size": 2, "members": [{"intent_id": "i1"}, {"intent_id": "i2"}],
            "min_group_size_bound": 2, "max_group_size_bound": 4,
            "selected_schedule": {"duration_minutes": 45}
        }
        v2 = check_hard_constraint_violations(self.host, flaw_2)
        self.assertGreater(len(v2), 0)
        self.assertTrue(any("kurang dari 60 menit" in msg for msg in v2))

        # Cacat 3: Anggota memiliki course_id berbeda
        cand_bad_course = make_intent("i_bad_c", "s_bad", "c_rob_b")
        flaw_3 = {
            "formation_status": "READY", "group_size": 2,
            "members": [{"intent_id": str(self.host.intent_id)}, {"intent_id": "i_bad_c"}],
            "min_group_size_bound": 2, "max_group_size_bound": 4,
            "selected_schedule": {"duration_minutes": 120}
        }
        v3 = check_hard_constraint_violations(self.host, flaw_3, {"i_bad_c": cand_bad_course})
        self.assertGreater(len(v3), 0)
        self.assertTrue(any("course_id berbeda" in msg for msg in v3))

        # Cacat 4: Campuran ONLINE dan OFFLINE
        cand_online = make_intent("i_on", "s_on", "c_rob_a", mode="ONLINE")
        flaw_4 = {
            "formation_status": "READY", "group_size": 2,
            "members": [{"intent_id": str(self.host.intent_id)}, {"intent_id": "i_on"}],
            "min_group_size_bound": 2, "max_group_size_bound": 4,
            "selected_schedule": {"duration_minutes": 120}
        }
        v4 = check_hard_constraint_violations(self.host, flaw_4, {"i_on": cand_online})
        self.assertGreater(len(v4), 0)
        self.assertTrue(any("ONLINE dan OFFLINE sekaligus" in msg for msg in v4))

    def test_12_evaluate_matching_robustness_end_to_end(self):
        """
        19.3.12: Menjalankan evaluasi end-to-end evaluate_matching_robustness()
        dan memvalidasi bahwa Constraint Violation Rate (CVR) tepat 0.0%.
        """
        scenarios = [
            {
                "scenario_name": "19.3.1 - Empty Pool",
                "description": "Candidate pool kosong",
                "expected_status": "NO_COMPATIBLE_GROUP",
                "candidates": []
            },
            {
                "scenario_name": "19.3.2 - No Overlap Schedule",
                "description": "Tidak ada irisan jadwal bersama",
                "expected_status": "NO_COMPATIBLE_GROUP",
                "candidates": [
                    make_intent("c_no_ov", "s_no_ov", "c_rob_a", earliest_date="2026-11-28", latest_date="2026-11-30")
                ]
            },
            {
                "scenario_name": "19.3.3 - Course Mismatch",
                "description": "Mata kuliah berbeda CS102",
                "expected_status": "NO_COMPATIBLE_GROUP",
                "candidates": [
                    make_intent("c_diff_c", "s_diff_c", "c_rob_b")
                ]
            },
            {
                "scenario_name": "19.3.4 - Insufficient Members",
                "description": "Hanya 1 kandidat padahal target min_size=3",
                "expected_status": "INSUFFICIENT_MEMBERS",
                "candidates": [
                    make_intent("c_single", "s_single", "c_rob_a", min_size=3, max_size=4)
                ]
            },
            {
                "scenario_name": "19.3.5 - Restricted Account",
                "description": "Kandidat berstatus RESTRICTED",
                "expected_status": "NO_COMPATIBLE_GROUP",
                "candidates": [
                    make_intent("c_restr", "s_restr", "c_rob_a")
                ]
            },
            {
                "scenario_name": "19.3.6 - Incompatible Mode",
                "description": "Kandidat ONLINE sedangkan Host OFFLINE",
                "expected_status": "NO_COMPATIBLE_GROUP",
                "candidates": [
                    make_intent("c_on_inc", "s_on_inc", "c_rob_a", mode="ONLINE")
                ]
            },
        ]

        # Isi student & availabilities untuk kandidat skenario secara independen
        for sc in scenarios:
            for c in sc["candidates"]:
                c.student = make_student(c.student_id, f"Name_{c.student_id}", f"{c.student_id}@t.ac.id")
                c.course = self.course_b if c.course_id == "c_rob_b" else self.course_a
                c.availabilities = [make_availability(c.intent_id)]

        # Atur student khusus restricted untuk scenario 5
        scenarios[4]["candidates"][0].student.account_status = "RESTRICTED"

        # Atur availabilities beda hari untuk scenario 2
        scenarios[1]["candidates"][0].availabilities = [
            make_availability("c_no_ov", day_or_date="2026-11-29")
        ]

        # Host khusus min_size=3 untuk scenario 4
        host_min3 = make_intent("ih_min3", "sh_rob", "c_rob_a", min_size=3, max_size=4)
        host_min3.availabilities = [make_availability("ih_min3")]
        host_min3.student = self.host_student
        host_min3.course = self.course_a

        # Jalankan evaluate_matching_robustness
        robust_res = evaluate_matching_robustness(
            host_intent=host_min3,
            candidate_scenarios=scenarios
        )

        self.assertIsInstance(robust_res, RobustnessEvaluationResult)
        self.assertEqual(robust_res.total_scenarios_tested, len(scenarios))
        self.assertEqual(robust_res.passed_scenarios, len(scenarios))
        self.assertEqual(robust_res.failed_scenarios, 0)
        self.assertEqual(robust_res.constraint_violation_rate, 0.0)
        self.assertTrue(robust_res.all_constraints_preserved)

        for sr in robust_res.scenario_results:
            self.assertFalse(sr.is_violation)
            self.assertEqual(sr.actual_status, sr.expected_status)


if __name__ == "__main__":
    unittest.main(verbosity=2)
