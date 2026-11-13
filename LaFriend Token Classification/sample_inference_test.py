"""
==============================================================================
sample_inference_test.py - Pengujian Model Fine-Tuned Telkom University
==============================================================================
"""

import sys
from pathlib import Path
from gliner import GLiNER

SCRIPT_DIR = Path(__file__).resolve().parent
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoints" / "best_gliner_telkom"
FALLBACK_DIR = SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights" / "gliner_small"

MODEL_PATH = CHECKPOINT_DIR if CHECKPOINT_DIR.exists() else FALLBACK_DIR

def run_sample_tests():
    print(f">> Memuat model dari: {MODEL_PATH}")
    model = GLiNER.from_pretrained(str(MODEL_PATH), local_files_only=True)
    print(">> Model siap!\n")

    test_cases = [
        "Saya mau belajar Binary Search Tree dan AVL Tree buat kuis Struktur Data hari Rabu jam 9 sampai 12 bareng 2 sampai 4 orang di Open Library",
        "Nyicil pengerjaan tubes perancangan VHDL Sistem Digital di TULT lantai 5 bareng 3 orang",
        "Diskusi materi Task Management FreeRTOS Sistem Tertanam dan IoT hari Kamis pukul 13:00 - 15:00 kelompok 3 orang",
        "Latihan soal Turunan Aturan Rantai persiapan UTS Kalkulus 1 online via Google Meet bareng berdua",
        "Bahas tuntas Subnetting IPv4 dan VLSM matkul Jaringan Komputer hari Jumat jam 14:00 s/d 16:30 di kosan Sukabirus"
    ]

    labels = ["course", "topic", "learning_goal", "schedule", "group_size", "study_mode"]

    for idx, text in enumerate(test_cases, 1):
        print("=" * 75)
        print(f"CONTOH #{idx}:")
        print(f"Teks: \"{text}\"")
        print("-" * 75)
        entities = model.predict_entities(text, labels, threshold=0.15)
        if entities:
            for ent in entities:
                print(f"  [{ent['label']:<12}] : \"{ent['text']}\" (skor: {ent['score']:.3f}, span: {ent['start']}-{ent['end']})")
        else:
            print("  (Tidak ada entitas yang melampaui batas threshold)")
        print()

if __name__ == "__main__":
    run_sample_tests()
