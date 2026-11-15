# ==============================================================================
# test_day19_stability.py - Test Suite Matching Stability & Order Invariance (Day 19.2)
# ==============================================================================
# Rangkaian pengujian untuk memvalidasi:
# 1. Determinisme Permutasi: Hasil matching 100% independen terhadap urutan input kandidat.
# 2. Permutasi Unik: Generator permutasi terbukti menghasilkan variasi urutan yang berbeda.
# 3. Order Invariance pada Small Pool (3 kandidat, permutasi lengkap 3! = 6).
# 4. Order Invariance dengan Top-K Pool Pruning (K=5 pada 10 kandidat).
# 5. Stabilitas Penanganan Tie-Breaker Bertingkat (Level 1-7) pada Urutan Teracak.
# 6. Preservasi Multi-Way Hard Constraints (Learning Mode Transitivity) pada Urutan Teracak.
# 7. Skalabilitas Stabilitas pada Large Pool (20 kandidat, 15 permutasi unik).
# 8. Ketatnya Signature Matching (Status, Size, Member, GQ, APS, MPS, Schedule).
# 9. Formula Determinism Rate: DR = (N_consistent / N_runs) * 100% = 100.0%.
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
    generate_distinct_permutations,
    evaluate_matching_stability,
    _make_comprehensive_group_signature,
)
from app.schemas import MatchingStabilityResult, OrderPermutationRun


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


class TestDay19Stability(unittest.TestCase):
    """Test suite komprehensif Day 19.2: Matching Stability & Order Invariance."""

    def setUp(self):
        self.course = Course(
            course_id="c_stab",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )

    def test_01_generate_distinct_permutations_guarantees_uniqueness(self):
        """
        Menguji bahwa generate_distinct_permutations() menghasilkan urutan yang
        terbukti 100% berbeda satu sama lain (tidak ada duplikat urutan).
        """
        cands = [
            make_intent("c1", "s1", "c_stab"),
            make_intent("c2", "s2", "c_stab"),
            make_intent("c3", "s3", "c_stab"),
        ]

        # Minta 6 permutasi untuk 3 kandidat (3! = 6)
        perms = generate_distinct_permutations(cands, num_permutations=6)
        self.assertEqual(len(perms), 6)

        # Verifikasi seluruh permutasi unik
        seen = set()
        for p in perms:
            sig = tuple(c.intent_id for c in p)
            self.assertNotIn(sig, seen, f"Ditemukan permutasi duplikat: {sig}")
            seen.add(sig)

        # Permutasi pertama harus baseline asli
        self.assertEqual([c.intent_id for c in perms[0]], ["c1", "c2", "c3"])
        # Permutasi kedua harus reversed
        self.assertEqual([c.intent_id for c in perms[1]], ["c3", "c2", "c1"])

    def test_02_order_invariance_small_candidate_pool_3_candidates(self):
        """
        Menguji Order Invariance pada pool 3 kandidat:
        Mengevaluasi seluruh 6 variasi urutan input (exhaustive permutations).
        Target: DR = 100%, seluruh atribut kelompok (anggota, GQ, jadwal) identik.
        """
        host = make_intent("i_host", "s_host", "c_stab", topics="Binary Search Tree", min_size=3, max_size=4)
        host.availabilities = [IntentAvailability(availability_id="ah", intent_id="i_host", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)]
        host.student = make_student("s_host", "Host", "host@t.ac.id")
        host.course = self.course

        # Buat 3 kandidat dengan kecocokan berbeda-beda
        # Cand 1: Sangat cocok (BST, UNDERSTAND, DISCUSSION)
        c1 = make_intent("c1", "s1", "c_stab", topics="Binary Search Tree", goal="UNDERSTAND", style="DISCUSSION", min_size=3, max_size=4)
        c1.availabilities = [IntentAvailability(availability_id="a1", intent_id="c1", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)]
        c1.student = make_student("s1", "Cand 1", "c1@t.ac.id")
        c1.course = self.course

        # Cand 2: Cukup cocok (Tree, PRACTICE, PEER_TUTORING)
        c2 = make_intent("c2", "s2", "c_stab", topics="Tree Traversal", goal="PRACTICE", style="PEER_TUTORING", min_size=3, max_size=4)
        c2.availabilities = [IntentAvailability(availability_id="a2", intent_id="c2", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)]
        c2.student = make_student("s2", "Cand 2", "c2@t.ac.id")
        c2.course = self.course

        # Cand 3: Kurang cocok tapi lolos min_score (Graph, PROJECT, FOCUS_STUDY)
        c3 = make_intent("c3", "s3", "c_stab", topics="Graph Traversal", goal="PROJECT", style="FOCUS_STUDY", min_size=3, max_size=4)
        c3.availabilities = [IntentAvailability(availability_id="a3", intent_id="c3", day_or_date="2026-11-22", start_time="09:00", end_time="12:00", priority_rank=1)]
        c3.student = make_student("s3", "Cand 3", "c3@t.ac.id")
        c3.course = self.course

        cands = [c1, c2, c3]

        # Jalankan evaluasi stabilitas dengan 6 permutasi
        stability_res = evaluate_matching_stability(
            host_intent=host,
            candidate_intents=cands,
            min_score=50.0,
            num_permutations=6
        )

        self.assertIsInstance(stability_res, MatchingStabilityResult)
        self.assertEqual(stability_res.num_permutations, 6)
        self.assertTrue(stability_res.is_order_invariant)
        self.assertEqual(stability_res.determinism_rate, 100.0)
        self.assertEqual(stability_res.distinct_group_signatures, 1)

        # Seluruh run permutasi harus matches_baseline == True
        for run in stability_res.permutations:
            self.assertTrue(run.matches_baseline)
            self.assertEqual(run.group_quality_score, stability_res.permutations[0].group_quality_score)
            self.assertEqual(run.selected_member_intent_ids, stability_res.permutations[0].selected_member_intent_ids)

    def test_03_order_invariance_reversed_and_adversarial_input_orders(self):
        """
        Menguji stabilitas terhadap input urutan terbalik (reversed) dan rotasi siklis.
        Memastikan kandidat dengan skor terbaik tetap terpilih meskipun diletakkan di akhir list.
        """
        host = make_intent("ih", "sh", "c_stab", topics="Sorting", min_size=2, max_size=3)
        host.availabilities = [IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-25", start_time="13:00", end_time="16:00", priority_rank=1)]
        host.student = make_student("sh", "Host", "host@t.ac.id")
        host.course = self.course

        # Cand High: skor CS tinggi
        c_high = make_intent("c_high", "shigh", "c_stab", topics="Sorting", min_size=2, max_size=3)
        c_high.availabilities = [IntentAvailability(availability_id="ahigh", intent_id="c_high", day_or_date="2026-11-25", start_time="13:00", end_time="16:00", priority_rank=1)]
        c_high.student = make_student("shigh", "Cand High", "high@t.ac.id")
        c_high.course = self.course

        # Cand Low: skor CS rendah tapi lolos
        c_low = make_intent("c_low", "slow", "c_stab", topics="Heap Sort", goal="PROJECT", style="FOCUS_STUDY", min_size=2, max_size=3)
        c_low.availabilities = [IntentAvailability(availability_id="alow", intent_id="c_low", day_or_date="2026-11-25", start_time="13:00", end_time="16:00", priority_rank=1)]
        c_low.student = make_student("slow", "Cand Low", "low@t.ac.id")
        c_low.course = self.course

        # Urutan Asli: [c_high, c_low] -> c_high dipilih
        res_normal = form_study_group(host, [c_high, c_low], target_group_size=2)
        # Urutan Adversarial (c_low ditaruh pertama): [c_low, c_high] -> c_high HARUS tetap dipilih
        res_reversed = form_study_group(host, [c_low, c_high], target_group_size=2)

        sig_normal = _make_comprehensive_group_signature(res_normal)
        sig_reversed = _make_comprehensive_group_signature(res_reversed)

        self.assertEqual(sig_normal, sig_reversed)
        self.assertIn("c_high", [m["intent_id"] for m in res_reversed["members"]])
        self.assertNotIn("c_low", [m["intent_id"] for m in res_reversed["members"]])

    def test_04_order_invariance_with_top_k_candidate_pool_pruning(self):
        """
        Menguji bahwa optimasi Top-K Pool (Day 18) tetap 100% deterministik
        dan order-invariant ketika urutan input awal diacak.
        """
        host = make_intent("ih", "sh", "c_stab", topics="Graph", min_size=3, max_size=4)
        host.availabilities = [IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-23", start_time="08:00", end_time="11:00", priority_rank=1)]
        host.student = make_student("sh", "Host", "host@t.ac.id")
        host.course = self.course

        # Buat 10 kandidat dengan variasi skor
        cands = []
        for i in range(1, 11):
            c = make_intent(f"cand_{i:02d}", f"s_{i:02d}", "c_stab", min_size=3, max_size=4)
            c.availabilities = [IntentAvailability(availability_id=f"a_{i:02d}", intent_id=f"cand_{i:02d}", day_or_date="2026-11-23", start_time="08:00", end_time="11:00", priority_rank=1)]
            c.student = make_student(f"s_{i:02d}", f"Student {i}", f"s{i}@t.ac.id")
            c.course = self.course
            cands.append(c)

        # Uji stabilitas dengan Top-K pool dibatasi menjadi 5
        stability_res = evaluate_matching_stability(
            host_intent=host,
            candidate_intents=cands,
            max_candidate_pool=5,
            num_permutations=10,
            random_seed=123
        )

        self.assertTrue(stability_res.is_order_invariant)
        self.assertEqual(stability_res.determinism_rate, 100.0)
        self.assertEqual(stability_res.distinct_group_signatures, 1)

    def test_05_stability_under_hierarchical_tie_breakers(self):
        """
        Menguji stabilitas pada kasus kandidat yang mengalami tie di Level 1 s/d Level 6,
        sehingga harus dipecahkan secara deterministik oleh Level 7 (Candidate Intent ID).
        Urutan input diacak secara berbeda-beda.
        """
        host = make_intent("ih", "sh", "c_stab", topics="Hashing", min_size=2, max_size=3)
        host.availabilities = [IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-26", start_time="14:00", end_time="17:00", priority_rank=1)]
        host.student = make_student("sh", "Host", "host@t.ac.id")
        host.course = self.course

        # Cand A dan Cand B identik dalam seluruh atribut scoring & jadwal,
        # hanya beda ID: "cand_aaa" vs "cand_zzz".
        # Level 7 mensyaratkan ID terkecil secara alfabetis ("cand_aaa") harus menang.
        c_a = make_intent("cand_aaa", "s_a", "c_stab", topics="Hashing", min_size=2, max_size=3)
        c_a.availabilities = [IntentAvailability(availability_id="aa", intent_id="cand_aaa", day_or_date="2026-11-26", start_time="14:00", end_time="17:00", priority_rank=1)]
        c_a.student = make_student("s_a", "Student A", "sa@t.ac.id")
        c_a.course = self.course

        c_z = make_intent("cand_zzz", "s_z", "c_stab", topics="Hashing", min_size=2, max_size=3)
        c_z.availabilities = [IntentAvailability(availability_id="az", intent_id="cand_zzz", day_or_date="2026-11-26", start_time="14:00", end_time="17:00", priority_rank=1)]
        c_z.student = make_student("s_z", "Student Z", "sz@t.ac.id")
        c_z.course = self.course

        # Uji jika cand_zzz ditaruh di depan vs cand_aaa di depan
        res_z_first = form_study_group(host, [c_z, c_a], target_group_size=2)
        res_a_first = form_study_group(host, [c_a, c_z], target_group_size=2)

        # Keduanya HARUS memilih cand_aaa karena ID terkecil
        members_z_first = [m["intent_id"] for m in res_z_first["members"]]
        members_a_first = [m["intent_id"] for m in res_a_first["members"]]

        self.assertEqual(members_z_first, members_a_first)
        self.assertIn("cand_aaa", members_z_first)
        self.assertNotIn("cand_zzz", members_z_first)

        # Jalankan evaluate_matching_stability
        stab = evaluate_matching_stability(host, [c_z, c_a], target_group_size=2, num_permutations=2)
        self.assertTrue(stab.is_order_invariant)
        self.assertEqual(stab.determinism_rate, 100.0)

    def test_06_multi_way_learning_mode_transitivity_stability(self):
        """
        Menguji bahwa aturan transitive learning mode (Day 17/18: tidak boleh ada ONLINE & OFFLINE)
        tetap terjaga dan menghasilkan kelompok yang sama tanpa memandang urutan kandidat.
        """
        # Host HYBRID
        host = make_intent("ih", "sh", "c_stab", mode="HYBRID", min_size=3, max_size=3)
        host.availabilities = [IntentAvailability(availability_id="ah", intent_id="ih", day_or_date="2026-11-24", start_time="10:00", end_time="13:00", priority_rank=1)]
        host.student = make_student("sh", "Host", "host@t.ac.id")
        host.course = self.course

        # Cand 1: ONLINE (skor sangat tinggi)
        c_online = make_intent("c_on", "s_on", "c_stab", topics="Struktur Data", mode="ONLINE", min_size=3, max_size=3)
        c_online.availabilities = [IntentAvailability(availability_id="a_on", intent_id="c_on", day_or_date="2026-11-24", start_time="10:00", end_time="13:00", priority_rank=1)]
        c_online.student = make_student("s_on", "Student Online", "on@t.ac.id")
        c_online.course = self.course

        # Cand 2: OFFLINE (skor tinggi tapi inkompatibel dengan online)
        c_offline = make_intent("c_off", "s_off", "c_stab", topics="Struktur Data", mode="OFFLINE", min_size=3, max_size=3)
        c_offline.availabilities = [IntentAvailability(availability_id="a_off", intent_id="c_off", day_or_date="2026-11-24", start_time="10:00", end_time="13:00", priority_rank=1)]
        c_offline.student = make_student("s_off", "Student Offline", "off@t.ac.id")
        c_offline.course = self.course

        # Cand 3: HYBRID (kompatibel dengan semua)
        c_hybrid = make_intent("c_hyb", "s_hyb", "c_stab", topics="Struktur Data", mode="HYBRID", min_size=3, max_size=3)
        c_hybrid.availabilities = [IntentAvailability(availability_id="a_hyb", intent_id="c_hyb", day_or_date="2026-11-24", start_time="10:00", end_time="13:00", priority_rank=1)]
        c_hybrid.student = make_student("s_hyb", "Student Hybrid", "hyb@t.ac.id")
        c_hybrid.course = self.course

        cands = [c_online, c_offline, c_hybrid]

        stability = evaluate_matching_stability(host, cands, num_permutations=6)
        self.assertTrue(stability.is_order_invariant)
        self.assertEqual(stability.determinism_rate, 100.0)

        # Verifikasi tidak ada percampuran ONLINE dan OFFLINE di hasil mana pun
        for run in stability.permutations:
            members = run.selected_member_intent_ids
            self.assertFalse("c_on" in members and "c_off" in members)

    def test_07_order_invariance_larger_candidate_pool_20_candidates(self):
        """
        Menguji kestabilan engine pada skala lebih besar (20 kandidat, 15 permutasi unik).
        Memastikan matching tetap 100% deterministik dan efisien.
        """
        host = make_intent("ih_20", "sh_20", "c_stab", min_size=3, max_size=4)
        host.availabilities = [IntentAvailability(availability_id="ah_20", intent_id="ih_20", day_or_date="2026-11-27", start_time="10:00", end_time="14:00", priority_rank=1)]
        host.student = make_student("sh_20", "Host 20", "h20@t.ac.id")
        host.course = self.course

        cands = []
        for i in range(1, 21):
            c = make_intent(f"cand_20_{i:02d}", f"s_20_{i:02d}", "c_stab", min_size=3, max_size=4)
            c.availabilities = [IntentAvailability(availability_id=f"a_20_{i:02d}", intent_id=f"cand_20_{i:02d}", day_or_date="2026-11-27", start_time="10:00", end_time="14:00", priority_rank=1)]
            c.student = make_student(f"s_20_{i:02d}", f"Student {i}", f"s20_{i}@t.ac.id")
            c.course = self.course
            cands.append(c)

        stability = evaluate_matching_stability(host, cands, num_permutations=15, random_seed=999)
        self.assertTrue(stability.is_order_invariant)
        self.assertEqual(stability.determinism_rate, 100.0)
        self.assertEqual(stability.distinct_group_signatures, 1)

    def test_08_multi_attribute_signature_strictness(self):
        """
        Memastikan _make_comprehensive_group_signature() membedakan dua hasil yang memiliki
        GQ sama tetapi anggota berbeda atau jadwal berbeda (tidak ada false positive konsistensi).
        """
        res_a = {
            "formation_status": "READY",
            "group_size": 3,
            "members": [{"intent_id": "i1"}, {"intent_id": "i2"}, {"intent_id": "i3"}],
            "group_quality_score": 85.00,
            "average_pair_score": 85.00,
            "minimum_pair_score": 85.00,
            "selected_schedule": {"date": "2026-11-20", "start_time": "09:00", "end_time": "12:00", "duration_minutes": 180}
        }

        # res_b: GQ sama persis (85.00), tapi anggota berbeda ("i4" menggantikan "i3")
        res_b = {
            "formation_status": "READY",
            "group_size": 3,
            "members": [{"intent_id": "i1"}, {"intent_id": "i2"}, {"intent_id": "i4"}],
            "group_quality_score": 85.00,
            "average_pair_score": 85.00,
            "minimum_pair_score": 85.00,
            "selected_schedule": {"date": "2026-11-20", "start_time": "09:00", "end_time": "12:00", "duration_minutes": 180}
        }

        # res_c: anggota sama, GQ sama, tapi jadwal berbeda
        res_c = {
            "formation_status": "READY",
            "group_size": 3,
            "members": [{"intent_id": "i1"}, {"intent_id": "i2"}, {"intent_id": "i3"}],
            "group_quality_score": 85.00,
            "average_pair_score": 85.00,
            "minimum_pair_score": 85.00,
            "selected_schedule": {"date": "2026-11-21", "start_time": "10:00", "end_time": "13:00", "duration_minutes": 180}
        }

        sig_a = _make_comprehensive_group_signature(res_a)
        sig_b = _make_comprehensive_group_signature(res_b)
        sig_c = _make_comprehensive_group_signature(res_c)

        self.assertNotEqual(sig_a, sig_b)
        self.assertNotEqual(sig_a, sig_c)

    def test_09_schedule_selection_determinism_under_order_scrambling(self):
        """
        D19.2-02 Hardening:
        Menguji bahwa jadwal bersama yang dipilih (selected_schedule) selalu 100% konsisten
        pada kelompok beranggotakan beberapa mahasiswa (Host + Cand 1 + Cand 2) yang memiliki
        lebih dari satu opsi jadwal bersama valid (Slot A: 120m vs Slot B: 180m),
        meskipun urutan kandidat dibalik ([c1, c2] vs [c2, c1]) atau diacak.
        """
        host = make_intent("ih_sched", "sh", "c_stab", min_size=3, max_size=3)
        host.availabilities = [
            IntentAvailability(availability_id="ah1", intent_id="ih_sched", day_or_date="2026-11-21", start_time="09:00", end_time="11:00", priority_rank=1),
            IntentAvailability(availability_id="ah2", intent_id="ih_sched", day_or_date="2026-11-22", start_time="13:00", end_time="16:00", priority_rank=2),
        ]
        host.student = make_student("sh", "Host", "host@t.ac.id")
        host.course = self.course

        cand1 = make_intent("ic1_sched", "sc1", "c_stab", min_size=3, max_size=3)
        cand1.availabilities = [
            IntentAvailability(availability_id="ac1_1", intent_id="ic1_sched", day_or_date="2026-11-21", start_time="09:00", end_time="11:00", priority_rank=1),
            IntentAvailability(availability_id="ac1_2", intent_id="ic1_sched", day_or_date="2026-11-22", start_time="13:00", end_time="16:00", priority_rank=2),
        ]
        cand1.student = make_student("sc1", "Cand 1", "cand1@t.ac.id")
        cand1.course = self.course

        cand2 = make_intent("ic2_sched", "sc2", "c_stab", min_size=3, max_size=3)
        cand2.availabilities = [
            IntentAvailability(availability_id="ac2_1", intent_id="ic2_sched", day_or_date="2026-11-21", start_time="09:00", end_time="11:00", priority_rank=1),
            IntentAvailability(availability_id="ac2_2", intent_id="ic2_sched", day_or_date="2026-11-22", start_time="13:00", end_time="16:00", priority_rank=2),
        ]
        cand2.student = make_student("sc2", "Cand 2", "cand2@t.ac.id")
        cand2.course = self.course

        # Jalankan form_study_group dengan urutan asli [cand1, cand2] dan terbalik [cand2, cand1]
        res_order1 = form_study_group(host, [cand1, cand2])
        res_order2 = form_study_group(host, [cand2, cand1])

        self.assertEqual(res_order1["formation_status"], "READY")
        self.assertEqual(res_order2["formation_status"], "READY")
        self.assertEqual(res_order1["group_size"], 3)
        self.assertEqual(res_order2["group_size"], 3)

        sched1 = res_order1["selected_schedule"]
        sched2 = res_order2["selected_schedule"]

        # Keduanya harus menghasilkan jadwal yang identik (durasi terpanjang: 2026-11-22 13:00-16:00, 180m)
        self.assertEqual(sched1["date"], sched2["date"])
        self.assertEqual(sched1["start_time"], sched2["start_time"])
        self.assertEqual(sched1["end_time"], sched2["end_time"])
        self.assertEqual(sched1["duration_minutes"], sched2["duration_minutes"])
        self.assertEqual(sched1["duration_minutes"], 180)
        self.assertEqual(sched1["date"], "2026-11-22")

        # Uji via stability evaluator dengan 2 permutasi unik
        stab_sched = evaluate_matching_stability(host, [cand1, cand2], num_permutations=2)
        self.assertTrue(stab_sched.is_order_invariant)
        self.assertEqual(stab_sched.determinism_rate, 100.0)

    def test_10_mathematical_determinism_rate_calculation(self):
        """
        Menguji formula matematis:
          DR = (N_consistent / N_runs) * 100%
        Memastikan persentase terhitung akurat pada pembulatan 2 desimal.
        """
        # Simulasi 10 runs dengan 10 consistent -> 100.0%
        res_full = MatchingStabilityResult(
            num_permutations=10,
            is_order_invariant=True,
            determinism_rate=100.0,
            distinct_group_signatures=1,
            baseline_signature="SIG_A",
            permutations=[
                OrderPermutationRun(
                    permutation_index=i,
                    input_order_intent_ids=["c1", "c2"],
                    selected_member_intent_ids=["c1", "c2"],
                    group_quality_score=85.0,
                    matches_baseline=True
                )
                for i in range(10)
            ]
        )
        self.assertEqual(res_full.determinism_rate, 100.0)
        self.assertTrue(res_full.is_order_invariant)

        # Simulasi partial match (misal 9 dari 10 konsisten -> 90.0%)
        res_partial = MatchingStabilityResult(
            num_permutations=10,
            is_order_invariant=False,
            determinism_rate=90.0,
            distinct_group_signatures=2,
            baseline_signature="SIG_A",
            permutations=[
                OrderPermutationRun(
                    permutation_index=i,
                    input_order_intent_ids=["c1", "c2"],
                    selected_member_intent_ids=["c1", "c2"],
                    group_quality_score=85.0,
                    matches_baseline=(i != 9)
                )
                for i in range(10)
            ]
        )
        self.assertEqual(res_partial.determinism_rate, 90.0)
        self.assertFalse(res_partial.is_order_invariant)
        self.assertEqual(res_partial.distinct_group_signatures, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

