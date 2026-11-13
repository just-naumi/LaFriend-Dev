"""Uji alur website dari daftar sampai feedback, termasuk mode uji. Data memori, tanpa database file."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient

import web

c = TestClient(web.app)


def call(method, url, token=None, ok=200, **kw):
    r = c.request(method, url, headers={"Authorization": f"Bearer {token}"} if token else {}, **kw)
    assert r.status_code == ok, (url, r.status_code, r.text)
    return r.json()


def test_full_flow_alone():
    assert c.get("/api/state").status_code == 401
    call("POST", "/api/register", json={"name": "Sari Wulan", "email": "x", "password": "rahasia123"}, ok=422)
    token = call("POST", "/api/register", json={"name": "Sari Wulan", "email": "sari@kampus.ac.id",
                                                 "password": "rahasia123"})["token"]
    call("POST", "/api/register", json={"name": "Sari", "email": "SARI@kampus.ac.id", "password": "rahasia123"}, ok=400)
    st = call("GET", "/api/state", token)
    assert st["account"]["onboarding"] == "gmail" and not st["account"]["ready"], st["account"]

    call("POST", "/api/gmail", token, json={"email": "sari@yahoo.com"}, ok=400)
    assert call("POST", "/api/gmail", token, json={"email": "sari.w@gmail.com"})["account"]["onboarding"] == "profile"
    call("PUT", "/api/profile", token, json={"name": "Sari Wulan", "nim": "1201250001", "university": "Telkom University",
                                             "program": "S1 Teknik Komputer", "cohort": 2025}, ok=400)  # NIM milik Andi
    call("PUT", "/api/profile", token, json={"name": "Sari Wulan", "nim": "1201259999", "university": "Telkom University",
                                             "program": "S1 Teknik Komputer", "cohort": 2025})
    call("PUT", "/api/prefs", token, json={"learning_mode": "OFFLINE", "collaboration_style": "DISCUSSION",
                                           "group_size": [4, 2]}, ok=422)
    st = call("PUT", "/api/prefs", token, json={"learning_mode": "OFFLINE", "collaboration_style": "DISCUSSION",
                                                "group_size": [2, 4], "campus_area": "Gedung TULT"})
    assert st["account"]["ready"] and st["habits"]["collaboration_style"] == "DISCUSSION", st

    # Chat: preferensi onboarding ditawarkan sebagai kebiasaan
    d1 = (date.today() + timedelta(days=2)).isoformat()
    st = call("POST", "/api/assistant", token, json={"text": f"strukdat materi Binary Tree biar paham, {d1} jam 10.00-12.00"})
    assert st["chat"]["ask"] == "collaboration_style" and "Biasanya kamu diskusi" in st["chat"]["messages"][-1]["text"], st["chat"]
    for text in ("ya", "tatap muka", "2-4 orang"):
        st = call("POST", "/api/assistant", token, json={"text": text})
    assert st["chat"]["done"], st["chat"]
    form = st["chat"]["fields"]
    st = call("POST", "/api/intent", token, json=form)
    assert st["intent"] and st["chat"]["messages"] == [] and st["recommendations"], st

    # Fitur 2 sendirian lewat mode uji
    st = call("POST", "/api/group", token)
    f = st["formation"]
    others = [m["id"] for m in f["members"] if m["id"] != st["me"]["id"]]
    assert f["status"] == "DRAFT" and others, f
    for who in others:
        st = call("POST", "/api/test/act", token, json={"as_id": who, "action": "invite", "yes": True})
    assert st["formation"]["status"] == "CONFIRMATION_PENDING", st["formation"]
    call("POST", "/api/test/act", token, json={"as_id": st["me"]["id"], "action": "schedule", "yes": True}, ok=400)
    st = call("POST", "/api/schedule", token, json={"approve": True})
    for who in others:
        st = call("POST", "/api/test/act", token, json={"as_id": who, "action": "schedule", "yes": True})
    session = next(s for s in st["sessions"] if not s["finished"])

    # Fitur 3: feedback setelah sesi dianggap lewat
    st = call("POST", "/api/test/end", token, json={"session_id": session["id"]})
    assert next(s for s in st["sessions"] if s["id"] == session["id"])["finished"]
    body = {"session_id": session["id"], "data": {"session_held": True, "overall_satisfaction": 5, "repeat_intention": True}}
    call("POST", "/api/feedback", token, json=body)
    call("POST", "/api/feedback", token, json=body, ok=400)

    # Riwayat sekarang ikut membentuk kebiasaan
    assert call("GET", "/api/state", token)["habits"]["group_size"] == [2, 4]


def test_seed_login_and_intent_requires_verified():
    assert call("POST", "/api/login", json={"email": "andi@student.telkomuniversity.ac.id", "password": "salah"}, ok=401)
    st = call("POST", "/api/login", json={"email": "andi@student.telkomuniversity.ac.id", "password": "password123"})
    assert st["state"]["account"]["onboarding"] == "prefs", st["state"]["account"]
    token = call("POST", "/api/register", json={"name": "Tono", "email": "tono@kampus.ac.id", "password": "rahasia123"})["token"]
    d1 = (date.today() + timedelta(days=2)).isoformat()
    form = dict(course_id="Struktur Data", topics="Heap", learning_goal="UNDERSTAND", collaboration_style="DISCUSSION",
                learning_mode="OFFLINE", earliest_date=d1, latest_date=d1, min_group_size=2, max_group_size=4,
                availabilities=[dict(day_or_date=d1, start_time="10:00", end_time="12:00")])
    call("POST", "/api/intent", token, json=form, ok=403)
    call("POST", "/api/logout", token)
    assert c.get("/api/state", headers={"Authorization": f"Bearer {token}"}).status_code == 401


if __name__ == "__main__":
    tests = [test_full_flow_alone, test_seed_login_and_intent_requires_verified]
    for t in tests:
        t()
        print(f"[OK] {t.__name__}")
    print(f"Semua {len(tests)} uji website lolos.")
