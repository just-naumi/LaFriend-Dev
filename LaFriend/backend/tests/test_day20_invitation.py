# ==============================================================================
# tests/test_day20_invitation.py
# ==============================================================================
# Test Suite Day 20.3 & 20.4: Invitation Management & Response Handling
# Memvalidasi alur inbox/sent, respon penerimaan/penolakan, proteksi idempotensi,
# otorisasi kepemilikan undangan, dan penolakan perubahan keputusan.
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


class TestDay20Invitation(unittest.TestCase):
    """Test suite untuk pengelolaan dan respon Invitation (Day 20.3 & Day 20.4)."""

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
            course_id="c_d20_inv",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.db.add(self.course)

        # Host Andi
        self.andi = Student(
            student_id="s_andi_inv",
            full_name="Andi Pratama",
            email="andi.inv@telkomuniversity.ac.id",
            student_number="1201250011",
            password_hash="hashed_pw_andi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.andi)

        # Kandidat Budi
        self.budi = Student(
            student_id="s_budi_inv",
            full_name="Budi Santoso",
            email="budi.inv@telkomuniversity.ac.id",
            student_number="1201250012",
            password_hash="hashed_pw_budi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.budi)

        # Pihak Ketiga Citra
        self.citra = Student(
            student_id="s_citra_inv",
            full_name="Citra Lestari",
            email="citra.inv@telkomuniversity.ac.id",
            student_number="1201250013",
            password_hash="hashed_pw_citra",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.citra)

        # Intent Andi (Host)
        self.intent_andi = StudyIntent(
            intent_id="i_andi_inv",
            student_id=self.andi.student_id,
            course_id=self.course.course_id,
            topics="Tree",
            learning_goal="PRACTICE",
            collaboration_style="DISCUSSION",
            learning_mode="OFFLINE",
            min_group_size=2,
            max_group_size=4,
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            status="ACTIVE"
        )
        self.db.add(self.intent_andi)

        # Intent Budi
        self.intent_budi = StudyIntent(
            intent_id="i_budi_inv",
            student_id=self.budi.student_id,
            course_id=self.course.course_id,
            topics="Tree",
            learning_goal="PRACTICE",
            collaboration_style="DISCUSSION",
            learning_mode="OFFLINE",
            min_group_size=2,
            max_group_size=4,
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            status="ACTIVE"
        )
        self.db.add(self.intent_budi)

        # Buat Proposal Group
        self.proposal = GroupProposal(
            proposal_id="prop_test_inv_1",
            host_intent_id=self.intent_andi.intent_id,
            host_student_id=self.andi.student_id,
            course_id=self.course.course_id,
            status="PENDING_RESPONSES",
            min_group_size_bound=2,
            max_group_size_bound=4,
            group_quality_score=85.0,
            average_pair_score=85.0,
            minimum_pair_score=85.0,
            selected_schedule_json='{"date":"2026-11-25","start_time":"10:00","end_time":"12:00","duration_minutes":120}',
            expires_at=datetime.utcnow() + timedelta(hours=24),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(self.proposal)

        # Undangan untuk Budi
        self.inv_budi = Invitation(
            invitation_id="inv_budi_1",
            invitation_type="PARTNER_INVITE",
            sender_id=self.andi.student_id,
            recipient_id=self.budi.student_id,
            target_intent_id=self.intent_budi.intent_id,
            proposal_id=self.proposal.proposal_id,
            status="PENDING",
            message="Yuk gabung!",
            created_at=datetime.utcnow()
        )
        self.db.add(self.inv_budi)

        self.db.commit()

        self.token_andi = create_token(self.andi.student_id, self.andi.email)
        self.token_budi = create_token(self.budi.student_id, self.budi.email)
        self.token_citra = create_token(self.citra.student_id, self.citra.email)

        self.headers_andi = {"Authorization": f"Bearer {self.token_andi}"}
        self.headers_budi = {"Authorization": f"Bearer {self.token_budi}"}
        self.headers_citra = {"Authorization": f"Bearer {self.token_citra}"}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        app.dependency_overrides = self.original_overrides

    def test_01_get_inbox_and_sent_invitations(self):
        """Budi melihat undangan di inbox, dan Andi melihat undangan di sent list."""
        # 1. Budi check inbox -> ada 1 undangan dari Andi
        r_inbox = self.client.get("/api/v1/invitations/inbox", headers=self.headers_budi)
        self.assertEqual(r_inbox.status_code, 200)
        items = r_inbox.json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["invitation_id"], self.inv_budi.invitation_id)
        self.assertEqual(items[0]["sender_id"], self.andi.student_id)

        # 2. Citra check inbox -> kosong (tidak ada undangan untuk Citra)
        r_citra = self.client.get("/api/v1/invitations/inbox", headers=self.headers_citra)
        self.assertEqual(r_citra.status_code, 200)
        self.assertEqual(len(r_citra.json()), 0)

        # 3. Andi check sent -> ada 1 undangan terkirim ke Budi
        r_sent = self.client.get("/api/v1/invitations/sent", headers=self.headers_andi)
        self.assertEqual(r_sent.status_code, 200)
        sent_items = r_sent.json()
        self.assertEqual(len(sent_items), 1)
        self.assertEqual(sent_items[0]["recipient_id"], self.budi.student_id)

    def test_02_respond_invitation_accept_success(self):
        """Budi menerima undangan (decision='ACCEPT') -> status ACCEPTED dan responded_at terisi."""
        payload = {"decision": "ACCEPT", "reason": "Siap bergabung!"}
        res = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json=payload,
            headers=self.headers_budi
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ACCEPTED")
        self.assertIsNotNone(data["responded_at"])

        # Verifikasi di database
        self.db.expire_all()
        db_inv = self.db.query(Invitation).filter(Invitation.invitation_id == self.inv_budi.invitation_id).first()
        self.assertEqual(db_inv.status, "ACCEPTED")

    def test_03_respond_invitation_decline_success(self):
        """Budi menolak undangan (decision='DECLINE') -> status REJECTED."""
        payload = {"decision": "DECLINE", "reason": "Maaf, jadwal bentrok"}
        res = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json=payload,
            headers=self.headers_budi
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "REJECTED")

        # Verifikasi di database
        self.db.expire_all()
        db_inv = self.db.query(Invitation).filter(Invitation.invitation_id == self.inv_budi.invitation_id).first()
        self.assertEqual(db_inv.status, "REJECTED")

    def test_04_respond_invitation_cross_student_forbidden(self):
        """Citra mencoba merespons undangan milik Budi -> ditolak (HTTP 403 Forbidden)."""
        payload = {"decision": "ACCEPT"}
        res = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json=payload,
            headers=self.headers_citra
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("tidak berhak merespons undangan milik mahasiswa lain", res.json()["detail"])

    def test_05_respond_invitation_idempotent_duplicate_click(self):
        """Klik ganda dengan keputusan yang sama (ACCEPT lalu ACCEPT lagi) bersifat idempoten (HTTP 200)."""
        payload = {"decision": "ACCEPT"}
        res1 = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json=payload,
            headers=self.headers_budi
        )
        self.assertEqual(res1.status_code, 200)

        # Klik kedua dengan keputusan sama
        res2 = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json=payload,
            headers=self.headers_budi
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "ACCEPTED")

    def test_06_respond_invitation_change_decision_rejected(self):
        """Mencoba mengubah keputusan setelah ACCEPT menjadi DECLINE ditolak (HTTP 400 Bad Request)."""
        res1 = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json={"decision": "ACCEPT"},
            headers=self.headers_budi
        )
        self.assertEqual(res1.status_code, 200)

        # Percobaan ganti ke DECLINE
        res2 = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json={"decision": "DECLINE"},
            headers=self.headers_budi
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("tidak dapat diubah", res2.json()["detail"])

    def test_07_respond_expired_proposal_rejected(self):
        """Undangan pada proposal yang sudah kedaluwarsa ditolak (HTTP 400 Bad Request)."""
        self.proposal.expires_at = datetime.utcnow() - timedelta(hours=1)
        self.db.commit()

        res = self.client.post(
            f"/api/v1/invitations/{self.inv_budi.invitation_id}/respond",
            json={"decision": "ACCEPT"},
            headers=self.headers_budi
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("kedaluwarsa", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
