# ==============================================================================
# main.py - Titik Awal (Entry Point) Aplikasi Server FastAPI
# ==============================================================================
# File ini bertugas untuk:
# 1. Menginisialisasi aplikasi FastAPI.
# 2. Membuat tabel-tabel SQLite otomatis saat server pertama kali dinyalakan.
# 3. Mengisi data awal (Seeder) mata kuliah dan akun mahasiswa jika database kosong.
# 4. Menyambungkan seluruh route API dari routes.py.
# 5. Menyajikan file antarmuka (Frontend HTML, CSS, JS) langsung ke browser.
# ==============================================================================

from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Import koneksi database, Base, dan tabel models
from app.database import engine, Base, SessionLocal
from app.models import Student, Course
from app.routes import api_router, hash_password


# ==============================================================================
# FUNGSI SEEDER DATA AWAL
# ==============================================================================
# Fungsi ini mengisi data awal jika database masih kosong, sehingga kita bisa
# langsung mencoba aplikasi tanpa perlu input mata kuliah manual satu per satu.
def seed_data_awal(db):
    # 1. Cek dan isi katalog mata kuliah standar jika belum ada
    if db.query(Course).count() == 0:
        daftar_mk = [
            Course(course_code="TC2043", course_name="Struktur Data", study_program="S1 Teknik Komputer"),
            Course(course_code="TC2033", course_name="Basis Data", study_program="S1 Teknik Komputer"),
            Course(course_code="TC1023", course_name="Algoritma Pemrograman", study_program="S1 Teknik Komputer"),
            Course(course_code="TC2013", course_name="Matematika Diskrit", study_program="S1 Teknik Komputer"),
            Course(course_code="TC1013", course_name="Kalkulus", study_program="S1 Teknik Komputer"),
            Course(course_code="TC3013", course_name="Jaringan Komputer", study_program="S1 Teknik Komputer"),
            Course(course_code="TC3023", course_name="Sistem Operasi", study_program="S1 Teknik Komputer"),
        ]
        db.add_all(daftar_mk)
        db.commit()
        print(">> [Seeder] 7 Mata kuliah awal berhasil ditambahkan ke database.")

    # 2. Cek dan isi akun mahasiswa awal (Andi Pratama)
    andi = db.query(Student).filter(Student.email == "andi@student.telkomuniversity.ac.id").first()
    if not andi:
        andi = Student(
            full_name="Andi Pratama",
            email="andi@student.telkomuniversity.ac.id",
            student_number="1201250001",
            study_program="S1 Teknik Komputer",
            academic_year=2025,
            password_hash=hash_password("password123"),
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        db.add(andi)
        db.commit()
        print(">> [Seeder] Akun mahasiswa awal (Andi Pratama) berhasil dibuat.")
    else:
        # Perbarui hash password agar sesuai dengan fungsi hash terbaru
        andi.password_hash = hash_password("password123")
        db.commit()


# ==============================================================================
# LIFESPAN (Proses yang Dijalankan Saat Server Menyala)
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Otomatis buat seluruh tabel di file database/lafriend.db jika belum ada
    Base.metadata.create_all(bind=engine)

    # 2. Jalankan pengisian data awal (seeder)
    db = SessionLocal()
    try:
        seed_data_awal(db)
    finally:
        db.close()

    yield  # Server berjalan melayani permintaan pengguna


# ==============================================================================
# INISIALISASI SERVER FASTAPI
# ==============================================================================
app = FastAPI(
    title="LaFriend API",
    version="1.0.0",
    description="Backend API Platform Kolaborasi Belajar Mahasiswa (LaFriend)",
    lifespan=lifespan
)

# Pengaturan CORS agar browser diizinkan mengakses API tanpa terblokir
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hubungkan seluruh endpoint API dari routes.py
app.include_router(api_router)


# ==============================================================================
# PENYAJIAN FILE FRONTEND (HTML, CSS, JS)
# ==============================================================================
# Tentukan path folder frontend
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    # Folder CSS
    css_path = FRONTEND_DIR / "css"
    if css_path.exists():
        app.mount("/css", StaticFiles(directory=str(css_path)), name="css")

    # Folder JavaScript
    js_path = FRONTEND_DIR / "js"
    if js_path.exists():
        app.mount("/js", StaticFiles(directory=str(js_path)), name="js")

    # Folder Gambar / Assets
    img_path = FRONTEND_DIR / "img"
    if img_path.exists():
        app.mount("/img", StaticFiles(directory=str(img_path)), name="img")

    # Route untuk membuka halaman utama (index.html)
    @app.get("/")
    def buka_halaman_utama():
        return FileResponse(FRONTEND_DIR / "index.html")

    # Route untuk membuka halaman HTML lainnya (misal: /dashboard, /create-intent, /login)
    @app.get("/{nama_halaman}")
    @app.get("/{nama_halaman}.html")
    def buka_halaman_web(nama_halaman: str):
        nama_bersih = nama_halaman.replace(".html", "")
        target_file = FRONTEND_DIR / f"{nama_bersih}.html"
        if target_file.is_file():
            return FileResponse(target_file)
        raise HTTPException(status_code=404, detail="Halaman web tidak ditemukan")
