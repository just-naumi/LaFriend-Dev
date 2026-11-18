# ==============================================================================
# tests/test_day22_session_lifecycle.py
# ==============================================================================
# Test Suite Day 22 (Day 22.2 - Day 22.4): Session Lifecycle & Post-Execution Management
# Memvalidasi:
# - Day 22.2: Session State Machine (CONFIRMED -> COMPLETED / CANCELLED), idempotency,
#   terminal guards, dan otorisasi Host.
# - Day 22.3: Membership Lifecycle (CONFIRMED -> WITHDRAWN / REMOVED), Kebijakan Quorum
#   Option A (Explicit Host Control), larangan Host self-withdraw/remove, proteksi
#   immutability histori StudyIntent Day 21, dan pengetatan otorisasi GET detail sesi.
# - Day 22.4: Concurrency race conditions (complete vs cancel, cancel vs withdraw,
#   withdraw vs remove) & real physical SQLite lock recovery menggunakan file-backed SQLite,
#   NullPool independent sessions, threading.Barrier, dan independent DB verification.
# ==============================================================================

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier, Event, Thread

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import jwt
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.database import ensure_database_schema, get_db
from app.main import app
from app.models import (
    Course,
    GroupProposal,
    Invitation,
    SessionMember,
    SessionSlot,
    Student,
    StudyIntent,
    StudySession,
)
from app.routes import ALGORITHM, SECRET_KEY
from app.session_lifecycle_service import (
    cancel_study_session_service,
    complete_study_session_service,
    remove_member_from_study_session_service,
    withdraw_from_study_session_service,
)


def create_token(student_id: str, email: str) -> str:
    payload = {
        "sub": student_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class TestDay22SessionAndMembershipLifecycle(unittest.TestCase):
    """Day 22.2 & Day 22.3: API & Service Lifecycle, Quorum Option A, Authorization & Provenance Tests."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
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
        self.client = TestClient(app)

        self.course = Course(
            course_id="c_d22",
            course_code="ACK4LIFE",
            course_name="Rekayasa Perangkat Lunak",
            study_program="S1 Teknik Komputer",
        )
        self.andi = Student(
            student_id="s_andi_d22", full_name="Andi Host", email="andi.d22@t.ac.id",
            student_number="5001", password_hash="pw", verification_status="VERIFIED",
            account_status="ACTIVE", is_discoverable=True,
        )
        self.budi = Student(
            student_id="s_budi_d22", full_name="Budi Member", email="budi.d22@t.ac.id",
            student_number="5002", password_hash="pw", verification_status="VERIFIED",
            account_status="ACTIVE", is_discoverable=True,
        )
        self.citra = Student(
            student_id="s_citra_d22", full_name="Citra Member", email="citra.d22@t.ac.id",
            student_number="5003", password_hash="pw", verification_status="VERIFIED",
            account_status="ACTIVE", is_discoverable=True,
        )
        self.doni = Student(
            student_id="s_doni_d22", full_name="Doni Outsider", email="doni.d22@t.ac.id",
            student_number="5004", password_hash="pw", verification_status="VERIFIED",
            account_status="ACTIVE", is_discoverable=True,
        )

        self.i_andi = StudyIntent(
            intent_id="i_andi_d22", student_id=self.andi.student_id, course_id=self.course.course_id,
            topics="Architecture", learning_mode="ONLINE", earliest_date="2026-11-20",
            latest_date="2026-11-30", min_group_size=2, max_group_size=4, status="ACTIVE",
        )
        self.i_budi = StudyIntent(
            intent_id="i_budi_d22", student_id=self.budi.student_id, course_id=self.course.course_id,
            topics="Architecture", learning_mode="ONLINE", earliest_date="2026-11-20",
            latest_date="2026-11-30", min_group_size=2, max_group_size=4, status="ACTIVE",
        )
        self.i_citra = StudyIntent(
            intent_id="i_citra_d22", student_id=self.citra.student_id, course_id=self.course.course_id,
            topics="Architecture", learning_mode="ONLINE", earliest_date="2026-11-20",
            latest_date="2026-11-30", min_group_size=2, max_group_size=4, status="ACTIVE",
        )
        self.db.add_all([
            self.course, self.andi, self.budi, self.citra, self.doni,
            self.i_andi, self.i_budi, self.i_citra,
        ])
        self.db.commit()

        self.tok_andi = create_token(self.andi.student_id, self.andi.email)
        self.tok_budi = create_token(self.budi.student_id, self.budi.email)
        self.tok_citra = create_token(self.citra.student_id, self.citra.email)
        self.tok_doni = create_token(self.doni.student_id, self.doni.email)

    def tearDown(self):
        app.dependency_overrides = self.original_overrides
        self.db.close()
        self.engine.dispose()

    def _execute_session_via_day21(self, include_citra: bool = True, min_group_size: int = 2) -> tuple[str, str]:
        """Membentuk StudySession CONFIRMED nyata melalui endpoint Day 21 untuk menguji lifecycle Day 22."""
        pid = f"prop_d22_{datetime.utcnow().timestamp()}"
        now = datetime.utcnow()
        sched = {"date": "2026-11-29", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120}

        prop = GroupProposal(
            proposal_id=pid,
            host_intent_id=self.i_andi.intent_id,
            host_student_id=self.andi.student_id,
            course_id=self.course.course_id,
            status="READY_FOR_SESSION",
            min_group_size_bound=min_group_size,
            max_group_size_bound=4,
            selected_schedule_json=json.dumps(sched),
            expires_at=now + timedelta(hours=24),
            created_at=now,
            updated_at=now,
            finalized_at=now,
        )
        invs = [
            Invitation(
                invitation_id=f"inv_b_{pid}",
                invitation_type="GROUP_PROPOSAL",
                sender_id=self.andi.student_id,
                recipient_id=self.budi.student_id,
                target_intent_id=self.i_budi.intent_id,
                proposal_id=pid,
                status="ACCEPTED",
                created_at=now,
                responded_at=now,
            )
        ]
        if include_citra:
            invs.append(
                Invitation(
                    invitation_id=f"inv_c_{pid}",
                    invitation_type="GROUP_PROPOSAL",
                    sender_id=self.andi.student_id,
                    recipient_id=self.citra.student_id,
                    target_intent_id=self.i_citra.intent_id,
                    proposal_id=pid,
                    status="ACCEPTED",
                    created_at=now,
                    responded_at=now,
                )
            )
        self.db.add(prop)
        self.db.add_all(invs)
        self.db.commit()

        r = self.client.post(
            f"/api/v1/group-proposals/{pid}/execute-session",
            headers={"Authorization": f"Bearer {self.tok_andi}"},
        )
        self.assertEqual(r.status_code, 201)
        return r.json()["session_id"], pid

    def test_01_complete_session_success_idempotent_and_provenance_intact(self):
        """Day 22.2: Host menyelesaikan sesi (CONFIRMED -> COMPLETED), idempotent saat diulang, provenance tetap utuh."""
        sid, pid = self._execute_session_via_day21(include_citra=True)

        r1 = self.client.post(f"/api/v1/sessions/{sid}/complete", headers={"Authorization": f"Bearer {self.tok_andi}"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["status"], "COMPLETED")

        # Replay complete -> idempotent 200 OK
        r2 = self.client.post(f"/api/v1/sessions/{sid}/complete", headers={"Authorization": f"Bearer {self.tok_andi}"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["status"], "COMPLETED")

        # Verifikasi DB independen: seluruh StudyIntent tetap MATCHED, Proposal tetap SESSION_EXECUTED, 3 member utuh
        v_db = self.TestingSession()
        try:
            self.assertEqual(v_db.query(StudySession).filter_by(session_id=sid).first().status, "COMPLETED")
            self.assertEqual(v_db.query(GroupProposal).filter_by(proposal_id=pid).first().status, "SESSION_EXECUTED")
            self.assertEqual(v_db.query(SessionMember).filter_by(session_id=sid).count(), 3)
            for iid in (self.i_andi.intent_id, self.i_budi.intent_id, self.i_citra.intent_id):
                self.assertEqual(v_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "MATCHED")
        finally:
            v_db.close()

    def test_02_cancel_session_success_idempotent_and_provenance_intact(self):
        """Day 22.2: Host membatalkan sesi (CONFIRMED -> CANCELLED), idempotent, histori StudyIntent tidak kembali ACTIVE."""
        sid, pid = self._execute_session_via_day21(include_citra=True)

        r1 = self.client.post(f"/api/v1/sessions/{sid}/cancel", headers={"Authorization": f"Bearer {self.tok_andi}"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["status"], "CANCELLED")

        # Replay cancel -> idempotent 200 OK
        r2 = self.client.post(f"/api/v1/sessions/{sid}/cancel", headers={"Authorization": f"Bearer {self.tok_andi}"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["status"], "CANCELLED")

        # Verifikasi DB: StudyIntent tetap MATCHED, 3 SessionMember tetap tersimpan (tidak dihapus fisik)
        v_db = self.TestingSession()
        try:
            self.assertEqual(v_db.query(StudySession).filter_by(session_id=sid).first().status, "CANCELLED")
            self.assertEqual(v_db.query(GroupProposal).filter_by(proposal_id=pid).first().status, "SESSION_EXECUTED")
            members = v_db.query(SessionMember).filter_by(session_id=sid).all()
            self.assertEqual(len(members), 3)
            self.assertEqual({m.intent_id for m in members}, {self.i_andi.intent_id, self.i_budi.intent_id, self.i_citra.intent_id})
            for iid in (self.i_andi.intent_id, self.i_budi.intent_id, self.i_citra.intent_id):
                self.assertEqual(v_db.query(StudyIntent).filter_by(intent_id=iid).first().status, "MATCHED")
        finally:
            v_db.close()

    def test_03_terminal_and_non_confirmed_transitions_rejected_409(self):
        """Day 22.2: Sesi COMPLETED tidak boleh di-cancel, sesi CANCELLED tidak boleh di-complete, sesi DRAFT ditolak."""
        sid, _ = self._execute_session_via_day21(include_citra=False)
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/complete", headers={"Authorization": f"Bearer {self.tok_andi}"}).status_code,
            200,
        )
        # COMPLETED -> cancel ditolak 409
        r_bad_cancel = self.client.post(f"/api/v1/sessions/{sid}/cancel", headers={"Authorization": f"Bearer {self.tok_andi}"})
        self.assertEqual(r_bad_cancel.status_code, 409)

        # Buat sesi terpisah status CANCELLED dan status DRAFT
        s_cancelled = StudySession(
            session_id="sess_d22_cancelled", host_id=self.andi.student_id, course_id=self.course.course_id,
            title="Sesi Batal", status="CANCELLED",
        )
        s_draft = StudySession(
            session_id="sess_d22_draft", host_id=self.andi.student_id, course_id=self.course.course_id,
            title="Sesi Draft", status="DRAFT",
        )
        self.db.add_all([s_cancelled, s_draft])
        self.db.commit()

        # CANCELLED -> complete ditolak 409
        self.assertEqual(
            self.client.post("/api/v1/sessions/sess_d22_cancelled/complete", headers={"Authorization": f"Bearer {self.tok_andi}"}).status_code,
            409,
        )
        # DRAFT -> complete & cancel ditolak 409
        self.assertEqual(
            self.client.post("/api/v1/sessions/sess_d22_draft/complete", headers={"Authorization": f"Bearer {self.tok_andi}"}).status_code,
            409,
        )
        self.assertEqual(
            self.client.post("/api/v1/sessions/sess_d22_draft/cancel", headers={"Authorization": f"Bearer {self.tok_andi}"}).status_code,
            409,
        )

    def test_04_session_lifecycle_host_only_authorization(self):
        """Day 22.2: Non-host (anggota Budi & outsider Doni) ditolak HTTP 403 untuk complete & cancel (termasuk pasca-terminal)."""
        sid, _ = self._execute_session_via_day21(include_citra=False)

        for tok in (self.tok_budi, self.tok_doni):
            self.assertEqual(
                self.client.post(f"/api/v1/sessions/{sid}/complete", headers={"Authorization": f"Bearer {tok}"}).status_code,
                403,
            )
            self.assertEqual(
                self.client.post(f"/api/v1/sessions/{sid}/cancel", headers={"Authorization": f"Bearer {tok}"}).status_code,
                403,
            )

        # Setelah selesai (COMPLETED), non-host tetap harus mendapat 403 (bukan 200 idempotent!)
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/complete", headers={"Authorization": f"Bearer {self.tok_andi}"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/complete", headers={"Authorization": f"Bearer {self.tok_budi}"}).status_code,
            403,
        )

    def test_05_member_withdraw_option_a_explicit_host_control_and_immutable_intent(self):
        """Day 22.3: Member withdraw mengembalikan response aksi minimal (privacy-safe), quorum turun di bawah min_group_size namun sesi TETAP CONFIRMED (Option A)."""
        # Exact Option A scenario: min_group_size=2, 1 Host (Andi) + 1 Member (Budi)
        sid, _ = self._execute_session_via_day21(include_citra=False, min_group_size=2)
        expected_minimal_keys = {"session_id", "session_status", "membership_status"}

        r_wd = self.client.post(f"/api/v1/sessions/{sid}/withdraw", headers={"Authorization": f"Bearer {self.tok_budi}"})
        self.assertEqual(r_wd.status_code, 200)
        body = r_wd.json()
        # Privacy guard: response withdraw pertama HANYA memuat field minimal (tanpa location, slots, members, email, NIM)
        self.assertEqual(set(body.keys()), expected_minimal_keys)
        self.assertEqual(body, {"session_id": sid, "session_status": "CONFIRMED", "membership_status": "WITHDRAWN"})

        # Replay withdraw saat sesi masih CONFIRMED -> idempotent 200 OK dengan response minimal identik (tidak membocorkan detail sesi)
        r_wd2 = self.client.post(f"/api/v1/sessions/{sid}/withdraw", headers={"Authorization": f"Bearer {self.tok_budi}"})
        self.assertEqual(r_wd2.status_code, 200)
        body2 = r_wd2.json()
        self.assertEqual(set(body2.keys()), expected_minimal_keys)
        self.assertEqual(body2, {"session_id": sid, "session_status": "CONFIRMED", "membership_status": "WITHDRAWN"})

        # Verifikasi Quorum Option A & Provenance langsung melalui database (bukan dari response withdraw)
        v_db = self.TestingSession()
        try:
            db_sess = v_db.query(StudySession).filter_by(session_id=sid).first()
            self.assertEqual(db_sess.status, "CONFIRMED")

            members = v_db.query(SessionMember).filter_by(session_id=sid).all()
            self.assertEqual(len(members), 2)
            member_statuses = {m.student_id: (m.status, m.intent_id) for m in members}
            self.assertEqual(member_statuses[self.andi.student_id], ("CONFIRMED", self.i_andi.intent_id))
            self.assertEqual(member_statuses[self.budi.student_id], ("WITHDRAWN", self.i_budi.intent_id))
            confirmed_count = sum(1 for m in members if m.status == "CONFIRMED")
            self.assertLess(confirmed_count, db_sess.min_group_size)

            # Invariant 5, 6, 8: StudyIntent Budi tetap MATCHED & tidak bisa dialokasikan ulang
            self.assertEqual(v_db.query(StudyIntent).filter_by(intent_id=self.i_budi.intent_id).first().status, "MATCHED")

            other_sess = StudySession(
                session_id="sess_reuse_check", host_id=self.doni.student_id, course_id=self.course.course_id,
                title="Sesi Lain", status="CONFIRMED",
            )
            v_db.add(other_sess)
            v_db.flush()
            v_db.add(SessionMember(
                member_id="m_illegal_reuse", session_id="sess_reuse_check", student_id=self.budi.student_id,
                intent_id=self.i_budi.intent_id, role="MEMBER", status="CONFIRMED",
            ))
            with self.assertRaises(IntegrityError):
                v_db.commit()
            v_db.rollback()
        finally:
            v_db.close()

        # Invariant 3: Host tetap dapat membatalkan sesi secara eksplisit setelah quorum turun
        r_cancel = self.client.post(f"/api/v1/sessions/{sid}/cancel", headers={"Authorization": f"Bearer {self.tok_andi}"})
        self.assertEqual(r_cancel.status_code, 200)
        self.assertEqual(r_cancel.json()["status"], "CANCELLED")

    def test_06_host_remove_member_option_a_idempotent_and_provenance_intact(self):
        """Day 22.3: Host mengeluarkan anggota (CONFIRMED -> REMOVED), sesi tetap CONFIRMED (Option A), provenance utuh."""
        sid, _ = self._execute_session_via_day21(include_citra=False, min_group_size=2)

        r1 = self.client.post(
            f"/api/v1/sessions/{sid}/members/{self.budi.student_id}/remove",
            headers={"Authorization": f"Bearer {self.tok_andi}"},
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["status"], "CONFIRMED")
        m_map = {m["student_id"]: (m["status"], m["intent_id"]) for m in r1.json()["members"]}
        self.assertEqual(m_map[self.budi.student_id], ("REMOVED", self.i_budi.intent_id))

        # Replay remove saat sesi masih CONFIRMED -> idempotent 200 OK
        r2 = self.client.post(
            f"/api/v1/sessions/{sid}/members/{self.budi.student_id}/remove",
            headers={"Authorization": f"Bearer {self.tok_andi}"},
        )
        self.assertEqual(r2.status_code, 200)

        # Verifikasi DB: StudyIntent tetap MATCHED, row tidak dihapus fisik
        v_db = self.TestingSession()
        try:
            self.assertEqual(v_db.query(SessionMember).filter_by(session_id=sid).count(), 2)
            self.assertEqual(v_db.query(StudyIntent).filter_by(intent_id=self.i_budi.intent_id).first().status, "MATCHED")
        finally:
            v_db.close()

    def test_07_host_cannot_withdraw_or_self_remove_and_membership_auth_guards(self):
        """Day 22.3: Invariant 4 (Host tidak boleh withdraw/self-remove -> 400), non-host remove -> 403, outsider withdraw -> 403, target 404."""
        sid, _ = self._execute_session_via_day21(include_citra=True)

        # Host withdraw -> 400
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/withdraw", headers={"Authorization": f"Bearer {self.tok_andi}"}).status_code,
            400,
        )
        # Host self-remove -> 400
        self.assertEqual(
            self.client.post(
                f"/api/v1/sessions/{sid}/members/{self.andi.student_id}/remove",
                headers={"Authorization": f"Bearer {self.tok_andi}"},
            ).status_code,
            400,
        )
        # Member Budi mencoba mengeluarkan Citra -> 403
        self.assertEqual(
            self.client.post(
                f"/api/v1/sessions/{sid}/members/{self.citra.student_id}/remove",
                headers={"Authorization": f"Bearer {self.tok_budi}"},
            ).status_code,
            403,
        )
        # Outsider Doni mencoba withdraw -> 403
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/withdraw", headers={"Authorization": f"Bearer {self.tok_doni}"}).status_code,
            403,
        )
        # Host mencoba mengeluarkan Doni (bukan anggota) -> 404
        self.assertEqual(
            self.client.post(
                f"/api/v1/sessions/{sid}/members/{self.doni.student_id}/remove",
                headers={"Authorization": f"Bearer {self.tok_andi}"},
            ).status_code,
            404,
        )

    def test_08_terminal_session_and_conflicting_member_transitions_rejected_409(self):
        """Day 22.3: Invariant 7 — sesi COMPLETED/CANCELLED menolak mutasi keanggotaan (409), dan konflik REMOVED vs WITHDRAWN ditolak (409)."""
        sid, _ = self._execute_session_via_day21(include_citra=True)

        # Budi withdraw -> Host tidak boleh remove Budi (konflik WITHDRAWN -> REMOVED: 409)
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/withdraw", headers={"Authorization": f"Bearer {self.tok_budi}"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/sessions/{sid}/members/{self.budi.student_id}/remove",
                headers={"Authorization": f"Bearer {self.tok_andi}"},
            ).status_code,
            409,
        )

        # Host remove Citra -> Citra tidak boleh withdraw (konflik REMOVED -> WITHDRAWN: 409)
        self.assertEqual(
            self.client.post(
                f"/api/v1/sessions/{sid}/members/{self.citra.student_id}/remove",
                headers={"Authorization": f"Bearer {self.tok_andi}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/withdraw", headers={"Authorization": f"Bearer {self.tok_citra}"}).status_code,
            409,
        )

        # Setelah Host complete sesi -> seluruh withdraw & remove ditolak 409
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/complete", headers={"Authorization": f"Bearer {self.tok_andi}"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/withdraw", headers={"Authorization": f"Bearer {self.tok_budi}"}).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/sessions/{sid}/members/{self.citra.student_id}/remove",
                headers={"Authorization": f"Bearer {self.tok_andi}"},
            ).status_code,
            409,
        )

    def test_09_detail_session_and_my_sessions_strict_authorization_policy(self):
        """Day 22.3/22.4: GET /sessions/{id} hanya untuk Host & anggota aktif (CONFIRMED/ACCEPTED); outsider, WITHDRAWN, dan REMOVED -> 403."""
        sid, _ = self._execute_session_via_day21(include_citra=True)

        # Awal: Host (Andi), Member aktif (Budi & Citra) -> 200; Outsider (Doni) -> 403
        for tok in (self.tok_andi, self.tok_budi, self.tok_citra):
            self.assertEqual(
                self.client.get(f"/api/v1/sessions/{sid}", headers={"Authorization": f"Bearer {tok}"}).status_code,
                200,
            )
        self.assertEqual(
            self.client.get(f"/api/v1/sessions/{sid}", headers={"Authorization": f"Bearer {self.tok_doni}"}).status_code,
            403,
        )

        # Budi withdraw, Citra di-remove
        self.assertEqual(
            self.client.post(f"/api/v1/sessions/{sid}/withdraw", headers={"Authorization": f"Bearer {self.tok_budi}"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/sessions/{sid}/members/{self.citra.student_id}/remove",
                headers={"Authorization": f"Bearer {self.tok_andi}"},
            ).status_code,
            200,
        )

        # Mantan anggota (WITHDRAWN & REMOVED) wajib ditolak 403 pada GET detail sesi dan hilang dari my-sessions
        self.assertEqual(
            self.client.get(f"/api/v1/sessions/{sid}", headers={"Authorization": f"Bearer {self.tok_budi}"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/sessions/{sid}", headers={"Authorization": f"Bearer {self.tok_citra}"}).status_code,
            403,
        )
        # Anti-bypass: replay POST /withdraw oleh mantan anggota WITHDRAWN tidak boleh membocorkan detail privat sesi
        r_bypass_attempt = self.client.post(
            f"/api/v1/sessions/{sid}/withdraw",
            headers={"Authorization": f"Bearer {self.tok_budi}"},
        )
        self.assertEqual(r_bypass_attempt.status_code, 200)
        bypass_body = r_bypass_attempt.json()
        self.assertEqual(set(bypass_body.keys()), {"session_id", "session_status", "membership_status"})
        for forbidden_key in ("location", "slots", "members", "course", "title", "description", "host_id"):
            self.assertNotIn(forbidden_key, bypass_body)
        # Host tetap punya akses penuh
        self.assertEqual(
            self.client.get(f"/api/v1/sessions/{sid}", headers={"Authorization": f"Bearer {self.tok_andi}"}).status_code,
            200,
        )

        budi_sessions = [s["session_id"] for s in self.client.get("/api/v1/sessions/my-sessions", headers={"Authorization": f"Bearer {self.tok_budi}"}).json()]
        citra_sessions = [s["session_id"] for s in self.client.get("/api/v1/sessions/my-sessions", headers={"Authorization": f"Bearer {self.tok_citra}"}).json()]
        andi_sessions = [s["session_id"] for s in self.client.get("/api/v1/sessions/my-sessions", headers={"Authorization": f"Bearer {self.tok_andi}"}).json()]
        self.assertNotIn(sid, budi_sessions)
        self.assertNotIn(sid, citra_sessions)
        self.assertIn(sid, andi_sessions)

    def test_09b_internal_exception_sanitization_no_raw_db_leak(self):
        """Day 22 Hardening (P2): Error DB/internal tidak pernah membocorkan SQL/stack detail ke client & dicatat ke server logger."""
        from unittest.mock import patch
        from sqlalchemy.exc import OperationalError
        from sqlalchemy.orm import Session as SASession
        import app.session_lifecycle_service as lc_mod

        sid, _ = self._execute_session_via_day21(include_citra=True)
        sensitive_marker = "SECRET_SQL_TABLE_session_members_disk_io_failure_991"

        def failing_non_lock_commit(_sess_self):
            raise OperationalError(
                "UPDATE session_members SET status='WITHDRAWN'",
                {},
                sqlite3.OperationalError(sensitive_marker),
            )

        endpoints = [
            ("complete", f"/api/v1/sessions/{sid}/complete", self.tok_andi),
            ("withdraw", f"/api/v1/sessions/{sid}/withdraw", self.tok_budi),
            ("remove", f"/api/v1/sessions/{sid}/members/{self.citra.student_id}/remove", self.tok_andi),
        ]

        for label, url, tok in endpoints:
            with self.subTest(endpoint=label):
                with patch.object(SASession, "commit", new=failing_non_lock_commit):
                    with patch.object(lc_mod.logger, "exception") as mock_log:
                        r = self.client.post(url, headers={"Authorization": f"Bearer {tok}"})
                self.assertEqual(r.status_code, 500)
                detail = r.json()["detail"]
                self.assertEqual(detail, lc_mod._GENERIC_INTERNAL_ERROR_DETAIL)
                self.assertNotIn(sensitive_marker, detail)
                self.assertNotIn("UPDATE session_members", detail)
                self.assertEqual(mock_log.call_count, 1)


class TestDay22LifecycleConcurrencyAndLockRecovery(unittest.TestCase):
    """Day 22.4: Concurrency Race Conditions & Real SQLite Physical Lock Recovery (DELETE & WAL + Retry Budget)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="lafriend_day22_")
        self._counter = 0

    def tearDown(self):
        self._tmpdir.cleanup()

    def _create_file_db(self, busy_timeout_ms: int = 5000, journal_mode: str = "WAL"):
        self._counter += 1
        db_file = Path(self._tmpdir.name) / f"lafriend_d22_{self._counter}.db"
        db_url = f"sqlite:///{db_file.as_posix()}"
        eng = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": max(0.05, busy_timeout_ms / 1000.0)},
            poolclass=NullPool,
        )

        @event.listens_for(eng, "connect")
        def _cfg(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            cur.close()

        with eng.connect() as conn:
            conn.execute(text(f"PRAGMA journal_mode={journal_mode}"))
            conn.commit()

        ensure_database_schema(eng)
        return db_file, db_url, eng

    def _open_verify_session(self, db_url: str):
        v_eng = create_engine(db_url, connect_args={"check_same_thread": False, "timeout": 5}, poolclass=NullPool)
        return v_eng, sessionmaker(autocommit=False, autoflush=False, bind=v_eng)()

    def _seed_confirmed_session(self, eng, session_id: str = "SESS-CONC-1"):
        SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = SessionFactory()
        try:
            now = datetime.utcnow()
            c = Course(course_id="c_d22c", course_code="ACK4C", course_name="Concurrency", study_program="TK")
            h = Student(student_id="s_host", full_name="Host", email="h@t.ac.id", student_number="6001", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True)
            m = Student(student_id="s_mem", full_name="Member", email="m@t.ac.id", student_number="6002", password_hash="pw", verification_status="VERIFIED", account_status="ACTIVE", is_discoverable=True)
            ih = StudyIntent(intent_id="i_host", student_id="s_host", course_id="c_d22c", topics="Locks", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=2, max_group_size=4, status="MATCHED")
            im = StudyIntent(intent_id="i_mem", student_id="s_mem", course_id="c_d22c", topics="Locks", learning_mode="ONLINE", earliest_date="2026-11-20", latest_date="2026-11-30", min_group_size=2, max_group_size=4, status="MATCHED")
            prop = GroupProposal(
                proposal_id=f"p_{session_id}", host_intent_id="i_host", host_student_id="s_host", course_id="c_d22c",
                status="SESSION_EXECUTED", min_group_size_bound=2, max_group_size_bound=4,
                selected_schedule_json=json.dumps({"date": "2026-11-29", "start_time": "10:00", "end_time": "12:00"}),
                expires_at=now + timedelta(hours=24), created_at=now, updated_at=now, finalized_at=now,
            )
            sess = StudySession(
                session_id=session_id, proposal_id=prop.proposal_id, host_id="s_host", course_id="c_d22c",
                title="Sesi Concurrency Day 22", min_group_size=2, max_group_size=4, status="CONFIRMED",
                created_at=now, updated_at=now,
            )
            slot = SessionSlot(slot_id=f"slot_{session_id}", session_id=session_id, session_date="2026-11-29", start_time="10:00", end_time="12:00", status="APPROVED")
            mh = SessionMember(member_id=f"mh_{session_id}", session_id=session_id, student_id="s_host", intent_id="i_host", role="HOST", status="CONFIRMED", joined_at=now)
            mm = SessionMember(member_id=f"mm_{session_id}", session_id=session_id, student_id="s_mem", intent_id="i_mem", role="MEMBER", status="CONFIRMED", joined_at=now)
            db.add_all([c, h, m, ih, im, prop, sess, slot, mh, mm])
            db.commit()
        finally:
            db.close()

    def test_10_concurrent_host_complete_vs_cancel_race(self):
        """Day 22.4: Host menjalankan complete & cancel bersamaan (mode DELETE & WAL) -> tepat 1 menang (COMPLETED/CANCELLED), 1 ditolak 409."""
        for journal_mode in ("DELETE", "WAL"):
            with self.subTest(journal_mode=journal_mode):
                _, db_url, eng = self._create_file_db(journal_mode=journal_mode)
                try:
                    self._seed_confirmed_session(eng, "SESS-RACE-CC")
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
                    barrier = Barrier(2)
                    outcomes = {}

                    def run_op(name: str, fn):
                        db = SessionFactory()
                        try:
                            host = db.query(Student).filter_by(student_id="s_host").first()
                            barrier.wait(timeout=10)
                            resp = fn(db, "SESS-RACE-CC", host)
                            outcomes[name] = ("SUCCESS", resp.status)
                        except HTTPException as he:
                            outcomes[name] = ("HTTP_ERROR", he.status_code)
                        except Exception as exc:
                            outcomes[name] = ("UNEXPECTED", exc)
                        finally:
                            db.close()

                    t1 = Thread(target=run_op, args=("complete", complete_study_session_service))
                    t2 = Thread(target=run_op, args=("cancel", cancel_study_session_service))
                    t1.start()
                    t2.start()
                    t1.join(timeout=15)
                    t2.join(timeout=15)
                    self.assertFalse(t1.is_alive())
                    self.assertFalse(t2.is_alive())

                    winners = [k for k, v in outcomes.items() if v[0] == "SUCCESS"]
                    losers = [k for k, v in outcomes.items() if v[0] == "HTTP_ERROR"]
                    self.assertEqual(len(winners), 1, f"Wajib tepat 1 pemenang terminal: {outcomes}")
                    self.assertEqual(len(losers), 1, f"Wajib tepat 1 ditolak 409: {outcomes}")
                    self.assertEqual(outcomes[losers[0]][1], 409)

                    expected_status = "COMPLETED" if winners[0] == "complete" else "CANCELLED"
                    v_eng, v_db = self._open_verify_session(db_url)
                    try:
                        self.assertEqual(v_db.query(StudySession).filter_by(session_id="SESS-RACE-CC").first().status, expected_status)
                        self.assertEqual(v_db.query(SessionMember).filter_by(session_id="SESS-RACE-CC").count(), 2)
                        self.assertEqual(v_db.query(StudyIntent).filter_by(intent_id="i_mem").first().status, "MATCHED")
                    finally:
                        v_db.close()
                        v_eng.dispose()
                finally:
                    eng.dispose()

    def test_11_concurrent_host_cancel_vs_member_withdraw_race(self):
        """Day 22.4: Host cancel bersamaan dengan Member withdraw (mode DELETE & WAL) -> serialisasi konsisten tanpa kehilangan provenance."""
        for journal_mode in ("DELETE", "WAL"):
            with self.subTest(journal_mode=journal_mode):
                _, db_url, eng = self._create_file_db(journal_mode=journal_mode)
                try:
                    self._seed_confirmed_session(eng, "SESS-RACE-CW")
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
                    barrier = Barrier(2)
                    outcomes = {}

                    def run_cancel():
                        db = SessionFactory()
                        try:
                            host = db.query(Student).filter_by(student_id="s_host").first()
                            barrier.wait(timeout=10)
                            resp = cancel_study_session_service(db, "SESS-RACE-CW", host)
                            outcomes["cancel"] = ("SUCCESS", resp.status)
                        except HTTPException as he:
                            outcomes["cancel"] = ("HTTP_ERROR", he.status_code)
                        finally:
                            db.close()

                    def run_withdraw():
                        db = SessionFactory()
                        try:
                            mem = db.query(Student).filter_by(student_id="s_mem").first()
                            barrier.wait(timeout=10)
                            resp = withdraw_from_study_session_service(db, "SESS-RACE-CW", mem)
                            outcomes["withdraw"] = ("SUCCESS", resp.membership_status)
                        except HTTPException as he:
                            outcomes["withdraw"] = ("HTTP_ERROR", he.status_code)
                        finally:
                            db.close()

                    t1 = Thread(target=run_cancel)
                    t2 = Thread(target=run_withdraw)
                    t1.start()
                    t2.start()
                    t1.join(timeout=15)
                    t2.join(timeout=15)
                    self.assertFalse(t1.is_alive())
                    self.assertFalse(t2.is_alive())

                    self.assertEqual(outcomes["cancel"], ("SUCCESS", "CANCELLED"))
                    self.assertIn(outcomes["withdraw"][0], ("SUCCESS", "HTTP_ERROR"))
                    if outcomes["withdraw"][0] == "HTTP_ERROR":
                        self.assertEqual(outcomes["withdraw"][1], 409)

                    v_eng, v_db = self._open_verify_session(db_url)
                    try:
                        self.assertEqual(v_db.query(StudySession).filter_by(session_id="SESS-RACE-CW").first().status, "CANCELLED")
                        mem_row = v_db.query(SessionMember).filter_by(session_id="SESS-RACE-CW", student_id="s_mem").first()
                        self.assertIsNotNone(mem_row)
                        self.assertEqual(mem_row.intent_id, "i_mem")
                        if outcomes["withdraw"][0] == "SUCCESS":
                            self.assertEqual(mem_row.status, "WITHDRAWN")
                        else:
                            self.assertEqual(mem_row.status, "CONFIRMED")
                        self.assertEqual(v_db.query(StudyIntent).filter_by(intent_id="i_mem").first().status, "MATCHED")
                    finally:
                        v_db.close()
                        v_eng.dispose()
                finally:
                    eng.dispose()

    def test_12_concurrent_member_withdraw_vs_host_remove_race(self):
        """Day 22.4: Member withdraw bersamaan dengan Host remove (mode DELETE & WAL) -> tepat 1 menang (WITHDRAWN/REMOVED), 1 ditolak 409."""
        for journal_mode in ("DELETE", "WAL"):
            with self.subTest(journal_mode=journal_mode):
                _, db_url, eng = self._create_file_db(journal_mode=journal_mode)
                try:
                    self._seed_confirmed_session(eng, "SESS-RACE-WR")
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
                    barrier = Barrier(2)
                    outcomes = {}

                    def run_withdraw():
                        db = SessionFactory()
                        try:
                            mem = db.query(Student).filter_by(student_id="s_mem").first()
                            barrier.wait(timeout=10)
                            resp = withdraw_from_study_session_service(db, "SESS-RACE-WR", mem)
                            outcomes["withdraw"] = ("SUCCESS", resp.membership_status)
                        except HTTPException as he:
                            outcomes["withdraw"] = ("HTTP_ERROR", he.status_code)
                        finally:
                            db.close()

                    def run_remove():
                        db = SessionFactory()
                        try:
                            host = db.query(Student).filter_by(student_id="s_host").first()
                            barrier.wait(timeout=10)
                            remove_member_from_study_session_service(db, "SESS-RACE-WR", "s_mem", host)
                            outcomes["remove"] = ("SUCCESS", "REMOVED")
                        except HTTPException as he:
                            outcomes["remove"] = ("HTTP_ERROR", he.status_code)
                        finally:
                            db.close()

                    t1 = Thread(target=run_withdraw)
                    t2 = Thread(target=run_remove)
                    t1.start()
                    t2.start()
                    t1.join(timeout=15)
                    t2.join(timeout=15)
                    self.assertFalse(t1.is_alive())
                    self.assertFalse(t2.is_alive())

                    winners = [k for k, v in outcomes.items() if v[0] == "SUCCESS"]
                    losers = [k for k, v in outcomes.items() if v[0] == "HTTP_ERROR"]
                    self.assertEqual(len(winners), 1, f"Wajib tepat 1 pemenang status anggota: {outcomes}")
                    self.assertEqual(len(losers), 1, f"Wajib tepat 1 ditolak 409: {outcomes}")
                    self.assertEqual(outcomes[losers[0]][1], 409)

                    expected_mem_status = "WITHDRAWN" if winners[0] == "withdraw" else "REMOVED"
                    v_eng, v_db = self._open_verify_session(db_url)
                    try:
                        # Option A: StudySession tetap CONFIRMED
                        self.assertEqual(v_db.query(StudySession).filter_by(session_id="SESS-RACE-WR").first().status, "CONFIRMED")
                        mem_row = v_db.query(SessionMember).filter_by(session_id="SESS-RACE-WR", student_id="s_mem").first()
                        self.assertEqual(mem_row.status, expected_mem_status)
                        self.assertEqual(mem_row.intent_id, "i_mem")
                        self.assertEqual(v_db.query(StudyIntent).filter_by(intent_id="i_mem").first().status, "MATCHED")
                    finally:
                        v_db.close()
                        v_eng.dispose()
                finally:
                    eng.dispose()

    def test_13_real_sqlite_lock_recovery_exhaustion_and_wall_clock_budget(self):
        """Day 22.4: Lock fisik SQLite nyata (DELETE & WAL) pulih saat dilepas, fail-closed 409 saat exhausted, & patuh bounded SQLite lock-wait budget."""
        import time

        # A. Lock dilepas setelah rollback pertama -> complete berhasil (uji pada DELETE & WAL)
        for journal_mode in ("DELETE", "WAL"):
            with self.subTest(lock_recovery_mode=journal_mode):
                db_file_a, _, eng_a = self._create_file_db(busy_timeout_ms=25, journal_mode=journal_mode)
                lock_conn_a = sqlite3.connect(str(db_file_a), isolation_level=None, timeout=5.0)
                try:
                    self._seed_confirmed_session(eng_a, "SESS-LOCK-REC")
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_a)
                    real_locks = []
                    rolled_back = Event()

                    @event.listens_for(eng_a, "handle_error")
                    def _cap_lock(ctx):
                        if "database is locked" in str(ctx.original_exception).lower():
                            real_locks.append(1)

                    @event.listens_for(SessionFactory, "after_rollback")
                    def _on_rb(_sess):
                        if real_locks:
                            rolled_back.set()

                    lock_conn_a.execute("BEGIN IMMEDIATE")
                    res = {"resp": None, "err": None}

                    def worker():
                        db = SessionFactory()
                        try:
                            host = db.query(Student).filter_by(student_id="s_host").first()
                            res["resp"] = complete_study_session_service(db, "SESS-LOCK-REC", host)
                        except Exception as exc:
                            res["err"] = exc
                        finally:
                            db.close()

                    t = Thread(target=worker)
                    t.start()
                    self.assertTrue(rolled_back.wait(timeout=5.0))
                    lock_conn_a.execute("COMMIT")
                    t.join(timeout=10.0)
                    self.assertFalse(t.is_alive())

                    self.assertIsNone(res["err"])
                    self.assertEqual(res["resp"].status, "COMPLETED")
                    self.assertGreaterEqual(len(real_locks), 1)
                finally:
                    lock_conn_a.close()
                    eng_a.dispose()

        # B. Pengujian konfigurasi produksi aktual (persis database.py: default timeout 5000ms, mode DELETE, TANPA patch budget):
        # Membuktikan _sqlite_bounded_busy_timeout benar-benar memotong penantian default 5 detik SQLite
        # agar penantian lock SQLite patuh pada bounded lock-wait budget 2 detik dan busy_timeout koneksi dipulihkan ke 5000ms.
        self._counter += 1
        prod_db_file = Path(self._tmpdir.name) / f"lafriend_d22_prod_bt_{self._counter}.db"
        prod_db_url = f"sqlite:///{prod_db_file.as_posix()}"
        # Persis seperti database.py: connect_args={"check_same_thread": False} tanpa override timeout (default Python sqlite3 = 5000ms)
        eng_prod = create_engine(prod_db_url, connect_args={"check_same_thread": False})

        @event.listens_for(eng_prod, "connect")
        def _prod_fk(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        ensure_database_schema(eng_prod)
        lock_conn_b = sqlite3.connect(str(prod_db_file), isolation_level=None, timeout=5.0)
        try:
            self._seed_confirmed_session(eng_prod, "SESS-LOCK-PROD-2S")
            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_prod)

            # Pastikan engine memang memiliki default busy_timeout 5000ms (5 detik) sebelum eksekusi
            with eng_prod.connect() as chk_conn:
                default_bt = chk_conn.execute(text("PRAGMA busy_timeout")).scalar()
                self.assertGreaterEqual(int(default_bt), 5000)

            lock_conn_b.execute("BEGIN IMMEDIATE")
            t0 = time.monotonic()
            try:
                db = SessionFactory()
                try:
                    mem = db.query(Student).filter_by(student_id="s_mem").first()
                    with self.assertRaises(HTTPException) as ctx:
                        withdraw_from_study_session_service(db, "SESS-LOCK-PROD-2S", mem)
                    self.assertEqual(ctx.exception.status_code, 409)
                finally:
                    db.close()
            finally:
                lock_conn_b.execute("ROLLBACK")
            elapsed = time.monotonic() - t0

            # Bukti nyata bounded SQLite lock-wait budget (2.0s): meskipun driver sqlite3 default 5.0s,
            # penantian lock terpotong jauh di bawah 5.0s (dengan toleransi kecil overhead Python/OS)
            self.assertLess(
                elapsed,
                2.5,
                f"Bounded SQLite lock-wait budget (2s) wajib membatasi tunggu SQLite default 5s, aktual: {elapsed:.3f}s",
            )

            # Pastikan PRAGMA busy_timeout koneksi pool dipulihkan ke nilai awal (5000ms)
            with eng_prod.connect() as chk_after:
                restored_bt = chk_after.execute(text("PRAGMA busy_timeout")).scalar()
                self.assertEqual(int(restored_bt), int(default_bt))

            v_eng, v_db = self._open_verify_session(prod_db_url)
            try:
                self.assertEqual(v_db.query(StudySession).filter_by(session_id="SESS-LOCK-PROD-2S").first().status, "CONFIRMED")
                self.assertEqual(v_db.query(SessionMember).filter_by(session_id="SESS-LOCK-PROD-2S", student_id="s_mem").first().status, "CONFIRMED")
            finally:
                v_db.close()
                v_eng.dispose()
        finally:
            lock_conn_b.close()
            eng_prod.dispose()

    def test_14_pool_busy_timeout_restored_after_successful_commit_and_invalidation_on_failure(self):
        """Day 22.4 (P1): Memastikan PRAGMA busy_timeout=5000 dipulihkan pasca commit sukses (complete/cancel/withdraw/remove) pada QueuePool(pool_size=1, max_overflow=0), dan koneksi di-invalidasi jika restorasi gagal."""
        from unittest.mock import patch
        from sqlalchemy.pool import QueuePool
        import app.session_lifecycle_service as lc_mod

        def _make_single_conn_pool_engine(tag: str):
            self._counter += 1
            db_file = Path(self._tmpdir.name) / f"lafriend_d22_pool_{tag}_{self._counter}.db"
            db_url = f"sqlite:///{db_file.as_posix()}"
            eng = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=QueuePool,
                pool_size=1,
                max_overflow=0,
            )

            @event.listens_for(eng, "connect")
            def _fk(dbapi_conn, _conn_record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

            ensure_database_schema(eng)
            return eng

        # --- Bagian A: Verifikasi pemulihan busy_timeout=5000 pada SEMUA 4 jalur commit sukses ---
        success_ops = [
            ("complete", lambda db, sid: complete_study_session_service(db, sid, db.query(Student).filter_by(student_id="s_host").first()), "COMPLETED"),
            ("cancel", lambda db, sid: cancel_study_session_service(db, sid, db.query(Student).filter_by(student_id="s_host").first()), "CANCELLED"),
            ("withdraw", lambda db, sid: withdraw_from_study_session_service(db, sid, db.query(Student).filter_by(student_id="s_mem").first()), "WITHDRAWN"),
            ("remove", lambda db, sid: remove_member_from_study_session_service(db, sid, "s_mem", db.query(Student).filter_by(student_id="s_host").first()), "REMOVED"),
        ]

        for op_name, op_fn, expected_val in success_ops:
            with self.subTest(successful_commit_op=op_name):
                eng = _make_single_conn_pool_engine(op_name)
                try:
                    sid = f"SESS-POOL-{op_name.upper()}"
                    self._seed_confirmed_session(eng, sid)

                    # Catat identitas koneksi fisik tunggal & busy_timeout awal (5000ms)
                    with eng.connect() as pre_conn:
                        raw_id_before = id(pre_conn.connection.dbapi_connection)
                        bt_before = int(pre_conn.execute(text("PRAGMA busy_timeout")).scalar())
                    self.assertEqual(bt_before, 5000)

                    # Eksekusi operasi lifecycle sampai commit sukses, lalu tutup Session
                    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
                    db = SessionFactory()
                    try:
                        resp = op_fn(db, sid)
                        actual_val = resp.membership_status if op_name == "withdraw" else resp.status
                        if op_name == "remove":
                            actual_val = next(m.status for m in resp.members if m.student_id == "s_mem")
                        self.assertEqual(actual_val, expected_val)
                    finally:
                        db.close()

                    # Checkout berikutnya dari single-connection pool WAJIB memakai ulang koneksi fisik yg sama dg busy_timeout=5000
                    with eng.connect() as post_conn:
                        raw_id_after = id(post_conn.connection.dbapi_connection)
                        bt_after = int(post_conn.execute(text("PRAGMA busy_timeout")).scalar())

                    self.assertEqual(
                        raw_id_after,
                        raw_id_before,
                        f"QueuePool(pool_size=1, max_overflow=0) wajib memakai ulang koneksi fisik yang sama pada {op_name}",
                    )
                    self.assertEqual(
                        bt_after,
                        5000,
                        f"PRAGMA busy_timeout pada koneksi pool bocor setelah commit sukses {op_name}: {bt_after} != 5000",
                    )
                finally:
                    eng.dispose()

        # --- Bagian B: Kegagalan restorasi PRAGMA wajib meng-invalidasi koneksi agar tidak kembali kotor ke pool ---
        eng_inv = _make_single_conn_pool_engine("invalidate")
        try:
            sid_inv = "SESS-POOL-INV"
            self._seed_confirmed_session(eng_inv, sid_inv)

            with eng_inv.connect() as pre_conn:
                old_raw_id = id(pre_conn.connection.dbapi_connection)
                self.assertEqual(int(pre_conn.execute(text("PRAGMA busy_timeout")).scalar()), 5000)

            orig_setter = lc_mod._set_sqlite_busy_timeout

            def fail_only_on_restore(raw_conn, timeout_ms: int):
                if int(timeout_ms) == 5000:
                    raise sqlite3.OperationalError("simulated pragma restore failure")
                return orig_setter(raw_conn, timeout_ms)

            SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng_inv)
            db = SessionFactory()
            try:
                host = db.query(Student).filter_by(student_id="s_host").first()
                with patch.object(lc_mod, "_set_sqlite_busy_timeout", side_effect=fail_only_on_restore):
                    with patch.object(lc_mod.logger, "exception") as mock_log:
                        resp = complete_study_session_service(db, sid_inv, host)
                self.assertEqual(resp.status, "COMPLETED")
                self.assertGreaterEqual(mock_log.call_count, 1)
            finally:
                db.close()

            # Checkout berikutnya WAJIB menerima koneksi fisik BARU (koneksi kotor telah di-invalidasi) dengan busy_timeout=5000
            with eng_inv.connect() as post_conn:
                new_raw_id = id(post_conn.connection.dbapi_connection)
                bt_fresh = int(post_conn.execute(text("PRAGMA busy_timeout")).scalar())

            self.assertNotEqual(
                new_raw_id,
                old_raw_id,
                "Koneksi fisik yang gagal memulihkan PRAGMA busy_timeout wajib di-invalidasi, bukan dipakai ulang",
            )
            self.assertEqual(bt_fresh, 5000)
        finally:
            eng_inv.dispose()


if __name__ == "__main__":
    unittest.main()

