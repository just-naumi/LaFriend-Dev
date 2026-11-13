"""Uji Fitur 2 dengan contoh Plan/Day7.MD dan KEPUTUSAN.md. Tanpa database."""
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app import group_formation as G
from app import matching as M

M._today = lambda: date(2026, 11, 12)  # tanggal uji tetap: rentang intent contoh 12-18 Nov 2026


def slot(day, start, end, rank=1):
    return NS(day_or_date=day, start_time=start, end_time=end, priority_rank=rank)


def intent(name, size=(2, 4), style="DISCUSSION", slots=None, status="ACTIVE", mode="OFFLINE"):
    return NS(student_id=name, course_id="SD", topics="Binary Tree", learning_goal="UNDERSTAND",
              collaboration_style=style, learning_mode=mode, alternative_modes="",
              earliest_date="2026-11-12", latest_date="2026-11-18", status=status,
              min_group_size=size[0], max_group_size=size[1],
              student=NS(verification_status="VERIFIED", account_status="ACTIVE"),
              availabilities=slots or [slot("Wednesday", "09:00", "12:00")])


def ids(proposal):
    return [m.student_id for m in proposal["members"]]


def test_size_range():
    """Day7 bagian 10: Andi 2-4, Budi 3-4, Citra 2-3 menghasilkan MinGroup 3 dan MaxGroup 3."""
    assert G.size_range([intent("a", (2, 4)), intent("b", (3, 4)), intent("c", (2, 3))]) == (3, 3)
    assert G.size_range([intent("a", (2, 9))]) == (2, 4)  # paling banyak 4 termasuk host


def test_group_schedule():
    """Day7 bagian 5: Andi 09-12, Budi 10-13, Citra 11-14 menghasilkan Rabu 11.00-12.00."""
    andi = intent("andi", (3, 4))
    budi = intent("budi", slots=[slot("Wednesday", "10:00", "13:00")])
    citra = intent("citra", slots=[slot("Wednesday", "11:00", "14:00")])
    p = G.build_group([andi], [budi, citra])
    assert ids(p) == ["andi", "budi", "citra"] and p["status"] == "DRAFT", p
    assert p["slots"] == [{"day": "2026-11-18", "start_time": "11:00", "end_time": "12:00"}], p["slots"]

    # Bila Citra hanya sampai 10.30, tidak ada waktu bersama 60 menit
    andi = intent("andi", (3, 4))
    citra = intent("citra", slots=[slot("Wednesday", "09:00", "10:30")])
    p = G.build_group([andi, budi], [citra])
    assert p["status"] == "FAILED" and p["trace"][0]["tried"][0]["reason"] == "TIME_OVERLAP", p
    assert andi.status == "ACTIVE"


def test_best_gq_not_best_host_score():
    """Day7 bagian 4: yang dipilih calon dengan GQ terbaik, bukan skor tertinggi terhadap host."""
    andi = intent("andi", (3, 4), style="PRACTICE")
    budi = intent("budi", style="FOCUS_STUDY")
    citra = intent("citra", style="FOCUS_STUDY")
    deni = intent("deni", style="TEACHING")
    assert M.compatibility(andi, deni)["total"] == 97 > M.compatibility(andi, citra)["total"] == 94
    p = G.build_group([andi, budi], [deni, citra])
    assert ids(p) == ["andi", "budi", "citra"], ids(p)
    # Pasangan 94, 94, 100: GQ = 0,7 x 96 + 0,3 x 94 = 95,4. Dengan Deni: 94, 97, 89,5 menjadi 92,3
    tried = {t["student_id"]: t["gq"] for t in p["trace"][0]["tried"]}
    assert tried == {"deni": 92.3, "citra": 95.4} and p["gq"] == 95.4, (tried, p["gq"])


def test_stop_at_min_group():
    andi = intent("andi")
    p = G.build_group([andi], [intent("budi", status="GROUP_FORMING"), intent("citra"), intent("deni")])
    assert ids(p) == ["andi", "citra"] and (p["min_group"], p["max_group"]) == (2, 4), p
    assert andi.status == "GROUP_FORMING" and p["accepted"] == ["andi"]
    # Yang diundang ikut ditandai, jadi host lain tidak bisa mengundangnya pada saat yang sama (Day10)
    citra = p["members"][1]
    assert citra.status == "GROUP_FORMING"
    assert G.build_group([intent("hadi")], [citra])["status"] == "FAILED"
    r = G.answer_invitations(p, {"citra": "REJECTED"})
    assert r["status"] == "FAILED" and citra.status == "ACTIVE" and andi.status == "ACTIVE", r

    andi = intent("andi")
    p = G.build_group([andi], [intent("x", mode="ONLINE")])
    assert p["status"] == "FAILED" and p["reason_code"] == "GROUP_SIZE" and andi.status == "ACTIVE", p
    assert p["trace"][0]["tried"] == [{"student_id": "x", "gq": None, "reason": "MODE"}]


def test_size_rejects_candidate():
    """Kelompok 4 orang ditolak calon yang maksimumnya 3."""
    pool = [intent("budi"), intent("citra", (2, 3)), intent("deni")]
    p = G.build_group([intent("andi", (4, 4))], pool)
    assert p["status"] == "FAILED", p
    assert {"student_id": "citra", "gq": None, "reason": "GROUP_SIZE"} in p["trace"][0]["tried"]
    p = G.build_group([intent("andi", (4, 4))], pool + [intent("eko")])
    assert ids(p) == ["andi", "budi", "deni", "eko"], ids(p)


def test_invitations():
    def proposal():
        return G.build_group([intent("andi", (3, 4))], [intent("budi"), intent("citra")])

    p = G.answer_invitations(proposal(), {"budi": "ACCEPTED"})
    assert p["status"] == "DRAFT" and p["accepted"] == ["andi", "budi"], p  # Citra belum menjawab
    p = G.answer_invitations(p, {"citra": "ACCEPTED"})
    assert p["status"] == "CONFIRMATION_PENDING", p

    # Menolak, sisa masih mencapai MinGroup
    two = G.build_group([intent("andi"), intent("budi"), intent("citra")], [])
    r = G.answer_invitations(two, {"budi": "ACCEPTED", "citra": "REJECTED"})
    assert ids(r) == ["andi", "budi"] and r["status"] == "CONFIRMATION_PENDING", r

    # Menolak, sisa kurang dari MinGroup, ada pengganti. Pengganti perlu diundang lagi.
    r = G.answer_invitations(proposal(), {"budi": "ACCEPTED", "citra": "REJECTED"},
                             candidates=[intent("citra"), intent("deni")])
    assert ids(r) == ["andi", "budi", "deni"] and r["status"] == "DRAFT", r
    assert r["accepted"] == ["andi", "budi"]

    # Tidak ada pengganti
    r = G.answer_invitations(proposal(), {"budi": "ACCEPTED", "citra": "REJECTED"})
    assert (r["status"], r["reason_code"]) == ("FAILED", "USER_WITHDRAWAL"), r
    assert r["members"][0].status == "ACTIVE"
    r = G.answer_invitations(proposal(), {"budi": "EXPIRED", "citra": "ACCEPTED"})
    assert (r["status"], r["reason_code"]) == ("FAILED", "NO_RESPONSE"), r

    for bad in ({"budi": "MUNGKIN"}, {"andi": "ACCEPTED"}):
        try:
            G.answer_invitations(proposal(), bad)
            assert False, "jawaban tidak sah harus ditolak"
        except ValueError:
            pass


def test_schedule():
    def pending(andi_size=(2, 4), slots=None):
        slots = slots or [slot("Wednesday", "09:00", "12:00", 1), slot("Friday", "13:00", "15:00", 2)]
        members = [intent("andi", andi_size, slots=slots), intent("budi", slots=slots), intent("citra", slots=slots)]
        return G.answer_invitations(G.build_group(members, []), {"budi": "ACCEPTED", "citra": "ACCEPTED"})

    yes = {"andi": True, "budi": True, "citra": True}
    p = pending()
    assert p["slots"][0]["day"] == "2026-11-18" and p["slot_index"] == 0  # pilihan pertama diusulkan dulu
    try:
        G.answer_invitations(p, {})
        assert False, "undangan tidak boleh dijawab saat CONFIRMATION_PENDING"
    except ValueError:
        pass
    c = G.answer_schedule(p, yes)
    assert c["status"] == "CONFIRMED" and all(m.status == "CONVERTED" for m in c["members"]), c

    # Citra tidak menjawab: waktu bersama berikutnya diusulkan (KEPUTUSAN.md nomor 7 langkah 1)
    p = G.answer_schedule(pending(), {"andi": True, "budi": True})
    assert p["status"] == "CONFIRMATION_PENDING" and p["slots"][p["slot_index"]]["day"] == "2026-11-13", p
    # Waktu bersama habis: Citra dikeluarkan, sisa 2 masih mencapai MinGroup 2 (langkah 2)
    p = G.answer_schedule(p, {"andi": True, "budi": True, "citra": False})
    assert ids(p) == ["andi", "budi"] and p["status"] == "CONFIRMATION_PENDING" and p["slot_index"] == 0, p
    assert G.answer_schedule(p, yes)["status"] == "CONFIRMED"

    # Sisa kurang dari MinGroup dan tidak ada pengganti
    one = [slot("Wednesday", "09:00", "12:00")]
    r = G.answer_schedule(pending((3, 4), one), {"andi": True, "budi": True})
    assert (r["status"], r["reason_code"]) == ("FAILED", "SCHEDULE_MISMATCH"), r
    # Ada pengganti: proposal baru, pengganti perlu diundang
    r = G.answer_schedule(pending((3, 4), one), {"andi": True, "budi": True}, candidates=[intent("deni", slots=one)])
    assert ids(r) == ["andi", "budi", "deni"] and r["status"] == "DRAFT" and r["accepted"] == ["andi", "budi"], r
    # Host sendiri yang menolak jadwal terakhir
    r = G.answer_schedule(pending(slots=one), {"budi": True, "citra": True})
    assert r["status"] == "FAILED" and r["members"][0].status == "ACTIVE", r


if __name__ == "__main__":
    tests = [test_size_range, test_group_schedule, test_best_gq_not_best_host_score, test_stop_at_min_group,
             test_size_rejects_candidate, test_invitations, test_schedule]
    for t in tests:
        t()
        print(f"[OK] {t.__name__}")
    print(f"Semua {len(tests)} uji Fitur 2 lolos.")
