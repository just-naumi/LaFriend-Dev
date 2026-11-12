"""Fitur 3: Outcome-Oriented Matching (Plan/Day9.MD).

Fitur 1 dan Fitur 2 melapor ke sini lewat fungsi OutcomeService:
record_event, start_formation, confirm_session, fail_formation, cancel_session.
Mahasiswa hanya mengirim "rekomendasi dilihat" dan feedback lewat router.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import StatisticsError, correlation, mean
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.outcome import Feedback, MatchingEvent, SessionOutcome, WeightVersion
from app.schemas.outcome import RecommendationFeedbackIn, SessionFeedbackIn, Weights

EVENT_TYPES = (
    "RECOMMENDATION_VIEWED", "JOIN_REQUEST_SENT", "INVITATION_SENT",
    "INVITATION_ACCEPTED", "INVITATION_REJECTED", "SCHEDULE_APPROVED",
    "SESSION_CONFIRMED", "SESSION_COMPLETED", "SESSION_CANCELLED",
)
# Tindakan positif untuk RAR: permintaan bergabung (sesi) atau undangan dikirim (partner). Klik profil tidak dihitung.
POSITIVE_ACTIONS = ("JOIN_REQUEST_SENT", "INVITATION_SENT")
REASON_CODES = (
    "SCHEDULE_MISMATCH", "TOPIC_MISMATCH", "GOAL_MISMATCH", "STYLE_MISMATCH",
    "GROUP_SIZE", "NO_RESPONSE", "USER_WITHDRAWAL", "OTHER",
)
DEFAULT_WEIGHTS = {"t": 0.30, "g": 0.25, "s": 0.15, "d": 0.15, "m": 0.15}  # Plan/Day4.MD
MIN_COMPLETED_FOR_WEIGHT_TEST = 30  # hipotesis, lihat KEPUTUSAN.md nomor 9


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_naive(dt: datetime) -> datetime:
    # SQLite menyimpan waktu tanpa zona, jadi semua waktu disamakan ke UTC tanpa zona
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _rate(numerator: int, denominator: int) -> dict:
    value = round(numerator / denominator * 100, 2) if denominator else None
    return {"value": value, "numerator": numerator, "denominator": denominator}


def session_result(session: SessionOutcome, held_answers: Dict[str, bool], now: datetime) -> str:
    """Pohon keputusan pelaksanaan sesi: NOT_CONFIRMED, NOT_DUE, NOT_HELD, DISPUTED, atau COMPLETED."""
    if session.confirmed_at is None:
        return "NOT_CONFIRMED"
    if session.scheduled_end > now:
        return "NOT_DUE"  # belum waktunya, tidak dihitung gagal
    if session.status == "CANCELLED":
        return "NOT_HELD"  # batal setelah CONFIRMED tetap masuk penyebut SCR
    yes = {sid for sid, held in held_answers.items() if held}
    no = set(held_answers) - yes
    if yes and no:
        return "DISPUTED"  # jawaban bertentangan, belum dihitung
    if session.host_id in yes and len(yes) >= 2:
        return "COMPLETED"  # host ditambah minimal satu anggota
    return "NOT_HELD"


class OutcomeService:

    # ---------- Dipanggil oleh Fitur 1 dan Fitur 2 ----------

    @staticmethod
    def record_event(db: Session, student_id: str, event_type: str, match_id: Optional[str] = None,
                     session_id: Optional[str] = None, event_status: Optional[str] = None,
                     reason_code: Optional[str] = None) -> MatchingEvent:
        if event_type not in EVENT_TYPES:
            raise _bad_request(f"Jenis aktivitas tidak dikenal: {event_type}")
        if reason_code is not None and reason_code not in REASON_CODES:
            raise _bad_request(f"Kode alasan tidak dikenal: {reason_code}")
        event = MatchingEvent(student_id=student_id, event_type=event_type, match_id=match_id,
                              session_id=session_id, event_status=event_status, reason_code=reason_code)
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def _get_session(db: Session, session_id: str) -> SessionOutcome:
        session = db.query(SessionOutcome).filter(SessionOutcome.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesi tidak ditemukan")
        return session

    @staticmethod
    def start_formation(db: Session, session_id: str, host_id: str,
                        scores: Optional[Dict[str, float]] = None) -> SessionOutcome:
        """Satu percobaan pembentukan kelompok dimulai. scores: total, t, g, s, d, m (0-100)."""
        if db.query(SessionOutcome).filter(SessionOutcome.session_id == session_id).first():
            raise _bad_request("Sesi sudah tercatat")
        scores = scores or {}
        session = SessionOutcome(
            session_id=session_id, host_id=host_id, status="FORMING",
            score_total=scores.get("total"), score_t=scores.get("t"), score_g=scores.get("g"),
            score_s=scores.get("s"), score_d=scores.get("d"), score_m=scores.get("m"),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def confirm_session(db: Session, session_id: str, scheduled_end: datetime,
                        member_ids: List[str]) -> SessionOutcome:
        session = OutcomeService._get_session(db, session_id)
        if session.status != "FORMING":
            raise _bad_request(f"Sesi dengan status {session.status} tidak dapat dikonfirmasi")
        if session.host_id not in member_ids or len(set(member_ids)) < 2:
            raise _bad_request("Anggota harus memuat host dan minimal satu anggota lain")
        session.status = "CONFIRMED"
        session.confirmed_at = _now()
        session.scheduled_end = _utc_naive(scheduled_end)
        session.member_ids = ",".join(sorted(set(member_ids)))
        db.commit()
        OutcomeService.record_event(db, session.host_id, "SESSION_CONFIRMED", session_id=session_id)
        db.refresh(session)
        return session

    @staticmethod
    def fail_formation(db: Session, session_id: str, reason_code: str) -> SessionOutcome:
        session = OutcomeService._get_session(db, session_id)
        if session.status != "FORMING":
            raise _bad_request(f"Sesi dengan status {session.status} tidak dapat ditandai gagal")
        if reason_code not in REASON_CODES:
            raise _bad_request(f"Kode alasan tidak dikenal: {reason_code}")
        session.status = "FAILED"
        session.reason_code = reason_code
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def cancel_session(db: Session, session_id: str) -> SessionOutcome:
        session = OutcomeService._get_session(db, session_id)
        if session.status != "CONFIRMED":
            raise _bad_request("Hanya sesi CONFIRMED yang dapat dibatalkan. Kelompok yang belum jadi memakai fail_formation")
        session.status = "CANCELLED"
        db.commit()
        OutcomeService.record_event(db, session.host_id, "SESSION_CANCELLED", session_id=session_id)
        db.refresh(session)
        return session

    # ---------- Dipanggil oleh router (mahasiswa) ----------

    @staticmethod
    def record_viewed(db: Session, student_id: str, match_id: str) -> MatchingEvent:
        # shortcut: match_id belum dicek ke tabel rekomendasi, tambahkan saat Fitur 1 sudah ada
        return OutcomeService.record_event(db, student_id, "RECOMMENDATION_VIEWED", match_id=match_id)

    @staticmethod
    def _save_feedback(db: Session, feedback: Optional[Feedback], new: Feedback, data: dict) -> Feedback:
        if feedback is None:
            feedback = new
            db.add(feedback)
        else:
            feedback.updated_at = _now()  # jawaban lama diperbarui, tidak menjadi data ganda
        for key, value in data.items():
            setattr(feedback, key, value)
        db.commit()
        db.refresh(feedback)
        return feedback

    @staticmethod
    def save_recommendation_feedback(db: Session, student_id: str, match_id: str,
                                     data: RecommendationFeedbackIn) -> Feedback:
        viewed = db.query(MatchingEvent).filter(
            MatchingEvent.student_id == student_id, MatchingEvent.match_id == match_id,
            MatchingEvent.event_type == "RECOMMENDATION_VIEWED",
        ).first()
        if not viewed:
            raise _bad_request("Rekomendasi ini belum pernah ditampilkan kepada Anda")
        existing = db.query(Feedback).filter(
            Feedback.student_id == student_id, Feedback.match_id == match_id).first()
        new = Feedback(student_id=student_id, match_id=match_id, feedback_type="RECOMMENDATION")
        return OutcomeService._save_feedback(db, existing, new, data.model_dump())

    @staticmethod
    def save_session_feedback(db: Session, student_id: str, session_id: str,
                              data: SessionFeedbackIn) -> Feedback:
        session = OutcomeService._get_session(db, session_id)
        if session.status != "CONFIRMED":
            raise _bad_request("Sesi belum dikonfirmasi atau sudah dibatalkan")
        if student_id not in (session.member_ids or "").split(","):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Anda bukan anggota sesi ini")
        if session.scheduled_end > _now():
            raise _bad_request("Feedback baru dapat diisi setelah jadwal sesi selesai")
        existing = db.query(Feedback).filter(
            Feedback.student_id == student_id, Feedback.session_id == session_id).first()
        new = Feedback(student_id=student_id, session_id=session_id, feedback_type="SESSION")
        return OutcomeService._save_feedback(db, existing, new, data.model_dump())

    # ---------- Evaluasi ----------

    @staticmethod
    def _snapshot(db: Session, now: Optional[datetime] = None):
        """Semua sesi, hasil tiap sesi, dan Session Feedback per sesi."""
        now = now or _now()
        sessions = db.query(SessionOutcome).all()
        feedback_by_session = defaultdict(list)
        for fb in db.query(Feedback).filter(Feedback.feedback_type == "SESSION").all():
            feedback_by_session[fb.session_id].append(fb)
        results = {
            s.session_id: session_result(
                s, {fb.student_id: fb.session_held for fb in feedback_by_session[s.session_id]}, now)
            for s in sessions
        }
        return sessions, results, feedback_by_session

    @staticmethod
    def _satisfaction(feedbacks: List[Feedback]) -> List[int]:
        # Yang tidak mengisi dilewati, bukan diberi nilai 0
        return [fb.overall_satisfaction for fb in feedbacks if fb.overall_satisfaction is not None]

    @staticmethod
    def compute_metrics(db: Session, now: Optional[datetime] = None) -> dict:
        """Lima metrik dilihat berdampingan. Sengaja tidak digabung menjadi satu skor."""
        events = db.query(MatchingEvent.student_id, MatchingEvent.match_id, MatchingEvent.event_type).filter(
            MatchingEvent.match_id.isnot(None),
            MatchingEvent.event_type.in_(("RECOMMENDATION_VIEWED",) + POSITIVE_ACTIONS),
        ).all()
        viewed = {(sid, mid) for sid, mid, etype in events if etype == "RECOMMENDATION_VIEWED"}
        acted = {(sid, mid) for sid, mid, etype in events if etype in POSITIVE_ACTIONS} & viewed

        sessions, results, feedback_by_session = OutcomeService._snapshot(db, now)
        # Kelompok yang masih FORMING belum punya hasil, jadi belum dihitung sebagai percobaan gagal
        attempts = [s for s in sessions if s.status != "FORMING"]
        confirmed = [s for s in attempts if s.confirmed_at is not None]
        completed_ids = [sid for sid, result in results.items() if result == "COMPLETED"]
        due = len(completed_ids) + sum(1 for result in results.values() if result == "NOT_HELD")

        completed_feedback = [fb for sid in completed_ids for fb in feedback_by_session[sid]]
        ratings = OutcomeService._satisfaction(completed_feedback)
        repeat = [fb.repeat_intention for fb in completed_feedback if fb.repeat_intention is not None]
        completed_with_feedback = sum(
            1 for sid in completed_ids if OutcomeService._satisfaction(feedback_by_session[sid]))

        recommendation_feedback = {"relevance_rating": Counter(), "explanation_rating": Counter(),
                                   "interest_level": Counter()}
        for fb in db.query(Feedback).filter(Feedback.feedback_type == "RECOMMENDATION").all():
            for field, counter in recommendation_feedback.items():
                if getattr(fb, field) is not None:
                    counter[getattr(fb, field)] += 1

        return {
            "rar": _rate(len(acted), len(viewed)),
            "gfr": _rate(len(confirmed), len(attempts)),
            "scr": _rate(len(completed_ids), due),
            "mss": {"value": round(mean(ratings), 2) if ratings else None,
                    "numerator": sum(ratings), "denominator": len(ratings)},
            "rsi": _rate(sum(repeat), len(repeat)),
            "failure_reasons": dict(Counter(s.reason_code for s in sessions if s.status == "FAILED")),
            "recommendation_feedback": {k: dict(v) for k, v in recommendation_feedback.items()},
            "sessions_not_due": sum(1 for result in results.values() if result == "NOT_DUE"),
            "sessions_disputed": sum(1 for result in results.values() if result == "DISPUTED"),
            "completed_with_feedback": completed_with_feedback,
            "min_completed_for_weight_test": MIN_COMPLETED_FOR_WEIGHT_TEST,
            "data_sufficient": completed_with_feedback >= MIN_COMPLETED_FOR_WEIGHT_TEST,
        }

    @staticmethod
    def score_analysis(db: Session, now: Optional[datetime] = None) -> List[dict]:
        """Hasil per rentang skor 10 poin (Day 9 bagian 8). Hubungan di sini korelasi, bukan sebab."""
        sessions, results, feedback_by_session = OutcomeService._snapshot(db, now)
        bands = defaultdict(lambda: {"due": 0, "completed": 0, "ratings": []})
        for s in sessions:
            result = results[s.session_id]
            if s.score_total is None or result not in ("COMPLETED", "NOT_HELD"):
                continue
            band = bands[min(int(s.score_total) // 10 * 10, 90)]
            band["due"] += 1
            if result == "COMPLETED":
                band["completed"] += 1
                band["ratings"] += OutcomeService._satisfaction(feedback_by_session[s.session_id])
        return [
            {"score_from": start, "score_to": 100 if start == 90 else start + 9,
             "sessions_due": band["due"], "sessions_completed": band["completed"],
             "mean_satisfaction": round(mean(band["ratings"]), 2) if band["ratings"] else None}
            for start, band in sorted(bands.items())
        ]

    @staticmethod
    def get_active_weights(db: Session) -> Dict[str, float]:
        """Bobot CS yang berlaku. Fitur 1 membaca dari sini."""
        latest = db.query(WeightVersion).order_by(WeightVersion.version_id.desc()).first()
        if not latest:
            return dict(DEFAULT_WEIGHTS)
        return {"t": latest.w_t, "g": latest.w_g, "s": latest.w_s, "d": latest.w_d, "m": latest.w_m}

    @staticmethod
    def set_weights(db: Session, weights: Weights, note: Optional[str] = None) -> WeightVersion:
        """Menetapkan bobot baru secara manual. Sengaja tidak punya endpoint: bobot tidak berubah otomatis."""
        version = WeightVersion(w_t=weights.t, w_g=weights.g, w_s=weights.s, w_d=weights.d,
                                w_m=weights.m, note=note)
        db.add(version)
        db.commit()
        db.refresh(version)
        return version

    @staticmethod
    def evaluate_weights(db: Session, candidate: Weights, test_from: datetime,
                         now: Optional[datetime] = None) -> dict:
        """Membandingkan bobot calon dengan bobot berlaku pada data uji: sesi yang berakhir sejak test_from.

        Ukuran yang dipakai: korelasi Pearson antara skor sesi dan rata-rata kepuasan anggotanya.
        """
        metrics = OutcomeService.compute_metrics(db, now)
        sessions, results, feedback_by_session = OutcomeService._snapshot(db, now)
        test_from = _utc_naive(test_from)
        rows = []
        for s in sessions:
            factors = (s.score_t, s.score_g, s.score_s, s.score_d, s.score_m)
            ratings = OutcomeService._satisfaction(feedback_by_session[s.session_id])
            if (results[s.session_id] == "COMPLETED" and s.scheduled_end >= test_from
                    and None not in factors and ratings):
                rows.append((factors, mean(ratings)))

        def pearson(w: Dict[str, float]) -> Optional[float]:
            scores = [w["t"] * f[0] + w["g"] * f[1] + w["s"] * f[2] + w["d"] * f[3] + w["m"] * f[4]
                      for f, _ in rows]
            try:
                return round(correlation(scores, [rating for _, rating in rows]), 4)
            except StatisticsError:  # data uji kurang dari dua sesi, atau semua nilainya sama
                return None

        current = OutcomeService.get_active_weights(db)
        sufficient = metrics["data_sufficient"]
        current_r = pearson(current) if sufficient else None
        candidate_r = pearson(candidate.model_dump()) if sufficient else None
        better = candidate_r > current_r if current_r is not None and candidate_r is not None else None
        return {
            "data_sufficient": sufficient,
            "completed_with_feedback": metrics["completed_with_feedback"],
            "test_sessions": len(rows),
            "current": {"weights": current, "correlation": current_r},
            "candidate": {"weights": candidate.model_dump(), "correlation": candidate_r},
            "candidate_better": better,
        }
