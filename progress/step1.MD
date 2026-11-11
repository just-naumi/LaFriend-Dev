# STEP 1: Fondasi Proyek, Database SQLite, & Manajemen Mahasiswa (Student Management)

Dokumen ini menjelaskan secara terperinci rencana kerja untuk **Tahap 1 (Step 1)** dalam pengembangan sistem **LaFriend** sebelum kode implementasi mulai dieksekusi.

---

## 1. Tujuan Utama Tahap 1
Membangun fondasi dasar aplikasi (arsitektur proyek, koneksi database, katalog mata kuliah resmi, serta manajemen profil dan autentikasi mahasiswa) yang menjadi prasyarat mutlak sebelum fitur *Study Intent* dan *Matching Engine* dapat berjalan.

Sesuai prinsip perancangan pada **Day 1** dan **Day 2**:
> *"LaFriend harus mengetahui siapa penggunanya dan mata kuliah apa yang tersedia sebelum mempertemukan mahasiswa dengan partner atau sesi belajar."*

---

## 2. Rencana Struktur Direktori Proyek
Struktur proyek di dalam folder `LaFriend-Dev/` dirancang bersih dan modular:

```text
LaFriend-Dev/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py          # Endpoint registrasi, login, & profil
│   │   │   │   ├── courses.py       # Endpoint katalog mata kuliah
│   │   │   │   └── router.py        # Agregator router API v1
│   │   ├── core/
│   │   │   ├── config.py            # Konfigurasi aplikasi & database
│   │   │   └── security.py          # Hashing password & token/session helper
│   │   ├── db/
│   │   │   ├── database.py          # Engine SQLite & session maker (PRAGMA foreign_keys)
│   │   │   └── seeder.py            # Data awal mata kuliah & dummy mahasiswa
│   │   ├── models/
│   │   │   ├── base.py              # Base declarative SQLAlchemy
│   │   │   ├── student.py           # Model tabel `students`
│   │   │   └── course.py            # Model tabel `courses`
│   │   ├── schemas/
│   │   │   ├── student.py           # Skema Pydantic request/response student
│   │   │   └── course.py            # Skema Pydantic request/response course
│   │   └── main.py                  # Entry point FastAPI (CORS, router, static files)
│   └── requirements.txt             # Dependensi (fastapi, uvicorn, sqlalchemy, pydantic, dll)
├── frontend/
│   ├── index.html                   # Halaman utama (Dashboard & status koneksi)
│   ├── login.html                   # Halaman / form autentikasi mahasiswa
│   ├── profile.html                 # Halaman kelola profil mahasiswa
│   ├── css/
│   │   └── style.css                # Custom styling ringan pendamping Bootstrap 5
│   └── js/
│       ├── api.js                   # Client HTTP fetch helper terpusat
│       └── auth.js                  # Logika interaksi login & profil
├── Plan/                            # Dokumen perancangan Day 1 - Day 10
└── progress/                        # Dokumentasi progres per langkah
    └── step1.MD
```

---

## 3. Komponen yang Akan Dikerjakan di Tahap 1

### A. Backend & Database (FastAPI + SQLite + SQLAlchemy)
1. **Inisialisasi Lingkungan & Dependensi**:
   - `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `pydantic[email]`, `python-multipart`.
2. **Koneksi Database SQLite**:
   - File database lokal: `lafriend.db`.
   - Konfigurasi listener `connect` SQLite untuk mengaktifkan `PRAGMA foreign_keys = ON;`.
3. **Model Data Tahap 1 (Sesuai Day 2)**:
   - **Tabel `students`**:
     - `student_id` (PK, UUID string)
     - `full_name` (String, required)
     - `email` (String, unique, required - validasi kampus)
     - `student_number` / NIM (String, required)
     - `study_program` (String, default: "S1 Teknik Komputer")
     - `academic_year` (Integer, misal: 2025)
     - `password_hash` (String, required untuk keamanan login)
     - `verification_status` (Enum/String: `VERIFIED`, `PENDING`)
     - `account_status` (Enum/String: `ACTIVE`, `RESTRICTED`)
     - `is_discoverable` (Boolean, default: True)
     - `created_at` (DateTime, default: now)
   - **Tabel `courses`**:
     - `course_id` (PK, UUID string)
     - `course_code` (String, unique, misal: "TC2043")
     - `course_name` (String, misal: "Struktur Data")
     - `study_program` (String)
4. **Data Seeder Awal**:
   - Menyiapkan katalog mata kuliah standar (misal: *Struktur Data*, *Algoritma Pemrograman*, *Basis Data*, *Matematika Diskrit*, *Kalkulus*).
   - Menyiapkan minimal 3 akun mahasiswa simulasi (misal: Andi, Budi, Citra) untuk pengujian.
5. **API Endpoints (v1)**:
   - `GET /api/v1/health` : Cek status backend & koneksi database.
   - `POST /api/v1/auth/register` : Registrasi mahasiswa baru.
   - `POST /api/v1/auth/login` : Login mahasiswa & pengembalian info sesi aktif.
   - `GET /api/v1/auth/me` : Mendapatkan data profil mahasiswa yang sedang login.
   - `PUT /api/v1/auth/profile` : Memperbarui preferensi dasar profil mahasiswa.
   - `GET /api/v1/courses` : Mengambil daftar seluruh mata kuliah resmi.
   - `GET /api/v1/courses/{course_id}` : Mengambil detail mata kuliah tertentu.

---

### B. Frontend UI (HTML5 + Bootstrap 5 + Vanilla JS)
1. Menggunakan **Bootstrap 5 (CDN)** yang ringan, responsif, dan rapi.
2. **Navbar Bersama**:
   - Menampilkan status login mahasiswa aktif (nama & NIM) atau tombol Login/Register.
3. **Antarmuka Registrasi & Login**:
   - Form pendaftaran mahasiswa (Nama, NIM, Email, Password, Program Studi, Angkatan).
   - Form login sederhana yang menyimpan identitas sesi di `localStorage`.
4. **Halaman / Komponen Profil**:
   - Menampilkan data identitas mahasiswa yang terverifikasi.
   - Menampilkan daftar katalog mata kuliah resmi yang diambil langsung dari backend API.
   - Indikator kesiapan untuk melangkah ke pembuatan *Study Intent* di Step 2.

---

## 4. Kriteria Selesai (Acceptance Criteria) Tahap 1
Tahap 1 dinyatakan selesai jika:
- [ ] Server FastAPI berhasil dijalankan tanpa error di port lokal (misal: `http://127.0.0.1:8000`).
- [ ] Database SQLite `lafriend.db` terbuat dengan relasi foreign keys aktif.
- [ ] Seeder mata kuliah berhasil mengisi daftar mata kuliah resmi.
- [ ] Pengguna dapat mendaftar dan login melalui antarmuka HTML/Bootstrap 5.
- [ ] Data profil mahasiswa tersimpan dan terbaca dengan benar dari database SQLite melalui API.

---

## 5. Status Persetujuan
- **Status Dokumen**: `MENUNGGU PENGESAHAN USER`
- Setelah Anda menyetujui cakupan dan langkah kerja di atas, kita akan langsung membuat file dan kode implementasi Tahap 1.

