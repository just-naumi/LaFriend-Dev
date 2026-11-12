from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DB_DIR / "lafriend.db"

DATABASE_URL = f"sqlite:///{DB_FILE.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Enable foreign keys in SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

