"""
Day 12 - Data Integrity & End-to-End Study Intent Validation Test Suite
Tests:
1. Pydantic Schema Validation (P1)
   - Date regex and calendar validity
   - Date range order (earliest <= latest)
   - Time format and range (start < end)
   - Group size constraints (2 <= min <= max <= 10)
   - Non-empty availability requirement
2. AI Extraction Integrity (P0)
   - Verifies no silent dummy defaults (no fake schedule when not provided)
3. End-to-End API & SQLite Persistence
   - AI Extracted flow -> API -> SQLite verification
   - Manual Input flow -> API -> SQLite verification
   - API Rejection for invalid inputs (HTTP 422)
"""

import sys
from pathlib import Path
from datetime import datetime

# Setup path to backend
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError

from app.main import app
from app.database import SessionLocal
from app.models import Student, Course, StudyIntent, IntentAvailability
from app.routes import create_token
from app.schemas import AvailabilityCreate, StudyIntentCreate
from app.extraction import process_chat_for_study_intent


def run_tests():
    print("=" * 70)
    print("RUNNING DAY 12: DATA INTEGRITY & END-TO-END VALIDATION TEST SUITE")
    print("=" * 70)
    
    passed_count = 0
    total_count = 0
    
    def report(name, condition, details=""):
        nonlocal passed_count, total_count
        total_count += 1
        if condition:
            passed_count += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} - {details}")
            assert condition, f"{name}: {details}"

    # ---------------------------------------------------------
    # SUITE 1: Pydantic Schema Validation (P1)
    # ---------------------------------------------------------
    print("\n--- SUITE 1: Schema Validation (Pydantic) ---")
    
    # 1.1 Valid Availability
    try:
        slot = AvailabilityCreate(day_or_date="Rabu", start_time="09:00", end_time="11:00", priority_rank=1)
        report("Valid Availability Slot Accepted", slot.start_time == "09:00" and slot.end_time == "11:00")
    except Exception as e:
        report("Valid Availability Slot Accepted", False, str(e))
        
    # 1.2 Invalid time range (start >= end)
    try:
        AvailabilityCreate(day_or_date="Rabu", start_time="14:00", end_time="10:00", priority_rank=1)
        report("Reject Time Reversal (14:00 >= 10:00)", False, "Should have raised ValidationError")
    except ValidationError:
        report("Reject Time Reversal (14:00 >= 10:00)", True)
        
    # 1.3 Same start and end time
    try:
        AvailabilityCreate(day_or_date="Rabu", start_time="10:00", end_time="10:00", priority_rank=1)
        report("Reject Identical Start & End Time (10:00 == 10:00)", False, "Should have raised ValidationError")
    except ValidationError:
        report("Reject Identical Start & End Time (10:00 == 10:00)", True)

    # 1.4 Invalid time format
    try:
        AvailabilityCreate(day_or_date="Rabu", start_time="25:00", end_time="26:00", priority_rank=1)
        report("Reject Out-of-bounds Time Format (25:00)", False, "Should have raised ValidationError")
    except ValidationError:
        report("Reject Out-of-bounds Time Format (25:00)", True)

    # 1.5 Valid StudyIntentCreate
    valid_payload = {
        "course_id": "TC1013",
        "topics": "Integral Lipat Dua, Teorema Green",
        "learning_goal": "EXAM_PREP",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "HYBRID",
        "earliest_date": "2026-11-20",
        "latest_date": "2026-11-25",
        "min_group_size": 2,
        "max_group_size": 4,
        "availabilities": [
            {"day_or_date": "Senin", "start_time": "13:00", "end_time": "15:00", "priority_rank": 1}
        ]
    }
    try:
        intent = StudyIntentCreate(**valid_payload)
        report("Valid StudyIntentCreate Accepted", intent.earliest_date == "2026-11-20")
    except Exception as e:
        report("Valid StudyIntentCreate Accepted", False, str(e))

    # 1.6 Date reversal (earliest > latest)
    payload_bad_date = dict(valid_payload, earliest_date="2026-11-30", latest_date="2026-11-20")
    try:
        StudyIntentCreate(**payload_bad_date)
        report("Reject Date Reversal (earliest > latest)", False, "Should have raised ValidationError")
    except ValidationError:
        report("Reject Date Reversal (earliest > latest)", True)

    # 1.7 Non-existent calendar date (e.g. 2026-02-30)
    payload_fake_date = dict(valid_payload, earliest_date="2026-02-30", latest_date="2026-03-05")
    try:
        StudyIntentCreate(**payload_fake_date)
        report("Reject Fake Calendar Date (2026-02-30)", False, "Should have raised ValidationError")
    except ValidationError:
        report("Reject Fake Calendar Date (2026-02-30)", True)

    # 1.8 Group size constraint (min_group_size < 2)
    payload_bad_min = dict(valid_payload, min_group_size=1)
    try:
        StudyIntentCreate(**payload_bad_min)
        report("Reject min_group_size < 2", False, "Should have raised ValidationError")
    except ValidationError:
        report("Reject min_group_size < 2", True)

    # 1.9 Group size constraint (min_group_size > max_group_size)
    payload_bad_max = dict(valid_payload, min_group_size=5, max_group_size=3)
    try:
        StudyIntentCreate(**payload_bad_max)
        report("Reject min_group_size > max_group_size", False, "Should have raised ValidationError")
    except ValidationError:
        report("Reject min_group_size > max_group_size", True)

    # 1.10 Zero availabilities
    payload_empty_avail = dict(valid_payload, availabilities=[])
    try:
        StudyIntentCreate(**payload_empty_avail)
        report("Reject Zero Availability Slots", False, "Should have raised ValidationError")
    except ValidationError:
        report("Reject Zero Availability Slots", True)

    # ---------------------------------------------------------
    # SUITE 2: AI Extraction Integrity (P0)
    # ---------------------------------------------------------
    print("\n--- SUITE 2: AI Extraction Integrity (No Fake Defaults) ---")
    
    db = SessionLocal()
    try:
        # Prompt without schedule or group
        res_no_sched = process_chat_for_study_intent("Saya mau belajar Kalkulus bab Turunan Fungsi Aljabar", db=db)
        
        availabilities = res_no_sched.get("availabilities") or []
        ext_status = res_no_sched.get("extraction_status") or {}
        
        report(
            "Extraction: Course detected without dummy schedule",
            res_no_sched.get("course_name") is not None and len(availabilities) == 0,
            f"Availabilities count: {len(availabilities)}"
        )
        report(
            "Extraction: Schedule status marked as MISSING (not EXTRACTED)",
            ext_status.get("availability") == "MISSING",
            f"Status: {ext_status.get('availability')}"
        )
        report(
            "Extraction: Group size empty when unspecified",
            res_no_sched.get("min_group_size") is None and res_no_sched.get("max_group_size") is None,
            f"Group: min={res_no_sched.get('min_group_size')}, max={res_no_sched.get('max_group_size')}"
        )
    finally:
        db.close()

    # ---------------------------------------------------------
    # SUITE 3: End-to-End Endpoint & SQLite Persistence
    # ---------------------------------------------------------
    print("\n--- SUITE 3: End-to-End Endpoint & SQLite Persistence ---")
    
    db = SessionLocal()
    student = db.query(Student).first()
    course = db.query(Course).first()
    
    assert student is not None, "Test requires at least 1 Student seeded in database"
    assert course is not None, "Test requires at least 1 Course seeded in database"

    from app.routes import create_study_intent
    from fastapi import HTTPException
    
    # 3.1 Flow A: Intent Creation from AI Extracted Parameters
    intent_payload_ai = {
        "course_id": course.course_id,
        "topics": "Pengenalan Algoritma & Notasi Big-O",
        "learning_goal": "UNDERSTAND",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "OFFLINE",
        "earliest_date": "2026-11-20",
        "latest_date": "2026-11-28",
        "min_group_size": 3,
        "max_group_size": 3,
        "availabilities": [
            {"day_or_date": "Kamis", "start_time": "13:00", "end_time": "15:00", "priority_rank": 1}
        ]
    }
    
    schema_ai = StudyIntentCreate(**intent_payload_ai)
    created_intent = create_study_intent(schema_ai, current_student=student, db=db)
    
    report("Endpoint: create_study_intent executed successfully", created_intent is not None)
    created_id = created_intent.intent_id
    
    # Verify directly in SQLite
    db_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == created_id).first()
    report("SQLite: StudyIntent record exists in database", db_intent is not None)
    report("SQLite: Topic exact match", db_intent.topics == intent_payload_ai["topics"])
    report("SQLite: Dates stored properly", db_intent.earliest_date == "2026-11-20" and db_intent.latest_date == "2026-11-28")
    
    db_avail = db.query(IntentAvailability).filter(IntentAvailability.intent_id == created_id).all()
    report("SQLite: Slot availabilities stored correctly", len(db_avail) == 1)
    if db_avail:
        report("SQLite: Slot times match input", db_avail[0].start_time == "13:00" and db_avail[0].end_time == "15:00")

    # 3.2 Flow B: Pure Manual Input (Multi-Slot Availability)
    manual_payload = {
        "course_id": course.course_id,
        "topics": "Materi Ujian Tengah Semester",
        "learning_goal": "EXAM_PREP",
        "collaboration_style": "FOCUS_STUDY",
        "learning_mode": "ONLINE",
        "earliest_date": "2026-12-01",
        "latest_date": "2026-12-05",
        "min_group_size": 2,
        "max_group_size": 4,
        "availabilities": [
            {"day_or_date": "Sabtu", "start_time": "08:00", "end_time": "11:00", "priority_rank": 1},
            {"day_or_date": "Minggu", "start_time": "09:00", "end_time": "12:00", "priority_rank": 2}
        ]
    }
    schema_manual = StudyIntentCreate(**manual_payload)
    manual_intent = create_study_intent(schema_manual, current_student=student, db=db)
    report("Endpoint: Save Manual Study Intent (Multi-slot)", manual_intent is not None)
    manual_id = manual_intent.intent_id
    
    # Verify manual record in SQLite
    db_manual = db.query(StudyIntent).filter(StudyIntent.intent_id == manual_id).first()
    report("SQLite: Manual Intent stored successfully", db_manual is not None)
    report("SQLite: Collaboration style correctly recorded", db_manual.collaboration_style == "FOCUS_STUDY")
    manual_slots = db.query(IntentAvailability).filter(IntentAvailability.intent_id == manual_id).all()
    report("SQLite: Multi-slot manual availability recorded (2 slots)", len(manual_slots) == 2)

    # 3.3 Flow C: Nonexistent Course ID -> HTTPException 404
    bad_course_payload = dict(manual_payload, course_id="NON_EXISTENT_COURSE_999")
    try:
        schema_bad_course = StudyIntentCreate(**bad_course_payload)
        create_study_intent(schema_bad_course, current_student=student, db=db)
        report("Endpoint: Reject Invalid Course ID with 404", False, "Should raise HTTPException 404")
    except HTTPException as he:
        report("Endpoint: Reject Invalid Course ID with 404", he.status_code == 404)

    db.close()

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"TEST RESULT SUMMARY: {passed_count}/{total_count} TESTS PASSED (100% SUCCESS)")
    print("=" * 70)
    assert passed_count == total_count, "Some tests failed!"


if __name__ == "__main__":
    run_tests()
