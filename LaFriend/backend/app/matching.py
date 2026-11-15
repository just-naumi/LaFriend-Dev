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
# 9. run_matching_pipeline: Orchestrator pencocokan end-to-end Session-First (Day 16)
# ==============================================================================

import re
import math
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Union, Sequence, Mapping
from sqlalchemy.orm import Session
from app.models import StudyIntent, IntentAvailability, StudySession, SessionSlot, SessionMember, Student, MatchResult, Course
from app.scoring import (
    calculate_session_score,
    calculate_partner_score,
    rank_session_candidates,
    rank_partner_candidates,
    format_match_result_payload,
    generate_match_explanation,
)
from app.schemas import MatchResultCreate


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
    """Mengubah format jam 'HH:MM' (wajib 2 digit jam dan 2 digit menit) menjadi total menit dari tengah malam."""
    clean = (time_str or "").strip()
    match = re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", clean)
    if not match:
        raise ValueError(f"Format waktu '{time_str}' tidak valid, gunakan format 2-digit HH:MM (contoh: 09:00 atau 14:00)")
    h, m = int(match.group(1)), int(match.group(2))
    return h * 60 + m


def format_time_minutes(minutes: int) -> str:
    """Mengubah total menit dari tengah malam kembali ke format 'HH:MM'."""
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def priority_pair_key(priority_a: int, priority_b: int) -> Tuple[int, int, int, int]:
    """
    Kriteria pemilihan pasangan prioritas jadwal terbaik secara holistik (bukan independen):
    1. Minimalkan nilai prioritas terburuk (minimax: max(prio_a, prio_b)).
    2. Minimalkan total prioritas (prio_a + prio_b).
    3. Pemecah seri prioritas A, lalu prioritas B.
    Peringkat angka lebih kecil = prioritas lebih tinggi (1 = Utama, 2 = Cadangan, 3 = Fleksibel).
    """
    return (
        max(priority_a, priority_b),
        priority_a + priority_b,
        priority_a,
        priority_b,
    )


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
    - Irisan minimal harus >= 60 menit (aturan produk non-negotiable floor: max(60, min_duration)).
    - Jika terdapat beberapa kombinasi slot pada tanggal & jam yang sama, pertahankan prioritas terbaik (nilai numerik terkecil).
    """
    effective_min_duration = max(60, int(min_duration))
    slots_by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for wa in windows_a:
        for wb in windows_b:
            # Wajib pada tanggal kalender yang persis sama
            if wa["date"] != wb["date"]:
                continue

            duration, overlap_start, overlap_end = calculate_overlap_minutes(
                wa["start_time"], wa["end_time"],
                wb["start_time"], wb["end_time"]
            )

            if duration >= effective_min_duration and overlap_start and overlap_end:
                slot_key = (wa["date"], overlap_start, overlap_end)
                prio_a = wa.get("priority", 1) or 1
                prio_b = wb.get("priority", 1) or 1

                if slot_key not in slots_by_key:
                    slots_by_key[slot_key] = {
                        "date": wa["date"],
                        "start_time": overlap_start,
                        "end_time": overlap_end,
                        "duration_minutes": duration,
                        "priority_a": prio_a,
                        "priority_b": prio_b
                    }
                else:
                    # Pertahankan pasangan prioritas asli terbaik secara utuh (holistik, bukan independen)
                    old_pair = (
                        slots_by_key[slot_key]["priority_a"],
                        slots_by_key[slot_key]["priority_b"]
                    )
                    new_pair = (prio_a, prio_b)
                    if priority_pair_key(*new_pair) < priority_pair_key(*old_pair):
                        slots_by_key[slot_key]["priority_a"] = prio_a
                        slots_by_key[slot_key]["priority_b"] = prio_b

    return list(slots_by_key.values())


# ==============================================================================
# 4. KOMPATIBILITAS MODE BELAJAR (is_learning_mode_compatible)
# ==============================================================================
VALID_LEARNING_MODES = {"ONLINE", "OFFLINE", "HYBRID"}

def is_learning_mode_compatible(mode1: str, mode2: str) -> Tuple[bool, Optional[str]]:
    """
    Memeriksa kompatibilitas mode belajar:
    - Whitelist ketat: ONLINE, OFFLINE, HYBRID. Mode di luar whitelist ditolak.
    - ONLINE + ONLINE -> (True, 'ONLINE')
    - OFFLINE + OFFLINE -> (True, 'OFFLINE')
    - HYBRID + apa pun yang valid -> (True, mode spesifik / 'HYBRID')
    - ONLINE + OFFLINE -> (False, None)
    """
    m1 = (mode1 or "").strip().upper()
    m2 = (mode2 or "").strip().upper()

    if m1 not in VALID_LEARNING_MODES or m2 not in VALID_LEARNING_MODES:
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
    Memeriksa apakah rentang kapasitas kelompok kedua intent valid [2..10] dan saling beririsan.
    Rumus: max(min1, min2) <= min(max1, max2)
    """
    try:
        n_min1, n_max1 = int(min1), int(max1)
        n_min2, n_max2 = int(min2), int(max2)
    except (ValueError, TypeError):
        return False

    # Validasi integritas masing-masing rentang kapasitas
    if not (2 <= n_min1 <= n_max1 <= 10):
        return False
    if not (2 <= n_min2 <= n_max2 <= 10):
        return False

    effective_min = max(n_min1, n_min2)
    effective_max = min(n_max1, n_max2)
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

        effective_min_duration = max(60, int(min_duration))
        common_schedule = find_common_schedule(intent_windows, session_windows, min_duration=effective_min_duration)
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
    8. Deduplikasi intent kandidat yang identik berdasarkan intent_id (seluruh intent berbeda dari mahasiswa yang sama lolos agar dapat dinilai di Day 15.5 dan dideduplikasi di Day 15.6)

    Mengembalikan daftar pasangan: [(StudyIntent, common_slots), ...]
    """
    if not intent or not getattr(intent, "course_id", None):
        return []

    intent_windows = resolve_availability_windows(intent)
    if not intent_windows:
        return []

    effective_min_duration = max(60, int(min_duration))
    qualified_partners: List[Tuple[StudyIntent, List[Dict[str, Any]]]] = []
    seen_intent_ids = set()

    for candidate in candidate_intents:
        # Constraint 1: Status intent kandidat harus ACTIVE
        if (candidate.status or "").upper() != "ACTIVE":
            continue

        # Constraint 2: Tidak boleh merekomendasikan diri sendiri (bahkan dengan intent_id berbeda)
        if candidate.student_id == intent.student_id:
            continue

        # Constraint 2b: Deduplikasi intent kandidat yang identik (berdasarkan intent_id / id)
        cand_id = getattr(candidate, "intent_id", None) or getattr(candidate, "id", None)
        if cand_id and cand_id in seen_intent_ids:
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

        common_schedule = find_common_schedule(intent_windows, candidate_windows, min_duration=effective_min_duration)
        if not common_schedule:
            continue

        if cand_id:
            seen_intent_ids.add(cand_id)
        qualified_partners.append((candidate, common_schedule))

    return qualified_partners


# ==============================================================================
# 9. MATCHING PIPELINE ORCHESTRATOR (Day 16)
# ==============================================================================
def run_matching_pipeline(
    intent: Union[str, StudyIntent],
    db: Optional[Session] = None,
    min_score: float = 60.0,
    limit: Optional[int] = 5,
    persist: bool = True,
) -> Dict[str, Any]:
    """
    Mengorkestrasi seluruh alur pencocokan Day 14 (Hard Constraint Filtering),
    Day 15 (Compatibility Scoring, Ranking, Deduplication, Explanation), dan Day 13 (Persistensi DB).

    Prinsip Utama:
    1. Session-First Architecture: Selalu mengevaluasi StudySession terlebih dahulu.
       Jika ditemukan sesi yang memenuhi kriteria min_score, maka rekomendasi sesi
       dikembalikan dan pencarian rekan (Partner Matching) sama sekali TIDAK dijalankan.
    2. Fallback to Partner Matching: Jika tidak ada sesi belajar yang lolos hard constraint
       atau tidak ada sesi yang mencapai batas min_score, maka otomatis mengevaluasi
       kandidat StudyIntent (Partner Matching) dengan deduplikasi per mahasiswa.
    3. Persistensi Atomik: Menyimpan seluruh kandidat terpilih ke tabel MatchResult di database
       dengan breakdown JSON yang tervalidasi skema Pydantic MatchResultCreate.
    4. Validasi Keamanan & Integritas: Memastikan status intent ACTIVE, akun mahasiswa
       terverifikasi dan tidak ditangguhkan, serta batas min_score dan limit numerik valid.
    """
    if intent is None:
        raise ValueError("Parameter intent tidak boleh None")

    # 1. Resolusi objek StudyIntent
    if isinstance(intent, str):
        intent_id_str = intent.strip()
        if not intent_id_str:
            raise ValueError("intent_id tidak boleh berupa string kosong")
        if db is None:
            raise ValueError("Database session (db) wajib disertakan saat mencari Study Intent berdasarkan ID")
        study_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == intent_id_str).first()
        if not study_intent:
            raise ValueError(f"Study Intent dengan ID '{intent_id_str}' tidak ditemukan")
    else:
        study_intent = intent

    # 2. Validasi status intent
    status_str = (getattr(study_intent, "status", "") or "").upper()
    if status_str != "ACTIVE":
        raise ValueError(f"Hanya Study Intent berstatus ACTIVE yang dapat dicocokkan (status saat ini: {status_str})")

    # 3. Validasi profil mahasiswa pembuat intent
    student = getattr(study_intent, "student", None)
    if student:
        acc_status = (getattr(student, "account_status", "") or "").upper()
        if acc_status and acc_status != "ACTIVE":
            raise ValueError(f"Akun mahasiswa pembuat intent sedang tidak aktif (status: {acc_status})")
        ver_status = (getattr(student, "verification_status", "") or "").upper()
        if ver_status and ver_status != "VERIFIED":
            raise ValueError(f"Akun mahasiswa pembuat intent belum terverifikasi (status: {ver_status})")

    # 4. Validasi min_score numerik non-boolean finite [0.0, 100.0]
    if min_score is None or isinstance(min_score, bool):
        raise ValueError("min_score harus berupa angka berhingga non-boolean")
    try:
        min_score_val = float(min_score)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("min_score harus berupa angka numerik valid")
    if math.isnan(min_score_val) or math.isinf(min_score_val):
        raise ValueError("min_score harus berupa angka berhingga (finite)")
    if not (0.0 <= min_score_val <= 100.0):
        raise ValueError(f"min_score ({min_score_val}) harus berada dalam rentang [0.0, 100.0]")

    # 5. Validasi limit positif integer non-boolean atau None
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit harus berupa integer positif atau None")
        if limit < 1:
            raise ValueError(f"limit ({limit}) harus bernilai minimal 1")

    # 6. Validasi course_id
    course_id = getattr(study_intent, "course_id", None)
    if not course_id:
        raise ValueError("Study Intent harus memiliki course_id yang valid")

    # 7. Validasi ketersediaan jadwal pencari
    intent_windows = resolve_availability_windows(study_intent)
    if not intent_windows:
        if persist and db is not None and getattr(study_intent, "intent_id", None):
            try:
                db.query(MatchResult).filter(MatchResult.intent_id == str(study_intent.intent_id)).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
                raise
        c_name = study_intent.course.course_name if getattr(study_intent, "course", None) else None
        return {
            "intent_id": str(getattr(study_intent, "intent_id", "")),
            "course_id": str(course_id),
            "course_name": c_name,
            "match_type": "NONE",
            "total_candidates": 0,
            "recommendations": [],
            "message": "Study Intent tidak memiliki jadwal ketersediaan yang valid."
        }

    # ==========================================================================
    # TAHAP 1: SESSION-FIRST MATCHING
    # ==========================================================================
    candidate_sessions = []
    if db is not None:
        candidate_sessions = (
            db.query(StudySession)
            .filter(
                StudySession.course_id == course_id,
                StudySession.status == "OPEN",
                StudySession.host_id != study_intent.student_id
            )
            .all()
        )

    qualified_sessions = filter_candidate_sessions(study_intent, candidate_sessions, min_duration=60)
    session_scores = []
    sessions_by_id = {}

    for session, common_slots in qualified_sessions:
        s_id = str(getattr(session, "session_id", None) or getattr(session, "id", None))
        sessions_by_id[s_id] = session
        score_dict = calculate_session_score(study_intent, session, common_slots)
        session_scores.append(score_dict)

    ranked_sessions = rank_session_candidates(
        session_scores,
        min_score=min_score_val,
        limit=limit
    )

    if ranked_sessions:
        # SESI DITEMUKAN: Prinsip Session-First terpenuhi, Partner Matching dilewati
        match_type = "SESSION"
        ranked_candidates = ranked_sessions
    else:
        # ======================================================================
        # TAHAP 2: FALLBACK TO PARTNER MATCHING
        # ======================================================================
        candidate_intents = []
        if db is not None:
            candidate_intents = (
                db.query(StudyIntent)
                .join(StudyIntent.student)
                .filter(
                    StudyIntent.course_id == course_id,
                    StudyIntent.status == "ACTIVE",
                    StudyIntent.student_id != study_intent.student_id,
                    Student.account_status == "ACTIVE",
                    Student.verification_status == "VERIFIED",
                    Student.is_discoverable == True
                )
                .all()
            )

        qualified_partners = filter_candidate_partners(study_intent, candidate_intents, min_duration=60)
        partner_scores = []
        partners_by_intent_id = {}

        for cand_intent, common_slots in qualified_partners:
            p_id = str(getattr(cand_intent, "intent_id", None) or getattr(cand_intent, "id", None))
            partners_by_intent_id[p_id] = cand_intent
            score_dict = calculate_partner_score(study_intent, cand_intent, common_slots)
            partner_scores.append(score_dict)

        ranked_partners = rank_partner_candidates(
            partner_scores,
            min_score=min_score_val,
            limit=limit
        )

        if ranked_partners:
            match_type = "PARTNER"
            ranked_candidates = ranked_partners
        else:
            match_type = "NONE"
            ranked_candidates = []

    # ==========================================================================
    # TAHAP 3: FORMAT PAYLOAD, DETAIL ENRICHMENT & PERSISTENSI
    # ==========================================================================
    formatted_recommendations = []

    if persist and db is not None and getattr(study_intent, "intent_id", None):
        try:
            # 1. Hapus rekaman rekomendasi lama dalam transaksi aman
            db.query(MatchResult).filter(MatchResult.intent_id == str(study_intent.intent_id)).delete(synchronize_session=False)

            # 2. Validasi seluruh kandidat, buat MatchResult, dan susun payload
            for item in ranked_candidates:
                payload = format_match_result_payload(item)
                validated_payload = MatchResultCreate.model_validate(payload)

                match_id = str(uuid.uuid4())
                sched = item.get("selected_schedule")
                sched_json = json.dumps(sched) if sched else None

                match_record = MatchResult(
                    match_id=match_id,
                    intent_id=validated_payload.intent_id,
                    candidate_type=validated_payload.candidate_type,
                    candidate_session_id=validated_payload.candidate_session_id,
                    target_intent_id=validated_payload.target_intent_id,
                    compatibility_score=validated_payload.compatibility_score,
                    breakdown_json=json.dumps(validated_payload.breakdown.model_dump()),
                    explanation=validated_payload.explanation,
                    selected_schedule_json=sched_json,
                    created_at=datetime.utcnow()
                )
                db.add(match_record)

                rec_item = {
                    "match_id": match_id,
                    "rank": item.get("rank", 1),
                    "candidate_type": validated_payload.candidate_type,
                    "candidate_session_id": validated_payload.candidate_session_id,
                    "target_intent_id": validated_payload.target_intent_id,
                    "compatibility_score": validated_payload.compatibility_score,
                    "breakdown": validated_payload.breakdown.model_dump(),
                    "explanation": validated_payload.explanation,
                    "selected_schedule": item.get("selected_schedule"),
                    "session_details": None,
                    "partner_details": None,
                }

                if validated_payload.candidate_type == "SESSION":
                    sess = sessions_by_id.get(validated_payload.candidate_session_id)
                    if sess:
                        occupied = calculate_session_occupied_capacity(sess)
                        host_name = sess.host.full_name if getattr(sess, "host", None) else None
                        course_title = sess.course.course_name if getattr(sess, "course", None) else None
                        rec_item["session_details"] = {
                            "session_id": sess.session_id,
                            "title": sess.title,
                            "description": sess.description,
                            "host_id": sess.host_id,
                            "host_name": host_name,
                            "course_id": sess.course_id,
                            "course_name": course_title,
                            "learning_goal": sess.learning_goal,
                            "collaboration_style": sess.collaboration_style,
                            "learning_mode": sess.learning_mode,
                            "location": sess.location,
                            "occupied_seats": occupied,
                            "max_group_size": sess.max_group_size,
                        }
                elif validated_payload.candidate_type == "PARTNER":
                    part = partners_by_intent_id.get(validated_payload.target_intent_id)
                    if part:
                        st = getattr(part, "student", None)
                        rec_item["partner_details"] = {
                            "target_intent_id": part.intent_id,
                            "student_id": part.student_id,
                            "student_name": st.full_name if st else None,
                            "study_program": st.study_program if st else None,
                            "academic_year": st.academic_year if st else None,
                            "topics": part.topics,
                            "learning_goal": part.learning_goal,
                            "collaboration_style": part.collaboration_style,
                            "learning_mode": part.learning_mode,
                            "min_group_size": part.min_group_size,
                            "max_group_size": part.max_group_size,
                        }

                formatted_recommendations.append(rec_item)

            # 3. Commit transaksi secara atomik hanya setelah SELURUH proses validasi & staging berhasil
            db.commit()
        except Exception:
            db.rollback()
            raise
    else:
        # Jalur non-persistensi (persist=False atau db is None)
        for item in ranked_candidates:
            payload = format_match_result_payload(item)
            validated_payload = MatchResultCreate.model_validate(payload)
            match_id = str(uuid.uuid4())

            rec_item = {
                "match_id": match_id,
                "rank": item.get("rank", 1),
                "candidate_type": validated_payload.candidate_type,
                "candidate_session_id": validated_payload.candidate_session_id,
                "target_intent_id": validated_payload.target_intent_id,
                "compatibility_score": validated_payload.compatibility_score,
                "breakdown": validated_payload.breakdown.model_dump(),
                "explanation": validated_payload.explanation,
                "selected_schedule": item.get("selected_schedule"),
                "session_details": None,
                "partner_details": None,
            }

            if validated_payload.candidate_type == "SESSION":
                sess = sessions_by_id.get(validated_payload.candidate_session_id)
                if sess:
                    occupied = calculate_session_occupied_capacity(sess)
                    host_name = sess.host.full_name if getattr(sess, "host", None) else None
                    course_title = sess.course.course_name if getattr(sess, "course", None) else None
                    rec_item["session_details"] = {
                        "session_id": sess.session_id,
                        "title": sess.title,
                        "description": sess.description,
                        "host_id": sess.host_id,
                        "host_name": host_name,
                        "course_id": sess.course_id,
                        "course_name": course_title,
                        "learning_goal": sess.learning_goal,
                        "collaboration_style": sess.collaboration_style,
                        "learning_mode": sess.learning_mode,
                        "location": sess.location,
                        "occupied_seats": occupied,
                        "max_group_size": sess.max_group_size,
                    }
            elif validated_payload.candidate_type == "PARTNER":
                part = partners_by_intent_id.get(validated_payload.target_intent_id)
                if part:
                    st = getattr(part, "student", None)
                    rec_item["partner_details"] = {
                        "target_intent_id": part.intent_id,
                        "student_id": part.student_id,
                        "student_name": st.full_name if st else None,
                        "study_program": st.study_program if st else None,
                        "academic_year": st.academic_year if st else None,
                        "topics": part.topics,
                        "learning_goal": part.learning_goal,
                        "collaboration_style": part.collaboration_style,
                        "learning_mode": part.learning_mode,
                        "min_group_size": part.min_group_size,
                        "max_group_size": part.max_group_size,
                    }

            formatted_recommendations.append(rec_item)

    if match_type == "SESSION":
        msg = f"Ditemukan {len(formatted_recommendations)} rekomendasi Study Session yang cocok untuk dipelajari bersama."
    elif match_type == "PARTNER":
        msg = f"Tidak ada sesi aktif yang cocok. Menampilkan {len(formatted_recommendations)} rekomendasi rekan belajar (Partner) sebagai alternatif."
    else:
        msg = "Belum ditemukan sesi belajar maupun rekan belajar yang memenuhi kriteria untuk Study Intent ini."

    course_name = study_intent.course.course_name if getattr(study_intent, "course", None) else None

    return {
        "intent_id": str(getattr(study_intent, "intent_id", "")),
        "course_id": str(course_id),
        "course_name": course_name,
        "match_type": match_type,
        "total_candidates": len(formatted_recommendations),
        "recommendations": formatted_recommendations,
        "message": msg,
    }

