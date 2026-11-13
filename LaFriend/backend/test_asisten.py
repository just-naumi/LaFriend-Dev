"""Uji asisten permintaan (chat dan transkrip suara). Tanpa database."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.schemas import StudyIntentCreate
from app import intent_assistant as A

# Sebagian katalog seeder main
COURSES = ["Struktur Data", "Algoritma dan Pemrograman", "Basis Data", "Matematika Diskrit",
           "Kalkulus 1", "Kalkulus 2", "Jaringan Komputer dan Data", "Kecerdasan Buatan & Machine Learning"]
TODAY = date(2026, 11, 13)  # Jumat


def talk(lines, usual=None):
    s = A.new_state()
    for line in lines:
        s = A.chat_turn(s, line, COURSES, usual or {}, TODAY)
    return s


def test_parse_full_sentence():
    r = A.parse("Mau belajar strukdat materi Binary Tree buat UTS, Senin dan Rabu jam 7-9 malam, "
                "minggu depan, diskusi online bertiga", COURSES, TODAY)
    f = r["fields"]
    assert f["course_id"] == "Struktur Data" and f["topics"] == "Binary Tree", f
    assert f["learning_goal"] == "EXAM_PREP" and f["collaboration_style"] == "DISCUSSION", f
    assert f["learning_mode"] == "ONLINE" and (f["min_group_size"], f["max_group_size"]) == (3, 3), f
    assert f["availabilities"] == [{"day_or_date": d, "start_time": "19:00", "end_time": "21:00", "priority_rank": 1}
                                   for d in ("Senin", "Rabu")], f
    assert (f["earliest_date"], f["latest_date"]) == ("2026-11-16", "2026-11-22"), f


def test_parse_does_not_invent():
    # Topik berhenti sebelum kata alasan
    assert A.parse("strukdat materi Binary Tree biar paham", COURSES, TODAY)["fields"]["topics"] == "Binary Tree"
    # Jam mulai saja: tidak mengarang jam selesai
    r = A.parse("Kalkulus selasa jam 7 malam", COURSES, TODAY)
    assert "availabilities" not in r["fields"] and r["notes"], r
    # "bab 3-4" dan "2-4 orang" bukan jam
    r = A.parse("matdis bab 3-4, 2-4 orang", COURSES, TODAY)
    assert "availabilities" not in r["fields"] and "time_only" not in r["fields"], r
    assert (r["fields"]["min_group_size"], r["fields"]["max_group_size"]) == (2, 4), r
    # "dua minggu" bukan hari Minggu
    r = A.parse("dua minggu ke depan", COURSES, TODAY)
    assert "days_only" not in r["fields"] and r["fields"]["latest_date"] == "2026-11-26", r
    # Dua tujuan berbeda: tidak dipilihkan
    r = A.parse("latihan soal untuk uts", COURSES, TODAY)
    assert "learning_goal" not in r["fields"] and set(r["unclear"]["learning_goal"]) == {"PRACTICE", "EXAM_PREP"}, r
    # Ukuran di luar 2-4 ditolak
    r = A.parse("kelompok 6 orang", COURSES, TODAY)
    assert "min_group_size" not in r["fields"] and r["notes"], r


def test_parse_times():
    f = A.parse("besok pukul 13.30-15.00", COURSES, TODAY)["fields"]
    assert f["availabilities"] == [{"day_or_date": "2026-11-14", "start_time": "13:30", "end_time": "15:00",
                                    "priority_rank": 1}], f
    f = A.parse("kamis jam 1-3 siang", COURSES, TODAY)["fields"]
    assert f["availabilities"][0]["start_time"] == "13:00", f
    r = A.parse("kamis jam 9-8", COURSES, TODAY)
    assert "availabilities" not in r["fields"] and r["notes"], r


def test_chat_asks_missing_in_order():
    s = talk(["halo"])
    assert s["ask"] == "course_id", s
    s = talk(["struktur data"])
    assert s["ask"] == "topics", s
    s = talk(["struktur data", "Binary Tree dan AVL"])  # jawaban langsung dipakai sebagai topik
    assert s["fields"]["topics"] == "Binary Tree dan AVL" and s["ask"] == "learning_goal", s
    s = talk(["halo", "struktur datta"])  # salah ketik tetap dikenali saat ditanya mata kuliah
    assert s["fields"]["course_id"] == "Struktur Data", s


def test_chat_joins_day_and_time_across_messages():
    s = talk(["basdat materi normalisasi buat tugas", "senin", "jam 19.00-21.00"])
    assert s["fields"]["availabilities"] == [{"day_or_date": "Senin", "start_time": "19:00", "end_time": "21:00",
                                              "priority_rank": 1}], s
    assert s["ask"] == "date_range", s


def test_chat_course_change_needs_confirmation():
    s = talk(["kalkulus 1 materi integral", "eh jarkom aja"])
    assert s["fields"]["course_id"] == "Kalkulus 1" and "Ganti mata kuliah" in s["reply"], s
    s = A.chat_turn(s, "ya", COURSES, {}, TODAY)
    assert s["fields"]["course_id"] == "Jaringan Komputer dan Data", s
    s = talk(["kalkulus 1 materi integral", "eh jarkom aja", "nggak"])
    assert s["fields"]["course_id"] == "Kalkulus 1", s


def test_habits_from_history():
    past = [dict(collaboration_style="PRACTICE", learning_mode="OFFLINE", min_group_size=3, max_group_size=4,
                 availabilities=[{"day_or_date": "Selasa", "start_time": "19:00", "end_time": "21:00"}]),
            dict(collaboration_style="PRACTICE", learning_mode="ONLINE", min_group_size=3, max_group_size=4,
                 availabilities=[{"day_or_date": "Selasa", "start_time": "19:00", "end_time": "21:00"},
                                 {"day_or_date": "2026-11-20", "start_time": "08:00", "end_time": "10:00"}]),
            dict(collaboration_style="DISCUSSION", learning_mode="ONLINE", min_group_size=2, max_group_size=2)]
    h = A.habits(past, {"learning_mode": "HYBRID", "language": "id"})
    assert h["collaboration_style"] == "PRACTICE" and h["learning_mode"] == "ONLINE", h
    assert h["group_size"] == (3, 4) and h["availabilities"] == [("Selasa", "19:00", "21:00")], h
    assert h["language"] == "id", h
    assert A.habits([], {"learning_mode": "HYBRID"}) == {"learning_mode": "HYBRID"}


def test_chat_uses_and_confirms_habits():
    usual = {"collaboration_style": "PRACTICE", "learning_mode": "OFFLINE", "group_size": (3, 4),
             "availabilities": [("Selasa", "19:00", "21:00")]}
    start = ["strukdat materi graph buat paham"]
    s = talk(start, usual)
    assert s["ask"] == "availabilities" and "Biasanya kamu Selasa 19:00-21:00" in s["reply"], s
    s = talk(start + ["ya", "minggu ini"], usual)
    assert s["fields"]["availabilities"][0]["day_or_date"] == "Selasa" and s["ask"] == "collaboration_style", s
    assert "Biasanya kamu latihan bersama" in s["reply"], s
    # Pengguna menyebut nilai lain: ditanya dulu, bukan langsung ditimpa
    s = talk(start + ["ya", "minggu ini", "diskusi"], usual)
    assert "collaboration_style" not in s["fields"], s
    assert "Biasanya kamu latihan bersama, sekarang diskusi? Benar?" in s["reply"], s
    s = A.chat_turn(s, "iya", COURSES, usual, TODAY)
    assert s["fields"]["collaboration_style"] == "DISCUSSION", s
    # Menolak saran: ditanya terbuka
    s = talk(start + ["ya", "minggu ini", "nggak"], usual)
    assert s["ask"] == "collaboration_style" and s["suggest"] is None and "Mau belajar dengan cara apa" in s["reply"], s


def test_chat_done_and_form_valid():
    s = talk(["Kecerdasan Buatan materi search buat ujian", "jumat jam 13-15", "minggu depan",
              "latihan bersama", "offline", "berempat"])
    assert s["done"] and "Periksa" in s["reply"], s
    assert "tidak ada di rentang" not in s["reply"], s["reply"]
    # Kamis tidak ada di "minggu ini" kalau hari ini Jumat
    s = talk(["Kalkulus 1 materi integral buat ujian", "kamis jam 19-21", "minggu ini", "diskusi", "online", "berdua"])
    assert s["done"] and "Kamis tidak ada di rentang" in s["reply"], s["reply"]
    form = A.to_form(talk(["Kecerdasan Buatan materi search buat ujian", "jumat jam 13-15", "minggu depan",
                           "latihan bersama", "offline", "berempat"])["fields"])
    StudyIntentCreate(**form)  # harus lolos validasi skema yang sama dengan form manual


if __name__ == "__main__":
    tests = [test_parse_full_sentence, test_parse_does_not_invent, test_parse_times, test_chat_asks_missing_in_order,
             test_chat_joins_day_and_time_across_messages, test_chat_course_change_needs_confirmation,
             test_habits_from_history, test_chat_uses_and_confirms_habits, test_chat_done_and_form_valid]
    for t in tests:
        t()
        print(f"[OK] {t.__name__}")
    print(f"Semua {len(tests)} uji asisten lolos.")
