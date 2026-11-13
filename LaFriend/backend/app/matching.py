"""Fitur 1: Intent-Based Matching.

Logika murni tanpa database. Urutannya: syarat wajib (H), lima nilai (T, G, S, D, M),
skor CS, lalu rekomendasi sesi lebih dulu dan partner sebagai cadangan.
Sumber: Plan/Day4.MD, Plan/Day5.MD, Plan/Day7.MD, peta-alur-sistem/KEPUTUSAN.md.

Objek intent yang dipakai di sini cukup punya atribut yang sama dengan model StudyIntent
(course_id, topics, learning_goal, collaboration_style, learning_mode, earliest_date,
latest_date, status, student_id, student, availabilities).
"""
from datetime import date, timedelta
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

from app.schemas import WEEKDAYS
from app.outcome import DEFAULT_WEIGHTS

MIN_OVERLAP_MINUTES = 60  # nilai awal, bisa diubah admin (KEPUTUSAN.md nomor 6)
MAX_RECOMMENDATIONS = 5   # Plan/Day4.MD bagian 10

# shortcut: daftar alias hanya berisi contoh dari Day4, pindahkan ke tabel materi saat katalog materi ada
TOPIC_ALIASES = {"bst": "binary search tree"}

# Tabel G, KEPUTUSAN.md nomor 1. Tujuan sama = 100.
GOAL_SCORES = {
    frozenset({"UNDERSTAND", "PRACTICE"}): 85,
    frozenset({"UNDERSTAND", "EXAM_PREP"}): 85,
    frozenset({"PRACTICE", "EXAM_PREP"}): 85,
    frozenset({"DISCUSSION", "EXAM_PREP"}): 75,
    frozenset({"PRACTICE", "ASSIGNMENT"}): 75,
    frozenset({"UNDERSTAND", "DISCUSSION"}): 70,
    frozenset({"DISCUSSION", "PRACTICE"}): 70,
    frozenset({"ASSIGNMENT", "UNDERSTAND"}): 60,
    frozenset({"DISCUSSION", "ASSIGNMENT"}): 60,
    frozenset({"EXAM_PREP", "ASSIGNMENT"}): 40,
}

# Tabel S, KEPUTUSAN.md nomor 2. Gaya sama = 100.
STYLE_SCORES = {
    frozenset({"TEACHING", "PRACTICE"}): 80,
    frozenset({"DISCUSSION", "PRACTICE"}): 80,
    frozenset({"DISCUSSION", "TEACHING"}): 80,
    frozenset({"PRACTICE", "FOCUS_STUDY"}): 60,
    frozenset({"DISCUSSION", "FOCUS_STUDY"}): 30,
    frozenset({"TEACHING", "FOCUS_STUDY"}): 30,
}


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def normalize_topics(topics: str) -> frozenset:
    """Seragamkan nama materi sebelum dibandingkan (Day4 bagian 4)."""
    names = (" ".join(part.split()).casefold() for part in topics.split(","))
    return frozenset(TOPIC_ALIASES.get(name, name) for name in names if name)


def topic_score(a, b) -> float:
    """T: Jaccard x 100."""
    ta, tb = normalize_topics(a.topics), normalize_topics(b.topics)
    union = ta | tb
    return len(ta & tb) / len(union) * 100 if union else 0.0


def _table_score(table: Dict[frozenset, int], x: str, y: str, kind: str) -> int:
    if x == y:
        return 100
    try:
        return table[frozenset({x, y})]
    except KeyError:
        raise ValueError(f"Pasangan {kind} tidak dikenal: {x} dan {y}")


def goal_score(a, b) -> int:
    return _table_score(GOAL_SCORES, a.learning_goal, b.learning_goal, "tujuan")


def style_score(a, b) -> int:
    return _table_score(STYLE_SCORES, a.collaboration_style, b.collaboration_style, "gaya belajar")


def _mode_ranks(intent) -> Dict[str, int]:
    """Metode yang bisa dipakai: 1 = pilihan utama, 2 = pilihan alternatif."""
    # shortcut: model StudyIntent belum punya kolom alternative_modes, jadi dibaca bila ada saja
    alternatives = getattr(intent, "alternative_modes", None) or ""
    choices = [(intent.learning_mode, 1)] + [(m.strip(), 2) for m in alternatives.split(",") if m.strip()]
    ranks: Dict[str, int] = {}
    for mode, rank in choices:
        # Hybrid berarti bersedia Offline maupun Online (KEPUTUSAN.md nomor 4)
        for usable in ("OFFLINE", "ONLINE", "HYBRID") if mode == "HYBRID" else (mode,):
            ranks[usable] = min(rank, ranks.get(usable, rank))
    return ranks


def mode_score(a, b) -> int:
    """M: 100 sama-sama utama, 85 utama dengan alternatif, 70 sama-sama alternatif, 0 tidak ada."""
    ra, rb = _mode_ranks(a), _mode_ranks(b)
    shared = ra.keys() & rb.keys()
    if not shared:
        return 0
    return {2: 100, 3: 85, 4: 70}[min(ra[m] + rb[m] for m in shared)]


def _dated_slots(intent, first: date, last: date) -> List[dict]:
    """Jam kosong satu intent sebagai tanggal nyata di antara first dan last.

    Nama hari ("Rabu", "Wednesday") menjadi semua tanggal berhari itu di dalam rentang.
    """
    slots = []
    for av in intent.availabilities:
        key = av.day_or_date.strip().casefold()
        if key in WEEKDAYS:
            days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
            days = [d for d in days if d.weekday() == WEEKDAYS[key]]
        else:
            days = [d for d in [date.fromisoformat(key)] if first <= d <= last]
        slots += [{"day": d.isoformat(), "start": _minutes(av.start_time), "end": _minutes(av.end_time),
                   "ranks": [av.priority_rank]} for d in days]
    return slots


def common_slots(intents: Sequence, min_minutes: int = MIN_OVERLAP_MINUTES) -> List[dict]:
    """Waktu yang sama-sama kosong untuk semua intent, minimal min_minutes, urut dari tanggal terawal.

    Hanya tanggal di dalam irisan rentang tanggal semua intent yang dipakai. Irisan jam dihitung
    per tanggal secara terpisah: mulai paling akhir sampai selesai paling awal.
    """
    first = max(date.fromisoformat(i.earliest_date) for i in intents)
    last = min(date.fromisoformat(i.latest_date) for i in intents)
    slots = _dated_slots(intents[0], first, last)
    for intent in intents[1:]:
        narrowed = []
        for slot in slots:
            for other in _dated_slots(intent, first, last):
                if other["day"] != slot["day"]:
                    continue
                start, end = max(slot["start"], other["start"]), min(slot["end"], other["end"])
                if end - start >= min_minutes:
                    narrowed.append({"day": slot["day"], "start": start, "end": end,
                                     "ranks": slot["ranks"] + other["ranks"]})
        slots = narrowed
    return sorted((s for s in slots if s["end"] - s["start"] >= min_minutes), key=lambda s: s["day"])


def _rank_score(ranks: Sequence[int]) -> int:
    """Nilai D untuk satu waktu bersama (Day4 bagian 7, KEPUTUSAN.md nomor 3)."""
    if max(ranks) >= 3:
        return 60
    return {2: 100, 3: 85, 4: 75}[sum(ranks)]


def date_score(a, b, min_minutes: int = MIN_OVERLAP_MINUTES) -> Tuple[int, Optional[dict]]:
    """D dan waktu yang diusulkan: waktu bersama dengan nilai tertinggi."""
    slots = common_slots([a, b], min_minutes)
    if not slots:
        return 0, None
    best = max(slots, key=lambda s: (_rank_score(s["ranks"]), s["end"] - s["start"]))
    proposed = {"day": best["day"], "start_time": _hhmm(best["start"]), "end_time": _hhmm(best["end"])}
    return _rank_score(best["ranks"]), proposed


def _account_ok(intent) -> bool:
    student = intent.student
    return student.verification_status == "VERIFIED" and student.account_status == "ACTIVE"


def hard_constraint(a, b, min_minutes: int = MIN_OVERLAP_MINUTES) -> Optional[str]:
    """Keputusan 1 sampai 5. Mengembalikan None bila lolos (H = 1), atau kode syarat yang gagal."""
    if a.course_id != b.course_id:
        return "COURSE"
    if not (_account_ok(a) and _account_ok(b)):
        return "ACCOUNT"
    # Tanggal berformat YYYY-MM-DD, jadi urutan teksnya sama dengan urutan tanggalnya
    if a.earliest_date > b.latest_date or b.earliest_date > a.latest_date:
        return "DATE_RANGE"
    if not common_slots([a, b], min_minutes):
        return "TIME_OVERLAP"
    if mode_score(a, b) == 0:
        return "MODE"
    return None


def compatibility(a, b, weights: Optional[Dict[str, float]] = None,
                  min_minutes: int = MIN_OVERLAP_MINUTES) -> dict:
    """CS = w_t T + w_g G + w_s S + w_d D + w_m M, rentang 0 sampai 100. Panggil setelah H = 1."""
    w = weights or DEFAULT_WEIGHTS
    d, proposed = date_score(a, b, min_minutes)
    scores = {"t": topic_score(a, b), "g": goal_score(a, b), "s": style_score(a, b),
              "d": d, "m": mode_score(a, b)}
    total = sum(w[k] * scores[k] for k in scores)
    return {"total": round(total, 2), **scores, "proposed_slot": proposed}


def group_quality(pair_scores: Sequence[float]) -> float:
    """GQ = 0,70 x rata-rata pasangan + 0,30 x pasangan terlemah (Day7)."""
    return round(0.70 * sum(pair_scores) / len(pair_scores) + 0.30 * min(pair_scores), 2)


def match_partners(seeker, intents: Sequence, weights: Optional[Dict[str, float]] = None,
                   min_minutes: int = MIN_OVERLAP_MINUTES, limit: int = MAX_RECOMMENDATIONS) -> List[dict]:
    """Partner Matching: intent aktif mahasiswa lain yang lolos H, diurutkan dari CS tertinggi.

    Tidak ada ambang skor. Skor hanya mengurutkan (Day4 bagian 10).
    Satu mahasiswa hanya muncul sekali, dengan intent yang skornya paling tinggi.
    """
    results = []
    for other in intents:
        if other.student_id == seeker.student_id or other.status != "ACTIVE":
            continue
        if hard_constraint(seeker, other, min_minutes):
            continue
        results.append({"intent": other, **compatibility(seeker, other, weights, min_minutes)})
    results.sort(key=lambda r: r["total"], reverse=True)
    seen, unique = set(), []
    for r in results:
        if r["intent"].student_id not in seen:
            seen.add(r["intent"].student_id)
            unique.append(r)
    return unique[:limit]


def match_sessions(seeker, sessions: Sequence, weights: Optional[Dict[str, float]] = None,
                   min_minutes: int = MIN_OVERLAP_MINUTES, limit: int = MAX_RECOMMENDATIONS) -> List[dict]:
    """Session Matching: sesi yang lolos syarat, diurutkan dari GQ tertinggi setelah pencari masuk.

    Sesi yang baru berisi host menghasilkan GQ = CS pencari dengan host (KEPUTUSAN.md nomor 5).
    """
    # shortcut: sesi = objek dengan members (intent anggota, host pertama) dan max_size,
    # ganti dengan tabel study_sessions saat Fitur 2 sudah ada
    results = []
    for session in sessions:
        members = list(session.members)
        if any(m.student_id == seeker.student_id for m in members):
            continue
        if len(members) >= session.max_size:  # Keputusan 6: sesi penuh
            continue
        if any(hard_constraint(seeker, m, min_minutes) for m in members):
            continue
        group = members + [seeker]
        if not common_slots(group, min_minutes):  # semua anggota harus punya waktu bersama
            continue
        if topic_score(seeker, members[0]) == 0:  # Day5 bagian 3: materi sesi harus relevan
            continue
        pairs = [compatibility(x, y, weights, min_minutes)["total"] for x, y in combinations(group, 2)]
        results.append({"session": session, "total": group_quality(pairs),
                        "seats_left": session.max_size - len(members)})
    results.sort(key=lambda r: r["total"], reverse=True)
    return results[:limit]


def recommend(seeker, sessions: Sequence, intents: Sequence, weights: Optional[Dict[str, float]] = None,
              min_minutes: int = MIN_OVERLAP_MINUTES, limit: int = MAX_RECOMMENDATIONS) -> dict:
    """Sesi yang sudah ada dicari lebih dulu. Partner dicari hanya bila tidak ada sesi yang lolos."""
    found = match_sessions(seeker, sessions, weights, min_minutes, limit)
    if found:
        return {"type": "SESSION", "items": found}
    found = match_partners(seeker, intents, weights, min_minutes, limit)
    return {"type": "PARTNER" if found else "NONE", "items": found}
