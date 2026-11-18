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

    def test_23_fk_validator_enforces_exact_cardinality_and_on_update_contract(self):
        """Day 21.1.2 Hardening: FK validator wajib menegakkan exact cardinality = 1, non-composite, dan kontrak ON UPDATE."""
        # Skenario A: 2 FK pada kolom yang sama (1 valid + 1 tambahan dengan target berbeda) -> DITOLAK
        eng_multi = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        try:
            with eng_multi.connect() as conn:
                conn.execute(text("CREATE TABLE group_proposals (proposal_id VARCHAR(36) PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE courses (course_id VARCHAR(36) PRIMARY KEY)"))
                conn.execute(text("""
                    CREATE TABLE study_sessions (
                        session_id VARCHAR(36) PRIMARY KEY,
                        host_id VARCHAR(36) NOT NULL,
                        course_id VARCHAR(36) NOT NULL,
                        title VARCHAR(150) NOT NULL,
                        proposal_id VARCHAR(36),
                        FOREIGN KEY (proposal_id) REFERENCES group_proposals(proposal_id) ON DELETE RESTRICT,
                        FOREIGN KEY (proposal_id) REFERENCES courses(course_id) ON DELETE CASCADE
                    );
                """))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_multi)
            self.assertIn("tepat 1 definisi Foreign Key", str(ctx.exception))
        finally:
            eng_multi.dispose()

        # Skenario B: FK dengan ON UPDATE CASCADE / SET NULL -> DITOLAK
        for bad_upd in ("CASCADE", "SET NULL"):
            with self.subTest(bad_on_update=bad_upd):
                eng_upd = self._create_legacy_day13_engine()
                try:
                    with eng_upd.connect() as conn:
                        conn.execute(text(
                            f"ALTER TABLE session_members ADD COLUMN intent_id VARCHAR(36) "
                            f"REFERENCES study_intents(intent_id) ON DELETE RESTRICT ON UPDATE {bad_upd}"
                        ))
                        conn.commit()
                    with self.assertRaises(RuntimeError) as ctx:
                        ensure_database_schema(eng_upd)
                    self.assertIn("ON UPDATE", str(ctx.exception))
                finally:
                    eng_upd.dispose()

        # Skenario C: Composite FK melibatkan proposal_id -> DITOLAK
        eng_comp = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        try:
            with eng_comp.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE group_proposals (
                        proposal_id VARCHAR(36) PRIMARY KEY,
                        course_id VARCHAR(36)
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE study_sessions (
                        session_id VARCHAR(36) PRIMARY KEY,
                        host_id VARCHAR(36) NOT NULL,
                        course_id VARCHAR(36) NOT NULL,
                        title VARCHAR(150) NOT NULL,
                        proposal_id VARCHAR(36),
                        FOREIGN KEY (proposal_id, course_id) REFERENCES group_proposals(proposal_id, course_id) ON DELETE RESTRICT
                    );
                """))
                conn.commit()
            with self.assertRaises(RuntimeError) as ctx:
                ensure_database_schema(eng_comp)
            self.assertIn("composite FK", str(ctx.exception))
        finally:
            eng_comp.dispose()


class TestDay21SessionExecutionAtomicity(unittest.TestCase):
    """
    Day 21.2 — Session Execution Transaction & Atomicity Acceptance Test Suite.
    Membuktikan D21.2-01 s/d D21.2-06 melalui failure injection nyata pada lapisan
    database/transaksi serta inspeksi langsung database menggunakan sesi DB independen.
    """

    def setUp(self):
        from sqlalchemy import event

        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )

        @event.listens_for(self.engine, "connect")
        def _set_fk(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        ensure_database_schema(self.engine)
        self.TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.TestingSession()
        self.original_overrides = dict(app.dependency_overrides)

        def override_get_db():
            session = self.TestingSession()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app, raise_server_exceptions=False)

        self.course = Course(
            course_id="c_d212_algo",
            course_code="ACK2AAB4",
            course_name="Algoritma Lanjut",
            study_program="S1 Teknik Komputer"
        )
        self.andi = Student(
            student_id="s_andi_d212",
            full_name="Andi Atomik",
            email="andi.d212@telkomuniversity.ac.id",
            student_number="1201250201",
            password_hash="hashed_pw",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.budi = Student(
            student_id="s_budi_d212",
            full_name="Budi Atomik",
            email="budi.d212@telkomuniversity.ac.id",
            student_number="1201250202",
            password_hash="hashed_pw",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.citra = Student(
            student_id="s_citra_d212",
            full_name="Citra Atomik",
            email="citra.d212@telkomuniversity.ac.id",
            student_number="1201250203",
            password_hash="hashed_pw",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.intent_andi = StudyIntent(
            intent_id="intent_andi_d212",
            student_id=self.andi.student_id,
            course_id=self.course.course_id,
            topics="Dynamic Programming, Graph",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            min_group_size=3,
            max_group_size=4,
            status="ACTIVE"
        )
        self.intent_budi = StudyIntent(
            intent_id="intent_budi_d212",
            student_id=self.budi.student_id,
            course_id=self.course.course_id,
            topics="Dynamic Programming",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            min_group_size=3,
            max_group_size=4,
            status="ACTIVE"
        )
        self.intent_citra = StudyIntent(
            intent_id="intent_citra_d212",
            student_id=self.citra.student_id,
            course_id=self.course.course_id,
            topics="Graph",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            min_group_size=3,
            max_group_size=4,
            status="ACTIVE"
        )
        self.db.add_all([
            self.course, self.andi, self.budi, self.citra,
            self.intent_andi, self.intent_budi, self.intent_citra
        ])
        self.db.commit()
        self.token_andi = create_token(self.andi.student_id, self.andi.email)

    def tearDown(self):
        app.dependency_overrides = self.original_overrides
        self.db.close()
        self.engine.dispose()

    def _create_ready_proposal(self, proposal_id: str, expires_delta_hours: int = 24) -> GroupProposal:
        sched = {
            "date": "2026-11-24",
            "start_time": "10:00",
            "end_time": "12:00",
            "duration_minutes": 120
        }
        proposal = GroupProposal(
            proposal_id=proposal_id,
            host_intent_id=self.intent_andi.intent_id,
            host_student_id=self.andi.student_id,
            course_id=self.course.course_id,
            status="READY_FOR_SESSION",
            min_group_size_bound=3,
            max_group_size_bound=4,
            group_quality_score=91.0,
            average_pair_score=92.0,
            minimum_pair_score=89.0,
            selected_schedule_json=json.dumps(sched),
            message="Sesi Atomicity Test",
            expires_at=datetime.utcnow() + timedelta(hours=expires_delta_hours),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            finalized_at=datetime.utcnow()
        )
        inv_budi = Invitation(
            invitation_id=f"inv_budi_{proposal_id}",
            invitation_type="GROUP_PROPOSAL",
            sender_id=self.andi.student_id,
            recipient_id=self.budi.student_id,
            target_intent_id=self.intent_budi.intent_id,
            proposal_id=proposal_id,
            status="ACCEPTED",
            created_at=datetime.utcnow(),
            responded_at=datetime.utcnow()
        )
        inv_citra = Invitation(
            invitation_id=f"inv_citra_{proposal_id}",
            invitation_type="GROUP_PROPOSAL",
            sender_id=self.andi.student_id,
            recipient_id=self.citra.student_id,
            target_intent_id=self.intent_citra.intent_id,
            proposal_id=proposal_id,
            status="ACCEPTED",
            created_at=datetime.utcnow(),
            responded_at=datetime.utcnow()
        )
        self.db.add_all([proposal, inv_budi, inv_citra])
        self.db.commit()
        return proposal

    def _assert_full_rollback_in_fresh_db_session(self, proposal_id: str):
        """Memeriksa kondisi database langsung dari sesi baru bahwa TIDAK ADA satu pun perubahan parsial tersisa."""
        verify_db = self.TestingSession()
        try:
            self.assertEqual(verify_db.query(StudySession).count(), 0, "StudySession tidak boleh tersisa pasca-rollback")
            self.assertEqual(verify_db.query(SessionSlot).count(), 0, "SessionSlot tidak boleh tersisa pasca-rollback")
            self.assertEqual(verify_db.query(SessionMember).count(), 0, "SessionMember tidak boleh tersisa pasca-rollback")

            for iid in (self.intent_andi.intent_id, self.intent_budi.intent_id, self.intent_citra.intent_id):
                intent_row = verify_db.query(StudyIntent).filter_by(intent_id=iid).first()
                self.assertEqual(intent_row.status, "ACTIVE", f"StudyIntent {iid} wajib tetap ACTIVE pasca-rollback")

            prop_row = verify_db.query(GroupProposal).filter_by(proposal_id=proposal_id).first()
            self.assertEqual(prop_row.status, "READY_FOR_SESSION", "GroupProposal wajib tetap READY_FOR_SESSION pasca-rollback")
        finally:
            verify_db.close()

    def test_d21_2_01_successful_execution_single_transaction_boundary(self):
        """D21.2-01: Eksekusi normal menyimpan seluruh entitas & status dalam tepat 1 commit transaksi, dan jalur EXPIRED terisolasi."""
        from sqlalchemy import event

        proposal = self._create_ready_proposal("prop_d212_01")
        commit_count = []

        @event.listens_for(self.TestingSession, "after_commit")
        def _count_commit(_session):
            commit_count.append(1)

        try:
            r = self.client.post(
                f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
                headers={"Authorization": f"Bearer {self.token_andi}"}
            )
        finally:
            event.remove(self.TestingSession, "after_commit", _count_commit)

        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(commit_count), 1, "Eksekusi sesi wajib terjadi dalam tepat 1 database commit")
        session_id = r.json()["session_id"]

        # Inspeksi database langsung melalui sesi independen
        verify_db = self.TestingSession()
        try:
            sessions = verify_db.query(StudySession).all()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].session_id, session_id)
            self.assertEqual(sessions[0].proposal_id, proposal.proposal_id)
            self.assertEqual(sessions[0].status, "CONFIRMED")

            slots = verify_db.query(SessionSlot).filter_by(session_id=session_id).all()
            self.assertEqual(len(slots), 1)
            self.assertEqual(slots[0].status, "APPROVED")
            self.assertEqual(slots[0].session_date, "2026-11-24")
            self.assertEqual(slots[0].start_time, "10:00")
            self.assertEqual(slots[0].end_time, "12:00")

            members = verify_db.query(SessionMember).filter_by(session_id=session_id).all()
            self.assertEqual(len(members), 3)
            role_by_student = {m.student_id: (m.role, m.status, m.intent_id) for m in members}
            self.assertEqual(role_by_student[self.andi.student_id], ("HOST", "CONFIRMED", self.intent_andi.intent_id))
            self.assertEqual(role_by_student[self.budi.student_id], ("MEMBER", "CONFIRMED", self.intent_budi.intent_id))
            self.assertEqual(role_by_student[self.citra.student_id], ("MEMBER", "CONFIRMED", self.intent_citra.intent_id))

            for iid in (self.intent_andi.intent_id, self.intent_budi.intent_id, self.intent_citra.intent_id):
                self.assertEqual(verify_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "MATCHED")

            self.assertEqual(
                verify_db.query(GroupProposal).filter_by(proposal_id=proposal.proposal_id).first().status,
                "SESSION_EXECUTED"
            )
        finally:
            verify_db.close()

    def test_d21_2_01b_expired_proposal_business_path_leaves_zero_session_artifacts(self):
        """D21.2.1: Transisi bisnis EXPIRED terpisah dari pembuatan sesi dan tidak membuat StudySession/Slot/Member."""
        proposal = self._create_ready_proposal("prop_d212_expired", expires_delta_hours=-2)

        r = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)

        verify_db = self.TestingSession()
        try:
            self.assertEqual(verify_db.query(StudySession).count(), 0)
            self.assertEqual(verify_db.query(SessionSlot).count(), 0)
            self.assertEqual(verify_db.query(SessionMember).count(), 0)
            self.assertEqual(
                verify_db.query(GroupProposal).filter_by(proposal_id=proposal.proposal_id).first().status,
                "EXPIRED"
            )
            for iid in (self.intent_andi.intent_id, self.intent_budi.intent_id, self.intent_citra.intent_id):
                self.assertEqual(verify_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "ACTIVE")
        finally:
            verify_db.close()

    def test_d21_2_02_session_slot_failure_after_session_flush_full_rollback(self):
        """D21.2-02: Kegagalan INSERT SessionSlot setelah StudySession di-flush wajib membatalkan seluruh transaksi."""
        from sqlalchemy import event

        proposal = self._create_ready_proposal("prop_d212_02")
        executed_statements = []

        @event.listens_for(self.engine, "before_cursor_execute")
        def _record_sql(_conn, _cursor, statement, _params, _ctx, _execmany):
            executed_statements.append(statement)

        # Suntikkan kegagalan nyata di level SQLite tepat pada INSERT session_slots
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TRIGGER trg_fault_slot_insert
                BEFORE INSERT ON session_slots
                BEGIN
                    SELECT RAISE(ABORT, 'Simulated SessionSlot DB failure');
                END;
            """))
            conn.commit()

        try:
            r = self.client.post(
                f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
                headers={"Authorization": f"Bearer {self.token_andi}"}
            )
            self.assertIn(r.status_code, (409, 500))
        finally:
            event.remove(self.engine, "before_cursor_execute", _record_sql)
            with self.engine.connect() as conn:
                conn.execute(text("DROP TRIGGER IF EXISTS trg_fault_slot_insert"))
                conn.commit()

        # Pastikan INSERT study_sessions memang sempat di-flush ke SQLite sebelum kegagalan slot
        self.assertTrue(
            any("INSERT INTO study_sessions" in sql for sql in executed_statements),
            "StudySession harus benar-benar di-flush terlebih dahulu untuk membuktikan rollback nyata"
        )
        self._assert_full_rollback_in_fresh_db_session(proposal.proposal_id)

    def test_d21_2_03_session_member_failure_partial_insert_full_rollback(self):
        """D21.2-03: Kegagalan pada anggota ke-3 (Citra) setelah StudySession, Slot, Host & Budi masuk wajib rollback penuh."""
        from sqlalchemy import event

        proposal = self._create_ready_proposal("prop_d212_03")
        member_inserts = []

        @event.listens_for(self.engine, "before_cursor_execute")
        def _record_member_sql(_conn, _cursor, statement, _params, _ctx, _execmany):
            if "INSERT INTO session_members" in statement:
                member_inserts.append(statement)

        # Suntikkan kegagalan nyata di level SQLite hanya pada anggota Citra (setelah Host & Budi berhasil di-insert)
        with self.engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TRIGGER trg_fault_member_citra
                BEFORE INSERT ON session_members
                WHEN NEW.student_id = '{self.citra.student_id}'
                BEGIN
                    SELECT RAISE(ABORT, 'Simulated SessionMember failure on candidate Citra');
                END;
            """))
            conn.commit()

        try:
            r = self.client.post(
                f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
                headers={"Authorization": f"Bearer {self.token_andi}"}
            )
            self.assertIn(r.status_code, (409, 500))
        finally:
            event.remove(self.engine, "before_cursor_execute", _record_member_sql)
            with self.engine.connect() as conn:
                conn.execute(text("DROP TRIGGER IF EXISTS trg_fault_member_citra"))
                conn.commit()

        # Pastikan INSERT session_members benar-benar sudah dieksekusi sebelum gagal di Citra
        self.assertGreaterEqual(len(member_inserts), 1)
        self._assert_full_rollback_in_fresh_db_session(proposal.proposal_id)

    def test_d21_2_04_status_transition_failure_full_rollback(self):
        """D21.2-04: Kegagalan saat update status StudyIntent (host/anggota) maupun GroupProposal wajib rollback seluruh sesi."""
        fault_cases = [
            (
                "host_intent_update_failure",
                "trg_fault_upd_host_intent",
                f"""
                CREATE TRIGGER trg_fault_upd_host_intent
                BEFORE UPDATE OF status ON study_intents
                WHEN NEW.intent_id = '{self.intent_andi.intent_id}' AND NEW.status = 'MATCHED'
                BEGIN
                    SELECT RAISE(ABORT, 'Simulated failure updating host StudyIntent status');
                END;
                """
            ),
            (
                "candidate_intent_update_failure",
                "trg_fault_upd_cand_intent",
                f"""
                CREATE TRIGGER trg_fault_upd_cand_intent
                BEFORE UPDATE OF status ON study_intents
                WHEN NEW.intent_id = '{self.intent_citra.intent_id}' AND NEW.status = 'MATCHED'
                BEGIN
                    SELECT RAISE(ABORT, 'Simulated failure updating candidate StudyIntent status');
                END;
                """
            ),
            (
                "proposal_status_update_failure",
                "trg_fault_upd_proposal",
                """
                CREATE TRIGGER trg_fault_upd_proposal
                BEFORE UPDATE OF status ON group_proposals
                WHEN NEW.status = 'SESSION_EXECUTED'
                BEGIN
                    SELECT RAISE(ABORT, 'Simulated failure updating GroupProposal status');
                END;
                """
            ),
        ]

        for idx, (label, trg_name, trg_sql) in enumerate(fault_cases):
            with self.subTest(fault_case=label):
                proposal = self._create_ready_proposal(f"prop_d212_04_{idx}")
                with self.engine.connect() as conn:
                    conn.execute(text(trg_sql))
                    conn.commit()
                try:
                    r = self.client.post(
                        f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
                        headers={"Authorization": f"Bearer {self.token_andi}"}
                    )
                    self.assertIn(r.status_code, (409, 500))
                finally:
                    with self.engine.connect() as conn:
                        conn.execute(text(f"DROP TRIGGER IF EXISTS {trg_name}"))
                        conn.commit()

                self._assert_full_rollback_in_fresh_db_session(proposal.proposal_id)

    def test_d21_2_05_commit_failure_boundary_pre_vs_post_commit(self):
        """D21.2-05: Membedakan kegagalan PRA-COMMIT (full rollback) vs PASCA-COMMIT (data committed & retry aman)."""
        from unittest.mock import patch
        from sqlalchemy.orm import Session as SASession
        from sqlalchemy.exc import OperationalError
        import app.session_execution_service as svc_mod

        # --- Skenario A: Kegagalan tepat sebelum commit DB sungguhan (pre-commit boundary) ---
        prop_pre = self._create_ready_proposal("prop_d212_05_pre")
        orig_commit = SASession.commit

        def failing_pre_commit(sess_self):
            # Flush semua SQL terlebih dahulu ke transaksi terbuka, lalu gagal SEBELUM commit nyata
            sess_self.flush()
            raise OperationalError("simulated disk I/O failure at commit boundary", None, None)

        with patch.object(SASession, "commit", new=failing_pre_commit):
            r_pre = self.client.post(
                f"/api/v1/group-proposals/{prop_pre.proposal_id}/execute-session",
                headers={"Authorization": f"Bearer {self.token_andi}"}
            )
        self.assertEqual(r_pre.status_code, 500)
        self._assert_full_rollback_in_fresh_db_session(prop_pre.proposal_id)

        # --- Skenario B: Commit SUKSES di database, tetapi kegagalan terjadi pasca-commit saat membentuk/mengirim respons ---
        prop_post = self._create_ready_proposal("prop_d212_05_post")
        orig_formatter = svc_mod.format_study_session_response
        call_counter = {"count": 0}

        def fail_once_after_commit(session_obj, db_sess):
            call_counter["count"] += 1
            if call_counter["count"] == 1:
                raise RuntimeError("Simulated response delivery failure after DB commit")
            return orig_formatter(session_obj, db_sess)

        with patch.object(svc_mod, "format_study_session_response", side_effect=fail_once_after_commit):
            r_first = self.client.post(
                f"/api/v1/group-proposals/{prop_post.proposal_id}/execute-session",
                headers={"Authorization": f"Bearer {self.token_andi}"}
            )
            self.assertEqual(r_first.status_code, 500)

            # Verifikasi DB secara jujur: commit SUDAH terjadi dan TIDAK dianggap rollback
            verify_db = self.TestingSession()
            try:
                committed_sess = verify_db.query(StudySession).filter_by(proposal_id=prop_post.proposal_id).first()
                self.assertIsNotNone(committed_sess)
                committed_id = committed_sess.session_id
                self.assertEqual(verify_db.query(SessionSlot).filter_by(session_id=committed_id).count(), 1)
                self.assertEqual(verify_db.query(SessionMember).filter_by(session_id=committed_id).count(), 3)
                self.assertEqual(
                    verify_db.query(GroupProposal).filter_by(proposal_id=prop_post.proposal_id).first().status,
                    "SESSION_EXECUTED"
                )
            finally:
                verify_db.close()

            # Retry setelah kegagalan pengiriman respons: wajib mengembalikan session_id yang persis sama
            r_retry = self.client.post(
                f"/api/v1/group-proposals/{prop_post.proposal_id}/execute-session",
                headers={"Authorization": f"Bearer {self.token_andi}"}
            )
            self.assertEqual(r_retry.status_code, 201)
            self.assertEqual(r_retry.json()["session_id"], committed_id)

    def test_d21_2_06_retry_after_successful_execution_idempotent_and_db_backed(self):
        """D21.2-06: Retry pasca-sukses mengembalikan sesi identik tanpa duplikasi; invariant DB uq_session_proposal juga teruji."""
        proposal = self._create_ready_proposal("prop_d212_06")

        # 1. Eksekusi pertama berhasil commit (misal client kehilangan response)
        r1 = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r1.status_code, 201)
        first_session_id = r1.json()["session_id"]

        # 2. Client mengirim request ulang (retry normal)
        r2 = self.client.post(
            f"/api/v1/group-proposals/{proposal.proposal_id}/execute-session",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r2.json()["session_id"], first_session_id)

        # 3. Verifikasi langsung terhadap invariant database (uq_session_proposal) jika jalur service di-bypass
        verify_db = self.TestingSession()
        try:
            dup_sess = StudySession(
                session_id="sess_forced_dup",
                proposal_id=proposal.proposal_id,
                host_id=self.andi.student_id,
                course_id=self.course.course_id,
                title="Forced Duplicate Session",
                status="CONFIRMED"
            )
            verify_db.add(dup_sess)
            with self.assertRaises(IntegrityError):
                verify_db.commit()
            verify_db.rollback()

            # Periksa seluruh tabel wajib sesuai spesifikasi D21.2-06
            self.assertEqual(verify_db.query(StudySession).filter_by(proposal_id=proposal.proposal_id).count(), 1)
            self.assertEqual(verify_db.query(SessionSlot).filter_by(session_id=first_session_id).count(), 1)
            self.assertEqual(verify_db.query(SessionMember).filter_by(session_id=first_session_id).count(), 3)
            for iid in (self.intent_andi.intent_id, self.intent_budi.intent_id, self.intent_citra.intent_id):
                self.assertEqual(verify_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "MATCHED")
            self.assertEqual(
                verify_db.query(GroupProposal).filter_by(proposal_id=proposal.proposal_id).first().status,
                "SESSION_EXECUTED"
            )
        finally:
            verify_db.close()


class TestDay21SessionExecutionConcurrency(unittest.TestCase):
    """
    Day 21.3 — Concurrency & Race Condition Acceptance Test Suite.
    Menggunakan temporary file-backed SQLite dengan koneksi independen (NullPool),
    SQLAlchemy Session terpisah per worker thread, threading.Barrier deterministik,
    serta verifikasi database independen pasca-eksekusi dari engine/koneksi baru.
    """

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory(prefix="lafriend_day21_3_")
        self._db_counter = 0

    def tearDown(self):
        self._tmpdir.cleanup()

    def _create_file_sqlite_engine(self, journal_mode: str = "WAL"):
        """Membuat database SQLite berbasis file sementara dengan NullPool agar tiap thread memakai koneksi independen."""
        from sqlalchemy import event
        from sqlalchemy.pool import NullPool

        self._db_counter += 1
        db_file = Path(self._tmpdir.name) / f"lafriend_d213_{self._db_counter}.db"
        db_url = f"sqlite:///{db_file.as_posix()}"

        eng = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 10},
            poolclass=NullPool,
        )

        @event.listens_for(eng, "connect")
        def _configure_sqlite(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

        with eng.connect() as conn:
            conn.execute(text(f"PRAGMA journal_mode={journal_mode}"))
            conn.commit()

        ensure_database_schema(eng)
        return db_url, eng

    def _open_independent_verify_session(self, db_url: str):
        """Membuka engine & session baru yang sepenuhnya independen untuk memverifikasi kondisi aktual di disk."""
        from sqlalchemy.pool import NullPool

        verify_eng = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 10},
            poolclass=NullPool,
        )
        VerifySession = sessionmaker(autocommit=False, autoflush=False, bind=verify_eng)
        return verify_eng, VerifySession()

    def _seed_same_proposal_scenario(self, eng, proposal_id: str = "PR-001"):
        """Menyiapkan 1 proposal READY_FOR_SESSION dengan Host Andi + 2 kandidat ACCEPTED (Budi & Citra)."""
        SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = SessionFactory()
        try:
            course = Course(
                course_id="c_d213",
                course_code="ACK3CON1",
                course_name="Sistem Terdistribusi",
                study_program="S1 Teknik Komputer",
            )
            andi = Student(
                student_id="s_andi_d213",
                full_name="Andi Concurrency",
                email="andi.d213@telkomuniversity.ac.id",
                student_number="1201250301",
                password_hash="pw",
                verification_status="VERIFIED",
                account_status="ACTIVE",
                is_discoverable=True,
            )
            budi = Student(
                student_id="s_budi_d213",
                full_name="Budi Concurrency",
                email="budi.d213@telkomuniversity.ac.id",
                student_number="1201250302",
                password_hash="pw",
                verification_status="VERIFIED",
                account_status="ACTIVE",
                is_discoverable=True,
            )
            citra = Student(
                student_id="s_citra_d213",
                full_name="Citra Concurrency",
                email="citra.d213@telkomuniversity.ac.id",
                student_number="1201250303",
                password_hash="pw",
                verification_status="VERIFIED",
                account_status="ACTIVE",
                is_discoverable=True,
            )
            i_andi = StudyIntent(
                intent_id="INTENT-ANDI",
                student_id=andi.student_id,
                course_id=course.course_id,
                topics="Raft, Consensus",
                learning_mode="OFFLINE",
                earliest_date="2026-11-20",
                latest_date="2026-11-30",
                min_group_size=3,
                max_group_size=4,
                status="ACTIVE",
            )
            i_budi = StudyIntent(
                intent_id="INTENT-BUDI",
                student_id=budi.student_id,
                course_id=course.course_id,
                topics="Raft",
                learning_mode="OFFLINE",
                earliest_date="2026-11-20",
                latest_date="2026-11-30",
                min_group_size=3,
                max_group_size=4,
                status="ACTIVE",
            )
            i_citra = StudyIntent(
                intent_id="INTENT-CITRA",
                student_id=citra.student_id,
                course_id=course.course_id,
                topics="Consensus",
                learning_mode="OFFLINE",
                earliest_date="2026-11-20",
                latest_date="2026-11-30",
                min_group_size=3,
                max_group_size=4,
                status="ACTIVE",
            )
            sched = {"date": "2026-11-26", "start_time": "13:00", "end_time": "15:00", "duration_minutes": 120}
            prop = GroupProposal(
                proposal_id=proposal_id,
                host_intent_id=i_andi.intent_id,
                host_student_id=andi.student_id,
                course_id=course.course_id,
                status="READY_FOR_SESSION",
                min_group_size_bound=3,
                max_group_size_bound=4,
                group_quality_score=90.0,
                average_pair_score=91.0,
                minimum_pair_score=88.0,
                selected_schedule_json=json.dumps(sched),
                message="Same Proposal Concurrency Test",
                expires_at=datetime.utcnow() + timedelta(hours=24),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                finalized_at=datetime.utcnow(),
            )
            inv_b = Invitation(
                invitation_id=f"inv_b_{proposal_id}",
                invitation_type="GROUP_PROPOSAL",
                sender_id=andi.student_id,
                recipient_id=budi.student_id,
                target_intent_id=i_budi.intent_id,
                proposal_id=proposal_id,
                status="ACCEPTED",
                created_at=datetime.utcnow(),
                responded_at=datetime.utcnow(),
            )
            inv_c = Invitation(
                invitation_id=f"inv_c_{proposal_id}",
                invitation_type="GROUP_PROPOSAL",
                sender_id=andi.student_id,
                recipient_id=citra.student_id,
                target_intent_id=i_citra.intent_id,
                proposal_id=proposal_id,
                status="ACCEPTED",
                created_at=datetime.utcnow(),
                responded_at=datetime.utcnow(),
            )
            db.add_all([course, andi, budi, citra, i_andi, i_budi, i_citra, prop, inv_b, inv_c])
            db.commit()
        finally:
            db.close()

    def _seed_shared_candidate_intent_scenario(self, eng):
        """
        Menyiapkan 2 proposal berbeda (PR-001 & PR-002) yang berbagi 1 StudyIntent kandidat (INTENT-SHARED):
        - PR-001: Host Andi (INTENT-ANDI) + Budi (INTENT-SHARED) + Citra (INTENT-CITRA)
        - PR-002: Host Doni (INTENT-DONI) + Budi (INTENT-SHARED) + Eka (INTENT-EKA)
        """
        SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = SessionFactory()
        try:
            course = Course(
                course_id="c_d213_shared",
                course_code="ACK3CON2",
                course_name="Jaringan Komputer",
                study_program="S1 Teknik Komputer",
            )
            students = [
                Student(student_id="s_andi", full_name="Andi", email="andi.s@t.ac.id", student_number="2001", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True),
                Student(student_id="s_budi", full_name="Budi Shared", email="budi.s@t.ac.id", student_number="2002", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True),
                Student(student_id="s_citra", full_name="Citra", email="citra.s@t.ac.id", student_number="2003", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True),
                Student(student_id="s_doni", full_name="Doni", email="doni.s@t.ac.id", student_number="2004", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True),
                Student(student_id="s_eka", full_name="Eka", email="eka.s@t.ac.id", student_number="2005", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True),
            ]
            intents = [
                StudyIntent(intent_id="INTENT-ANDI", student_id="s_andi", course_id=course.course_id, topics="TCP/IP", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=3, max_group_size=4, status="ACTIVE"),
                StudyIntent(intent_id="INTENT-SHARED", student_id="s_budi", course_id=course.course_id, topics="TCP/IP, Routing", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=3, max_group_size=4, status="ACTIVE"),
                StudyIntent(intent_id="INTENT-CITRA", student_id="s_citra", course_id=course.course_id, topics="TCP/IP", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=3, max_group_size=4, status="ACTIVE"),
                StudyIntent(intent_id="INTENT-DONI", student_id="s_doni", course_id=course.course_id, topics="Routing", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=3, max_group_size=4, status="ACTIVE"),
                StudyIntent(intent_id="INTENT-EKA", student_id="s_eka", course_id=course.course_id, topics="Routing", learning_mode="OFFLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=3, max_group_size=4, status="ACTIVE"),
            ]
            sched = {"date": "2026-11-27", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120}
            now = datetime.utcnow()
            p1 = GroupProposal(
                proposal_id="PR-001", host_intent_id="INTENT-ANDI", host_student_id="s_andi",
                course_id=course.course_id, status="READY_FOR_SESSION",
                min_group_size_bound=3, max_group_size_bound=4,
                group_quality_score=89.0, average_pair_score=90.0, minimum_pair_score=87.0,
                selected_schedule_json=json.dumps(sched), message="Proposal A",
                expires_at=now + timedelta(hours=24), created_at=now, updated_at=now, finalized_at=now,
            )
            p2 = GroupProposal(
                proposal_id="PR-002", host_intent_id="INTENT-DONI", host_student_id="s_doni",
                course_id=course.course_id, status="READY_FOR_SESSION",
                min_group_size_bound=3, max_group_size_bound=4,
                group_quality_score=88.0, average_pair_score=89.0, minimum_pair_score=86.0,
                selected_schedule_json=json.dumps(sched), message="Proposal B",
                expires_at=now + timedelta(hours=24), created_at=now, updated_at=now, finalized_at=now,
            )
            invs = [
                Invitation(invitation_id="inv_p1_budi", invitation_type="GROUP_PROPOSAL", sender_id="s_andi", recipient_id="s_budi", target_intent_id="INTENT-SHARED", proposal_id="PR-001", status="ACCEPTED", created_at=now, responded_at=now),
                Invitation(invitation_id="inv_p1_citra", invitation_type="GROUP_PROPOSAL", sender_id="s_andi", recipient_id="s_citra", target_intent_id="INTENT-CITRA", proposal_id="PR-001", status="ACCEPTED", created_at=now, responded_at=now),
                Invitation(invitation_id="inv_p2_budi", invitation_type="GROUP_PROPOSAL", sender_id="s_doni", recipient_id="s_budi", target_intent_id="INTENT-SHARED", proposal_id="PR-002", status="ACCEPTED", created_at=now, responded_at=now),
                Invitation(invitation_id="inv_p2_eka", invitation_type="GROUP_PROPOSAL", sender_id="s_doni", recipient_id="s_eka", target_intent_id="INTENT-EKA", proposal_id="PR-002", status="ACCEPTED", created_at=now, responded_at=now),
            ]
            db.add(course)
            db.add_all(students)
            db.add_all(intents)
            db.add_all([p1, p2])
            db.add_all(invs)
            db.commit()
        finally:
            db.close()

    def _assert_same_proposal_db_integrity(self, db_url: str, proposal_id: str, expected_session_id: str):
        """Verifikasi independen D21.3-01 & D21.3-02 dari koneksi database baru."""
        verify_eng, verify_db = self._open_independent_verify_session(db_url)
        try:
            sessions = verify_db.query(StudySession).filter_by(proposal_id=proposal_id).all()
            self.assertEqual(len(sessions), 1, "Wajib ada tepat 1 StudySession untuk proposal yang sama")
            self.assertEqual(sessions[0].session_id, expected_session_id)
            self.assertEqual(sessions[0].status, "CONFIRMED")

            self.assertEqual(verify_db.query(StudySession).count(), 1)
            self.assertEqual(verify_db.query(SessionSlot).filter_by(session_id=expected_session_id).count(), 1)
            self.assertEqual(verify_db.query(SessionSlot).count(), 1)

            members = verify_db.query(SessionMember).filter_by(session_id=expected_session_id).all()
            self.assertEqual(len(members), 3)
            self.assertEqual(verify_db.query(SessionMember).count(), 3)
            self.assertEqual(
                {m.intent_id for m in members},
                {"INTENT-ANDI", "INTENT-BUDI", "INTENT-CITRA"}
            )

            for iid in ("INTENT-ANDI", "INTENT-BUDI", "INTENT-CITRA"):
                self.assertEqual(verify_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "MATCHED")

            self.assertEqual(
                verify_db.query(GroupProposal).filter_by(proposal_id=proposal_id).first().status,
                "SESSION_EXECUTED"
            )
        finally:
            verify_db.close()
            verify_eng.dispose()

    def _assert_shared_intent_db_integrity(
        self,
        db_url: str,
        winner_proposal_id: str,
        loser_proposal_id: str,
        winner_session_id: str,
        shared_intent_id: str,
        winner_exclusive_intents: list[str],
        loser_exclusive_intents: list[str],
        expected_member_count: int,
    ):
        """Verifikasi independen D21.3-03 s/d D21.3-06 dari koneksi database baru."""
        verify_eng, verify_db = self._open_independent_verify_session(db_url)
        try:
            # 1. Total sesi di seluruh DB tepat 1, milik proposal pemenang
            all_sessions = verify_db.query(StudySession).all()
            self.assertEqual(len(all_sessions), 1, "Hanya tepat 1 StudySession boleh terbentuk pada Shared Intent Race")
            self.assertEqual(all_sessions[0].session_id, winner_session_id)
            self.assertEqual(all_sessions[0].proposal_id, winner_proposal_id)

            # 2. Proposal kalah memiliki 0 StudySession, 0 SessionSlot, 0 SessionMember parsial
            self.assertIsNone(verify_db.query(StudySession).filter_by(proposal_id=loser_proposal_id).first())
            self.assertEqual(verify_db.query(SessionSlot).count(), 1)
            self.assertEqual(verify_db.query(SessionSlot).filter_by(session_id=winner_session_id).count(), 1)
            self.assertEqual(verify_db.query(SessionMember).count(), expected_member_count)
            self.assertEqual(verify_db.query(SessionMember).filter_by(session_id=winner_session_id).count(), expected_member_count)

            # 3. Shared StudyIntent muncul TEPAT 1 kali di session_members (milik sesi pemenang)
            shared_members = verify_db.query(SessionMember).filter_by(intent_id=shared_intent_id).all()
            self.assertEqual(len(shared_members), 1)
            self.assertEqual(shared_members[0].session_id, winner_session_id)
            self.assertEqual(verify_db.query(StudyIntent).filter_by(intent_id=shared_intent_id).first().status, "MATCHED")

            # 4. Intent eksklusif pemenang berstatus MATCHED; intent eksklusif kalah tetap ACTIVE
            for iid in winner_exclusive_intents:
                self.assertEqual(verify_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "MATCHED")
            for iid in loser_exclusive_intents:
                self.assertEqual(
                    verify_db.query(StudyIntent).filter_by(intent_id=iid).first().status,
                    "ACTIVE",
                    f"Intent eksklusif proposal kalah ({iid}) wajib tetap ACTIVE!"
                )

            # 5. Status kedua proposal konsisten: pemenang SESSION_EXECUTED, kalah tetap READY_FOR_SESSION
            self.assertEqual(
                verify_db.query(GroupProposal).filter_by(proposal_id=winner_proposal_id).first().status,
                "SESSION_EXECUTED"
            )
            self.assertEqual(
                verify_db.query(GroupProposal).filter_by(proposal_id=loser_proposal_id).first().status,
                "READY_FOR_SESSION"
            )
        finally:
            verify_db.close()
            verify_eng.dispose()

    def test_d21_3_01_same_proposal_concurrent_race_barrier_at_entry(self):
        """D21.3-01 & D21.3-02: Dua thread bersamaan (Barrier + file SQLite + Session independen) mengeksekusi proposal yang sama."""
        from threading import Barrier, Thread
        from app.session_execution_service import execute_study_session_from_proposal_service

        for journal_mode in ("DELETE", "WAL"):
            with self.subTest(journal_mode=journal_mode):
                db_url, eng = self._create_file_sqlite_engine(journal_mode=journal_mode)
                try:
                    self._seed_same_proposal_scenario(eng, proposal_id="PR-001")
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)

                    barrier = Barrier(2)
                    results = [None, None]
                    errors = [None, None]

                    def worker(idx: int):
                        db = SessionFactory()
                        try:
                            host = db.query(Student).filter_by(student_id="s_andi_d213").first()
                            barrier.wait(timeout=10)
                            results[idx] = execute_study_session_from_proposal_service(db, "PR-001", host)
                        except Exception as exc:
                            errors[idx] = exc
                        finally:
                            db.close()

                    t_a = Thread(target=worker, args=(0,))
                    t_b = Thread(target=worker, args=(1,))
                    t_a.start()
                    t_b.start()
                    t_a.join(timeout=15)
                    t_b.join(timeout=15)

                    self.assertFalse(t_a.is_alive())
                    self.assertFalse(t_b.is_alive())
                    self.assertEqual(errors, [None, None], f"Kedua request pada Same Proposal Race wajib selesai bersih: {errors}")
                    self.assertIsNotNone(results[0])
                    self.assertIsNotNone(results[1])
                    self.assertEqual(
                        results[0].session_id,
                        results[1].session_id,
                        "Kontrak idempotensi: kedua thread wajib menerima session_id yang persis sama"
                    )

                    self._assert_same_proposal_db_integrity(db_url, "PR-001", results[0].session_id)
                finally:
                    eng.dispose()

    def test_d21_3_02_same_proposal_deterministic_uq_session_proposal_race(self):
        """D21.3-01 & D21.3-02: Barrier di titik kritis pasca-read membuktikan uq_session_proposal benar-benar tertabrak & dipulihkan idempotent."""
        from threading import Barrier, Event, Lock, Thread
        from unittest.mock import patch
        from sqlalchemy import event as sa_event
        import app.session_execution_service as svc_mod

        db_url, eng = self._create_file_sqlite_engine(journal_mode="WAL")
        try:
            self._seed_same_proposal_scenario(eng, proposal_id="PR-001")
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)

            pre_write_barrier = Barrier(2)
            winner_committed = Event()
            turn_lock = Lock()
            winner_claimed = {"claimed": False}
            insert_attempts = []
            constraint_errors_seen = []

            @sa_event.listens_for(eng, "before_cursor_execute")
            def _track_inserts(_conn, _cursor, statement, _params, _ctx, _execmany):
                if "INSERT INTO study_sessions" in statement:
                    insert_attempts.append(statement)

            @sa_event.listens_for(eng, "handle_error")
            def _track_constraint_errors(exception_context):
                err_txt = str(exception_context.original_exception).lower()
                if "study_sessions.proposal_id" in err_txt:
                    constraint_errors_seen.append(err_txt)

            orig_parse_time = svc_mod.parse_time_minutes
            thread_parse_calls = {}

            def synchronized_parse_time(raw_time: str) -> int:
                # Sinkronisasi hanya pada pemanggilan pertama per thread (Step 9), tepat setelah
                # kedua thread selesai membaca existing_session=None & proposal.status=READY_FOR_SESSION
                import threading
                tid = threading.get_ident()
                count = thread_parse_calls.get(tid, 0) + 1
                thread_parse_calls[tid] = count
                val = orig_parse_time(raw_time)
                if count == 2:
                    pre_write_barrier.wait(timeout=10)
                    with turn_lock:
                        is_winner = not winner_claimed["claimed"]
                        if is_winner:
                            winner_claimed["claimed"] = True
                    if not is_winner:
                        # Biarkan thread pemenang commit terlebih dahulu agar thread kedua
                        # benar-benar menabrak uq_session_proposal di level SQLite
                        self.assertTrue(winner_committed.wait(timeout=10))
                return val

            results = [None, None]
            errors = [None, None]

            def worker(idx: int):
                db = SessionFactory()
                try:
                    host = db.query(Student).filter_by(student_id="s_andi_d213").first()
                    results[idx] = svc_mod.execute_study_session_from_proposal_service(db, "PR-001", host)
                    winner_committed.set()
                except Exception as exc:
                    errors[idx] = exc
                    winner_committed.set()
                finally:
                    db.close()

            with patch.object(svc_mod, "parse_time_minutes", side_effect=synchronized_parse_time):
                t_a = Thread(target=worker, args=(0,))
                t_b = Thread(target=worker, args=(1,))
                t_a.start()
                t_b.start()
                t_a.join(timeout=15)
                t_b.join(timeout=15)

            self.assertEqual(errors, [None, None], f"Tidak boleh ada error tak tertangani: {errors}")
            self.assertEqual(results[0].session_id, results[1].session_id)
            self.assertGreaterEqual(len(insert_attempts), 2, "Kedua thread wajib benar-benar mencoba INSERT study_sessions")
            self.assertGreaterEqual(len(constraint_errors_seen), 1, "Constraint uq_session_proposal wajib benar-benar terpicu")

            self._assert_same_proposal_db_integrity(db_url, "PR-001", results[0].session_id)
        finally:
            eng.dispose()

    def test_d21_3_03_shared_intent_concurrent_race_barrier_at_entry(self):
        """D21.3-03 s/d D21.3-06: Dua proposal berbeda (PR-001 & PR-002) berbagi INTENT-SHARED dieksekusi bersamaan."""
        from threading import Barrier, Thread
        from fastapi import HTTPException
        from app.session_execution_service import execute_study_session_from_proposal_service

        for journal_mode in ("DELETE", "WAL"):
            with self.subTest(journal_mode=journal_mode):
                db_url, eng = self._create_file_sqlite_engine(journal_mode=journal_mode)
                try:
                    self._seed_shared_candidate_intent_scenario(eng)
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)

                    barrier = Barrier(2)
                    outcomes = {}

                    def worker(proposal_id: str, host_student_id: str):
                        db = SessionFactory()
                        try:
                            host = db.query(Student).filter_by(student_id=host_student_id).first()
                            barrier.wait(timeout=10)
                            resp = execute_study_session_from_proposal_service(db, proposal_id, host)
                            outcomes[proposal_id] = ("SUCCESS", resp)
                        except HTTPException as he:
                            outcomes[proposal_id] = ("HTTP_ERROR", he)
                        except Exception as exc:
                            outcomes[proposal_id] = ("UNEXPECTED_ERROR", exc)
                        finally:
                            db.close()

                    t1 = Thread(target=worker, args=("PR-001", "s_andi"))
                    t2 = Thread(target=worker, args=("PR-002", "s_doni"))
                    t1.start()
                    t2.start()
                    t1.join(timeout=15)
                    t2.join(timeout=15)

                    self.assertFalse(t1.is_alive())
                    self.assertFalse(t2.is_alive())

                    winners = [pid for pid, (kind, _) in outcomes.items() if kind == "SUCCESS"]
                    losers = [pid for pid, (kind, _) in outcomes.items() if kind == "HTTP_ERROR"]
                    unexpected = [pid for pid, (kind, _) in outcomes.items() if kind == "UNEXPECTED_ERROR"]

                    self.assertEqual(unexpected, [], f"Tidak boleh ada exception tak terduga: {outcomes}")
                    self.assertEqual(len(winners), 1, f"Wajib tepat 1 proposal menang, aktual: {outcomes}")
                    self.assertEqual(len(losers), 1, f"Wajib tepat 1 proposal ditolak konflik, aktual: {outcomes}")

                    winner_pid = winners[0]
                    loser_pid = losers[0]
                    winner_resp = outcomes[winner_pid][1]
                    loser_exc = outcomes[loser_pid][1]

                    self.assertIn(loser_exc.status_code, (400, 409), f"Proposal kalah wajib 400/409, bukan {loser_exc.status_code}")

                    if winner_pid == "PR-001":
                        win_excl = ["INTENT-ANDI", "INTENT-CITRA"]
                        lose_excl = ["INTENT-DONI", "INTENT-EKA"]
                    else:
                        win_excl = ["INTENT-DONI", "INTENT-EKA"]
                        lose_excl = ["INTENT-ANDI", "INTENT-CITRA"]

                    self._assert_shared_intent_db_integrity(
                        db_url=db_url,
                        winner_proposal_id=winner_pid,
                        loser_proposal_id=loser_pid,
                        winner_session_id=winner_resp.session_id,
                        shared_intent_id="INTENT-SHARED",
                        winner_exclusive_intents=win_excl,
                        loser_exclusive_intents=lose_excl,
                        expected_member_count=3,
                    )
                finally:
                    eng.dispose()

    def test_d21_3_04_shared_intent_deterministic_uq_session_member_intent_race(self):
        """D21.3-03 s/d D21.3-06: Barrier pasca-read membuktikan PR-002 menabrak uq_session_member_intent, rollback penuh, & HTTP 409 (BUKAN idempotent)."""
        from threading import Barrier, Event, Thread
        from unittest.mock import patch
        from fastapi import HTTPException
        from sqlalchemy import event as sa_event
        import app.session_execution_service as svc_mod

        db_url, eng = self._create_file_sqlite_engine(journal_mode="WAL")
        try:
            self._seed_shared_candidate_intent_scenario(eng)
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)

            pre_write_barrier = Barrier(2)
            pr1_done = Event()
            pr2_flushed_session = []
            intent_constraint_errors = []

            @sa_event.listens_for(eng, "before_cursor_execute")
            def _track_sql(_conn, _cursor, statement, params, _ctx, _execmany):
                if "INSERT INTO study_sessions" in statement and "PR-002" in str(params):
                    pr2_flushed_session.append(statement)

            @sa_event.listens_for(eng, "handle_error")
            def _track_errors(exception_context):
                err_txt = str(exception_context.original_exception).lower()
                if "session_members.intent_id" in err_txt:
                    intent_constraint_errors.append(err_txt)

            orig_parse_time = svc_mod.parse_time_minutes
            thread_context = {}

            def synchronized_parse_time(raw_time: str) -> int:
                import threading
                tid = threading.get_ident()
                info = thread_context[tid]
                info["calls"] += 1
                val = orig_parse_time(raw_time)
                if info["calls"] == 2:
                    # Kedua thread SUDAH melewati pre-flight & melihat INTENT-SHARED=ACTIVE
                    pre_write_barrier.wait(timeout=10)
                    if info["proposal_id"] == "PR-002":
                        # Tahan PR-002 hingga PR-001 selesai commit agar PR-002 menabrak uq_session_member_intent
                        self.assertTrue(pr1_done.wait(timeout=10))
                return val

            outcomes = {}

            def worker(proposal_id: str, host_student_id: str):
                import threading
                thread_context[threading.get_ident()] = {"proposal_id": proposal_id, "calls": 0}
                db = SessionFactory()
                try:
                    host = db.query(Student).filter_by(student_id=host_student_id).first()
                    resp = svc_mod.execute_study_session_from_proposal_service(db, proposal_id, host)
                    outcomes[proposal_id] = ("SUCCESS", resp)
                except HTTPException as he:
                    outcomes[proposal_id] = ("HTTP_ERROR", he)
                except Exception as exc:
                    outcomes[proposal_id] = ("UNEXPECTED_ERROR", exc)
                finally:
                    if proposal_id == "PR-001":
                        pr1_done.set()
                    db.close()

            with patch.object(svc_mod, "parse_time_minutes", side_effect=synchronized_parse_time):
                t1 = Thread(target=worker, args=("PR-001", "s_andi"))
                t2 = Thread(target=worker, args=("PR-002", "s_doni"))
                t1.start()
                t2.start()
                t1.join(timeout=15)
                t2.join(timeout=15)

            self.assertEqual(outcomes["PR-001"][0], "SUCCESS")
            self.assertEqual(outcomes["PR-002"][0], "HTTP_ERROR")
            self.assertEqual(
                outcomes["PR-002"][1].status_code,
                409,
                "Konflik uq_session_member_intent wajib mengembalikan HTTP 409 CONFLICT (bukan idempotent)"
            )
            self.assertIn("telah dialokasikan", outcomes["PR-002"][1].detail)
            self.assertGreaterEqual(len(pr2_flushed_session), 1, "PR-002 wajib terbukti sempat flush StudySession sebelum rollback")
            self.assertGreaterEqual(len(intent_constraint_errors), 1, "Constraint uq_session_member_intent wajib benar-benar terpicu")

            self._assert_shared_intent_db_integrity(
                db_url=db_url,
                winner_proposal_id="PR-001",
                loser_proposal_id="PR-002",
                winner_session_id=outcomes["PR-001"][1].session_id,
                shared_intent_id="INTENT-SHARED",
                winner_exclusive_intents=["INTENT-ANDI", "INTENT-CITRA"],
                loser_exclusive_intents=["INTENT-DONI", "INTENT-EKA"],
                expected_member_count=3,
            )
        finally:
            eng.dispose()

    def test_d21_3_05_shared_intent_host_vs_candidate_concurrent_race(self):
        """D21.3-03 s/d D21.3-06: Shared Intent antara Host Proposal A (INTENT-001) dan Kandidat Proposal B (INTENT-001)."""
        from threading import Barrier, Thread
        from fastapi import HTTPException
        from app.session_execution_service import execute_study_session_from_proposal_service

        db_url, eng = self._create_file_sqlite_engine(journal_mode="WAL")
        try:
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
            db = SessionFactory()
            try:
                course = Course(course_id="c_hc", course_code="ACK3HC", course_name="Basis Data", study_program="S1 Teknik Komputer")
                s1 = Student(student_id="s_001", full_name="Student 1", email="s1@t.ac.id", student_number="3001", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True)
                s2 = Student(student_id="s_002", full_name="Student 2", email="s2@t.ac.id", student_number="3002", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True)
                s3 = Student(student_id="s_003", full_name="Student 3", email="s3@t.ac.id", student_number="3003", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True)
                i1 = StudyIntent(intent_id="INTENT-001", student_id="s_001", course_id="c_hc", topics="SQL", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=2, max_group_size=4, status="ACTIVE")
                i2 = StudyIntent(intent_id="INTENT-002", student_id="s_002", course_id="c_hc", topics="SQL", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=2, max_group_size=4, status="ACTIVE")
                i3 = StudyIntent(intent_id="INTENT-003", student_id="s_003", course_id="c_hc", topics="SQL", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=2, max_group_size=4, status="ACTIVE")
                sched = {"date": "2026-11-28", "start_time": "14:00", "end_time": "16:00", "duration_minutes": 120}
                now = datetime.utcnow()

                # Proposal A: host = INTENT-001, candidate = INTENT-002
                p_a = GroupProposal(
                    proposal_id="PR-001", host_intent_id="INTENT-001", host_student_id="s_001", course_id="c_hc",
                    status="READY_FOR_SESSION", min_group_size_bound=2, max_group_size_bound=4,
                    selected_schedule_json=json.dumps(sched), expires_at=now + timedelta(hours=24),
                    created_at=now, updated_at=now, finalized_at=now,
                )
                inv_a = Invitation(
                    invitation_id="inv_a_2", invitation_type="GROUP_PROPOSAL", sender_id="s_001",
                    recipient_id="s_002", target_intent_id="INTENT-002", proposal_id="PR-001",
                    status="ACCEPTED", created_at=now, responded_at=now,
                )
                # Proposal B: host = INTENT-003, candidate = INTENT-001
                p_b = GroupProposal(
                    proposal_id="PR-002", host_intent_id="INTENT-003", host_student_id="s_003", course_id="c_hc",
                    status="READY_FOR_SESSION", min_group_size_bound=2, max_group_size_bound=4,
                    selected_schedule_json=json.dumps(sched), expires_at=now + timedelta(hours=24),
                    created_at=now, updated_at=now, finalized_at=now,
                )
                inv_b = Invitation(
                    invitation_id="inv_b_1", invitation_type="GROUP_PROPOSAL", sender_id="s_003",
                    recipient_id="s_001", target_intent_id="INTENT-001", proposal_id="PR-002",
                    status="ACCEPTED", created_at=now, responded_at=now,
                )
                db.add_all([course, s1, s2, s3, i1, i2, i3, p_a, inv_a, p_b, inv_b])
                db.commit()
            finally:
                db.close()

            barrier = Barrier(2)
            outcomes = {}

            def worker(proposal_id: str, host_student_id: str):
                w_db = SessionFactory()
                try:
                    host = w_db.query(Student).filter_by(student_id=host_student_id).first()
                    barrier.wait(timeout=10)
                    resp = execute_study_session_from_proposal_service(w_db, proposal_id, host)
                    outcomes[proposal_id] = ("SUCCESS", resp)
                except HTTPException as he:
                    outcomes[proposal_id] = ("HTTP_ERROR", he)
                except Exception as exc:
                    outcomes[proposal_id] = ("UNEXPECTED_ERROR", exc)
                finally:
                    w_db.close()

            t1 = Thread(target=worker, args=("PR-001", "s_001"))
            t2 = Thread(target=worker, args=("PR-002", "s_003"))
            t1.start()
            t2.start()
            t1.join(timeout=15)
            t2.join(timeout=15)

            winners = [pid for pid, (kind, _) in outcomes.items() if kind == "SUCCESS"]
            losers = [pid for pid, (kind, _) in outcomes.items() if kind == "HTTP_ERROR"]
            self.assertEqual(len(winners), 1, f"Wajib tepat 1 pemenang: {outcomes}")
            self.assertEqual(len(losers), 1, f"Wajib tepat 1 kalah konflik: {outcomes}")
            self.assertIn(outcomes[losers[0]][1].status_code, (400, 409))

            winner_pid = winners[0]
            loser_pid = losers[0]
            self._assert_shared_intent_db_integrity(
                db_url=db_url,
                winner_proposal_id=winner_pid,
                loser_proposal_id=loser_pid,
                winner_session_id=outcomes[winner_pid][1].session_id,
                shared_intent_id="INTENT-001",
                winner_exclusive_intents=["INTENT-002"] if winner_pid == "PR-001" else ["INTENT-003"],
                loser_exclusive_intents=["INTENT-003"] if winner_pid == "PR-001" else ["INTENT-002"],
                expected_member_count=2,
            )
        finally:
            eng.dispose()

    def test_d21_3_06_sqlite_lock_contention_recovery_and_exhaustion_fail_closed(self):
        """Day 21.3: Membedakan SQLite lock contention transien (retry bersih) vs lock exhausted (HTTP 409, tanpa data parsial)."""
        import sqlite3
        from unittest.mock import patch
        from fastapi import HTTPException
        from sqlalchemy.orm import Session as SASession
        from sqlalchemy.exc import OperationalError
        import app.session_execution_service as svc_mod

        # Skenario A: Lock contention sementara 1x lalu berhasil -> sukses atomik tanpa duplikasi
        db_url_a, eng_a = self._create_file_sqlite_engine(journal_mode="WAL")
        try:
            self._seed_same_proposal_scenario(eng_a, proposal_id="PR-LOCK-OK")
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_a)
            db = SessionFactory()
            orig_commit = SASession.commit
            commit_calls = {"n": 0}

            def fail_once_locked(sess_self):
                commit_calls["n"] += 1
                if commit_calls["n"] == 1:
                    raise OperationalError("COMMIT", {}, sqlite3.OperationalError("database is locked"))
                return orig_commit(sess_self)

            try:
                host = db.query(Student).filter_by(student_id="s_andi_d213").first()
                with patch.object(SASession, "commit", new=fail_once_locked):
                    resp = svc_mod.execute_study_session_from_proposal_service(db, "PR-LOCK-OK", host)
                self.assertEqual(commit_calls["n"], 2)
                self._assert_same_proposal_db_integrity(db_url_a, "PR-LOCK-OK", resp.session_id)
            finally:
                db.close()
        finally:
            eng_a.dispose()

        # Skenario B: Lock contention tak kunjung reda (exhausted) -> WAJIB fail-closed HTTP 409 & 0 data parsial
        db_url_b, eng_b = self._create_file_sqlite_engine(journal_mode="WAL")
        try:
            self._seed_same_proposal_scenario(eng_b, proposal_id="PR-LOCK-FAIL")
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_b)
            db = SessionFactory()

            def always_locked(_sess_self):
                raise OperationalError("COMMIT", {}, sqlite3.OperationalError("database is locked"))

            try:
                host = db.query(Student).filter_by(student_id="s_andi_d213").first()
                with patch.object(SASession, "commit", new=always_locked):
                    with self.assertRaises(HTTPException) as ctx:
                        svc_mod.execute_study_session_from_proposal_service(db, "PR-LOCK-FAIL", host)
                self.assertEqual(ctx.exception.status_code, 409)
            finally:
                db.close()

            # Verifikasi independen: 0 StudySession, 0 Slot, 0 Member, semua intent ACTIVE, proposal READY_FOR_SESSION
            verify_eng, verify_db = self._open_independent_verify_session(db_url_b)
            try:
                self.assertEqual(verify_db.query(StudySession).count(), 0)
                self.assertEqual(verify_db.query(SessionSlot).count(), 0)
                self.assertEqual(verify_db.query(SessionMember).count(), 0)
                for iid in ("INTENT-ANDI", "INTENT-BUDI", "INTENT-CITRA"):
                    self.assertEqual(verify_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "ACTIVE")
                self.assertEqual(
                    verify_db.query(GroupProposal).filter_by(proposal_id="PR-LOCK-FAIL").first().status,
                    "READY_FOR_SESSION"
                )
            finally:
                verify_db.close()
                verify_eng.dispose()
        finally:
            eng_b.dispose()


class TestDay21SessionExecutionRecovery(unittest.TestCase):
    """
    Day 21.4 — Failure Recovery, Real SQLite Lock Recovery, Idempotent Replay,
    Inconsistent State Fail-Closed Validation & Final Day 21 Closure Suite.
    """

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory(prefix="lafriend_day21_4_")
        self._db_counter = 0

    def tearDown(self):
        self._tmpdir.cleanup()

    def _create_file_sqlite_db(self, busy_timeout_ms: int = 5000, journal_mode: str = "WAL"):
        """Membuat database SQLite file sementara dengan NullPool dan busy_timeout yang dapat dikonfigurasi khusus tes."""
        from sqlalchemy import event
        from sqlalchemy.pool import NullPool

        self._db_counter += 1
        db_file = Path(self._tmpdir.name) / f"lafriend_d214_{self._db_counter}.db"
        db_url = f"sqlite:///{db_file.as_posix()}"

        eng = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": max(0.05, busy_timeout_ms / 1000.0)},
            poolclass=NullPool,
        )

        @event.listens_for(eng, "connect")
        def _configure_sqlite(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            cur.close()

        with eng.connect() as conn:
            conn.execute(text(f"PRAGMA journal_mode={journal_mode}"))
            conn.commit()

        ensure_database_schema(eng)
        return db_file, db_url, eng

    def _open_independent_verify_session(self, db_url: str):
        from sqlalchemy.pool import NullPool

        verify_eng = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 5},
            poolclass=NullPool,
        )
        VerifySession = sessionmaker(autocommit=False, autoflush=False, bind=verify_eng)
        return verify_eng, VerifySession()

    def _seed_ready_proposal(self, eng, proposal_id: str = "PR-REC-001", status_val: str = "READY_FOR_SESSION"):
        SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = SessionFactory()
        try:
            course = Course(
                course_id="c_d214",
                course_code="ACK4REC1",
                course_name="Keandalan Sistem",
                study_program="S1 Teknik Komputer",
            )
            andi = Student(
                student_id="s_andi_d214", full_name="Andi Recovery", email="andi.d214@t.ac.id",
                student_number="4001", password_hash="pw", verification_status="VERIFIED",
                account_status="ACTIVE", is_discoverable=True,
            )
            budi = Student(
                student_id="s_budi_d214", full_name="Budi Recovery", email="budi.d214@t.ac.id",
                student_number="4002", password_hash="pw", verification_status="VERIFIED",
                account_status="ACTIVE", is_discoverable=True,
            )
            citra = Student(
                student_id="s_citra_d214", full_name="Citra Recovery", email="citra.d214@t.ac.id",
                student_number="4003", password_hash="pw", verification_status="VERIFIED",
                account_status="ACTIVE", is_discoverable=True,
            )
            doni = Student(
                student_id="s_doni_d214", full_name="Doni NonHost", email="doni.d214@t.ac.id",
                student_number="4004", password_hash="pw", verification_status="VERIFIED",
                account_status="ACTIVE", is_discoverable=True,
            )
            i_andi = StudyIntent(
                intent_id="INTENT-REC-ANDI", student_id=andi.student_id, course_id=course.course_id,
                topics="Fault Tolerance", learning_mode="ONLINE", earliest_date="2026-11-20",
                latest_date="2026-11-30", min_group_size=3, max_group_size=4, status="ACTIVE",
            )
            i_budi = StudyIntent(
                intent_id="INTENT-REC-BUDI", student_id=budi.student_id, course_id=course.course_id,
                topics="Fault Tolerance", learning_mode="ONLINE", earliest_date="2026-11-20",
                latest_date="2026-11-30", min_group_size=3, max_group_size=4, status="ACTIVE",
            )
            i_citra = StudyIntent(
                intent_id="INTENT-REC-CITRA", student_id=citra.student_id, course_id=course.course_id,
                topics="Fault Tolerance", learning_mode="ONLINE", earliest_date="2026-11-20",
                latest_date="2026-11-30", min_group_size=3, max_group_size=4, status="ACTIVE",
            )
            sched = {"date": "2026-11-29", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120}
            now = datetime.utcnow()
            prop = GroupProposal(
                proposal_id=proposal_id, host_intent_id=i_andi.intent_id, host_student_id=andi.student_id,
                course_id=course.course_id, status=status_val, min_group_size_bound=3, max_group_size_bound=4,
                group_quality_score=93.0, average_pair_score=93.0, minimum_pair_score=91.0,
                selected_schedule_json=json.dumps(sched), message="Recovery Test Proposal",
                expires_at=now + timedelta(hours=24), created_at=now, updated_at=now, finalized_at=now,
            )
            inv_b = Invitation(
                invitation_id=f"inv_b_{proposal_id}", invitation_type="GROUP_PROPOSAL",
                sender_id=andi.student_id, recipient_id=budi.student_id, target_intent_id=i_budi.intent_id,
                proposal_id=proposal_id, status="ACCEPTED", created_at=now, responded_at=now,
            )
            inv_c = Invitation(
                invitation_id=f"inv_c_{proposal_id}", invitation_type="GROUP_PROPOSAL",
                sender_id=andi.student_id, recipient_id=citra.student_id, target_intent_id=i_citra.intent_id,
                proposal_id=proposal_id, status="ACCEPTED", created_at=now, responded_at=now,
            )
            db.add_all([course, andi, budi, citra, doni, i_andi, i_budi, i_citra, prop, inv_b, inv_c])
            db.commit()
        finally:
            db.close()

    def _assert_exact_single_session_state(self, db_url: str, proposal_id: str, expected_session_id: str):
        verify_eng, verify_db = self._open_independent_verify_session(db_url)
        try:
            self.assertEqual(verify_db.query(StudySession).count(), 1)
            sess = verify_db.query(StudySession).filter_by(proposal_id=proposal_id).first()
            self.assertIsNotNone(sess)
            self.assertEqual(sess.session_id, expected_session_id)
            self.assertEqual(sess.status, "CONFIRMED")

            self.assertEqual(verify_db.query(SessionSlot).count(), 1)
            self.assertEqual(verify_db.query(SessionSlot).filter_by(session_id=expected_session_id).count(), 1)

            members = verify_db.query(SessionMember).filter_by(session_id=expected_session_id).all()
            self.assertEqual(len(members), 3)
            self.assertEqual(verify_db.query(SessionMember).count(), 3)
            self.assertEqual(
                {m.intent_id for m in members},
                {"INTENT-REC-ANDI", "INTENT-REC-BUDI", "INTENT-REC-CITRA"}
            )

            for iid in ("INTENT-REC-ANDI", "INTENT-REC-BUDI", "INTENT-REC-CITRA"):
                self.assertEqual(verify_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "MATCHED")

            self.assertEqual(
                verify_db.query(GroupProposal).filter_by(proposal_id=proposal_id).first().status,
                "SESSION_EXECUTED"
            )
        finally:
            verify_db.close()
            verify_eng.dispose()

    def test_d21_4_01_post_commit_recovery_across_fresh_database_session(self):
        """Day 21.4 (A & D21.4-01/02): Pemulihan pasca-commit (formatter/serialization/disconnect error) memakai SQLAlchemy Session baru."""
        from unittest.mock import patch
        import app.session_execution_service as svc_mod

        failure_scenarios = [
            ("formatter_error_after_commit", RuntimeError("Simulated response formatter failure after commit")),
            ("serialization_error_after_commit", ValueError("Simulated JSON serialization error after commit")),
            ("client_disconnect_timeout_after_commit", ConnectionResetError("Simulated client timeout/disconnect after commit")),
        ]

        for idx, (label, sim_error) in enumerate(failure_scenarios):
            with self.subTest(scenario=label):
                _, db_url, eng = self._create_file_sqlite_db(journal_mode="WAL")
                try:
                    pid = f"PR-REC-01-{idx}"
                    self._seed_ready_proposal(eng, proposal_id=pid)
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)

                    # 1. Request pertama menggunakan Session #1: DB commit SUKSES, lalu respons gagal dikirim
                    db_first = SessionFactory()
                    try:
                        host_first = db_first.query(Student).filter_by(student_id="s_andi_d214").first()
                        with patch.object(svc_mod, "format_study_session_response", side_effect=sim_error):
                            with self.assertRaises(type(sim_error)):
                                svc_mod.execute_study_session_from_proposal_service(db_first, pid, host_first)
                    finally:
                        # Tutup penuh Session #1 agar pemulihan tidak boleh bergantung pada state Session #1
                        db_first.close()

                    # Catat session_id aktual yang sudah committed dari koneksi independen
                    v_eng, v_db = self._open_independent_verify_session(db_url)
                    try:
                        committed_sess = v_db.query(StudySession).filter_by(proposal_id=pid).first()
                        self.assertIsNotNone(committed_sess, "Transaksi wajib sudah committed walau pengiriman respons gagal")
                        committed_session_id = committed_sess.session_id
                    finally:
                        v_db.close()
                        v_eng.dispose()

                    # 2. Request ulang menggunakan Session #2 yang benar-benar baru
                    db_second = SessionFactory()
                    try:
                        host_second = db_second.query(Student).filter_by(student_id="s_andi_d214").first()
                        recovered_resp = svc_mod.execute_study_session_from_proposal_service(db_second, pid, host_second)
                    finally:
                        db_second.close()

                    self.assertEqual(
                        recovered_resp.session_id,
                        committed_session_id,
                        "Retry pada fresh Session wajib memulihkan session_id yang persis sama"
                    )
                    self._assert_exact_single_session_state(db_url, pid, committed_session_id)
                finally:
                    eng.dispose()

    def test_d21_4_02_repeated_idempotent_request_replay_10x(self):
        """Day 21.4 (B & D21.4-03): Replay request identik sebanyak 10 kali pada fresh Sessions menghasilkan 1 sesi konsisten."""
        from app.session_execution_service import execute_study_session_from_proposal_service

        _, db_url, eng = self._create_file_sqlite_db(journal_mode="WAL")
        try:
            pid = "PR-REC-REPLAY-10X"
            self._seed_ready_proposal(eng, proposal_id=pid)
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)

            # Eksekusi pertama
            db0 = SessionFactory()
            try:
                host0 = db0.query(Student).filter_by(student_id="s_andi_d214").first()
                initial_resp = execute_study_session_from_proposal_service(db0, pid, host0)
            finally:
                db0.close()

            expected_session_id = initial_resp.session_id
            self.assertEqual(len(initial_resp.slots), 1)
            self.assertEqual(len(initial_resp.members), 3)

            # Replay 10 kali berturut-turut menggunakan Session independen baru setiap kali
            for replay_idx in range(10):
                db_rep = SessionFactory()
                try:
                    host_rep = db_rep.query(Student).filter_by(student_id="s_andi_d214").first()
                    replay_resp = execute_study_session_from_proposal_service(db_rep, pid, host_rep)
                    self.assertEqual(
                        replay_resp.session_id,
                        expected_session_id,
                        f"Replay ke-{replay_idx + 1} mengembalikan session_id berbeda"
                    )
                    self.assertEqual(len(replay_resp.slots), 1)
                    self.assertEqual(len(replay_resp.members), 3)
                finally:
                    db_rep.close()

            # Verifikasi database independen: 1 session, 1 slot, 3 member, 3 MATCHED intent, 1 SESSION_EXECUTED proposal
            self._assert_exact_single_session_state(db_url, pid, expected_session_id)
        finally:
            eng.dispose()

    def test_d21_4_03_real_sqlite_physical_lock_recovery_and_exhaustion(self):
        """Day 21.4 (C & D21.4-04): Pengujian lock fisik SQLite nyata (BEGIN IMMEDIATE) untuk recovery sukses & fail-closed exhaustion."""
        import sqlite3
        from threading import Event, Thread
        from fastapi import HTTPException
        from sqlalchemy import event as sa_event
        from app.session_execution_service import execute_study_session_from_proposal_service

        # --- Skenario A: Lock fisik dipegang Connection A, dilepas setelah Connection B menabrak lock & rollback -> retry BERHASIL ---
        db_file_a, db_url_a, eng_a = self._create_file_sqlite_db(busy_timeout_ms=25, journal_mode="WAL")
        lock_conn_a = sqlite3.connect(str(db_file_a), isolation_level=None, timeout=5.0)
        try:
            pid_a = "PR-REAL-LOCK-RECOVER"
            self._seed_ready_proposal(eng_a, proposal_id=pid_a)
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_a)

            real_lock_errors = []
            rollback_events = []
            lock_hit_and_rolled_back = Event()

            @sa_event.listens_for(eng_a, "handle_error")
            def _capture_real_lock(exception_context):
                err_txt = str(exception_context.original_exception).lower()
                if "database is locked" in err_txt:
                    real_lock_errors.append(err_txt)

            @sa_event.listens_for(SessionFactory, "after_rollback")
            def _on_rollback(_session):
                rollback_events.append(1)
                if real_lock_errors:
                    lock_hit_and_rolled_back.set()

            # Connection A memegang write lock fisik SQLite via BEGIN IMMEDIATE
            lock_conn_a.execute("BEGIN IMMEDIATE")

            worker_result = {"resp": None, "err": None}

            def run_execution():
                w_db = SessionFactory()
                try:
                    host = w_db.query(Student).filter_by(student_id="s_andi_d214").first()
                    worker_result["resp"] = execute_study_session_from_proposal_service(w_db, pid_a, host)
                except Exception as exc:
                    worker_result["err"] = exc
                finally:
                    w_db.close()

            worker_thread = Thread(target=run_execution)
            worker_thread.start()

            # Tunggu secara deterministik hingga worker benar-benar menabrak lock fisik SQLite & menjalankan rollback
            self.assertTrue(
                lock_hit_and_rolled_back.wait(timeout=5.0),
                "Worker harus benar-benar mengalami OperationalError lock fisik SQLite dan melakukan rollback"
            )

            # Selama lock masih dipegang, pastikan tidak ada data parsial yang bocor ke database
            mid_eng, mid_db = self._open_independent_verify_session(db_url_a)
            try:
                self.assertEqual(mid_db.query(StudySession).count(), 0)
                self.assertEqual(mid_db.query(SessionSlot).count(), 0)
                self.assertEqual(mid_db.query(SessionMember).count(), 0)
            finally:
                mid_db.close()
                mid_eng.dispose()

            # Lepaskan write lock fisik dari Connection A agar retry worker berikutnya dapat menuntaskan transaksi
            lock_conn_a.execute("COMMIT")
            worker_thread.join(timeout=10.0)

            self.assertFalse(worker_thread.is_alive())
            self.assertIsNone(worker_result["err"], f"Retry pasca pelepasan lock fisik wajib sukses: {worker_result['err']}")
            self.assertIsNotNone(worker_result["resp"])
            self.assertGreaterEqual(len(real_lock_errors), 1, "Wajib terbukti mengalami sqlite3 OperationalError: database is locked nyata")
            self.assertGreaterEqual(len(rollback_events), 1, "Wajib terbukti menjalankan rollback sebelum retry")

            self._assert_exact_single_session_state(db_url_a, pid_a, worker_result["resp"].session_id)
        finally:
            lock_conn_a.close()
            eng_a.dispose()

        # --- Skenario B: Lock fisik tidak dilepas sampai batas retry habis -> fail-closed HTTP 409 & 0 data parsial ---
        db_file_b, db_url_b, eng_b = self._create_file_sqlite_db(busy_timeout_ms=15, journal_mode="WAL")
        lock_conn_b = sqlite3.connect(str(db_file_b), isolation_level=None, timeout=5.0)
        try:
            pid_b = "PR-REAL-LOCK-EXHAUST"
            self._seed_ready_proposal(eng_b, proposal_id=pid_b)
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_b)

            exhaust_lock_errors = []

            @sa_event.listens_for(eng_b, "handle_error")
            def _capture_exhaust_lock(exception_context):
                err_txt = str(exception_context.original_exception).lower()
                if "database is locked" in err_txt:
                    exhaust_lock_errors.append(err_txt)

            # Pegang write lock fisik terus-menerus melampaui seluruh percobaan retry
            lock_conn_b.execute("BEGIN IMMEDIATE")
            try:
                w_db = SessionFactory()
                try:
                    host = w_db.query(Student).filter_by(student_id="s_andi_d214").first()
                    with self.assertRaises(HTTPException) as ctx:
                        execute_study_session_from_proposal_service(w_db, pid_b, host)
                    self.assertEqual(ctx.exception.status_code, 409)
                finally:
                    w_db.close()
            finally:
                lock_conn_b.execute("ROLLBACK")

            self.assertGreaterEqual(len(exhaust_lock_errors), 6, "Seluruh percobaan retry wajib benar-benar menemui lock fisik SQLite")

            # Verifikasi independen: ZERO data parsial tertinggal pasca retry exhaustion
            v_eng, v_db = self._open_independent_verify_session(db_url_b)
            try:
                self.assertEqual(v_db.query(StudySession).count(), 0)
                self.assertEqual(v_db.query(SessionSlot).count(), 0)
                self.assertEqual(v_db.query(SessionMember).count(), 0)
                for iid in ("INTENT-REC-ANDI", "INTENT-REC-BUDI", "INTENT-REC-CITRA"):
                    self.assertEqual(v_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "ACTIVE")
                self.assertEqual(
                    v_db.query(GroupProposal).filter_by(proposal_id=pid_b).first().status,
                    "READY_FOR_SESSION"
                )
            finally:
                v_db.close()
                v_eng.dispose()
        finally:
            lock_conn_b.close()
            eng_b.dispose()

    def test_d21_4_04_inconsistent_state_matrix_and_fail_closed_validation(self):
        """Day 21.4 (D & D21.4-05): Validasi fail-closed atas seluruh kondisi korup & otorisasi host sebelum recovery."""
        from fastapi import HTTPException
        from app.session_execution_service import execute_study_session_from_proposal_service

        # --- Kasus 1: Proposal SESSION_EXECUTED, tetapi StudySession TIDAK ADA -> Fail-closed HTTP 400, 0 sesi baru ---
        _, db_url_1, eng_1 = self._create_file_sqlite_db()
        try:
            self._seed_ready_proposal(eng_1, proposal_id="PR-CORRUPT-1", status_val="SESSION_EXECUTED")
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_1)
            db = SessionFactory()
            try:
                host = db.query(Student).filter_by(student_id="s_andi_d214").first()
                with self.assertRaises(HTTPException) as ctx:
                    execute_study_session_from_proposal_service(db, "PR-CORRUPT-1", host)
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertIn("SESSION_EXECUTED", ctx.exception.detail)
            finally:
                db.close()

            v_eng, v_db = self._open_independent_verify_session(db_url_1)
            try:
                self.assertEqual(v_db.query(StudySession).count(), 0, "Tidak boleh membuat sesi baru secara otomatis")
            finally:
                v_db.close()
                v_eng.dispose()
        finally:
            eng_1.dispose()

        # --- Kasus 2: Proposal masih READY_FOR_SESSION, tetapi StudySession SUDAH ADA -> Fail-closed HTTP 409 ---
        _, db_url_2, eng_2 = self._create_file_sqlite_db()
        try:
            self._seed_ready_proposal(eng_2, proposal_id="PR-CORRUPT-2", status_val="READY_FOR_SESSION")
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_2)
            db = SessionFactory()
            try:
                # Simulasikan state korup: StudySession & slot/member ada, tetapi status proposal masih READY_FOR_SESSION
                corrupt_sess = StudySession(
                    session_id="sess_corrupt_2", proposal_id="PR-CORRUPT-2", host_id="s_andi_d214",
                    course_id="c_d214", title="Sesi Korup", status="CONFIRMED"
                )
                db.add(corrupt_sess)
                db.flush()
                db.add(SessionSlot(
                    slot_id="slot_c2", session_id="sess_corrupt_2", session_date="2026-11-29",
                    start_time="10:00", end_time="12:00", status="APPROVED"
                ))
                db.add(SessionMember(
                    member_id="mem_c2", session_id="sess_corrupt_2", student_id="s_andi_d214",
                    intent_id="INTENT-REC-ANDI", role="HOST", status="CONFIRMED"
                ))
                db.query(StudyIntent).filter_by(intent_id="INTENT-REC-ANDI").update({"status": "MATCHED"})
                db.commit()

                host = db.query(Student).filter_by(student_id="s_andi_d214").first()
                with self.assertRaises(HTTPException) as ctx:
                    execute_study_session_from_proposal_service(db, "PR-CORRUPT-2", host)
                self.assertEqual(ctx.exception.status_code, 409)
                self.assertIn("Inkonsistensi state database", ctx.exception.detail)
                self.assertIn("READY_FOR_SESSION", ctx.exception.detail)

                # Non-host tetap ditolak HTTP 403 sebelum inspeksi existing session
                non_host = db.query(Student).filter_by(student_id="s_doni_d214").first()
                with self.assertRaises(HTTPException) as ctx_auth:
                    execute_study_session_from_proposal_service(db, "PR-CORRUPT-2", non_host)
                self.assertEqual(ctx_auth.exception.status_code, 403)
            finally:
                db.close()

            # Pastikan service tidak diam-diam memperbaiki/mengubah status proposal korup
            v_eng, v_db = self._open_independent_verify_session(db_url_2)
            try:
                self.assertEqual(v_db.query(StudySession).count(), 1)
                self.assertEqual(
                    v_db.query(GroupProposal).filter_by(proposal_id="PR-CORRUPT-2").first().status,
                    "READY_FOR_SESSION"
                )
            finally:
                v_db.close()
                v_eng.dispose()
        finally:
            eng_2.dispose()

        # --- Kasus 3: Proposal SESSION_EXECUTED & StudySession ada, tetapi hilang SessionSlot / intent belum MATCHED -> Fail-closed HTTP 409 ---
        for sub_case in ("missing_slot", "unmatched_intent"):
            with self.subTest(corruption_variant=sub_case):
                _, _, eng_3 = self._create_file_sqlite_db()
                try:
                    pid = f"PR-CORRUPT-3-{sub_case}"
                    self._seed_ready_proposal(eng_3, proposal_id=pid, status_val="SESSION_EXECUTED")
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_3)
                    db = SessionFactory()
                    try:
                        s_obj = StudySession(
                            session_id=f"sess_c3_{sub_case}", proposal_id=pid, host_id="s_andi_d214",
                            course_id="c_d214", title="Sesi Parsial Korup", status="CONFIRMED"
                        )
                        db.add(s_obj)
                        db.flush()
                        if sub_case != "missing_slot":
                            db.add(SessionSlot(
                                slot_id=f"slot_c3_{sub_case}", session_id=s_obj.session_id,
                                session_date="2026-11-29", start_time="10:00", end_time="12:00", status="APPROVED"
                            ))
                        db.add(SessionMember(
                            member_id=f"mem_c3_{sub_case}", session_id=s_obj.session_id,
                            student_id="s_andi_d214", intent_id="INTENT-REC-ANDI", role="HOST", status="CONFIRMED"
                        ))
                        if sub_case != "unmatched_intent":
                            db.query(StudyIntent).filter_by(intent_id="INTENT-REC-ANDI").update({"status": "MATCHED"})
                        db.commit()

                        host = db.query(Student).filter_by(student_id="s_andi_d214").first()
                        with self.assertRaises(HTTPException) as ctx:
                            execute_study_session_from_proposal_service(db, pid, host)
                        self.assertEqual(ctx.exception.status_code, 409)
                        self.assertIn("Inkonsistensi state database", ctx.exception.detail)
                    finally:
                        db.close()
                finally:
                    eng_3.dispose()


if __name__ == "__main__":
    unittest.main()
