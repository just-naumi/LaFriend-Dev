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


# 7. Fungsi Migrasi Aman SQLite (Schema Migration - Fail-Closed)
def _normalize_sql_predicate(sql_fragment: str) -> str:
    """Normalisasi spasi, kapitalisasi, dan tanda kurung luar untuk perbandingan predikat WHERE SQLite."""
    import re
    cleaned = re.sub(r"\s+", " ", sql_fragment.strip()).upper()
    while cleaned.startswith("(") and cleaned.endswith(")"):
        inner = cleaned[1:-1].strip()
        depth = 0
        balanced = True
        for ch in inner:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    balanced = False
                    break
        if balanced and depth == 0:
            cleaned = inner
        else:
            break
    return cleaned


def _ensure_sqlite_column(conn, table_name: str, column_name: str, column_ddl: str) -> None:
    """
    Memastikan kolom tersedia pada tabel SQLite (migrasi skema legacy).
    Fail-closed: tidak menelan kegagalan berdasarkan pencocokan teks error.
    Jika ALTER TABLE memicu OperationalError, katalog PRAGMA table_info diperiksa ulang;
    bila kolom tetap tidak ada, exception langsung diteruskan.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    cols = [row[1] for row in conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()]
    if not cols:
        raise RuntimeError(
            f"Validasi migrasi gagal (fail-closed): Tabel '{table_name}' tidak ditemukan."
        )

    if column_name not in cols:
        try:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}"))
            conn.commit()
        except OperationalError as oe:
            re_cols = [row[1] for row in conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()]
            if column_name not in re_cols:
                raise oe

    final_cols = [row[1] for row in conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()]
    if column_name not in final_cols:
        raise RuntimeError(
            f"Validasi migrasi gagal (fail-closed): Kolom '{column_name}' tidak ditemukan pada tabel '{table_name}' setelah migrasi."
        )


def _inspect_sqlite_index(conn, table_name: str, index_name: str):
    """
    Menginspeksi metadata indeks SQLite aktual melalui PRAGMA index_list,
    PRAGMA index_info, dan sqlite_master.
    """
    import re
    from sqlalchemy import text

    idx_rows = conn.execute(text(f'PRAGMA index_list("{table_name}")')).fetchall()
    target_row = None
    for row in idx_rows:
        # Format PRAGMA index_list: (seq, name, unique, origin, partial)
        if row[1] == index_name:
            target_row = row
            break

    if target_row is None:
        return None

    is_unique = bool(target_row[2])
    is_partial = bool(target_row[4])

    info_rows = conn.execute(text(f'PRAGMA index_info("{index_name}")')).fetchall()
    # Format PRAGMA index_info: (seqno, cid, name)
    info_rows_sorted = sorted(info_rows, key=lambda r: r[0])
    indexed_columns = [r[2] for r in info_rows_sorted]

    ddl_sql = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = :tbl AND name = :idx"),
        {"tbl": table_name, "idx": index_name}
    ).scalar()

    where_predicate = None
    if ddl_sql:
        match = re.search(r"\bWHERE\b\s+(.+)$", ddl_sql, flags=re.IGNORECASE | re.DOTALL)
        if match:
            where_predicate = match.group(1).strip().rstrip(";").strip()

    return {
        "name": index_name,
        "unique": is_unique,
        "partial": is_partial,
        "columns": indexed_columns,
        "sql": ddl_sql,
        "where_predicate": where_predicate,
    }


def _validate_sqlite_unique_index(
    conn,
    table_name: str,
    index_name: str,
    expected_columns: list[str],
    expected_where: str | None = None
) -> None:
    """
    Validasi fail-closed atas definisi unique index SQLite.
    Memastikan nama, status unique, daftar/urutan kolom, serta predikat partial WHERE
    cocok persis dengan invariant. Melempar RuntimeError jika terjadi ketidaksesuaian.
    """
    meta = _inspect_sqlite_index(conn, table_name, index_name)
    if meta is None:
        raise RuntimeError(
            f"Validasi migrasi gagal (fail-closed): Indeks '{index_name}' tidak ditemukan pada tabel '{table_name}'."
        )

    if not meta["unique"]:
        raise RuntimeError(
            f"Validasi migrasi gagal (fail-closed): Indeks '{index_name}' pada tabel '{table_name}' bukan UNIQUE index."
        )

    if meta["columns"] != expected_columns:
        raise RuntimeError(
            f"Validasi migrasi gagal (fail-closed): Kolom indeks '{index_name}' pada tabel '{table_name}' "
            f"adalah {meta['columns']}, diharapkan {expected_columns}."
        )

    if expected_where is not None:
        if not meta["partial"] or not meta["where_predicate"]:
            raise RuntimeError(
                f"Validasi migrasi gagal (fail-closed): Indeks '{index_name}' pada tabel '{table_name}' "
                f"wajib berupa partial index dengan kondisi 'WHERE {expected_where}', definisi aktual: {meta['sql']}."
            )
        actual_norm = _normalize_sql_predicate(meta["where_predicate"])
        expected_norm = _normalize_sql_predicate(expected_where)
        if actual_norm != expected_norm:
            raise RuntimeError(
                f"Validasi migrasi gagal (fail-closed): Predikat partial index '{index_name}' pada tabel '{table_name}' "
                f"adalah '{meta['where_predicate']}', diharapkan '{expected_where}'."
            )
    else:
        if meta["partial"] or meta["where_predicate"]:
            raise RuntimeError(
                f"Validasi migrasi gagal (fail-closed): Indeks '{index_name}' pada tabel '{table_name}' "
                f"tidak boleh berupa partial index, definisi aktual: {meta['sql']}."
            )


def _ensure_sqlite_unique_index(
    conn,
    table_name: str,
    index_name: str,
    expected_columns: list[str],
    expected_where: str | None = None
) -> None:
    """
    Membuat (jika belum ada) dan memvalidasi definisi unique index SQLite secara fail-closed.
    Tidak ada silent pass: setiap error DDL (termasuk duplikasi data eksisting atau error I/O)
    maupun ketidaksesuaian definisi indeks lama langsung menghentikan migrasi dengan exception.
    """
    from sqlalchemy import text

    # Pastikan kolom target benar-benar tersedia sebelum membuat indeks
    curr_cols = [row[1] for row in conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()]
    missing_cols = [col for col in expected_columns if col not in curr_cols]
    if missing_cols:
        raise RuntimeError(
            f"Validasi migrasi gagal (fail-closed): Kolom {missing_cols} tidak ditemukan pada tabel '{table_name}' "
            f"saat menyiapkan indeks '{index_name}'."
        )

    existing_meta = _inspect_sqlite_index(conn, table_name, index_name)
    if existing_meta is None:
        cols_sql = ", ".join(expected_columns)
        ddl = f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({cols_sql})"
        if expected_where:
            ddl += f" WHERE {expected_where}"
        conn.execute(text(ddl))
        conn.commit()

    # Verifikasi katalog SQLite secara eksplisit pasca-DDL maupun pada indeks eksisting
    _validate_sqlite_unique_index(
        conn=conn,
        table_name=table_name,
        index_name=index_name,
        expected_columns=expected_columns,
        expected_where=expected_where,
    )


def ensure_database_schema(target_engine=None):
    """
    Memastikan seluruh tabel, kolom migrasi legacy, dan unique index invariant
    terbentuk dan terverifikasi secara ketat (idempotent & fail-closed).
    Kegagalan migrasi tidak pernah ditelan secara diam-diam dan selalu memicu exception.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    with eng.connect() as conn:
        # 1. Migrasi kolom selected_schedule_json pada tabel match_results (Day 16)
        _ensure_sqlite_column(conn, "match_results", "selected_schedule_json", "TEXT")

        # 2. Migrasi kolom proposal_id & partial unique index pada tabel invitations (Day 20)
        _ensure_sqlite_column(
            conn,
            "invitations",
            "proposal_id",
            "VARCHAR(36) REFERENCES group_proposals(proposal_id)"
        )
        _ensure_sqlite_unique_index(
            conn=conn,
            table_name="invitations",
            index_name="uq_proposal_recipient",
            expected_columns=["proposal_id", "recipient_id"],
            expected_where="proposal_id IS NOT NULL",
        )

        # 3. Migrasi kolom proposal_id & partial unique index pada tabel study_sessions (Day 21)
        # Invariant: Satu GroupProposal hanya dapat menghasilkan tepat satu StudySession.
        _ensure_sqlite_column(
            conn,
            "study_sessions",
            "proposal_id",
            "VARCHAR(36) REFERENCES group_proposals(proposal_id) ON DELETE RESTRICT"
        )
        _ensure_sqlite_unique_index(
            conn=conn,
            table_name="study_sessions",
            index_name="uq_session_proposal",
            expected_columns=["proposal_id"],
            expected_where="proposal_id IS NOT NULL",
        )

        # 4. Migrasi kolom intent_id & unique indexes pada tabel session_members (Day 21.1 - 21.1.1)
        # Invariant Global Permanen: Satu StudyIntent hanya boleh digunakan sekali sepanjang riwayat
        # untuk maksimal satu keanggotaan sesi (tidak digunakan ulang walaupun sesi selesai/dibatalkan).
        _ensure_sqlite_column(
            conn,
            "session_members",
            "intent_id",
            "VARCHAR(36) REFERENCES study_intents(intent_id) ON DELETE RESTRICT"
        )
        _ensure_sqlite_unique_index(
            conn=conn,
            table_name="session_members",
            index_name="uq_session_member_intent",
            expected_columns=["intent_id"],
            expected_where="intent_id IS NOT NULL",
        )
        # Invariant: Satu mahasiswa hanya boleh tercatat maksimal satu kali dalam sesi belajar yang sama.
        _ensure_sqlite_unique_index(
            conn=conn,
            table_name="session_members",
            index_name="uq_session_member_student",
            expected_columns=["session_id", "student_id"],
            expected_where=None,
        )

