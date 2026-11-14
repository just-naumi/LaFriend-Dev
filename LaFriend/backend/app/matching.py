# ==============================================================================
# matching.py - Mesin Hard Constraint Filtering (Day 14)
# ==============================================================================
# Modul ini bertugas menyaring kandidat sebelum masuk ke Compatibility Score (Day 15).
# Prinsip: Jangan memberi skor kepada kandidat yang tidak memenuhi syarat dasar.
#
# Fungsi Utama:
# 1. resolve_availability_windows: Normalisasi jadwal ke tanggal riil YYYY-MM-DD
# 2. calculate_overlap_minutes: Hitung irisan waktu dalam menit
# 3. find_common_schedule: Temukan tanggal dan jam ketersediaan bersama
# 4. is_learning_mode_compatible: Cek kompatibilitas Online / Offline / Hybrid
# 5. is_group_capacity_compatible: Cek irisan rentang ukuran kelompok
# 6. calculate_session_occupied_capacity: Hitung keterisian kursi sesi tanpa duplikasi
# 7. filter_candidate_sessions: Hard constraint filter untuk Session Matching
# 8. filter_candidate_partners: Hard constraint filter untuk Partner Matching
# ==============================================================================

import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from app.models import StudyIntent, IntentAvailability, StudySession, SessionSlot, SessionMember, Student


# Pemetaan nama hari bahasa Indonesia & Inggris ke indeks hari (0 = Senin, 6 = Minggu)
DAY_NAME_TO_WEEKDAY = {
    "senin": 0, "monday": 0,
    "selasa": 1, "tuesday": 1,
    "rabu": 2, "wednesday": 2,
    "kamis": 3, "thursday": 3,
    "jumat": 4, "jum'at": 4, "friday": 4,
    "sabtu": 5, "saturday": 5,
    "minggu": 6, "ahad": 6, "sunday": 6
}


def parse_time_minutes(time_str: str) -> int:
    """Mengubah format jam 'HH:MM' menjadi total menit dari tengah malam."""
    clean = (time_str or "").strip()
    match = re.match(r"^(\d{1,2}):(\d{2})$", clean)
    if not match:
        raise ValueError(f"Format waktu '{time_str}' tidak valid, gunakan format HH:MM")
    h, m = int(match.group(1)), int(match.group(2))
    return h * 60 + m


def format_time_minutes(minutes: int) -> str:
    """Mengubah total menit dari tengah malam kembali ke format 'HH:MM'."""
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


# ==============================================================================
# 1. NORMALISASI JADWAL KE TANGGAL RIIL (resolve_availability_windows)
# ==============================================================================
def resolve_availability_windows(intent: StudyIntent) -> List[Dict[str, Any]]:
    """
    Mengubah seluruh ketersediaan jadwal intent menjadi daftar jendela waktu kalender riil:
    [{"date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM", "priority": int}, ...]

    Aturan Day 14:
    - Seluruh tanggal riil yang jatuh dalam rentang [earliest_date, latest_date] diekspansi.
    - Jika pilihan adalah "Senin" dan rentang mencakup 3 hari Senin, ketiganya dikembalikan.
    - Jika slot berupa tanggal spesifik YYYY-MM-DD di luar rentang, slot tersebut ditolak.
    - Jika rentang tanggal tidak valid, mengembalikan list kosong (tanpa tanggal palsu).
    """
    if not intent or not getattr(intent, "earliest_date", None) or not getattr(intent, "latest_date", None):
        return []

    try:
        start_dt = datetime.strptime(intent.earliest_date.strip(), "%Y-%m-%d").date()
        end_dt = datetime.strptime(intent.latest_date.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return []

    if start_dt > end_dt:
        return []

    resolved_windows: List[Dict[str, Any]] = []
    availabilities = getattr(intent, "availabilities", []) or []

    for slot in availabilities:
        day_raw = (slot.day_or_date or "").strip()
        start_time = (slot.start_time or "").strip()
        end_time = (slot.end_time or "").strip()
        priority = getattr(slot, "priority_rank", 1) or 1

        if not day_raw or not start_time or not end_time:
            continue

        # Kasus A: day_or_date sudah berupa tanggal spesifik (YYYY-MM-DD)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", day_raw):
            try:
                specific_date = datetime.strptime(day_raw, "%Y-%m-%d").date()
                # Tanggal spesifik di luar rentang intent ditolak
                if start_dt <= specific_date <= end_dt:
                    resolved_windows.append({
                        "date": day_raw,
                        "start_time": start_time,
                        "end_time": end_time,
                        "priority": priority
                    })
            except ValueError:
                continue

        # Kasus B: day_or_date berupa nama hari (misal "Senin", "Rabu")
        else:
            day_clean = day_raw.lower()
            target_weekday = DAY_NAME_TO_WEEKDAY.get(day_clean)
            if target_weekday is None:
                continue

            # Iterasi seluruh tanggal kalender dalam rentang [start_dt, end_dt]
            curr_date = start_dt
            while curr_date <= end_dt:
                if curr_date.weekday() == target_weekday:
                    resolved_windows.append({
                        "date": curr_date.strftime("%Y-%m-%d"),
                        "start_time": start_time,
                        "end_time": end_time,
                        "priority": priority
                    })
                curr_date += timedelta(days=1)

    return resolved_windows


# ==============================================================================
# 2. PENGHITUNGAN IRISAN WAKTU (calculate_overlap_minutes)
# ==============================================================================
def calculate_overlap_minutes(start_a: str, end_a: str, start_b: str, end_b: str) -> Tuple[int, Optional[str], Optional[str]]:
    """
    Menghitung durasi irisan waktu dalam menit antara dua interval pada tanggal yang sama.
    Rumus: Overlap = max(0, min(E_a, E_b) - max(S_a, S_b))
    Batas waktu bersinggungan (misal 10:00-11:00 & 11:00-12:00) menghasilkan 0 menit.
    Mengembalikan: (durasi_menit, waktu_mulai_irisan, waktu_selesai_irisan)
    """
    try:
        sa_min = parse_time_minutes(start_a)
        ea_min = parse_time_minutes(end_a)
        sb_min = parse_time_minutes(start_b)
        eb_min = parse_time_minutes(end_b)
    except ValueError:
        return 0, None, None

    # Penanganan jadwal tidak valid atau melewati tengah malam (end <= start)
    if sa_min >= ea_min or sb_min >= eb_min:
        return 0, None, None

    overlap_start = max(sa_min, sb_min)
    overlap_end = min(ea_min, eb_min)
    overlap_duration = max(0, overlap_end - overlap_start)

    if overlap_duration > 0:
        return overlap_duration, format_time_minutes(overlap_start), format_time_minutes(overlap_end)
    return 0, None, None


# ==============================================================================
# 3. PENCARIAN JADWAL BERSAMA (find_common_schedule)
# ==============================================================================
def find_common_schedule(windows_a: List[Dict[str, Any]], windows_b: List[Dict[str, Any]], min_duration: int = 60) -> List[Dict[str, Any]]:
    """
    Membandingkan dua daftar jendela ketersediaan dan mencari slot irisan dengan durasi >= min_duration menit.
    Aturan Day 14:
    - Jadwal dibandingkan strictly per tanggal kalender yang sama.
    - Irisan minimal harus >= 60 menit.
    - Slot identik pada tanggal dan jam yang sama di-deduplikasi otomatis.
    """
    common_slots: List[Dict[str, Any]] = []
    seen_slots = set()

    for wa in windows_a:
        for wb in windows_b:
            # Wajib pada tanggal kalender yang persis sama
            if wa["date"] != wb["date"]:
                continue

            duration, overlap_start, overlap_end = calculate_overlap_minutes(
                wa["start_time"], wa["end_time"],
                wb["start_time"], wb["end_time"]
            )

            if duration >= min_duration and overlap_start and overlap_end:
                slot_key = (wa["date"], overlap_start, overlap_end)
                if slot_key not in seen_slots:
                    seen_slots.add(slot_key)
                    common_slots.append({
                        "date": wa["date"],
                        "start_time": overlap_start,
                        "end_time": overlap_end,
                        "duration_minutes": duration,
                        "priority_a": wa.get("priority", 1),
                        "priority_b": wb.get("priority", 1)
                    })

    return common_slots


# ==============================================================================
# 4. KOMPATIBILITAS MODE BELAJAR (is_learning_mode_compatible)
# ==============================================================================
def is_learning_mode_compatible(mode1: str, mode2: str) -> Tuple[bool, Optional[str]]:
    """
    Memeriksa kompatibilitas mode belajar:
    - ONLINE + ONLINE -> (True, 'ONLINE')
    - OFFLINE + OFFLINE -> (True, 'OFFLINE')
    - HYBRID + apa pun -> (True, mode spesifik / 'HYBRID')
    - ONLINE + OFFLINE -> (False, None)
    """
    m1 = (mode1 or "").strip().upper()
    m2 = (mode2 or "").strip().upper()

    if not m1 or not m2:
        return False, None

    if m1 == m2:
        return True, m1

    if m1 == "HYBRID":
        return True, m2
    if m2 == "HYBRID":
        return True, m1

    # ONLINE vs OFFLINE tidak kompatibel
    return False, None


# ==============================================================================
# 5. KELAYAKAN UKURAN KELOMPOK (is_group_capacity_compatible)
# ==============================================================================
def is_group_capacity_compatible(min1: int, max1: int, min2: int, max2: int) -> bool:
    """
    Memeriksa apakah rentang kapasitas kelompok kedua intent beririsan dan dalam batas wajar [2..10].
    Rumus: max(min1, min2) <= min(max1, max2)
    """
    effective_min = max(int(min1), int(min2))
    effective_max = min(int(max1), int(max2))
    if effective_min < 2 or effective_max > 10:
        return False
    return effective_min <= effective_max


# ==============================================================================
# 6. PENGHITUNGAN KETERISIAN KURSI SESI (calculate_session_occupied_capacity)
# ==============================================================================
def calculate_session_occupied_capacity(session: StudySession) -> int:
    """
    Menghitung jumlah mahasiswa unik yang saat ini mengisi kuota sesi belajar:
    - Host selalu dihitung 1 kursi.
    - Anggota dengan status ACCEPTED dan CONFIRMED dihitung.
    - Host tidak dihitung dua kali meskipun ada di daftar SessionMember.
    - Anggota dengan status INVITED, DECLINED, WITHDRAWN, REMOVED tidak memakan kuota.
    """
    occupied_student_ids = set()

    # Masukkan host
    if getattr(session, "host_id", None):
        occupied_student_ids.add(session.host_id)

    # Masukkan anggota aktif
    members = getattr(session, "members", []) or []
    for member in members:
        mem_status = (getattr(member, "status", "") or "").upper()
        if mem_status in {"ACCEPTED", "CONFIRMED"}:
            if getattr(member, "student_id", None):
                occupied_student_ids.add(member.student_id)

    return len(occupied_student_ids)


# ==============================================================================
# 7. HARD CONSTRAINT FILTER: SESSION MATCHING (filter_candidate_sessions)
# ==============================================================================
def filter_candidate_sessions(
    intent: StudyIntent,
    sessions: List[StudySession],
    min_duration: int = 60
) -> List[Tuple[StudySession, List[Dict[str, Any]]]]:
    """
    Menyaring sesi belajar yang memenuhi seluruh hard constraints:
    1. Status sesi wajib OPEN
    2. Mata kuliah harus sama persis (session.course_id == intent.course_id)
    3. Bukan sesi milik sendiri (session.host_id != intent.student_id)
    4. Mahasiswa belum menjadi anggota aktif di sesi tersebut
    5. Kapasitas sesi masih tersedia (occupied < max_group_size)
    6. Mode belajar kompatibel (ONLINE, OFFLINE, HYBRID)
    7. Memiliki irisan jadwal bersama >= min_duration menit pada slot APPROVED

    Mengembalikan daftar pasangan: [(StudySession, common_slots), ...]
    """
    if not intent or not getattr(intent, "course_id", None):
        return []

    # Normalisasi ketersediaan intent pencari
    intent_windows = resolve_availability_windows(intent)
    if not intent_windows:
        return []

    qualified_sessions: List[Tuple[StudySession, List[Dict[str, Any]]]] = []

    for session in sessions:
        # Constraint 1: Status sesi harus OPEN
        if (session.status or "").upper() != "OPEN":
            continue

        # Constraint 2: Mata kuliah harus sama
        if session.course_id != intent.course_id:
            continue

        # Constraint 3: Tidak boleh merekomendasikan sesi milik sendiri
        if session.host_id == intent.student_id:
            continue

        # Constraint 4: Mahasiswa belum menjadi anggota sesi
        is_already_member = False
        for member in (getattr(session, "members", []) or []):
            if member.student_id == intent.student_id:
                mem_status = (member.status or "").upper()
                if mem_status in {"HOST", "ACCEPTED", "CONFIRMED", "INVITED"}:
                    is_already_member = True
                    break
        if is_already_member:
            continue

        # Constraint 5: Kapasitas masih tersedia
        occupied = calculate_session_occupied_capacity(session)
        if occupied >= session.max_group_size:
            continue

        # Constraint 6: Mode belajar kompatibel
        mode_compat, _ = is_learning_mode_compatible(session.learning_mode, intent.learning_mode)
        if not mode_compat:
            continue

        # Constraint 7: Jadwal beririsan >= min_duration pada slot APPROVED
        approved_slots = [
            s for s in (getattr(session, "slots", []) or [])
            if (getattr(s, "status", "") or "").upper() == "APPROVED"
        ]
        if not approved_slots:
            continue

        session_windows = [
            {
                "date": s.session_date,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "priority": 1
            }
            for s in approved_slots
            if getattr(s, "session_date", None) and getattr(s, "start_time", None) and getattr(s, "end_time", None)
        ]

        common_schedule = find_common_schedule(intent_windows, session_windows, min_duration=min_duration)
        if not common_schedule:
            continue

        qualified_sessions.append((session, common_schedule))

    return qualified_sessions


# ==============================================================================
# 8. HARD CONSTRAINT FILTER: PARTNER MATCHING (filter_candidate_partners)
# ==============================================================================
def filter_candidate_partners(
    intent: StudyIntent,
    candidate_intents: List[StudyIntent],
    min_duration: int = 60
) -> List[Tuple[StudyIntent, List[Dict[str, Any]]]]:
    """
    Menyaring calon rekan belajar yang memenuhi seluruh hard constraints:
    1. Status intent kandidat wajib ACTIVE
    2. Bukan intent milik sendiri (candidate.student_id != intent.student_id)
    3. Akun kandidat wajib ACTIVE, VERIFIED, dan is_discoverable == True
    4. Mata kuliah harus sama persis (candidate.course_id == intent.course_id)
    5. Mode belajar kompatibel
    6. Rentang kapasitas kelompok beririsan
    7. Memiliki irisan ketersediaan waktu bersama >= min_duration menit

    Mengembalikan daftar pasangan: [(StudyIntent, common_slots), ...]
    """
    if not intent or not getattr(intent, "course_id", None):
        return []

    intent_windows = resolve_availability_windows(intent)
    if not intent_windows:
        return []

    qualified_partners: List[Tuple[StudyIntent, List[Dict[str, Any]]]] = []

    for candidate in candidate_intents:
        # Constraint 1: Status intent kandidat harus ACTIVE
        if (candidate.status or "").upper() != "ACTIVE":
            continue

        # Constraint 2: Tidak boleh merekomendasikan diri sendiri (bahkan dengan intent_id berbeda)
        if candidate.student_id == intent.student_id:
            continue

        # Constraint 3: Profil mahasiswa kandidat harus valid
        cand_student = getattr(candidate, "student", None)
        if not cand_student:
            continue
        if (cand_student.account_status or "").upper() != "ACTIVE":
            continue
        if not getattr(cand_student, "is_discoverable", False):
            continue
        if (getattr(cand_student, "verification_status", "") or "").upper() != "VERIFIED":
            continue

        # Constraint 4: Mata kuliah harus sama
        if candidate.course_id != intent.course_id:
            continue

        # Constraint 5: Mode belajar kompatibel
        mode_compat, _ = is_learning_mode_compatible(intent.learning_mode, candidate.learning_mode)
        if not mode_compat:
            continue

        # Constraint 6: Kapasitas kelompok beririsan
        intent_min = getattr(intent, "min_group_size", 2) or 2
        intent_max = getattr(intent, "max_group_size", 4) or 4
        cand_min = getattr(candidate, "min_group_size", 2) or 2
        cand_max = getattr(candidate, "max_group_size", 4) or 4
        if not is_group_capacity_compatible(intent_min, intent_max, cand_min, cand_max):
            continue

        # Constraint 7: Jadwal beririsan >= min_duration menit
        candidate_windows = resolve_availability_windows(candidate)
        if not candidate_windows:
            continue

        common_schedule = find_common_schedule(intent_windows, candidate_windows, min_duration=min_duration)
        if not common_schedule:
            continue

        qualified_partners.append((candidate, common_schedule))

    return qualified_partners
