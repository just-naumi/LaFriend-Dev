# ==============================================================================
# app/session_execution_service.py
# ==============================================================================
# Service Layer Day 21: Study Session Execution Layer
# Bertanggung jawab atas:
# 1. Validasi pre-flight ketat sebelum eksekusi sesi (Proposal READY_FOR_SESSION, Otorisasi Host).
# 2. Pembuatan StudySession, SessionSlot, dan SessionMember secara atomik dalam 1 transaksi DB.
# 3. Transisi status StudyIntent seluruh anggota menjadi 'MATCHED'.
# 4. Transisi status GroupProposal menjadi 'SESSION_EXECUTED'.
# 5. Proteksi idempotensi tahan race condition (One Proposal = One Session).
# ==============================================================================

import json
import time
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models import (
    Student, Course, StudyIntent, IntentAvailability,
    GroupProposal, Invitation, StudySession, SessionSlot, SessionMember
)
from app.schemas import (
    StudySessionResponse, SessionSlotResponse, SessionMemberResponse,
    StudentResponse, CourseResponse
)
from app.group_formation import parse_time_minutes


_MAX_SQLITE_LOCK_RETRIES = 6


class _IntentAllocationConflictError(Exception):
    """Konflik konkurensi: salah satu StudyIntent telah dikonsumsi transaksi lain."""


class _ProposalStateConflictError(Exception):
    """Konflik konkurensi: status GroupProposal berubah sebelum commit selesai."""


def _is_sqlite_lock_error(exc: OperationalError) -> bool:
    """Membedakan lock contention transien SQLite dari error operasional lain (mis. disk I/O)."""
    orig = getattr(exc, "orig", None)
    msg = str(orig if orig is not None else exc).lower()
    return "database is locked" in msg or "database table is locked" in msg


def format_study_session_response(session: StudySession, db: Session) -> StudySessionResponse:
    """Format ORM StudySession ke skema Pydantic StudySessionResponse secara lengkap."""
    slots_resp = [
        SessionSlotResponse(
            slot_id=s.slot_id,
            session_id=s.session_id,
            session_date=s.session_date,
            start_time=s.start_time,
            end_time=s.end_time,
            status=s.status
        )
        for s in session.slots
    ]

    members_resp = []
    for m in session.members:
        st_resp = StudentResponse.model_validate(m.student) if m.student else None
        members_resp.append(
            SessionMemberResponse(
                member_id=m.member_id,
                session_id=m.session_id,
                student_id=m.student_id,
                intent_id=m.intent_id,
                role=m.role,
                status=m.status,
                joined_at=m.joined_at,
                student=st_resp
            )
        )

    course_resp = CourseResponse.model_validate(session.course) if session.course else None

    return StudySessionResponse(
        session_id=session.session_id,
        host_id=session.host_id,
        course_id=session.course_id,
        title=session.title,
        description=session.description,
        learning_goal=session.learning_goal,
        collaboration_style=session.collaboration_style,
        learning_mode=session.learning_mode,
        location=session.location,
        min_group_size=session.min_group_size,
        max_group_size=session.max_group_size,
        status=session.status,
        proposal_id=session.proposal_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        course=course_resp,
        slots=slots_resp,
        members=members_resp
    )


def execute_study_session_from_proposal_service(
    db: Session,
    proposal_id: str,
    host_student: Student
) -> StudySessionResponse:
    """
    Day 21.2 - 21.5: Eksekusi proposal kelompok (READY_FOR_SESSION) menjadi StudySession resmi.
    Transisi ini bersifat atomik, aman terhadap race condition (Same Proposal Race & Shared Intent Race),
    menggunakan atomic conditional update + DB unique constraints (uq_session_proposal &
    uq_session_member_intent), dan menjamin One Proposal = One Session.
    """
    for attempt in range(_MAX_SQLITE_LOCK_RETRIES):
        try:
            # 1. Cari proposal
            proposal = db.query(GroupProposal).filter(GroupProposal.proposal_id == proposal_id).first()
            if not proposal:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Group Proposal dengan ID '{proposal_id}' tidak ditemukan."
                )

            # 2. Otorisasi Host: HANYA host pembuat proposal yang berhak mengeksekusi
            # Validasi otorisasi mendahului pembacaan data sesi agar pengguna non-host tidak bisa mengintip
            if proposal.host_student_id != host_student.student_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Hanya host pembuat proposal yang berhak mengeksekusi sesi belajar."
                )

            # 3. Proteksi Idempotensi Awal: Jika sesi belajar untuk proposal ini sudah ada, kembalikan sesi tersebut
            existing_session = db.query(StudySession).filter(StudySession.proposal_id == proposal.proposal_id).first()
            if existing_session:
                return format_study_session_response(existing_session, db)

            # 4. Validasi Status Proposal: Wajib READY_FOR_SESSION
            if proposal.status != "READY_FOR_SESSION":
                if proposal.status == "SESSION_EXECUTED":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Proposal berstatus 'SESSION_EXECUTED' tetapi data sesi belajar terkait tidak ditemukan di database."
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Hanya proposal berstatus 'READY_FOR_SESSION' yang dapat dieksekusi. Status proposal saat ini: '{proposal.status}'."
                )

            # 5. Validasi Kedaluwarsa Proposal
            if proposal.expires_at < datetime.utcnow():
                proposal.status = "EXPIRED"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Proposal telah kedaluwarsa dan tidak dapat dieksekusi menjadi sesi belajar."
                )

            # 6. Validasi Akun Host
            host_rec = db.query(Student).filter(Student.student_id == proposal.host_student_id).first()
            if not host_rec or (host_rec.account_status or "").upper() != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Akun mahasiswa host ({proposal.host_student_id}) tidak aktif."
                )

            # 7. Validasi Host StudyIntent
            host_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == proposal.host_intent_id).first()
            if not host_intent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Study Intent host tidak ditemukan."
                )
            if host_intent.status == "MATCHED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Study Intent host ({host_intent.intent_id}) sudah berstatus MATCHED oleh sesi belajar lain."
                )
            if host_intent.status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Study Intent host tidak aktif ({host_intent.status})."
                )

            # 8. Validasi Anggota yang Menerima (ACCEPTED) & Intent masing-masing
            accepted_invs = db.query(Invitation).filter(
                Invitation.proposal_id == proposal.proposal_id,
                Invitation.status == "ACCEPTED"
            ).all()

            active_candidate_intents: List[StudyIntent] = []
            active_members: List[Student] = [host_rec]

            for inv in accepted_invs:
                cand_student = db.query(Student).filter(Student.student_id == inv.recipient_id).first()
                if not cand_student or (cand_student.account_status or "").upper() != "ACTIVE":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Akun mahasiswa anggota {inv.recipient_id} tidak aktif."
                    )

                c_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == inv.target_intent_id).first()
                if not c_intent:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Study Intent kandidat {inv.recipient_id} tidak ditemukan."
                    )
                if c_intent.status == "MATCHED":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Study Intent kandidat {inv.recipient_id} sudah berstatus MATCHED oleh sesi belajar lain."
                    )
                if c_intent.status != "ACTIVE":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Study Intent kandidat {inv.recipient_id} sudah tidak aktif ({c_intent.status})."
                    )

                active_candidate_intents.append(c_intent)
                active_members.append(cand_student)

            all_intent_ids = [host_intent.intent_id] + [ci.intent_id for ci in active_candidate_intents]
            if len(set(all_intent_ids)) != len(all_intent_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Terdapat duplikasi Study Intent di dalam proposal yang sama."
                )

            # 9. Validasi Fail-Closed Format Jadwal Terpilih
            if not proposal.selected_schedule_json or not proposal.selected_schedule_json.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Jadwal terpilih proposal kosong atau tidak tersedia."
                )

            try:
                sched = json.loads(proposal.selected_schedule_json)
                s_date = str(sched.get("date", "")).strip()
                s_start_raw = str(sched.get("start_time", "")).strip()
                s_end_raw = str(sched.get("end_time", "")).strip()
                if not s_date or not s_start_raw or not s_end_raw:
                    raise ValueError("Field date, start_time, atau end_time tidak lengkap")
                s_start = parse_time_minutes(s_start_raw)
                s_end = parse_time_minutes(s_end_raw)
                if s_start >= s_end:
                    raise ValueError(f"Waktu mulai ({s_start_raw}) harus lebih awal dari waktu selesai ({s_end_raw})")
            except Exception as err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Jadwal terpilih tidak valid: {str(err)}"
                )

            # 10. EKSEKUSI ATOMIK DALAM SATU TRANSAKSI DATABASE (Day 21.2 & Day 21.3)
            course = db.query(Course).filter(Course.course_id == proposal.course_id).first()
            course_name = course.course_code if course else proposal.course_id
            session_title = f"Sesi Belajar: {course_name}"
            if host_intent.topics:
                topic_hint = host_intent.topics.split(",")[0].strip()
                session_title += f" - {topic_hint}"

            # A. Buat Objek StudySession (uq_session_proposal menjaga One Proposal = One Session)
            new_session = StudySession(
                session_id=str(uuid.uuid4()),
                proposal_id=proposal.proposal_id,
                host_id=proposal.host_student_id,
                course_id=proposal.course_id,
                title=session_title[:150],
                description=proposal.message or f"Sesi belajar bersama mata kuliah {course_name}",
                learning_goal=host_intent.learning_goal or "UNDERSTAND",
                collaboration_style=host_intent.collaboration_style or "DISCUSSION",
                learning_mode=host_intent.learning_mode or "OFFLINE",
                min_group_size=proposal.min_group_size_bound,
                max_group_size=proposal.max_group_size_bound,
                status="CONFIRMED",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_session)
            db.flush()

            # B. Buat Objek SessionSlot
            slot = SessionSlot(
                slot_id=str(uuid.uuid4()),
                session_id=new_session.session_id,
                session_date=s_date,
                start_time=s_start_raw,
                end_time=s_end_raw,
                status="APPROVED"
            )
            db.add(slot)

            # C. Buat SessionMember untuk Host (dengan provenance intent_id)
            host_member = SessionMember(
                member_id=str(uuid.uuid4()),
                session_id=new_session.session_id,
                student_id=proposal.host_student_id,
                intent_id=proposal.host_intent_id,
                role="HOST",
                status="CONFIRMED",
                joined_at=datetime.utcnow()
            )
            db.add(host_member)

            # D. Buat SessionMember untuk Setiap Anggota yang ACCEPTED (dengan provenance intent_id)
            for inv in accepted_invs:
                mem = SessionMember(
                    member_id=str(uuid.uuid4()),
                    session_id=new_session.session_id,
                    student_id=inv.recipient_id,
                    intent_id=inv.target_intent_id,
                    role="MEMBER",
                    status="CONFIRMED",
                    joined_at=datetime.utcnow()
                )
                db.add(mem)

            # Flush eksplisit agar constraint uq_session_member_intent & uq_session_member_student
            # tervalidasi deterministik sebelum conditional update status
            db.flush()

            # E. Atomic Conditional Update: Transisi StudyIntent hanya bila masih ACTIVE
            updated_intents = (
                db.query(StudyIntent)
                .filter(
                    StudyIntent.intent_id.in_(all_intent_ids),
                    StudyIntent.status == "ACTIVE",
                )
                .update({StudyIntent.status: "MATCHED"}, synchronize_session="fetch")
            )
            if updated_intents != len(all_intent_ids):
                raise _IntentAllocationConflictError(
                    "Salah satu Study Intent anggota atau host telah dikonsumsi oleh sesi belajar lain secara bersamaan."
                )

            # F. Atomic Conditional Update: Transisi GroupProposal hanya bila masih READY_FOR_SESSION
            updated_proposals = (
                db.query(GroupProposal)
                .filter(
                    GroupProposal.proposal_id == proposal.proposal_id,
                    GroupProposal.status == "READY_FOR_SESSION",
                )
                .update(
                    {
                        GroupProposal.status: "SESSION_EXECUTED",
                        GroupProposal.updated_at: datetime.utcnow(),
                    },
                    synchronize_session="fetch",
                )
            )
            if updated_proposals != 1:
                raise _ProposalStateConflictError(
                    "Status proposal telah berubah secara bersamaan sebelum eksekusi selesai."
                )

            # Komit tunggal di akhir batas transaksi atomik
            db.commit()
            break

        except _IntentAllocationConflictError as conflict_err:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(conflict_err)
            )
        except _ProposalStateConflictError as prop_err:
            db.rollback()
            concurrent_session = db.query(StudySession).filter(StudySession.proposal_id == proposal_id).first()
            if concurrent_session:
                return format_study_session_response(concurrent_session, db)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(prop_err)
            )
        except IntegrityError as ie:
            db.rollback()
            orig_exc = getattr(ie, "orig", None)
            orig_err = str(orig_exc if orig_exc is not None else ie).lower()

            # 1. Konflik uq_session_member_intent TIDAK BOLEH dianggap sukses idempotent untuk proposal lain
            if (
                "uq_session_member_intent" in orig_err
                or "unique constraint failed: session_members.intent_id" in orig_err
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Salah satu Study Intent anggota atau host telah dialokasikan ke sesi belajar lain."
                )

            # 2. Konflik duplikasi anggota mahasiswa dalam sesi yang sama
            if (
                "uq_session_member_student" in orig_err
                or "unique constraint failed: session_members.session_id, session_members.student_id" in orig_err
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Terdapat duplikasi keanggotaan mahasiswa dalam sesi belajar yang sama."
                )

            # 3. Konflik Same Proposal Race (uq_session_proposal): kembalikan sesi pemenang yang sudah committed
            if (
                "uq_session_proposal" in orig_err
                or "unique constraint failed: study_sessions.proposal_id" in orig_err
            ):
                concurrent_session = db.query(StudySession).filter(StudySession.proposal_id == proposal_id).first()
                if concurrent_session:
                    return format_study_session_response(concurrent_session, db)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Konflik uq_session_proposal tetapi sesi terkait tidak ditemukan: {str(ie)}"
                )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Terjadi konflik integritas database saat mengeksekusi sesi: {str(ie)}"
            )
        except OperationalError as oe:
            db.rollback()
            if _is_sqlite_lock_error(oe):
                if attempt < _MAX_SQLITE_LOCK_RETRIES - 1:
                    db.expire_all()
                    time.sleep(0.015 * (attempt + 1))
                    continue
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Database sedang sibuk memproses eksekusi konkuren. Silakan coba kembali."
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Gagal mengeksekusi sesi belajar: {str(oe)}"
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Gagal mengeksekusi sesi belajar: {str(exc)}"
            )

    # Pasca-commit (di luar batas rollback transaksi): muat ulang & bentuk respons DTO
    db.refresh(new_session)
    return format_study_session_response(new_session, db)


def get_study_session_detail_service(
    db: Session,
    session_id: str,
    current_student: Student
) -> StudySessionResponse:
    """Mengambil detail lengkap sesi belajar beserta jadwal (slots) dan anggota (members)."""
    session = db.query(StudySession).filter(StudySession.session_id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesi belajar dengan ID '{session_id}' tidak ditemukan."
        )
    return format_study_session_response(session, db)


def get_my_study_sessions_service(
    db: Session,
    current_student: Student,
    status_filter: Optional[str] = None
) -> List[StudySessionResponse]:
    """
    Mengambil daftar seluruh sesi belajar yang diikuti mahasiswa (baik sebagai host maupun anggota).
    """
    # Cari seluruh session_id di mana mahasiswa terdaftar di SessionMember
    member_session_ids = [
        m.session_id for m in db.query(SessionMember.session_id).filter(
            SessionMember.student_id == current_student.student_id,
            SessionMember.status.in_(["CONFIRMED", "ACCEPTED"])
        ).all()
    ]

    query = db.query(StudySession).filter(
        (StudySession.host_id == current_student.student_id) |
        (StudySession.session_id.in_(member_session_ids))
    )

    if status_filter:
        clean_status = status_filter.strip().upper()
        query = query.filter(StudySession.status == clean_status)

    sessions = query.order_by(StudySession.created_at.desc()).all()
    return [format_study_session_response(s, db) for s in sessions]
