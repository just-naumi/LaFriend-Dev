"""Uji Fitur 3 dengan angka contoh Plan/Day9.MD. Memakai database di memori, bukan lafriend.db."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.routes import create_token, hash_password
from app.models import Feedback
from app.models import Student
from app.schemas import SessionFeedbackIn, Weights
from app.outcome import OutcomeService as S, DEFAULT_WEIGHTS

NOW = datetime.now(timezone.utc).replace(tzinfo=None)
PAST = NOW - timedelta(days=1)
FUTURE = NOW + timedelta(days=1)


def new_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    ids = {}
    for name in ("andi", "budi", "citra", "nadia"):
        student = Student(full_name=name, email=f"{name}@x.ac.id", student_number=name,
                          password_hash=hash_password("x"))
        db.add(student)
        db.flush()
        ids[name] = student.student_id
    db.commit()
    return db, ids


def confirmed(db, sid, host, members, end, scores=None):
    S.start_formation(db, sid, host, scores)
    return S.confirm_session(db, sid, end, members)


def held(db, sid, student, session_held=True, **answers):
    return S.save_session_feedback(db, student, sid, SessionFeedbackIn(session_held=session_held, **answers))


def expect_error(code, fn, *args):
    try:
        fn(*args)
    except HTTPException as e:
        assert e.status_code == code, e.status_code
        return
    raise AssertionError(f"Seharusnya gagal dengan kode {code}")


def test_metrics_day9():
    db, u = new_db()
    andi, budi, citra, nadia = u["andi"], u["budi"], u["citra"], u["nadia"]

    # RAR: 100 rekomendasi ditampilkan, 35 mendapat tindakan positif
    for i in range(100):
        S.record_viewed(db, andi, f"m{i}")
        S.record_viewed(db, andi, f"m{i}")  # dilihat dua kali tetap satu rekomendasi
    for i in range(35):
        S.record_event(db, andi, "JOIN_REQUEST_SENT" if i % 2 else "INVITATION_SENT", match_id=f"m{i}")

    # GFR: 40 percobaan, 24 dikonfirmasi, 16 gagal. Satu lagi masih FORMING dan tidak dihitung.
    for i in range(16):
        S.start_formation(db, f"gagal{i}", andi)
        S.fail_formation(db, f"gagal{i}", "SCHEDULE_MISMATCH" if i < 10 else "NO_RESPONSE")
    S.start_formation(db, "masih-forming", andi)

    # SCR: dari 24 sesi terkonfirmasi, 20 sudah jatuh tempo dan 16 terlaksana
    for i in range(16):
        confirmed(db, f"ok{i}", andi, [andi, budi, citra], PAST)
        held(db, f"ok{i}", andi, repeat_intention=(True if i < 10 else None))
        held(db, f"ok{i}", budi, repeat_intention=(i < 5 if i < 10 else None))
    for i in range(2):  # batal setelah CONFIRMED: masuk penyebut
        confirmed(db, f"batal{i}", andi, [andi, budi], PAST)
        S.cancel_session(db, f"batal{i}")
    confirmed(db, "host-saja", andi, [andi, budi], PAST)
    held(db, "host-saja", andi)  # satu orang tidak bisa mengklaim sendirian
    confirmed(db, "tanpa-konfirmasi", andi, [andi, budi], PAST)
    for i in range(2):  # belum waktunya: tidak dihitung gagal
        confirmed(db, f"nanti{i}", andi, [andi, budi], FUTURE)
    for i in range(2):  # jawaban bertentangan: disputed, belum dihitung
        confirmed(db, f"sengketa{i}", andi, [andi, budi], PAST)
        held(db, f"sengketa{i}", andi, True)
        held(db, f"sengketa{i}", budi, False)

    # MSS: Andi 5, Budi 4, Citra 4. Anggota lain tidak mengisi dan tidak dihitung nol.
    held(db, "ok0", andi, overall_satisfaction=5, repeat_intention=True)
    held(db, "ok0", budi, overall_satisfaction=4, repeat_intention=True)
    held(db, "ok0", citra, overall_satisfaction=4)

    m = S.compute_metrics(db)
    assert m["rar"] == {"value": 35.0, "numerator": 35, "denominator": 100}, m["rar"]
    assert m["gfr"] == {"value": 60.0, "numerator": 24, "denominator": 40}, m["gfr"]
    assert m["scr"] == {"value": 80.0, "numerator": 16, "denominator": 20}, m["scr"]
    assert m["mss"] == {"value": 4.33, "numerator": 13, "denominator": 3}, m["mss"]
    assert m["rsi"] == {"value": 75.0, "numerator": 15, "denominator": 20}, m["rsi"]
    assert m["failure_reasons"] == {"SCHEDULE_MISMATCH": 10, "NO_RESPONSE": 6}
    assert m["sessions_not_due"] == 2 and m["sessions_disputed"] == 2
    assert m["completed_with_feedback"] == 1 and m["data_sufficient"] is False
    print("[PASS] 1. Lima metrik cocok dengan Day9: RAR 35%, GFR 60%, SCR 80%, MSS 4,33, RSI 75%")

    # Feedback dua kali tidak menjadi data ganda
    before = db.query(Feedback).count()
    fb = held(db, "ok0", citra, overall_satisfaction=4)
    assert db.query(Feedback).count() == before and fb.updated_at is not None
    print("[PASS] 2. Feedback kedua memperbarui jawaban lama")

    # Aturan penolakan
    expect_error(400, held, db, "nanti0", andi)            # jadwal belum selesai
    expect_error(403, held, db, "ok1", nadia)              # bukan anggota
    expect_error(400, held, db, "batal0", andi)            # sesi dibatalkan
    expect_error(400, S.fail_formation, db, "masih-forming", "TIDAK_ADA")
    expect_error(400, S.cancel_session, db, "masih-forming")
    print("[PASS] 3. Feedback ditolak bila belum waktunya, bukan anggota, atau sesi batal")

    # Data belum cukup: bobot tidak dibandingkan, bobot awal tetap
    result = S.evaluate_weights(db, Weights(t=0.4, g=0.2, s=0.15, d=0.15, m=0.1), PAST)
    assert result["data_sufficient"] is False and result["candidate_better"] is None
    assert S.get_active_weights(db) == DEFAULT_WEIGHTS
    print("[PASS] 4. Di bawah 30 sesi, bobot tidak dibandingkan dan bobot Day4 tetap")


def test_empty_is_none():
    db, _ = new_db()
    m = S.compute_metrics(db)
    assert all(m[k]["value"] is None for k in ("rar", "gfr", "scr", "mss", "rsi"))
    assert S.score_analysis(db) == []
    print("[PASS] 5. Tanpa data, metrik bernilai kosong, bukan 0")


def test_weights_and_analysis():
    db, u = new_db()
    andi, budi = u["andi"], u["budi"]
    # 30 sesi: kepuasan mengikuti faktor topik (t), sedangkan faktor tujuan (g) berlawanan
    for i in range(30):
        t = 50 + (i % 5) * 10
        scores = {"total": float(t), "t": float(t), "g": float(200 - 2 * t), "s": 70.0, "d": 70.0, "m": 70.0}
        confirmed(db, f"s{i}", andi, [andi, budi], PAST, scores)
        held(db, f"s{i}", andi, overall_satisfaction=1 + i % 5)
        held(db, f"s{i}", budi, overall_satisfaction=1 + i % 5)

    bands = S.score_analysis(db)
    assert [b["score_from"] for b in bands] == [50, 60, 70, 80, 90]
    assert bands[0] == {"score_from": 50, "score_to": 59, "sessions_due": 6,
                        "sessions_completed": 6, "mean_satisfaction": 1.0}
    assert bands[-1]["score_to"] == 100 and bands[-1]["mean_satisfaction"] == 5.0
    print("[PASS] 6. Analisis per rentang skor")

    candidate = Weights(t=0.6, g=0.1, s=0.1, d=0.1, m=0.1)
    result = S.evaluate_weights(db, candidate, PAST - timedelta(hours=1))
    assert result["data_sufficient"] and result["test_sessions"] == 30
    assert result["current"]["correlation"] == -1.0 and result["candidate"]["correlation"] == 1.0, result
    assert result["candidate_better"] is True
    assert S.get_active_weights(db) == DEFAULT_WEIGHTS  # evaluasi tidak mengubah bobot
    assert S.evaluate_weights(db, candidate, FUTURE)["test_sessions"] == 0  # di luar data uji
    S.set_weights(db, candidate, "uji")
    assert S.get_active_weights(db) == candidate.model_dump()
    print("[PASS] 7. Bobot calon dibandingkan pada data uji, lalu ditetapkan manual")


def test_http():
    db, u = new_db()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    andi = {"Authorization": "Bearer " + create_token(u["andi"], "andi@x.id")}
    nadia = {"Authorization": "Bearer " + create_token(u["nadia"], "nadia@x.id")}
    try:
        assert client.get("/api/v1/outcomes/metrics").status_code == 401

        rec = {"relevance_rating": "RELEVANT", "explanation_rating": "CLEAR", "interest_level": "INTERESTED"}
        assert client.put("/api/v1/outcomes/matches/m1/feedback", headers=andi, json=rec).status_code == 400
        assert client.post("/api/v1/outcomes/events/viewed", headers=andi, json={"match_id": "m1"}).status_code == 201
        assert client.put("/api/v1/outcomes/matches/m1/feedback", headers=andi, json=rec).status_code == 200
        rec["relevance_rating"] = "VERY_RELEVANT"
        assert client.put("/api/v1/outcomes/matches/m1/feedback", headers=andi, json=rec).status_code == 200
        assert client.put("/api/v1/outcomes/matches/m1/feedback", headers=andi,
                          json={"relevance_rating": "BAGUS"}).status_code == 422

        confirmed(db, "sesi", u["andi"], [u["andi"], u["budi"]], PAST)
        body = {"session_held": True, "overall_satisfaction": 5, "repeat_intention": True}
        assert client.put("/api/v1/outcomes/sessions/sesi/feedback", headers=andi, json=body).status_code == 200
        assert client.put("/api/v1/outcomes/sessions/sesi/feedback", headers=nadia, json=body).status_code == 403
        assert client.put("/api/v1/outcomes/sessions/sesi/feedback", headers=andi,
                          json={"session_held": True, "overall_satisfaction": 6}).status_code == 422
        assert client.put("/api/v1/outcomes/sessions/tidak-ada/feedback", headers=andi, json=body).status_code == 404

        metrics = client.get("/api/v1/outcomes/metrics", headers=andi)
        assert metrics.status_code == 200, metrics.text
        assert metrics.json()["recommendation_feedback"]["relevance_rating"] == {"VERY_RELEVANT": 1}
        assert metrics.json()["scr"]["value"] == 0.0  # host saja belum cukup
        assert client.get("/api/v1/outcomes/analysis", headers=andi).json() == []

        weights = {"t": 0.4, "g": 0.2, "s": 0.15, "d": 0.15, "m": 0.1}
        payload = {"candidate": weights, "test_from": "2026-11-01T00:00:00Z"}
        res = client.post("/api/v1/outcomes/weights/evaluate", headers=andi, json=payload)
        assert res.status_code == 200 and res.json()["data_sufficient"] is False, res.text
        weights["t"] = 0.9
        assert client.post("/api/v1/outcomes/weights/evaluate", headers=andi, json=payload).status_code == 422
    finally:
        app.dependency_overrides.clear()
    print("[PASS] 8. Endpoint: login wajib, validasi isi, dan feedback tidak ganda")


if __name__ == "__main__":
    test_metrics_day9()
    test_empty_is_none()
    test_weights_and_analysis()
    test_http()
    print("\n>>> SEMUA UJI FITUR 3 LULUS <<<")
