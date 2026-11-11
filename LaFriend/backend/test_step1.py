import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

def run_tests():
    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200, f"Health check failed: {res_health.text}"
    print("[PASS] 1. Health Check OK:", res_health.json())

    # 2. Get Courses
    res_courses = client.get("/api/v1/courses")
    assert res_courses.status_code == 200, f"Get courses failed: {res_courses.text}"
    courses = res_courses.json()
    assert len(courses) >= 7, f"Expected at least 7 courses, got {len(courses)}"
    selected_course = courses[0]
    print(f"[PASS] 2. Get Courses OK: {len(courses)} courses found (Selected: {selected_course['course_code']} - {selected_course['course_name']})")

    # 3. Login Demo Account (Andi)
    res_login = client.post("/api/v1/auth/login", json={
        "email": "andi@student.telkomuniversity.ac.id",
        "password": "password123"
    })
    assert res_login.status_code == 200, f"Login failed: {res_login.text}"
    login_data = res_login.json()
    token = login_data["access_token"]
    student = login_data["student"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[PASS] 3. Login OK: Authenticated as {student['full_name']} (NIM: {student['student_number']})")

    # 4. Create Study Intent with Availabilities (Form Day 3)
    intent_payload = {
        "course_id": selected_course["course_id"],
        "topics": "Binary Search Tree, AVL Tree, Red-Black Tree",
        "learning_goal": "UNDERSTAND",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "OFFLINE",
        "earliest_date": "2026-11-12",
        "latest_date": "2026-11-19",
        "min_group_size": 2,
        "max_group_size": 4,
        "availabilities": [
            {
                "day_or_date": "Rabu",
                "start_time": "09:00",
                "end_time": "12:00",
                "priority_rank": 1
            },
            {
                "day_or_date": "Kamis",
                "start_time": "13:00",
                "end_time": "16:00",
                "priority_rank": 2
            }
        ]
    }
    res_create = client.post("/api/v1/study-intents", headers=headers, json=intent_payload)
    assert res_create.status_code == 201, f"Create Study Intent failed: {res_create.text}"
    created_intent = res_create.json()
    intent_id = created_intent["intent_id"]
    print(f"[PASS] 4. Create Study Intent OK: Intent ID {intent_id}, Status: {created_intent['status']}, Slots: {len(created_intent['availabilities'])}")

    # 5. List Student's Study Intents
    res_my_intents = client.get("/api/v1/study-intents", headers=headers)
    assert res_my_intents.status_code == 200, f"Get My Intents failed: {res_my_intents.text}"
    my_intents = res_my_intents.json()
    assert len(my_intents) >= 1, "Expected at least 1 intent in student's dashboard list"
    print(f"[PASS] 5. List Study Intents OK: Retrieved {len(my_intents)} intents for current student")

    # 6. Cancel Study Intent
    res_cancel = client.patch(f"/api/v1/study-intents/{intent_id}/cancel", headers=headers)
    assert res_cancel.status_code == 200, f"Cancel Study Intent failed: {res_cancel.text}"
    cancelled_intent = res_cancel.json()
    assert cancelled_intent["status"] == "CANCELLED", f"Expected status CANCELLED, got {cancelled_intent['status']}"
    print(f"[PASS] 6. Cancel Study Intent OK: Intent ID {intent_id} successfully cancelled")

    print("\n" + "="*60)
    print(">>> ALL STEP 1 BACKEND, DATABASE & API TESTS PASSED! <<<")
    print("="*60)

if __name__ == "__main__":
    run_tests()
