# ==============================================================================
# database.py - Konfigurasi dan Koneksi Database SQLite
# ==============================================================================
# File ini bertugas untuk:
# 1. Menentukan lokasi file database SQLite (database/lafriend.db).
# 2. Membuat engine SQLAlchemy untuk berbicara dengan database.
# 3. Mengaktifkan fitur Foreign Key pada SQLite (agar relasi antar tabel aktif).
# 4. Menyediakan session database untuk membaca dan menyimpan data.
# ==============================================================================

import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Tentukan path lokasi folder database/lafriend.db
# __file__ adalah posisi file database.py ini berada
# Kita naik 3 tingkat: app -> backend -> LaFriend
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_FOLDER = BASE_DIR / "database"

# Buat folder 'database' secara otomatis jika belum ada
DB_FOLDER.mkdir(parents=True, exist_ok=True)

# Lokasi file database SQLite kita
DB_FILE = DB_FOLDER / "lafriend.db"

# Format URL koneksi untuk SQLite: sqlite:///alamat_file
DATABASE_URL = f"sqlite:///{DB_FILE.as_posix()}"

# 2. Buat engine SQLAlchemy
# check_same_thread=False diperlukan oleh SQLite saat digunakan bersama FastAPI
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# 3. Aktifkan penegakan Foreign Key di SQLite
# Secara default, SQLite tidak mengecek relasi antar tabel. Event listener ini
# memastikan relasi (foreign key) selalu dicek setiap kali koneksi baru dibuka.
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# 4. Buat pembuat Session (SessionLocal) untuk transaksi query database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. Base class untuk mendefinisikan tabel-tabel di file models.py
Base = declarative_base()

# 6. Dependency fungsi untuk dipakai di routes.py
# Fungsi ini membuka koneksi database saat request datang, dan otomatis menutupnya
# setelah request selesai diproses oleh server FastAPI.
def get_db():
    db = SessionLocal()
    try:
        yield db  # Kirim session database ke fungsi router
    finally:
        db.close()  # Pastikan koneksi selalu ditutup agar tidak bocor memory
