"""Website LaFriend untuk mahasiswa. Jalankan: python web.py, lalu buka http://127.0.0.1:8020

Memakai logika asli Fitur 1, 2, dan 3 di app/services. Berdiri sendiri: tidak memakai app/main.py
dan tidak menyentuh database/lafriend.db. Tampilan ada di ../frontend (React), dibangun ke web/dist.
"""
# shortcut: intent, kelompok, dan undangan disimpan di memori dan hilang saat program berhenti,
# ganti dengan tabel study_sessions dan invitations saat integrasi backend
import secrets
import sys
import uuid
from datetime import date, datetime, timedelta
from itertools import combinations
from pathlib import Path
from statistics import mean
from types import SimpleNamespace as NS
from typing import Literal, Optional

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

import uvicorn
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401, mendaftarkan semua tabel ke Base
from app.routes import hash_password, verify_password
from app.database import Base
from app.main import seed_data_awal
from app.models import Course
from app.schemas import SessionFeedbackIn
from app.schemas import StudyIntentCreate
from app import group_formation as G
from app import intent_assistant as AI
from app import matching as M
from app.outcome import OutcomeService as S, _now

WEB_DIR = backend_dir / "web" / "dist"
WIB = timedelta(hours=7)
RUNNING = ("ACTIVE", "GROUP_FORMING", "JOIN_PENDING")
# Mahasiswa contoh untuk mode uji (seeder main hanya berisi Andi). Password semua: password123
INITIAL_STUDENTS = [
    {
        "full_name": "Andi Pratama",
        "email": "andi@student.telkomuniversity.ac.id",
        "student_number": "1201250001",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Budi Santoso",
        "email": "budi@student.telkomuniversity.ac.id",
        "student_number": "1201250002",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Citra Dewi",
        "email": "citra@student.telkomuniversity.ac.id",
        "student_number": "1201250003",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Nadia Putri",
        "email": "nadia@student.telkomuniversity.ac.id",
        "student_number": "1201250004",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Fadly Rahman",
        "email": "fadly@student.telkomuniversity.ac.id",
        "student_number": "1201250005",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2025,
        "password": "password123",
    },
    {
        "full_name": "Raka Aditya",
        "email": "raka@student.telkomuniversity.ac.id",
        "student_number": "1201250006",
        "study_program": "S1 Teknik Komputer",
        "academic_year": 2024,
        "password": "password123",
    },
]
PEOPLE = {"andi": "Andi", "budi": "Budi", "citra": "Citra", "nadia": "Nadia", "fadly": "Fadly", "raka": "Raka"}
# Akun contoh dari seeder (email dan password sama). Universitas diambil dari domain email seeder.
ACCOUNTS = {s["email"].split("@")[0]: {
    "id": s["email"].split("@")[0], "email": s["email"], "password_hash": hash_password(s["password"]),
    "name": s["full_name"], "nim": s["student_number"], "university": "Telkom University",
    "program": s["study_program"], "cohort": s["academic_year"], "gmail": None, "verified": True,
    "prefs": None} for s in INITIAL_STUDENTS}
TOKENS, CHATS = {}, {}
EMAIL = r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$"

app = FastAPI(title="LaFriend")
WEB_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets"), check_dir=False), name="assets")
INTENTS, FORMATIONS, VIEWED = [], [], set()
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(bind=engine)
DB = sessionmaker(bind=engine)()  # tabel students kosong: database memori ini tidak memeriksa foreign key

# Katalog mata kuliah sama dengan seeder main (kurikulum S1 Teknik Komputer), diisi ke database memori terpisah
_catalog_engine = create_engine("sqlite://", poolclass=StaticPool)
Base.metadata.create_all(bind=_catalog_engine)
with sessionmaker(bind=_catalog_engine)() as _catalog:
    seed_data_awal(_catalog)
    COURSES = [c.course_name for c in _catalog.query(Course).all()]


def add_intent(student_id: str, data: StudyIntentCreate) -> NS:
    intent = NS(student_id=student_id, name=PEOPLE[student_id], course_id=data.course_id, topics=data.topics,
                learning_goal=data.learning_goal, collaboration_style=data.collaboration_style,
                learning_mode=data.learning_mode, earliest_date=data.earliest_date, latest_date=data.latest_date,
                min_group_size=data.min_group_size, max_group_size=data.max_group_size, status="ACTIVE",
                student=NS(verification_status="VERIFIED" if ACCOUNTS[student_id]["verified"] else "PENDING",
                           account_status="ACTIVE"),
                availabilities=[NS(**slot.model_dump()) for slot in data.availabilities])
    INTENTS.append(intent)
    return intent


def running_intent(student_id: str) -> Optional[NS]:
    return next((i for i in INTENTS if i.student_id == student_id and i.status in RUNNING), None)


def my_formation(student_id: str) -> Optional[dict]:
    """Kelompok terakhir yang memuat mahasiswa ini dan belum selesai, atau yang baru saja gagal miliknya."""
    for formation in reversed(FORMATIONS):
        proposal = formation["proposal"]
        members = [m.student_id for m in proposal["members"]]
        if proposal["status"] in ("DRAFT", "CONFIRMATION_PENDING") and student_id in members:
            return formation
        if proposal["status"] == "FAILED" and members[0] == student_id and not formation.get("seen"):
            return formation
    return None


def session_end(slot: dict) -> datetime:
    """Waktu sesi selesai dalam UTC. Jam di jadwal adalah WIB."""
    return datetime.fromisoformat(f"{slot['day']}T{slot['end_time']}") - WIB


def settle(formation: dict, proposal: dict) -> None:
    """Menyimpan hasil satu langkah Fitur 2 dan melapor ke Fitur 3."""
    old = formation.get("proposal") or proposal
    host = proposal["members"][0]
    kept = {m.student_id for m in proposal["members"]}
    gone = {m.student_id for m in old["members"]} - kept
    # Yang sudah keluar dari kelompok ini tidak diundang lagi sebagai pengganti
    formation["pool"] = [c for c in formation["pool"] if c.student_id not in gone]
    changed = gone or proposal.get("slot_index") != old.get("slot_index") or len(kept) != len(old["members"])
    if changed:
        formation["approvals"] = {}
    if proposal["status"] == "DRAFT":
        for member in proposal["members"][1:]:
            if member.student_id not in formation["invited"]:
                formation["invited"].add(member.student_id)
                S.record_event(DB, host.student_id, "INVITATION_SENT", session_id=formation["id"],
                               match_id=f"{host.student_id}:{member.student_id}")
    elif proposal["status"] == "FAILED":
        S.fail_formation(DB, formation["id"], proposal["reason_code"])
    elif proposal["status"] == "CONFIRMED":
        S.confirm_session(DB, formation["id"], session_end(proposal["slots"][proposal["slot_index"]]),
                          [m.student_id for m in proposal["members"]])
    formation["proposal"] = proposal


def start_group(host: NS) -> dict:
    weights = S.get_active_weights(DB)
    pool = [r["intent"] for r in M.match_partners(host, INTENTS, weights, limit=len(INTENTS))]
    proposal = G.build_group([host], pool, weights)
    formation = {"id": str(uuid.uuid4()), "pool": pool, "weights": weights, "invited": set(), "approvals": {}}
    pairs = [M.compatibility(a, b, weights) for a, b in combinations(proposal["members"], 2)]
    scores = {k: mean(p[k] for p in pairs) for k in "tgsdm"} if pairs else {}
    S.start_formation(DB, formation["id"], host.student_id, {"total": proposal.get("gq"), **scores})
    settle(formation, proposal)
    FORMATIONS.append(formation)
    return formation


def answer_invite(formation: dict, student_id: str, answer: str) -> None:
    settle(formation, G.answer_invitations(formation["proposal"], {student_id: answer},
                                           formation["pool"], formation["weights"]))


def answer_schedule(formation: dict, student_id: str, approve: bool) -> None:
    formation["approvals"][student_id] = approve
    proposal = formation["proposal"]
    # Menunggu semua anggota menjawab, supaya yang belum menjawab tidak dianggap menolak
    if all(m.student_id in formation["approvals"] for m in proposal["members"]):
        settle(formation, G.answer_schedule(proposal, formation["approvals"], formation["pool"], formation["weights"]))


def day_slots(intent: NS, day: str) -> list:
    d = date.fromisoformat(day)
    return [[M._hhmm(s["start"]), M._hhmm(s["end"])] for s in M._dated_slots(intent, d, d)]


def recommendations(me: NS) -> list:
    weights = S.get_active_weights(DB)
    items = []
    for r in M.match_partners(me, INTENTS, weights):
        other = r["intent"]
        key = f"{me.student_id}:{other.student_id}"
        if key not in VIEWED:
            VIEWED.add(key)
            S.record_viewed(DB, me.student_id, key)
        day = r["proposed_slot"]["day"]
        shared = sorted(M.normalize_topics(me.topics) & M.normalize_topics(other.topics))
        items.append({"id": other.student_id, "name": other.name, "total": r["total"],
                      "scores": {k: r[k] for k in "tgsdm"}, "slot": r["proposed_slot"], "shared_topics": shared,
                      "topics": other.topics, "goal": other.learning_goal, "style": other.collaboration_style,
                      "mode": other.learning_mode, "mine": day_slots(me, day), "theirs": day_slots(other, day)})
    return items


def intent_view(intent: NS) -> dict:
    return {"course": intent.course_id, "topics": intent.topics, "goal": intent.learning_goal,
            "style": intent.collaboration_style, "mode": intent.learning_mode, "earliest": intent.earliest_date,
            "latest": intent.latest_date, "min": intent.min_group_size, "max": intent.max_group_size,
            "status": intent.status,
            "slots": [{"day": a.day_or_date, "start": a.start_time, "end": a.end_time, "rank": a.priority_rank}
                      for a in intent.availabilities]}


def formation_view(formation: dict, me: str) -> dict:
    p = formation["proposal"]
    view = {"status": p["status"], "reason_code": p.get("reason_code"), "is_host": p["members"][0].student_id == me,
            "members": [{"id": m.student_id, "name": m.name, "host": i == 0,
                         "accepted": m.student_id in p.get("accepted", []),
                         "approved": formation["approvals"].get(m.student_id)}
                        for i, m in enumerate(p["members"])]}
    if "slots" in p:
        view.update(slot=p["slots"][p["slot_index"]], slot_number=p["slot_index"] + 1, slot_count=len(p["slots"]),
                    gq=p["gq"], my_invite_pending=me not in p["accepted"],
                    my_approval=formation["approvals"].get(me))
    return view


def sessions_view(me: str) -> list:
    out = []
    for formation in FORMATIONS:
        p = formation["proposal"]
        if p["status"] != "CONFIRMED" or me not in [m.student_id for m in p["members"]]:
            continue
        slot = p["slots"][p["slot_index"]]
        out.append({"id": formation["id"], "slot": slot, "course": p["members"][0].course_id,
                    "topics": p["members"][0].topics, "members": [m.name for m in p["members"]],
                    "finished": formation.get("ended") or session_end(slot) <= _now(), "feedback_given": me in formation.get("feedback", set())})
    return out


def student(authorization: Optional[str]) -> str:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token not in TOKENS:
        raise HTTPException(status_code=401, detail="Masuk dulu ke akunmu")
    return TOKENS[token]


def past_intents(me: str) -> list:
    return [{"collaboration_style": i.collaboration_style, "learning_mode": i.learning_mode,
             "min_group_size": i.min_group_size, "max_group_size": i.max_group_size,
             "availabilities": [vars(a) for a in i.availabilities]} for i in INTENTS if i.student_id == me]


def usual(me: str) -> dict:
    """Kebiasaan untuk asisten: riwayat permintaan dulu, preferensi onboarding sebagai cadangan."""
    prefs = ACCOUNTS[me]["prefs"] or {}
    base = {k: prefs[k] for k in ("collaboration_style", "learning_mode") if prefs.get(k)}
    if prefs.get("group_size"):
        base["group_size"] = tuple(prefs["group_size"])
    return AI.habits(past_intents(me), base)


def account_view(me: str) -> dict:
    a = ACCOUNTS[me]
    ready = a["verified"] and a["nim"] and a["prefs"]
    step = "gmail" if not a["verified"] else "profile" if not a["nim"] else "prefs" if not a["prefs"] else None
    return {k: a[k] for k in ("id", "email", "name", "nim", "university", "program", "cohort", "gmail",
                              "verified", "prefs")} | {"ready": bool(ready), "onboarding": step}


def chat_view(me: str) -> dict:
    c = CHATS.get(me)
    if not c:
        return {"messages": [], "fields": {}, "done": False, "ask": None, "suggest": None, "confirm": False}
    return {"messages": c["messages"], "fields": AI.to_form(c["state"]["fields"]), "done": c["state"]["done"],
            "ask": c["state"]["ask"], "suggest": bool(c["state"]["suggest"]), "confirm": bool(c["state"]["confirm"])}


@app.get("/")
def page():
    return FileResponse(WEB_DIR / "index.html")


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=EMAIL, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=120)
    password: str = Field(min_length=1, max_length=128)


class Prefs(BaseModel):
    learning_mode: Literal["OFFLINE", "ONLINE", "HYBRID"]
    collaboration_style: Literal["DISCUSSION", "PRACTICE", "TEACHING", "FOCUS_STUDY"]
    group_size: tuple[int, int]
    language: Literal["id", "en"] = "id"
    campus_area: str = Field(default="", max_length=60)


class Profile(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    nim: str = Field(pattern=r"^\d{6,15}$")
    university: str = Field(min_length=2, max_length=100)
    program: str = Field(min_length=2, max_length=100)
    cohort: int = Field(ge=2000, le=2100)


def login_token(me: str) -> dict:
    token = secrets.token_urlsafe(24)
    TOKENS[token] = me
    return {"token": token, "state": view(me)}


@app.post("/api/register")
def register(data: Register):
    email = data.email.lower()
    if any(a["email"] == email for a in ACCOUNTS.values()):
        raise HTTPException(status_code=400, detail="Email ini sudah terdaftar. Masuk saja.")
    me = uuid.uuid4().hex[:8]
    ACCOUNTS[me] = {"id": me, "email": email, "password_hash": hash_password(data.password), "name": data.name.strip(),
                    "nim": None, "university": None, "program": None, "cohort": None, "gmail": None,
                    "verified": False, "prefs": None}
    PEOPLE[me] = data.name.strip().split()[0]
    return login_token(me)


@app.post("/api/login")
def login(data: Login):
    account = next((a for a in ACCOUNTS.values() if a["email"] == data.email.lower()), None)
    if not account or not verify_password(data.password, account["password_hash"]):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    return login_token(account["id"])


@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    TOKENS.pop((authorization or "").removeprefix("Bearer ").strip(), None)
    return {"ok": True}


@app.post("/api/gmail")
def link_gmail(email: str = Body(..., embed=True, pattern=EMAIL, max_length=120), authorization: Optional[str] = Header(None)):
    # shortcut: tiruan tanpa OAuth, akun langsung dianggap terverifikasi; ganti dengan OAuth Google + cek domain kampus
    me = student(authorization)
    if not email.lower().endswith("@gmail.com"):
        raise HTTPException(status_code=400, detail="Pakai alamat @gmail.com")
    ACCOUNTS[me].update(gmail=email.lower(), verified=True)
    return view(me)


@app.put("/api/profile")
def save_profile(data: Profile, authorization: Optional[str] = Header(None)):
    me = student(authorization)
    if any(a["nim"] == data.nim and a["id"] != me for a in ACCOUNTS.values()):
        raise HTTPException(status_code=400, detail="NIM ini sudah dipakai akun lain")
    ACCOUNTS[me].update(data.model_dump())
    PEOPLE[me] = data.name.strip().split()[0]
    return view(me)


@app.put("/api/prefs")
def save_prefs(data: Prefs, authorization: Optional[str] = Header(None)):
    me = student(authorization)
    lo, hi = data.group_size
    if not 2 <= lo <= hi <= 4:
        raise HTTPException(status_code=422, detail="Ukuran kelompok harus 2 sampai 4 orang")
    ACCOUNTS[me]["prefs"] = data.model_dump()
    return view(me)


@app.post("/api/assistant")
def assistant(text: str = Body(..., embed=True, min_length=1, max_length=500), authorization: Optional[str] = Header(None)):
    me = student(authorization)
    chat = CHATS.setdefault(me, {"state": {**AI.new_state(), "done": False}, "messages": []})
    chat["state"] = AI.chat_turn(chat["state"], text, COURSES, usual(me), date.today())
    chat["messages"] += [{"from": "me", "text": text}, {"from": "bot", "text": chat["state"]["reply"]}]
    return view(me)


@app.post("/api/assistant/reset")
def assistant_reset(authorization: Optional[str] = Header(None)):
    me = student(authorization)
    CHATS.pop(me, None)
    return view(me)


@app.post("/api/test/act")
def test_act(as_id: str = Body(...), action: Literal["invite", "schedule"] = Body(...), yes: bool = Body(...),
             authorization: Optional[str] = Header(None)):
    """Mode uji: menjawab undangan atau jadwal atas nama anggota lain, supaya Fitur 2 bisa dicoba sendirian."""
    me = student(authorization)
    formation = my_formation(me)
    if not formation or as_id not in [m.student_id for m in formation["proposal"]["members"]] or as_id == me:
        raise HTTPException(status_code=400, detail="Orang ini bukan anggota lain di kelompokmu")
    status = formation["proposal"]["status"]
    if action == "invite" and status == "DRAFT" and as_id not in formation["proposal"]["accepted"]:
        answer_invite(formation, as_id, "ACCEPTED" if yes else "REJECTED")
    elif action == "schedule" and status == "CONFIRMATION_PENDING" and as_id not in formation["approvals"]:
        answer_schedule(formation, as_id, yes)
    else:
        raise HTTPException(status_code=400, detail="Tidak ada yang menunggu jawaban orang ini")
    return view(me)


@app.post("/api/test/end")
def test_end(session_id: str = Body(..., embed=True), authorization: Optional[str] = Header(None)):
    """Mode uji: anggap sesi sudah lewat, supaya feedback Fitur 3 bisa diisi tanpa menunggu."""
    me = student(authorization)
    formation = next((f for f in FORMATIONS if f["id"] == session_id), None)
    if not formation or me not in [m.student_id for m in formation["proposal"]["members"]]:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")
    if formation["proposal"]["status"] != "CONFIRMED":
        raise HTTPException(status_code=400, detail="Sesi ini belum terkonfirmasi")
    formation["ended"] = True
    S._get_session(DB, session_id).scheduled_end = _now() - timedelta(minutes=1)  # Fitur 3 memeriksa jam ini
    DB.commit()
    return view(me)


@app.get("/api/state")
def state(authorization: Optional[str] = Header(None)):
    return view(student(authorization))


def view(me: str) -> dict:
    intent, formation = running_intent(me), my_formation(me)
    return {
        "me": {"id": me, "name": PEOPLE[me]}, "account": account_view(me), "habits": usual(me),
        "chat": chat_view(me), "people": PEOPLE, "courses": COURSES,
        "today": date.today().isoformat(), "weights": S.get_active_weights(DB),
        "intent": intent_view(intent) if intent else None,
        "recommendations": recommendations(intent) if intent and intent.status == "ACTIVE" else [],
        "formation": formation_view(formation, me) if formation else None,
        "sessions": sessions_view(me),
        "metrics": S.compute_metrics(DB),
    }


@app.post("/api/intent")
def create_intent(data: StudyIntentCreate, authorization: Optional[str] = Header(None)):
    me = student(authorization)
    if data.course_id not in COURSES:
        raise HTTPException(status_code=400, detail="Mata kuliah tidak ada di katalog")
    if running_intent(me):
        raise HTTPException(status_code=400, detail="Kamu masih punya permintaan belajar yang berjalan")
    if not ACCOUNTS[me]["verified"]:
        raise HTTPException(status_code=403, detail="Hubungkan akun Gmail dulu supaya akunmu terverifikasi")
    add_intent(me, data)
    CHATS.pop(me, None)
    return view(me)


@app.post("/api/intent/cancel")
def cancel_intent(authorization: Optional[str] = Header(None)):
    me = student(authorization)
    intent = running_intent(me)
    if not intent or intent.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Permintaan hanya bisa dibatalkan selama belum masuk kelompok")
    intent.status = "CANCELLED"
    return view(me)


@app.post("/api/group")
def group(authorization: Optional[str] = Header(None)):
    me = student(authorization)
    intent = running_intent(me)
    if not intent or intent.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Buat permintaan belajar dulu, atau selesaikan kelompok yang berjalan")
    for old in FORMATIONS:
        if old["proposal"]["members"][0].student_id == me:
            old["seen"] = True
    start_group(intent)
    return view(me)


@app.post("/api/invite")
def invite(answer: Literal["ACCEPTED", "REJECTED"] = Body(..., embed=True), authorization: Optional[str] = Header(None)):
    me = student(authorization)
    formation = my_formation(me)
    if not formation or formation["proposal"]["status"] != "DRAFT" or me in formation["proposal"]["accepted"]:
        raise HTTPException(status_code=400, detail="Tidak ada undangan yang menunggu jawabanmu")
    answer_invite(formation, me, answer)
    return view(me)


@app.post("/api/schedule")
def schedule(approve: bool = Body(..., embed=True), authorization: Optional[str] = Header(None)):
    me = student(authorization)
    formation = my_formation(me)
    if not formation or formation["proposal"]["status"] != "CONFIRMATION_PENDING":
        raise HTTPException(status_code=400, detail="Belum ada jadwal yang menunggu persetujuanmu")
    answer_schedule(formation, me, approve)
    return view(me)


@app.post("/api/feedback")
def feedback(session_id: str = Body(...), data: SessionFeedbackIn = Body(...), authorization: Optional[str] = Header(None)):
    me = student(authorization)
    formation = next((f for f in FORMATIONS if f["id"] == session_id), None)
    if not formation or me not in [m.student_id for m in formation["proposal"]["members"]]:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")
    if me in formation.get("feedback", set()):
        raise HTTPException(status_code=400, detail="Kamu sudah mengisi penilaian sesi ini")
    S.save_session_feedback(DB, me, session_id, data)
    formation.setdefault("feedback", set()).add(me)
    return view(me)


def seed() -> None:
    """Data contoh: satu sesi minggu lalu yang sudah selesai, dan empat permintaan belajar minggu ini."""
    today = date.today()

    def intent(who, start, end, slots, **changes):
        base = dict(course_id="Struktur Data", topics="Binary Tree", learning_goal="UNDERSTAND",
                    collaboration_style="DISCUSSION", learning_mode="OFFLINE",
                    earliest_date=start.isoformat(), latest_date=end.isoformat(),
                    availabilities=[dict(day_or_date=d.isoformat(), start_time=s, end_time=e, priority_rank=n + 1)
                                    for n, (d, s, e) in enumerate(slots)])
        return add_intent(who, StudyIntentCreate(**{**base, **changes}))

    # Sesi minggu lalu: Nadia (host), Fadly, Raka. Raka belum mengisi feedback.
    past = today - timedelta(days=3)
    week = (past - timedelta(days=3), past)
    old = [intent(who, *week, [(past, "13:00", "15:00")], topics="Graph", min_group_size=3)
           for who in ("nadia", "fadly", "raka")]
    real_today, M._today = M._today, lambda: week[0]  # sesi contoh ini dibentuk "minggu lalu"
    try:
        formation = start_group(old[0])
        for who in ("fadly", "raka"):
            answer_invite(formation, who, "ACCEPTED")
        for who in ("nadia", "fadly", "raka"):
            answer_schedule(formation, who, True)
    finally:
        M._today = real_today
    for who, satisfaction, again in (("nadia", 5, True), ("fadly", 4, True)):
        S.save_session_feedback(DB, who, formation["id"], SessionFeedbackIn(
            session_held=True, overall_satisfaction=satisfaction, repeat_intention=again))
        formation.setdefault("feedback", set()).add(who)

    # Permintaan minggu ini. Andi dan Raka belum punya permintaan.
    d1, d2, d3 = (today + timedelta(days=n) for n in (2, 3, 5))
    span = (today, today + timedelta(days=6))
    intent("budi", *span, [(d1, "10:00", "12:00"), (d3, "13:00", "16:00")], topics="Binary Tree, BST")
    intent("citra", *span, [(d1, "09:00", "12:00"), (d2, "15:00", "17:00")],
           learning_goal="PRACTICE", collaboration_style="PRACTICE")
    intent("nadia", *span, [(d2, "09:00", "11:00"), (d1, "11:00", "14:00")],
           topics="Binary Tree, AVL Tree", learning_goal="EXAM_PREP", learning_mode="HYBRID")
    intent("fadly", *span, [(d3, "13:00", "15:00")], topics="Heap", collaboration_style="FOCUS_STUDY")


seed()


@app.get("/{path:path}")
def spa(path: str):
    # Halaman React: semua alamat selain /api dan /assets memakai index.html yang sama
    if path.startswith("api/"):
        raise HTTPException(status_code=404)
    return FileResponse(WEB_DIR / "index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8020)
