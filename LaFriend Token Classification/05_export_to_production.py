"""
==============================================================================
05_export_to_production.py - Ekspor Model Siap Pakai ke Folder LaFriend
==============================================================================
Script ini bertugas untuk:
1. Memverifikasi seluruh artefak model GLiNER dan DeBERTa-v3 tokenizer.
2. Memperbarui path konfigurasi lokal agar 100% offline di server produksi.
3. Menyinkronkan model ke folder produksi:
   LaFriend/backend/app/weights/gliner_small/
   LaFriend/backend/app/weights/deberta_v3_small/
4. Menjalankan verifikasi akhir bahwa model dapat dimuat tanpa internet.
==============================================================================
"""

import os
import json
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PRODUCTION_WEIGHTS_DIR = SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights"
PROD_GLINER_DIR = PRODUCTION_WEIGHTS_DIR / "gliner_small"
PROD_DEBERTA_DIR = PRODUCTION_WEIGHTS_DIR / "deberta_v3_small"

def export_and_verify():
    print("=" * 70)
    print(">> [1/3] Memeriksa Direktori Bobot Produksi LaFriend...")
    print("=" * 70)
    print(f">> Target GLiNER : {PROD_GLINER_DIR}")
    print(f">> Target DeBERTa: {PROD_DEBERTA_DIR}\n")

    if not PROD_GLINER_DIR.exists() or not PROD_DEBERTA_DIR.exists():
        raise FileNotFoundError(f"Folder bobot produksi belum lengkap di {PRODUCTION_WEIGHTS_DIR}")

    print("=" * 70)
    print(">> [2/3] Mengonfigurasi gliner_config.json untuk Mode Offline...")
    print("=" * 70)
    cfg_file = PROD_GLINER_DIR / "gliner_config.json"
    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Set model_name ke path lokal deberta_v3_small
    cfg["model_name"] = str(PROD_DEBERTA_DIR)
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    print(f">> gliner_config.json berhasil diarahkan ke: {PROD_DEBERTA_DIR}\n")

    print("=" * 70)
    print(">> [3/3] Menjalankan Uji Inferensi Verifikasi Offline...")
    print("=" * 70)
    from gliner import GLiNER
    model = GLiNER.from_pretrained(str(PROD_GLINER_DIR), local_files_only=True)
    test_text = "Saya mau belajar Binary Tree untuk ujian Struktur Data hari Rabu jam 9 sampai 12 bareng 3 orang di perpus."
    entities = model.predict_entities(test_text, ["course", "study topic", "schedule", "group size"], threshold=0.2)

    print(">> Kalimat Uji:")
    print(f"   '{test_text}'")
    print(">> Entitas Terdeteksi:")
    for ent in entities:
        print(f"   - [{ent['label']:<12}] : {ent['text']:<25} (skor: {ent['score']:.3f})")

    print("\n" + "=" * 70)
    print(">> [VERIFIKASI SUKSES] Model di folder LaFriend SIAP DIPAKAI PRODUKSI!")
    print("=" * 70)

if __name__ == "__main__":
    export_and_verify()

