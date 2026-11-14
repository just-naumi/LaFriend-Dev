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

import threading
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
from app.extraction import get_gliner_model

def warmup_ai_model():
    """Memuat bobot GLiNER ke RAM saat startup agar respons chat pertama tidak delay/cold-start."""
    try:
        print(">> [Warmup] Memuat model NLP AI GLiNER ke memori RAM...")
        get_gliner_model()
        print(">> [Warmup] Model NLP AI GLiNER siap digunakan (warm state).")
    except Exception as e:
        print(f">> [Warmup] Catatan pemuatan model AI: {e}")


# ==============================================================================
# FUNGSI SEEDER DATA AWAL
# ==============================================================================
# Fungsi ini mengisi data awal jika database masih kosong, sehingga kita bisa
# langsung mencoba aplikasi tanpa perlu input mata kuliah manual satu per satu.
def seed_data_awal(db):
    # 1. Katalog lengkap Mata Kuliah S1 Teknik Komputer Telkom University (Semester 1 s/d 8)
    daftar_mk_kurikulum = [
        # Semester 1
        ("DUK1A3", "Kalkulus 1", "S1 Teknik Komputer (Semester 1)"),
        ("DUK1B3", "Fisika 1", "S1 Teknik Komputer (Semester 1)"),
        ("DUK1D3", "Kimia", "S1 Teknik Komputer (Semester 1)"),
        ("ACK1A2", "Pengenalan Teknik Komputer", "S1 Teknik Komputer (Semester 1)"),
        ("DUK1E2", "Logika Matematika", "S1 Teknik Komputer (Semester 1)"),
        ("ACK1B3", "Pengantar Rekayasa dan Desain", "S1 Teknik Komputer (Semester 1)"),
        # Semester 2
        ("DUK2A3", "Kalkulus 2", "S1 Teknik Komputer (Semester 2)"),
        ("DUK2B3", "Fisika 2", "S1 Teknik Komputer (Semester 2)"),
        ("ACK1C3", "Algoritma dan Pemrograman", "S1 Teknik Komputer (Semester 2)"),
        ("ACK1D3", "Matematika Diskrit", "S1 Teknik Komputer (Semester 2)"),
        ("ACK1E3", "Jaringan Komputer dan Data", "S1 Teknik Komputer (Semester 2)"),
        # Semester 3
        ("ACK2AAB3", "Struktur Data", "S1 Teknik Komputer (Semester 3)"),
        ("ACK2BAB3", "Keamanan Jaringan", "S1 Teknik Komputer (Semester 3)"),
        ("AZK2DAB3", "Rangkaian Listrik", "S1 Teknik Komputer (Semester 3)"),
        ("AZK2CAB3", "Persamaan Diferensial", "S1 Teknik Komputer (Semester 3)"),
        ("AZK2AAB3", "Probabilitas dan Statistika", "S1 Teknik Komputer (Semester 3)"),
        ("AZK1KAB3", "Aljabar Linier", "S1 Teknik Komputer (Semester 3)"),
        # Semester 4
        ("AZK2HAB3", "Sistem Digital", "S1 Teknik Komputer (Semester 4)"),
        ("AZK2FAB3", "Elektronika", "S1 Teknik Komputer (Semester 4)"),
        ("ACK2DAB3", "Komputasi Awan", "S1 Teknik Komputer (Semester 4)"),
        ("AZK2GAB3", "Pengolahan Sinyal Waktu Kontinu", "S1 Teknik Komputer (Semester 4)"),
        ("ACK2EAB3", "Analisis dan Desain Sistem", "S1 Teknik Komputer (Semester 4)"),
        ("ACK2FAB3", "Perancangan Catu Daya", "S1 Teknik Komputer (Semester 4)"),
        # Semester 5
        ("ACK3AAB3", "Organisasi dan Arsitektur Komputer", "S1 Teknik Komputer (Semester 5)"),
        ("ACK3BAB3", "Sistem Mikroprosesor", "S1 Teknik Komputer (Semester 5)"),
        ("ACK3CAB3", "Basis Data", "S1 Teknik Komputer (Semester 5)"),
        ("ACK3DAB3", "Sistem Jaringan Lanjut", "S1 Teknik Komputer (Semester 5)"),
        ("AZK3AAB3", "Pengolahan Sinyal Digital", "S1 Teknik Komputer (Semester 5)"),
        # Semester 6
        ("ACK3FAB3", "Sistem Tertanam & IoT", "S1 Teknik Komputer (Semester 6)"),
        ("ACK3GAB3", "Sistem Operasi & RTOS", "S1 Teknik Komputer (Semester 6)"),
        ("ACK3HAB3", "Kecerdasan Buatan & Machine Learning", "S1 Teknik Komputer (Semester 6)"),
        ("ACK3IAB3", "Sistem Kendali dan Robotika", "S1 Teknik Komputer (Semester 6)"),
        # Semester 7 & 8
        ("ACK4BAB3", "Manajemen Proyek TI", "S1 Teknik Komputer (Semester 7)"),
        ("ACK4CAB3", "Keamanan Sistem Komputer", "S1 Teknik Komputer (Semester 7)"),
        ("ACK4AAB2", "Proposal Tugas Akhir", "S1 Teknik Komputer (Semester 7)"),
        ("ACK4EAB4", "Tugas Akhir / Skripsi", "S1 Teknik Komputer (Semester 8)"),
        # Peminatan Khusus
        ("ACK4P01", "Pembelajaran Mendalam (Deep Learning)", "S1 Teknik Komputer (Peminatan)"),
        ("ACK4P02", "Komputer Forensik", "S1 Teknik Komputer (Peminatan)"),
        ("ACK4P03", "DevSecOps", "S1 Teknik Komputer (Peminatan)"),
        ("ACK4P04", "Perancangan Sistem VLSI", "S1 Teknik Komputer (Peminatan)"),
        ("ACK4P05", "Teknologi Big Data", "S1 Teknik Komputer (Peminatan)"),
    ]

    new_courses = []
    for code, name, major in daftar_mk_kurikulum:
        existing = db.query(Course).filter(Course.course_name.ilike(name)).first()
        if not existing:
            new_courses.append(Course(course_code=code, course_name=name, study_program=major))
    
    if new_courses:
        db.add_all(new_courses)
        db.commit()
        print(f">> [Seeder] {len(new_courses)} Mata Kuliah S1 Teknik Komputer berhasil ditambahkan.")

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

    # 3. Warm-up model NLP AI GLiNER di background agar inferensi chat langsung instan (tanpa cold-start lag)
    threading.Thread(target=warmup_ai_model, daemon=True).start()

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

# Middleware anti-cache untuk memastikan browser selalu memuat versi frontend terbaru
@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if any(path.endswith(ext) for ext in [".html", ".js", ".css", "/"]) or path == "":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

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
