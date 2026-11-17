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

    def test_13_sqlite_legacy_migration_day21(self):
        """Memverifikasi auto-migrasi skema SQLite lama (tanpa proposal_id dan intent_id) secara aman, idempotent, dan fail-closed."""
        legacy_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        # Buat skema SQLite mentah versi Day 13 (tanpa proposal_id pada study_sessions, tanpa intent_id pada session_members)
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
            conn.commit()

        # Jalankan auto-migrasi ensure_database_schema pada legacy engine
        ensure_database_schema(legacy_engine)

        with legacy_engine.connect() as conn:
            # 1. Periksa kolom proposal_id di study_sessions
            cols_sess = [row[1] for row in conn.execute(text("PRAGMA table_info(study_sessions)")).fetchall()]
            self.assertIn("proposal_id", cols_sess)

            # 2. Periksa index uq_session_proposal
            idxs_sess = [row[1] for row in conn.execute(text("PRAGMA index_list(study_sessions)")).fetchall()]
            self.assertIn("uq_session_proposal", idxs_sess)

            # 3. Periksa kolom intent_id di session_members
            cols_mem = [row[1] for row in conn.execute(text("PRAGMA table_info(session_members)")).fetchall()]
            self.assertIn("intent_id", cols_mem)

            # 4. Periksa index uq_session_member_intent dan uq_session_member_student
            idxs_mem = [row[1] for row in conn.execute(text("PRAGMA index_list(session_members)")).fetchall()]
            self.assertIn("uq_session_member_intent", idxs_mem)
            self.assertIn("uq_session_member_student", idxs_mem)

            # 5. Uji idempotensi migrasi: panggil ulang tidak boleh melempar exception
            ensure_database_schema(legacy_engine)

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


if __name__ == "__main__":
    unittest.main()
