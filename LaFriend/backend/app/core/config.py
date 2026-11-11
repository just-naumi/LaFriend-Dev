import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DB_DIR / "lafriend.db"

class Settings:
    PROJECT_NAME: str = "LaFriend API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # SQLite Database File
    DATABASE_URL: str = f"sqlite:///{DB_FILE.as_posix()}"
    
    # Security & JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "lafriend_super_secret_jwt_key_hackathon_2026_tele_univ")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

settings = Settings()

