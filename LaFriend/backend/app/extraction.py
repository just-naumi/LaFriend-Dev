# ==============================================================================
# extraction.py - Pipeline Ekstraksi AI untuk Study Intent (GLiNER + Normalizer)
# ==============================================================================
# File ini bertugas untuk:
# 1. Menerima 1 pesan teks curhatan belajar dari mahasiswa dalam Bahasa Indonesia.
# 2. Menjalankan model AI GLiNER (Zero-Shot Named Entity Recognition) secara lokal.
# 3. Mengekstrak entitas penting (Mata kuliah, topik, tujuan, gaya, waktu, grup).
# 4. Melakukan normalisasi ke format parameter resmi LaFriend & validasi SQLite.
# 5. Mengembalikan data terstruktur yang siap mengisi formulir secara otomatis.
# ==============================================================================

import os
import re
import json
import logging
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
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
# 1. KAMUS PEMETAAN NORMALISASI (NORMALIZATION DICTIONARY)
# ==============================================================================

GOAL_PATTERNS = {
    "EXAM_PREP": ["uas", "uts", "ujian", "persiapan ujian", "persiapan uas", "persiapan uts", "midterm", "final exam", "kuis", "quiz", "kuis praktikum", "responsi", "responsi lab", "tes awal", "asessment 1", "asessment 2", "asessment", "remedial"],
    "PRACTICE": ["latihan soal", "latihan koding", "latihan", "ngoding bareng", "praktik", "solve problem", "soal", "ngoding"],
    "ASSIGNMENT": ["tugas", "tubes", "tugas besar", "praktikum", "laporan", "pr", "jurnal praktikum", "tugas mingguan", "nyicil tubes"],
    "DISCUSSION": ["diskusi", "bedah materi", "sharing materi", "brainstorming", "tanya jawab", "bahas tuntas"],
    "UNDERSTAND": ["paham", "pemahaman", "konsep", "belajar dasar", "materi awal", "mengerti", "dasar"]
}

STYLE_PATTERNS = {
    "PRACTICE": ["praktik", "latihan bersama", "hands on", "ngoding", "live coding"],
    "DISCUSSION": ["diskusi interaktif", "diskusi", "tanya jawab", "aktif diskusi", "bedah materi", "sharing"],
    "TEACHING": ["saling mengajar", "mengajar", "mentor", "peer tutoring", "ajari"],
    "FOCUS_STUDY": ["belajar tenang", "hening", "fokus", "silent study", "mandiri bareng", "nyicil"]
}

MODE_PATTERNS = {
    "ONLINE": ["online", "daring", "gmeet", "google meet", "zoom", "discord", "virtual"],
    "HYBRID": ["hybrid", "fleksibel", "bisa online bisa offline", "bebas"],
    "OFFLINE": [
        "offline", "tatap muka", "kampus", "perpus", "perpus telkom", "open library",
        "oplib", "mezzanine", "tult", "tult lantai 5", "kelas", "langsung",
        "selasar fte", "selasar fit", "selasar gd b", "kantin tult", "sukabirus",
        "sukapura", "kosan", "cafe sukabirus", "discussion room"
    ]
}

DAYS_LIST = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# ==============================================================================
# 2. FUNGSI PREPROCESSING
# ==============================================================================
def preprocess_text(text: str) -> str:
    """Membersihkan spasi ganda dan karakter tanpa menghilangkan esensi pesan."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


# ==============================================================================
# 3. FUNGSI DETEKSI DAN PEMETAAN PARAMETER
# ==============================================================================

def match_course_from_database(text_lower: str, db: Session, ai_entities: Optional[List[dict]] = None) -> Optional[Course]:
    """Mencari apakah teks menyebutkan salah satu mata kuliah resmi di SQLite."""
    courses = db.query(Course).all()

    # 1. Cek dari entitas yang diekstrak oleh AI jika ada
    if ai_entities:
        for ent in ai_entities:
            ent_text = ent.get("text", "").lower().strip()
            for c in courses:
                if c.course_name.lower() in ent_text or ent_text in c.course_name.lower():
                    if len(ent_text) >= 4:  # Hindari false positive substring pendek
                        return c
    
    # 2. Cek kecocokan nama mata kuliah lengkap di teks utuh
    for c in courses:
        if c.course_name.lower() in text_lower:
            return c
        if c.course_code.lower() in text_lower:
            return c
            
    # 3. Cek kecocokan kata kunci singkatan umum di Telkom University
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
        "algoritma": "Algoritma Pemrograman",
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
        if alias in text_lower:
            matched = db.query(Course).filter(Course.course_name.ilike(f"%{full_name}%")).first()
            if matched:
                return matched
                
    return None


def extract_learning_goal(text_lower: str) -> str:
    """Mendeteksi tujuan belajar dari teks."""
    for goal, keywords in GOAL_PATTERNS.items():
        for kw in keywords:
            if kw in text_lower:
                return goal
    return "UNDERSTAND"


def extract_collaboration_style(text_lower: str) -> str:
    """Mendeteksi gaya belajar dari teks."""
    for style, keywords in STYLE_PATTERNS.items():
        for kw in keywords:
            if kw in text_lower:
                return style
    return "DISCUSSION"


def extract_learning_mode(text_lower: str) -> str:
    """Mendeteksi mode belajar (offline/online/hybrid)."""
    if "tidak mau online" in text_lower or "bukan online" in text_lower:
        return "OFFLINE"
    if "tidak mau offline" in text_lower or "bukan offline" in text_lower:
        return "ONLINE"

    for mode, keywords in MODE_PATTERNS.items():
        for kw in keywords:
            if kw in text_lower:
                return mode
    return "OFFLINE"


def extract_group_size(text: str) -> (int, int):
    """Mendeteksi ukuran kelompok belajar (misal: 2-4 orang, 3 orang)."""
    # Pola rentang: "2 sampai 4 orang" atau "2-4 orang"
    range_match = re.search(
        r"(?:kelompok|group)?\s*(\d+)\s*(?:sampai|s/d|-|hingga)\s*(\d+)\s*(?:orang|mahasiswa|anggota|anak|teman)",
        text,
        re.IGNORECASE
    )
    if range_match:
        val1 = int(range_match.group(1))
        val2 = int(range_match.group(2))
        return min(val1, val2), max(val1, val2)

    group_range_match = re.search(
        r"(?:kelompok|group)\s*(\d+)\s*(?:sampai|s/d|-|hingga)\s*(\d+)",
        text,
        re.IGNORECASE
    )
    if group_range_match:
        val1 = int(group_range_match.group(1))
        val2 = int(group_range_match.group(2))
        return min(val1, val2), max(val1, val2)

    # Pola angka tunggal: "3 orang", "kelompok 4", "bertiga"
    single_match = re.search(r"(\d+)\s*(?:orang|mahasiswa|anggota)", text, re.IGNORECASE)
    if single_match:
        val = int(single_match.group(1))
        return val, val

    if "berdua" in text.lower():
        return 2, 2
    if "bertiga" in text.lower():
        return 3, 3
    if "berempat" in text.lower():
        return 4, 4

    return 2, 4


def extract_availabilities(text: str) -> List[Dict[str, Any]]:
    """Mengekstrak hari dan jam ketersediaan waktu."""
    results = []
    text_lower = text.lower()

    found_days = []
    for day in DAYS_LIST:
        if day.lower() in text_lower:
            found_days.append(day)

    start_time = "09:00"
    end_time = "12:00"

    time_match = re.search(r"(?:jam|pukul)?\s*(\d{1,2})[.:](\d{2})?\s*(?:sampai|s/d|-|hingga)\s*(?:jam|pukul)?\s*(\d{1,2})[.:]?(\d{2})?", text, re.IGNORECASE)
    if time_match:
        s_hour = int(time_match.group(1))
        s_min = time_match.group(2) or "00"
        e_hour = int(time_match.group(3))
        e_min = time_match.group(4) or "00"

        start_time = f"{s_hour:02d}:{s_min}"
        end_time = f"{e_hour:02d}:{e_min}"
    else:
        simple_time = re.search(r"(?:jam|pukul)\s*(\d{1,2})\s*(?:sampai|s/d|-|hingga)\s*(\d{1,2})", text, re.IGNORECASE)
        if simple_time:
            s_hour = int(simple_time.group(1))
            e_hour = int(simple_time.group(2))
            start_time = f"{s_hour:02d}:00"
            end_time = f"{e_hour:02d}:00"
        else:
            single_time = re.search(r"(?:jam|pukul)\s*(\d{1,2})[.:]?(\d{2})?", text, re.IGNORECASE)
            if single_time:
                s_hour = int(single_time.group(1))
                s_min = single_time.group(2) or "00"
                start_time = f"{s_hour:02d}:{s_min}"
                end_time = f"{(s_hour + 2) % 24:02d}:{s_min}"

    if found_days:
        for idx, d in enumerate(found_days):
            results.append({
                "day_or_date": d,
                "start_time": start_time,
                "end_time": end_time,
                "priority_rank": idx + 1
            })
    else:
        results.append({
            "day_or_date": "Rabu",
            "start_time": start_time,
            "end_time": end_time,
            "priority_rank": 1
        })

    return results


def extract_topics(raw_text: str, course_name: Optional[str], ai_entities: Optional[List[dict]] = None) -> str:
    """Mengekstrak topik belajar dengan cerdas memadukan pemahaman konteks dan entitas AI."""
    # 1. Coba pola kalimat natural mahasiswa terlebih dahulu:
    # Contoh: "belajar Binary Tree dan AVL Tree buat..." -> "Binary Tree dan AVL Tree"
    match = re.search(
        r"(?:belajar|materi|topik|khususnya|tentang|bahas|diskusi)\s+([^.,;]+?)(?:\s+(?:untuk|buat|karena|pada|secara|hari|jam|kelompok|bareng|persiapan)|[.,;]|$)",
        raw_text,
        re.IGNORECASE
    )
    if match:
        extracted = match.group(1).strip()
        extracted = re.sub(r"^(?:soal|materi|topik|tentang|mengenai)\s+", "", extracted, flags=re.IGNORECASE).strip()
        if course_name and extracted.lower() != course_name.lower() and len(extracted) >= 3:
            return extracted
        elif not course_name and len(extracted) >= 3:
            return extracted

    # 2. Jika tidak ada pola kalimat langsung, kumpulkan dari entitas GLiNER yang relevan
    if ai_entities:
        topic_parts = []
        for ent in ai_entities:
            label = ent.get("label", "")
            text_ent = ent.get("text", "").strip()
            if label in ["study topic", "topic"]:
                if course_name and text_ent.lower() in course_name.lower():
                    continue
                if len(text_ent) >= 3:
                    topic_parts.append(text_ent)
        if topic_parts:
            return ", ".join(dict.fromkeys(topic_parts))

    return "Pembahasan Materi & Latihan Soal"


# ==============================================================================
# 4. PIPELINE EKSTRAKSI UTAMA
# ==============================================================================
def process_chat_for_study_intent(raw_text: str, db: Session) -> Dict[str, Any]:
    """
    Fungsi Utama:
    Menerima 1 pesan mentah dari mahasiswa -> mengekstrak entitas dengan GLiNER ->
    melakukan normalisasi parameter -> menghasilkan objek data lengkap untuk form frontend.
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
                ["course", "study topic", "learning goal", "schedule", "group size", "study mode"],
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

    # 2. Deteksi mata kuliah dari database SQLite
    course = match_course_from_database(text_lower, db, ai_entities)
    course_id = course.course_id if course else None
    course_name = course.course_name if course else None

    # 3. Deteksi Topik Materi (Dipadukan dengan AI Entities)
    topics = extract_topics(cleaned_text, course_name, ai_entities)

    # 4. Deteksi Parameter Tujuan, Gaya, Mode, dan Ukuran Grup
    learning_goal = extract_learning_goal(text_lower)
    collaboration_style = extract_collaboration_style(text_lower)
    learning_mode = extract_learning_mode(text_lower)
    min_size, max_size = extract_group_size(cleaned_text)

    # 5. Deteksi Jadwal Waktu Ketersediaan
    availabilities = extract_availabilities(cleaned_text)

    # 6. Rentang Tanggal Default: Hari ini s/d 7 hari ke depan
    today = datetime.now().strftime("%Y-%m-%d")
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    # 7. Format data balasan terstruktur
    return {
        "status": "success",
        "course_id": course_id,
        "course_name": course_name,
        "topics": topics,
        "learning_goal": learning_goal,
        "collaboration_style": collaboration_style,
        "learning_mode": learning_mode,
        "earliest_date": today,
        "latest_date": next_week,
        "min_group_size": min_size,
        "max_group_size": max_size,
        "availabilities": availabilities,
        "extracted_summary": {
            "course": "EXTRACTED" if course else "MISSING",
            "topics": "EXTRACTED" if topics else "MISSING",
            "learning_goal": "EXTRACTED",
            "collaboration_style": "EXTRACTED",
            "learning_mode": "EXTRACTED",
            "availability": "EXTRACTED" if availabilities else "MISSING",
            "group_size": "EXTRACTED"
        },
        "ai_model": model_name_tag,
        "ai_raw_entities": ai_entities,
        "message": "Informasi berhasil diekstrak oleh AI. Silakan verifikasi dan sesuaikan di formulir bawah ini."
    }
