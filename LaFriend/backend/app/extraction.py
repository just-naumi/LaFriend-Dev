# ==============================================================================
# extraction.py - Pipeline Ekstraksi AI untuk Study Intent (GLiNER + Normalizer)
# ==============================================================================
# File ini bertugas untuk:
# 1. Menerima 1 pesan teks bebas dari mahasiswa dalam Bahasa Indonesia.
# 2. Menjalankan model AI GLiNER secara lokal (Span-Level NER).
# 3. Mengekstrak entitas & normalisasi parameter ke format resmi LaFriend.
# 4. Memastikan Data Integrity: TIDAK ADA DATA PALSU (Null jika tidak disebut).
# 5. Memberikan 3 Status Ekstraksi: EXTRACTED, NEEDS_REVIEW, MISSING.
# 6. Memisahkan Learning Mode, Physical Location, dan Online Platform.
# ==============================================================================

import os
import re
import json
import logging
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from sqlalchemy.orm import Session
from app.models import Course

logger = logging.getLogger("lafriend.extraction")

# Global singleton untuk model GLiNER
_gliner_model = None

def get_gliner_model():
    """
    Mengambil instance model GLiNER lokal secara singleton.
    Memastikan konfigurasi lokal mengarah ke weights/deberta_v3_small secara offline.
    """
    global _gliner_model
    if _gliner_model is not None:
        return _gliner_model

    base_dir = Path(__file__).resolve().parent / "weights"
    gliner_dir = base_dir / "gliner_small"
    deb_dir = base_dir / "deberta_v3_small"

    # Pastikan file konfigurasi GLiNER mengarah ke direktori deberta_v3_small lokal
    cfg_file = gliner_dir / "gliner_config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("model_name") != str(deb_dir):
                cfg["model_name"] = str(deb_dir)
                with open(cfg_file, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
        except Exception as e:
            logger.warning(f"Gagal sinkronisasi path gliner_config.json: {e}")

    try:
        from gliner import GLiNER
        logger.info(f"Memuat model GLiNER dari {gliner_dir}...")
        _gliner_model = GLiNER.from_pretrained(str(gliner_dir), local_files_only=True)
        logger.info("Model GLiNER berhasil dimuat secara offline.")
    except Exception as e:
        logger.error(f"Error saat memuat GLiNER: {e}")
        _gliner_model = None

    return _gliner_model


# ==============================================================================
# 1. KAMUS PEMETAAN NORMALISASI (NORMALIZATION DICTIONARIES)
# ==============================================================================

GOAL_PATTERNS = {
    "EXAM_PREP": [
        "uas", "uts", "ujian", "persiapan ujian", "persiapan uas", "persiapan uts",
        "midterm", "final exam", "kuis", "quiz", "kuis praktikum", "responsi",
        "responsi lab", "tes awal", "asessment 1", "asessment 2", "asessment",
        "remedial", "bedah soal", "latihan soal uts", "latihan soal uas"
    ],
    "PRACTICE": [
        "latihan soal", "latihan koding", "latihan", "ngoding bareng", "praktik",
        "solve problem", "soal", "ngoding", "latihan mandiri"
    ],
    "ASSIGNMENT": [
        "tugas", "tubes", "tugas besar", "praktikum", "laporan", "pr",
        "jurnal praktikum", "tugas mingguan", "nyicil tubes"
    ],
    "DISCUSSION": [
        "diskusi", "bedah materi", "sharing materi", "brainstorming", "tanya jawab", "bahas tuntas"
    ],
    "UNDERSTAND": [
        "paham", "memahami", "pemahaman", "konsep", "belajar dasar", "materi awal",
        "mengerti", "dasar", "pendalaman materi"
    ]
}

STYLE_PATTERNS = {
    "PRACTICE": ["praktik", "latihan bersama", "hands on", "ngoding", "live coding"],
    "DISCUSSION": ["diskusi interaktif", "diskusi", "tanya jawab", "aktif diskusi", "bedah materi", "sharing"],
    "TEACHING": ["saling mengajar", "mengajar", "mentor", "peer tutoring", "ajari"],
    "FOCUS_STUDY": ["belajar tenang", "hening", "fokus", "silent study", "mandiri bareng", "nyicil"]
}

PHYSICAL_LOCATION_PATTERNS = {
    "Open Library": ["open library", "oplib", "mezzanine oplib", "mezzanine", "discussion room oplib", "discussion room"],
    "TULT": ["tult lantai 5", "tult lt 5", "tult", "gedung tult"],
    "Kantin TULT": ["kantin tult"],
    "Selasar FTE": ["selasar fte", "lab komputer fte", "fte"],
    "Selasar Gd B": ["selasar gd b", "gedung b"],
    "Sukabirus": ["sukabirus", "kosan sukabirus", "cafe sukabirus"],
    "Sukapura": ["sukapura", "kosan sukapura"]
}

ONLINE_PLATFORM_PATTERNS = {
    "Google Meet": ["google meet", "gmeet", "g-meet"],
    "Discord": ["discord", "dc"],
    "Zoom": ["zoom", "zoom meeting"],
    "Microsoft Teams": ["teams", "ms teams", "microsoft teams"]
}

DAYS_LIST = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# ==============================================================================
# 2. PREPROCESSING
# ==============================================================================

def preprocess_text(text: str) -> str:
    """Membersihkan spasi ganda dan karakter tanpa menghilangkan esensi pesan."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    # Normalisasi dash Unicode (en-dash \u2013, em-dash \u2014) menjadi hyphen standar
    normalized = re.sub(r"[–—]", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()



# ==============================================================================
# 3. EXTRACTION LOGIC PER PARAMETER
# ==============================================================================

def match_course_from_database(
    text_lower: str,
    db: Session,
    ai_entities: Optional[List[dict]] = None
) -> Tuple[Optional[Course], str, Optional[str]]:
    """
    Mencari apakah teks menyebutkan salah satu mata kuliah resmi di SQLite.
    Returns: (course_obj, status, source_text)
    Status: 'EXTRACTED' | 'MISSING'
    """
    courses = db.query(Course).all()

    # 1. Cek dari entitas AI yang berlabel 'course'
    if ai_entities:
        for ent in ai_entities:
            if ent.get("label") == "course":
                ent_text = ent.get("text", "").lower().strip()
                if len(ent_text) >= 3:
                    for c in courses:
                        if c.course_name.lower() == ent_text:
                            return c, "EXTRACTED", ent.get("text")
                    for c in courses:
                        if c.course_name.lower() in ent_text or ent_text in c.course_name.lower():
                            if len(ent_text) >= 4:
                                return c, "EXTRACTED", ent.get("text")

    # 2. Cek kecocokan nama mata kuliah lengkap di teks utuh
    for c in courses:
        pattern = r"\b" + re.escape(c.course_name.lower()) + r"\b"
        match = re.search(pattern, text_lower)
        if match:
            return c, "EXTRACTED", match.group(0)
        code_pat = r"\b" + re.escape(c.course_code.lower()) + r"\b"
        code_match = re.search(code_pat, text_lower)
        if code_match:
            return c, "EXTRACTED", code_match.group(0)

    # 3. Cek kamus alias singkatan resmi di lingkungan Telkom University
    keyword_alias = {
        # Semester 1
        "kalkulus 1": "Kalkulus 1",
        "kalkul 1": "Kalkulus 1",
        "fisika 1": "Fisika 1",
        "fisdas 1": "Fisika 1",
        "kimia": "Kimia",
        "ptk": "Pengenalan Teknik Komputer",
        "pengenalan tekkom": "Pengenalan Teknik Komputer",
        "logmat": "Logika Matematika",
        "logika matematika": "Logika Matematika",
        "prd": "Pengantar Rekayasa dan Desain",
        "rekayasa desain": "Pengantar Rekayasa dan Desain",
        # Semester 2
        "kalkulus 2": "Kalkulus 2",
        "kalkul 2": "Kalkulus 2",
        "fisika 2": "Fisika 2",
        "fisdas 2": "Fisika 2",
        "alpro": "Algoritma Pemrograman",
        "algoritma pemrograman": "Algoritma Pemrograman",
        "matdis": "Matematika Diskrit",
        "diskrit": "Matematika Diskrit",
        "jarkom data": "Jaringan Komputer dan Data",
        # Semester 3
        "strukdat": "Struktur Data",
        "struktur data": "Struktur Data",
        "kamjar": "Keamanan Jaringan",
        "keamanan jaringan": "Keamanan Jaringan",
        "rl": "Rangkaian Listrik",
        "rangkaian listrik": "Rangkaian Listrik",
        "pdl": "Persamaan Diferensial",
        "pers diff": "Persamaan Diferensial",
        "persamaan diferensial": "Persamaan Diferensial",
        "probstat": "Probabilitas dan Statistika",
        "alin": "Aljabar Linier",
        "aljabar linier": "Aljabar Linier",
        # Semester 4
        "sisdig": "Sistem Digital",
        "sistem digital": "Sistem Digital",
        "teknik digital": "Sistem Digital",
        "elka": "Elektronika",
        "elektronika": "Elektronika",
        "cloud": "Komputasi Awan",
        "komputasi awan": "Komputasi Awan",
        "sinyal kontinu": "Pengolahan Sinyal Waktu Kontinu",
        "ads": "Analisis dan Desain Sistem",
        "catu daya": "Perancangan Catu Daya",
        "power supply": "Perancangan Catu Daya",
        # Semester 5
        "orkom": "Organisasi dan Arsitektur Komputer",
        "arkom": "Organisasi dan Arsitektur Komputer",
        "arsitektur komputer": "Organisasi dan Arsitektur Komputer",
        "sismin": "Sistem Mikroprosesor",
        "mikroprosesor": "Sistem Mikroprosesor",
        "mikrokontroler": "Sistem Mikroprosesor",
        "basdat": "Basis Data",
        "basis data": "Basis Data",
        "jarkom lanjut": "Sistem Jaringan Lanjut",
        "routing": "Sistem Jaringan Lanjut",
        "jarkom": "Jaringan Komputer",
        "dsp": "Pengolahan Sinyal Digital",
        "sinyal digital": "Pengolahan Sinyal Digital",
        # Semester 6
        "sisbed": "Sistem Tertanam",
        "embedded": "Sistem Tertanam",
        "sistem tertanam": "Sistem Tertanam",
        "iot": "Sistem Tertanam & IoT",
        "sisop": "Sistem Operasi",
        "sistem operasi": "Sistem Operasi",
        "rtos": "Sistem Operasi & RTOS",
        "ai": "Kecerdasan Buatan",
        "machine learning": "Kecerdasan Buatan & Machine Learning",
        "ml": "Kecerdasan Buatan & Machine Learning",
        "kecerdasan buatan": "Kecerdasan Buatan & Machine Learning",
        "robotika": "Sistem Kendali dan Robotika",
        "sistem kendali": "Sistem Kendali dan Robotika",
        # Semester 7 & 8
        "manpro": "Manajemen Proyek TI",
        "manajemen proyek": "Manajemen Proyek TI",
        "kamsis": "Keamanan Sistem Komputer",
        "pemrograman web": "Pemrograman Web",
        "web programming": "Pemrograman Web",
        "proposal ta": "Proposal Tugas Akhir",
        "pra-ta": "Proposal Tugas Akhir",
        "ta": "Tugas Akhir / Skripsi",
        "skripsi": "Tugas Akhir / Skripsi",
        "tugas akhir": "Tugas Akhir / Skripsi",
        # Peminatan
        "deep learning": "Pembelajaran Mendalam (Deep Learning)",
        "dl": "Pembelajaran Mendalam (Deep Learning)",
        "komputer forensik": "Komputer Forensik",
        "forensik": "Komputer Forensik",
        "devsecops": "DevSecOps",
        "vlsi": "Perancangan Sistem VLSI",
        "fpga": "Perancangan Sistem VLSI",
        "big data": "Teknologi Big Data",
        "kalkulus": "Kalkulus"
    }

    for alias, full_name in keyword_alias.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        match = re.search(pattern, text_lower)
        if match:
            matched = db.query(Course).filter(Course.course_name.ilike(f"%{full_name}%")).first()
            if matched:
                return matched, "EXTRACTED", match.group(0)

    return None, "MISSING", None


def extract_topics(
    raw_text: str,
    course_name: Optional[str],
    ai_entities: Optional[List[dict]] = None
) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Mengekstrak topik materi belajar tanpa default palsu.
    Returns: (topic_string, status, source_text)
    Status: 'EXTRACTED' | 'MISSING'
    """
    # 1. Cek entitas AI berlabel 'topic' terlebih dahulu
    if ai_entities:
        topic_parts = []
        for ent in ai_entities:
            label = ent.get("label", "")
            text_ent = ent.get("text", "").strip()
            if label in ["topic", "study topic"]:
                if course_name and text_ent.lower() in course_name.lower():
                    continue
                if len(text_ent) >= 3:
                    topic_parts.append(text_ent)
        if topic_parts:
            unique_topics = list(dict.fromkeys(topic_parts))
            return ", ".join(unique_topics), "EXTRACTED", ", ".join(unique_topics)

    # 2. Coba pola kalimat natural mahasiswa (e.g. "memahami Binary Tree", "bahas AVL Tree")
    match = re.search(
        r"(?:memahami|materi|topik|khususnya|tentang|bahas|bab|mempelajari)\s+([^.,;]+?)(?:\s+(?:untuk|buat|karena|pada|secara|hari|jam|kelompok|bareng|persiapan|bersama)|[.,;]|$)",
        raw_text,
        re.IGNORECASE
    )
    if match:
        extracted = match.group(1).strip()
        extracted = re.sub(r"^(?:soal|materi|topik|tentang|mengenai)\s+", "", extracted, flags=re.IGNORECASE).strip()
        # Hindari menganggap nama mata kuliah sebagai topik jika sama persis
        if course_name and extracted.lower() == course_name.lower():
            return None, "MISSING", None
        if len(extracted) >= 3:
            return extracted, "EXTRACTED", match.group(0)

    return None, "MISSING", None


def extract_learning_goal(
    text_lower: str,
    ai_entities: Optional[List[dict]] = None
) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Mendeteksi tujuan belajar dari teks tanpa default palsu.
    Returns: (goal, status, source_text)
    Status: 'EXTRACTED' | 'MISSING'
    """
    # 1. Cek apakah ada konteks ujian (UTS/UAS/ujian/kuis)
    # Konteks ujian memiliki prioritas tertinggi (misal: 'latihan soal UTS' -> tujuan utamanya EXAM_PREP)
    exam_terms = ["uts", "uas", "ujian", "kuis", "midterm", "final exam", "responsi"]
    for term in exam_terms:
        if re.search(r"\b" + re.escape(term) + r"\b", text_lower):
            for kw in sorted(GOAL_PATTERNS["EXAM_PREP"], key=len, reverse=True):
                if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                    return "EXAM_PREP", "EXTRACTED", kw
            return "EXAM_PREP", "EXTRACTED", term

    # 2. Cek entitas AI
    if ai_entities:
        for ent in ai_entities:
            if ent.get("label") in ["learning_goal", "goal", "exam_prep"]:
                txt = ent.get("text", "").lower()
                for goal, keywords in GOAL_PATTERNS.items():
                    for kw in keywords:
                        if kw in txt:
                            return goal, "EXTRACTED", ent.get("text")

    # 3. Cek kecocokan kata kunci dengan word-boundary (prioritaskan kata/frasa terpanjang)
    candidates = []
    for goal, keywords in GOAL_PATTERNS.items():
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            match = re.search(pattern, text_lower)
            if match:
                candidates.append((len(kw), goal, match.group(0)))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1], "EXTRACTED", candidates[0][2]

    return None, "MISSING", None




def extract_collaboration_style(
    text_lower: str
) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Mendeteksi gaya belajar dari teks tanpa default palsu.
    Returns: (style, status, source_text)
    Status: 'EXTRACTED' | 'MISSING'
    """
    for style, keywords in STYLE_PATTERNS.items():
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            match = re.search(pattern, text_lower)
            if match:
                return style, "EXTRACTED", match.group(0)

    return None, "MISSING", None


def extract_mode_and_locations(
    text_lower: str,
    raw_text: str,
    ai_entities: Optional[List[dict]] = None
) -> Dict[str, Any]:
    """
    Memisahkan secara tegas:
    - learning_mode (OFFLINE, ONLINE, HYBRID / ['OFFLINE', 'ONLINE'])
    - physical_location (Open Library, TULT, Selasar FTE, Sukabirus, dll. atau Kampus [NEEDS_REVIEW])
    - online_platform (Google Meet, Discord, Zoom, Teams)
    Mendukung deteksi negasi ('tidak mau online') dan multi-mode ('bisa online maupun offline').
    """
    result = {
        "learning_mode": {"value": None, "status": "MISSING", "source_text": None},
        "physical_location": {"value": None, "status": "MISSING", "source_text": None},
        "online_platform": {"value": None, "status": "MISSING", "source_text": None},
        "preferred_location": None,
    }

    # 1. Deteksi Platform Online Spesifik
    for plat_name, keywords in ONLINE_PLATFORM_PATTERNS.items():
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            match = re.search(pattern, text_lower)
            if match:
                result["online_platform"] = {
                    "value": plat_name,
                    "status": "EXTRACTED",
                    "source_text": match.group(0)
                }
                break
        if result["online_platform"]["value"]:
            break

    # 2. Deteksi Lokasi Fisik Spesifik
    for loc_name, keywords in PHYSICAL_LOCATION_PATTERNS.items():
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            match = re.search(pattern, text_lower)
            if match:
                result["physical_location"] = {
                    "value": loc_name,
                    "status": "EXTRACTED",
                    "source_text": match.group(0)
                }
                break
        if result["physical_location"]["value"]:
            break

    # Jika tidak ada lokasi fisik spesifik, cek apakah ada sebutan umum 'kampus'
    if not result["physical_location"]["value"]:
        kampus_match = re.search(r"\b(?:di\s+)?kampus\b", text_lower)
        if kampus_match:
            result["physical_location"] = {
                "value": "Kampus",
                "status": "NEEDS_REVIEW",  # Terlalu luas / umum, butuh konfirmasi gedung
                "source_text": kampus_match.group(0)
            }

    # 3. Deteksi Negasi
    neg_online = re.search(r"\b(?:tidak\s+mau|bukan|jangan|nggak\s+mau|gak\s+mau|ogah|enggan)\s+(?:belajar\s+)?online\b", text_lower)
    neg_offline = re.search(r"\b(?:tidak\s+mau|bukan|jangan|nggak\s+mau|gak\s+mau|ogah|enggan)\s+(?:belajar\s+)?(?:offline|tatap muka|ke kampus)\b", text_lower)

    if neg_online:
        result["learning_mode"] = {
            "value": "OFFLINE",
            "status": "EXTRACTED",
            "source_text": neg_online.group(0)
        }
    elif neg_offline:
        result["learning_mode"] = {
            "value": "ONLINE",
            "status": "EXTRACTED",
            "source_text": neg_offline.group(0)
        }
    else:
        # 4. Deteksi Multi-mode / Fleksibilitas (Online maupun Offline)
        multi_pattern = re.search(
            r"\b(?:bisa\s+online\s+maupun\s+offline|bisa\s+offline\s+maupun\s+online|online\s+maupun\s+offline|offline\s+maupun\s+online|bisa\s+online\s+atau\s+offline|bisa\s+offline\s+atau\s+online|online\s+atau\s+offline|offline\s+atau\s+online|bisa\s+dua-duanya|bebas\s+online\s+atau\s+offline)\b",
            text_lower
        )
        if multi_pattern:
            result["learning_mode"] = {
                "value": ["OFFLINE", "ONLINE"],
                "status": "EXTRACTED",
                "source_text": multi_pattern.group(0)
            }
        # 5. Jika lokasi fisik DAN online platform keduanya disebut (misal: "di kampus atau Google Meet")
        elif result["physical_location"]["value"] and result["online_platform"]["value"]:
            combined_src = f"{result['physical_location']['source_text']} atau {result['online_platform']['source_text']}"
            result["learning_mode"] = {
                "value": ["OFFLINE", "ONLINE"],
                "status": "EXTRACTED",
                "source_text": combined_src
            }
        else:
            # 6. Deteksi Kata Kunci Mode Tunggal
            has_offline_word = bool(re.search(r"\b(?:offline|tatap muka)\b", text_lower))
            has_online_word = bool(re.search(r"\b(?:online|daring)\b", text_lower))
            has_hybrid_word = bool(re.search(r"\b(?:hybrid|fleksibel)\b", text_lower))

            if has_hybrid_word:
                result["learning_mode"] = {
                    "value": "HYBRID",
                    "status": "EXTRACTED",
                    "source_text": "hybrid"
                }
            elif has_offline_word:
                result["learning_mode"] = {
                    "value": "OFFLINE",
                    "status": "EXTRACTED",
                    "source_text": "offline"
                }
            elif has_online_word:
                result["learning_mode"] = {
                    "value": "ONLINE",
                    "status": "EXTRACTED",
                    "source_text": "online"
                }
            elif result["physical_location"]["value"]:
                # Lokasi fisik mengindikasikan belajar tatap muka
                result["learning_mode"] = {
                    "value": "OFFLINE",
                    "status": "EXTRACTED",
                    "source_text": result["physical_location"]["source_text"]
                }
            elif result["online_platform"]["value"]:
                # Platform online mengindikasikan belajar daring
                result["learning_mode"] = {
                    "value": "ONLINE",
                    "status": "EXTRACTED",
                    "source_text": result["online_platform"]["source_text"]
                }

    # Backward compatibility: preferred_location
    if result["physical_location"]["value"]:
        result["preferred_location"] = result["physical_location"]["value"]
    elif result["online_platform"]["value"]:
        result["preferred_location"] = result["online_platform"]["value"]

    return result


def extract_group_size(
    text: str,
    ai_entities: Optional[List[dict]] = None
) -> Tuple[Optional[int], Optional[int], str, Optional[str]]:
    """
    Mendeteksi ukuran kelompok belajar tanpa default palsu.
    Returns: (min_size, max_size, status, source_text)
    Status: 'EXTRACTED' | 'MISSING'
    """
    target_text = text
    src_text = None
    if ai_entities:
        for ent in ai_entities:
            if ent.get("label") in ["group_size", "group"]:
                target_text = ent.get("text", text)
                src_text = ent.get("text")
                break

    # Pola rentang: "2 sampai 4 orang" atau "2-4 orang"
    range_match = re.search(
        r"(?:kelompok|group)?\s*(\d+)\s*(?:sampai|s/d|-|hingga)\s*(\d+)\s*(?:orang|mahasiswa|anggota|anak|teman)?",
        target_text,
        re.IGNORECASE
    )
    if range_match:
        val1 = int(range_match.group(1))
        val2 = int(range_match.group(2))
        return min(val1, val2), max(val1, val2), "EXTRACTED", range_match.group(0)

    # Pola angka tunggal: "4 orang", "kelompok 4", "berisi 4 orang"
    single_match = re.search(r"(?:kelompok|group|berisi)?\s*(\d+)\s*(?:orang|mahasiswa|anggota)", target_text, re.IGNORECASE)
    if single_match:
        val = int(single_match.group(1))
        return val, val, "EXTRACTED", single_match.group(0)

    # Sebutan kata bilangan bahasa Indonesia
    words_map = {
        "berdua": (2, 2),
        "bertiga": (3, 3),
        "berempat": (4, 4),
        "berlima": (5, 5)
    }
    for word, (mn, mx) in words_map.items():
        if re.search(r"\b" + re.escape(word) + r"\b", target_text.lower()):
            return mn, mx, "EXTRACTED", word

    # Tidak disebutkan -> return None (MISSING)
    return None, None, "MISSING", None


def extract_availabilities(
    text: str,
    ai_entities: Optional[List[dict]] = None
) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
    """
    Mengekstrak hari dan jam ketersediaan waktu secara jujur.
    Returns: (slots_list, status, source_text)
    Status: 'EXTRACTED' | 'NEEDS_REVIEW' | 'MISSING'
    """
    text_lower = text.lower()

    # 1. Cek apakah ada frasa eksplisit bahwa user belum punya jadwal
    no_schedule_match = re.search(
        r"\b(?:belum\s+tahu\s+jadwalnya|jadwal\s+belum\s+tahu|belum\s+ada\s+jadwal|jadwal\s+menyusul|belum\s+menentukan\s+jadwal)\b",
        text_lower
    )
    if no_schedule_match:
        return [], "MISSING", no_schedule_match.group(0)

    results = []

    # 2. Deteksi Hari
    found_days = []
    for day in DAYS_LIST:
        if re.search(r"\b" + re.escape(day.lower()) + r"\b", text_lower):
            found_days.append(day)

    # 3. Deteksi Jam Spesifik (e.g. 13.00-15.00, 13:00-15:00)
    start_time = None
    end_time = None
    time_src = None

    # Normalisasi teks lokal jika ada dash unicode
    text = re.sub(r"[–—]", "-", text)

    time_match = re.search(
        r"(?:jam|pukul)?\s*(\d{1,2})[.:](\d{2})?\s*(?:sampai|s/d|[-–—]|hingga)\s*(?:jam|pukul)?\s*(\d{1,2})[.:]?(\d{2})?",
        text,
        re.IGNORECASE
    )

    if time_match:
        s_hour = int(time_match.group(1))
        s_min = time_match.group(2) or "00"
        e_hour = int(time_match.group(3))
        e_min = time_match.group(4) or "00"
        start_time = f"{s_hour:02d}:{s_min}"
        end_time = f"{e_hour:02d}:{e_min}"
        time_src = time_match.group(0)
    else:
        simple_time = re.search(
            r"(?:jam|pukul)\s*(\d{1,2})\s*(?:sampai|s/d|-|hingga)\s*(\d{1,2})",
            text,
            re.IGNORECASE
        )
        if simple_time:
            s_hour = int(simple_time.group(1))
            e_hour = int(simple_time.group(2))
            start_time = f"{s_hour:02d}:00"
            end_time = f"{e_hour:02d}:00"
            time_src = simple_time.group(0)

    # 4. Deteksi Waktu Relatif / Kisaran (Pagi, Siang, Sore, Malam)
    # Ini ambigu sehingga harus ditandai NEEDS_REVIEW
    is_approximate_time = False
    if not start_time:
        if re.search(r"\bsore\b", text_lower):
            start_time = "15:00"
            end_time = "18:00"
            time_src = "sore"
            is_approximate_time = True
        elif re.search(r"\bpagi\b", text_lower):
            start_time = "08:00"
            end_time = "11:00"
            time_src = "pagi"
            is_approximate_time = True
        elif re.search(r"\bsiang\b", text_lower):
            start_time = "11:00"
            end_time = "14:00"
            time_src = "siang"
            is_approximate_time = True
        elif re.search(r"\bmalam\b", text_lower):
            start_time = "19:00"
            end_time = "21:00"
            time_src = "malam"
            is_approximate_time = True

    # 5. Bangun Hasil Slot Waktu
    if not found_days and not start_time:
        return [], "MISSING", None

    # Ada hari tapi tidak ada jam sama sekali -> NEEDS_REVIEW
    if found_days and not start_time:
        for idx, d in enumerate(found_days):
            results.append({
                "day_or_date": d,
                "start_time": "",
                "end_time": "",
                "priority_rank": idx + 1,
                "status": "NEEDS_TIME"
            })
        return results, "NEEDS_REVIEW", ", ".join(found_days)

    # Ada jam tapi tidak ada hari -> NEEDS_REVIEW
    if start_time and not found_days:
        results.append({
            "day_or_date": "",
            "start_time": start_time,
            "end_time": end_time,
            "priority_rank": 1,
            "status": "NEEDS_DAY"
        })
        return results, "NEEDS_REVIEW", time_src

    # Lengkap (Ada hari DAN ada jam)
    for idx, d in enumerate(found_days):
        results.append({
            "day_or_date": d,
            "start_time": start_time,
            "end_time": end_time,
            "priority_rank": idx + 1,
            "status": "COMPLETE" if not is_approximate_time else "APPROXIMATE_TIME"
        })

    overall_status = "NEEDS_REVIEW" if (is_approximate_time or len(found_days) > 1) else "EXTRACTED"
    combined_src = f"{', '.join(found_days)} {time_src}" if time_src else ", ".join(found_days)
    return results, overall_status, combined_src


# ==============================================================================
# 4. PIPELINE EKSTRAKSI UTAMA (PROCESS_CHAT_FOR_STUDY_INTENT)
# ==============================================================================

def process_chat_for_study_intent(raw_text: str, db: Session) -> Dict[str, Any]:
    """
    Fungsi Utama:
    Menerima 1 pesan mentah dari mahasiswa -> ekstraksi GLiNER & Normalizer ->
    memberikan format output terstruktur dengan 3 status: EXTRACTED, NEEDS_REVIEW, MISSING.
    Memastikan integritas data: parameter yang tidak disebut bernilai None / [].
    """
    cleaned_text = preprocess_text(raw_text)
    text_lower = cleaned_text.lower()

    # 1. Jalankan Model AI GLiNER Lokal
    ai_entities = []
    model_name_tag = "GLiNER-small-v2.1"
    try:
        model = get_gliner_model()
        if model is not None:
            raw_preds = model.predict_entities(
                cleaned_text,
                ["course", "topic", "learning_goal", "schedule", "group_size", "study_mode"],
                threshold=0.20
            )
            ai_entities = [
                {
                    "text": p["text"],
                    "label": p["label"],
                    "score": round(float(p["score"]), 3),
                    "start": p["start"],
                    "end": p["end"]
                }
                for p in raw_preds
            ]
    except Exception as e:
        logger.error(f"Error inferensi GLiNER: {e}")
        model_name_tag = "Pattern-Based Fallback (Offline)"

    # 2. Ekstraksi Course
    course, course_status, course_src = match_course_from_database(text_lower, db, ai_entities)
    course_id = course.course_id if course else None
    course_name = course.course_name if course else None

    # 3. Ekstraksi Topics
    topics, topic_status, topic_src = extract_topics(cleaned_text, course_name, ai_entities)

    # 4. Ekstraksi Learning Goal & Collaboration Style
    learning_goal, goal_status, goal_src = extract_learning_goal(text_lower, ai_entities)
    collaboration_style, style_status, style_src = extract_collaboration_style(text_lower)

    # 5. Ekstraksi Mode Belajar, Lokasi Fisik, dan Platform Online
    mode_loc = extract_mode_and_locations(text_lower, cleaned_text, ai_entities)
    learning_mode_obj = mode_loc["learning_mode"]
    phys_loc_obj = mode_loc["physical_location"]
    online_plat_obj = mode_loc["online_platform"]
    preferred_loc = mode_loc["preferred_location"]

    # 6. Ekstraksi Ukuran Kelompok
    min_size, max_size, group_status, group_src = extract_group_size(cleaned_text, ai_entities)

    # 7. Ekstraksi Jadwal Waktu Ketersediaan
    availabilities, avail_status, avail_src = extract_availabilities(cleaned_text, ai_entities)

    # Struktur parameter detail dengan status & source text (Task 3 & 4)
    extracted_parameters = {
        "course": {
            "value": course_name,
            "course_id": course_id,
            "status": course_status,
            "source_text": course_src
        },
        "topic": {
            "value": topics,
            "status": topic_status,
            "source_text": topic_src
        },
        "learning_goal": {
            "value": learning_goal,
            "status": goal_status,
            "source_text": goal_src
        },
        "collaboration_style": {
            "value": collaboration_style,
            "status": style_status,
            "source_text": style_src
        },
        "learning_mode": {
            "value": learning_mode_obj["value"],
            "status": learning_mode_obj["status"],
            "source_text": learning_mode_obj["source_text"]
        },
        "physical_location": {
            "value": phys_loc_obj["value"],
            "status": phys_loc_obj["status"],
            "source_text": phys_loc_obj["source_text"]
        },
        "online_platform": {
            "value": online_plat_obj["value"],
            "status": online_plat_obj["status"],
            "source_text": online_plat_obj["source_text"]
        },
        "group_size": {
            "value": {"min_group_size": min_size, "max_group_size": max_size} if min_size is not None else None,
            "status": group_status,
            "source_text": group_src
        },
        "availability": {
            "value": availabilities if availabilities else None,
            "status": avail_status,
            "source_text": avail_src
        }
    }

    # Summary dictionary status
    extraction_status = {
        "course": course_status,
        "topic": topic_status,
        "learning_goal": goal_status,
        "collaboration_style": style_status,
        "learning_mode": learning_mode_obj["status"],
        "physical_location": phys_loc_obj["status"],
        "online_platform": online_plat_obj["status"],
        "group_size": group_status,
        "availability": avail_status
    }

    # Format kompatibel dengan frontend radio button
    primary_mode_for_ui = None
    if isinstance(learning_mode_obj["value"], list):
        primary_mode_for_ui = "HYBRID"
    elif isinstance(learning_mode_obj["value"], str):
        primary_mode_for_ui = learning_mode_obj["value"]

    return {
        "status": "success",
        "course_id": course_id,
        "course_name": course_name,
        "topics": topics,
        "learning_goal": learning_goal,
        "collaboration_style": collaboration_style,
        "learning_mode": primary_mode_for_ui,
        "preferred_location": preferred_loc,
        "physical_location": phys_loc_obj["value"],
        "online_platform": online_plat_obj["value"],
        "earliest_date": None,
        "latest_date": None,
        "min_group_size": min_size,
        "max_group_size": max_size,
        "availabilities": availabilities,
        "extraction_status": extraction_status,
        "extracted_parameters": extracted_parameters,
        "source_text": raw_text,
        "ai_model": model_name_tag,
        "ai_raw_entities": ai_entities,
        "message": "Informasi berhasil diproses dengan aman (parameter tidak disebut dibiarkan kosong)."
    }


# Alias fungsi agar kompatibel dengan pemanggilan extract_study_intent
extract_study_intent = process_chat_for_study_intent
