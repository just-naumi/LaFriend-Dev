# Laporan Evaluasi Ilmiah Model GLiNER Span-Level (LaFriend)

- **Waktu Evaluasi**: `2026-11-13 20:28:25`
- **Metode Evaluasi**: **Strict Exact Span Match** (Batas karakter & teks wajib tepat 100%)
- **Jumlah Sampel Uji**: 200 kalimat (*Unseen Sentence Patterns*)
- **Total Entitas Ground Truth**: 1053 entitas

### Tabel Metrik Per Kategori Entitas

| Entitas Target | Precision | Recall | F1-Score | Dukungan (*Support*) |
| :--- | :---: | :---: | :---: | :---: |
| `course` | 80.18% | 89.0% | **84.36%** | 200 entitas |
| `topic` | 93.97% | 93.5% | **93.73%** | 200 entitas |
| `learning_goal` | 68.83% | 88.33% | **77.37%** | 120 entitas |
| `schedule` | 100.0% | 100.0% | **100.0%** | 200 entitas |
| `group_size` | 94.48% | 94.48% | **94.48%** | 145 entitas |
| `study_mode` | 94.92% | 99.47% | **97.14%** | 188 entitas |
| **Macro Average** | — | — | **91.18%** | 1053 total |
| **Micro Average** | 89.08% | 94.49% | **91.71%** | 1053 total |

> **Catatan Metodologis**: Seluruh data validasi dihasilkan dari 20 struktur kalimat yang sama sekali berbeda dari dataset training untuk memastikan model benar-benar mampu melakukan generalisasi terhadap variasi percakapan mahasiswa.
