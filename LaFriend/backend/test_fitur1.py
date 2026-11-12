"""Uji Fitur 1 dengan angka contoh Plan/Day4.MD, Day5.MD, Day7.MD, dan KEPUTUSAN.md. Tanpa database."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services import matching as M


def slot(day, start, end, rank=1):
    return NS(day_or_date=day, start_time=start, end_time=end, priority_rank=rank)


def intent(name, topics="Binary Tree", goal="UNDERSTAND", style="DISCUSSION", mode="OFFLINE",
           slots=None, course="SD", dates=("2026-11-12", "2026-11-18"), status="ACTIVE",
           alternative_modes="", verification="VERIFIED", account="ACTIVE"):
    return NS(student_id=name, course_id=course, topics=topics, learning_goal=goal,
              collaboration_style=style, learning_mode=mode, alternative_modes=alternative_modes,
              earliest_date=dates[0], latest_date=dates[1], status=status,
              student=NS(verification_status=verification, account_status=account),
              availabilities=slots or [slot("Wednesday", "09:00", "12:00")])


ANDI = intent("andi")
BUDI = intent("budi", topics="Binary Tree, BST", slots=[slot("Wednesday", "10:00", "12:00")])


def test_andi_budi():
    """Day4 bagian 9: T 50, G 100, S 100, D 100, M 100, CS 85."""
    assert M.hard_constraint(ANDI, BUDI) is None
    r = M.compatibility(ANDI, BUDI)
    assert (r["t"], r["g"], r["s"], r["d"], r["m"]) == (50, 100, 100, 100, 100), r
    assert r["total"] == 85, r
    assert r["proposed_slot"] == {"day": "2026-11-18", "start_time": "10:00", "end_time": "12:00"}, r


def test_topics():
    assert M.topic_score(intent("x", topics="BST"), intent("y", topics="binary  search tree")) == 100
    assert M.topic_score(intent("x", topics="Binary Tree"), intent("y", topics="Sorting")) == 0


def test_goal_and_style_tables():
    goals = ["UNDERSTAND", "PRACTICE", "EXAM_PREP", "ASSIGNMENT", "DISCUSSION"]
    values = sorted(M.goal_score(intent("x", goal=a), intent("y", goal=b))
                    for i, a in enumerate(goals) for b in goals[i:])
    assert values == sorted([100] * 5 + [85, 85, 85, 75, 75, 70, 70, 60, 60, 40]), values
    assert M.goal_score(intent("x", goal="DISCUSSION"), intent("y", goal="UNDERSTAND")) == 70
    assert M.goal_score(intent("x", goal="ASSIGNMENT"), intent("y", goal="EXAM_PREP")) == 40

    def s(a, b):
        return M.style_score(intent("x", style=a), intent("y", style=b))
    assert s("TEACHING", "PRACTICE") == s("PRACTICE", "DISCUSSION") == s("DISCUSSION", "TEACHING") == 80
    assert s("PRACTICE", "FOCUS_STUDY") == 60
    assert s("DISCUSSION", "FOCUS_STUDY") == s("FOCUS_STUDY", "TEACHING") == 30
    assert s("FOCUS_STUDY", "FOCUS_STUDY") == 100
    try:
        s("DISCUSSION", "TIDAK_ADA")
        assert False, "gaya tidak dikenal harus ditolak"
    except ValueError:
        pass


def test_hard_constraints():
    assert M.hard_constraint(ANDI, intent("x", course="PW")) == "COURSE"
    assert M.hard_constraint(ANDI, intent("x", verification="PENDING")) == "ACCOUNT"
    assert M.hard_constraint(ANDI, intent("x", account="RESTRICTED")) == "ACCOUNT"
    assert M.hard_constraint(ANDI, intent("x", dates=("2026-11-20", "2026-11-25"))) == "DATE_RANGE"
    # 11.30-12.00 hanya 30 menit, dan jadwal Senin tidak boleh dicampur dengan Rabu
    assert M.hard_constraint(ANDI, intent("x", slots=[slot("Wednesday", "11:30", "13:00")])) == "TIME_OVERLAP"
    assert M.hard_constraint(ANDI, intent("x", slots=[slot("Monday", "09:00", "12:00")])) == "TIME_OVERLAP"
    assert M.hard_constraint(ANDI, intent("x", slots=[slot("Wednesday", "11:00", "13:00")])) is None  # tepat 60
    assert M.hard_constraint(ANDI, intent("x", mode="ONLINE")) == "MODE"
    assert M.hard_constraint(ANDI, intent("x", mode="HYBRID")) is None
    assert M.hard_constraint(ANDI, intent("x", slots=[slot("Wednesday", "11:00", "13:00")]), min_minutes=90) == "TIME_OVERLAP"


def test_real_dates():
    """Jam kosong dihitung pada tanggal nyata. 18 November 2026 adalah hari Rabu."""
    for day in ("Rabu", "wednesday", "2026-11-18"):
        assert M.hard_constraint(ANDI, intent("x", slots=[slot(day, "09:00", "12:00")])) is None, day
    # Rentang 12-18 dan 18-25 hanya beririsan di Rabu 18 November, jadi jam kosong Senin tidak terpakai
    monday = [slot("Monday", "09:00", "12:00")]
    late = ("2026-11-18", "2026-11-25")
    assert M.hard_constraint(intent("a", slots=monday), intent("b", slots=monday, dates=late)) == "TIME_OVERLAP"
    assert M.hard_constraint(ANDI, intent("b", dates=late)) is None
    assert M.hard_constraint(ANDI, intent("x", slots=[slot("2026-11-25", "09:00", "12:00")])) == "TIME_OVERLAP"
    # Rentang dua minggu memuat dua hari Rabu. Yang diusulkan tanggal terawal.
    two_weeks = ("2026-11-12", "2026-11-26")
    slots = M.common_slots([intent("a", dates=two_weeks), intent("b", dates=two_weeks)])
    assert [s["day"] for s in slots] == ["2026-11-18", "2026-11-25"], slots
    assert M.date_score(intent("a", dates=two_weeks), intent("b", dates=two_weeks))[1]["day"] == "2026-11-18"


def test_schema():
    """Isian intent yang salah ditolak sebelum sampai ke Fitur 1."""
    from pydantic import ValidationError
    from app.schemas.study_intent import StudyIntentCreate, StudyIntentUpdate
    good = dict(course_id="x", topics="Binary Tree", learning_goal="UNDERSTAND", collaboration_style="DISCUSSION",
                earliest_date="2026-11-12", latest_date="2026-11-18",
                availabilities=[dict(day_or_date="Rabu", start_time="09:00", end_time="12:00")])
    assert StudyIntentCreate(**good).availabilities[0].priority_rank == 1
    bad_slots = [dict(day_or_date="Besok", start_time="09:00", end_time="12:00"),
                 dict(day_or_date="Rabu", start_time="9:00", end_time="12:00"),
                 dict(day_or_date="Rabu", start_time="09:00", end_time="25:99"),
                 dict(day_or_date="Rabu", start_time="12:00", end_time="09:00"),
                 dict(day_or_date="Rabu", start_time="09:00", end_time="12:00", priority_rank=0)]
    bad = [{"learning_goal": "NGASAL"}, {"collaboration_style": "APA_SAJA"}, {"learning_mode": "LURING"},
           {"earliest_date": "besok"}, {"latest_date": "2026-11-01"}, {"min_group_size": 1}, {"max_group_size": 5},
           {"min_group_size": 4, "max_group_size": 2}] + [{"availabilities": [s]} for s in bad_slots]
    for change in bad:
        try:
            StudyIntentCreate(**{**good, **change})
            assert False, f"harus ditolak: {change}"
        except ValidationError:
            pass
    for change in ({"learning_goal": "NGASAL"}, {"latest_date": "lusa"}, {"min_group_size": 0}):
        try:
            StudyIntentUpdate(**change)
            assert False, f"harus ditolak: {change}"
        except ValidationError:
            pass


def test_one_running_intent_per_course():
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    import app.models  # noqa: F401
    from app.database import Base
    from app.models.course import Course
    from app.models.student import Student
    from app.schemas.study_intent import StudyIntentCreate, StudyIntentUpdate
    from app.services.study_intent import StudyIntentService as Intents

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add_all([Student(student_id="s1", full_name="A", email="a@x.id", student_number="1", password_hash="x"),
                Course(course_id="c1", course_code="TC1", course_name="Struktur Data", study_program="S1"),
                Course(course_id="c2", course_code="TC2", course_name="Kalkulus", study_program="S1")])
    db.commit()

    def data(course):
        return StudyIntentCreate(course_id=course, topics="Binary Tree", learning_goal="UNDERSTAND",
                                 collaboration_style="DISCUSSION", earliest_date="2026-11-12", latest_date="2026-11-18",
                                 availabilities=[dict(day_or_date="Rabu", start_time="09:00", end_time="12:00")])
    first = Intents.create_intent(db, "s1", data("c1")).intent_id
    Intents.create_intent(db, "s1", data("c2"))  # mata kuliah lain boleh
    for call in (lambda: Intents.create_intent(db, "s1", data("c1")),
                 lambda: Intents.update_intent(db, first, "s1", StudyIntentUpdate(earliest_date="2026-12-01")),
                 lambda: Intents.update_intent(db, first, "s1", StudyIntentUpdate(min_group_size=4, max_group_size=3))):
        try:
            call()
            assert False, "harus ditolak"
        except HTTPException as error:
            assert error.status_code == 400
    assert Intents.get_intent_by_id(db, first).earliest_date == "2026-11-12"  # perubahan yang ditolak tidak tersimpan
    Intents.cancel_intent(db, first, "s1")
    Intents.create_intent(db, "s1", data("c1"))  # setelah dibatalkan boleh membuat lagi


def test_date_score():
    """KEPUTUSAN.md nomor 3: Rabu (1 dan 1) dan Jumat (2 dan 3) menghasilkan D = 100 dari Rabu."""
    a = intent("a", slots=[slot("Wednesday", "09:00", "12:00", 1), slot("Friday", "13:00", "17:00", 2)])
    b = intent("b", slots=[slot("Friday", "14:00", "16:00", 3), slot("Wednesday", "10:00", "12:00", 1)])
    d, proposed = M.date_score(a, b)
    assert d == 100 and proposed["day"] == "2026-11-18", (d, proposed)

    def d_for(rank_a, rank_b):
        return M.date_score(intent("a", slots=[slot("Friday", "13:00", "17:00", rank_a)]),
                            intent("b", slots=[slot("Friday", "14:00", "16:00", rank_b)]))[0]
    assert (d_for(1, 2), d_for(2, 2), d_for(1, 3), d_for(2, 3), d_for(4, 4)) == (85, 75, 60, 60, 60)


def test_mode_score():
    def m(mode_a, alt_a, mode_b, alt_b):
        return M.mode_score(intent("a", mode=mode_a, alternative_modes=alt_a),
                            intent("b", mode=mode_b, alternative_modes=alt_b))
    assert m("OFFLINE", "ONLINE", "OFFLINE", "HYBRID") == 100  # contoh Day4 bagian 8
    assert m("OFFLINE", "", "ONLINE", "OFFLINE") == 85
    assert m("OFFLINE", "HYBRID", "ONLINE", "HYBRID") == 85   # Hybrid alternatif mencakup Offline dan Online
    assert m("OFFLINE", "", "ONLINE", "") == 0
    assert m("HYBRID", "", "ONLINE", "") == 100
    # Metode bersama hanya di pilihan alternatif kedua pihak. Hanya mungkin bila utamanya tidak bertemu.
    a = NS(learning_mode="OFFLINE", alternative_modes="X")
    b = NS(learning_mode="ONLINE", alternative_modes="X")
    assert M.mode_score(a, b) == 70


def test_group_quality():
    """Day7: pasangan 90, 85, 75 menghasilkan GQ 80,83."""
    assert M.group_quality([90, 85, 75]) == 80.83
    assert M.group_quality([85]) == 85


def test_partner_ranking():
    citra = intent("citra", goal="PRACTICE")                       # T 100, G 85
    deni = intent("deni", topics="Binary Tree, AVL, Heap", style="FOCUS_STUDY", goal="ASSIGNMENT")
    pool = [BUDI, citra, deni, ANDI, intent("eko", status="CANCELLED"), intent("fajar", mode="ONLINE")]
    ranked = M.match_partners(ANDI, pool)
    assert [r["intent"].student_id for r in ranked] == ["citra", "budi", "deni"], ranked
    assert ranked[0]["total"] == 96.25 and ranked[1]["total"] == 85
    # deni: T 33,33 G 60 S 30 D 100 M 100 = 10 + 15 + 4,5 + 15 + 15 = 59,5. Tetap tampil, tidak ada ambang.
    assert ranked[2]["total"] == 59.5, ranked[2]
    assert len(M.match_partners(ANDI, [intent(f"m{i}") for i in range(8)])) == 5
    # Dua intent aktif dari mahasiswa yang sama hanya muncul sekali, dengan skor tertinggi
    twice = M.match_partners(ANDI, [BUDI, intent("budi")])
    assert [(r["intent"].student_id, r["total"]) for r in twice] == [("budi", 100)], twice
    # Bobot dari Fitur 3 dipakai bila diberikan
    only_topic = {"t": 1.0, "g": 0.0, "s": 0.0, "d": 0.0, "m": 0.0}
    assert M.compatibility(ANDI, BUDI, only_topic)["total"] == 50


def test_sessions_first():
    """Day5 bagian 3: Session A lolos, Session B gugur (Sorting), Session C gugur (penuh)."""
    session_a = NS(name="A", members=[BUDI, intent("citra")], max_size=4)
    session_b = NS(name="B", members=[intent("h2", topics="Sorting"), intent("m2", topics="Sorting")], max_size=4)
    session_c = NS(name="C", members=[intent(f"c{i}") for i in range(4)], max_size=4)
    result = M.recommend(ANDI, [session_a, session_b, session_c], [intent("gilang")])
    assert result["type"] == "SESSION"
    assert [r["session"].name for r in result["items"]] == ["A"], result
    # Pasangan: andi-budi 85, andi-citra 100, budi-citra 85. GQ = 0,7 x 90 + 0,3 x 85 = 88,5
    assert result["items"][0]["total"] == 88.5 and result["items"][0]["seats_left"] == 2, result

    host_only = NS(name="H", members=[BUDI], max_size=4)
    assert M.match_sessions(ANDI, [host_only])[0]["total"] == M.compatibility(ANDI, BUDI)["total"] == 85

    # Tiap anggota cocok berdua dengan pencari, tetapi tidak ada satu waktu untuk bertiga
    seeker = intent("s", slots=[slot("Wednesday", "09:00", "12:00")])
    early = intent("e", slots=[slot("Wednesday", "09:00", "10:30")])
    late = intent("l", slots=[slot("Wednesday", "10:30", "12:00")])
    assert M.match_sessions(seeker, [NS(members=[early, late], max_size=4)]) == []

    assert M.match_sessions(BUDI, [session_a]) == []  # sudah menjadi anggota
    fallback = M.recommend(ANDI, [session_b, session_c], [BUDI])
    assert fallback["type"] == "PARTNER" and fallback["items"][0]["intent"] is BUDI
    assert M.recommend(ANDI, [], [intent("x", course="PW")]) == {"type": "NONE", "items": []}


if __name__ == "__main__":
    tests = [test_andi_budi, test_topics, test_goal_and_style_tables, test_hard_constraints, test_real_dates, test_schema,
             test_one_running_intent_per_course, test_date_score,
             test_mode_score, test_group_quality, test_partner_ranking, test_sessions_first]
    for t in tests:
        t()
        print(f"[OK] {t.__name__}")
    print(f"Semua {len(tests)} uji Fitur 1 lolos.")
