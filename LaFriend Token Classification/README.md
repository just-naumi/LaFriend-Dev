# 🧠 LaFriend Token Classification (AI Model Development Toolkit)

Folder ini dikhususkan sebagai **ruang kerja riset & pengembangan model AI (AI Lab)** untuk fitur **AI Study Intent Assistant** pada platform **LaFriend** (Telkom University).

Dengan pemisahan ini:
- **`LaFriend Token Classification/`**: Berisi seluruh *raw code*, dataset generator, pipeline training/fine-tuning, benchmarking evaluasi, dan script ekspor model.
- **`LaFriend/` (Aplikasi Utama)**: Tetap bersih dan hanya berisi bobot model yang sudah siap pakai (`backend/app/weights/`) serta kode logika aplikasi operasional (`extraction.py`, `routes.py`, database, dan frontend).

---

## 🏗️ 1. Teori & Arsitektur: Bagaimana AI Memahami Teks?

Untuk mengubah curhatan belajar bahasa Indonesia:
> *"Saya mau belajar Binary Tree dan AVL Tree buat persiapan UAS Struktur Data hari Rabu jam 9 sampai 12 bareng 2 sampai 4 orang di perpus"*

Menjadi parameter sistem terstruktur:
- **Course**: `Struktur Data` (ID: `cb22b2fe-...`)
- **Topics**: `Binary Tree dan AVL Tree`
- **Goal**: `EXAM_PREP` (UAS)
- **Schedule**: `Rabu (09:00 - 12:00)`
- **Group Size**: `Min: 2, Max: 4`
- **Mode**: `OFFLINE`

### Mengapa Menggunakan GLiNER (Generalist and Lightweight Named Entity Recognition)?
1. **Span-Level vs BIO Tagging Tradisional**:  
   Model NER klasik (seperti BERT-base token classification) menggunakan skema `B-TAG`, `I-TAG`, `O` pada tingkat subtoken. Skema ini sering rapuh pada frasa panjang dan kata serapan bahasa Indonesia. GLiNER merepresentasikan setiap pasangan `(start_token, end_token)` sebagai *span embedding*, lalu menghitung kesamaan semantik (*dot-product similarity*) dengan representasi label.
2. **Zero-Shot & Open-Vocabulary**:  
   GLiNER dilatih secara *bidirectional span-matching*, sehingga dapat mendeteksi label baru seperti `study topic`, `exam preparation`, dan `group size` tanpa harus melatih ulang seluruh jaringan transformer dari nol.
3. **Ringan & Hemat Resource**:  
   Menggunakan *backbone* `microsoft/deberta-v3-small` (~140M parameter), model dapat berjalan cepat di CPU laptop mahasiswa dengan memori < 1GB RAM.

---

## 📁 2. Struktur File dalam Toolkit Ini

```text
LaFriend Token Classification/
├── 01_download_weights.py       # Unduh bobot mentah GLiNER & DeBERTa dari Hugging Face
├── 02_dataset_generator.py      # Generator dataset anotasi entitas Telkom University
├── 03_train_finetune_gliner.py  # Script training & fine-tuning Span GLiNER
├── 04_evaluate_model.py         # Evaluasi metrik Precision, Recall, dan F1-Score
├── 05_export_to_production.py   # Sinkronisasi & verifikasi model ke LaFriend/backend
├── sample_inference_test.py     # Script uji inferensi raw di terminal
├── data/                        # Dataset JSON (train_data.json, val_data.json, labels.json)
└── README.md                    # Dokumentasi teknis & panduan penggunaan
```

---

## 🚀 3. Panduan Menjalankan Script (Tahap demi Tahap)

### Langkah 1: Mengunduh Bobot Model Mentah (Offline Setup)
Jalankan script untuk mengunduh bobot `urchade/gliner_small-v2.1` dan tokenizer `microsoft/deberta-v3-small`:
```bash
py "LaFriend Token Classification/01_download_weights.py"
```

### Langkah 2: Menyiapkan Dataset Anotasi Akademik
Jalankan generator dataset untuk menyusun 300 sampel data training dan 60 data validasi dengan 6 entitas target (`course`, `topic`, `exam_prep`, `schedule`, `group_size`, `study_mode`):
```bash
py "LaFriend Token Classification/02_dataset_generator.py"
```
*Hasil akan tersimpan otomatis di folder `data/`.*

### Langkah 3: Menjalankan Training / Fine-Tuning
Jika ingin melakukan fine-tuning tambahan pada model menggunakan dataset di atas:
```bash
py "LaFriend Token Classification/03_train_finetune_gliner.py"
```

### Langkah 4: Evaluasi & Benchmark Model
Uji performa akurasi model terhadap data validasi untuk melihat tabel Precision, Recall, dan F1-Score per kategori:
```bash
py "LaFriend Token Classification/04_evaluate_model.py"
```

### Langkah 5: Ekspor Model ke Folder Produksi LaFriend
Sinkronkan konfigurasi dan bobot model langsung ke folder aplikasi `LaFriend/backend/app/weights/` agar aplikasi web siap dijalankan secara 100% offline:
```bash
py "LaFriend Token Classification/05_export_to_production.py"
```

### Langkah 6: Uji Coba Inferensi Bebas di Terminal
Untuk melihat bagaimana model membedah kalimat teks bebas secara langsung:
```bash
py "LaFriend Token Classification/sample_inference_test.py"
```

---

## 🔗 4. Integrasi ke Sistem Utama LaFriend

Setelah model diekspor ke folder `LaFriend/backend/app/weights/`:
1. File **`LaFriend/backend/app/extraction.py`** memuat model secara lokal via singleton:
   ```python
   model = GLiNER.from_pretrained(weights_dir, local_files_only=True)
   ```
2. Fungsi `process_chat_for_study_intent(raw_text, db)` menerima pesan dari endpoint `/api/v1/study-intents/extract-ai`, mengekstrak entitas neural, lalu memetakan hasilnya ke katalog mata kuliah resmi di SQLite `database/lafriend.db`.
3. Frontend **`create-intent.html`** otomatis mengisi form dan memberikan indikator visual **Diisi AI ✨** kepada mahasiswa.

