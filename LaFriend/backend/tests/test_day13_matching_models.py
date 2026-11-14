"""
Day 13 - Database & Matching Architecture Verification Test Suite
Tests:
1. Pydantic Schemas Validation for 5 New Models
   - SessionSlot (dates, time range, status)
   - SessionMember (role, status)
   - StudySession (group sizes, enums, status)
   - Invitation (type exclusivity, required targets)
   - MatchResult (candidate target exclusivity, score bounds)
2. Database ORM & SQLite Persistence (9 Core Models)
   - StudySession creation with Host FK & Course FK
   - SessionSlot & SessionMember relations
   - Invitation (JOIN_SESSION & PARTNER_INVITE)
   - MatchResult (SESSION & PARTNER)
   - Foreign key integrity & Cascade delete verification
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Setup path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError
from app.database import engine, Base, SessionLocal
from app.models import (
    Student, Course, StudyIntent, IntentAvailability,
    StudySession, SessionSlot, SessionMember, Invitation, MatchResult
)
from app.schemas import (
    SessionSlotCreate, SessionMemberCreate, StudySessionCreate,
    InvitationCreate, MatchBreakdown, MatchResultCreate
)


def run_tests():
    print("=" * 70)
    print("RUNNING DAY 13: DATABASE & MATCHING ARCHITECTURE TEST SUITE")
    print("=" * 70)
    
    # 0. Initialize SQLite tables for all 9 models
    Base.metadata.create_all(bind=engine)
    
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
    # SUITE 1: Pydantic Schema Validation (5 New Models)
    # ---------------------------------------------------------
    print("\n--- SUITE 1: Schema Validation for Day 13 Models ---")
    
    # 1.1 SessionSlotCreate - Valid
    try:
        slot = SessionSlotCreate(
            session_date="2026-11-20",
            start_time="10:00",
            end_time="12:00",
            status="PROPOSED"
        )
        report("Slot: Valid slot accepted", slot.session_date == "2026-11-20")
    except Exception as e:
        report("Slot: Valid slot accepted", False, str(e))

    # 1.2 SessionSlotCreate - Time Reversal (start >= end)
    try:
        SessionSlotCreate(
            session_date="2026-11-20",
            start_time="14:00",
            end_time="10:00"
        )
        report("Slot: Reject time reversal", False, "Should raise ValidationError")
    except ValidationError:
        report("Slot: Reject time reversal", True)

    # 1.3 SessionSlotCreate - Invalid Date
    try:
        SessionSlotCreate(
            session_date="2026-02-30",
            start_time="10:00",
            end_time="12:00"
        )
        report("Slot: Reject fake calendar date (2026-02-30)", False, "Should raise ValidationError")
    except ValidationError:
        report("Slot: Reject fake calendar date (2026-02-30)", True)

    # 1.4 SessionMemberCreate - Valid Role & Status
    try:
        mem = SessionMemberCreate(student_id="std_123", role="HOST", status="CONFIRMED")
        report("Member: Valid role and status accepted", mem.role == "HOST" and mem.status == "CONFIRMED")
    except Exception as e:
        report("Member: Valid role and status accepted", False, str(e))

    # 1.5 SessionMemberCreate - Invalid Role
    try:
        SessionMemberCreate(student_id="std_123", role="ADMIN", status="CONFIRMED")
        report("Member: Reject invalid role (ADMIN)", False, "Should raise ValidationError")
    except ValidationError:
        report("Member: Reject invalid role (ADMIN)", True)

    # 1.6 StudySessionCreate - Valid
    try:
        sess = StudySessionCreate(
            course_id="crs_123",
            title="Kelompok Belajar Kalkulus Bab Turunan",
            learning_goal="EXAM_PREP",
            collaboration_style="PRACTICE",
            learning_mode="HYBRID",
            min_group_size=2,
            max_group_size=4,
            status="DRAFT"
        )
        report("Session: Valid session payload accepted", sess.title.startswith("Kelompok Belajar"))
    except Exception as e:
        report("Session: Valid session payload accepted", False, str(e))

    # 1.7 StudySessionCreate - Group Size Validation (min > max)
    try:
        StudySessionCreate(
            course_id="crs_123",
            title="Sesi Belajar",
            min_group_size=5,
            max_group_size=3
        )
        report("Session: Reject min_group_size > max_group_size", False, "Should raise ValidationError")
    except ValidationError:
        report("Session: Reject min_group_size > max_group_size", True)

    # 1.8 StudySessionCreate - Group Size Validation (min < 2)
    try:
        StudySessionCreate(
            course_id="crs_123",
            title="Sesi Belajar",
            min_group_size=1,
            max_group_size=3
        )
        report("Session: Reject min_group_size < 2", False, "Should raise ValidationError")
    except ValidationError:
        report("Session: Reject min_group_size < 2", True)

    # 1.9 InvitationCreate - JOIN_SESSION requires session_id
    try:
        InvitationCreate(
            invitation_type="JOIN_SESSION",
            recipient_id="std_target",
            session_id=None
        )
        report("Invitation: Reject JOIN_SESSION without session_id", False, "Should raise ValidationError")
    except ValidationError:
        report("Invitation: Reject JOIN_SESSION without session_id", True)

    # 1.10 InvitationCreate - PARTNER_INVITE requires target_intent_id
    try:
        InvitationCreate(
            invitation_type="PARTNER_INVITE",
            recipient_id="std_target",
            target_intent_id=None
        )
        report("Invitation: Reject PARTNER_INVITE without target_intent_id", False, "Should raise ValidationError")
    except ValidationError:
        report("Invitation: Reject PARTNER_INVITE without target_intent_id", True)

    # 1.11 InvitationCreate - Valid
    try:
        inv = InvitationCreate(
            invitation_type="JOIN_SESSION",
            recipient_id="std_target",
            session_id="sess_123",
            message="Yuk gabung sesi belajar Kalkulus kami!"
        )
        report("Invitation: Valid JOIN_SESSION accepted", inv.session_id == "sess_123")
    except Exception as e:
        report("Invitation: Valid JOIN_SESSION accepted", False, str(e))

    # 1.12 MatchResultCreate - Exclusivity (SESSION cannot have target_intent_id)
    breakdown_data = MatchBreakdown(
        topic_similarity=90.0,
        goal_compatibility=100.0,
        style_compatibility=80.0,
        date_preference=100.0,
        mode_compatibility=100.0
    )
    try:
        MatchResultCreate(
            intent_id="int_123",
            candidate_type="SESSION",
            candidate_session_id="sess_123",
            target_intent_id="int_456",  # Both targets provided -> should reject!
            compatibility_score=94.0,
            breakdown=breakdown_data
        )
        report("MatchResult: Reject dual candidate targets", False, "Should raise ValidationError")
    except ValidationError:
        report("MatchResult: Reject dual candidate targets", True)

    # 1.13 MatchResultCreate - Valid PARTNER matching
    try:
        match_partner = MatchResultCreate(
            intent_id="int_123",
            candidate_type="PARTNER",
            target_intent_id="int_456",
            compatibility_score=94.0,
            breakdown=breakdown_data,
            explanation="Kesesuaian tinggi pada materi Kalkulus dan jadwal sore"
        )
        report("MatchResult: Valid PARTNER candidate accepted", match_partner.compatibility_score == 94.0)
    except Exception as e:
        report("MatchResult: Valid PARTNER candidate accepted", False, str(e))

    # 1.14 MatchResultCreate - Out-of-bounds score
    try:
        MatchResultCreate(
            intent_id="int_123",
            candidate_type="PARTNER",
            target_intent_id="int_456",
            compatibility_score=110.0,
            breakdown=breakdown_data
        )
        report("MatchResult: Reject score > 100", False, "Should raise ValidationError")
    except ValidationError:
        report("MatchResult: Reject score > 100", True)

    # ---------------------------------------------------------
    # SUITE 2: Database ORM & SQLite Persistence (9 Core Models)
    # ---------------------------------------------------------
    print("\n--- SUITE 2: Database ORM & SQLite Persistence ---")
    
    db = SessionLocal()
    try:
        student = db.query(Student).first()
        student2 = db.query(Student).offset(1).first() or student
        course = db.query(Course).first()
        
        assert student is not None, "Need at least 1 Student"
        assert course is not None, "Need at least 1 Course"

        # 2.1 Buat StudySession
        new_session = StudySession(
            host_id=student.student_id,
            course_id=course.course_id,
            title="Kelompok Belajar Struktur Data - Pohon Biner",
            description="Mempersiapkan tugas praktikum pohon biner dan AVL",
            learning_goal="PRACTICE",
            collaboration_style="DISCUSSION",
            learning_mode="OFFLINE",
            location="Gedung TULT Lantai 2",
            min_group_size=2,
            max_group_size=4,
            status="OPEN"
        )
        db.add(new_session)
        db.flush()
        report("DB: StudySession created and flushed", new_session.session_id is not None)

        # 2.2 Tambahkan SessionSlot
        new_slot = SessionSlot(
            session_id=new_session.session_id,
            session_date="2026-11-22",
            start_time="13:00",
            end_time="15:00",
            status="APPROVED"
        )
        db.add(new_slot)
        
        # 2.3 Tambahkan SessionMember (Host & Member)
        host_member = SessionMember(
            session_id=new_session.session_id,
            student_id=student.student_id,
            role="HOST",
            status="CONFIRMED"
        )
        db.add(host_member)
        
        # 2.4 Tambahkan Invitation (JOIN_SESSION)
        new_invitation = Invitation(
            invitation_type="JOIN_SESSION",
            sender_id=student2.student_id,
            recipient_id=student.student_id,
            session_id=new_session.session_id,
            status="PENDING",
            message="Halo Andi, bolehkah saya bergabung ke sesi Struktur Data ini?"
        )
        db.add(new_invitation)

        # 2.5 Tambahkan StudyIntent & MatchResult
        new_intent = StudyIntent(
            student_id=student.student_id,
            course_id=course.course_id,
            topics="Binary Tree, Binary Search Tree",
            learning_goal="PRACTICE",
            collaboration_style="DISCUSSION",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-25",
            min_group_size=2,
            max_group_size=4,
            status="ACTIVE"
        )
        db.add(new_intent)
        db.flush()

        match_res = MatchResult(
            intent_id=new_intent.intent_id,
            candidate_type="SESSION",
            candidate_session_id=new_session.session_id,
            compatibility_score=95.5,
            breakdown_json=json.dumps({
                "topic_similarity": 95,
                "goal_compatibility": 100,
                "style_compatibility": 90,
                "date_preference": 100,
                "mode_compatibility": 92
            }),
            explanation="Topik dan mode belajar sangat cocok dengan sesi aktif"
        )
        db.add(match_res)
        
        db.commit()
        report("DB: All 5 matching models committed to SQLite", True)

        # 2.6 Verifikasi ORM Traversal & Relasi
        sess_check = db.query(StudySession).filter(StudySession.session_id == new_session.session_id).first()
        report("ORM: session.host relationship resolved", sess_check.host.student_id == student.student_id)
        report("ORM: session.course relationship resolved", sess_check.course.course_id == course.course_id)
        report("ORM: session.slots list contains slot", len(sess_check.slots) == 1 and sess_check.slots[0].start_time == "13:00")
        report("ORM: session.members list contains host member", len(sess_check.members) == 1 and sess_check.members[0].role == "HOST")
        report("ORM: session.invitations contains invitation", len(sess_check.invitations) == 1)

        # 2.7 Verifikasi MatchResult Traversal
        intent_check = db.query(StudyIntent).filter(StudyIntent.intent_id == new_intent.intent_id).first()
        report("ORM: intent.match_results linked properly", len(intent_check.match_results) == 1)
        report("ORM: match_result candidate_session resolved", intent_check.match_results[0].candidate_session.title == sess_check.title)

        # 2.8 Verifikasi Cascade Delete pada StudySession
        db.delete(sess_check)
        db.commit()
        
        orphan_slots = db.query(SessionSlot).filter(SessionSlot.session_id == new_session.session_id).all()
        orphan_members = db.query(SessionMember).filter(SessionMember.session_id == new_session.session_id).all()
        orphan_invitations = db.query(Invitation).filter(Invitation.session_id == new_session.session_id).all()
        
        report(
            "Cascade: session delete cascades to slots, members, invitations",
            len(orphan_slots) == 0 and len(orphan_members) == 0 and len(orphan_invitations) == 0,
            f"Slots={len(orphan_slots)}, Members={len(orphan_members)}, Invs={len(orphan_invitations)}"
        )
        
    finally:
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
