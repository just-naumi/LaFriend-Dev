"""
==============================================================================
01_download_weights.py - Download Model Pretrained & Tokenizer Weights
==============================================================================
Script ini bertugas untuk:
1. Mengunduh bobot (weights) model GLiNER (urchade/gliner_small-v2.1).
2. Mengunduh tokenizer dan base config microsoft/deberta-v3-small.
3. Menyimpan seluruh artefak mentah ke folder lokal ./raw_weights/
   sehingga proses training, evaluasi, dan deployment dapat dilakukan 100% offline.
==============================================================================
"""

import os
from pathlib import Path
from huggingface_hub import snapshot_download

# Tentukan direktori penyimpanan
SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DIR = SCRIPT_DIR / "raw_weights"
GLINER_RAW_DIR = RAW_DIR / "gliner_small_v2.1"
DEBERTA_RAW_DIR = RAW_DIR / "deberta_v3_small"

def download_models():
    print("=" * 70)
    print(">> [1/2] Mengunduh Bobot Model GLiNER small v2.1 dari HuggingFace...")
    print("=" * 70)
    GLINER_RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    snapshot_download(
        repo_id="urchade/gliner_small-v2.1",
        local_dir=str(GLINER_RAW_DIR),
        local_dir_use_symlinks=False
    )
    print(f">> Berhasil mengunduh GLiNER ke: {GLINER_RAW_DIR}\n")

    print("=" * 70)
    print(">> [2/2] Mengunduh Tokenizer & Config microsoft/deberta-v3-small...")
    print("=" * 70)
    DEBERTA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    snapshot_download(
        repo_id="microsoft/deberta-v3-small",
        local_dir=str(DEBERTA_RAW_DIR),
        local_dir_use_symlinks=False
    )
    print(f">> Berhasil mengunduh DeBERTa-v3-small ke: {DEBERTA_RAW_DIR}\n")

    print("=" * 70)
    print(">> SEMUA BOBOT MODEL BERHASIL DIUNDUH LENGKAP SECARA OFFLINE!")
    print("=" * 70)

if __name__ == "__main__":
    download_models()

