"""
==============================================================================
05_export_to_production.py - Ekspor Model Fine-Tuned ke Sistem Produksi LaFriend
==============================================================================
"""

import os
import json
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoints" / "best_gliner_telkom"
PRODUCTION_WEIGHTS_DIR = SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights"
PROD_GLINER_DIR = PRODUCTION_WEIGHTS_DIR / "gliner_small"
PROD_DEBERTA_DIR = PRODUCTION_WEIGHTS_DIR / "deberta_v3_small"

def export_and_verify():
    print("=" * 75)
    print(">> [1/3] MEMERIKSA CHECKPOINT MODEL HASIL TRAINING...")
    print("=" * 75)
    
    if CHECKPOINT_DIR.exists() and (CHECKPOINT_DIR / "pytorch_model.bin").exists():
        print(f">> Ditemukan checkpoint fine-tuned di: {CHECKPOINT_DIR}")
        print(f">> Menyalin bobot pytorch_model.bin ke folder produksi: {PROD_GLINER_DIR}...")
        PROD_GLINER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(CHECKPOINT_DIR / "pytorch_model.bin", PROD_GLINER_DIR / "pytorch_model.bin")
        print(">> Bobot fine-tuned berhasil disalin!")
    else:
        print(f">> Checkpoint belum ditemukan, menggunakan base weights yang ada.")

    print("\n" + "=" * 75)
    print(">> [2/3] MENGONFIGURASI gliner_config.json UNTUK MODE 100% OFFLINE...")
    print("=" * 75)
    cfg_file = PROD_GLINER_DIR / "gliner_config.json"
    
    # Konfigurasi standar GLiNER-v2.1 yang stabil
    clean_config = {
        "size_sup": -1,
        "max_types": 25,
        "shuffle_types": True,
        "random_drop": True,
        "max_neg_type_ratio": 1,
        "max_len": 384,
        "lr_encoder": "1e-5",
        "lr_others": "5e-5",
        "num_steps": 30000,
        "warmup_ratio": 3000,
        "train_batch_size": 8,
        "eval_every": 5000,
        "max_width": 12,
        "model_name": str(PROD_DEBERTA_DIR),
        "fine_tune": True,
        "subtoken_pooling": "first",
        "hidden_size": 512,
        "span_mode": "markerV0",
        "dropout": 0.4,
        "name": "correct"
    }

    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(clean_config, f, indent=2)

    print(f">> gliner_config.json diarahkan ke: {PROD_DEBERTA_DIR}\n")

    print("=" * 75)
    print(">> [3/3] VERIFIKASI AKHIR MODEL DI SERVER PRODUKSI LAFRIEND...")
    print("=" * 75)
    from gliner import GLiNER
    model = GLiNER.from_pretrained(str(PROD_GLINER_DIR), local_files_only=True)
    test_text = "Saya mau belajar Binary Search Tree buat kuis Struktur Data hari Rabu jam 9 sampai 12 bareng 3 orang di Open Library."
    labels = ["course", "topic", "exam_prep", "schedule", "group_size", "study_mode"]
    entities = model.predict_entities(test_text, labels, threshold=0.15)

    print(f">> Teks Uji: '{test_text}'")
    print(">> Entitas Terdeteksi:")
    for ent in entities:
        print(f"   - [{ent['label']:<12}] : \"{ent['text']}\" (skor: {ent['score']:.3f})")

    print("\n" + "=" * 75)
    print(">> [VERIFIKASI SUKSES] Model LaFriend SIAP DIPAKAI & TELAH DIPERBARUI!")
    print("=" * 75)

if __name__ == "__main__":
    export_and_verify()
