"""
==============================================================================
sample_inference_test.py - Pengujian Interaktif Raw Model Token Classification
==============================================================================
Gunakan script ini untuk menguji bagaimana model GLiNER membedah kalimat mentah
bahasa Indonesia menjadi entitas spesifik (Course, Topic, Schedule, Group, Mode).
==============================================================================
"""

import sys
from pathlib import Path
from gliner import GLiNER

SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR = SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights" / "gliner_small"

def run_sample_tests():
    print(">> Memuat model GLiNER...")
    model = GLiNER.from_pretrained(str(MODEL_DIR), local_files_only=True)
    print(">> Model siap!\n")

    test_cases = [
        "Saya mau belajar Binary Tree dan AVL Tree buat persiapan UAS Struktur Data hari Rabu jam 9 sampai 12 bareng 2 sampai 4 orang di perpus",
        "Diskusi santai materi Normalisasi 1NF sampai 3NF Basis Data kelompok 3 orang tatap muka Kamis 13:00-15:00",
        "Latihan soal Turunan dan Integral persiapan kuis Kalkulus online hari Jumat jam 10",
        "Ada yang mau ngoding bareng Subnetting IPv4 Jaringan Komputer? Yuk kumpul di TULT hari Selasa pukul 14:00 bareng 3 orang",
        "Butuh partner belajar Teori Graf Matematika Diskrit hari Sabtu jam 8 pagi sampai 11"
    ]

    labels = ["course", "study topic", "exam preparation", "schedule", "group size", "study mode"]

    for idx, text in enumerate(test_cases, 1):
        print("=" * 75)
        print(f"CONTOH #{idx}:")
        print(f"Teks: \"{text}\"")
        print("-" * 75)
        entities = model.predict_entities(text, labels, threshold=0.20)
        if entities:
            for ent in entities:
                print(f"  [{ent['label']:<16}] : \"{ent['text']}\" (skor: {ent['score']:.3f}, span: {ent['start']}-{ent['end']})")
        else:
            print("  (Tidak ada entitas yang melampaui batas threshold)")
        print()

if __name__ == "__main__":
    run_sample_tests()

