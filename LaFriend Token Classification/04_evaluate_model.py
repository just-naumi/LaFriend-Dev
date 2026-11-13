"""
==============================================================================
04_evaluate_model.py - Script Evaluasi & Benchmark Model GLiNER Span-Level
==============================================================================
Script ini bertugas untuk:
1. Memuat model GLiNER yang telah di-fine-tune.
2. Menguji model terhadap data validasi di ./data/val_data.json (Unseen patterns).
3. Menghitung metrik performa nyata per entitas:
   - Precision (Ketepatan deteksi span)
   - Recall    (Kelengkapan span yang tertangkap)
   - F1-Score  (Harmonic mean Precision & Recall)
   - Support   (Jumlah entitas aktual dalam data validasi)
4. Menghitung Macro-F1 dan Micro-F1 secara menyeluruh.
==============================================================================
"""

import json
from pathlib import Path
from collections import defaultdict
from gliner import GLiNER

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoints" / "best_gliner_telkom"
PRODUCTION_DIR = SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights" / "gliner_small"


def evaluate():
    print("=" * 75)
    print(">> [1/3] MEMUAT DATASET VALIDASI & MODEL...")
    print("=" * 75)

    val_path = DATA_DIR / "val_data.json"
    with open(val_path, "r", encoding="utf-8") as f:
        val_samples = json.load(f)

    with open(DATA_DIR / "labels.json", "r", encoding="utf-8") as f:
        labels = json.load(f)["labels"]

    # Gunakan checkpoint jika ada, jika belum ada pakai production
    load_dir = CHECKPOINT_DIR if CHECKPOINT_DIR.exists() else PRODUCTION_DIR
    model = GLiNER.from_pretrained(str(load_dir), local_files_only=True)
    print(f">> Model berhasil dimuat dari: {load_dir}")
    print(f">> Total sampel validasi: {len(val_samples)} kalimat")
    print(f">> Target entitas: {labels}\n")

    print("=" * 75)
    print(">> [2/3] MENJALANKAN INFERENSI EVALUASI PADA 200 SAMPEL VALIDASI...")
    print("=" * 75)

    tp = defaultdict(int)  # True Positives
    fp = defaultdict(int)  # False Positives
    fn = defaultdict(int)  # False Negatives

    # Evaluasi pada threshold 0.20
    for sample in val_samples:
        text = sample["text"]
        gt_spans = sample.get("spans", [])

        # Model predict
        preds = model.predict_entities(text, labels, threshold=0.20)

        matched_gt = set()
        for p in preds:
            p_label = p["label"]
            p_text = p["text"].strip().lower()
            
            found_match = False
            for idx, gt in enumerate(gt_spans):
                if idx in matched_gt:
                    continue
                gt_label = gt["label"]
                gt_text = gt["text"].strip().lower()

                # Cek overlap substring atau match label
                if p_label == gt_label and (p_text in gt_text or gt_text in p_text):
                    tp[p_label] += 1
                    matched_gt.add(idx)
                    found_match = True
                    break

            if not found_match:
                fp[p_label] += 1

        # Sisa ground truth yang tidak terprediksi adalah False Negative
        for idx, gt in enumerate(gt_spans):
            if idx not in matched_gt:
                fn[gt["label"]] += 1

    print("=" * 75)
    print(">> [3/3] LAPORAN HASIL EVALUASI SPAN-LEVEL GLINER:")
    print("=" * 75)
    header = f"{'Entitas Target':<18} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Dukungan (Support)'}"
    print(header)
    print("-" * 75)

    total_tp = 0
    total_fp = 0
    total_fn = 0
    f1_list = []

    for lbl in labels:
        p_tp = tp[lbl]
        p_fp = fp[lbl]
        p_fn = fn[lbl]
        support = p_tp + p_fn

        total_tp += p_tp
        total_fp += p_fp
        total_fn += p_fn

        prec = p_tp / (p_tp + p_fp) if (p_tp + p_fp) > 0 else 0.0
        rec = p_tp / (p_tp + p_fn) if (p_tp + p_fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_list.append(f1)

        print(f"{lbl:<18} | {prec*100:>8.2f}% | {rec*100:>8.2f}% | {f1*100:>8.2f}% | {support:>6} entitas")

    print("-" * 75)
    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0
    micro_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_prec * micro_rec) / (micro_prec + micro_rec) if (micro_prec + micro_rec) > 0 else 0.0

    print(f"{'Macro Average':<18} | {'-':<10} | {'-':<10} | {macro_f1*100:>8.2f}% | {total_tp + total_fn:>6} total")
    print(f"{'Micro Average':<18} | {micro_prec*100:>8.2f}% | {micro_rec*100:>8.2f}% | {micro_f1*100:>8.2f}% | {total_tp + total_fn:>6} total")
    print("=" * 75)


if __name__ == "__main__":
    evaluate()
