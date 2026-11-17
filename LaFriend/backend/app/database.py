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


# 7. Fungsi Migrasi Aman SQLite (Schema Migration)
def ensure_database_schema(target_engine=None):
    """
    Memastikan seluruh tabel dibuat dan kolom-kolom baru (seperti selected_schedule_json)
    pada tabel match_results termigrasi secara otomatis jika belum ada (SQLite safe migration).
    Kegagalan migrasi tidak boleh ditelan secara diam-diam dan akan memicu exception.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    with eng.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(match_results)"))
        columns = [row[1] for row in result.fetchall()]
        if columns and "selected_schedule_json" not in columns:
            try:
                conn.execute(text("ALTER TABLE match_results ADD COLUMN selected_schedule_json TEXT"))
                conn.commit()
            except OperationalError as oe:
                # Periksa apakah error disebabkan oleh race condition duplicate column
                err_msg = str(oe).lower()
                if "duplicate column name" in err_msg or "already exists" in err_msg:
                    re_check = conn.execute(text("PRAGMA table_info(match_results)"))
                    current_cols = [row[1] for row in re_check.fetchall()]
                    if "selected_schedule_json" not in current_cols:
                        raise oe
                else:
                    raise oe

        # Migrasi kolom proposal_id pada tabel invitations (Day 20)
        inv_result = conn.execute(text("PRAGMA table_info(invitations)"))
        inv_columns = [row[1] for row in inv_result.fetchall()]
        if inv_columns and "proposal_id" not in inv_columns:
            try:
                conn.execute(text("ALTER TABLE invitations ADD COLUMN proposal_id VARCHAR(36) REFERENCES group_proposals(proposal_id)"))
                conn.commit()
            except OperationalError as oe:
                err_msg = str(oe).lower()
                if "duplicate column name" in err_msg or "already exists" in err_msg:
                    re_check = conn.execute(text("PRAGMA table_info(invitations)"))
                    current_cols = [row[1] for row in re_check.fetchall()]
                    if "proposal_id" not in current_cols:
                        raise oe
                else:
                    raise oe

        # Migrasi Unique Index uq_proposal_recipient pada tabel invitations (Day 20.8 - Day 20.9)
        inv_recheck = conn.execute(text("PRAGMA table_info(invitations)"))
        inv_curr_cols = [row[1] for row in inv_recheck.fetchall()]
        if "proposal_id" in inv_curr_cols and "recipient_id" in inv_curr_cols:
            idx_res = conn.execute(text("PRAGMA index_list(invitations)")).fetchall()
            existing_indexes = [row[1] for row in idx_res]
            if "uq_proposal_recipient" not in existing_indexes:
                try:
                    conn.execute(text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_proposal_recipient "
                        "ON invitations (proposal_id, recipient_id) "
                        "WHERE proposal_id IS NOT NULL"
                    ))
                    conn.commit()
                except OperationalError as oe:
                    err_msg = str(oe).lower()
                    if "already exists" in err_msg or "duplicate" in err_msg:
                        pass
                    else:
                        raise oe

