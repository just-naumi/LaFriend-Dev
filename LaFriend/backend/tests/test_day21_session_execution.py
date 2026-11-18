# ==============================================================================
# tests/test_day21_session_execution.py
# ==============================================================================
# Test Suite Day 21: Study Session Execution Layer
# Memvalidasi transisi GroupProposal (READY_FOR_SESSION) -> StudySession (CONFIRMED),
# pembentukan SessionSlot & SessionMember secara atomik, transisi StudyIntent ke MATCHED,
# status proposal ke SESSION_EXECUTED, proteksi idempotensi dan konkurensi (One Proposal = One Session),
# serta otorisasi ketat host.
# ==============================================================================

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import unittest
from datetime import datetime, timedelta
import json
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.database import Base, get_db, ensure_database_schema
from app.models import (
    Student, Course, StudyIntent, IntentAvailability,
    GroupProposal, Invitation, StudySession, SessionSlot, SessionMember
)
from app.routes import SECRET_KEY, ALGORITHM


def create_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    ensure_database_schema(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, TestingSession


def create_token(student_id: str, email: str) -> str:
    payload = {
        "sub": student_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class TestDay21SessionExecution(unittest.TestCase):
    """Test suite untuk eksekusi sesi belajar dari usulan kelompok (Day 21)."""

    def setUp(self):
        self.engine, self.TestingSession = create_test_db()
        self.db = self.TestingSession()
        self.original_overrides = dict(app.dependency_overrides)

        def override_get_db():
            session = self.TestingSession()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.course = Course(
            course_id="c_d21_struct",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.db.add(self.course)

        # Host Andi
        self.andi = Student(
            student_id="s_andi_d21",
            full_name="Andi Pratama",
            email="andi.d21@telkomuniversity.ac.id",
            student_number="1201250051",
            password_hash="hashed_pw_andi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.andi)

        # Anggota 1 Budi
        self.budi = Student(
            student_id="s_budi_d21",
            full_name="Budi Santoso",
            email="budi.d21@telkomuniversity.ac.id",
            student_number="1201250052",
            password_hash="hashed_pw_budi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.budi)

        # Anggota 2 Citra
        self.citra = Student(
            student_id="s_citra_d21",
            full_name="Citra Lestari",
            email="citra.d21@telkomuniversity.ac.id",
            student_number="1201250053",
            password_hash="hashed_pw_citra",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.citra)

        # Non-member Doni
        self.doni = Student(
            student_id="s_doni_d21",
            full_name="Doni Setiawan",
            email="doni.d21@telkomuniversity.ac.id",
            student_number="1201250054",
            password_hash="hashed_pw_doni",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.doni)

        # Intents
        self.intent_andi = StudyIntent(
            intent_id="intent_andi_d21",
            student_id=self.andi.student_id,
            course_id=self.course.course_id,
            topics="Binary Trees, AVL",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            min_group_size=3,
            max_group_size=4,
            status="ACTIVE"
        )
        self.db.add(self.intent_andi)

        self.intent_budi = StudyIntent(
            intent_id="intent_budi_d21",
            student_id=self.budi.student_id,
            course_id=self.course.course_id,
            topics="Binary Trees",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            min_group_size=3,
            max_group_size=4,
            status="ACTIVE"
        )
        self.db.add(self.intent_budi)

        self.intent_citra = StudyIntent(
            intent_id="intent_citra_d21",
            student_id=self.citra.student_id,
            course_id=self.course.course_id,
            topics="Binary Trees",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            min_group_size=3,
            max_group_size=4,
            status="ACTIVE"
        )
        self.db.add(self.intent_citra)

        self.db.commit()

        self.token_andi = create_token(self.andi.student_id, self.andi.email)
        self.token_budi = create_token(self.budi.student_id, self.budi.email)
        self.token_doni = create_token(self.doni.student_id, self.doni.email)

    def tearDown(self):
        app.dependency_overrides = self.original_overrides
        self.db.close()
        self.engine.dispose()

    def _setup_ready_proposal(self, status="READY_FOR_SESSION"):
        """Helper untuk membuat proposal siap eksekusi."""
        selected_schedule = {
            "date": "2026-11-25",
            "start_time": "10:00",
            "end_time": "12:00",
            "overlap_hours": 2.0
        }
        proposal = GroupProposal(
            proposal_id=f"prop_d21_{datetime.utcnow().timestamp()}",
            host_intent_id=self.intent_andi.intent_id,
            host_student_id=self.andi.student_id,
            course_id=self.course.course_id,
            status=status,
            min_group_size_bound=3,
            max_group_size_bound=4,
            group_quality_score=90.0,
            average_pair_score=90.0,
            minimum_pair_score=85.0,
            selected_schedule_json=json.dumps(selected_schedule),
            proposal_snapshot_json=json.dumps({"members": [self.andi.student_id, self.budi.student_id, self.citra.student_id]}),
            message="Belajar bareng binary tree",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            finalized_at=datetime.utcnow() if status == "READY_FOR_SESSION" else None
        )
        self.db.add(proposal)
        self.db.flush()

        # Undangan Budi (ACCEPTED)
        inv_budi = Invitation(
            invitation_id=f"inv_b_{proposal.proposal_id}",
            invitation_type="GROUP_PROPOSAL",
            proposal_id=proposal.proposal_id,
            target_intent_id=self.intent_budi.intent_id,
            sender_id=self.andi.student_id,
            recipient_id=self.budi.student_id,
            status="ACCEPTED",
            created_at=datetime.utcnow(),
            responded_at=datetime.utcnow()
        )
        self.db.add(inv_budi)

        # Undangan Citra (ACCEPTED)
        inv_citra = Invitation(
            invitation_id=f"inv_c_{proposal.proposal_id}",
            invitation_type="GROUP_PROPOSAL",
            proposal_id=proposal.proposal_id,
            target_intent_id=self.intent_citra.intent_id,
            sender_id=self.andi.student_id,
            recipient_id=self.citra.student_id,
            status="ACCEPTED",
            created_at=datetime.utcnow(),
            responded_at=datetime.utcnow()
        )
        self.db.add(inv_citra)
        self.db.commit()

        return proposal, inv_budi, inv_citra

    def test_01_successful_session_execution(self):
        """Host berhasil mengeksekusi proposal READY_FOR_SESSION -> StudySession CONFIRMED terbentuk atomik."""
        proposal, _, _ = self._setup_ready_proposal("READY_FOR_SESSION")

        r = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 201)
        data = r.json()

        # Verifikasi objek StudySession
        self.assertIn("session_id", data)
        self.assertEqual(data["status"], "CONFIRMED")
        self.assertEqual(data["host_id"], self.andi.student_id)
        self.assertEqual(data["course_id"], self.course.course_id)
        self.assertEqual(data["proposal_id"], proposal.proposal_id)

        # Verifikasi SessionSlot
        self.assertEqual(len(data["slots"]), 1)
        self.assertEqual(data["slots"][0]["session_date"], "2026-11-25")
        self.assertEqual(data["slots"][0]["start_time"], "10:00")
        self.assertEqual(data["slots"][0]["end_time"], "12:00")
        self.assertEqual(data["slots"][0]["status"], "APPROVED")

        # Verifikasi SessionMember: Host + 2 accepted members = 3
        self.assertEqual(len(data["members"]), 3)
        member_roles = {m["student_id"]: m["role"] for m in data["members"]}
        self.assertEqual(member_roles[self.andi.student_id], "HOST")
        self.assertEqual(member_roles[self.budi.student_id], "MEMBER")
        self.assertEqual(member_roles[self.citra.student_id], "MEMBER")

        # Verifikasi Database: StudyIntent seluruh anggota beralih ke MATCHED
        self.db.expire_all()
        db_intent_andi = self.db.query(StudyIntent).filter(StudyIntent.intent_id == self.intent_andi.intent_id).first()
        db_intent_budi = self.db.query(StudyIntent).filter(StudyIntent.intent_id == self.intent_budi.intent_id).first()
        db_intent_citra = self.db.query(StudyIntent).filter(StudyIntent.intent_id == self.intent_citra.intent_id).first()
        self.assertEqual(db_intent_andi.status, "MATCHED")
        self.assertEqual(db_intent_budi.status, "MATCHED")
        self.assertEqual(db_intent_citra.status, "MATCHED")

        # Verifikasi Database: Proposal beralih ke SESSION_EXECUTED
        db_prop = self.db.query(GroupProposal).filter(GroupProposal.proposal_id == proposal.proposal_id).first()
        self.assertEqual(db_prop.status, "SESSION_EXECUTED")
        self.assertIsNotNone(db_prop.study_session)

    def test_02_idempotency_duplicate_request(self):
        """Memanggil execute berkali-kali untuk proposal yang sama mengembalikan sesi yang sama tanpa duplikasi."""
        proposal, _, _ = self._setup_ready_proposal("READY_FOR_SESSION")

        r1 = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r1.status_code, 201)
        session_id_1 = r1.json()["session_id"]

        # Request kedua oleh host
        r2 = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertIn(r2.status_code, [200, 201])
        session_id_2 = r2.json()["session_id"]

        self.assertEqual(session_id_1, session_id_2)

        # Verifikasi hanya ada tepat 1 StudySession di database untuk proposal tersebut
        self.db.expire_all()
        sessions = self.db.query(StudySession).filter(StudySession.proposal_id == proposal.proposal_id).all()
        self.assertEqual(len(sessions), 1)

    def test_03_non_host_authorization_rejected(self):
        """Bukan host (Doni atau Budi) dilarang mengeksekusi sesi -> HTTP 403."""
        proposal, _, _ = self._setup_ready_proposal("READY_FOR_SESSION")

        # Doni (bukan anggota)
        r_doni = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_doni}"}
        )
        self.assertEqual(r_doni.status_code, 403)
        self.assertIn("Hanya host", r_doni.json()["detail"])

        # Budi (anggota tapi bukan host)
        r_budi = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_budi}"}
        )
        self.assertEqual(r_budi.status_code, 403)
        self.assertIn("Hanya host", r_budi.json()["detail"])

    def test_04_execute_rejected_if_not_ready_for_session(self):
        """Proposal yang belum READY_FOR_SESSION (misal QUORUM_REACHED atau PENDING_RESPONSES) ditolak -> HTTP 400."""
        proposal, _, _ = self._setup_ready_proposal("QUORUM_REACHED")

        r = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("READY_FOR_SESSION", r.json()["detail"])

    def test_05_proposal_already_session_executed_without_session(self):
        """Jika proposal berstatus SESSION_EXECUTED tapi datanya tidak ada di tabel study_sessions -> HTTP 400."""
        proposal, _, _ = self._setup_ready_proposal("SESSION_EXECUTED")

        r = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("SESSION_EXECUTED", r.json()["detail"])

    def test_06_intent_already_matched_by_another_session(self):
        """Jika salah satu intent anggota sudah berstatus MATCHED oleh sesi lain -> HTTP 400."""
        proposal, _, _ = self._setup_ready_proposal("READY_FOR_SESSION")

        # Budi sudah ter-matched di sesi lain
        self.intent_budi.status = "MATCHED"
        self.db.commit()

        r = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("sudah berstatus MATCHED", r.json()["detail"])

    def test_07_invalid_or_missing_schedule_fails_atomically(self):
        """Jadwal terpilih rusak / tidak valid membatalkan eksekusi secara atomik -> HTTP 400."""
        proposal, _, _ = self._setup_ready_proposal("READY_FOR_SESSION")
        proposal.selected_schedule_json = "{bad_json: 123"
        self.db.commit()

        r = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)

        # Verifikasi tidak ada sesi yang terbentuk
        self.db.expire_all()
        sess = self.db.query(StudySession).filter(StudySession.proposal_id == proposal.proposal_id).first()
        self.assertIsNone(sess)

        # Verifikasi intent tetap ACTIVE
        db_intent = self.db.query(StudyIntent).filter(StudyIntent.intent_id == self.intent_andi.intent_id).first()
        self.assertEqual(db_intent.status, "ACTIVE")

    def test_08_unique_constraint_one_proposal_one_session(self):
        """Memverifikasi constraint database uq_session_proposal menolak dua sesi untuk proposal yang sama."""
        proposal, _, _ = self._setup_ready_proposal("READY_FOR_SESSION")

        # Insert sesi pertama langsung ke DB
        sess1 = StudySession(
            session_id=f"sess1_{datetime.utcnow().timestamp()}",
            proposal_id=proposal.proposal_id,
            host_id=self.andi.student_id,
            course_id=self.course.course_id,
            title="Sesi 1",
            status="CONFIRMED"
        )
        self.db.add(sess1)
        self.db.commit()

        # Insert sesi kedua dengan proposal_id yang sama
        sess2 = StudySession(
            session_id=f"sess2_{datetime.utcnow().timestamp()}",
            proposal_id=proposal.proposal_id,
            host_id=self.andi.student_id,
            course_id=self.course.course_id,
            title="Sesi 2",
            status="CONFIRMED"
        )
        self.db.add(sess2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_09_get_session_detail_and_my_sessions(self):
        """Memverifikasi endpoint GET /api/v1/sessions/{id} dan GET /api/v1/sessions/my-sessions."""
        proposal, _, _ = self._setup_ready_proposal("READY_FOR_SESSION")

        r_exec = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r_exec.status_code, 201)
        session_id = r_exec.json()["session_id"]

        # GET detail sesi
        r_detail = self.client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r_detail.status_code, 200)
        self.assertEqual(r_detail.json()["session_id"], session_id)

        # GET my-sessions untuk Host (Andi)
        r_my_andi = self.client.get(
            "/api/v1/sessions/my-sessions",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r_my_andi.status_code, 200)
        my_andi_ids = [s["session_id"] for s in r_my_andi.json()]
        self.assertIn(session_id, my_andi_ids)

        # GET my-sessions untuk Anggota (Budi)
        r_my_budi = self.client.get(
            "/api/v1/sessions/my-sessions",
            headers={"Authorization": f"Bearer {self.token_budi}"}
        )
        self.assertEqual(r_my_budi.status_code, 200)
        my_budi_ids = [s["session_id"] for s in r_my_budi.json()]
        self.assertIn(session_id, my_budi_ids)

        # GET my-sessions untuk Non-anggota (Doni)
        r_my_doni = self.client.get(
            "/api/v1/sessions/my-sessions",
            headers={"Authorization": f"Bearer {self.token_doni}"}
        )
        self.assertEqual(r_my_doni.status_code, 200)
        my_doni_ids = [s["session_id"] for s in r_my_doni.json()]
        self.assertNotIn(session_id, my_doni_ids)

    def test_10_unique_constraint_one_intent_one_session(self):
        """Memverifikasi partial unique index uq_session_member_intent menolak intent_id yang sama dialokasikan ke 2 sesi."""
        sess1 = StudySession(
            session_id=f"sess1_{datetime.utcnow().timestamp()}",
            host_id=self.andi.student_id,
            course_id=self.course.course_id,
            title="Sesi 1",
            status="CONFIRMED"
        )
        self.db.add(sess1)
        self.db.commit()

        # Alokasikan intent_andi ke sess1
        m1 = SessionMember(
            member_id=f"mem1_{datetime.utcnow().timestamp()}",
            session_id=sess1.session_id,
            student_id=self.andi.student_id,
            intent_id=self.intent_andi.intent_id,
            role="HOST",
            status="CONFIRMED"
        )
        self.db.add(m1)
        self.db.commit()

        # Buat sesi kedua
        sess2 = StudySession(
            session_id=f"sess2_{datetime.utcnow().timestamp()}",
            host_id=self.budi.student_id,
            course_id=self.course.course_id,
            title="Sesi 2",
            status="CONFIRMED"
        )
        self.db.add(sess2)
        self.db.commit()

        # Coba alokasikan intent_andi yang sama ke sess2
        m2 = SessionMember(
            member_id=f"mem2_{datetime.utcnow().timestamp()}",
            session_id=sess2.session_id,
            student_id=self.budi.student_id,
            intent_id=self.intent_andi.intent_id,
            role="MEMBER",
            status="CONFIRMED"
        )
        self.db.add(m2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_11_unique_constraint_session_member_student(self):
        """Memverifikasi compound unique constraint uq_session_member_student menolak mahasiswa yang sama tercatat ganda dalam satu sesi."""
        sess = StudySession(
            session_id=f"sess_dup_{datetime.utcnow().timestamp()}",
            host_id=self.andi.student_id,
            course_id=self.course.course_id,
            title="Sesi Uji Mahasiswa Duplikat",
            status="CONFIRMED"
        )
        self.db.add(sess)
        self.db.commit()

        m1 = SessionMember(
            member_id=f"mem1_{datetime.utcnow().timestamp()}",
            session_id=sess.session_id,
            student_id=self.budi.student_id,
            role="MEMBER",
            status="CONFIRMED"
        )
        self.db.add(m1)
        self.db.commit()

        # Coba masukkan budi lagi ke sesi yang sama
        m2 = SessionMember(
            member_id=f"mem2_{datetime.utcnow().timestamp()}",
            session_id=sess.session_id,
            student_id=self.budi.student_id,
            role="MEMBER",
            status="CONFIRMED"
        )
        self.db.add(m2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_12_intent_provenance_and_backward_compatibility(self):
        """Memverifikasi backward compatibility session_members tanpa intent_id (multiple nulls diizinkan) dan navigasi relasi ORM."""
        sess = StudySession(
            session_id=f"sess_compat_{datetime.utcnow().timestamp()}",
            host_id=self.andi.student_id,
            course_id=self.course.course_id,
            title="Sesi Kompatibilitas Legacy",
            status="CONFIRMED"
        )
        self.db.add(sess)
        self.db.commit()

        # 1. Dua anggota lama tanpa intent_id (intent_id=None) wajib berhasil disimpan
        m_legacy_1 = SessionMember(
            member_id=f"mem_leg_1_{datetime.utcnow().timestamp()}",
            session_id=sess.session_id,
            student_id=self.andi.student_id,
            intent_id=None,
            role="HOST",
            status="CONFIRMED"
        )
        m_legacy_2 = SessionMember(
            member_id=f"mem_leg_2_{datetime.utcnow().timestamp()}",
            session_id=sess.session_id,
            student_id=self.budi.student_id,
            intent_id=None,
            role="MEMBER",
            status="CONFIRMED"
        )
        self.db.add(m_legacy_1)
        self.db.add(m_legacy_2)
        self.db.commit()

        # 2. Anggota baru dengan intent_id terisi
        m_new = SessionMember(
            member_id=f"mem_new_{datetime.utcnow().timestamp()}",
            session_id=sess.session_id,
            student_id=self.citra.student_id,
            intent_id=self.intent_citra.intent_id,
            role="MEMBER",
            status="CONFIRMED"
        )
        self.db.add(m_new)
        self.db.commit()

        # 3. Verifikasi provenance navigasi ORM
        self.db.refresh(m_new)
        self.assertIsNotNone(m_new.intent)
        self.assertEqual(m_new.intent.topics, "Binary Trees")

        # 4. Verifikasi navigasi dua arah dari StudyIntent ke SessionMember
        self.db.refresh(self.intent_citra)
        member_ids = [mem.member_id for mem in self.intent_citra.session_members]
        self.assertIn(m_new.member_id, member_ids)

    def _create_legacy_day13_engine(self):
        """Membuat engine SQLite in-memory dengan skema legacy Day 13 (tanpa proposal_id, intent_id, dan unique indexes Day 20/21)."""
        legacy_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        with legacy_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE students (
                    student_id VARCHAR(36) PRIMARY KEY,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    student_number VARCHAR(20) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    verification_status VARCHAR(20) DEFAULT 'UNVERIFIED',
                    account_status VARCHAR(20) DEFAULT 'ACTIVE',
                    is_discoverable BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE courses (
                    course_id VARCHAR(36) PRIMARY KEY,
                    course_code VARCHAR(20) NOT NULL,
                    course_name VARCHAR(100) NOT NULL,
                    study_program VARCHAR(50) NOT NULL
                );
            """))
            conn.execute(text("""
                CREATE TABLE study_intents (
                    intent_id VARCHAR(36) PRIMARY KEY,
                    student_id VARCHAR(36) NOT NULL,
                    course_id VARCHAR(36) NOT NULL,
                    topics TEXT NOT NULL,
                    learning_goal VARCHAR(50) DEFAULT 'UNDERSTAND',
                    collaboration_style VARCHAR(50) DEFAULT 'DISCUSSION',
                    learning_mode VARCHAR(20) DEFAULT 'OFFLINE',
                    earliest_date VARCHAR(20) NOT NULL,
                    latest_date VARCHAR(20) NOT NULL,
                    min_group_size INTEGER DEFAULT 2,
                    max_group_size INTEGER DEFAULT 4,
                    status VARCHAR(20) DEFAULT 'ACTIVE',
                    created_at TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE study_sessions (
                    session_id VARCHAR(36) PRIMARY KEY,
                    host_id VARCHAR(36) NOT NULL,
                    course_id VARCHAR(36) NOT NULL,
                    title VARCHAR(150) NOT NULL,
                    description TEXT,
                    learning_goal VARCHAR(50) DEFAULT 'UNDERSTAND',
                    collaboration_style VARCHAR(50) DEFAULT 'DISCUSSION',
                    learning_mode VARCHAR(20) DEFAULT 'OFFLINE',
                    location VARCHAR(100),
                    min_group_size INTEGER DEFAULT 2,
                    max_group_size INTEGER DEFAULT 4,
                    status VARCHAR(30) DEFAULT 'DRAFT',
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE session_members (
                    member_id VARCHAR(36) PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL,
                    student_id VARCHAR(36) NOT NULL,
                    role VARCHAR(20) DEFAULT 'MEMBER',
                    status VARCHAR(20) DEFAULT 'INVITED',
                    joined_at TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE invitations (
                    invitation_id VARCHAR(36) PRIMARY KEY,
                    invitation_type VARCHAR(30) NOT NULL,
                    sender_id VARCHAR(36) NOT NULL,
                    recipient_id VARCHAR(36) NOT NULL,
                    session_id VARCHAR(36),
                    target_intent_id VARCHAR(36),
                    status VARCHAR(20) DEFAULT 'PENDING',
                    message TEXT,
                    created_at TIMESTAMP,
                    responded_at TIMESTAMP
                );
            """))
            conn.commit()
        return legacy_engine

    def test_13_sqlite_legacy_migration_day21(self):
        """Day 21.1.1 (P1): Verifikasi migrasi legacy (kolom, metadata indeks, enforcement) dan idempotensi berulang."""
        from app.database import _inspect_sqlite_index

        legacy_engine = self._create_legacy_day13_engine()
        try:
            # 1. Jalankan auto-migrasi pertama kali pada legacy engine
            ensure_database_schema(legacy_engine)

            with legacy_engine.connect() as conn:
                # Verifikasi kolom terbentuk
                cols_sess = [row[1] for row in conn.execute(text("PRAGMA table_info(study_sessions)")).fetchall()]
                self.assertIn("proposal_id", cols_sess)

                cols_mem = [row[1] for row in conn.execute(text("PRAGMA table_info(session_members)")).fetchall()]
                self.assertIn("intent_id", cols_mem)

                # Verifikasi metadata lengkap seluruh 4 unique index melalui PRAGMA index_list/index_info/sqlite_master
                meta_sess_prop = _inspect_sqlite_index(conn, "study_sessions", "uq_session_proposal")
                self.assertIsNotNone(meta_sess_prop)
                self.assertTrue(meta_sess_prop["unique"])
                self.assertTrue(meta_sess_prop["partial"])
                self.assertEqual(meta_sess_prop["columns"], ["proposal_id"])
                self.assertIn("PROPOSAL_ID IS NOT NULL", meta_sess_prop["where_predicate"].upper())

                meta_mem_intent = _inspect_sqlite_index(conn, "session_members", "uq_session_member_intent")
                self.assertIsNotNone(meta_mem_intent)
                self.assertTrue(meta_mem_intent["unique"])
                self.assertTrue(meta_mem_intent["partial"])
                self.assertEqual(meta_mem_intent["columns"], ["intent_id"])
                self.assertIn("INTENT_ID IS NOT NULL", meta_mem_intent["where_predicate"].upper())

                meta_mem_student = _inspect_sqlite_index(conn, "session_members", "uq_session_member_student")
                self.assertIsNotNone(meta_mem_student)
                self.assertTrue(meta_mem_student["unique"])
                self.assertFalse(meta_mem_student["partial"])
                self.assertEqual(meta_mem_student["columns"], ["session_id", "student_id"])

                meta_inv_rec = _inspect_sqlite_index(conn, "invitations", "uq_proposal_recipient")
                self.assertIsNotNone(meta_inv_rec)
                self.assertTrue(meta_inv_rec["unique"])
                self.assertTrue(meta_inv_rec["partial"])
                self.assertEqual(meta_inv_rec["columns"], ["proposal_id", "recipient_id"])

                # Snapshot skema sebelum migrasi berulang
                schema_before = conn.execute(
                    text("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name")
                ).fetchall()

            # 2. Jalankan migrasi berulang (idempotensi): skema tidak boleh rusak atau berubah
            ensure_database_schema(legacy_engine)
            ensure_database_schema(legacy_engine)

            with legacy_engine.connect() as conn:
                schema_after = conn.execute(
                    text("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name")
                ).fetchall()
                self.assertEqual(schema_before, schema_after)

                # 3. Verifikasi enforcement aktual constraint pada DB hasil migrasi
                conn.execute(text(
                    "INSERT INTO study_sessions (session_id, host_id, course_id, title, proposal_id) "
                    "VALUES ('s1', 'u1', 'c1', 'T1', 'p1')"
                ))
                conn.commit()
                with self.assertRaises(IntegrityError):
                    conn.execute(text(
                        "INSERT INTO study_sessions (session_id, host_id, course_id, title, proposal_id) "
                        "VALUES ('s2', 'u1', 'c1', 'T2', 'p1')"
                    ))
                    conn.commit()
                conn.rollback()

                conn.execute(text(
                    "INSERT INTO session_members (member_id, session_id, student_id, intent_id, role, status) "
                    "VALUES ('m1', 's1', 'u1', 'i1', 'HOST', 'CONFIRMED')"
                ))
                conn.commit()
                # Duplikasi intent_id ditolak
                with self.assertRaises(IntegrityError):
                    conn.execute(text(
                        "INSERT INTO session_members (member_id, session_id, student_id, intent_id, role, status) "
                        "VALUES ('m2', 's2', 'u2', 'i1', 'MEMBER', 'CONFIRMED')"
                    ))
                    conn.commit()
                conn.rollback()
                # Duplikasi (session_id, student_id) ditolak
                with self.assertRaises(IntegrityError):
                    conn.execute(text(
                        "INSERT INTO session_members (member_id, session_id, student_id, intent_id, role, status) "
                        "VALUES ('m3', 's1', 'u1', 'i2', 'MEMBER', 'CONFIRMED')"
                    ))
                    conn.commit()
                conn.rollback()
        finally:
            legacy_engine.dispose()

    def test_14_service_populates_intent_id_on_host_and_members(self):
        """Memverifikasi eksekusi proposal via API mengisi intent_id pada host dan anggota di response maupun DB."""
        proposal, _, _ = self._setup_ready_proposal("READY_FOR_SESSION")

        r_exec = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r_exec.status_code, 201)
        data = r_exec.json()

        # Verifikasi response members memiliki intent_id yang tepat
        members = data["members"]
        self.assertEqual(len(members), 3)

        host_mem = next(m for m in members if m["student_id"] == self.andi.student_id)
        self.assertEqual(host_mem["role"], "HOST")
        self.assertEqual(host_mem["status"], "CONFIRMED")
        self.assertEqual(host_mem["intent_id"], self.intent_andi.intent_id)

        budi_mem = next(m for m in members if m["student_id"] == self.budi.student_id)
        self.assertEqual(budi_mem["role"], "MEMBER")
        self.assertEqual(budi_mem["status"], "CONFIRMED")
        self.assertEqual(budi_mem["intent_id"], self.intent_budi.intent_id)

        citra_mem = next(m for m in members if m["student_id"] == self.citra.student_id)
        self.assertEqual(citra_mem["role"], "MEMBER")
        self.assertEqual(citra_mem["status"], "CONFIRMED")
        self.assertEqual(citra_mem["intent_id"], self.intent_citra.intent_id)

        # Verifikasi langsung pada data database
        db_members = self.db.query(SessionMember).filter(SessionMember.session_id == data["session_id"]).all()
        intent_map = {m.student_id: m.intent_id for m in db_members}
        self.assertEqual(intent_map[self.andi.student_id], self.intent_andi.intent_id)
        self.assertEqual(intent_map[self.budi.student_id], self.intent_budi.intent_id)
        self.assertEqual(intent_map[self.citra.student_id], self.intent_citra.intent_id)

    def test_15_migration_fails_closed_on_duplicate_data_in_legacy_db(self):
        """Day 21.1.1 (P1): Migrasi WAJIB gagal eksplisit (IntegrityError) bila database legacy berisi data duplikat."""
        # Skenario A: Duplikat proposal_id di study_sessions
        eng_a = self._create_legacy_day13_engine()
        try:
            with eng_a.connect() as conn:
                conn.execute(text("ALTER TABLE study_sessions ADD COLUMN proposal_id VARCHAR(36) REFERENCES group_proposals(proposal_id)"))
                conn.execute(text(
                    "INSERT INTO study_sessions (session_id, host_id, course_id, title, proposal_id) "
                    "VALUES ('s1', 'u1', 'c1', 'S1', 'prop_dup'), ('s2', 'u1', 'c1', 'S2', 'prop_dup')"
                ))
                conn.commit()
            with self.assertRaises(IntegrityError):
                ensure_database_schema(eng_a)
        finally:
            eng_a.dispose()

        # Skenario B: Duplikat intent_id di session_members
        eng_b = self._create_legacy_day13_engine()
        try:
            with eng_b.connect() as conn:
                conn.execute(text("ALTER TABLE session_members ADD COLUMN intent_id VARCHAR(36) REFERENCES study_intents(intent_id)"))
                conn.execute(text(
                    "INSERT INTO session_members (member_id, session_id, student_id, intent_id) "
                    "VALUES ('m1', 's1', 'u1', 'intent_dup'), ('m2', 's2', 'u2', 'intent_dup')"
                ))
                conn.commit()
            with self.assertRaises(IntegrityError):
                ensure_database_schema(eng_b)
        finally:
            eng_b.dispose()

        # Skenario C: Duplikat (session_id, student_id) di session_members
        eng_c = self._create_legacy_day13_engine()
        try:
            with eng_c.connect() as conn:
                conn.execute(text(
                    "INSERT INTO session_members (member_id, session_id, student_id) "
                    "VALUES ('m1', 's_same', 'u_same'), ('m2', 's_same', 'u_same')"
                ))
                conn.commit()
            with self.assertRaises(IntegrityError):
                ensure_database_schema(eng_c)
        finally:
            eng_c.dispose()

        # Skenario D: Duplikat (proposal_id, recipient_id) di invitations
        eng_d = self._create_legacy_day13_engine()
        try:
            with eng_d.connect() as conn:
                conn.execute(text("ALTER TABLE invitations ADD COLUMN proposal_id VARCHAR(36)"))
                conn.execute(text(
                    "INSERT INTO invitations (invitation_id, invitation_type, sender_id, recipient_id, proposal_id) "
                    "VALUES ('inv1', 'GROUP_PROPOSAL', 'h1', 'r_dup', 'p_dup'), "
                    "('inv2', 'GROUP_PROPOSAL', 'h1', 'r_dup', 'p_dup')"
                ))
                conn.commit()
            with self.assertRaises(IntegrityError):
                ensure_database_schema(eng_d)
        finally:
            eng_d.dispose()

    def test_16_migration_fails_closed_on_malformed_existing_index_definition(self):
        """Day 21.1.1 (P0): Migrasi WAJIB menolak indeks lama yang namanya sama tetapi definisinya salah (fail-closed)."""
        # Skenario A: Nama uq_session_member_intent ada, tapi BUKAN UNIQUE
        eng_a = self._create_legacy_day13_engine()
        try:
            with eng_a.connect() as conn:
                conn.execute(text("ALTER TABLE session_members ADD COLUMN intent_id VARCHAR(36) REFERENCES study_intents(intent_id)"))
                conn.execute(text(
                    "CREATE INDEX uq_session_member_intent ON session_members (intent_id) WHERE intent_id IS NOT NULL"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_a)
            self.assertIn("bukan UNIQUE index", str(ctx.exception))
        finally:
            eng_a.dispose()

        # Skenario B: Nama uq_session_member_intent ada dan UNIQUE, tapi TANPA partial WHERE intent_id IS NOT NULL
        eng_b = self._create_legacy_day13_engine()
        try:
            with eng_b.connect() as conn:
                conn.execute(text("ALTER TABLE session_members ADD COLUMN intent_id VARCHAR(36) REFERENCES study_intents(intent_id)"))
                conn.execute(text(
                    "CREATE UNIQUE INDEX uq_session_member_intent ON session_members (intent_id)"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_b)
            self.assertIn("partial index", str(ctx.exception))
        finally:
            eng_b.dispose()

        # Skenario C: Nama uq_session_member_student ada dan UNIQUE, tapi KOLOM SALAH
        eng_c = self._create_legacy_day13_engine()
        try:
            with eng_c.connect() as conn:
                conn.execute(text(
                    "CREATE UNIQUE INDEX uq_session_member_student ON session_members (student_id)"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_c)
            self.assertIn("Kolom indeks", str(ctx.exception))
        finally:
            eng_c.dispose()

        # Skenario D: Nama uq_session_proposal ada dan UNIQUE + partial, tapi PREDIKAT WHERE SALAH
        eng_d = self._create_legacy_day13_engine()
        try:
            with eng_d.connect() as conn:
                conn.execute(text("ALTER TABLE study_sessions ADD COLUMN proposal_id VARCHAR(36) REFERENCES group_proposals(proposal_id)"))
                conn.execute(text(
                    "CREATE UNIQUE INDEX uq_session_proposal ON study_sessions (proposal_id) WHERE host_id IS NOT NULL"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_d)
            self.assertIn("Predikat partial index", str(ctx.exception))
        finally:
            eng_d.dispose()

        # Skenario E: Nama uq_session_member_intent terpasang di tabel LAIN (menyebabkan CREATE INDEX IF NOT EXISTS no-op)
        eng_e = self._create_legacy_day13_engine()
        try:
            with eng_e.connect() as conn:
                conn.execute(text(
                    "CREATE UNIQUE INDEX uq_session_member_intent ON courses (course_code)"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_e)
            self.assertIn("tidak ditemukan pada tabel 'session_members'", str(ctx.exception))
        finally:
            eng_e.dispose()

    def test_17_migration_fails_closed_on_unexpected_index_operational_error(self):
        """Day 21.1.1 (P0): OperationalError saat CREATE UNIQUE INDEX (meski mengandung teks 'already exists') TIDAK boleh ditelan."""
        from unittest.mock import patch
        from sqlalchemy.engine import Connection
        from sqlalchemy.exc import OperationalError

        legacy_engine = self._create_legacy_day13_engine()
        orig_execute = Connection.execute
        intercepted = []

        def failing_index_execute(conn_self, statement, *args, **kwargs):
            sql_str = str(statement)
            if "CREATE UNIQUE INDEX IF NOT EXISTS uq_session_member_intent" in sql_str:
                intercepted.append(sql_str)
                # Simulasikan error yang bahkan mengandung kata 'already exists' agar memastikan tidak ada silent pass berbasis string
                raise OperationalError("simulated failure: index already exists / locked", None, None)
            return orig_execute(conn_self, statement, *args, **kwargs)

        try:
            with patch.object(Connection, "execute", new=failing_index_execute):
                with self.assertRaises(OperationalError):
                    ensure_database_schema(legacy_engine)
            self.assertEqual(len(intercepted), 1)
        finally:
            legacy_engine.dispose()

    def test_18_global_permanent_intent_uniqueness_across_completed_and_cancelled_sessions(self):
        """Day 21.1.1 (P2): Menegaskan kebijakan global permanen — StudyIntent tidak boleh digunakan ulang meski sesi sebelumnya COMPLETED/CANCELLED."""
        for terminal_status in ("COMPLETED", "CANCELLED"):
            with self.subTest(terminal_status=terminal_status):
                intent = StudyIntent(
                    intent_id=f"intent_perm_{terminal_status.lower()}",
                    student_id=self.doni.student_id,
                    course_id=self.course.course_id,
                    topics="Graph Theory",
                    learning_mode="ONLINE",
                    earliest_date="2026-11-20",
                    latest_date="2026-11-30",
                    min_group_size=2,
                    max_group_size=4,
                    status="MATCHED"
                )
                self.db.add(intent)

                sess_old = StudySession(
                    session_id=f"sess_old_{terminal_status.lower()}",
                    host_id=self.doni.student_id,
                    course_id=self.course.course_id,
                    title=f"Sesi Lama ({terminal_status})",
                    status=terminal_status
                )
                sess_new = StudySession(
                    session_id=f"sess_new_{terminal_status.lower()}",
                    host_id=self.andi.student_id,
                    course_id=self.course.course_id,
                    title=f"Sesi Baru ({terminal_status})",
                    status="CONFIRMED"
                )
                self.db.add_all([sess_old, sess_new])
                self.db.commit()

                # Keanggotaan pertama pada sesi lama (COMPLETED / CANCELLED)
                m_old = SessionMember(
                    member_id=f"m_old_{terminal_status.lower()}",
                    session_id=sess_old.session_id,
                    student_id=self.doni.student_id,
                    intent_id=intent.intent_id,
                    role="HOST",
                    status="CONFIRMED"
                )
                self.db.add(m_old)
                self.db.commit()

                # Percobaan penggunaan ulang intent yang sama pada sesi baru WAJIB ditolak oleh uq_session_member_intent
                m_reuse = SessionMember(
                    member_id=f"m_reuse_{terminal_status.lower()}",
                    session_id=sess_new.session_id,
                    student_id=self.doni.student_id,
                    intent_id=intent.intent_id,
                    role="MEMBER",
                    status="CONFIRMED"
                )
                self.db.add(m_reuse)
                with self.assertRaises(IntegrityError):
                    self.db.commit()
                self.db.rollback()

    def _enable_fk_pragma(self, engine):
        """Mengaktifkan PRAGMA foreign_keys=ON pada engine SQLite uji agar penegakan FK diverifikasi nyata."""
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_fk(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    def _create_day21_1_upgraded_engine(self, with_fk_pragma: bool = False):
        """
        Mensimulasikan database nyata hasil upgrade Day 21.1 (commit d6eb1b8):
        - study_sessions.proposal_id sudah ada dengan FK REFERENCES group_proposals(proposal_id) (NO ACTION)
        - session_members.intent_id sudah ada dengan FK REFERENCES study_intents(intent_id) (NO ACTION)
        - session_members memiliki UniqueConstraint(session_id, student_id) bawaan tabel (sqlite_autoindex)
        - Belum memiliki immutability triggers Day 21.1.2.
        """
        eng = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        if with_fk_pragma:
            self._enable_fk_pragma(eng)

        with eng.connect() as conn:
            conn.execute(text("""
                CREATE TABLE students (
                    student_id VARCHAR(36) PRIMARY KEY,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    student_number VARCHAR(20) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    verification_status VARCHAR(20) DEFAULT 'VERIFIED',
                    account_status VARCHAR(20) DEFAULT 'ACTIVE',
                    is_discoverable BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE courses (
                    course_id VARCHAR(36) PRIMARY KEY,
                    course_code VARCHAR(20) NOT NULL,
                    course_name VARCHAR(100) NOT NULL,
                    study_program VARCHAR(50) NOT NULL
                );
            """))
            conn.execute(text("""
                CREATE TABLE study_intents (
                    intent_id VARCHAR(36) PRIMARY KEY,
                    student_id VARCHAR(36) NOT NULL,
                    course_id VARCHAR(36) NOT NULL,
                    topics TEXT NOT NULL,
                    learning_goal VARCHAR(50) DEFAULT 'UNDERSTAND',
                    collaboration_style VARCHAR(50) DEFAULT 'DISCUSSION',
                    learning_mode VARCHAR(20) DEFAULT 'OFFLINE',
                    earliest_date VARCHAR(20) NOT NULL,
                    latest_date VARCHAR(20) NOT NULL,
                    min_group_size INTEGER DEFAULT 2,
                    max_group_size INTEGER DEFAULT 4,
                    status VARCHAR(20) DEFAULT 'ACTIVE',
                    created_at TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE group_proposals (
                    proposal_id VARCHAR(36) PRIMARY KEY,
                    host_intent_id VARCHAR(36) NOT NULL,
                    host_student_id VARCHAR(36) NOT NULL,
                    course_id VARCHAR(36) NOT NULL,
                    status VARCHAR(32) DEFAULT 'PENDING_RESPONSES',
                    min_group_size_bound INTEGER DEFAULT 2,
                    max_group_size_bound INTEGER DEFAULT 4,
                    group_quality_score FLOAT DEFAULT 0.0,
                    average_pair_score FLOAT DEFAULT 0.0,
                    minimum_pair_score FLOAT DEFAULT 0.0,
                    selected_schedule_json TEXT,
                    proposal_snapshot_json TEXT,
                    message TEXT,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    finalized_at TIMESTAMP
                );
            """))
            # study_sessions hasil migrasi Day 21.1 (FK tanpa ON DELETE eksplisit -> NO ACTION)
            conn.execute(text("""
                CREATE TABLE study_sessions (
                    session_id VARCHAR(36) PRIMARY KEY,
                    host_id VARCHAR(36) NOT NULL,
                    course_id VARCHAR(36) NOT NULL,
                    title VARCHAR(150) NOT NULL,
                    status VARCHAR(30) DEFAULT 'CONFIRMED',
                    proposal_id VARCHAR(36) REFERENCES group_proposals(proposal_id)
                );
            """))
            conn.execute(text(
                "CREATE UNIQUE INDEX uq_session_proposal ON study_sessions (proposal_id) WHERE proposal_id IS NOT NULL"
            ))
            # session_members hasil Day 21.1 (FK NO ACTION + table-level UniqueConstraint -> sqlite_autoindex)
            conn.execute(text("""
                CREATE TABLE session_members (
                    member_id VARCHAR(36) PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL REFERENCES study_sessions(session_id) ON DELETE CASCADE,
                    student_id VARCHAR(36) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
                    intent_id VARCHAR(36) REFERENCES study_intents(intent_id),
                    role VARCHAR(20) DEFAULT 'MEMBER',
                    status VARCHAR(20) DEFAULT 'CONFIRMED',
                    joined_at TIMESTAMP,
                    CONSTRAINT uq_session_member_student UNIQUE (session_id, student_id)
                );
            """))
            conn.execute(text(
                "CREATE UNIQUE INDEX uq_session_member_intent ON session_members (intent_id) WHERE intent_id IS NOT NULL"
            ))
            conn.commit()
        return eng

    def test_19_fk_migration_convergence_all_schema_variants(self):
        """Day 21.1.2 (P1): Verifikasi konvergensi FK PRAGMA foreign_key_list dan penegakan aktual di semua varian skema."""
        from app.database import _inspect_sqlite_foreign_keys

        # --- Varian A: Database Baru (Fresh DB) -> ON DELETE RESTRICT + blokir delete parent ---
        eng_fresh = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self._enable_fk_pragma(eng_fresh)
        try:
            ensure_database_schema(eng_fresh)
            with eng_fresh.connect() as conn:
                fk_prop = _inspect_sqlite_foreign_keys(conn, "study_sessions", "proposal_id")
                self.assertEqual(len(fk_prop), 1)
                self.assertEqual(fk_prop[0]["ref_table"], "group_proposals")
                self.assertEqual(fk_prop[0]["ref_column"], "proposal_id")
                self.assertEqual(fk_prop[0]["on_delete"], "RESTRICT")

                fk_intent = _inspect_sqlite_foreign_keys(conn, "session_members", "intent_id")
                self.assertEqual(len(fk_intent), 1)
                self.assertEqual(fk_intent[0]["ref_table"], "study_intents")
                self.assertEqual(fk_intent[0]["ref_column"], "intent_id")
                self.assertEqual(fk_intent[0]["on_delete"], "RESTRICT")
        finally:
            eng_fresh.dispose()

        # --- Varian B: Database Legacy Day 13 -> migrasi menambah FK ON DELETE RESTRICT ---
        eng_d13 = self._create_legacy_day13_engine()
        try:
            ensure_database_schema(eng_d13)
            with eng_d13.connect() as conn:
                fk_prop = _inspect_sqlite_foreign_keys(conn, "study_sessions", "proposal_id")
                self.assertEqual(fk_prop[0]["on_delete"], "RESTRICT")
                fk_intent = _inspect_sqlite_foreign_keys(conn, "session_members", "intent_id")
                self.assertEqual(fk_intent[0]["on_delete"], "RESTRICT")
        finally:
            eng_d13.dispose()

        # --- Varian C: Database Upgrade Day 21.1 (NO ACTION) -> diterima kontrak + blokir delete parent nyata ---
        eng_d21_1 = self._create_day21_1_upgraded_engine(with_fk_pragma=True)
        try:
            ensure_database_schema(eng_d21_1)
            with eng_d21_1.connect() as conn:
                fk_prop = _inspect_sqlite_foreign_keys(conn, "study_sessions", "proposal_id")
                self.assertEqual(fk_prop[0]["ref_table"], "group_proposals")
                self.assertEqual(fk_prop[0]["on_delete"], "NO ACTION")

                fk_intent = _inspect_sqlite_foreign_keys(conn, "session_members", "intent_id")
                self.assertEqual(fk_intent[0]["ref_table"], "study_intents")
                self.assertEqual(fk_intent[0]["on_delete"], "NO ACTION")

                # Buktikan perilaku aktual: DELETE group_proposals dan study_intents yang direferensikan WAJIB ditolak
                conn.execute(text(
                    "INSERT INTO students (student_id, full_name, email, student_number, password_hash) "
                    "VALUES ('u1', 'Andi', 'a@t.ac.id', '123', 'pw')"
                ))
                conn.execute(text(
                    "INSERT INTO courses (course_id, course_code, course_name, study_program) "
                    "VALUES ('c1', 'CS1', 'Algo', 'TK')"
                ))
                conn.execute(text(
                    "INSERT INTO study_intents (intent_id, student_id, course_id, topics, earliest_date, latest_date) "
                    "VALUES ('i1', 'u1', 'c1', 'Trees', '2026-11-20', '2026-11-30')"
                ))
                conn.execute(text(
                    "INSERT INTO group_proposals (proposal_id, host_intent_id, host_student_id, course_id, expires_at) "
                    "VALUES ('p1', 'i1', 'u1', 'c1', '2026-11-25 10:00:00')"
                ))
                conn.execute(text(
                    "INSERT INTO study_sessions (session_id, host_id, course_id, title, proposal_id) "
                    "VALUES ('s1', 'u1', 'c1', 'Sesi 1', 'p1')"
                ))
                conn.execute(text(
                    "INSERT INTO session_members (member_id, session_id, student_id, intent_id, role, status) "
                    "VALUES ('m1', 's1', 'u1', 'i1', 'HOST', 'CONFIRMED')"
                ))
                conn.commit()

                # Penghapusan proposal yang direferensikan StudySession wajib ditolak FK NO ACTION
                with self.assertRaises(IntegrityError):
                    conn.execute(text("DELETE FROM group_proposals WHERE proposal_id = 'p1'"))
                    conn.commit()
                conn.rollback()

                # Penghapusan StudyIntent yang direferensikan SessionMember wajib ditolak FK NO ACTION
                with self.assertRaises(IntegrityError):
                    conn.execute(text("DELETE FROM study_intents WHERE intent_id = 'i1'"))
                    conn.commit()
                conn.rollback()
        finally:
            eng_d21_1.dispose()

        # --- Varian D: FK destruktif (SET NULL / CASCADE) -> WAJIB ditolak fail-closed ---
        eng_bad_act = self._create_legacy_day13_engine()
        try:
            with eng_bad_act.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE study_sessions ADD COLUMN proposal_id VARCHAR(36) "
                    "REFERENCES group_proposals(proposal_id) ON DELETE SET NULL"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_bad_act)
            self.assertIn("SET NULL", str(ctx.exception))
        finally:
            eng_bad_act.dispose()

        eng_bad_cascade = self._create_legacy_day13_engine()
        try:
            with eng_bad_cascade.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE session_members ADD COLUMN intent_id VARCHAR(36) "
                    "REFERENCES study_intents(intent_id) ON DELETE CASCADE"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_bad_cascade)
            self.assertIn("CASCADE", str(ctx.exception))
        finally:
            eng_bad_cascade.dispose()

        # --- Varian E: Kolom ada tetapi TANPA Foreign Key -> WAJIB ditolak fail-closed ---
        eng_no_fk = self._create_legacy_day13_engine()
        try:
            with eng_no_fk.connect() as conn:
                conn.execute(text("ALTER TABLE study_sessions ADD COLUMN proposal_id VARCHAR(36)"))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_no_fk)
            self.assertIn("tidak memiliki Foreign Key", str(ctx.exception))
        finally:
            eng_no_fk.dispose()

        # --- Varian F: Foreign Key menunjuk ke tabel/kolom SALAH -> WAJIB ditolak fail-closed ---
        eng_wrong_ref = self._create_legacy_day13_engine()
        try:
            with eng_wrong_ref.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE session_members ADD COLUMN intent_id VARCHAR(36) "
                    "REFERENCES courses(course_id) ON DELETE RESTRICT"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_wrong_ref)
            self.assertIn("tidak merujuk ke 'study_intents.intent_id'", str(ctx.exception))
        finally:
            eng_wrong_ref.dispose()

    def test_20_historical_allocation_immutability_protection(self):
        """Day 21.1.2 (P1): Membuktikan semua 6 skenario immutability histori alokasi StudyIntent (ORM & SQL)."""
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self._enable_fk_pragma(eng)
        ensure_database_schema(eng)
        LocalSession = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = LocalSession()

        try:
            course = Course(course_id="c_imm", course_code="CS901", course_name="OS", study_program="TK")
            s_host = Student(
                student_id="u_imm_host", full_name="Host", email="h@t.ac.id",
                student_number="1001", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE"
            )
            s_mem = Student(
                student_id="u_imm_mem", full_name="Member", email="m@t.ac.id",
                student_number="1002", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE"
            )
            intent_alloc = StudyIntent(
                intent_id="i_imm_alloc", student_id=s_host.student_id, course_id=course.course_id,
                topics="Deadlock", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-30",
                min_group_size=2, max_group_size=4, status="MATCHED"
            )
            intent_other = StudyIntent(
                intent_id="i_imm_other", student_id=s_mem.student_id, course_id=course.course_id,
                topics="Scheduling", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-30",
                min_group_size=2, max_group_size=4, status="ACTIVE"
            )
            sess_alloc = StudySession(
                session_id="sess_imm_alloc", host_id=s_host.student_id, course_id=course.course_id,
                title="Sesi Teralokasi", status="CONFIRMED"
            )
            sess_other = StudySession(
                session_id="sess_imm_other", host_id=s_mem.student_id, course_id=course.course_id,
                title="Sesi Lain", status="CONFIRMED"
            )
            db.add_all([course, s_host, s_mem, intent_alloc, intent_other, sess_alloc, sess_other])
            db.flush()

            m_allocated = SessionMember(
                member_id="m_imm_alloc", session_id=sess_alloc.session_id, student_id=s_host.student_id,
                intent_id=intent_alloc.intent_id, role="HOST", status="CONFIRMED"
            )
            m_legacy_null = SessionMember(
                member_id="m_imm_legacy", session_id=sess_alloc.session_id, student_id=s_mem.student_id,
                intent_id=None, role="MEMBER", status="CONFIRMED"
            )
            db.add_all([m_allocated, m_legacy_null])
            db.commit()

            # 1. Hapus SessionMember dengan intent_id terisi -> DITOLAK (ORM delete, delete-orphan, & raw SQL)
            db.delete(m_allocated)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            sess_alloc = db.query(StudySession).filter_by(session_id="sess_imm_alloc").first()
            m_allocated = db.query(SessionMember).filter_by(member_id="m_imm_alloc").first()
            sess_alloc.members.remove(m_allocated)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            with self.assertRaises(IntegrityError):
                db.execute(text("DELETE FROM session_members WHERE member_id = 'm_imm_alloc'"))
                db.commit()
            db.rollback()

            # 2. Hapus SessionMember legacy dengan intent_id=NULL -> DIIZINKAN (kompatibilitas Day 13)
            m_legacy = db.query(SessionMember).filter_by(member_id="m_imm_legacy").first()
            db.delete(m_legacy)
            db.commit()
            self.assertIsNone(db.query(SessionMember).filter_by(member_id="m_imm_legacy").first())

            # 3. Hapus StudySession yang memiliki histori alokasi -> DITOLAK (ORM cascade & raw SQL)
            sess_alloc = db.query(StudySession).filter_by(session_id="sess_imm_alloc").first()
            db.delete(sess_alloc)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            with self.assertRaises(IntegrityError):
                db.execute(text("DELETE FROM study_sessions WHERE session_id = 'sess_imm_alloc'"))
                db.commit()
            db.rollback()

            # Verifikasi histori alokasi tetap utuh di DB
            self.assertIsNotNone(db.query(StudySession).filter_by(session_id="sess_imm_alloc").first())
            self.assertIsNotNone(db.query(SessionMember).filter_by(member_id="m_imm_alloc").first())

            # 4. Hapus StudyIntent yang sudah dialokasikan -> DITOLAK (FK ON DELETE RESTRICT)
            intent_db = db.query(StudyIntent).filter_by(intent_id="i_imm_alloc").first()
            db.delete(intent_db)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 5. Ubah intent_id yang sudah dialokasikan (ganti nilai & kosongkan ke NULL) -> DITOLAK
            m_allocated = db.query(SessionMember).filter_by(member_id="m_imm_alloc").first()
            m_allocated.intent_id = "i_imm_other"
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            m_allocated = db.query(SessionMember).filter_by(member_id="m_imm_alloc").first()
            m_allocated.intent_id = None
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # Perubahan soft-status keanggotaan (tanpa mengubah intent_id) WAJIB tetap diizinkan
            m_allocated = db.query(SessionMember).filter_by(member_id="m_imm_alloc").first()
            m_allocated.status = "WITHDRAWN"
            db.commit()
            db.refresh(m_allocated)
            self.assertEqual(m_allocated.status, "WITHDRAWN")
            self.assertEqual(m_allocated.intent_id, "i_imm_alloc")

            # 6. Gunakan kembali intent yang sudah dialokasikan di sesi lain -> DITOLAK
            m_reuse = SessionMember(
                member_id="m_imm_reuse", session_id="sess_imm_other", student_id=s_host.student_id,
                intent_id="i_imm_alloc", role="MEMBER", status="CONFIRMED"
            )
            db.add(m_reuse)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
            eng.dispose()

    def test_21_migration_fails_closed_on_tampered_immutability_trigger(self):
        """Day 21.1.2 (P1): Migrasi WAJIB menolak trigger immutability yang definisinya telah dimodifikasi/no-op."""
        eng = self._create_legacy_day13_engine()
        try:
            with eng.connect() as conn:
                conn.execute(text(
                    "CREATE TRIGGER trg_session_members_prevent_allocated_delete "
                    "BEFORE DELETE ON session_members BEGIN SELECT 1; END;"
                ))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng)
            self.assertIn("Definisi trigger 'trg_session_members_prevent_allocated_delete' tidak sesuai kontrak", str(ctx.exception))
        finally:
            eng.dispose()

    def test_22_legacy_index_redundancy_catalog_audit(self):
        """Day 21.1.2 (P2): Audit katalog redundansi indeks pada DB baru, hasil migrasi Day 13, dan upgrade Day 21.1."""
        from app.database import inspect_sqlite_unique_index_redundancy

        # 1. Database Baru: ZERO redundansi pada session_members
        eng_fresh = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        try:
            ensure_database_schema(eng_fresh)
            with eng_fresh.connect() as conn:
                self.assertEqual(inspect_sqlite_unique_index_redundancy(conn, "session_members"), [])
                self.assertEqual(inspect_sqlite_unique_index_redundancy(conn, "study_sessions"), [])
        finally:
            eng_fresh.dispose()

        # 2. Database hasil migrasi Day 13: ZERO redundansi pada session_members
        eng_d13 = self._create_legacy_day13_engine()
        try:
            ensure_database_schema(eng_d13)
            with eng_d13.connect() as conn:
                self.assertEqual(inspect_sqlite_unique_index_redundancy(conn, "session_members"), [])
                self.assertEqual(inspect_sqlite_unique_index_redundancy(conn, "study_sessions"), [])
        finally:
            eng_d13.dispose()

        # 3. Database hasil upgrade Day 21.1: mendeteksi redundansi sqlite_autoindex + named index tanpa rebuild destruktif
        eng_d21_1 = self._create_day21_1_upgraded_engine()
        try:
            ensure_database_schema(eng_d21_1)
            with eng_d21_1.connect() as conn:
                red = inspect_sqlite_unique_index_redundancy(conn, "session_members")
                self.assertEqual(len(red), 1)
                self.assertEqual(red[0]["columns"], ["session_id", "student_id"])
                idx_names = {item["name"] for item in red[0]["indexes"]}
                self.assertIn("uq_session_member_student", idx_names)
                self.assertTrue(any(name.startswith("sqlite_autoindex_session_members_") for name in idx_names))
        finally:
            eng_d21_1.dispose()


if __name__ == "__main__":
    unittest.main()
