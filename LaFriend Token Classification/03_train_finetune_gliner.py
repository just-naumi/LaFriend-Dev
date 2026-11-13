"""
==============================================================================
03_train_finetune_gliner.py - Script Training & Fine-Tuning Model GLiNER
Domain: Kurikulum S1 Teknik Komputer Telkom University (Semester 1 s/d 8)
==============================================================================
Pembaruan Sesuai Feedback Revisi:
1. Training 2 Epoch Penuh (400 steps untuk 800 sampel, batch_size=4).
2. Evaluasi Validation Loss pada SELURUH 200 sampel dataset validasi setiap epoch.
3. Checkpoint Selection Nyata: Model hanya disimpan jika menghasilkan val_loss terendah (best_val_loss).
4. Taxonomy Label Konsisten: ['course', 'topic', 'learning_goal', 'schedule', 'group_size', 'study_mode'].
==============================================================================
"""

import os
import json
import time
import shutil
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


def clean_gliner_config(target_dir: Path):
    """Membersihkan bug class_token_index pada GLiNER config saat disimpan ulang."""
    cfg_path = target_dir / "gliner_config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "class_token_index" in cfg:
                del cfg["class_token_index"]
            cfg["model_name"] = str(SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights" / "deberta_v3_small")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            print(f"Warning saat merapikan gliner_config.json: {e}")


def run_training(epochs=3, batch_size=4, lr=1e-5):
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
    print(f">> Dataset Uji (Val)     : {len(val_data)} kalimat (Unseen Patterns)\n")

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

    steps_per_epoch = len(train_loader)
    total_steps = epochs * steps_per_epoch
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)

    print(f">> Optimizer       : AdamW (LR={lr}, Weight Decay=0.01)")
    print(f">> Batch Size      : {batch_size}")
    print(f">> Steps per Epoch : {steps_per_epoch} batch steps")
    print(f">> Total Epochs    : {epochs} ({total_steps} total steps)\n")

    print("=" * 75)
    print(">> [4/4] MEMULAI TRAINING LOOP DENGAN VALIDASI & BEST CHECKPOINTING...")
    print("=" * 75)
    
    global_step = 0
    best_val_loss = float("inf")
    start_time = time.time()
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        running_loss = 0.0
        
        print(f"\n--- [EPOCH {epoch}/{epochs}] ---")
        for batch_idx, batch in enumerate(train_loader, 1):
            global_step += 1
            batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
            
            optimizer.zero_grad()
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            epoch_loss += loss.item()
            running_loss += loss.item()

            if batch_idx % 25 == 0 or batch_idx == 1:
                avg_step_loss = running_loss / (25 if batch_idx > 1 else 1)
                elapsed = time.time() - start_time
                print(f"   [Epoch {epoch} | Step {batch_idx:03d}/{steps_per_epoch}] Step Loss: {loss.item():.4f} (Avg: {avg_step_loss:.4f}) | Waktu: {elapsed:.1f}s")
                running_loss = 0.0

        # Evaluasi Validasi Penuh pada Seluruh Val Data di akhir setiap epoch
        model.eval()
        val_loss_total = 0.0
        val_batches = 0
        with torch.no_grad():
            for vbatch in val_loader:
                vbatch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in vbatch.items()}
                vout = model(**vbatch)
                val_loss_total += vout.loss.item()
                val_batches += 1

        avg_val_loss = val_loss_total / max(val_batches, 1)
        avg_train_loss = epoch_loss / steps_per_epoch
        print(f"\n>> Selesai Epoch {epoch}: Train Loss = {avg_train_loss:.4f} | Validation Loss = {avg_val_loss:.4f}")

        # Mekanisme Simpan Model Terbaik
        if avg_val_loss < best_val_loss:
            print(f">> [CHECKPOINT] Validation loss membaik ({best_val_loss:.4f} -> {avg_val_loss:.4f})! Menyimpan model...")
            best_val_loss = avg_val_loss
            model.save_pretrained(str(CHECKPOINT_DIR))
            clean_gliner_config(CHECKPOINT_DIR)
            
            # Salin tokenizer config jika perlu
            for fname in ["config.json", "spm.model", "tokenizer_config.json"]:
                src = MODEL_DIR / fname
                if src.exists():
                    shutil.copy(src, CHECKPOINT_DIR / fname)
        else:
            print(f">> Validation loss ({avg_val_loss:.4f}) belum melampaui rekor terbaik ({best_val_loss:.4f}). Checkpoint dipertahankan.")

    print("\n" + "=" * 75)
    print(f">> [SUKSES] TRAINING SELESAI! Rekor Validation Loss Terbaik: {best_val_loss:.4f}")
    print(f">> Checkpoint Tersimpan di: {CHECKPOINT_DIR}")
    print("=" * 75)


if __name__ == "__main__":
    # 2 epoch untuk 800 data (400 steps) agar cepat dan optimal pada CPU/GPU
    run_training(epochs=2, batch_size=4, lr=1e-5)
