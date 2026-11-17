# ==============================================================================
# tests/test_day20_group_proposal.py
# ==============================================================================
# Test Suite Day 20.1 & 20.2: Group Proposal Creation & Access Control
# Memvalidasi pembuatan entitas GroupProposal, broadcast Invitation ke calon
# anggota secara atomik, proteksi anti-tampering, dan kontrol akses (ownership guard).
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


class TestDay20GroupProposal(unittest.TestCase):
    """Test suite untuk pembuatan dan akses GroupProposal (Day 20.1 & Day 20.2)."""

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

        # Seed data dasar
        self.course = Course(
            course_id="c_d20_1",
            course_code="ACK2AAB3",
            course_name="Struktur Data",
            study_program="S1 Teknik Komputer"
        )
        self.db.add(self.course)

        # Host Andi
        self.andi = Student(
            student_id="s_host_andi",
            full_name="Andi Pratama",
            email="andi@telkomuniversity.ac.id",
            student_number="1201250001",
            password_hash="hashed_pw_andi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.andi)

        # Kandidat Budi (kompatibel penuh dengan Andi)
        self.budi = Student(
            student_id="s_cand_budi",
            full_name="Budi Santoso",
            email="budi@telkomuniversity.ac.id",
            student_number="1201250002",
            password_hash="hashed_pw_budi",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.budi)

        # Mahasiswa Luar Citra (tidak diundang)
        self.citra = Student(
            student_id="s_third_citra",
            full_name="Citra Lestari",
            email="citra@telkomuniversity.ac.id",
            student_number="1201250003",
            password_hash="hashed_pw_citra",
            verification_status="VERIFIED",
            account_status="ACTIVE",
            is_discoverable=True
        )
        self.db.add(self.citra)

        # Intent Andi (Host)
        self.intent_andi = StudyIntent(
            intent_id="i_andi_1",
            student_id=self.andi.student_id,
            course_id=self.course.course_id,
            topics="Tree, Graph",
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

        # Jadwal Andi (25 Nov, 09:00 - 13:00)
        self.db.add(IntentAvailability(
            availability_id="av_andi_1",
            intent_id=self.intent_andi.intent_id,
            day_or_date="2026-11-25",
            start_time="09:00",
            end_time="13:00",
            priority_rank=1
        ))

        # Intent Budi (Kandidat cocok)
        self.intent_budi = StudyIntent(
            intent_id="i_budi_1",
            student_id=self.budi.student_id,
            course_id=self.course.course_id,
            topics="Tree, Graph",
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

        # Jadwal Budi (25 Nov, 10:00 - 12:00 -> irisan 120 menit)
        self.db.add(IntentAvailability(
            availability_id="av_budi_1",
            intent_id=self.intent_budi.intent_id,
            day_or_date="2026-11-25",
            start_time="10:00",
            end_time="12:00",
            priority_rank=1
        ))

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

    def test_01_create_group_proposal_success(self):
        """Host berhasil membuat proposal kelompok, menyimpan snapshot jadwal, dan broadcast undangan."""
        payload = {
            "host_intent_id": self.intent_andi.intent_id,
            "min_score": 60.0,
            "message": "Halo Budi, yuk belajar Struktur Data bareng!",
            "duration_hours": 24
        }
        res = self.client.post("/api/v1/matching/group-proposals", json=payload, headers=self.headers_andi)
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertEqual(data["status"], "PENDING_RESPONSES")
        self.assertEqual(data["host_intent_id"], self.intent_andi.intent_id)
        self.assertEqual(data["host_student_id"], self.andi.student_id)
        self.assertGreaterEqual(data["group_quality_score"], 60.0)
        self.assertIsNotNone(data["selected_schedule"])
        self.assertEqual(data["selected_schedule"]["date"], "2026-11-25")
        self.assertEqual(data["active_member_count"], 1)  # Host sendiri yang aktif di awal
        self.assertFalse(data["quorum_reached"])

        # Verifikasi undangan yang terbentuk di database
        invs = self.db.query(Invitation).filter(Invitation.proposal_id == data["proposal_id"]).all()
        self.assertEqual(len(invs), 1)
        self.assertEqual(invs[0].recipient_id, self.budi.student_id)
        self.assertEqual(invs[0].sender_id, self.andi.student_id)
        self.assertEqual(invs[0].status, "PENDING")
        self.assertEqual(invs[0].message, "Halo Budi, yuk belajar Struktur Data bareng!")

    def test_02_create_proposal_cross_student_forbidden(self):
        """Budi tidak berhak membuat proposal menggunakan host_intent milik Andi (HTTP 403)."""
        payload = {
            "host_intent_id": self.intent_andi.intent_id,
            "min_score": 60.0
        }
        res = self.client.post("/api/v1/matching/group-proposals", json=payload, headers=self.headers_budi)
        self.assertEqual(res.status_code, 403)
        self.assertIn("hanya berhak membuat usulan kelompok untuk Study Intent milikmu sendiri", res.json()["detail"])

    def test_03_create_proposal_unverified_host_forbidden(self):
        """Host dengan status belum VERIFIED ditolak membuat proposal (HTTP 403)."""
        self.andi.verification_status = "PENDING"
        self.db.commit()

        payload = {
            "host_intent_id": self.intent_andi.intent_id,
            "min_score": 60.0
        }
        res = self.client.post("/api/v1/matching/group-proposals", json=payload, headers=self.headers_andi)
        self.assertEqual(res.status_code, 403)
        self.assertIn("belum berstatus VERIFIED", res.json()["detail"])

    def test_04_create_proposal_inactive_intent_bad_request(self):
        """Host dengan intent CANCELLED ditolak membuat proposal (HTTP 400)."""
        self.intent_andi.status = "CANCELLED"
        self.db.commit()

        payload = {
            "host_intent_id": self.intent_andi.intent_id,
            "min_score": 60.0
        }
        res = self.client.post("/api/v1/matching/group-proposals", json=payload, headers=self.headers_andi)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Usulan hanya dapat dibuat untuk intent ACTIVE", res.json()["detail"])

    def test_05_create_proposal_anti_tampering_no_compatible_group(self):
        """Jika tidak ada kandidat yang cocok (status NO_COMPATIBLE_GROUP), proposal ditolak (HTTP 400)."""
        # Ubah jadwal Budi agar tidak beririsan dengan Andi
        budi_av = self.db.query(IntentAvailability).filter(IntentAvailability.intent_id == self.intent_budi.intent_id).first()
        budi_av.day_or_date = "2026-11-28"
        self.db.commit()

        payload = {
            "host_intent_id": self.intent_andi.intent_id,
            "min_score": 60.0
        }
        res = self.client.post("/api/v1/matching/group-proposals", json=payload, headers=self.headers_andi)
        self.assertEqual(res.status_code, 400)
        self.assertIn("wajib READY", res.json()["detail"])

    def test_06_prevent_duplicate_active_proposal(self):
        """Host tidak dapat membuat proposal baru jika masih ada proposal aktif untuk intent yang sama."""
        payload = {
            "host_intent_id": self.intent_andi.intent_id,
            "min_score": 60.0
        }
        res1 = self.client.post("/api/v1/matching/group-proposals", json=payload, headers=self.headers_andi)
        self.assertEqual(res1.status_code, 201)

        res2 = self.client.post("/api/v1/matching/group-proposals", json=payload, headers=self.headers_andi)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("Sudah ada usulan kelompok aktif", res2.json()["detail"])

    def test_07_get_proposal_detail_permissions(self):
        """Host dan kandidat penerima berhak melihat detail, mahasiswa luar ditolak (HTTP 403)."""
        payload = {
            "host_intent_id": self.intent_andi.intent_id,
            "min_score": 60.0
        }
        res_create = self.client.post("/api/v1/matching/group-proposals", json=payload, headers=self.headers_andi)
        self.assertEqual(res_create.status_code, 201)
        prop_id = res_create.json()["proposal_id"]

        # 1. Host mengakses -> 200 OK
        r_host = self.client.get(f"/api/v1/matching/group-proposals/{prop_id}", headers=self.headers_andi)
        self.assertEqual(r_host.status_code, 200)
        self.assertEqual(r_host.json()["proposal_id"], prop_id)

        # 2. Budi (Penerima undangan) mengakses -> 200 OK
        r_cand = self.client.get(f"/api/v1/matching/group-proposals/{prop_id}", headers=self.headers_budi)
        self.assertEqual(r_cand.status_code, 200)

        # 3. Citra (Mahasiswa luar) mengakses -> 403 Forbidden
        r_third = self.client.get(f"/api/v1/matching/group-proposals/{prop_id}", headers=self.headers_citra)
        self.assertEqual(r_third.status_code, 403)
        self.assertIn("tidak memiliki izin", r_third.json()["detail"])


if __name__ == "__main__":
    unittest.main()
