"""Halaman cek untuk Fitur 1, 2, dan 3. Jalankan: python demo_ui.py, lalu buka http://127.0.0.1:8010

Berdiri sendiri: tidak memakai app/main.py dan tidak menyentuh database/lafriend.db.
Data Fitur 3 disimpan di database memori dan hilang saat program berhenti.
"""
import sys
import uuid
from datetime import timedelta
from itertools import combinations
from pathlib import Path
from statistics import mean
from types import SimpleNamespace as NS

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401, mendaftarkan semua tabel ke Base
from app.database import Base
from app.schemas import SessionFeedbackIn
from app import group_formation as G
from app import matching as M
from app.outcome import OutcomeService as S, _now

RABU = {"day": "Wednesday", "start": "09:00", "end": "12:00", "rank": 1}
JUMAT = {"day": "Friday", "start": "13:00", "end": "16:00", "rank": 2}


def person(pid, name, **changes):
    base = {"id": pid, "name": name, "course": "Struktur Data", "topics": "Binary Tree", "goal": "UNDERSTAND",
            "style": "DISCUSSION", "mode": "OFFLINE", "alt_modes": "", "earliest": "2026-11-12",
            "latest": "2026-11-18", "min": 2, "max": 4, "status": "ACTIVE", "verified": "VERIFIED",
            "account": "ACTIVE", "slots": [RABU, JUMAT]}
    return {**base, **changes}


# Andi dan Budi mengikuti contoh Plan/Day4.MD. Yang lain dibuat agar tiap cabang keputusan terlihat.
DEFAULT_SCENARIO = {
    "people": [
        person("andi", "Andi", min=3),
        person("budi", "Budi", topics="Binary Tree, BST",
               slots=[{"day": "Wednesday", "start": "10:00", "end": "12:00", "rank": 1}, JUMAT]),
        person("citra", "Citra", goal="PRACTICE", style="PRACTICE"),
        person("deni", "Deni", topics="Binary Tree, AVL Tree", style="FOCUS_STUDY", max=3),
        person("eko", "Eko", mode="ONLINE"),
        person("fajar", "Fajar", course="Pemrograman Web"),
        person("gita", "Gita", earliest="2026-11-20", latest="2026-11-25"),
        person("hana", "Hana", slots=[{"day": "Monday", "start": "09:00", "end": "12:00", "rank": 1}]),
        person("indra", "Indra", mode="HYBRID", goal="EXAM_PREP",
               slots=[{"day": "Wednesday", "start": "11:00", "end": "14:00", "rank": 2}]),
        # Anggota sesi yang sudah ada. Intent mereka CONVERTED, jadi tidak muncul sebagai calon partner.
        person("jaka", "Jaka", status="CONVERTED"),
        person("kiki", "Kiki", status="CONVERTED", goal="PRACTICE"),
        person("lina", "Lina", status="CONVERTED", topics="Sorting"),
        person("mira", "Mira", status="CONVERTED"),
        person("nando", "Nando", status="CONVERTED"),
    ],
    # Contoh Plan/Day5.MD: Sesi A lolos, Sesi B gugur karena materinya Sorting, Sesi C gugur karena penuh.
    "sessions": [
        {"name": "Sesi A", "max_size": 4, "members": ["jaka", "kiki"]},
        {"name": "Sesi B", "max_size": 4, "members": ["lina"]},
        {"name": "Sesi C", "max_size": 2, "members": ["mira", "nando"]},
    ],
}

app = FastAPI(title="LaFriend: halaman cek")
STATE = {}


def reset_state():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    # Tabel students dibiarkan kosong: database memori ini tidak memeriksa foreign key
    STATE.clear()
    STATE["db"] = sessionmaker(bind=engine)()


reset_state()


def to_intent(p: dict) -> NS:
    return NS(student_id=p["id"], name=p["name"], course_id=p["course"], topics=p["topics"],
              learning_goal=p["goal"], collaboration_style=p["style"], learning_mode=p["mode"],
              alternative_modes=p.get("alt_modes", ""), earliest_date=p["earliest"], latest_date=p["latest"],
              min_group_size=int(p["min"]), max_group_size=int(p["max"]), status=p.get("status", "ACTIVE"),
              student=NS(verification_status=p.get("verified", "VERIFIED"), account_status=p.get("account", "ACTIVE")),
              availabilities=[NS(day_or_date=s["day"], start_time=s["start"], end_time=s["end"],
                                 priority_rank=int(s.get("rank", 1))) for s in p["slots"]])


def load(scenario: dict, seeker_id: str):
    try:
        intents = {p["id"]: to_intent(p) for p in scenario["people"]}
        sessions = [NS(name=s["name"], max_size=int(s["max_size"]), members=[intents[m] for m in s["members"]])
                    for s in scenario.get("sessions", [])]
        return intents[seeker_id], list(intents.values()), sessions
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"Data skenario tidak lengkap atau salah: {error!r}")


def proposal_view(p: dict) -> dict:
    view = {"status": p["status"], "reason_code": p.get("reason_code"), "trace": p.get("trace", []),
            "members": [{"id": m.student_id, "name": m.name, "intent_status": m.status} for m in p["members"]]}
    if "slots" in p:
        view.update(accepted=p["accepted"], slots=p["slots"], slot_index=p["slot_index"], gq=p["gq"],
                    min_group=p["min_group"], max_group=p["max_group"], session_id=STATE.get("session_id"))
    return view


def report(proposal: dict) -> dict:
    """Melapor ke Fitur 3 saat kelompok gagal atau dikonfirmasi."""
    db, session_id = STATE["db"], STATE["session_id"]
    host = proposal["members"][0]
    # Yang sudah keluar dari kelompok ini tidak diundang lagi sebagai pengganti
    kept = {m.student_id for m in proposal["members"]}
    gone = {m.student_id for m in (STATE.get("proposal") or proposal)["members"]} - kept
    STATE["pool"] = [c for c in STATE["pool"] if c.student_id not in gone]
    if proposal["status"] == "DRAFT":
        # Anggota baru, termasuk pengganti, dicatat sebagai undangan terkirim
        for member in proposal["members"][1:]:
            if member.student_id not in STATE["invited"]:
                STATE["invited"].add(member.student_id)
                S.record_event(db, host.student_id, "INVITATION_SENT", session_id=session_id,
                               match_id=f"{host.student_id}:{member.student_id}")
    if proposal["status"] == "FAILED":
        S.fail_formation(db, session_id, proposal["reason_code"])
    elif proposal["status"] == "CONFIRMED":
        # shortcut: jadwal dianggap sudah lewat agar feedback bisa langsung diisi, pakai waktu sesi asli saat integrasi
        S.confirm_session(db, session_id, _now() - timedelta(minutes=1), [m.student_id for m in proposal["members"]])
    STATE["proposal"] = proposal
    return proposal_view(proposal)


def current(status: str) -> dict:
    proposal = STATE.get("proposal")
    if not proposal or proposal["status"] != status:
        raise HTTPException(status_code=400, detail=f"Langkah ini butuh proposal berstatus {status}")
    return proposal


@app.get("/")
def page():
    return FileResponse(backend_dir / "demo_ui.html")


@app.get("/api/scenario")
def scenario():
    return DEFAULT_SCENARIO


@app.post("/api/match")
def match(scenario: dict = Body(...), seeker_id: str = Body(...)):
    """Fitur 1: syarat wajib, lima nilai, CS, lalu sesi dulu dan partner sebagai cadangan."""
    seeker, intents, sessions = load(scenario, seeker_id)
    weights = S.get_active_weights(STATE["db"])
    rows = []
    for other in intents:
        if other.student_id == seeker.student_id:
            continue
        reason = "NOT_ACTIVE" if other.status != "ACTIVE" else M.hard_constraint(seeker, other)
        scores = None if reason else M.compatibility(seeker, other, weights)
        rows.append({"id": other.student_id, "name": other.name, "reason": reason, "scores": scores})
    partners = M.match_partners(seeker, intents, weights)
    # Halaman ini menampilkan daftar partner walau ada sesi yang lolos, jadi semuanya dicatat sebagai dilihat
    for item in partners:
        S.record_viewed(STATE["db"], seeker.student_id, f"{seeker.student_id}:{item['intent'].student_id}")
    return {
        "weights": weights, "candidates": rows, "type": M.recommend(seeker, sessions, intents, weights)["type"],
        "sessions": [{"name": r["session"].name, "total": r["total"], "seats_left": r["seats_left"]}
                     for r in M.match_sessions(seeker, sessions, weights)],
        "partners": [{"id": r["intent"].student_id, "name": r["intent"].name, "total": r["total"]} for r in partners],
    }


@app.post("/api/group")
def group(scenario: dict = Body(...), seeker_id: str = Body(...)):
    """Fitur 2: pencari menjadi host, lalu calon dari Fitur 1 dicoba satu per satu."""
    host, intents, _ = load(scenario, seeker_id)
    db, weights = STATE["db"], S.get_active_weights(STATE["db"])
    pool = [r["intent"] for r in M.match_partners(host, intents, weights, limit=len(intents))]
    proposal = G.build_group([host], pool, weights)
    STATE.update(pool=pool, weights=weights, session_id=str(uuid.uuid4()), invited=set(), proposal=None)
    pairs = [M.compatibility(a, b, weights) for a, b in combinations(proposal["members"], 2)]
    scores = {k: mean(p[k] for p in pairs) for k in "tgsdm"} if pairs else {}
    S.start_formation(db, STATE["session_id"], host.student_id, {"total": proposal.get("gq"), **scores})
    return report(proposal)


@app.post("/api/invites")
def invites(answers: dict = Body(..., embed=True)):
    try:
        return report(G.answer_invitations(current("DRAFT"), answers, STATE["pool"], STATE["weights"]))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/api/schedule")
def schedule(approvals: dict = Body(..., embed=True)):
    return report(G.answer_schedule(current("CONFIRMATION_PENDING"), approvals, STATE["pool"], STATE["weights"]))


@app.post("/api/feedback")
def feedback(student_id: str = Body(...), data: SessionFeedbackIn = Body(...)):
    """Fitur 3: Session Feedback untuk sesi yang baru dikonfirmasi."""
    current("CONFIRMED")
    S.save_session_feedback(STATE["db"], student_id, STATE["session_id"], data)
    return metrics()


@app.get("/api/metrics")
def metrics():
    return {"metrics": S.compute_metrics(STATE["db"]), "analysis": S.score_analysis(STATE["db"])}


@app.post("/api/reset")
def reset():
    reset_state()
    return metrics()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8010)
