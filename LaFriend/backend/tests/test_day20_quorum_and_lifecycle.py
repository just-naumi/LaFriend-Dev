# ==============================================================================
# tests/test_day20_quorum_and_lifecycle.py
# ==============================================================================
# Test Suite Day 20.4 & 20.5: Dynamic Quorum Calculation & Proposal Lifecycle
# Memvalidasi formula kuorum dinamis (QUORUM_REACHED vs PENDING_RESPONSES vs NOT_FORMED),
# pembatalan proposal oleh host, serta transisi penarikan undangan (WITHDRAWN).
# ==============================================================================

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import unittest
from datetime import datetime, timedelta
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db, ensure_database_schema
from app.models import Student, Course, StudyIntent, IntentAvailability, GroupProposal, Invitation
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


class TestDay20QuorumAndLifecycle(unittest.TestCase):
    """Test suite untuk perhitungan kuorum dinamis dan siklus hidup proposal."""

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
            course_id="c_d20_ql",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.db.add(self.course)

        # Host Andi (min 3, max 4)
        self.andi = Student(
            student_id="s_andi_ql",
            full_name="Andi Pratama",
            email="andi.ql@telkomuniversity.ac.id",
            student_number="1201250021",
            password_hash="hashed_pw_andi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.andi)

        # Kandidat 1: Budi (min 3, max 4)
        self.budi = Student(
            student_id="s_budi_ql",
            full_name="Budi Santoso",
            email="budi.ql@telkomuniversity.ac.id",
            student_number="1201250022",
            password_hash="hashed_pw_budi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.budi)

        # Kandidat 2: Dono (min 3, max 4)
        self.dono = Student(
            student_id="s_dono_ql",
            full_name="Dono Kasino",
            email="dono.ql@telkomuniversity.ac.id",
            student_number="1201250023",
            password_hash="hashed_pw_dono",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.dono)

        # Pihak luar Citra
        self.citra = Student(
            student_id="s_citra_ql",
            full_name="Citra Lestari",
            email="citra.ql@telkomuniversity.ac.id",
            student_number="1201250024",
            password_hash="hashed_pw_citra",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.citra)

        # Intents
        self.intent_andi = StudyIntent(
            intent_id="i_andi_ql",
            student_id=self.andi.student_id,
            course_id=self.course.course_id,
            topics="Graph",
            learning_goal="PRACTICE",
            collaboration_style="DISCUSSION",
            learning_mode="OFFLINE",
            min_group_size=3,
            max_group_size=4,
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            status="ACTIVE"
        )
        self.db.add(self.intent_andi)

        self.intent_budi = StudyIntent(
            intent_id="i_budi_ql",
            student_id=self.budi.student_id,
            course_id=self.course.course_id,
            topics="Graph",
            learning_goal="PRACTICE",
            collaboration_style="DISCUSSION",
            learning_mode="OFFLINE",
            min_group_size=3,
            max_group_size=4,
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            status="ACTIVE"
        )
        self.db.add(self.intent_budi)

        self.intent_dono = StudyIntent(
            intent_id="i_dono_ql",
            student_id=self.dono.student_id,
            course_id=self.course.course_id,
            topics="Graph",
            learning_goal="PRACTICE",
            collaboration_style="DISCUSSION",
            learning_mode="OFFLINE",
            min_group_size=3,
            max_group_size=4,
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            status="ACTIVE"
        )
        self.db.add(self.intent_dono)

        # Buat Proposal Group (Min: 3, Max: 4)
        self.proposal = GroupProposal(
            proposal_id="prop_ql_1",
            host_intent_id=self.intent_andi.intent_id,
            host_student_id=self.andi.student_id,
            course_id=self.course.course_id,
            status="PENDING_RESPONSES",
            min_group_size_bound=3,
            max_group_size_bound=4,
            group_quality_score=88.0,
            average_pair_score=88.0,
            minimum_pair_score=88.0,
            selected_schedule_json='{"date":"2026-11-25","start_time":"10:00","end_time":"12:00","duration_minutes":120}',
            expires_at=datetime.utcnow() + timedelta(hours=24),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(self.proposal)

        # Undangan untuk Budi dan Dono
        self.inv_budi = Invitation(
            invitation_id="inv_budi_ql",
            invitation_type="PARTNER_INVITE",
            sender_id=self.andi.student_id,
            recipient_id=self.budi.student_id,
            target_intent_id=self.intent_budi.intent_id,
            proposal_id=self.proposal.proposal_id,
            status="PENDING",
            created_at=datetime.utcnow()
        )
        self.db.add(self.inv_budi)

        self.inv_dono = Invitation(
            invitation_id="inv_dono_ql",
            invitation_type="PARTNER_INVITE",
            sender_id=self.andi.student_id,
            recipient_id=self.dono.student_id,
            target_intent_id=self.intent_dono.intent_id,
            proposal_id=self.proposal.proposal_id,
            status="PENDING",
            created_at=datetime.utcnow()
        )
        self.db.add(self.inv_dono)

        self.db.commit()

        self.token_andi = create_token(self.andi.student_id, self.andi.email)
        self.token_budi = create_token(self.budi.student_id, self.budi.email)
        self.token_dono = create_token(self.dono.student_id, self.dono.email)
        self.token_citra = create_token(self.citra.student_id, self.citra.email)

        self.headers_andi = {"Authorization": f"Bearer {self.token_andi}"}
        self.headers_budi = {"Authorization": f"Bearer {self.token_budi}"}
        self.headers_dono = {"Authorization": f"Bearer {self.token_dono}"}
        self.headers_citra = {"Authorization": f"Bearer {self.token_citra}"}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        app.dependency_overrides = self.original_overrides

    def test_01_quorum_stepwise_reached_when_all_accept(self):
        """Kuorum bertahap: PENDING -> ACCEPT (1) masih PENDING -> ACCEPT (2) menjadi QUORUM_REACHED."""
        # Awal: 1 aktif (Andi), butuh min 3
        self.db.expire_all()
        prop = self.db.query(GroupProposal).filter(GroupProposal.proposal_id == self.proposal.proposal_id).first()
        self.assertEqual(prop.status, "PENDING_RESPONSES")

        # 1. Budi menerima (aktif = 2, pending = 1, butuh min 3) -> tetap PENDING_RESPONSES
        r1 = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json={"decision": "ACCEPT"},
            headers=self.headers_budi
        )
        self.assertEqual(r1.status_code, 200)

        self.db.expire_all()
        prop1 = self.db.query(GroupProposal).filter(GroupProposal.proposal_id == self.proposal.proposal_id).first()
        self.assertEqual(prop1.status, "PENDING_RESPONSES")

        # 2. Dono menerima (aktif = 3, pending = 0, min 3 terpenuhi: 3 <= 3 <= 4) -> QUORUM_REACHED
        r2 = self.client.post(
            f"/api/v1/invitations/{self.inv_dono.invitation_id}/respond",
            json={"decision": "ACCEPT"},
            headers=self.headers_dono
        )
        self.assertEqual(r2.status_code, 200)

        self.db.expire_all()
        prop2 = self.db.query(GroupProposal).filter(GroupProposal.proposal_id == self.proposal.proposal_id).first()
        self.assertEqual(prop2.status, "QUORUM_REACHED")

        # Cek response detail proposal via API
        r_detail = self.client.get(f"/api/v1/matching/group-proposals/{self.proposal.proposal_id}", headers=self.headers_andi)
        self.assertEqual(r_detail.status_code, 200)
        self.assertEqual(r_detail.json()["status"], "QUORUM_REACHED")
        self.assertEqual(r_detail.json()["active_member_count"], 3)
        self.assertTrue(r_detail.json()["quorum_reached"])

    def test_02_quorum_fails_and_transitions_to_not_formed(self):
        """Jika kandidat menolak sehingga kuorum minimal tidak tercapai, status proposal menjadi NOT_FORMED."""
        # 1. Budi menerima (aktif = 2)
        self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json={"decision": "ACCEPT"},
            headers=self.headers_budi
        )

        # 2. Dono menolak (sisa pending = 0, aktif = 2 < 3) -> NOT_FORMED
        r_dec = self.client.post(
            f"/api/v1/invitations/{self.inv_dono.invitation_id}/respond",
            json={"decision": "DECLINE", "reason": "Sibuk proyek lain"},
            headers=self.headers_dono
        )
        self.assertEqual(r_dec.status_code, 200)

        self.db.expire_all()
        prop = self.db.query(GroupProposal).filter(GroupProposal.proposal_id == self.proposal.proposal_id).first()
        self.assertEqual(prop.status, "NOT_FORMED")

        # Verifikasi via API
        r_detail = self.client.get(f"/api/v1/matching/group-proposals/{self.proposal.proposal_id}", headers=self.headers_andi)
        self.assertEqual(r_detail.json()["status"], "NOT_FORMED")
        self.assertFalse(r_detail.json()["quorum_reached"])

    def test_03_host_cancel_proposal_withdraws_pending_invitations(self):
        """Host membatalkan proposal -> status proposal menjadi CANCELLED dan sisa undangan PENDING menjadi WITHDRAWN."""
        r_cancel = self.client.post(
            f"/api/v1/matching/group-proposals/{self.proposal.proposal_id}/cancel",
            json={"reason": "Jadwal host berubah"},
            headers=self.headers_andi
        )
        self.assertEqual(r_cancel.status_code, 200)
        self.assertEqual(r_cancel.json()["status"], "CANCELLED")

        self.db.expire_all()
        # Seluruh undangan PENDING harus menjadi WITHDRAWN
        invs = self.db.query(Invitation).filter(Invitation.proposal_id == self.proposal.proposal_id).all()
        for inv in invs:
            self.assertEqual(inv.status, "WITHDRAWN")

        # Kandidat mencoba menerima undangan yang sudah WITHDRAWN -> HTTP 400
        r_resp = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json={"decision": "ACCEPT"},
            headers=self.headers_budi
        )
        self.assertEqual(r_resp.status_code, 400)
        self.assertIn("sudah berstatus 'WITHDRAWN'", r_resp.json()["detail"])

    def test_04_cancel_proposal_cross_student_forbidden(self):
        """Budi (bukan host) mencoba membatalkan proposal -> HTTP 403 Forbidden."""
        r_cancel = self.client.post(
            f"/api/v1/matching/group-proposals/{self.proposal.proposal_id}/cancel",
            headers=self.headers_budi
        )
        self.assertEqual(r_cancel.status_code, 403)
        self.assertIn("Hanya host pembuat proposal yang berhak", r_cancel.json()["detail"])


if __name__ == "__main__":
    unittest.main()
