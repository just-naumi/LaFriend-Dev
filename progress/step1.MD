# STEP 1: Fondasi LaFriend & Manajemen Study Intent (Struktur Sederhana)

Dokumen ini menjelaskan implementasi resmi **Tahap 1 (Step 1)** yang telah disederhanakan agar mudah dipelajari oleh mahasiswa, tidak rumit, dan setiap baris kodenya memiliki komentar penjelasan bahasa Indonesia yang jelas.

---

## 1. Struktur Proyek Sederhana & Bersih
Seluruh folder modular lama yang rumit (`models/`, `schemas/`, `routers/`, `services/`, `api/`, `core/`, `db/`) telah **dihapus dan disatukan** ke dalam 5 file utama yang jelas tanggung jawabnya:

```text
LaFriend/
│
├── backend/
│   ├── app/
│   │   ├── main.py          # Server FastAPI, seeder otomatis, dan penyaji frontend
│   │   ├── database.py      # Konfigurasi SQLite (database/lafriend.db)
│   │   ├── models.py        # 4 Tabel: Student, Course, StudyIntent, IntentAvailability
│   │   ├── schemas.py       # Validasi Pydantic request/response
│   │   └── routes.py        # Seluruh endpoint API (Auth, Courses, Study Intent)
│   └── test_step1.py        # Pengujian otomatis backend & database
│
├── frontend/
│   ├── index.html           # Halaman Onboarding / Splash Screen visual sesuai desain referensi
│   ├── login.html           # Halaman login mahasiswa (gaya purple modern)
│   ├── register.html        # Halaman pendaftaran mahasiswa baru
│   ├── dashboard.html       # Dashboard utama (Daftar Study Intent & Katalog MK)
│   ├── create-intent.html   # Form pembuatan Study Intent didukung AI (One-Shot NLP)
│   │
│   ├── css/
│   │   └── style.css        # Desain ungu modern, rounded, dan responsif
│   │
│   ├── js/
│   │   └── app.js           # Satu file JavaScript untuk seluruh alur interaksi frontend
│   │
│   └── img/
│       └── study-illustration.png # Ilustrasi 3D mahasiswa belajar bersama
│
├── database/
│   └── lafriend.db          # Database SQLite aktif dengan Foreign Key
│
├── .gitignore
├── README.md
└── requirements.txt         # Daftar dependensi di root proyek
```

---

## 2. Tanggung Jawab Masing-Masing File

| File | Tanggung Jawab |
|---|---|
| `backend/app/database.py` | Mengatur path `database/lafriend.db`, membuat engine SQLAlchemy, dan mengaktifkan `PRAGMA foreign_keys = ON;`. |
| `backend/app/models.py` | Mendefinisikan 4 tabel: `students`, `courses`, `study_intents`, dan `intent_availabilities` dengan relasi cascade delete. |
| `backend/app/schemas.py` | Memvalidasi data yang dikirim pengguna agar sesuai tipe data (format email, minimal password, minimal 1 slot waktu, dan skema request/response chat AI). |
| `backend/app/routes.py` | Seluruh endpoint API dirangkum di sini (Register, Login, /me, Katalog MK, Buat Intent, List Intent, Batalkan Intent, serta Endpoint Ekstraksi AI). Disertai fungsi hashing password SHA-256 dan token JWT. |
| `backend/app/extraction.py` | Pipeline NLP One-Shot AI untuk memproses pesan teks bebas mahasiswa, mengekstrak entitas penting (Mata kuliah, topik, tujuan, gaya, mode, waktu, grup), dan mengembalikannya ke frontend. |
| `backend/app/main.py` | Titik awal aplikasi FastAPI, menjalankan seeder data awal otomatis (7 mata kuliah dan akun Andi Pratama), serta menyajikan file HTML/CSS/JS ke browser. |
| `frontend/js/app.js` | Satu-satunya script JS untuk mengelola localStorage token, memanggil API backend dengan fetch, dan merender tampilan kartu serta form. |

---

## 3. Hasil Pengujian Otomatis (test_step1.py)
Semua fungsi telah diverifikasi dan lulus 100%:
- [x] **Health Check**: Server backend dan SQLite terhubung aktif.
- [x] **Get Courses**: 7 mata kuliah standar (Struktur Data, Basis Data, dll) otomatis terbaca.
- [x] **Login Mahasiswa**: Berhasil autentikasi dengan email `andi@student.telkomuniversity.ac.id` dan password `password123`.
- [x] **Create Study Intent**: Berhasil menyimpan data kebutuhan belajar dan slot ketersediaan waktu ke SQLite.
- [x] **List Study Intent**: Berhasil menampilkan daftar intent aktif milik mahasiswa.
- [x] **Cancel Study Intent**: Berhasil membatalkan status intent menjadi `CANCELLED`.
- [x] **AI-Assisted Study Intent Extraction**: Berhasil mengekstrak pesan teks bebas dalam 1 kali proses (One-Shot) menjadi parameter terstruktur (MK, Topik, Goal, Mode, Waktu, Ukuran Grup).
