from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.database import engine, Base, SessionLocal
from app.db.seeder import seed_initial_data
from app.api.v1.auth import router as auth_router
from app.routers.courses import router as courses_router
from app.routers.study_intent import router as study_intent_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Pastikan tabel dibuat di database/lafriend.db
    Base.metadata.create_all(bind=engine)
    
    # 2. Seed data awal (mata kuliah dan mahasiswa demo)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
        
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API LaFriend — Platform Kolaborasi Belajar Mahasiswa Berbasis Kebutuhan Akademik",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health Check
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "SQLite (database/lafriend.db connected)"
    }

# Register API routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(courses_router, prefix=settings.API_V1_STR)
app.include_router(study_intent_router, prefix=settings.API_V1_STR)

# Mount frontend files
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    css_dir = FRONTEND_DIR / "css"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
    
    js_dir = FRONTEND_DIR / "js"
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

    @app.get("/")
    def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{page_name}")
    @app.get("/{page_name}.html")
    def serve_html_page(page_name: str):
        clean_name = page_name.replace(".html", "")
        file_path = FRONTEND_DIR / f"{clean_name}.html"
        if file_path.is_file():
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Halaman tidak ditemukan")
