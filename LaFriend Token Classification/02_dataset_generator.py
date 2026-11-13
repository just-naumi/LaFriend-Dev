"""
==============================================================================
02_dataset_generator.py - Pembuat Dataset Token Classification (NER) LaFriend
==============================================================================
Script ini bertugas untuk:
1. Menyusun struktur anotasi data token classification / span-level NER
   khusus untuk domain akademik Telkom University.
2. Menghasilkan dataset latihan (train) dan validasi (val) berformat JSON.
3. Mendukung 6 entitas spesifik:
   - course       : Nama mata kuliah resmi / singkatan umum (Struktur Data, Basdat, dll)
   - topic        : Topik materi yang ingin dipelajari (Binary Tree, Normalisasi, dll)
   - exam_prep    : Target ujian akademik (UAS, UTS, Kuis)
   - schedule     : Waktu dan hari ketersediaan belajar (Rabu jam 9-12, Kamis siang)
   - group_size   : Jumlah anggota kelompok (2-4 orang, 3 orang, berdua)
   - study_mode   : Mode dan lokasi belajar (tatap muka di perpus, online di Discord)
==============================================================================
"""

import json
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

# Domain Data Telkom University
COURSES = [
    ("Struktur Data", "strukdat"),
    ("Basis Data", "basdat"),
    ("Algoritma Pemrograman", "alpro"),
    ("Matematika Diskrit", "matdis"),
    ("Kalkulus", "kalkulus"),
    ("Jaringan Komputer", "jarkom"),
    ("Sistem Operasi", "sisop")
]

TOPICS_MAP = {
    "Struktur Data": ["Binary Tree", "AVL Tree", "Red-Black Tree", "Graph Dijkstra", "Linked List", "Stack dan Queue", "Hash Table", "Heap Sort"],
    "Basis Data": ["Normalisasi 1NF sampai 3NF", "Desain ERD", "Query SQL Join", "Agregasi GROUP BY", "Subquery", "Index dan Relasi"],
    "Algoritma Pemrograman": ["Percabangan dan Looping", "Rekursif", "Fungsi dan Prosedur", "Array Multidimensi", "Sorting dan Searching"],
    "Matematika Diskrit": ["Teori Graf", "Logika Proposisi", "Relasi dan Fungsi", "Kombinatorika", "Induksi Matematika"],
    "Kalkulus": ["Turunan dan Aplikasi", "Integral Tentu dan Tak Tentu", "Limit dan Kekontinuan", "Persamaan Diferensial Dasar"],
    "Jaringan Komputer": ["Subnetting IPv4", "Topologi Jaringan", "Konfigurasi Router Cisco", "Model OSI dan TCP/IP", "VLAN"],
    "Sistem Operasi": ["CPU Scheduling", "Deadlock Avoidance", "Manajemen Memori Paging", "Virtual Memory", "Sinkronisasi Process"]
}

DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
TIME_SLOTS = [
    "jam 9 sampai 12",
    "jam 09:00 - 12:00",
    "pukul 13:00 - 15:00",
    "jam 10 sampai 12",
    "jam 14:00 s/d 16:30",
    "pukul 8 pagi sampai 11"
]

MODES = [
    "tatap muka di perpus",
    "offline santai di TULT",
    "online via Google Meet",
    "online di Discord",
    "offline langsung di kampus",
    "hybrid fleksibel"
]

GROUP_SIZES = [
    "bareng 2 sampai 4 orang",
    "kelompok 3 orang",
    "bareng 2 orang",
    "maksimal 4 mahasiswa",
    "berdua aja",
    "kelompok 3-4 orang",
    "bareng 4 orang"
]

EXAMS = [
    "persiapan UAS",
    "persiapan UTS",
    "latihan kuis minggu depan",
    "persiapan ujian akhir",
    "kuis praktikum",
    "persiapan ujian tengah semester"
]

TEMPLATES = [
    "Saya mau belajar {topic} buat {exam} {course} hari {day} {time} {group} {mode}.",
    "Mau diskusi materi {topic} mata kuliah {course} kelompok {group} secara {mode} hari {day} {time}.",
    "Ada yang mau ngoding bareng {topic} untuk {course} {exam}? Yuk kumpul {mode} {day} {time} {group}.",
    "Latihan soal {topic} persiapan kuis {course} yuk, jadwalnya hari {day} {time} bareng {group} {mode}.",
    "Cari temen belajar {course} bab {topic} buat {exam}, preferensi {mode} hari {day} {time} {group}.",
    "Butuh partner diskusi {topic} mata kuliah {course} hari {day} {time} {mode} untuk {group}.",
    "Yuk bedah materi {topic} {course} {exam} hari {day} {time} {mode} {group}."
]

def generate_sample(template_idx=None):
    course_name, alias = random.choice(COURSES)
    chosen_course = course_name if random.random() > 0.4 else alias
    topic = random.choice(TOPICS_MAP[course_name])
    day = random.choice(DAYS)
    time = random.choice(TIME_SLOTS)
    schedule = f"{day} {time}"
    group = random.choice(GROUP_SIZES)
    mode = random.choice(MODES)
    exam = random.choice(EXAMS)

    tmpl = random.choice(TEMPLATES) if template_idx is None else TEMPLATES[template_idx % len(TEMPLATES)]
    text = tmpl.format(
        course=chosen_course,
        topic=topic,
        day=day,
        time=time,
        schedule=schedule,
        group=group,
        mode=mode,
        exam=exam
    )

    # Temukan koordinat karakter (start, end) untuk setiap entitas
    entities = []
    
    def find_span(substring, label):
        idx = text.find(substring)
        if idx != -1:
            entities.append({
                "start": idx,
                "end": idx + len(substring),
                "text": substring,
                "label": label
            })

    find_span(topic, "topic")
    find_span(chosen_course, "course")
    find_span(exam, "exam_prep")
    find_span(f"hari {day} {time}" if f"hari {day} {time}" in text else f"{day} {time}", "schedule")
    find_span(group, "group_size")
    find_span(mode, "study_mode")

    # Sort entitas berdasarkan indeks awal (start)
    entities.sort(key=lambda x: x["start"])

    # Format GLiNER (tokenized words + ner spans)
    return {
        "text": text,
        "ner": [[ent["start"], ent["end"], ent["label"]] for ent in entities],
        "spans": entities
    }

def build_dataset(num_train=300, num_val=60):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f">> Membuat {num_train} sampel dataset training...")
    train_data = [generate_sample() for _ in range(num_train)]
    
    print(f">> Membuat {num_val} sampel dataset validasi...")
    val_data = [generate_sample() for _ in range(num_val)]

    # Simpan dataset
    train_path = DATA_DIR / "train_data.json"
    val_path = DATA_DIR / "val_data.json"
    labels_path = DATA_DIR / "labels.json"

    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train_data, f, indent=2, ensure_ascii=False)

    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(val_data, f, indent=2, ensure_ascii=False)

    labels = ["course", "topic", "exam_prep", "schedule", "group_size", "study_mode"]
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump({"labels": labels, "total_train": num_train, "total_val": num_val}, f, indent=2)

    print(f">> [SUKSES] Dataset tersimpan di:")
    print(f"   - {train_path}")
    print(f"   - {val_path}")
    print(f"   - {labels_path}")

if __name__ == "__main__":
    build_dataset()

