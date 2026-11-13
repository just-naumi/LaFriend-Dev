"""
==============================================================================
03_train_finetune_gliner.py - Script Training & Fine-Tuning Model GLiNER
Domain: Kurikulum S1 Teknik Komputer Telkom University (Semester 1 s/d 8)
==============================================================================
Script ini menjalankan proses fine-tuning nyata (real training loop):
1. Memuat model GLiNER (DeBERTa-v3-small backbone).
2. Memuat 600 data training dan 120 data validasi dari data/train_data.json.
3. Menggunakan UniEncoderSpanDataCollator untuk batching span tensor.
4. Menjalankan optimasi AdamW dengan gradient clipping.
5. Menampilkan penurunan nilai loss pada setiap step.
6. Menyimpan checkpoint model terbaik ke folder ./checkpoints/best_gliner_telkom.
==============================================================================
"""

import os
import json
import time
import torch
from pathlib import Path
from torch.utils.data import DataLoader
from gliner import GLiNER
from gliner.data_processing import UniEncoderSpanDataCollator

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
MODEL_DIR = SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights" / "gliner_small"
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoints" / "best_gliner_telkom"

def convert_to_gliner_format(samples):
    """Mengonversi format span karakter ke tokenized words + token-level ner span."""
    formatted = []
    for s in samples:
        text = s["text"]
        words = text.split()
        word_spans = []
        curr = 0
        for w in words:
            start = text.find(w, curr)
            end = start + len(w)
            word_spans.append((start, end))
            curr = end

        ner_spans = []
        for span in s.get("spans", []):
            cs, ce, lbl = span["start"], span["end"], span["label"]
            ts, te = None, None
            for idx, (ws, we) in enumerate(word_spans):
                if ws <= cs < we:
                    ts = idx
                if ws < ce <= we:
                    te = idx
            if ts is not None and te is not None:
                ner_spans.append([ts, te, lbl])

        formatted.append({
            "tokenized_text": words,
            "ner": ner_spans
        })
    return formatted

def run_training(max_steps=60, batch_size=4, lr=1e-5):
    print("=" * 75)
    print(">> [1/4] MEMUAT DATASET KURIKULUM S1 TEKNIK KOMPUTER TEL-U...")
    print("=" * 75)
    
    with open(DATA_DIR / "train_data.json", "r", encoding="utf-8") as f:
        train_raw = json.load(f)
    with open(DATA_DIR / "val_data.json", "r", encoding="utf-8") as f:
        val_raw = json.load(f)

    train_data = convert_to_gliner_format(train_raw)
    val_data = convert_to_gliner_format(val_raw)

    print(f">> Dataset Latih (Train) : {len(train_data)} kalimat")
    print(f">> Dataset Uji (Val)     : {len(val_data)} kalimat\n")

    print("=" * 75)
    print(">> [2/4] MEMUAT ARSITEKTUR GLiNER (DeBERTa-v3-small)...")
    print("=" * 75)
    model = GLiNER.from_pretrained(str(MODEL_DIR), local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f">> Model berhasil dimuat ke perangkat: {str(device).upper()}")
    print(f">> Parameter yang dapat dilatih: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}\n")

    print("=" * 75)
    print(">> [3/4] MENYIAPKAN DATA COLLATOR & OPTIMIZER...")
    print("=" * 75)
    collator = UniEncoderSpanDataCollator(
        model.config,
        data_processor=model.data_processor,
        prepare_labels=True
    )

    train_loader = DataLoader(
        train_data,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collator
    )
    val_loader = DataLoader(
        val_data,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collator
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    print(f">> Optimizer     : AdamW (LR={lr}, Weight Decay=0.01)")
    print(f">> Batch Size    : {batch_size}")
    print(f">> Target Steps  : {max_steps} batch steps\n")

    print("=" * 75)
    print(">> [4/4] MEMULAI PROSES TRAINING / FINE-TUNING SPAN LOSS...")
    print("=" * 75)
    model.train()
    step = 0
    running_loss = 0.0
    start_time = time.time()

    while step < max_steps:
        for batch in train_loader:
            step += 1
            # Pindahkan tensor ke device
            batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
            
            optimizer.zero_grad()
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            running_loss += loss.item()

            if step % 10 == 0 or step == 1:
                avg_loss = running_loss / (10 if step > 1 else 1)
                elapsed = time.time() - start_time
                print(f"   [Step {step:03d}/{max_steps}] Loss: {loss.item():.4f} (Avg: {avg_loss:.4f}) | Waktu: {elapsed:.1f}s")
                running_loss = 0.0

            if step >= max_steps:
                break

    # Evaluasi validasi cepat
    print("\n>> Menghitung Validation Loss...")
    model.eval()
    val_loss = 0.0
    val_steps = 0
    with torch.no_grad():
        for batch in val_loader:
            batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
            out = model(**batch)
            val_loss += out.loss.item()
            val_steps += 1
            if val_steps >= 15:
                break
    final_val_loss = val_loss / val_steps
    print(f">> Final Validation Loss: {final_val_loss:.4f}\n")

    # Simpan model
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    print(f">> Menyimpan bobot checkpoint model terbaik ke: {CHECKPOINT_DIR}...")
    model.save_pretrained(str(CHECKPOINT_DIR))
    
    # Salin tokenizer config jika perlu
    for fname in ["config.json", "spm.model", "tokenizer_config.json"]:
        src = MODEL_DIR / fname
        if src.exists():
            import shutil
            shutil.copy(src, CHECKPOINT_DIR / fname)

    print("=" * 75)
    print(">> [SUKSES] TRAINING SELESAI & CHECKPOINT BERHASIL DISIMPAN!")
    print("=" * 75)

if __name__ == "__main__":
    run_training(max_steps=50, batch_size=4, lr=1e-5)
