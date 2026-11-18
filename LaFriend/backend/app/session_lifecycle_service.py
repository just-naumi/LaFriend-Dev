# ==============================================================================
# app/session_lifecycle_service.py
# ==============================================================================
# Service Layer Day 22: Study Session Lifecycle & Post-Execution Management
# Bertanggung jawab atas:
# 1. Otorisasi ketat akses detail sesi (Host & anggota aktif CONFIRMED/ACCEPTED).
# 2. Session State Machine: CONFIRMED -> COMPLETED / CANCELLED (Host only, atomic, idempotent).
# 3. Membership Lifecycle: CONFIRMED -> WITHDRAWN (self) / REMOVED (Host), soft-status only.
#    - Withdraw mengembalikan SessionWithdrawResponse minimal (tanpa detail privat sesi)
#      agar mantan anggota tidak dapat membypass larangan GET detail sesi.
# 4. Kebijakan Quorum Option A (Explicit Host Control): withdraw/remove tidak otomatis
#    mengubah status StudySession meskipun anggota CONFIRMED < min_group_size.
# 5. Perlindungan penuh histori alokasi StudyIntent Day 21 (immutable provenance,
#    tanpa hard delete, tanpa mengembalikan StudyIntent ke ACTIVE).
# 6. Concurrency safety via atomic conditional UPDATE + bounded retry & wall-clock budget
#    untuk SQLite lock contention, serta sanitasi error HTTP 500 (server-side logging).
# ==============================================================================

from contextlib import contextmanager
import logging
import threading
import time
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import StudySession, SessionMember, Student
from app.schemas import StudySessionResponse
from app.session_execution_service import format_study_session_response


logger = logging.getLogger(__name__)

_MAX_SQLITE_LOCK_RETRIES = 4
_LOCK_RETRY_TIME_BUDGET_SECONDS = 2.0
_PER_ATTEMPT_BUSY_TIMEOUT_MS = 450
_ORIG_BUSY_TIMEOUT_INFO_KEY = "_lafriend_orig_busy_timeout"
_POOL_LISTENER_LOCK = threading.Lock()
_ACTIVE_DETAIL_MEMBER_STATUSES = ("CONFIRMED", "ACCEPTED")
_GENERIC_INTERNAL_ERROR_DETAIL = "Terjadi kesalahan internal saat memproses permintaan sesi belajar."


class SessionWithdrawResponse(BaseModel):
    """
    Response aksi minimal untuk endpoint POST /api/v1/sessions/{session_id}/withdraw.
    Secara ketat hanya memuat identitas sesi, status sesi, dan status keanggotaan
    (tanpa location, slot jadwal, daftar anggota, email, NIM, atau profil mahasiswa lain)
    untuk mencegah mantan anggota WITHDRAWN mengakses detail privat sesi.
    """
    session_id: str
    session_status: str
    membership_status: str


def _is_sqlite_lock_error(exc: OperationalError) -> bool:
    """Membedakan lock contention transien SQLite dari error operasional non-lock."""
    orig = getattr(exc, "orig", None)
    msg = str(orig if orig is not None else exc).lower()
    return "database is locked" in msg or "database table is locked" in msg


def _compute_lock_retry_delay(attempt: int, started_at: float) -> Optional[float]:
    """
    Menentukan apakah percobaan ulang lock contention masih berada di dalam batas
    jumlah retry (_MAX_SQLITE_LOCK_RETRIES) DAN anggaran waktu wall-clock
    (_LOCK_RETRY_TIME_BUDGET_SECONDS). Mengembalikan delay tidur (detik) atau None jika habis.
    """
    if attempt >= _MAX_SQLITE_LOCK_RETRIES - 1:
        return None
    elapsed = time.monotonic() - started_at
    remaining = _LOCK_RETRY_TIME_BUDGET_SECONDS - elapsed
    if remaining <= 0.0:
        return None
    return min(0.015 * (attempt + 1), remaining)


def _set_sqlite_busy_timeout(raw_conn, timeout_ms: int) -> None:
    """Mengatur PRAGMA busy_timeout pada koneksi fisik SQLite."""
    cur = raw_conn.cursor()
    try:
        cur.execute(f"PRAGMA busy_timeout = {int(timeout_ms)}")
    finally:
        cur.close()


def _restore_sqlite_busy_timeout_on_checkin(dbapi_conn, conn_record) -> None:
    """
    Pool checkin listener SQLAlchemy: memulihkan PRAGMA busy_timeout asli SEBELUM
    koneksi fisik SQLite dikembalikan ke free queue pool (termasuk pasca db.commit() sukses).
    Jika pemulihan gagal, koneksi fisik langsung di-invalidasi agar tidak pernah masuk kembali
    ke pool dalam konfigurasi yang tidak diketahui.
    """
    orig_bt = conn_record.info.pop(_ORIG_BUSY_TIMEOUT_INFO_KEY, None)
    if orig_bt is None or dbapi_conn is None:
        return
    try:
        _set_sqlite_busy_timeout(dbapi_conn, int(orig_bt))
    except Exception as exc:
        logger.exception(
            "Gagal memulihkan PRAGMA busy_timeout=%s saat pool checkin; menginvalidasi koneksi SQLite.",
            orig_bt,
        )
        conn_record.invalidate(exc)


@contextmanager
def _sqlite_bounded_busy_timeout(db: Session, started_at: float):
    """
    Menegakkan bounded SQLite lock-wait budget per percobaan dengan membatasi
    PRAGMA busy_timeout <= min(existing_timeout, _PER_ATTEMPT_BUSY_TIMEOUT_MS, remaining_ms).
    Catatan kontrak: anggaran 2 detik ini adalah bounded SQLite lock-wait budget
    (memotong tunggu lock default 5 detik sqlite3), bukan jaminan SLA total durasi seluruh HTTP request.

    Pemulihan busy_timeout dijamin pada seluruh jalur (commit sukses, rollback, maupun early return)
    melalui:
    1. Pool `checkin` event listener (saat koneksi dikembalikan ke pool oleh commit/rollback/close), dan
    2. Blok `finally` (jika koneksi masih aktif/checked-out, mis. jalur idempotent tanpa commit).
    Bila pemulihan gagal pada salah satu jalur, koneksi fisik langsung di-invalidasi.
    """
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        yield
        return

    remaining_s = _LOCK_RETRY_TIME_BUDGET_SECONDS - (time.monotonic() - started_at)
    if remaining_s <= 0.0:
        raise OperationalError("SQLite lock budget exceeded before statement", {}, Exception("database is locked"))

    engine = getattr(bind, "engine", bind)
    pool = getattr(engine, "pool", None)
    if pool is not None:
        with _POOL_LISTENER_LOCK:
            if not event.contains(pool, "checkin", _restore_sqlite_busy_timeout_on_checkin):
                event.listen(pool, "checkin", _restore_sqlite_busy_timeout_on_checkin)

    cap_ms = max(1, min(_PER_ATTEMPT_BUSY_TIMEOUT_MS, int(remaining_s * 1000)))
    sa_conn = db.connection()
    fairy = sa_conn.connection
    raw_conn = getattr(fairy, "dbapi_connection", None)
    if raw_conn is None:
        yield
        return

    orig_bt: Optional[int] = None
    read_cur = raw_conn.cursor()
    try:
        read_cur.execute("PRAGMA busy_timeout")
        row = read_cur.fetchone()
        orig_bt = int(row[0]) if row and row[0] is not None else None
    finally:
        read_cur.close()

    if orig_bt is not None:
        fairy.info.setdefault(_ORIG_BUSY_TIMEOUT_INFO_KEY, orig_bt)

    effective_ms = max(1, min(orig_bt, cap_ms) if (orig_bt is not None and orig_bt > 0) else cap_ms)
    _set_sqlite_busy_timeout(raw_conn, effective_ms)

    try:
        yield
    finally:
        if not sa_conn.closed and not sa_conn.invalidated:
            pending_bt = fairy.info.pop(_ORIG_BUSY_TIMEOUT_INFO_KEY, None)
            if pending_bt is not None:
                try:
                    _set_sqlite_busy_timeout(raw_conn, int(pending_bt))
                except Exception as exc:
                    logger.exception(
                        "Gagal memulihkan PRAGMA busy_timeout=%s saat keluar blok; menginvalidasi koneksi SQLite.",
                        pending_bt,
                    )
                    sa_conn.invalidate(exc)


def _get_session_or_404(db: Session, session_id: str) -> StudySession:
    session = db.query(StudySession).filter(StudySession.session_id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesi belajar dengan ID '{session_id}' tidak ditemukan."
        )
    return session


def get_authorized_study_session_detail_service(
    db: Session,
    session_id: str,
    current_student: Student,
) -> StudySessionResponse:
    """
    Day 22 Authorization Guard untuk GET /api/v1/sessions/{session_id}:
    Hanya Host sesi dan anggota aktif (status CONFIRMED atau ACCEPTED) yang berhak
    membaca detail privat sesi. Outsider serta mantan anggota (WITHDRAWN/REMOVED)
    ditolak dengan HTTP 403 Forbidden.
    """
    session = _get_session_or_404(db, session_id)

    if session.host_id != current_student.student_id:
        active_member = (
            db.query(SessionMember)
            .filter(
                SessionMember.session_id == session_id,
                SessionMember.student_id == current_student.student_id,
                SessionMember.status.in_(_ACTIVE_DETAIL_MEMBER_STATUSES),
            )
            .first()
        )
        if not active_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hanya host atau anggota aktif sesi belajar ini yang berhak mengakses detail sesi."
            )

    return format_study_session_response(session, db)


def _transition_session_status_atomic(
    db: Session,
    session_id: str,
    current_student: Student,
    target_status: str,
    action_label: str,
) -> StudySessionResponse:
    """
    Day 22.2: Transisi atomik status StudySession (CONFIRMED -> COMPLETED / CANCELLED).
    - Otorisasi Host diperiksa pertama kali sebelum mengembalikan status apapun.
    - Idempotent untuk pengulangan target status yang sama (COMPLETED->COMPLETED, CANCELLED->CANCELLED).
    - Menolak konflik terminal (COMPLETED->CANCELLED, CANCELLED->COMPLETED) & status non-CONFIRMED (409).
    - Menggunakan atomic conditional UPDATE + rowcount check untuk keamanan concurrency.
    - Tidak pernah menghapus data anggota maupun mengubah status StudyIntent/GroupProposal.
    """
    started_at = time.monotonic()
    for attempt in range(_MAX_SQLITE_LOCK_RETRIES):
        try:
            with _sqlite_bounded_busy_timeout(db, started_at):
                session = _get_session_or_404(db, session_id)

                # 1. Otorisasi Host wajib mendahului idempotency agar non-host tidak dapat mengintip state
                if session.host_id != current_student.student_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Hanya host sesi belajar yang berhak melakukan {action_label}."
                    )

                # 2. Idempotency jalur cepat jika sudah berada pada target_status
                if session.status == target_status:
                    return format_study_session_response(session, db)

                # 3. Validasi State Machine: hanya status CONFIRMED yang boleh bertransisi
                if session.status != "CONFIRMED":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Tidak dapat melakukan {action_label} pada sesi berstatus '{session.status}'. "
                            f"Transisi hanya diizinkan dari status 'CONFIRMED'."
                        )
                    )

                # 4. Atomic Conditional Update (anti race condition)
                updated_rows = (
                    db.query(StudySession)
                    .filter(
                        StudySession.session_id == session_id,
                        StudySession.host_id == current_student.student_id,
                        StudySession.status == "CONFIRMED",
                    )
                    .update(
                        {
                            StudySession.status: target_status,
                            StudySession.updated_at: datetime.utcnow(),
                        },
                        synchronize_session="fetch",
                    )
                )

                if updated_rows == 1:
                    db.commit()
                    db.expire_all()
                    fresh = _get_session_or_404(db, session_id)
                    return format_study_session_response(fresh, db)

                # Rowcount == 0 berarti transaksi konkuren lain lebih dulu mengubah status sesi
                db.rollback()
                db.expire_all()
                fresh = _get_session_or_404(db, session_id)
                if fresh.status == target_status:
                    return format_study_session_response(fresh, db)

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Konflik transisi status: sesi belajar telah berubah menjadi '{fresh.status}' "
                        f"sebelum {action_label} selesai."
                    )
                )

        except OperationalError as oe:
            db.rollback()
            if _is_sqlite_lock_error(oe):
                delay = _compute_lock_retry_delay(attempt, started_at)
                if delay is not None:
                    db.expire_all()
                    time.sleep(delay)
                    continue
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Database sedang sibuk memproses {action_label}. Silakan coba kembali."
                )
            logger.exception("OperationalError non-lock saat %s pada session_id=%s", action_label, session_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_GENERIC_INTERNAL_ERROR_DETAIL,
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception("Unexpected error saat %s pada session_id=%s", action_label, session_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_GENERIC_INTERNAL_ERROR_DETAIL,
            )

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Gagal menyelesaikan {action_label} karena konflik konkurensi."
    )


def complete_study_session_service(
    db: Session,
    session_id: str,
    current_student: Student,
) -> StudySessionResponse:
    """Day 22.2: Menyelesaikan sesi belajar (CONFIRMED -> COMPLETED) oleh Host."""
    return _transition_session_status_atomic(
        db=db,
        session_id=session_id,
        current_student=current_student,
        target_status="COMPLETED",
        action_label="penyelesaian sesi (complete)",
    )


def cancel_study_session_service(
    db: Session,
    session_id: str,
    current_student: Student,
) -> StudySessionResponse:
    """Day 22.2: Membatalkan sesi belajar (CONFIRMED -> CANCELLED) oleh Host."""
    return _transition_session_status_atomic(
        db=db,
        session_id=session_id,
        current_student=current_student,
        target_status="CANCELLED",
        action_label="pembatalan sesi (cancel)",
    )


def withdraw_from_study_session_service(
    db: Session,
    session_id: str,
    current_student: Student,
) -> SessionWithdrawResponse:
    """
    Day 22.3: Anggota mengundurkan diri dari sesi belajar (CONFIRMED -> WITHDRAWN).
    - Mengembalikan SessionWithdrawResponse minimal (tanpa location, slot, daftar anggota,
      atau profil mahasiswa lain) baik pada withdraw pertama maupun replay idempotent.
    - Host dilarang melakukan withdraw (HTTP 400; Host wajib cancel sesi).
    - Hanya diizinkan selama StudySession.status == 'CONFIRMED' (jika terminal -> HTTP 409).
    - Kebijakan Quorum Option A: TIDAK mengubah StudySession.status meskipun anggota CONFIRMED < min_group_size.
    - Soft-status only: TIDAK menghapus SessionMember, TIDAK mengubah intent_id, TIDAK mengembalikan StudyIntent ke ACTIVE.
    - Atomic conditional UPDATE dengan EXISTS (session status='CONFIRMED') mencegah race condition dengan cancel/complete/remove.
    """
    started_at = time.monotonic()
    for attempt in range(_MAX_SQLITE_LOCK_RETRIES):
        try:
            with _sqlite_bounded_busy_timeout(db, started_at):
                session = _get_session_or_404(db, session_id)

                # 1. Host tidak boleh withdraw dari sesinya sendiri
                if session.host_id == current_student.student_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Host tidak dapat mengundurkan diri dari sesi belajar. Gunakan pembatalan sesi (cancel)."
                    )

                # 2. Pastikan pemanggil tercatat sebagai anggota sesi ini
                member = (
                    db.query(SessionMember)
                    .filter(
                        SessionMember.session_id == session_id,
                        SessionMember.student_id == current_student.student_id,
                    )
                    .first()
                )
                if not member:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Anda bukan anggota sesi belajar ini."
                    )
                if member.role == "HOST":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Host tidak dapat mengundurkan diri dari sesi belajar. Gunakan pembatalan sesi (cancel)."
                    )

                # 3. Sesi terminal (COMPLETED / CANCELLED) atau non-CONFIRMED tidak menerima perubahan keanggotaan
                if session.status != "CONFIRMED":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Tidak dapat mengundurkan diri karena sesi belajar berstatus '{session.status}'."
                    )

                # 4. Idempotency (mengembalikan response minimal tanpa detail privat sesi) & konflik status anggota
                if member.status == "WITHDRAWN":
                    return SessionWithdrawResponse(
                        session_id=session.session_id,
                        session_status=session.status,
                        membership_status="WITHDRAWN",
                    )
                if member.status != "CONFIRMED":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Anggota berstatus '{member.status}' tidak dapat melakukan withdraw."
                    )

                # 5. Atomic Conditional Update (memastikan sesi & member masih CONFIRMED secara atomik di DB)
                session_still_confirmed = (
                    db.query(StudySession.session_id)
                    .filter(
                        StudySession.session_id == session_id,
                        StudySession.status == "CONFIRMED",
                    )
                    .exists()
                )
                updated_rows = (
                    db.query(SessionMember)
                    .filter(
                        SessionMember.session_id == session_id,
                        SessionMember.student_id == current_student.student_id,
                        SessionMember.role == "MEMBER",
                        SessionMember.status == "CONFIRMED",
                        session_still_confirmed,
                    )
                    .update({SessionMember.status: "WITHDRAWN"}, synchronize_session="fetch")
                )

                if updated_rows == 1:
                    db.commit()
                    db.expire_all()
                    fresh_session = _get_session_or_404(db, session_id)
                    return SessionWithdrawResponse(
                        session_id=fresh_session.session_id,
                        session_status=fresh_session.status,
                        membership_status="WITHDRAWN",
                    )

                # Rowcount == 0: cek penyebab konflik dari state terbaru di database
                db.rollback()
                db.expire_all()
                fresh_session = _get_session_or_404(db, session_id)
                if fresh_session.status != "CONFIRMED":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Tidak dapat mengundurkan diri karena sesi belajar telah berubah menjadi '{fresh_session.status}'."
                    )
                fresh_member = (
                    db.query(SessionMember)
                    .filter(
                        SessionMember.session_id == session_id,
                        SessionMember.student_id == current_student.student_id,
                    )
                    .first()
                )
                if fresh_member and fresh_member.status == "WITHDRAWN":
                    return SessionWithdrawResponse(
                        session_id=fresh_session.session_id,
                        session_status=fresh_session.status,
                        membership_status="WITHDRAWN",
                    )

                actual_m_status = fresh_member.status if fresh_member else "MISSING"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Konflik perubahan keanggotaan: status anggota saat ini adalah '{actual_m_status}'."
                )

        except OperationalError as oe:
            db.rollback()
            if _is_sqlite_lock_error(oe):
                delay = _compute_lock_retry_delay(attempt, started_at)
                if delay is not None:
                    db.expire_all()
                    time.sleep(delay)
                    continue
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Database sedang sibuk memproses pengunduran diri anggota. Silakan coba kembali."
                )
            logger.exception("OperationalError non-lock saat withdraw pada session_id=%s", session_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_GENERIC_INTERNAL_ERROR_DETAIL,
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception("Unexpected error saat withdraw pada session_id=%s", session_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_GENERIC_INTERNAL_ERROR_DETAIL,
            )

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Gagal menyelesaikan withdraw karena konflik konkurensi."
    )


def remove_member_from_study_session_service(
    db: Session,
    session_id: str,
    target_student_id: str,
    current_student: Student,
) -> StudySessionResponse:
    """
    Day 22.3: Host mengeluarkan anggota dari sesi belajar (CONFIRMED -> REMOVED).
    - Hanya Host sesi yang berhak melakukan remove (non-host -> HTTP 403).
    - Host tidak dapat mengeluarkan dirinya sendiri (HTTP 400).
    - Hanya diizinkan selama StudySession.status == 'CONFIRMED' (jika terminal -> HTTP 409).
    - Kebijakan Quorum Option A: TIDAK mengubah StudySession.status meskipun anggota CONFIRMED < min_group_size.
    - Soft-status only: TIDAK menghapus SessionMember, TIDAK mengubah intent_id, TIDAK mengembalikan StudyIntent ke ACTIVE.
    - Atomic conditional UPDATE dengan EXISTS (session status='CONFIRMED') mencegah race condition dengan cancel/complete/withdraw.
    """
    started_at = time.monotonic()
    for attempt in range(_MAX_SQLITE_LOCK_RETRIES):
        try:
            with _sqlite_bounded_busy_timeout(db, started_at):
                session = _get_session_or_404(db, session_id)

                # 1. Otorisasi Host
                if session.host_id != current_student.student_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Hanya host sesi belajar yang berhak mengeluarkan anggota."
                    )

                # 2. Host tidak dapat mengeluarkan dirinya sendiri
                if target_student_id == session.host_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Host tidak dapat mengeluarkan dirinya sendiri dari sesi belajar. Gunakan pembatalan sesi (cancel)."
                    )

                # 3. Sesi terminal (COMPLETED / CANCELLED) atau non-CONFIRMED tidak menerima perubahan keanggotaan
                if session.status != "CONFIRMED":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Anggota tidak dapat dikeluarkan karena sesi belajar berstatus '{session.status}'."
                    )

                # 4. Cari anggota target
                target_member = (
                    db.query(SessionMember)
                    .filter(
                        SessionMember.session_id == session_id,
                        SessionMember.student_id == target_student_id,
                    )
                    .first()
                )
                if not target_member:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Mahasiswa '{target_student_id}' bukan anggota sesi belajar ini."
                    )
                if target_member.role == "HOST":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Host tidak dapat dikeluarkan dari sesi belajar."
                    )

                # 5. Idempotency & konflik status anggota
                if target_member.status == "REMOVED":
                    return format_study_session_response(session, db)
                if target_member.status != "CONFIRMED":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Anggota berstatus '{target_member.status}' tidak dapat dikeluarkan (remove)."
                    )

                # 6. Atomic Conditional Update
                session_still_confirmed = (
                    db.query(StudySession.session_id)
                    .filter(
                        StudySession.session_id == session_id,
                        StudySession.status == "CONFIRMED",
                    )
                    .exists()
                )
                updated_rows = (
                    db.query(SessionMember)
                    .filter(
                        SessionMember.session_id == session_id,
                        SessionMember.student_id == target_student_id,
                        SessionMember.role == "MEMBER",
                        SessionMember.status == "CONFIRMED",
                        session_still_confirmed,
                    )
                    .update({SessionMember.status: "REMOVED"}, synchronize_session="fetch")
                )

                if updated_rows == 1:
                    db.commit()
                    db.expire_all()
                    fresh_session = _get_session_or_404(db, session_id)
                    return format_study_session_response(fresh_session, db)

                # Rowcount == 0: evaluasi konflik dari state terbaru di database
                db.rollback()
                db.expire_all()
                fresh_session = _get_session_or_404(db, session_id)
                if fresh_session.status != "CONFIRMED":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Anggota tidak dapat dikeluarkan karena sesi belajar telah berubah menjadi '{fresh_session.status}'."
                    )
                fresh_target = (
                    db.query(SessionMember)
                    .filter(
                        SessionMember.session_id == session_id,
                        SessionMember.student_id == target_student_id,
                    )
                    .first()
                )
                if fresh_target and fresh_target.status == "REMOVED":
                    return format_study_session_response(fresh_session, db)

                actual_m_status = fresh_target.status if fresh_target else "MISSING"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Konflik perubahan keanggotaan: status anggota saat ini adalah '{actual_m_status}'."
                )

        except OperationalError as oe:
            db.rollback()
            if _is_sqlite_lock_error(oe):
                delay = _compute_lock_retry_delay(attempt, started_at)
                if delay is not None:
                    db.expire_all()
                    time.sleep(delay)
                    continue
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Database sedang sibuk memproses pengeluaran anggota. Silakan coba kembali."
                )
            logger.exception("OperationalError non-lock saat remove anggota pada session_id=%s", session_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_GENERIC_INTERNAL_ERROR_DETAIL,
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception("Unexpected error saat remove anggota pada session_id=%s", session_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_GENERIC_INTERNAL_ERROR_DETAIL,
            )

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Gagal menyelesaikan remove anggota karena konflik konkurensi."
    )
