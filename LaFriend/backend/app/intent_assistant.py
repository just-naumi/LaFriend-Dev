"""Asisten permintaan belajar: membaca teks bebas (chat atau transkrip suara) menjadi isian form.

Berbasis aturan, jalan offline. Aturan dari Plan (Struktur_Sistem.MD, LLM Intent Extraction):
tidak mengarang jadwal, tidak mengganti mata kuliah tanpa konfirmasi, menanyakan field yang kosong,
dan hasilnya selalu diperiksa pengguna sebelum disimpan (asisten ini tidak pernah menyimpan).
"""
import re
from collections import Counter
from datetime import date, timedelta
from difflib import get_close_matches

DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
# Singkatan ke nama resmi di katalog seeder main
ALIASES = {"strukdat": "Struktur Data", "basdat": "Basis Data", "alpro": "Algoritma dan Pemrograman",
           "algoritma": "Algoritma dan Pemrograman", "matdis": "Matematika Diskrit",
           "jarkom": "Jaringan Komputer dan Data", "ai": "Kecerdasan Buatan & Machine Learning",
           "kecerdasan buatan": "Kecerdasan Buatan & Machine Learning"}
GOALS = [(r"\b(uts|uas|ujian|kuis|quiz)\b", "EXAM_PREP"), (r"\b(tugas|pr|proyek|project)\b", "ASSIGNMENT"),
         (r"latihan soal|(ngerjain|mengerjakan) soal", "PRACTICE"), (r"\b(paham|pahami|memahami|ngerti|mengerti)\b", "UNDERSTAND"),
         (r"\b(berbagi|sharing)\b", "KNOWLEDGE_SHARING")]
STYLES = [(r"diskusi|bahas bareng", "DISCUSSION"), (r"latihan (bareng|bersama)|ngerjain bareng", "PRACTICE"),
          (r"diajari|diajarin|ajarin|mengajari|tutor|dijelasin", "TEACHING"), (r"\bfokus\b|belajar tenang", "FOCUS_STUDY")]
MODES = [(r"\b(online|daring|zoom|g?meet|discord)\b", "ONLINE"), (r"\b(hybrid|campuran)\b", "HYBRID"),
         (r"\b(offline|luring|tatap muka|kampus|perpus\w*)\b", "OFFLINE")]
LABEL = {"UNDERSTAND": "memahami materi", "PRACTICE": "latihan soal", "EXAM_PREP": "persiapan ujian",
         "ASSIGNMENT": "mengerjakan tugas", "DISCUSSION": "diskusi", "KNOWLEDGE_SHARING": "berbagi pengetahuan", "TEACHING": "saling mengajari",
         "FOCUS_STUDY": "belajar fokus bersama", "OFFLINE": "tatap muka", "ONLINE": "online", "HYBRID": "campuran"}
STYLE_LABEL = {**LABEL, "PRACTICE": "latihan bersama"}

T = r"(\d{1,2})(?:[.:](\d{2}))?"
P = r"(pagi|siang|sore|malam)"
DAY_OR_TIME = re.compile(
    rf"(?P<range>(?:jam|pukul)?\s*{T}\s*{P}?\s*(?:-|–|sampai|sampe|s/d|hingga)\s*(?:jam|pukul)?\s*{T}\s*{P}?)"
    rf"|(?P<single>(?:jam|pukul)\s*{T}\s*{P}?)"
    r"|(?P<day>\b(?:senin|selasa|rabu|kamis|jumat|sabtu|minggu|besok|lusa)\b(?<!dua minggu)(?<!2 minggu)(?!\s+(?:ini|depan|ke)))"
    r"|(?P<iso>\b\d{4}-\d{2}-\d{2}\b)")
SIZE_WORDS = {"berdua": 2, "bertiga": 3, "berempat": 4}
TOPIC = re.compile(r"\b(?:topik|materi|bab|tentang|bahas)\s+(.+?)(?=\s+(?:hari|jam|pukul|untuk|buat|biar|agar|supaya|karena|dengan|secara|"
                   r"bareng|bersama|minggu|besok|lusa|online|offline|di|senin|selasa|rabu|kamis|jumat|sabtu)\b|[,.;!?]|$)", re.I)
YES = re.compile(r"^(ya|iya+|yes|boleh|oke|ok|betul|benar|sip|setuju|pakai|lanjut)\b")
NO = re.compile(r"^(tidak|nggak|ngga|gak|enggak|bukan|jangan|no)\b")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().replace("jum'at", "jumat")).strip()


def _one(text, table):
    """Nilai dari tabel kata kunci. Lebih dari satu nilai berbeda berarti belum jelas: kembalikan semuanya."""
    return list(dict.fromkeys(value for pattern, value in table if re.search(pattern, text)))


def _hhmm(h, m, period):
    h, m = int(h), int(m or 0)
    if period in ("sore", "malam") and h < 12 or period == "siang" and h < 6:
        h += 12
    return f"{h:02d}:{m:02d}" if h <= 23 and m <= 59 else None


def _date_range(text, today):
    if "dua minggu" in text or "2 minggu" in text:
        return today.isoformat(), (today + timedelta(days=13)).isoformat()
    if "minggu depan" in text:
        start = today + timedelta(days=7 - today.weekday())
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    if "minggu ini" in text:
        return today.isoformat(), (today + timedelta(days=6 - today.weekday())).isoformat()
    return None


def parse(text: str, courses: list[str], today: date) -> dict:
    """Baca satu pesan. Hanya mengisi yang benar-benar disebut; sisanya dibiarkan kosong untuk ditanyakan."""
    t = _norm(text)
    fields, notes, unclear = {}, [], {}

    hits = [c for c in courses if c.casefold() in t]
    hits += [c for alias, c in ALIASES.items() if c in courses and re.search(rf"\b{re.escape(alias)}\b", t)]
    hits = list(dict.fromkeys(hits))
    if len(hits) == 1:
        fields["course_id"] = hits[0]
    elif hits:
        unclear["course_id"] = hits

    m = TOPIC.search(re.sub(r"\s+", " ", text).strip())  # teks asli, supaya huruf besar topik tetap
    if m:
        fields["topics"] = m.group(1).strip()

    for key, table in (("learning_goal", GOALS), ("collaboration_style", STYLES), ("learning_mode", MODES)):
        found = _one(t, table)
        if len(found) == 1:
            fields[key] = found[0]
        elif found:
            unclear[key] = found

    size = re.search(r"\b([1-9])\s*(?:-|sampai|s/d|atau)\s*([1-9])\s*orang", t) or re.search(r"\b([1-9])\s*orang", t)
    word = next((n for w, n in SIZE_WORDS.items() if w in t), None)
    if size or word:
        lo, hi = (int(size.group(1)), int(size.group(size.lastindex))) if size else (word, word)
        if 2 <= lo <= hi <= 4:
            fields["min_group_size"], fields["max_group_size"] = lo, hi
        else:
            notes.append("Ukuran kelompok harus 2 sampai 4 orang.")
    t_time = re.sub(r"\b[1-9]\s*(?:(?:-|sampai|s/d|atau)\s*[1-9]\s*)?orang", " ", t)  # angka orang bukan jam

    slots, waiting = [], []  # waiting: hari yang belum punya jam
    for m in DAY_OR_TIME.finditer(t_time):
        if m.group("day") or m.group("iso"):
            if m.group("iso"):
                waiting.append(m.group("iso"))
            elif m.group("day") in ("besok", "lusa"):
                waiting.append((today + timedelta(days=1 if m.group("day") == "besok" else 2)).isoformat())
            else:
                waiting.append(m.group("day").capitalize())
            continue
        if m.group("single"):
            notes.append("Jam selesainya belum disebut. Sebutkan dari jam berapa sampai jam berapa.")
            continue
        g = m.groups()  # range: g[1..6] = jam1, menit1, waktu1, jam2, menit2, waktu2
        text_range = m.group("range")
        if not re.search(r"jam|pukul|[.:]|pagi|siang|sore|malam", text_range):
            continue  # angka biasa (misalnya "bab 3-4"), bukan jam
        start = _hhmm(g[1], g[2], g[3] or g[6])
        end = _hhmm(g[4], g[5], g[6] or g[3])
        if not start or not end or end <= start:
            notes.append("Jamnya tidak masuk akal: jam selesai harus setelah jam mulai.")
            continue
        if waiting:
            slots += [{"day_or_date": d, "start_time": start, "end_time": end, "priority_rank": 1} for d in waiting]
            waiting = []
        else:
            fields["time_only"] = {"start_time": start, "end_time": end}
    if slots:
        fields["availabilities"] = slots
    if waiting:
        fields["days_only"] = waiting

    rng = _date_range(t, today)
    if rng:
        fields["earliest_date"], fields["latest_date"] = rng
    return {"fields": fields, "unclear": unclear, "notes": notes}


def habits(past: list[dict], prefs: dict | None = None) -> dict:
    """Kebiasaan pengguna: nilai yang paling sering dipakai di permintaan sebelumnya.
    Belum ada riwayat: pakai preferensi dari onboarding. Seri: yang terbaru menang."""
    out = dict(prefs or {})
    recent_first = list(reversed(past))
    for key in ("collaboration_style", "learning_mode"):
        values = [p[key] for p in recent_first if p.get(key)]
        if values:
            out[key] = Counter(values).most_common(1)[0][0]
    sizes = [(p["min_group_size"], p["max_group_size"]) for p in recent_first if p.get("min_group_size")]
    if sizes:
        out["group_size"] = Counter(sizes).most_common(1)[0][0]
    # Hanya slot nama hari yang berulang tiap minggu; tanggal tertentu tidak menjadi kebiasaan
    slots = [(s["day_or_date"].capitalize(), s["start_time"], s["end_time"]) for p in recent_first
             for s in p.get("availabilities", []) if s["day_or_date"].capitalize() in DAYS]
    if slots:
        out["availabilities"] = [Counter(slots).most_common(1)[0][0]]
    return out


ORDER = ["course_id", "topics", "learning_goal", "availabilities", "date_range",
         "collaboration_style", "learning_mode", "group_size"]
QUESTIONS = {
    "course_id": "Mau belajar mata kuliah apa?",
    "topics": "Topik atau bab apa yang mau dibahas?",
    "learning_goal": "Tujuannya apa: memahami materi, latihan soal, persiapan ujian, atau mengerjakan tugas?",
    "availabilities": "Kapan kamu kosong? Sebutkan hari dan jamnya, misalnya \"Selasa jam 19.00-21.00\".",
    "date_range": "Untuk kapan: minggu ini, minggu depan, atau dua minggu ke depan?",
    "collaboration_style": "Mau belajar dengan cara apa: diskusi, latihan bersama, saling mengajari, atau belajar fokus?",
    "learning_mode": "Tatap muka, online, atau campuran?",
    "group_size": "Kelompoknya berapa orang? Boleh 2 sampai 4.",
}


def _has(fields, key):
    if key == "date_range":
        return "earliest_date" in fields
    if key == "group_size":
        return "min_group_size" in fields
    return bool(fields.get(key))


def _show(key, value):
    if key == "group_size":
        lo, hi = value
        return f"{lo} orang" if lo == hi else f"{lo}-{hi} orang"
    if key == "availabilities":
        return ", ".join(f"{d} {a}-{b}" for d, a, b in value)
    return STYLE_LABEL[value] if key == "collaboration_style" else LABEL.get(value, value)


def _apply(fields, key, value):
    if key == "group_size":
        fields["min_group_size"], fields["max_group_size"] = value
    elif key == "availabilities":
        fields["availabilities"] = [{"day_or_date": d, "start_time": a, "end_time": b, "priority_rank": 1}
                                    for d, a, b in value]
    else:
        fields[key] = value


def _value(fields, key):
    if key == "group_size":
        return (fields["min_group_size"], fields["max_group_size"])
    if key == "availabilities":
        return [(s["day_or_date"], s["start_time"], s["end_time"]) for s in fields["availabilities"]]
    return fields.get(key)


def new_state() -> dict:
    return {"fields": {}, "ask": None, "suggest": None, "confirm": [], "declined": [], "days_only": [], "time_only": None}


def chat_turn(state: dict, text: str, courses: list[str], usual: dict, today: date) -> dict:
    """Satu giliran chat. Mengembalikan state baru dan balasan; tidak pernah menyimpan permintaan."""
    s = {**state, "fields": dict(state["fields"]), "confirm": list(state["confirm"]), "declined": list(state["declined"])}
    f, t, said = s["fields"], _norm(text), []

    if s["confirm"]:
        key, value, fallback = s["confirm"].pop(0)
        _apply(f, key, value if YES.match(t) else fallback)  # selain "ya", nilai lama/kebiasaan dipakai
    elif s["suggest"] and YES.match(t):
        _apply(f, s["ask"], s["suggest"])
        said.append(_show(s["ask"], s["suggest"]))
    elif s["suggest"] and NO.match(t) and len(t.split()) <= 2:
        s["declined"].append(s["ask"])
    else:
        r = parse(text, courses, today)
        new, notes = r["fields"], list(r["notes"])
        if s["ask"] == "topics" and "topics" not in new and not r["unclear"]:
            new["topics"] = text.strip()[:120]
        if s["ask"] == "course_id" and "course_id" not in new and "course_id" not in r["unclear"]:
            close = get_close_matches(t, [c.casefold() for c in courses], n=1, cutoff=0.6)
            if close:
                new["course_id"] = next(c for c in courses if c.casefold() == close[0])
        for key, values in r["unclear"].items():
            names = " atau ".join(values if key == "course_id" else (LABEL[v] for v in values))
            notes.append(f"Aku dengar lebih dari satu pilihan: {names}. Pilih satu ya.")

        # Hari tanpa jam dan jam tanpa hari dari pesan berbeda digabung; tidak ada yang dikarang
        days = s["days_only"] + new.pop("days_only", [])
        time = new.pop("time_only", None) or s["time_only"]
        if days and time:
            new.setdefault("availabilities", [])
            new["availabilities"] += [{"day_or_date": d, **time, "priority_rank": 1} for d in days]
            days, time = [], None
        s["days_only"], s["time_only"] = days, time
        if days and not new.get("availabilities"):
            notes.append(f"{', '.join(days)} jam berapa sampai jam berapa?")

        if "course_id" in new and f.get("course_id") and new["course_id"] != f["course_id"]:
            s["confirm"].append(("course_id", new.pop("course_id"), f["course_id"]))
        for key in ("collaboration_style", "learning_mode", "group_size", "availabilities"):
            have = "min_group_size" in new if key == "group_size" else key in new
            if not have or not usual.get(key) or _has(f, key):
                continue
            value = _value(new, key)
            if key == "availabilities":
                value = value + _value(f, key) if f.get(key) else value
            if value != usual[key]:
                s["confirm"].append((key, value, usual[key]))
                for k in (("min_group_size", "max_group_size") if key == "group_size" else (key,)):
                    new.pop(k)
        if new.get("availabilities") and f.get("availabilities"):
            new["availabilities"] = f["availabilities"] + new["availabilities"]
        if new.get("availabilities") and "earliest_date" not in new and "earliest_date" not in f:
            dates = [a["day_or_date"] for a in new["availabilities"]]
            if all(d[:1].isdigit() for d in dates):  # tanggal pasti: rentangnya ikut dari tanggal itu
                new["earliest_date"], new["latest_date"] = min(dates), max(dates)
        f.update(new)
        s["notes"] = notes

    s["suggest"], reply = None, list(s.pop("notes", []))
    if said:
        reply.insert(0, f"Oke, {said[0]}.")
    if s["confirm"]:
        key, value, fallback = s["confirm"][0]
        s["ask"] = key
        if key == "course_id":
            reply.append(f"Ganti mata kuliah dari {fallback} ke {value}?")
        else:
            reply.append(f"Biasanya kamu {_show(key, fallback)}, sekarang {_show(key, value)}? Benar?")
        return {**s, "reply": " ".join(reply), "done": False}

    missing = [k for k in ORDER if not _has(f, k)]
    if not missing:
        s["ask"] = None
        out = outside_range(f)
        if out:
            reply.append(f"{', '.join(out)} tidak ada di rentang {f['earliest_date']} sampai {f['latest_date']}, "
                         "jadi tidak akan cocok dengan siapa pun. Ubah di layar Periksa.")
        reply.append("Semua sudah terisi. Periksa dulu sebelum disimpan.")
        return {**s, "reply": " ".join(reply), "done": True}
    key = missing[0]
    s["ask"] = key
    if key in usual and key not in s["declined"] and usual[key]:
        s["suggest"] = usual[key]
        reply.append(f"Biasanya kamu {_show(key, usual[key])}. Pakai itu lagi?")
    else:
        reply.append(QUESTIONS[key])
    return {**s, "reply": " ".join(reply), "done": False}


def outside_range(fields: dict) -> list[str]:
    """Hari atau tanggal di waktu kosong yang tidak ada di rentang tanggal permintaan."""
    first, last = date.fromisoformat(fields["earliest_date"]), date.fromisoformat(fields["latest_date"])
    days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    names = {DAYS[d.weekday()] for d in days}
    return [s["day_or_date"] for s in fields["availabilities"]
            if (s["day_or_date"] not in names if s["day_or_date"] in DAYS else
                not first.isoformat() <= s["day_or_date"] <= last.isoformat())]


def to_form(fields: dict) -> dict:
    """Isian chat ke bentuk StudyIntentCreate, untuk layar Periksa. Field kosong dibiarkan kosong."""
    keys = ("course_id", "topics", "learning_goal", "collaboration_style", "learning_mode",
            "earliest_date", "latest_date", "min_group_size", "max_group_size", "availabilities")
    return {k: fields[k] for k in keys if k in fields}
