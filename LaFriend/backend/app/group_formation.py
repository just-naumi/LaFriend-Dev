"""Fitur 2: Feasibility-Aware Group Formation.

Logika murni tanpa database. Urutannya: host menjadi anggota pertama, calon dicoba satu per satu
(ukuran, jadwal bersama, skor antaranggota), calon dengan GQ terbaik masuk, lalu undangan dan
persetujuan jadwal. Kelompok tidak pernah dikonfirmasi otomatis.
Sumber: Plan/Day5.MD, Plan/Day7.MD, Plan/Day10.MD, peta-alur-sistem/KEPUTUSAN.md.

Proposal berupa dict. Statusnya: DRAFT (masih ada undangan yang belum dijawab),
CONFIRMATION_PENDING (menunggu persetujuan jadwal), CONFIRMED, atau FAILED.
"""
from itertools import combinations
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

from app import matching as M

MAX_GROUP_SIZE = 4  # termasuk host, nilai awal yang bisa diubah admin (KEPUTUSAN.md nomor 6)


def size_range(intents: Sequence, cap: int = MAX_GROUP_SIZE) -> Tuple[int, int]:
    """MinGroup = minimum terbesar, MaxGroup = maksimum terkecil dan paling tinggi cap (Day7 bagian 10)."""
    return max(i.min_group_size for i in intents), min(cap, min(i.max_group_size for i in intents))


def slot_score(ranks: Sequence[int]) -> float:
    """Nilai D satu waktu bersama untuk kelompok: rata-rata nilai D semua pasangan anggotanya."""
    return mean(M._rank_score(pair) for pair in combinations(ranks, 2)) if len(ranks) > 1 else 100


def group_slots(intents: Sequence, min_minutes: int = M.MIN_OVERLAP_MINUTES) -> List[dict]:
    """Waktu bersama seluruh anggota, diurutkan dari nilai D tertinggi."""
    # sorted() stabil, jadi bila nilainya seri tanggal terawal tetap di depan
    slots = sorted(M.common_slots(intents, min_minutes),
                   key=lambda s: (slot_score(s["ranks"]), s["end"] - s["start"]), reverse=True)
    return [{"day": s["day"], "start_time": M._hhmm(s["start"]), "end_time": M._hhmm(s["end"])} for s in slots]


def pair_scores(intents: Sequence, weights: Optional[Dict[str, float]] = None,
                min_minutes: int = M.MIN_OVERLAP_MINUTES) -> List[float]:
    """CS semua pasangan anggota, bukan hanya pasangan dengan host."""
    return [M.compatibility(a, b, weights, min_minutes)["total"] for a, b in combinations(intents, 2)]


def _try_candidate(members: Sequence, candidate, weights, min_minutes: int, cap: int) -> Tuple[Optional[float], str]:
    """Mengembalikan (GQ, "") bila calon bisa masuk, atau (None, kode alasan) bila tidak."""
    group = list(members) + [candidate]
    min_group, max_group = size_range(group, cap)
    if min_group > max_group or len(group) > max_group:
        return None, "GROUP_SIZE"
    for member in members:
        reason = M.hard_constraint(candidate, member, min_minutes)
        if reason:
            return None, reason
    if not M.common_slots(group, min_minutes):
        return None, "TIME_OVERLAP"
    return M.group_quality(pair_scores(group, weights, min_minutes)), ""


def _release(intents: Sequence) -> None:
    """Intent kembali ACTIVE supaya bisa dicarikan lagi. Intent tidak dihapus."""
    for intent in intents:
        intent.status = "ACTIVE"


def build_group(members: Sequence, candidates: Sequence, weights: Optional[Dict[str, float]] = None,
                min_minutes: int = M.MIN_OVERLAP_MINUTES, cap: int = MAX_GROUP_SIZE,
                accepted: Sequence[str] = ()) -> dict:
    """Menambah calon satu per satu sampai jumlah anggota mencapai MinGroup.

    members[0] adalah host. Tiap putaran, calon dengan GQ terbaik yang masuk, bukan calon dengan
    skor tertinggi terhadap host. Cara bertahap ini tidak menjamin kombinasi terbaik (Day7).
    """
    members = list(members)
    host = members[0]
    taken = {m.student_id for m in members}
    # Satu mahasiswa hanya boleh punya satu proses pembentukan kelompok aktif (Day10)
    pool = [c for c in candidates if c.student_id not in taken and c.status == "ACTIVE"]
    trace = []
    while len(members) < size_range(members, cap)[0]:
        tried = []
        for candidate in pool:
            gq, reason = _try_candidate(members, candidate, weights, min_minutes, cap)
            tried.append({"student_id": candidate.student_id, "gq": gq, "reason": reason})
        passed = [t for t in tried if t["gq"] is not None]
        chosen = max(passed, key=lambda t: t["gq"])["student_id"] if passed else None
        trace.append({"members": [m.student_id for m in members], "tried": tried, "chosen": chosen})
        if chosen is None:
            _release(members)
            return {"status": "FAILED", "reason_code": "GROUP_SIZE", "members": members, "trace": trace}
        members.append(next(c for c in pool if c.student_id == chosen))
        pool = [c for c in pool if c.student_id != chosen]

    min_group, max_group = size_range(members, cap)
    if len(members) > max_group or min_group > max_group:
        _release(members)
        return {"status": "FAILED", "reason_code": "GROUP_SIZE", "members": members, "trace": trace}
    slots = group_slots(members, min_minutes)
    if not slots:
        _release(members)
        return {"status": "FAILED", "reason_code": "SCHEDULE_MISMATCH", "members": members, "trace": trace}
    accepted = [host.student_id] + [s for s in accepted if s != host.student_id and s in {m.student_id for m in members}]
    # Semua anggota proposal ditandai, supaya tidak diundang kelompok lain pada saat yang sama (Day10)
    for member in members:
        member.status = "GROUP_FORMING"
    scores = pair_scores(members, weights, min_minutes)
    return {
        "status": "CONFIRMATION_PENDING" if len(accepted) == len(members) else "DRAFT",
        "members": members,
        "accepted": accepted,  # host dan anggota yang sudah menerima undangan
        "slots": slots,        # slots[slot_index] adalah jadwal yang sedang diusulkan
        "slot_index": 0,
        "gq": M.group_quality(scores) if scores else None,
        "min_group": min_group,
        "max_group": max_group,
        "trace": trace,
    }


def answer_invitations(proposal: dict, answers: Dict[str, str], candidates: Sequence = (),
                       weights: Optional[Dict[str, float]] = None,
                       min_minutes: int = M.MIN_OVERLAP_MINUTES, cap: int = MAX_GROUP_SIZE) -> dict:
    """Jawaban undangan per student_id: ACCEPTED, REJECTED, atau EXPIRED (tidak menjawab 24 jam).

    Yang menolak atau tidak menjawab dikeluarkan. Bila sisa anggota kurang dari MinGroup, sistem
    mencari pengganti dari candidates. Anggota yang belum ada di answers tetap menunggu.
    """
    if proposal["status"] != "DRAFT":
        raise ValueError(f"Undangan hanya dijawab saat proposal DRAFT, bukan {proposal['status']}")
    host = proposal["members"][0]
    unknown = [a for a in answers.values() if a not in ("ACCEPTED", "REJECTED", "EXPIRED")]
    if unknown or host.student_id in answers:
        raise ValueError("Jawaban undangan tidak sah")
    out = {sid for sid, answer in answers.items() if answer != "ACCEPTED"}
    accepted = proposal["accepted"] + [sid for sid, answer in answers.items()
                                       if answer == "ACCEPTED" and sid not in proposal["accepted"]]
    remaining = [m for m in proposal["members"] if m.student_id not in out]
    _release(m for m in proposal["members"] if m.student_id in out)
    result = build_group(remaining, [c for c in candidates if c.student_id not in out],
                         weights, min_minutes, cap, accepted)
    if result["status"] == "FAILED":
        expired = any(answer == "EXPIRED" for answer in answers.values())
        result["reason_code"] = "NO_RESPONSE" if expired else "USER_WITHDRAWAL"
    return result


def answer_schedule(proposal: dict, approvals: Dict[str, bool], candidates: Sequence = (),
                    weights: Optional[Dict[str, float]] = None,
                    min_minutes: int = M.MIN_OVERLAP_MINUTES, cap: int = MAX_GROUP_SIZE) -> dict:
    """Persetujuan jadwal akhir per student_id. Yang tidak menjawab dianggap tidak setuju.

    Semua setuju: CONFIRMED. Bila tidak: waktu bersama berikutnya diusulkan. Bila waktu bersama
    habis, yang menolak dikeluarkan dan sisa anggota dicek terhadap MinGroup (KEPUTUSAN.md nomor 7).
    """
    if proposal["status"] != "CONFIRMATION_PENDING":
        raise ValueError(f"Jadwal hanya disetujui saat CONFIRMATION_PENDING, bukan {proposal['status']}")
    members = proposal["members"]
    host = members[0]
    refused = [m for m in members if not approvals.get(m.student_id, False)]
    if not refused:
        for member in members:
            member.status = "CONVERTED"
        return {**proposal, "status": "CONFIRMED"}
    if proposal["slot_index"] + 1 < len(proposal["slots"]):
        return {**proposal, "slot_index": proposal["slot_index"] + 1}
    if host in refused:
        _release(members)
        return {**proposal, "status": "FAILED", "reason_code": "SCHEDULE_MISMATCH"}
    out = {m.student_id for m in refused}
    remaining = [m for m in members if m.student_id not in out]
    _release(refused)
    result = build_group(remaining, [c for c in candidates if c.student_id not in out], weights, min_minutes, cap,
                         [m.student_id for m in remaining])
    if result["status"] == "FAILED":
        result["reason_code"] = "SCHEDULE_MISMATCH"
    return result
