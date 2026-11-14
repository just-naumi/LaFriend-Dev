"""
Day 14 - Hard Constraint Filtering Test Suite
Tests:
1. Schedule Normalization (resolve_availability_windows)
   - Multi-date expansion across intent date range
   - Strict rejection of specific dates outside range
   - Day of week mapping
2. Overlap Minutes Boundary (calculate_overlap_minutes)
   - Exact 60 minutes boundary (PASS)
   - 59 minutes boundary (FAIL)
   - Abutting schedule 0 minutes (FAIL)
   - Cross-date schedule separation
3. Learning Mode Compatibility (is_learning_mode_compatible)
   - ONLINE, OFFLINE, HYBRID matrix
4. Group Capacity Compatibility (is_group_capacity_compatible)
5. Session Capacity Occupancy (calculate_session_occupied_capacity)
   - Host de-duplication
   - ACCEPTED & CONFIRMED counting
   - INVITED & WITHDRAWN exclusion
6. Session Matching Filter (filter_candidate_sessions)
   - All 10 acceptance/rejection criteria
7. Partner Matching Filter (filter_candidate_partners)
   - All 10 acceptance/rejection criteria
"""

import sys
from pathlib import Path
from datetime import datetime

# Setup path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError
from app.database import engine, Base, SessionLocal
from app.schemas import AvailabilityCreate
from app.models import (
    Student, Course, StudyIntent, IntentAvailability,
    StudySession, SessionSlot, SessionMember
)
from app.matching import (
    parse_time_minutes,
    resolve_availability_windows,
    calculate_overlap_minutes,
    find_common_schedule,
    priority_pair_key,
    is_learning_mode_compatible,
    is_group_capacity_compatible,
    calculate_session_occupied_capacity,
    filter_candidate_sessions,
    filter_candidate_partners
)


def run_tests():
    print("=" * 70)
    print("RUNNING DAY 14: HARD CONSTRAINT FILTERING TEST SUITE")
    print("=" * 70)
    
    passed_count = 0
    total_count = 0
    
    def report(name, condition, details=""):
        nonlocal passed_count, total_count
        total_count += 1
        if condition:
            passed_count += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} - {details}")
            assert condition, f"{name}: {details}"

    # ---------------------------------------------------------
    # SUITE 1: Normalisasi Jadwal (resolve_availability_windows)
    # ---------------------------------------------------------
    print("\n--- SUITE 1: Schedule Normalization ---")
    
    class DummySlot:
        def __init__(self, day_or_date, start, end, prio=1):
            self.day_or_date = day_or_date
            self.start_time = start
            self.end_time = end
            self.priority_rank = prio

    class DummyIntent:
        def __init__(self, earliest, latest, slots):
            self.earliest_date = earliest
            self.latest_date = latest
            self.availabilities = slots

    # 1.1 Rentang 16–30 November 2026 (Senin jatuh di tgl 16, 23, 30)
    # 2026-11-16 = Senin, 2026-11-23 = Senin, 2026-11-30 = Senin
    intent_senin = DummyIntent(
        earliest="2026-11-16",
        latest="2026-11-30",
        slots=[DummySlot("Senin", "09:00", "12:00")]
    )
    windows_senin = resolve_availability_windows(intent_senin)
    dates_found = [w["date"] for w in windows_senin]
    report(
        "Senin dalam 16-30 Nov diekspansi ke 3 tanggal riil (16, 23, 30)",
        dates_found == ["2026-11-16", "2026-11-23", "2026-11-30"],
        f"Found: {dates_found}"
    )

    # 1.2 Hari di luar rentang tanggal tidak masuk hasil
    # Rentang 17–20 Nov (Selasa s/d Jumat) -> tidak ada hari Senin
    intent_no_senin = DummyIntent(
        earliest="2026-11-17",
        latest="2026-11-20",
        slots=[DummySlot("Senin", "09:00", "12:00")]
    )
    windows_no_senin = resolve_availability_windows(intent_no_senin)
    report("Hari di luar rentang tanggal menghasilkan list kosong", len(windows_no_senin) == 0)

    # 1.3 Tanggal spesifik di luar rentang intent ditolak
    intent_specific_out = DummyIntent(
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("2026-11-10", "09:00", "12:00")]  # tgl 10 sebelum tgl 20
    )
    windows_spec_out = resolve_availability_windows(intent_specific_out)
    report("Tanggal spesifik di luar rentang ditolak", len(windows_spec_out) == 0)

    # 1.4 Tanggal spesifik di dalam rentang diterima
    intent_specific_in = DummyIntent(
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("2026-11-22", "14:00", "16:00")]
    )
    windows_spec_in = resolve_availability_windows(intent_specific_in)
    report(
        "Tanggal spesifik di dalam rentang diterima",
        len(windows_spec_in) == 1 and windows_spec_in[0]["date"] == "2026-11-22"
    )

    # ---------------------------------------------------------
    # SUITE 2: Boundary Test Overlap Minutes
    # ---------------------------------------------------------
    print("\n--- SUITE 2: Overlap Minutes Boundary ---")
    
    # 2.1 Overlap tepat 60 menit -> Lolos
    # Slot A: 09:00 - 11:00, Slot B: 10:00 - 12:00 -> Irisan 10:00 - 11:00 (60 menit)
    dur, s, e = calculate_overlap_minutes("09:00", "11:00", "10:00", "12:00")
    report("Batas tepat 60 menit terhitung akurat", dur == 60 and s == "10:00" and e == "11:00")

    # 2.2 Overlap 59 menit -> Ditolak di find_common_schedule
    dur_59, _, _ = calculate_overlap_minutes("09:00", "10:59", "10:00", "12:00")
    report("Durasi 59 menit terhitung akurat", dur_59 == 59)
    
    w_a = [{"date": "2026-11-20", "start_time": "09:00", "end_time": "10:59"}]
    w_b = [{"date": "2026-11-20", "start_time": "10:00", "end_time": "12:00"}]
    common_59 = find_common_schedule(w_a, w_b, min_duration=60)
    report("Jadwal 59 menit ditolak oleh find_common_schedule", len(common_59) == 0)

    # 2.3 Batas waktu bersinggungan (10:00-11:00 & 11:00-12:00) -> 0 menit
    dur_abut, _, _ = calculate_overlap_minutes("10:00", "11:00", "11:00", "12:00")
    report("Jadwal tepat bersinggungan menghasilkan overlap 0 menit", dur_abut == 0)

    # 2.4 Tidak ada irisan waktu pada tanggal yang sama
    dur_none, _, _ = calculate_overlap_minutes("08:00", "10:00", "13:00", "15:00")
    report("Jadwal tidak bertemu menghasilkan overlap 0 menit", dur_none == 0)

    # 2.5 Tanggal berbeda tidak boleh digabung
    w_diff1 = [{"date": "2026-11-16", "start_time": "09:00", "end_time": "12:00"}]
    w_diff2 = [{"date": "2026-11-17", "start_time": "09:00", "end_time": "12:00"}]
    common_diff = find_common_schedule(w_diff1, w_diff2, min_duration=60)
    report("Jadwal beda tanggal tidak boleh menghasilkan irisan", len(common_diff) == 0)

    # ---------------------------------------------------------
    # SUITE 3: Mode Belajar & Kapasitas Kelompok
    # ---------------------------------------------------------
    print("\n--- SUITE 3: Learning Mode & Capacity Compatibility ---")

    # 3.1 Mode Kompatibilitas
    report("ONLINE + ONLINE kompatibel", is_learning_mode_compatible("ONLINE", "ONLINE")[0] is True)
    report("OFFLINE + OFFLINE kompatibel", is_learning_mode_compatible("OFFLINE", "OFFLINE")[0] is True)
    report("HYBRID + ONLINE kompatibel", is_learning_mode_compatible("HYBRID", "ONLINE")[0] is True)
    report("HYBRID + OFFLINE kompatibel", is_learning_mode_compatible("HYBRID", "OFFLINE")[0] is True)
    report("ONLINE + OFFLINE tidak kompatibel", is_learning_mode_compatible("ONLINE", "OFFLINE")[0] is False)

    # 3.2 Kapasitas Kelompok Beririsan
    report("[2, 4] dan [3, 5] beririsan (3..4)", is_group_capacity_compatible(2, 4, 3, 5) is True)
    report("[4, 6] dan [2, 3] tidak beririsan", is_group_capacity_compatible(4, 6, 2, 3) is False)

    # ---------------------------------------------------------
    # SUITE 4: Penghitungan Keterisian Kursi Sesi
    # ---------------------------------------------------------
    print("\n--- SUITE 4: Session Capacity Calculation ---")

    class DummyMember:
        def __init__(self, sid, status, role="MEMBER"):
            self.student_id = sid
            self.status = status
            self.role = role

    class DummySession:
        def __init__(self, host_id, members=None, max_size=4):
            self.host_id = host_id
            self.members = members or []
            self.max_group_size = max_size

    # Host saja -> 1
    sess_host_only = DummySession("host_1")
    report("Sesi hanya host terhitung 1 kursi", calculate_session_occupied_capacity(sess_host_only) == 1)

    # Host + record host di members -> tetap 1 (de-duplication)
    sess_host_dup = DummySession("host_1", [DummyMember("host_1", "CONFIRMED", "HOST")])
    report("Host tidak terhitung dua kali walau ada di session.members", calculate_session_occupied_capacity(sess_host_dup) == 1)

    # Host + 1 ACCEPTED + 1 CONFIRMED -> 3
    sess_with_members = DummySession("host_1", [
        DummyMember("mem_1", "ACCEPTED"),
        DummyMember("mem_2", "CONFIRMED")
    ])
    report("Anggota ACCEPTED & CONFIRMED mengurangi kapasitas", calculate_session_occupied_capacity(sess_with_members) == 3)

    # Anggota INVITED atau WITHDRAWN tidak mengurangi kapasitas
    sess_with_invited = DummySession("host_1", [
        DummyMember("mem_1", "INVITED"),
        DummyMember("mem_2", "WITHDRAWN")
    ])
    report("Anggota INVITED & WITHDRAWN tidak memakan kuota", calculate_session_occupied_capacity(sess_with_invited) == 1)

    # ---------------------------------------------------------
    # SUITE 5: Session Matching Hard Constraints Filter
    # ---------------------------------------------------------
    print("\n--- SUITE 5: Session Matching Filter (10 Skenario) ---")

    class DummySlotModel:
        def __init__(self, date, start, end, status="APPROVED"):
            self.session_date = date
            self.start_time = start
            self.end_time = end
            self.status = status

    class FullDummySession:
        def __init__(self, sid, host_id, cid, mode, status="OPEN", max_size=4, slots=None, members=None):
            self.session_id = sid
            self.host_id = host_id
            self.course_id = cid
            self.learning_mode = mode
            self.status = status
            self.max_group_size = max_size
            self.slots = slots or []
            self.members = members or []

    class FullDummyIntent:
        def __init__(self, iid, sid, cid, mode, earliest, latest, slots, min_size=2, max_size=4):
            self.intent_id = iid
            self.student_id = sid
            self.course_id = cid
            self.learning_mode = mode
            self.earliest_date = earliest
            self.latest_date = latest
            self.availabilities = slots
            self.min_group_size = min_size
            self.max_group_size = max_size

    # Intent pencari: Andi (std_andi), TC1013, OFFLINE, 2026-11-20 s/d 2026-11-25, Rabu 09:00–12:00
    # 2026-11-25 adalah Rabu
    intent_andi = FullDummyIntent(
        iid="int_andi",
        sid="std_andi",
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "09:00", "12:00")]
    )

    # Skenario 5.1: Sesi Sempurna (APPROVED slot Rabu 10:00–12:00 di tgl 2026-11-25) -> Lolos
    sess_perfect = FullDummySession(
        sid="sess_1",
        host_id="std_host",
        cid="TC1013",
        mode="OFFLINE",
        status="OPEN",
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "APPROVED")]
    )
    res_sess_1 = filter_candidate_sessions(intent_andi, [sess_perfect])
    report("Session Filter: Sesi sempurna lolos", len(res_sess_1) == 1)

    # Skenario 5.2: Slot PROPOSED saja -> Ditolak
    sess_proposed = FullDummySession(
        sid="sess_2",
        host_id="std_host",
        cid="TC1013",
        mode="OFFLINE",
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "PROPOSED")]
    )
    report("Session Filter: Tolak slot bertatus PROPOSED", len(filter_candidate_sessions(intent_andi, [sess_proposed])) == 0)

    # Skenario 5.3: Slot REJECTED saja -> Ditolak
    sess_rejected = FullDummySession(
        sid="sess_3",
        host_id="std_host",
        cid="TC1013",
        mode="OFFLINE",
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "REJECTED")]
    )
    report("Session Filter: Tolak slot bertatus REJECTED", len(filter_candidate_sessions(intent_andi, [sess_rejected])) == 0)

    # Skenario 5.4: Status sesi DRAFT / CONFIRMED (bukan OPEN) -> Ditolak
    sess_draft = FullDummySession(
        sid="sess_4",
        host_id="std_host",
        cid="TC1013",
        mode="OFFLINE",
        status="DRAFT",
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "APPROVED")]
    )
    report("Session Filter: Tolak sesi berstatus DRAFT", len(filter_candidate_sessions(intent_andi, [sess_draft])) == 0)

    # Skenario 5.5: Mata kuliah berbeda (TC2043 vs TC1013) -> Ditolak
    sess_diff_course = FullDummySession(
        sid="sess_5",
        host_id="std_host",
        cid="TC2043",
        mode="OFFLINE",
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "APPROVED")]
    )
    report("Session Filter: Tolak sesi dengan mata kuliah berbeda", len(filter_candidate_sessions(intent_andi, [sess_diff_course])) == 0)

    # Skenario 5.6: Sesi milik sendiri (host_id == std_andi) -> Ditolak
    sess_own = FullDummySession(
        sid="sess_6",
        host_id="std_andi",
        cid="TC1013",
        mode="OFFLINE",
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "APPROVED")]
    )
    report("Session Filter: Tolak sesi milik mahasiswa sendiri", len(filter_candidate_sessions(intent_andi, [sess_own])) == 0)

    # Skenario 5.7: Mahasiswa sudah menjadi anggota sesi -> Ditolak
    sess_already_mem = FullDummySession(
        sid="sess_7",
        host_id="std_host",
        cid="TC1013",
        mode="OFFLINE",
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "APPROVED")],
        members=[DummyMember("std_andi", "CONFIRMED")]
    )
    report("Session Filter: Tolak sesi jika mahasiswa sudah terdaftar", len(filter_candidate_sessions(intent_andi, [sess_already_mem])) == 0)

    # Skenario 5.8: Sesi penuh kapasitas (kapasitas 3, terisi 3) -> Ditolak
    sess_full = FullDummySession(
        sid="sess_8",
        host_id="std_host",
        cid="TC1013",
        mode="OFFLINE",
        max_size=3,
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "APPROVED")],
        members=[DummyMember("m1", "CONFIRMED"), DummyMember("m2", "ACCEPTED")]
    )
    report("Session Filter: Tolak sesi yang kapasitasnya sudah penuh", len(filter_candidate_sessions(intent_andi, [sess_full])) == 0)

    # Skenario 5.9: Mode belajar tidak kompatibel (OFFLINE vs ONLINE) -> Ditolak
    sess_online = FullDummySession(
        sid="sess_9",
        host_id="std_host",
        cid="TC1013",
        mode="ONLINE",
        slots=[DummySlotModel("2026-11-25", "10:00", "12:00", "APPROVED")]
    )
    report("Session Filter: Tolak sesi mode tidak kompatibel", len(filter_candidate_sessions(intent_andi, [sess_online])) == 0)

    # Skenario 5.10: Irisan waktu hanya 59 menit (11:01–12:00) -> Ditolak
    sess_59min = FullDummySession(
        sid="sess_10",
        host_id="std_host",
        cid="TC1013",
        mode="OFFLINE",
        slots=[DummySlotModel("2026-11-25", "11:01", "13:00", "APPROVED")]
    )
    report("Session Filter: Tolak sesi dengan irisan 59 menit", len(filter_candidate_sessions(intent_andi, [sess_59min])) == 0)

    # ---------------------------------------------------------
    # SUITE 6: Partner Matching Hard Constraints Filter
    # ---------------------------------------------------------
    print("\n--- SUITE 6: Partner Matching Filter (10 Skenario) ---")

    class DummyStudentModel:
        def __init__(self, sid, acc_status="ACTIVE", verified="VERIFIED", discoverable=True):
            self.student_id = sid
            self.account_status = acc_status
            self.verification_status = verified
            self.is_discoverable = discoverable

    class FullDummyCandidateIntent:
        def __init__(self, iid, student, cid, mode, earliest, latest, slots, status="ACTIVE", min_size=2, max_size=4):
            self.intent_id = iid
            self.student_id = student.student_id
            self.student = student
            self.course_id = cid
            self.learning_mode = mode
            self.status = status
            self.min_group_size = min_size
            self.max_group_size = max_size
            self.earliest_date = earliest
            self.latest_date = latest
            self.availabilities = slots

    std_budi = DummyStudentModel("std_budi", "ACTIVE", "VERIFIED", True)
    
    # Skenario 6.1: Partner Sempurna (Budi, TC1013, OFFLINE, Rabu 10:00–12:00) -> Lolos
    cand_perfect = FullDummyCandidateIntent(
        iid="int_budi",
        student=std_budi,
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    res_part_1 = filter_candidate_partners(intent_andi, [cand_perfect])
    report("Partner Filter: Partner sempurna lolos", len(res_part_1) == 1)

    # Skenario 6.2: Pemilik intent yang sama (student_id sama walau intent_id beda) -> Ditolak
    cand_same_std = FullDummyCandidateIntent(
        iid="int_andi_2",
        student=DummyStudentModel("std_andi"),
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    report("Partner Filter: Tolak intent milik mahasiswa sendiri", len(filter_candidate_partners(intent_andi, [cand_same_std])) == 0)

    # Skenario 6.3: Status intent kandidat != ACTIVE (misal MATCHED) -> Ditolak
    cand_matched = FullDummyCandidateIntent(
        iid="int_matched",
        student=std_budi,
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")],
        status="MATCHED"
    )
    report("Partner Filter: Tolak intent kandidat yang sudah MATCHED", len(filter_candidate_partners(intent_andi, [cand_matched])) == 0)

    # Skenario 6.4: Akun mahasiswa RESTRICTED -> Ditolak
    cand_restricted = FullDummyCandidateIntent(
        iid="int_restr",
        student=DummyStudentModel("std_r", acc_status="RESTRICTED", verified="VERIFIED", discoverable=True),
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    report("Partner Filter: Tolak kandidat dengan akun RESTRICTED", len(filter_candidate_partners(intent_andi, [cand_restricted])) == 0)

    # Skenario 6.5: Akun mahasiswa non-discoverable -> Ditolak
    cand_nondisc = FullDummyCandidateIntent(
        iid="int_nondisc",
        student=DummyStudentModel("std_nd", acc_status="ACTIVE", verified="VERIFIED", discoverable=False),
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    report("Partner Filter: Tolak kandidat yang tidak discoverable", len(filter_candidate_partners(intent_andi, [cand_nondisc])) == 0)

    # Skenario 6.6: Akun mahasiswa belum VERIFIED (PENDING) -> Ditolak
    cand_unverified = FullDummyCandidateIntent(
        iid="int_unver",
        student=DummyStudentModel("std_uv", acc_status="ACTIVE", verified="PENDING", discoverable=True),
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    report("Partner Filter: Tolak kandidat yang belum VERIFIED", len(filter_candidate_partners(intent_andi, [cand_unverified])) == 0)

    # Skenario 6.7: Mata kuliah berbeda -> Ditolak
    cand_diff_course = FullDummyCandidateIntent(
        iid="int_diff",
        student=std_budi,
        cid="TC2043",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    report("Partner Filter: Tolak kandidat dengan mata kuliah berbeda", len(filter_candidate_partners(intent_andi, [cand_diff_course])) == 0)

    # Skenario 6.8: Mode tidak kompatibel (ONLINE vs OFFLINE) -> Ditolak
    cand_online = FullDummyCandidateIntent(
        iid="int_onl",
        student=std_budi,
        cid="TC1013",
        mode="ONLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    report("Partner Filter: Tolak kandidat dengan mode tidak kompatibel", len(filter_candidate_partners(intent_andi, [cand_online])) == 0)

    # Skenario 6.9: Kapasitas kelompok tidak beririsan ([4, 6] vs [2, 3]) -> Ditolak
    cand_bad_size = FullDummyCandidateIntent(
        iid="int_size",
        student=std_budi,
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")],
        min_size=4,
        max_size=6
    )
    # Intent Andi adalah default [2, 3]
    intent_andi.min_group_size = 2
    intent_andi.max_group_size = 3
    report("Partner Filter: Tolak kandidat dengan kapasitas tidak beririsan", len(filter_candidate_partners(intent_andi, [cand_bad_size])) == 0)

    # Skenario 6.10: Irisan waktu hanya 59 menit -> Ditolak
    cand_59min = FullDummyCandidateIntent(
        iid="int_59",
        student=std_budi,
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "11:01", "13:00")],
        min_size=2,
        max_size=4
    )
    intent_andi.max_group_size = 4
    report("Partner Filter: Tolak kandidat dengan irisan hanya 59 menit", len(filter_candidate_partners(intent_andi, [cand_59min])) == 0)

    # ---------------------------------------------------------
    # SUITE 7: Edge Case Hardening (Audit Temuan 1–7)
    # ---------------------------------------------------------
    print("\n--- SUITE 7: Edge Case Hardening (Temuan Audit) ---")

    # 7.1 parse_time_minutes validasi jam 00-23 dan menit 00-59 (format ketat HH:MM 2-digit)
    report("parse_time: Jam valid 09:30 dikonversi ke 570", parse_time_minutes("09:30") == 570)
    report("parse_time: Jam valid 23:59 dikonversi ke 1439", parse_time_minutes("23:59") == 1439)
    for bad_t in ["9:00", "24:00", "25:00", "12:60", "12:75", "99:99", "-01:00", "abc"]:
        try:
            parse_time_minutes(bad_t)
            report(f"parse_time: Tolak jam/menit di luar batas/format ({bad_t})", False, "Should raise ValueError")
        except ValueError:
            report(f"parse_time: Tolak jam/menit di luar batas/format ({bad_t})", True)

    # 7.2 is_group_capacity_compatible validasi seluruh rentang
    report("Kapasitas: Tolak rentang asal yang melanggar batas (2, 99, 2, 4)", is_group_capacity_compatible(2, 99, 2, 4) is False)
    report("Kapasitas: Tolak min < 2 (1, 4, 2, 4)", is_group_capacity_compatible(1, 4, 2, 4) is False)
    report("Kapasitas: Tolak min > max (5, 3, 2, 4)", is_group_capacity_compatible(5, 3, 2, 4) is False)
    report("Kapasitas: Terima rentang valid [2..4] dan [3..5]", is_group_capacity_compatible(2, 4, 3, 5) is True)

    # 7.3 Whitelist learning mode ketat (ONLINE, OFFLINE, HYBRID)
    report("Mode: Tolak mode tidak dikenal REMOTE + REMOTE", is_learning_mode_compatible("REMOTE", "REMOTE")[0] is False)
    report("Mode: Tolak mode tidak dikenal HYBRID + REMOTE", is_learning_mode_compatible("HYBRID", "REMOTE")[0] is False)
    report("Mode: Terima HYBRID + ONLINE", is_learning_mode_compatible("HYBRID", "ONLINE")[0] is True)

    # 7.4 Tolak priority_rank di luar 1, 2, 3 di schemas.py
    try:
        AvailabilityCreate(day_or_date="Senin", start_time="09:00", end_time="11:00", priority_rank=4)
        report("Schema: Tolak priority_rank=4", False, "Should raise ValidationError")
    except ValidationError:
        report("Schema: Tolak priority_rank=4", True)

    try:
        AvailabilityCreate(day_or_date="Senin", start_time="09:00", end_time="11:00", priority_rank=0)
        report("Schema: Tolak priority_rank=0", False, "Should raise ValidationError")
    except ValidationError:
        report("Schema: Tolak priority_rank=0", True)

    # 7.5 Deduplikasi kandidat partner (1 mahasiswa hanya muncul 1 kali)
    cand_budi_intent1 = FullDummyCandidateIntent(
        iid="int_budi_1",
        student=std_budi,
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    cand_budi_intent2 = FullDummyCandidateIntent(
        iid="int_budi_2",
        student=std_budi,
        cid="TC1013",
        mode="OFFLINE",
        earliest="2026-11-20",
        latest="2026-11-25",
        slots=[DummySlot("Rabu", "10:00", "12:00")]
    )
    res_dedup_partners = filter_candidate_partners(intent_andi, [cand_budi_intent1, cand_budi_intent2])
    report("Partner: 1 mahasiswa dengan 2 intent hanya muncul 1 kali", len(res_dedup_partners) == 1)

    # 7.6 Pertahankan prioritas terbaik saat deduplikasi slot
    w_prio1 = [{"date": "2026-11-20", "start_time": "10:00", "end_time": "12:00", "priority": 3}]
    w_prio2 = [{"date": "2026-11-20", "start_time": "10:00", "end_time": "12:00", "priority": 2}]
    w_prio3 = [{"date": "2026-11-20", "start_time": "10:00", "end_time": "12:00", "priority": 1}]
    # Gabung: iterasi kombinasi pertama menghasilkan (3, 2), kombinasi kedua menghasilkan (1, 1)
    common_prio = find_common_schedule(w_prio1 + w_prio3, w_prio2 + w_prio3, min_duration=60)
    report(
        "Jadwal: Pertahankan prioritas terbaik (prio 1) saat deduplikasi slot",
        len(common_prio) == 1 and common_prio[0]["priority_a"] == 1 and common_prio[0]["priority_b"] == 1,
        f"Result: {common_prio}"
    )

    # 7.6b Pasangan prioritas silang tidak boleh menghasilkan (1, 1) palsu pada slot_key yang bertabrakan (deduplikasi riil)
    # Evaluasi minimax comparator:
    pair1 = (1, 3)
    pair2 = (3, 1)
    best_pair = min([pair1, pair2], key=lambda p: priority_pair_key(*p))
    report("Priority minimax: Memilih pasangan utuh tanpa membuat (1, 1) palsu", best_pair == (1, 3))

    # Skenario tabrakan irisan waktu riil 10:00–12:00:
    # Kombinasi 1 (wa1 & wb1): 09:00-12:00 (prio 1) vs 10:00-13:00 (prio 3) -> irisan 10:00-12:00, prioritas (1, 3)
    # Kombinasi 2 (wa2 & wb2): 10:00-13:00 (prio 3) vs 09:00-12:00 (prio 1) -> irisan 10:00-12:00, prioritas (3, 1)
    # Kedua kombinasi bertabrakan di slot_key identik ("2026-11-20", "10:00", "12:00").
    # Algoritma lama min(1, 3) & min(3, 1) akan membuat kombinasi palsu (1, 1).
    # Algoritma minimax baru wajib mempertahankan salah satu pasangan asli: (1, 3) atau (3, 1), dan BUKAN (1, 1).
    w_cross_a = [
        {"date": "2026-11-20", "start_time": "09:00", "end_time": "12:00", "priority": 1},
        {"date": "2026-11-20", "start_time": "10:00", "end_time": "13:00", "priority": 3},
    ]
    w_cross_b = [
        {"date": "2026-11-20", "start_time": "10:00", "end_time": "13:00", "priority": 3},
        {"date": "2026-11-20", "start_time": "09:00", "end_time": "12:00", "priority": 1},
    ]
    results = find_common_schedule(w_cross_a, w_cross_b, min_duration=60)
    target = next((item for item in results if item["start_time"] == "10:00" and item["end_time"] == "12:00"), None)
    target_pair = (target["priority_a"], target["priority_b"]) if target else None

    report(
        "Jadwal: Tabrakan slot identik 10:00-12:00 mempertahankan pasangan asli dan menolak (1, 1) palsu",
        target is not None and target_pair in {(1, 3), (3, 1)} and target_pair != (1, 1),
        f"Target pair: {target_pair}"
    )

    # 7.7 Perlindungan floor minimal 60 menit (pemanggil tidak bisa menurunkan di bawah 60)
    w_45a = [{"date": "2026-11-20", "start_time": "10:00", "end_time": "10:45"}]
    w_45b = [{"date": "2026-11-20", "start_time": "10:00", "end_time": "11:00"}]
    common_floor = find_common_schedule(w_45a, w_45b, min_duration=30)  # Coba request 30 menit
    report("Jadwal: Floor 60 menit melindungi pemanggilan dengan min_duration=30", len(common_floor) == 0)

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"TEST RESULT SUMMARY: {passed_count}/{total_count} TESTS PASSED (100% SUCCESS)")
    print("=" * 70)
    assert passed_count == total_count, "Some tests failed!"


if __name__ == "__main__":
    run_tests()
