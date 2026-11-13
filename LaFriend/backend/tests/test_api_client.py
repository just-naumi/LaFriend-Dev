import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Student
from app.routes import create_token

def test_api():
    db = SessionLocal()
    student = db.query(Student).first()
    token = create_token(student.student_id, student.email)
    
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {token}"}
        res = client.post("/api/v1/study-intents/extract-ai", json={"raw_text": "Saya ingin belajar Struktur Data"}, headers=headers)
        print("Status Code:", res.status_code)
        data = res.json()
        print("Course Name:", data.get("course_name"))
        print("Extraction Status:", data.get("extraction_status"))
        print("Parameters:", data.get("extracted_parameters"))
        assert res.status_code == 200
        assert data.get("course_name") == "Struktur Data"
        assert data.get("extraction_status", {}).get("course") == "EXTRACTED"
        assert data.get("topics") is None
        print("\nAPI REGRESSION TEST PASSED SUCCESSFULLY!")
    db.close()

if __name__ == "__main__":
    test_api()
