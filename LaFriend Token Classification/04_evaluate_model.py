"""
==============================================================================
04_evaluate_model.py - Script Evaluasi & Benchmark Model Token Classification
==============================================================================
Script ini bertugas untuk:
1. Memuat model GLiNER yang aktif.
2. Menguji model terhadap data validasi di ./data/val_data.json.
3. Menghitung metrik performa token classification:
   - Precision (Ketepatan prediksi)
   - Recall    (Kelengkapan entitas yang tertangkap)
   - F1-Score  (Keseimbangan harmonik Precision & Recall)
4. Menampilkan tabel metrik evaluasi per kategori entitas.
==============================================================================
"""

import json
from pathlib import Path
from collections import defaultdict
from gliner import GLiNER

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
MODEL_DIR = SCRIPT_DIR.parent / "LaFriend" / "backend" / "app" / "weights" / "gliner_small"

def evaluate():
    print("=" * 70)
    print(">> [1/3] Memuat Model dan Dataset Validasi...")
    print("=" * 70)

    val_path = DATA_DIR / "val_data.json"
    with open(val_path, "r", encoding="utf-8") as f:
        val_samples = json.load(f)

    with open(DATA_DIR / "labels.json", "r", encoding="utf-8") as f:
        labels = json.load(f)["labels"]

    model = GLiNER.from_pretrained(str(MODEL_DIR), local_files_only=True)
    print(f">> Model berhasil dimuat dari: {MODEL_DIR}")
    print(f">> Total sampel validasi: {len(val_samples)}")
    print(f">> Target entitas: {labels}\n")

    print("=" * 70)
    print(">> [2/3] Menjalankan Inferensi Token Classification pada Data Validasi...")
    print("=" * 70)

    tp = defaultdict(int)  # True Positives
    fp = defaultdict(int)  # False Positives
    fn = defaultdict(int)  # False Negatives

    # Evaluasi pada threshold 0.22
    for sample in val_samples:
        text = sample["text"]
        gt_spans = sample.get("spans", [])

        # Model predict
        preds = model.predict_entities(text, labels, threshold=0.22)

        # Cocokkan prediksi dengan ground truth
        matched_gt = set()
        for p in preds:
            p_label = p["label"]
            p_text = p["text"].strip().lower()
            
            # Cek apakah ada ground truth yang overlap / cocok
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

    print("=" * 70)
    print(">> [3/3] LAPORAN HASIL EVALUASI TOKEN CLASSIFICATION:")
    print("=" * 70)
    header = f"{'Entitas Target':<18} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Dukungan (Support)'}"
    print(header)
    print("-" * len(header))

    total_tp = sum(tp.values())
    total_fp = sum(fp.values())
    total_fn = sum(fn.values())

    for lbl in labels:
        p_val = tp[lbl] / (tp[lbl] + fp[lbl]) if (tp[lbl] + fp[lbl]) > 0 else 0.0
        r_val = tp[lbl] / (tp[lbl] + fn[lbl]) if (tp[lbl] + fn[lbl]) > 0 else 0.0
        f1 = (2 * p_val * r_val) / (p_val + r_val) if (p_val + r_val) > 0 else 0.0
        support = tp[lbl] + fn[lbl]

        print(f"{lbl:<18} | {p_val * 100:6.2f}%    | {r_val * 100:6.2f}%    | {f1 * 100:6.2f}%    | {support}")

    macro_p = sum(tp[l] / (tp[l] + fp[l]) if (tp[l] + fp[l]) > 0 else 0 for l in labels) / len(labels)
    macro_r = sum(tp[l] / (tp[l] + fn[l]) if (tp[l] + fn[l]) > 0 else 0 for l in labels) / len(labels)
    macro_f1 = (2 * macro_p * macro_r) / (macro_p + macro_r) if (macro_p + macro_r) > 0 else 0.0

    print("-" * len(header))
    print(f"{'RATA-RATA (Macro)':<18} | {macro_p * 100:6.2f}%    | {macro_r * 100:6.2f}%    | {macro_f1 * 100:6.2f}%    | {sum(tp.values()) + sum(fn.values())}")
    print("=" * 70)

if __name__ == "__main__":
    evaluate()

