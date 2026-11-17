# ==============================================================================
# tests/test_day20_finalization.py
# ==============================================================================
# Test Suite Day 20.6: Finalization & Pre-Finalization Hardening
# Memvalidasi transisi proposal ke READY_FOR_SESSION, penarikan undangan sisa (WITHDRAWN),
# otorisasi host, serta pre-flight re-validation (intent aktif, akun aktif, jadwal, mode).
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


class TestDay20Finalization(unittest.TestCase):
    """Test suite untuk finalisasi usulan kelompok dan validasi pra-finalisasi."""

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
            course_id="c_d20_fin",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.db.add(self.course)

        # Host Andi
        self.andi = Student(
            student_id="s_andi_fin",
            full_name="Andi Pratama",
            email="andi.fin@telkomuniversity.ac.id",
            student_number="1201250031",
            password_hash="hashed_pw_andi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.andi)

        # Kandidat Budi
        self.budi = Student(
            student_id="s_budi_fin",
            full_name="Budi Santoso",
            email="budi.fin@telkomuniversity.ac.id",
            student_number="1201250032",
            password_hash="hashed_pw_budi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.budi)

        # Kandidat Citra
        self.citra = Student(
            student_id="s_citra_fin",
            full_name="Citra Lestari",
            email="citra.fin@telkomuniversity.ac.id",
            student_number="1201250033",
            password_hash="hashed_pw_citra",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.citra)

        # Kandidat Dini (cadangan)
        self.dini = Student(
            student_id="s_dini_fin",
            full_name="Dini Wahyuni",
            email="dini.fin@telkomuniversity.ac.id",
            student_number="1201250034",
            password_hash="hashed_pw_dini",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.dini)

        # Intent Andi (Host)
        self.intent_andi = StudyIntent(
            intent_id="intent_andi_fin",
            student_id=self.andi.student_id,
            course_id=self.course.course_id,
            topics="Binary Trees",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            min_group_size=3,
            max_group_size=4,
            status="ACTIVE"
        )
        self.db.add(self.intent_andi)

        # Intent Budi
        self.intent_budi = StudyIntent(
            intent_id="intent_budi_fin",
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

        # Intent Citra
        self.intent_citra = StudyIntent(
            intent_id="intent_citra_fin",
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

        # Intent Dini
        self.intent_dini = StudyIntent(
            intent_id="intent_dini_fin",
            student_id=self.dini.student_id,
            course_id=self.course.course_id,
            topics="Binary Trees",
            learning_mode="OFFLINE",
            earliest_date="2026-11-20",
            latest_date="2026-11-30",
            min_group_size=3,
            max_group_size=4,
            status="ACTIVE"
        )
        self.db.add(self.intent_dini)

        # Schedule Overlap pada 2026-11-25 10:00 - 12:00
        for intent in [self.intent_andi, self.intent_budi, self.intent_citra, self.intent_dini]:
            avail = IntentAvailability(
                availability_id=f"avail_{intent.intent_id}",
                intent_id=intent.intent_id,
                day_or_date="2026-11-25",
                start_time="09:00",
                end_time="13:00"
            )
            self.db.add(avail)

        self.db.commit()

        self.token_andi = create_token(self.andi.student_id, self.andi.email)
        self.token_budi = create_token(self.budi.student_id, self.budi.email)
        self.token_citra = create_token(self.citra.student_id, self.citra.email)
        self.token_dini = create_token(self.dini.student_id, self.dini.email)

    def tearDown(self):
        app.dependency_overrides = self.original_overrides
        self.db.close()
        self.engine.dispose()

    def _setup_proposal_with_status(self, initial_status="QUORUM_REACHED", expires_in_hours=24):
        """Helper untuk membuat proposal siap uji finalisasi."""
        selected_schedule = {
            "date": "2026-11-25",
            "start_time": "10:00",
            "end_time": "12:00",
            "overlap_hours": 2.0
        }
        proposal = GroupProposal(
            proposal_id=f"prop_fin_{datetime.utcnow().timestamp()}",
            host_intent_id=self.intent_andi.intent_id,
            host_student_id=self.andi.student_id,
            course_id=self.course.course_id,
            status=initial_status,
            min_group_size_bound=3,
            max_group_size_bound=4,
            group_quality_score=87.5,
            average_pair_score=87.5,
            minimum_pair_score=82.0,
            selected_schedule_json=json.dumps(selected_schedule),
            proposal_snapshot_json=json.dumps({"members": [self.andi.student_id, self.budi.student_id, self.citra.student_id]}),
            message="Siap finalisasi belajar bersama",
            expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(proposal)
        self.db.flush()

        # Undangan Budi: ACCEPTED
        inv_budi = Invitation(
            invitation_id=f"inv_budi_{proposal.proposal_id}",
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

        # Undangan Citra: ACCEPTED
        inv_citra = Invitation(
            invitation_id=f"inv_citra_{proposal.proposal_id}",
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

        # Undangan Dini: PENDING (belum merespons)
        inv_dini = Invitation(
            invitation_id=f"inv_dini_{proposal.proposal_id}",
            invitation_type="GROUP_PROPOSAL",
            proposal_id=proposal.proposal_id,
            target_intent_id=self.intent_dini.intent_id,
            sender_id=self.andi.student_id,
            recipient_id=self.dini.student_id,
            status="PENDING",
            created_at=datetime.utcnow()
        )
        self.db.add(inv_dini)
        self.db.commit()

        return proposal, inv_budi, inv_citra, inv_dini

    def test_01_successful_finalization_by_host(self):
        """Host berhasil memfinalisasi proposal QUORUM_REACHED -> READY_FOR_SESSION dan sisa PENDING menjadi WITHDRAWN."""
        proposal, inv_budi, inv_citra, inv_dini = self._setup_proposal_with_status("QUORUM_REACHED")

        r = self.client.post(
            f"/api/v1/matching/group-proposals/{proposal.proposal_id}/finalize",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "READY_FOR_SESSION")
        self.assertIsNotNone(data["finalized_at"])

        # Verifikasi di database
        self.db.expire_all()
        db_prop = self.db.query(GroupProposal).filter(GroupProposal.proposal_id == proposal.proposal_id).first()
        self.assertEqual(db_prop.status, "READY_FOR_SESSION")
        self.assertIsNotNone(db_prop.finalized_at)

        # Verifikasi sisa undangan PENDING (Dini) otomatis berubah menjadi WITHDRAWN
        db_inv_dini = self.db.query(Invitation).filter(Invitation.invitation_id == inv_dini.invitation_id).first()
        self.assertEqual(db_inv_dini.status, "WITHDRAWN")

        # Verifikasi undangan yang sudah ACCEPTED (Budi, Citra) tetap ACCEPTED
        db_inv_budi = self.db.query(Invitation).filter(Invitation.invitation_id == inv_budi.invitation_id).first()
        self.assertEqual(db_inv_budi.status, "ACCEPTED")

    def test_02_finalize_forbidden_for_non_host(self):
        """Anggota kelompok bukan host (Budi) dilarang memfinalisasi proposal -> HTTP 403."""
        proposal, _, _, _ = self._setup_proposal_with_status("QUORUM_REACHED")

        r = self.client.post(
            f"/api/v1/matching/group-proposals/{proposal.proposal_id}/finalize",
            headers={"Authorization": f"Bearer {self.token_budi}"}
        )
        self.assertEqual(r.status_code, 403)
        self.assertIn("Hanya host pembuat proposal yang berhak", r.json()["detail"])

    def test_03_finalize_rejected_if_not_quorum_reached(self):
        """Finalisasi ditolak jika proposal belum mencapai status QUORUM_REACHED -> HTTP 400."""
        proposal, _, _, _ = self._setup_proposal_with_status("PENDING_RESPONSES")

        r = self.client.post(
            f"/api/v1/matching/group-proposals/{proposal.proposal_id}/finalize",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("Hanya proposal berstatus QUORUM_REACHED", r.json()["detail"])

    def test_04_finalize_rejected_if_expired(self):
        """Finalisasi ditolak dan proposal ditandai EXPIRED jika waktu expires_at terlewati -> HTTP 400."""
        proposal, _, _, _ = self._setup_proposal_with_status("QUORUM_REACHED", expires_in_hours=-2)

        r = self.client.post(
            f"/api/v1/matching/group-proposals/{proposal.proposal_id}/finalize",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("telah kedaluwarsa", r.json()["detail"])

        self.db.expire_all()
        db_prop = self.db.query(GroupProposal).filter(GroupProposal.proposal_id == proposal.proposal_id).first()
        self.assertEqual(db_prop.status, "EXPIRED")

    def test_05_pre_finalization_guard_intent_cancelled(self):
        """Jika salah satu anggota membatalkan StudyIntent sebelum finalisasi, finalisasi ditolak -> HTTP 400."""
        proposal, _, _, _ = self._setup_proposal_with_status("QUORUM_REACHED")

        # Budi membatalkan intent-nya
        self.intent_budi.status = "CANCELLED"
        self.db.commit()

        r = self.client.post(
            f"/api/v1/matching/group-proposals/{proposal.proposal_id}/finalize",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("sudah tidak aktif", r.json()["detail"])

    def test_06_pre_finalization_guard_student_restricted(self):
        """Jika akun salah satu anggota dibekukan (RESTRICTED) sebelum finalisasi, finalisasi ditolak -> HTTP 400."""
        proposal, _, _, _ = self._setup_proposal_with_status("QUORUM_REACHED")

        # Citra dibekukan akunnya
        self.citra.account_status = "RESTRICTED"
        self.db.commit()

        r = self.client.post(
            f"/api/v1/matching/group-proposals/{proposal.proposal_id}/finalize",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("tidak aktif", r.json()["detail"])

    def test_07_finalize_already_finalized_proposal_rejected(self):
        """Memanggil finalize pada proposal yang sudah READY_FOR_SESSION ditolak -> HTTP 400."""
        proposal, _, _, _ = self._setup_proposal_with_status("READY_FOR_SESSION")

        r = self.client.post(
            f"/api/v1/matching/group-proposals/{proposal.proposal_id}/finalize",
            headers={"Authorization": f"Bearer {self.token_andi}"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("READY_FOR_SESSION", r.json()["detail"])


if __name__ == "__main__":
    unittest.main()
