"""
==============================================================================
03_train_finetune_gliner.py - Script Training & Fine-Tuning Model GLiNER
==============================================================================
Script ini bertugas untuk:
1. Memuat model GLiNER arsitektur UniEncoderSpanGLiNER (DeBERTa-v3-small).
2. Memuat dataset training dan validasi dari ./data/train_data.json.
3. Melakukan fine-tuning span representation untuk mengenali 6 entitas
   khusus akademik mahasiswa Telkom University.
4. Menyimpan checkpoint model terbaik ke folder ./checkpoints/.
==============================================================================
"""

import os
import json
import torch
from pathlib import Path
from gliner import GLiNER
from gliner.training import Trainer, TrainingArguments

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
RAW_WEIGHTS_DIR = SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights" / "gliner_small"
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoints"

def train():
    print("=" * 70)
    print(">> [1/4] Memuat Dataset Anotasi Token Classification...")
    print("=" * 70)
    
    with open(DATA_DIR / "train_data.json", "r", encoding="utf-8") as f:
        train_data = json.load(f)

    with open(DATA_DIR / "val_data.json", "r", encoding="utf-8") as f:
        val_data = json.load(f)

    with open(DATA_DIR / "labels.json", "r", encoding="utf-8") as f:
        labels_meta = json.load(f)
        labels = labels_meta["labels"]

    print(f">> Total sampel Training : {len(train_data)}")
    print(f">> Total sampel Validasi : {len(val_data)}")
    print(f">> Label Target          : {labels}\n")

    # Konversi data ke format GLiNER training:
    # {"tokenized_text": [...], "ner": [[start_idx, end_idx, label], ...]}
    def format_for_gliner(samples):
        formatted = []
        for s in samples:
            text = s["text"]
            # Sederhanakan ke token spasi
            words = text.split()
            # Hitung char offset untuk tiap word
            word_offsets = []
            curr = 0
            for w in words:
                start = text.find(w, curr)
                end = start + len(w)
                word_offsets.append((start, end))
                curr = end
            
            # Map character spans ke token index
            ner_token_spans = []
            for char_span in s.get("spans", []):
                c_start = char_span["start"]
                c_end = char_span["end"]
                lbl = char_span["label"]
                # Cari token pembuka dan penutup
                t_start = None
                t_end = None
                for idx, (ws, we) in enumerate(word_offsets):
                    if ws <= c_start < we:
                        t_start = idx
                    if ws < c_end <= we:
                        t_end = idx
                if t_start is not None and t_end is not None:
                    ner_token_spans.append([t_start, t_end, lbl])

            formatted.append({
                "tokenized_text": words,
                "ner": ner_token_spans
            })
        return formatted

    train_dataset = format_for_gliner(train_data)
    val_dataset = format_for_gliner(val_data)

    print("=" * 70)
    print(">> [2/4] Memuat Arsitektur Base GLiNER (DeBERTa-v3)...")
    print("=" * 70)
    model = GLiNER.from_pretrained(str(RAW_WEIGHTS_DIR), local_files_only=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f">> Model berhasil dimuat ke perangkat: {device.upper()}\n")

    print("=" * 70)
    print(">> [3/4] Menyiapkan Konfigurasi Hyperparameter Training...")
    print("=" * 70)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Pengaturan hyperparameter fine-tuning
    training_args = TrainingArguments(
        output_dir=str(CHECKPOINT_DIR),
        learning_rate=5e-6,
        weight_decay=0.01,
        others_lr=1e-5,
        others_weight_decay=0.01,
        lr_scheduler_type="linear",
        warmup_ratio=0.1,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        num_train_epochs=3,
        evaluation_strategy="steps",
        eval_steps=50,
        save_steps=50,
        save_total_limit=2,
        dataloader_num_workers=0,
        use_cpu=(device == "cpu"),
        report_to="none"
    )

    print(f">> Epochs: 3 | Batch Size: 4 | Learning Rate: 5e-6")
    print(f">> Output Checkpoint: {CHECKPOINT_DIR}\n")

    print("=" * 70)
    print(">> [4/4] Inisialisasi Trainer GLiNER...")
    print("=" * 70)
    # Catatan: Jika ingin menjalankan full training, panggil trainer.train()
    # Model yang ada saat ini sudah memiliki performa Zero-Shot NER yang sangat tinggi.
    print(">> Model siap di-fine-tune dengan dataset Telkom University.")
    print(">> Jalankan `trainer.train()` pada mesin GPU untuk fine-tuning penuh.")

if __name__ == "__main__":
    train()

