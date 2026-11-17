# ==============================================================================
# group_proposal_service.py - Service Layer Group Proposal & Agreement (Day 20)
# ==============================================================================
# Mengelola siklus hidup Usulan Kelompok Belajar (GroupProposal), distribusi
# dan penerimaan Undangan (Invitation), validasi kuorum dinamis (Dynamic Quorum),
# serta finalisasi proposal menjadi status READY_FOR_SESSION.
# ==============================================================================

import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Student, StudyIntent, GroupProposal, Invitation
from app.schemas import (
    GroupProposalCreateRequest,
    GroupProposalResponse,
    InvitationResponse,
    StudentResponse
)
from app.group_formation import preview_group_formation_pipeline
from app.matching import resolve_availability_windows, parse_time_minutes, is_learning_mode_compatible


def format_proposal_response(proposal: GroupProposal, db: Session) -> GroupProposalResponse:
    """
    Mengonversi objek GroupProposal ORM menjadi schema GroupProposalResponse
    lengkap dengan perhitungan kuorum aktual dan daftar undangan.
    """
    selected_sched = None
    if proposal.selected_schedule_json:
        try:
            selected_sched = json.loads(proposal.selected_schedule_json)
        except Exception:
            selected_sched = None

    # Hitung anggota aktif (Host selalu terhitung 1 + seluruh kandidat ACCEPTED)
    invitations = db.query(Invitation).filter(Invitation.proposal_id == proposal.proposal_id).all()
    accepted_count = sum(1 for inv in invitations if inv.status == "ACCEPTED")
    active_member_count = 1 + accepted_count

    is_quorum = proposal.status in ["QUORUM_REACHED", "READY_FOR_SESSION"]

    invitation_responses = []
    for inv in invitations:
        inv_resp = InvitationResponse(
            invitation_id=inv.invitation_id,
            invitation_type=inv.invitation_type,
            sender_id=inv.sender_id,
            recipient_id=inv.recipient_id,
            session_id=inv.session_id,
            target_intent_id=inv.target_intent_id,
            proposal_id=inv.proposal_id,
            status=inv.status,
            message=inv.message,
            created_at=inv.created_at,
            responded_at=inv.responded_at,
            sender=StudentResponse.model_validate(inv.sender) if inv.sender else None,
            recipient=StudentResponse.model_validate(inv.recipient) if inv.recipient else None,
        )
        invitation_responses.append(inv_resp)

    host_student_resp = StudentResponse.model_validate(proposal.host_student) if proposal.host_student else None

    return GroupProposalResponse(
        proposal_id=proposal.proposal_id,
        host_intent_id=proposal.host_intent_id,
        host_student_id=proposal.host_student_id,
        course_id=proposal.course_id,
        status=proposal.status,
        min_group_size_bound=proposal.min_group_size_bound,
        max_group_size_bound=proposal.max_group_size_bound,
        group_quality_score=proposal.group_quality_score,
        average_pair_score=proposal.average_pair_score,
        minimum_pair_score=proposal.minimum_pair_score,
        selected_schedule=selected_sched,
        message=proposal.message,
        expires_at=proposal.expires_at,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
        finalized_at=proposal.finalized_at,
        invitations=invitation_responses,
        active_member_count=active_member_count,
        quorum_reached=is_quorum,
        host_student=host_student_resp,
        session_id=proposal.study_session.session_id if proposal.study_session else None
    )


def create_group_proposal_service(
    db: Session,
    host_student: Student,
    req: GroupProposalCreateRequest
) -> GroupProposalResponse:
    """
    Day 20.2: Host membuat usulan kelompok belajar (GroupProposal) baru
    berdasarkan hasil matching pipeline dan secara atomik mengirimkan undangan
    ke setiap calon anggota non-host.
    """
    # 1. Validasi otorisasi dan status akun host
    if (host_student.account_status or "").upper() != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu sedang ditangguhkan atau tidak aktif."
        )
    if (host_student.verification_status or "").upper() != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun mahasiswa kamu belum berstatus VERIFIED."
        )

    # 2. Validasi keberadaan dan kepemilikan host intent
    host_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == req.host_intent_id).first()
    if not host_intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study Intent dengan ID '{req.host_intent_id}' tidak ditemukan."
        )
    if host_intent.student_id != host_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu hanya berhak membuat usulan kelompok untuk Study Intent milikmu sendiri."
        )
    if host_intent.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Study Intent ini berstatus '{host_intent.status}'. Usulan hanya dapat dibuat untuk intent ACTIVE."
        )

    # 3. Cek apakah sudah ada proposal aktif untuk host intent ini
    active_proposal = db.query(GroupProposal).filter(
        GroupProposal.host_intent_id == req.host_intent_id,
        GroupProposal.status.in_(["PENDING_RESPONSES", "QUORUM_REACHED"])
    ).first()
    if active_proposal:
        # Periksa kedaluwarsa jika ada
        if active_proposal.expires_at < datetime.utcnow():
            active_proposal.status = "EXPIRED"
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sudah ada usulan kelompok aktif untuk Study Intent ini. Harap batalkan usulan sebelumnya terlebih dahulu."
            )

    # 4. Anti-Tampering Engine Recalculation (Hitung ulang rekomendasi kelompok di backend)
    try:
        formation_res = preview_group_formation_pipeline(
            host_intent_id=req.host_intent_id,
            db=db,
            min_score=req.min_score,
            target_group_size=req.target_group_size,
            max_candidate_pool=req.max_candidate_pool
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gagal menghitung formasi kelompok: {str(exc)}"
        )

    form_status = formation_res.get("formation_status", "UNKNOWN")
    if form_status != "READY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tidak dapat membuat usulan kelompok: status formasi rekomendasi adalah '{form_status}' (wajib READY)."
        )

    selected_sched = formation_res.get("selected_schedule")
    if not selected_sched or not isinstance(selected_sched, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calon kelompok tidak memiliki selected_schedule yang valid."
        )

    members = formation_res.get("members", [])
    if len(members) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jumlah anggota kelompok hasil rekomendasi kurang dari 2 mahasiswa."
        )

    # 5. Eksekusi Transaksi Atomik Database
    expires_at = datetime.utcnow() + timedelta(hours=req.duration_hours or 24)
    proposal_id = str(uuid.uuid4())

    new_proposal = GroupProposal(
        proposal_id=proposal_id,
        host_intent_id=host_intent.intent_id,
        host_student_id=host_student.student_id,
        course_id=host_intent.course_id,
        status="PENDING_RESPONSES",
        min_group_size_bound=int(formation_res.get("min_group_size_bound", 2)),
        max_group_size_bound=int(formation_res.get("max_group_size_bound", 4)),
        group_quality_score=float(formation_res.get("group_quality_score", 0.0)),
        average_pair_score=float(formation_res.get("average_pair_score", 0.0)),
        minimum_pair_score=float(formation_res.get("minimum_pair_score", 0.0)),
        selected_schedule_json=json.dumps(selected_sched),
        proposal_snapshot_json=json.dumps(formation_res),
        message=req.message,
        expires_at=expires_at,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        finalized_at=None
    )

    try:
        db.add(new_proposal)
        db.flush()

        # Buat Invitation untuk tiap calon anggota non-host
        for m in members:
            cand_intent_id = m.get("intent_id") if isinstance(m, dict) else getattr(m, "intent_id", None)
            if not cand_intent_id or str(cand_intent_id) == str(host_intent.intent_id):
                continue

            cand_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == cand_intent_id).first()
            if not cand_intent:
                continue

            inv = Invitation(
                invitation_id=str(uuid.uuid4()),
                invitation_type="PARTNER_INVITE",
                sender_id=host_student.student_id,
                recipient_id=cand_intent.student_id,
                target_intent_id=cand_intent.intent_id,
                session_id=None,
                proposal_id=new_proposal.proposal_id,
                status="PENDING",
                message=req.message,
                created_at=datetime.utcnow(),
                responded_at=None
            )
            db.add(inv)

        db.commit()
        db.refresh(new_proposal)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat menyimpan usulan kelompok: {str(exc)}"
        )

    return format_proposal_response(new_proposal, db)


def get_group_proposal_detail_service(
    db: Session,
    proposal_id: str,
    current_student: Student
) -> GroupProposalResponse:
    """
    Day 20.3: Mengambil rincian proposal beserta status respons undangan dan kuorum.
    Hanya host atau mahasiswa yang diundang yang berhak mengakses (Otorisasi).
    """
    proposal = db.query(GroupProposal).filter(GroupProposal.proposal_id == proposal_id).first()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group Proposal dengan ID '{proposal_id}' tidak ditemukan."
        )

    # Otomatis update status ke EXPIRED jika batas waktu telah lewat
    if proposal.status in ["PENDING_RESPONSES", "QUORUM_REACHED"] and proposal.expires_at < datetime.utcnow():
        proposal.status = "EXPIRED"
        for inv in proposal.invitations:
            if inv.status == "PENDING":
                inv.status = "EXPIRED"
        db.commit()
        db.refresh(proposal)

    # Validasi Otorisasi: Host atau Recipient
    is_host = (proposal.host_student_id == current_student.student_id)
    recipient_ids = {inv.recipient_id for inv in proposal.invitations}
    if not is_host and current_student.student_id not in recipient_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu tidak memiliki izin untuk melihat usulan kelompok ini."
        )

    return format_proposal_response(proposal, db)


def respond_invitation_service(
    db: Session,
    invitation_id: str,
    decision: str,
    current_student: Student,
    reason: Optional[str] = None
) -> InvitationResponse:
    """
    Day 20.4: Calon anggota merespons undangan (ACCEPT atau DECLINE).
    Menerapkan validasi kuorum dinamis (Dynamic Quorum Calculation) dan proteksi idempotensi.
    """
    inv = db.query(Invitation).filter(Invitation.invitation_id == invitation_id).first()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Undangan dengan ID '{invitation_id}' tidak ditemukan."
        )

    # Otorisasi: Hanya penerima undangan yang berhak merespons
    if inv.recipient_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu tidak berhak merespons undangan milik mahasiswa lain."
        )

    # Proteksi Idempotensi respons & status undangan terminal
    clean_dec = decision.strip().upper()
    target_status = "ACCEPTED" if clean_dec == "ACCEPT" else "REJECTED"

    if inv.status in ["WITHDRAWN", "EXPIRED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Undangan ini sudah berstatus '{inv.status}' dan tidak dapat direspons."
        )

    if inv.status in ["ACCEPTED", "REJECTED"]:
        if inv.status == target_status:
            # Idempoten: respons sama dipanggil berulang kali
            return InvitationResponse.model_validate(inv)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Undangan sudah dijawab sebelumnya dengan '{inv.status}' dan tidak dapat diubah."
            )

    # Cek proposal terkait jika ada
    proposal = None
    if inv.proposal_id:
        proposal = db.query(GroupProposal).filter(GroupProposal.proposal_id == inv.proposal_id).first()
        if proposal:
            # Cek apakah proposal sudah kedaluwarsa
            if proposal.status in ["PENDING_RESPONSES", "QUORUM_REACHED"] and proposal.expires_at < datetime.utcnow():
                proposal.status = "EXPIRED"
                inv.status = "EXPIRED"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Usulan kelompok ini telah kedaluwarsa."
                )

            # Cek apakah proposal sudah dalam status terminal
            if proposal.status in ["CANCELLED", "EXPIRED", "READY_FOR_SESSION", "NOT_FORMED"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Usulan kelompok ini sudah berstatus '{proposal.status}' dan tidak lagi menerima respons."
                )

    # Update status undangan
    inv.status = target_status
    inv.responded_at = datetime.utcnow()

    # Dynamic Quorum Calculation jika terhubung ke GroupProposal
    if proposal:
        _evaluate_dynamic_quorum(db, proposal)

    db.commit()
    db.refresh(inv)

    return InvitationResponse.model_validate(inv)


def _evaluate_dynamic_quorum(db: Session, proposal: GroupProposal) -> None:
    """
    Menghitung ulang keterpenuhan kuorum kelompok secara dinamis dan deterministik (Day 20.4).

    Aturan:
      G_active = {Host} U {Kandidat dengan status ACCEPTED}
      MinGroup_active = max(min_group_size_i) untuk i in G_active
      MaxGroup_active = min(max_group_size_i) untuk i in G_active

      Status:
      - QUORUM_REACHED: MinGroup_active <= |G_active| <= MaxGroup_active
      - PENDING_RESPONSES: |G_active| < MinGroup_active DAN masih ada PENDING yang berpotensi mencapai kuorum
      - NOT_FORMED: Kuorum gagal terpenuhi dan tidak ada lagi kemungkinan (semua sudah merespon atau sisa PENDING tidak cukup)
    """
    # 1. Himpun seluruh objek intent anggota aktif
    active_intents: List[StudyIntent] = []

    host_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == proposal.host_intent_id).first()
    if host_intent:
        active_intents.append(host_intent)

    invitations = db.query(Invitation).filter(Invitation.proposal_id == proposal.proposal_id).all()
    accepted_invs = [i for i in invitations if i.status == "ACCEPTED"]
    pending_invs = [i for i in invitations if i.status == "PENDING"]

    for a_inv in accepted_invs:
        cand_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == a_inv.target_intent_id).first()
        if cand_intent:
            active_intents.append(cand_intent)

    n_active = len(active_intents)
    n_pending = len(pending_invs)

    # 2. Hitung rentang kapasitas dinamis anggota aktif
    min_active_bound = max((getattr(m, "min_group_size", 2) or 2) for m in active_intents)
    max_active_bound = min((getattr(m, "max_group_size", 4) or 4) for m in active_intents)

    # 3. Evaluasi kuorum
    if min_active_bound > max_active_bound:
        proposal.status = "NOT_FORMED"
    elif min_active_bound <= n_active <= max_active_bound:
        proposal.status = "QUORUM_REACHED"
    elif n_active < min_active_bound:
        # Cek apakah secara matematis kuorum masih mungkin tercapai jika seluruh sisa pending menerima
        max_possible_members = n_active + n_pending
        if max_possible_members < min_active_bound:
            proposal.status = "NOT_FORMED"
        else:
            proposal.status = "PENDING_RESPONSES"
    else:
        # n_active > max_active_bound
        proposal.status = "NOT_FORMED"

    proposal.updated_at = datetime.utcnow()


def finalize_group_proposal_service(
    db: Session,
    proposal_id: str,
    host_student: Student
) -> GroupProposalResponse:
    """
    Day 20.5: Host memfinalisasi proposal yang sudah berstatus QUORUM_REACHED.
    Menjalankan validasi ulang constraints independen, mengubah status ke READY_FOR_SESSION,
    dan menarik (WITHDRAWN) seluruh sisa undangan yang masih PENDING.
    """
    proposal = db.query(GroupProposal).filter(GroupProposal.proposal_id == proposal_id).first()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group Proposal dengan ID '{proposal_id}' tidak ditemukan."
        )

    # Otorisasi: Hanya host yang berhak memfinalisasi
    if proposal.host_student_id != host_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya host pembuat proposal yang berhak melakukan finalisasi."
        )

    # Cek apakah proposal kedaluwarsa
    if proposal.expires_at < datetime.utcnow():
        proposal.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal telah kedaluwarsa dan tidak dapat difinalisasi."
        )

    # Cek status kuorum
    if proposal.status != "QUORUM_REACHED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal berstatus '{proposal.status}'. Hanya proposal berstatus QUORUM_REACHED yang dapat difinalisasi."
        )

    # VALIDASI ULANG INDEPENDEN SEBELUM FINALISASI:
    # A. Verifikasi Host Intent & Akun
    host_student_rec = db.query(Student).filter(Student.student_id == proposal.host_student_id).first()
    if not host_student_rec or (host_student_rec.account_status or "").upper() != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Akun mahasiswa host ({proposal.host_student_id}) tidak aktif."
        )

    if (host_student_rec.verification_status or "").upper() != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status verifikasi akun host ({proposal.host_student_id}) belum VERIFIED."
        )

    host_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == proposal.host_intent_id).first()
    if not host_intent or host_intent.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Study Intent milik host sudah tidak aktif."
        )

    if host_intent.course_id != proposal.course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mata kuliah pada Study Intent host ({host_intent.course_id}) tidak cocok dengan proposal ({proposal.course_id})."
        )

    # B. Verifikasi Anggota yang Menerima (ACCEPTED)
    accepted_invs = db.query(Invitation).filter(
        Invitation.proposal_id == proposal.proposal_id,
        Invitation.status == "ACCEPTED"
    ).all()

    active_members = [host_intent]
    for inv in accepted_invs:
        cand_student = db.query(Student).filter(Student.student_id == inv.recipient_id).first()
        if not cand_student or (cand_student.account_status or "").upper() != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Akun mahasiswa anggota {inv.recipient_id} tidak aktif."
            )

        if (cand_student.verification_status or "").upper() != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status verifikasi akun anggota {inv.recipient_id} belum VERIFIED."
            )

        if not cand_student.is_discoverable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mahasiswa anggota {inv.recipient_id} tidak mengaktifkan mode discoverable (is_discoverable=False)."
            )

        c_intent = db.query(StudyIntent).filter(StudyIntent.intent_id == inv.target_intent_id).first()
        if not c_intent or c_intent.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Study Intent kandidat {inv.recipient_id} sudah tidak aktif."
            )

        if c_intent.course_id != proposal.course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mata kuliah pada Study Intent anggota {inv.recipient_id} ({c_intent.course_id}) tidak cocok dengan proposal ({proposal.course_id})."
            )

        active_members.append(c_intent)

    # C. Perhitungan Ulang Batasan Ukuran Kelompok Aktif (Group Size Constraints)
    for m in active_members:
        m_min = getattr(m, "min_group_size", 2) or 2
        m_max = getattr(m, "max_group_size", 4) or 4
        if m_min < 2 or m_max > 10 or m_min > m_max:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batasan ukuran kelompok pada Study Intent {m.intent_id} tidak valid ({m_min}-{m_max}). Batas valid: min >= 2, max <= 10, min <= max."
            )

    n_active = len(active_members)
    min_bound_active = max((getattr(m, "min_group_size", 2) or 2) for m in active_members)
    max_bound_active = min((getattr(m, "max_group_size", 4) or 4) for m in active_members)

    if min_bound_active > max_bound_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batasan ukuran kelompok anggota saling bertentangan: MinGroup ({min_bound_active}) > MaxGroup ({max_bound_active})."
        )

    if n_active < min_bound_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Jumlah anggota aktif ({n_active}) kurang dari batas minimum kelompok ({min_bound_active})."
        )

    if n_active > max_bound_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Jumlah anggota aktif ({n_active}) melebihi batas maksimum kelompok ({max_bound_active})."
        )

    # D. Verifikasi Kompatibilitas Mode Belajar Transitif & Whitelist
    valid_modes = {"ONLINE", "OFFLINE", "HYBRID"}
    for m in active_members:
        mode_clean = (m.learning_mode or "").strip().upper()
        if mode_clean not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mode belajar '{m.learning_mode}' pada Study Intent {m.intent_id} tidak valid. Pilihan: ONLINE, OFFLINE, HYBRID."
            )

    modes = [(m.learning_mode or "").strip().upper() for m in active_members]
    if "ONLINE" in modes and "OFFLINE" in modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Finalisasi gagal: kelompok memuat anggota ONLINE dan OFFLINE sekaligus."
        )

    # E. Verifikasi Jadwal Terpilih (Fail-Closed)
    if not proposal.selected_schedule_json or not proposal.selected_schedule_json.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jadwal terpilih (selected_schedule_json) kosong atau tidak tersedia."
        )

    try:
        sched = json.loads(proposal.selected_schedule_json)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Jadwal terpilih malformed / format JSON tidak valid: {str(err)}"
        )

    if not isinstance(sched, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format jadwal terpilih harus berupa objek JSON."
        )

    s_date = str(sched.get("date", "")).strip()
    s_start_raw = str(sched.get("start_time", "")).strip()
    s_end_raw = str(sched.get("end_time", "")).strip()

    if not s_date or not s_start_raw or not s_end_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jadwal terpilih tidak lengkap (memerlukan field date, start_time, dan end_time)."
        )

    try:
        s_start = parse_time_minutes(s_start_raw)
        s_end = parse_time_minutes(s_end_raw)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format waktu jadwal terpilih tidak valid: {str(err)}"
        )

    if s_start >= s_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Waktu mulai jadwal ({s_start_raw}) harus lebih awal dari waktu selesai ({s_end_raw})."
        )

    if (s_end - s_start) < 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Durasi jadwal terpilih ({s_end - s_start} menit) kurang dari batas minimal 60 menit."
        )

    for mem in active_members:
        windows = resolve_availability_windows(mem)
        covered = False
        for w in windows:
            if str(w.get("date", "")).strip() == s_date:
                try:
                    w_s = parse_time_minutes(str(w.get("start_time", "00:00")))
                    w_e = parse_time_minutes(str(w.get("end_time", "00:00")))
                    if w_s <= s_start and w_e >= s_end:
                        covered = True
                        break
                except Exception:
                    continue
        if not covered:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Jadwal terpilih ({s_date} {s_start_raw}-{s_end_raw}) sudah tidak lagi cocok dengan jadwal anggota {mem.student_id}."
            )

    # Transisi Status Proposal ke READY_FOR_SESSION
    proposal.status = "READY_FOR_SESSION"
    proposal.finalized_at = datetime.utcnow()
    proposal.updated_at = datetime.utcnow()

    # Seluruh sisa undangan yang masih PENDING diubah menjadi WITHDRAWN
    pending_invs = db.query(Invitation).filter(
        Invitation.proposal_id == proposal.proposal_id,
        Invitation.status == "PENDING"
    ).all()
    for p_inv in pending_invs:
        p_inv.status = "WITHDRAWN"
        p_inv.responded_at = datetime.utcnow()

    db.commit()
    db.refresh(proposal)

    return format_proposal_response(proposal, db)


def cancel_group_proposal_service(
    db: Session,
    proposal_id: str,
    host_student: Student,
    reason: Optional[str] = None
) -> GroupProposalResponse:
    """
    Day 20.5: Host membatalkan proposal kelompok.
    Status berubah ke CANCELLED dan seluruh sisa undangan PENDING diubah menjadi WITHDRAWN.
    """
    proposal = db.query(GroupProposal).filter(GroupProposal.proposal_id == proposal_id).first()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group Proposal dengan ID '{proposal_id}' tidak ditemukan."
        )

    # Otorisasi: Hanya host yang berhak membatalkan
    if proposal.host_student_id != host_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya host pembuat proposal yang berhak membatalkan usulan kelompok."
        )

    if proposal.status == "READY_FOR_SESSION":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal yang sudah READY_FOR_SESSION tidak dapat dibatalkan melalui endpoint ini."
        )

    if proposal.status in ["CANCELLED", "EXPIRED", "NOT_FORMED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal sudah berstatus '{proposal.status}'."
        )

    proposal.status = "CANCELLED"
    proposal.updated_at = datetime.utcnow()

    # Ubah seluruh undangan PENDING menjadi WITHDRAWN
    pending_invs = db.query(Invitation).filter(
        Invitation.proposal_id == proposal.proposal_id,
        Invitation.status == "PENDING"
    ).all()
    for p_inv in pending_invs:
        p_inv.status = "WITHDRAWN"
        p_inv.responded_at = datetime.utcnow()

    db.commit()
    db.refresh(proposal)

    return format_proposal_response(proposal, db)


def get_student_inbox_service(
    db: Session,
    student: Student,
    status_filter: Optional[str] = None
) -> List[InvitationResponse]:
    """
    Day 20.3: Mengambil daftar undangan masuk (received invitations) untuk mahasiswa saat ini.
    """
    query = db.query(Invitation).filter(Invitation.recipient_id == student.student_id)
    if status_filter:
        clean_st = status_filter.strip().upper()
        query = query.filter(Invitation.status == clean_st)
    invitations = query.order_by(Invitation.created_at.desc()).all()

    return [InvitationResponse.model_validate(inv) for inv in invitations]


def get_student_sent_service(
    db: Session,
    student: Student,
    status_filter: Optional[str] = None
) -> List[InvitationResponse]:
    """
    Day 20.3: Mengambil daftar undangan terkirim (sent invitations) oleh mahasiswa saat ini.
    """
    query = db.query(Invitation).filter(Invitation.sender_id == student.student_id)
    if status_filter:
        clean_st = status_filter.strip().upper()
        query = query.filter(Invitation.status == clean_st)
    invitations = query.order_by(Invitation.created_at.desc()).all()

    return [InvitationResponse.model_validate(inv) for inv in invitations]
