# ==============================================================================
# group_formation.py - Engine Pembentukan Kelompok Belajar (Day 17)
# ==============================================================================
# Modul ini bertugas mengubah rekomendasi individual (Partner Matching)
# menjadi kelompok belajar terpadu yang memenuhi 3 pilar utama:
# 1. Kompatibilitas seluruh pasangan (Pairwise Compatibility & Min Score Threshold).
# 2. Irisan ketersediaan waktu bersama seluruh anggota (Group Availability Intersection >= 60 min).
# 3. Keselarasan batasan ukuran kelompok (Group Size Capacity Bounds: Max(Min) <= Min(Max)).
#
# Formula Kualitas Kelompok (Group Quality Score / GQ dari Day 7):
#   APS = sum(CS_ij) / N_pair
#   MPS = min(CS_ij)
#   GQ  = 0.70 * APS + 0.30 * MPS
#
# Seluruh komputasi bersifat READ-ONLY (Preview). Tidak ada mutasi atau penulisan
# ke tabel StudySession, SessionMember, SessionSlot, maupun Invitation pada Day 17.
# ==============================================================================

import math
import itertools
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple, Optional, Sequence, Union

from sqlalchemy.orm import Session

from app.models import Student, Course, StudyIntent, IntentAvailability
from app.matching import (
    resolve_availability_windows,
    calculate_overlap_minutes,
    parse_time_minutes,
    format_time_minutes,
    find_common_schedule,
    is_learning_mode_compatible
)
from app.scoring import calculate_partner_score, generate_match_explanation


# ==============================================================================
# 1. HELPER IRISAN JADWAL KELOMPOK (GROUP AVAILABILITY INTERSECTION)
# ==============================================================================
def intersect_two_window_lists(
    windows_a: Sequence[Dict[str, Any]],
    windows_b: Sequence[Dict[str, Any]],
    min_duration: int = 60
) -> List[Dict[str, Any]]:
    """
    Menghitung irisan waktu antara dua kumpulan jendela ketersediaan pada tanggal yang sama.
    Hanya interval dengan durasi >= max(60, min_duration) yang dipertahankan.
    """
    effective_min = max(60, int(min_duration))
    result: List[Dict[str, Any]] = []
    seen = set()

    for wa in windows_a:
        date_a = wa.get("date")
        if not date_a:
            continue
        for wb in windows_b:
            date_b = wb.get("date")
            if date_a != date_b:
                continue

            dur, s_str, e_str = calculate_overlap_minutes(
                wa["start_time"], wa["end_time"],
                wb["start_time"], wb["end_time"]
            )
            if dur >= effective_min and s_str and e_str:
                key = (date_a, s_str, e_str)
                if key not in seen:
                    seen.add(key)
                    result.append({
                        "date": date_a,
                        "start_time": s_str,
                        "end_time": e_str,
                        "duration_minutes": dur,
                    })

    return result


def find_group_common_schedules(
    member_windows_list: Sequence[Sequence[Dict[str, Any]]],
    min_duration: int = 60
) -> List[Dict[str, Any]]:
    """
    Mencari seluruh interval jadwal di mana SELURUH anggota kelompok tersedia
    secara bersamaan pada tanggal yang sama dengan durasi minimal 60 menit.

    Aturan:
    - Jadwal hanya dihitung untuk tanggal kalender yang sama persis.
    - Durasi harus >= 60 menit (aturan non-negotiable floor).
    - Interval dipersempit secara iteratif: Start_G = max(starts), End_G = min(ends).
    - Diurutkan menurun berdasarkan durasi terpanjang, lalu tanggal dan jam mulai lebih awal.
    """
    if not member_windows_list:
        return []

    effective_min = max(60, int(min_duration))

    # Jika hanya ada 1 anggota (misal host sendiri)
    if len(member_windows_list) == 1:
        valid_single = []
        for w in member_windows_list[0]:
            s_min = parse_time_minutes(w["start_time"])
            e_min = parse_time_minutes(w["end_time"])
            dur = e_min - s_min
            if dur >= effective_min:
                valid_single.append({
                    "date": w["date"],
                    "start_time": w["start_time"],
                    "end_time": w["end_time"],
                    "duration_minutes": dur
                })
        valid_single.sort(key=lambda s: (-s["duration_minutes"], s["date"], s["start_time"]))
        return valid_single

    # Iterasi perpotongan berantai untuk N >= 2
    common_intervals = list(member_windows_list[0])
    for member_windows in member_windows_list[1:]:
        common_intervals = intersect_two_window_lists(common_intervals, member_windows, min_duration=effective_min)
        if not common_intervals:
            return []

    # Pengurutan deterministik: durasi lebih panjang > tanggal lebih awal > jam lebih awal
    common_intervals.sort(key=lambda s: (-s["duration_minutes"], s["date"], s["start_time"]))
    return common_intervals


# ==============================================================================
# 2. HELPER BATASAN UKURAN KELOMPOK (GROUP CAPACITY BOUNDS)
# ==============================================================================
def calculate_group_size_bounds(intents: Sequence[Any]) -> Tuple[int, int]:
    """
    Menghitung batas kelompok bersama:
      MinGroup = max(min_group_size seluruh anggota)
      MaxGroup = min(max_group_size seluruh anggota)
    Kelompok kompatibel jika MinGroup <= MaxGroup.
    """
    if not intents:
        return 2, 4

    min_bound = max(int(getattr(i, "min_group_size", 2) or 2) for i in intents)
    max_bound = min(int(getattr(i, "max_group_size", 4) or 4) for i in intents)
    return min_bound, max_bound


# ==============================================================================
# 3. HELPER SKOR KUALITAS KELOMPOK (GROUP QUALITY SCORE / GQ)
# ==============================================================================
def calculate_group_quality_score(
    pairwise_scores: Sequence[Union[float, int, Decimal]]
) -> Tuple[float, float, float]:
    """
    Menghitung Group Quality Score (GQ) sesuai formula Day 7:
      APS = sum(CS_ij) / N_pair
      MPS = min(CS_ij)
      GQ  = 0.70 * APS + 0.30 * MPS

    Mengembalikan (GQ, APS, MPS) dalam float berpresisi 2 desimal (ROUND_HALF_UP).
    """
    if not pairwise_scores:
        return 0.0, 0.0, 0.0

    dec_scores = [Decimal(str(round(float(s), 4))) for s in pairwise_scores]
    n_pair = Decimal(len(dec_scores))

    aps_dec = sum(dec_scores) / n_pair
    mps_dec = min(dec_scores)

    weight_aps = Decimal("0.70")
    weight_mps = Decimal("0.30")

    gq_dec = (weight_aps * aps_dec) + (weight_mps * mps_dec)

    q2 = Decimal("0.01")
    gq_rounded = float(gq_dec.quantize(q2, rounding=ROUND_HALF_UP))
    aps_rounded = float(aps_dec.quantize(q2, rounding=ROUND_HALF_UP))
    mps_rounded = float(mps_dec.quantize(q2, rounding=ROUND_HALF_UP))

    return gq_rounded, aps_rounded, mps_rounded


# ==============================================================================
# 4. EVALUASI KOMPATIBILITAS SEPASANG MAHASISWA (PAIRWISE COMPATIBILITY)
# ==============================================================================
def evaluate_pairwise_compatibility(
    intent_a: StudyIntent,
    intent_b: StudyIntent
) -> Optional[Dict[str, Any]]:
    """
    Mengevaluasi apakah intent_a dan intent_b memenuhi syarat kecocokan dasar
    dan menghitung Compatibility Score Day 15 beserta rincian penjelasannya.
    Mengembalikan dictionary hasil atau None jika tidak ada irisan jadwal valid.
    """
    # 1. Mode belajar harus kompatibel (Day 14 Hard Constraint)
    # is_learning_mode_compatible mengembalikan tuple (is_compat: bool, agreed_mode: Optional[str])
    mode_a = getattr(intent_a, "learning_mode", "OFFLINE")
    mode_b = getattr(intent_b, "learning_mode", "OFFLINE")
    mode_compatible, _ = is_learning_mode_compatible(mode_a, mode_b)
    if not mode_compatible:
        return None

    # 2. Irisan jadwal >= 60 menit
    windows_a = resolve_availability_windows(intent_a)
    windows_b = resolve_availability_windows(intent_b)
    common_slots = find_common_schedule(windows_a, windows_b, min_duration=60)
    if not common_slots:
        return None

    # 3. Hitung Compatibility Score Day 15
    score_dict = calculate_partner_score(intent_a, intent_b, common_slots)
    return score_dict


# ==============================================================================
# 5. INTI ENGINE PEMBENTUKAN KELOMPOK (GREEDY STEPWISE FORMATION ENGINE)
# ==============================================================================
def form_study_group(
    host_intent: StudyIntent,
    candidate_intents: Sequence[StudyIntent],
    min_score: float = 60.0,
    target_group_size: Optional[int] = None,
    max_candidate_pool: Optional[int] = 20
) -> Dict[str, Any]:
    """
    Algoritma pembentukan kelompok belajar teroptimasi (Day 18):
    1. Pre-Filtering & Candidate Pool Pruning:
       - Evaluasi hard constraints kandidat terhadap host_intent.
       - Hitung skor kompatibilitas kandidat terhadap host.
       - Buang kandidat dengan CS < min_score atau irisan jadwal < 60 menit.
       - Urutkan kandidat potensial secara deterministik berdasarkan skor terhadap host.
       - Ambil Top-K kandidat (default max_candidate_pool = 20) untuk masuk ke Greedy Loop.
       - Catat statistik pruning untuk evaluasi performa & debugging.
    2. Pairwise Memoization Cache:
       - Memoization berbasis tuple sorted intent ID dengan cakupan satu kali pemanggilan fungsi.
    3. Multi-Way Hard Constraints Check:
       - Batasan ukuran kelompok dinamis: MinGroup <= MaxGroup.
       - Mode belajar konsisten secara multi-arah (no ONLINE-OFFLINE mix).
       - Irisan jadwal bersama seluruh anggota >= 60 menit.
    4. Deterministic Hierarchical Tie-Breaker:
       - Urutan: (-gq, -best_duration, -mps, -aps, earliest_date, earliest_start_time, cand_id).
    """
    # Validasi parameter input
    if host_intent is None:
        raise ValueError("host_intent tidak boleh None")
    if getattr(host_intent, "status", None) != "ACTIVE":
        raise ValueError(f"host_intent harus berstatus ACTIVE, saat ini '{getattr(host_intent, 'status', None)}'")

    if min_score is None or isinstance(min_score, bool):
        raise ValueError("min_score harus numerik non-boolean")
    try:
        min_score_val = float(min_score)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("min_score harus numerik valid")
    if math.isnan(min_score_val) or math.isinf(min_score_val) or not (0.0 <= min_score_val <= 100.0):
        raise ValueError(f"min_score ({min_score_val}) harus dalam rentang [0.0, 100.0]")

    if target_group_size is not None:
        if isinstance(target_group_size, bool) or not isinstance(target_group_size, int):
            raise ValueError("target_group_size harus integer positif")
        if target_group_size < 2:
            raise ValueError(f"target_group_size ({target_group_size}) minimal harus 2")

    if max_candidate_pool is not None:
        if isinstance(max_candidate_pool, bool) or not isinstance(max_candidate_pool, int):
            raise ValueError("max_candidate_pool harus integer positif")
        if max_candidate_pool < 1:
            raise ValueError(f"max_candidate_pool ({max_candidate_pool}) minimal harus 1")
        if max_candidate_pool > 100:
            raise ValueError(f"max_candidate_pool ({max_candidate_pool}) maksimal bernilai 100")

    host_student_id = str(getattr(host_intent, "student_id", ""))
    course_id = str(getattr(host_intent, "course_id", ""))

    # Pairwise Memoization Cache (Scoping lokal per pemanggilan form_study_group)
    pairwise_cache: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}

    def get_pair_score(ia: StudyIntent, ib: StudyIntent) -> Optional[Dict[str, Any]]:
        id_a = str(ia.intent_id)
        id_b = str(ib.intent_b_id if hasattr(ib, "intent_b_id") else ib.intent_id)
        pair_key = tuple(sorted([id_a, id_b]))
        if pair_key not in pairwise_cache:
            pairwise_cache[pair_key] = evaluate_pairwise_compatibility(ia, ib)
        return pairwise_cache[pair_key]

    # ==========================================================================
    # TAHAP 1: PRE-FILTERING KANDIDAT & CANDIDATE PRUNING
    # ==========================================================================
    total_candidates_examined = 0
    candidates_pruned_hard_constraints = 0
    candidates_pruned_min_score = 0
    viable_candidates = []

    for cand in candidate_intents or []:
        total_candidates_examined += 1
        if cand is None or getattr(cand, "intent_id", None) == host_intent.intent_id:
            candidates_pruned_hard_constraints += 1
            continue
        c_student_id = str(getattr(cand, "student_id", ""))
        if not c_student_id or c_student_id == host_student_id:
            candidates_pruned_hard_constraints += 1
            continue
        if str(getattr(cand, "course_id", "")) != course_id:
            candidates_pruned_hard_constraints += 1
            continue
        if getattr(cand, "status", None) != "ACTIVE":
            candidates_pruned_hard_constraints += 1
            continue

        st = getattr(cand, "student", None)
        if st is not None:
            if (getattr(st, "account_status", "ACTIVE") or "").upper() != "ACTIVE":
                candidates_pruned_hard_constraints += 1
                continue
            if (getattr(st, "verification_status", "VERIFIED") or "").upper() != "VERIFIED":
                candidates_pruned_hard_constraints += 1
                continue
            if getattr(st, "is_discoverable", True) is False:
                candidates_pruned_hard_constraints += 1
                continue

        # Evaluasi kompatibilitas awal terhadap Host (Hard Constraints & Jadwal >= 60m)
        score_dict = get_pair_score(host_intent, cand)
        if score_dict is None:
            candidates_pruned_hard_constraints += 1
            continue

        # Evaluasi batas skor minimal terhadap Host
        score_vs_host = float(score_dict.get("total_score", 0.0))
        if score_vs_host < min_score_val:
            candidates_pruned_min_score += 1
            continue

        # Ambil jadwal terbaik bersama host untuk penentuan urutan awal
        sched_host = score_dict.get("selected_schedule") or {}
        dur_host = int(sched_host.get("duration_minutes", 0))
        date_host = sched_host.get("date", "9999-12-31")
        time_host = sched_host.get("start_time", "23:59")

        viable_candidates.append({
            "candidate": cand,
            "score_vs_host": score_vs_host,
            "best_duration": dur_host,
            "earliest_date": date_host,
            "earliest_start_time": time_host,
            "cand_id": str(cand.intent_id),
        })

    # Urutkan kandidat yang lolos pra-syarat secara deterministik terhadap Host
    viable_candidates.sort(
        key=lambda item: (
            -item["score_vs_host"],
            -item["best_duration"],
            item["earliest_date"],
            item["earliest_start_time"],
            item["cand_id"]
        )
    )

    # Batasi pada Top-K kandidat untuk masuk ke Greedy Loop (Heuristik Skalabilitas)
    if max_candidate_pool is not None and len(viable_candidates) > max_candidate_pool:
        pool_candidates = [item["candidate"] for item in viable_candidates[:max_candidate_pool]]
    else:
        pool_candidates = [item["candidate"] for item in viable_candidates]

    candidate_pruning_stats = {
        "total_candidates_examined": total_candidates_examined,
        "candidates_pruned_hard_constraints": candidates_pruned_hard_constraints,
        "candidates_pruned_min_score": candidates_pruned_min_score,
        "candidates_in_pool": len(pool_candidates),
    }

    # ==========================================================================
    # TAHAP 2: INTI ENGINE GREEDY SELECTION DENGAN MULTI-WAY CONSTRAINTS
    # ==========================================================================
    selected_members: List[StudyIntent] = [host_intent]

    while True:
        curr_min, curr_max = calculate_group_size_bounds(selected_members)
        curr_size = len(selected_members)

        # Hentikan jika sudah mencapai target ukuran kelompok atau kapasitas maksimum
        if target_group_size and curr_size >= target_group_size:
            break
        if curr_size >= curr_max:
            break

        existing_student_ids = {str(m.student_id) for m in selected_members}
        candidate_evaluations = []

        for cand in pool_candidates:
            # 1. Deduplikasi Mahasiswa
            if str(cand.student_id) in existing_student_ids:
                continue

            # 2. Batasan Ukuran Kelompok jika kandidat ditambahkan
            test_group = selected_members + [cand]
            test_min, test_max = calculate_group_size_bounds(test_group)
            if test_min > test_max or len(test_group) > test_max:
                continue
            if target_group_size and len(test_group) > target_group_size:
                continue

            # 3. Multi-Way Learning Mode Consistency
            # Setiap pasang anggota harus kompatibel secara mode belajar
            cand_mode = getattr(cand, "learning_mode", "OFFLINE")
            modes_compatible = True
            for m in selected_members:
                m_mode = getattr(m, "learning_mode", "OFFLINE")
                compat, _ = is_learning_mode_compatible(m_mode, cand_mode)
                if not compat:
                    modes_compatible = False
                    break
            if not modes_compatible:
                continue

            # 4. Multi-Way Irisan Jadwal Bersama Seluruh Anggota
            all_windows = [resolve_availability_windows(m) for m in test_group]
            common_scheds = find_group_common_schedules(all_windows, min_duration=60)
            if not common_scheds:
                continue

            # 5. Kompatibilitas Seluruh Pasangan & Threshold Skor Minimal
            all_pairs_valid = True
            for member in selected_members:
                score_dict = get_pair_score(member, cand)
                if not score_dict or score_dict.get("total_score", 0.0) < min_score_val:
                    all_pairs_valid = False
                    break

            if not all_pairs_valid:
                continue

            # 6. Hitung Calon Group Quality Score (GQ) untuk seluruh pasangan di test_group
            total_group_pairwise_scores = []
            for m1, m2 in itertools.combinations(test_group, 2):
                ps = get_pair_score(m1, m2)
                if ps:
                    total_group_pairwise_scores.append(ps["total_score"])

            calon_gq, calon_aps, calon_mps = calculate_group_quality_score(total_group_pairwise_scores)

            # Metadata jadwal terbaik (sudah berurutan -durasi, date, start_time)
            best_sched = common_scheds[0]
            best_duration = best_sched["duration_minutes"]
            earliest_date = best_sched["date"]
            earliest_start_time = best_sched["start_time"]
            cand_id = str(cand.intent_id)

            candidate_evaluations.append({
                "candidate": cand,
                "gq": calon_gq,
                "aps": calon_aps,
                "mps": calon_mps,
                "best_duration": best_duration,
                "earliest_date": earliest_date,
                "earliest_start_time": earliest_start_time,
                "schedules": common_scheds,
                "cand_id": cand_id,
            })

        if not candidate_evaluations:
            break

        # Pengurutan deterministik bertingkat lengkap (Day 18.5):
        # 1. Group Quality Score (GQ) tertinggi (-item["gq"])
        # 2. Durasi jadwal bersama terpanjang (-item["best_duration"])
        # 3. Minimum Pairwise Score (MPS) tertinggi (-item["mps"])
        # 4. Average Pairwise Score (APS) tertinggi (-item["aps"])
        # 5. Tanggal jadwal bersama paling awal (item["earliest_date"])
        # 6. Jam mulai jadwal bersama paling awal (item["earliest_start_time"])
        # 7. ID intent terkecil secara alfabetis (item["cand_id"])
        candidate_evaluations.sort(
            key=lambda item: (
                -item["gq"],
                -item["best_duration"],
                -item["mps"],
                -item["aps"],
                item["earliest_date"],
                item["earliest_start_time"],
                item["cand_id"]
            )
        )

        best_choice = candidate_evaluations[0]
        selected_members.append(best_choice["candidate"])

    # ==========================================================================
    # TAHAP 3: PEMBENTUKAN OUTPUT PROPOSAL LENGKAP
    # ==========================================================================
    final_size = len(selected_members)
    min_bound, max_bound = calculate_group_size_bounds(selected_members)

    # Rincian Anggota Kelompok
    member_items = []
    for idx, m in enumerate(selected_members):
        st = getattr(m, "student", None)
        role = "HOST" if idx == 0 else "MEMBER"
        member_items.append({
            "student_id": str(m.student_id),
            "student_name": st.full_name if st else None,
            "intent_id": str(m.intent_id),
            "role": role,
            "study_program": st.study_program if st else None,
            "academic_year": st.academic_year if st else None,
            "learning_goal": m.learning_goal,
            "collaboration_style": m.collaboration_style,
            "min_group_size": int(getattr(m, "min_group_size", 2) or 2),
            "max_group_size": int(getattr(m, "max_group_size", 4) or 4),
        })

    # Rincian Skor Pasangan (Pairwise Scores)
    pairwise_score_items = []
    all_final_scores = []
    for m1, m2 in itertools.combinations(selected_members, 2):
        ps = get_pair_score(m1, m2)
        if ps:
            score_val = ps["total_score"]
            all_final_scores.append(score_val)
            breakdown_dict = ps["components"]
            explanation_text = generate_match_explanation(ps)
            pairwise_score_items.append({
                "student_a_id": str(m1.student_id),
                "student_b_id": str(m2.student_id),
                "intent_a_id": str(m1.intent_id),
                "intent_b_id": str(m2.intent_id),
                "compatibility_score": round(float(score_val), 2),
                "breakdown": breakdown_dict,
                "explanation": explanation_text,
            })

    # Hitung GQ, APS, MPS akhir
    gq, aps, mps = calculate_group_quality_score(all_final_scores)

    # Jadwal bersama akhir
    all_final_windows = [resolve_availability_windows(m) for m in selected_members]
    final_schedules = find_group_common_schedules(all_final_windows, min_duration=60)
    selected_sched = final_schedules[0] if final_schedules else None

    # Penentuan Status Kelompok
    if final_size >= min_bound and final_size >= 2:
        formation_status = "READY"
        message = f"Kelompok belajar beranggotakan {final_size} orang siap dibentuk dengan Group Quality Score {gq:.2f}."
    elif final_size > 1 and final_size < min_bound:
        formation_status = "INSUFFICIENT_MEMBERS"
        message = f"Kelompok baru beranggotakan {final_size} orang, belum memenuhi batas minimum ({min_bound} orang)."
    else:
        formation_status = "NO_COMPATIBLE_GROUP"
        message = "Tidak ditemukan kombinasi kandidat yang saling kompatibel untuk membentuk kelompok."

    course_obj = getattr(host_intent, "course", None)
    course_name = course_obj.course_name if course_obj else None

    return {
        "host_intent_id": str(host_intent.intent_id),
        "course_id": course_id,
        "course_name": course_name,
        "formation_status": formation_status,
        "group_size": final_size,
        "min_group_size_bound": min_bound,
        "max_group_size_bound": max_bound,
        "group_quality_score": gq,
        "average_pair_score": aps,
        "minimum_pair_score": mps,
        "members": member_items,
        "pairwise_scores": pairwise_score_items,
        "schedule_options": final_schedules,
        "selected_schedule": selected_sched,
        "candidate_pruning_stats": candidate_pruning_stats,
        "message": message,
    }


# ==============================================================================
# 6. PIPELINE PREVIEW API ORCHESTRATOR
# ==============================================================================
def preview_group_formation_pipeline(
    host_intent_id: str,
    db: Session,
    min_score: float = 60.0,
    target_group_size: Optional[int] = None,
    max_candidate_pool: Optional[int] = 20
) -> Dict[str, Any]:
    """
    Menjalankan alur pencarian dan penyusunan calon kelompok belajar untuk host_intent_id.
    Operasi ini murni READ-ONLY (tidak menulis atau mengubah database apa pun).
    """
    if db is None:
        raise ValueError("Database session (db) tidak boleh None")

    host_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == host_intent_id).first()
    if not host_intent:
        raise ValueError(f"Study Intent dengan ID '{host_intent_id}' tidak ditemukan")

    if host_intent.status != "ACTIVE":
        raise ValueError(f"Study Intent harus berstatus ACTIVE, status saat ini: '{host_intent.status}'")

    # Ambil kandidat partner dari database yang memiliki mata kuliah sama
    candidate_intents = (
        db.query(StudyIntent)
        .join(StudyIntent.student)
        .filter(
            StudyIntent.course_id == host_intent.course_id,
            StudyIntent.status == "ACTIVE",
            StudyIntent.student_id != host_intent.student_id,
            Student.account_status == "ACTIVE",
            Student.verification_status == "VERIFIED",
            Student.is_discoverable == True
        )
        .all()
    )

    return form_study_group(
        host_intent=host_intent,
        candidate_intents=candidate_intents,
        min_score=min_score,
        target_group_size=target_group_size,
        max_candidate_pool=max_candidate_pool
    )

