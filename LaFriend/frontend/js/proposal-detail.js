// ==============================================================================
// proposal-detail.js - Logika Halaman Detail Group Proposal (Day 24.2 & 24.3)
// ==============================================================================
// Bertanggung jawab atas:
// 1. Mengambil detail proposal segar dari GET /api/v1/group-proposals/{proposal_id}
//    (tidak pernah memakai localStorage sebagai sumber kebenaran proposal).
// 2. Lookup nama & kode mata kuliah dari GET /api/v1/courses/{course_id}.
// 3. Menampilkan 4 bagian utama: Ringkasan Proposal, Progres Kuorum (murni dari
//    active_member_count & quorum_reached backend), Daftar Undangan (privacy-safe),
//    dan Kontrol Aksi sesuai matriks ProposalStatus x InvitationStatus.
// 4. Penanganan otorisasi 403 tanpa menghapus token, 401 logout, 404, 409, & network error.
// ==============================================================================

const proposalDetailState = {
  proposalId: "",
  user: null,
  proposal: null,
  courseCache: {},
  isActionPending: false,
  requestSeq: 0,
};

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("proposalDetailPageRoot")) {
    initProposalDetailPage();
  }
});

function initProposalDetailPage() {
  const user = app.requireAuth();
  if (!user) return;
  proposalDetailState.user = user;

  const params = new URLSearchParams(window.location.search);
  const proposalId = (params.get("id") || "").trim();
  proposalDetailState.proposalId = proposalId;

  // Tampilkan flash message bila baru diarahkan dari halaman matching.html
  const alertBox = document.getElementById("proposalAlertContainer");
  const flashRaw = sessionStorage.getItem(SESSION_FLASH_KEY);
  let hasInitialFlash = false;
  if (flashRaw) {
    sessionStorage.removeItem(SESSION_FLASH_KEY);
    hasInitialFlash = true;
    try {
      const parsed = JSON.parse(flashRaw);
      renderInlineAlert(alertBox, parsed.variant || "success", parsed.message || "");
    } catch {
      renderInlineAlert(alertBox, "success", flashRaw);
    }
  }

  const btnRefresh = document.getElementById("btnRefreshProposal");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      if (!proposalDetailState.isActionPending) {
        loadProposalDetail({ preserveAlert: false });
      }
    });
  }

  if (!proposalId) {
    const sub = document.getElementById("proposalHeaderSub");
    if (sub) sub.textContent = "ID proposal tidak valid";
    const container = document.getElementById("proposalDetailContent");
    if (container) {
      renderStatePanel(container, {
        icon: "bi-search",
        iconVariant: "warning",
        title: "Proposal Tidak Ditemukan",
        description: "Tautan detail proposal tidak menyertakan ID proposal yang valid.",
        actions: [{ label: "Kembali ke Undangan", href: "invitations.html", variantClass: "btn-la--primary" }],
      });
    }
    return;
  }

  loadProposalDetail({ preserveAlert: hasInitialFlash });
}

async function resolveProposalCourse(courseId) {
  if (!courseId) return null;
  if (proposalDetailState.courseCache[courseId]) {
    return proposalDetailState.courseCache[courseId];
  }
  try {
    const course = await app.courses.getDetail(courseId);
    if (course && course.course_id) {
      proposalDetailState.courseCache[courseId] = course;
      return course;
    }
  } catch {
    // Graceful fallback: gagal lookup course tidak boleh menggagalkan detail proposal
  }
  return null;
}

async function loadProposalDetail({ preserveAlert = false } = {}) {
  const container = document.getElementById("proposalDetailContent");
  const alertBox = document.getElementById("proposalAlertContainer");
  const headerSub = document.getElementById("proposalHeaderSub");
  if (!container) return;

  if (!preserveAlert && alertBox) {
    renderInlineAlert(alertBox, "info", "");
  }

  const seq = ++proposalDetailState.requestSeq;
  renderStatePanel(container, {
    icon: "spinner",
    title: "Memuat Detail Proposal...",
    description: "Mengambil status kuorum dan undangan terbaru dari server.",
  });

  try {
    const proposal = await app.proposals.getDetail(proposalDetailState.proposalId);
    if (seq !== proposalDetailState.requestSeq) return;

    proposalDetailState.proposal = proposal;
    const course = await resolveProposalCourse(proposal.course_id);
    if (seq !== proposalDetailState.requestSeq) return;

    renderProposalDetail(proposal, course);
  } catch (err) {
    if (seq !== proposalDetailState.requestSeq) return;
    proposalDetailState.proposal = null;

    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }

    if (err.status === 403) {
      // PENTING: HTTP 403 bukan logout; jangan hapus token!
      if (headerSub) headerSub.textContent = "Akses ditolak";
      renderStatePanel(container, {
        icon: "bi-shield-lock",
        iconVariant: "danger",
        title: "Akses Ditolak",
        description: err.message || "Kamu tidak memiliki izin untuk melihat usulan kelompok ini.",
        actions: [
          { label: "Kembali ke Undangan", href: "invitations.html", variantClass: "btn-la--primary" },
          { label: "Ke Dashboard", href: "dashboard.html", variantClass: "btn-la--secondary" },
        ],
      });
      return;
    }

    if (err.status === 404) {
      if (headerSub) headerSub.textContent = "Proposal tidak ditemukan";
      renderStatePanel(container, {
        icon: "bi-question-circle",
        iconVariant: "warning",
        title: "Proposal Tidak Ditemukan",
        description: err.message || "Usulan kelompok yang kamu cari tidak ditemukan di server.",
        actions: [
          { label: "Kembali ke Undangan", href: "invitations.html", variantClass: "btn-la--primary" },
          { label: "Cari Partner", href: "matching.html", variantClass: "btn-la--secondary" },
        ],
      });
      return;
    }

    if (err.isNetworkError || err.status === 0) {
      if (headerSub) headerSub.textContent = "Koneksi bermasalah";
      renderStatePanel(container, {
        icon: "bi-wifi-off",
        iconVariant: "warning",
        title: "Koneksi Bermasalah",
        description: "Tidak dapat terhubung ke server. Periksa jaringanmu lalu coba muat ulang.",
        actions: [
          { label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadProposalDetail({ preserveAlert: false }) },
          { label: "Kembali ke Undangan", href: "invitations.html", variantClass: "btn-la--secondary" },
        ],
      });
      return;
    }

    if (headerSub) headerSub.textContent = "Gagal memuat proposal";
    renderStatePanel(container, {
      icon: "bi-exclamation-octagon",
      iconVariant: "danger",
      title: "Gagal Memuat Proposal",
      description: err.status >= 500
        ? "Terjadi kesalahan pada server. Silakan coba beberapa saat lagi."
        : (err.message || "Terjadi kesalahan saat mengambil detail proposal."),
      actions: [
        { label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadProposalDetail({ preserveAlert: false }) },
        { label: "Kembali ke Undangan", href: "invitations.html", variantClass: "btn-la--secondary" },
      ],
    });
  }
}

function setProposalActionButtonsDisabled(disabled, activeBtn) {
  document.querySelectorAll("#proposalDetailContent button[data-proposal-action], #btnRefreshProposal").forEach((btn) => {
    btn.disabled = Boolean(disabled);
    if (disabled && btn === activeBtn) {
      btn.dataset.loading = "true";
    } else if (!disabled) {
      delete btn.dataset.loading;
    }
  });
}

function renderProposalDetail(proposal, course) {
  const container = document.getElementById("proposalDetailContent");
  const headerSub = document.getElementById("proposalHeaderSub");
  const user = proposalDetailState.user;
  if (!container || !proposal || !user) return;

  const proposalStatus = (proposal.status || "").toUpperCase();
  const statusMeta = getProposalStatusMeta(proposalStatus);
  const invitations = Array.isArray(proposal.invitations) ? proposal.invitations : [];
  const isHost = proposal.host_student_id === user.student_id;
  const myInvitation = invitations.find((inv) => inv.recipient_id === user.student_id) || null;
  const hostName = (proposal.host_student && proposal.host_student.full_name) ? proposal.host_student.full_name : "Host";

  if (headerSub) {
    headerSub.textContent = `${statusMeta.label} · ${isHost ? "Host" : "Calon Anggota"}`;
  }

  container.textContent = "";
  const fragment = document.createDocumentFragment();

  // --- BAGIAN 1: RINGKASAN PROPOSAL ---
  const summaryCard = createEl("section", "detail-section-card");
  summaryCard.setAttribute("aria-label", "Ringkasan Proposal");

  const badgeRow = createEl("div", "badge-row");
  badgeRow.appendChild(createEl("span", `s-badge ${statusMeta.badgeClass}`, statusMeta.label));
  badgeRow.appendChild(
    createEl("span", `s-badge ${isHost ? "s-badge--host" : "s-badge--member"}`, isHost ? "Kamu adalah HOST" : "Kamu adalah INVITEE")
  );
  summaryCard.appendChild(badgeRow);

  const courseDisplay = course
    ? [course.course_code, course.course_name].filter(Boolean).join(" — ")
    : "Usulan Kelompok Belajar";
  summaryCard.appendChild(createEl("h2", "detail-hero-title", courseDisplay));
  summaryCard.appendChild(createEl("div", "detail-course-line", `Dibuat oleh ${hostName}${isHost ? " (Kamu)" : ""}`));

  if (proposal.message && proposal.message.trim()) {
    summaryCard.appendChild(createEl("p", "detail-description", proposal.message.trim()));
  }

  // KPI Skor dari backend
  const kpiGrid = createEl("div", "score-kpi-grid");
  [
    { label: "Group Quality", sub: "GQ Score", val: formatProposalScore(proposal.group_quality_score), highlight: true },
    { label: "Avg Pair", sub: "APS", val: formatProposalScore(proposal.average_pair_score), highlight: false },
    { label: "Min Pair", sub: "MPS", val: formatProposalScore(proposal.minimum_pair_score), highlight: false },
  ].forEach((kpi) => {
    const box = createEl("div", `score-kpi-box${kpi.highlight ? " score-kpi-box--highlight" : ""}`);
    box.appendChild(createEl("div", "score-kpi-label", kpi.label));
    box.appendChild(createEl("div", "score-kpi-val", kpi.val));
    box.appendChild(createEl("div", "score-kpi-sub", kpi.sub));
    kpiGrid.appendChild(box);
  });
  summaryCard.appendChild(kpiGrid);

  // Jadwal Rekomendasi (Read-only)
  if (proposal.selected_schedule && typeof proposal.selected_schedule === "object") {
    const sched = proposal.selected_schedule;
    const schedBox = createEl("div", "schedule-primary-box");
    schedBox.appendChild(createEl("div", "schedule-readonly-tag", "Jadwal Rekomendasi Kelompok"));
    schedBox.appendChild(createEl("div", "slot-item-date", formatSessionDateIndo(sched.date)));
    const durSuffix = sched.duration_minutes ? ` (${sched.duration_minutes} menit)` : "";
    schedBox.appendChild(createEl("div", "slot-item-time", `${sched.start_time || "--:--"} – ${sched.end_time || "--:--"}${durSuffix}`));
    summaryCard.appendChild(schedBox);
  }

  const kvGrid = createEl("div", "detail-kv-grid");
  const kvItems = [
    { label: "Batas Kedaluwarsa", value: formatDateTimeIndo(proposal.expires_at) },
    { label: "Rentang Grup", value: `${proposal.min_group_size_bound}–${proposal.max_group_size_bound} mahasiswa` },
  ];
  if (proposal.finalized_at) {
    kvItems.push({ label: "Difinalisasi Pada", value: formatDateTimeIndo(proposal.finalized_at), full: true });
  }
  kvItems.forEach((item) => {
    const box = createEl("div", `detail-kv-item${item.full ? " detail-kv-item--full" : ""}`);
    box.appendChild(createEl("div", "detail-kv-label", item.label));
    box.appendChild(createEl("div", "detail-kv-value", item.value));
    kvGrid.appendChild(box);
  });
  summaryCard.appendChild(kvGrid);
  fragment.appendChild(summaryCard);

  // --- BAGIAN 2: PROGRES KUORUM (MURNI DARI active_member_count & quorum_reached BACKEND) ---
  const quorumCard = createEl("section", "detail-section-card");
  quorumCard.setAttribute("aria-label", "Progres Kuorum");

  const qHead = createEl("div", "detail-section-header");
  const qTitle = createEl("div", "detail-section-title");
  qTitle.appendChild(createIcon("bi-graph-up-arrow"));
  qTitle.appendChild(createEl("span", "", "Progres Kuorum"));
  qHead.appendChild(qTitle);
  const quorumReached = Boolean(proposal.quorum_reached);
  qHead.appendChild(
    createEl("span", `s-badge ${quorumReached ? "s-badge--confirmed" : "s-badge--pending"}`, quorumReached ? "Kuorum Tercapai" : "Belum Kuorum")
  );
  quorumCard.appendChild(qHead);

  const activeCount = Number(proposal.active_member_count ?? 1);
  const minBound = Math.max(1, Number(proposal.min_group_size_bound ?? 2));
  const pct = Math.min(100, Math.round((activeCount / minBound) * 100));

  const qWrap = createEl("div", "quorum-progress-wrap");
  const numRow = createEl("div", "quorum-numbers-row");
  numRow.appendChild(createEl("div", "quorum-big-count", `${activeCount} anggota aktif`));
  numRow.appendChild(createEl("div", "quorum-bounds-label", `Minimal ${proposal.min_group_size_bound} · Maksimal ${proposal.max_group_size_bound}`));
  qWrap.appendChild(numRow);

  const track = createEl("div", "quorum-bar-track");
  const fill = createEl("div", `quorum-bar-fill${quorumReached ? " quorum-bar-fill--reached" : ""}`);
  fill.style.width = `${pct}%`;
  track.appendChild(fill);
  qWrap.appendChild(track);

  qWrap.appendChild(createEl("div", "lifecycle-status-note", getQuorumGuidanceText(proposalStatus, isHost, quorumReached)));
  quorumCard.appendChild(qWrap);
  fragment.appendChild(quorumCard);

  // --- BAGIAN 3: DAFTAR UNDANGAN & ANGGOTA (STRICT PRIVACY: tanpa email, NIM, atau ID internal) ---
  const invCard = createEl("section", "detail-section-card");
  invCard.setAttribute("aria-label", "Daftar Undangan Anggota");

  const invHead = createEl("div", "detail-section-header");
  const invTitle = createEl("div", "detail-section-title");
  invTitle.appendChild(createIcon("bi-people-fill"));
  invTitle.appendChild(createEl("span", "", "Daftar Anggota & Undangan"));
  invHead.appendChild(invTitle);
  invHead.appendChild(createEl("span", "s-badge s-badge--neutral", `${1 + invitations.length} orang`));
  invCard.appendChild(invHead);

  const memList = createEl("div", "member-list");

  // Baris Host
  memList.appendChild(
    buildProposalParticipantRow({
      displayName: hostName,
      studyProgram: proposal.host_student ? proposal.host_student.study_program : "",
      academicYear: proposal.host_student ? proposal.host_student.academic_year : null,
      isMe: isHost,
      isHostRow: true,
      statusMeta: { label: "Host Aktif", badgeClass: "s-badge--confirmed" },
    })
  );

  // Baris Invitee (menggunakan InvitationStatus terpisah)
  invitations.forEach((inv) => {
    const recName = (inv.recipient && inv.recipient.full_name) ? inv.recipient.full_name : "Calon Anggota";
    const invStatus = (inv.status || "").toUpperCase();
    const invMeta = getInvitationStatusMeta(invStatus);
    const isInactive = invStatus === "REJECTED" || invStatus === "WITHDRAWN" || invStatus === "EXPIRED";

    memList.appendChild(
      buildProposalParticipantRow({
        displayName: recName,
        studyProgram: inv.recipient ? inv.recipient.study_program : "",
        academicYear: inv.recipient ? inv.recipient.academic_year : null,
        isMe: inv.recipient_id === user.student_id,
        isHostRow: false,
        statusMeta: invMeta,
        isInactive,
      })
    );
  });

  invCard.appendChild(memList);
  fragment.appendChild(invCard);

  // --- BAGIAN 4: KONTROL AKSI ---
  const actionCard = createEl("section", "detail-section-card");
  actionCard.setAttribute("aria-label", "Kontrol Aksi Proposal");

  const actHead = createEl("div", "detail-section-header");
  const actTitle = createEl("div", "detail-section-title");
  actTitle.appendChild(createIcon("bi-sliders"));
  actTitle.appendChild(createEl("span", "", "Tindakan"));
  actHead.appendChild(actTitle);
  actHead.appendChild(createEl("span", `s-badge ${statusMeta.badgeClass}`, statusMeta.label));
  actionCard.appendChild(actHead);

  const actionsStack = createEl("div", "lifecycle-actions-stack");
  actionsStack.id = "proposalActionsSlot";

  if (isHost) {
    if (typeof renderHostProposalControls === "function") {
      renderHostProposalControls(actionsStack, { proposal, proposalStatus });
    } else {
      renderHostFallbackControls(actionsStack, { proposal, proposalStatus });
    }
  } else {
    renderInviteeProposalControls(actionsStack, { proposal, proposalStatus, myInvitation, hostName });
  }

  actionCard.appendChild(actionsStack);
  fragment.appendChild(actionCard);

  container.appendChild(fragment);
}

function buildProposalParticipantRow({ displayName, studyProgram, academicYear, isMe, isHostRow, statusMeta, isInactive = false }) {
  const row = createEl("div", `member-item-row${isInactive ? " member-item-row--inactive" : ""}`);
  const left = createEl("div", "member-item-left");
  left.appendChild(createEl("div", "member-avatar", (displayName || "M").trim().charAt(0).toUpperCase() || "M"));

  const info = createEl("div", "member-info");
  const nameRow = createEl("div", "member-name-row");
  nameRow.appendChild(createEl("span", "member-name", displayName));
  if (isMe) nameRow.appendChild(createEl("span", "s-badge s-badge--you", "Kamu"));
  info.appendChild(nameRow);

  const subParts = [];
  if (studyProgram) subParts.push(studyProgram);
  if (academicYear) subParts.push(`Angkatan ${academicYear}`);
  if (subParts.length > 0) {
    info.appendChild(createEl("div", "invitation-sub-meta", subParts.join(" · ")));
  }

  const badges = createEl("div", "badge-row");
  badges.appendChild(createEl("span", `s-badge ${isHostRow ? "s-badge--host" : "s-badge--member"}`, isHostRow ? "HOST" : "MEMBER"));
  badges.appendChild(createEl("span", `s-badge ${statusMeta.badgeClass}`, statusMeta.label));
  info.appendChild(badges);

  left.appendChild(info);
  row.appendChild(left);
  return row;
}

function getQuorumGuidanceText(proposalStatus, isHost, quorumReached) {
  if (proposalStatus === "PENDING_RESPONSES") {
    return isHost
      ? "Menunggu calon anggota merespons undangan agar jumlah anggota aktif mencapai batas minimal kuorum."
      : "Proposal masih menunggu respons calon anggota lain untuk mencapai kuorum.";
  }
  if (proposalStatus === "QUORUM_REACHED") {
    return isHost
      ? "Kuorum telah terpenuhi! Kamu dapat memfinalisasi proposal sekarang atau menunggu anggota lain yang masih pending."
      : "Kuorum telah tercapai. Menunggu Host memfinalisasi proposal.";
  }
  if (proposalStatus === "READY_FOR_SESSION") {
    return isHost
      ? "Proposal telah difinalisasi. Langkah terakhir: eksekusi proposal untuk membentuk Study Session resmi."
      : "Proposal telah difinalisasi oleh Host. Menunggu Host mengeksekusi pembentukan sesi belajar.";
  }
  if (proposalStatus === "SESSION_EXECUTED") {
    return "Study Session resmi telah berhasil dibentuk dari proposal ini.";
  }
  if (proposalStatus === "NOT_FORMED") {
    return "Kuorum tidak dapat terpenuhi sehingga kelompok belajar tidak terbentuk.";
  }
  if (proposalStatus === "CANCELLED") {
    return "Proposal kelompok ini telah dibatalkan oleh Host.";
  }
  if (proposalStatus === "EXPIRED") {
    return "Batas waktu respons proposal telah berakhir (kedaluwarsa).";
  }
  return quorumReached ? "Kuorum telah tercapai." : "Status kuorum mengikuti pembaruan terbaru server.";
}

function renderHostFallbackControls(container, { proposal, proposalStatus }) {
  if ((proposalStatus === "SESSION_EXECUTED" || proposal.session_id) && proposal.session_id) {
    const link = createEl("a", "btn-la btn-la--primary");
    link.id = "btnOpenExecutedSession";
    link.href = `session-detail.html?id=${encodeURIComponent(proposal.session_id)}`;
    link.appendChild(createIcon("bi-calendar2-check-fill"));
    link.appendChild(createEl("span", "", "Buka Detail Sesi"));
    container.appendChild(link);
    return;
  }
  container.appendChild(
    createEl("div", "lifecycle-status-note", `Status proposal saat ini: ${getProposalStatusMeta(proposalStatus).label}.`)
  );
}

// Matriks Lengkap Status Invitee x Status Proposal (Day 24.0 Klarifikasi #2)
function renderInviteeProposalControls(container, { proposal, proposalStatus, myInvitation, hostName }) {
  container.textContent = "";
  const invStatus = myInvitation ? (myInvitation.status || "").toUpperCase() : "";

  // 1. Invitee PENDING pada PENDING_RESPONSES atau QUORUM_REACHED -> Tombol Terima & Tolak
  if (invStatus === "PENDING" && (proposalStatus === "PENDING_RESPONSES" || proposalStatus === "QUORUM_REACHED")) {
    const btnAccept = createEl("button", "btn-la btn-la--success");
    btnAccept.type = "button";
    btnAccept.id = "btnAcceptProposalInvite";
    btnAccept.dataset.proposalAction = "accept";
    btnAccept.appendChild(createIcon("bi-check-circle-fill"));
    btnAccept.appendChild(createEl("span", "", "Terima Undangan (Accept)"));
    btnAccept.addEventListener("click", () => {
      if (proposalDetailState.isActionPending) return;
      openSharedConfirmModal({
        title: "Terima Undangan Kelompok?",
        message: `Kamu akan menerima undangan kelompok belajar dari ${hostName}. Backend akan menghitung ulang status kuorum secara otomatis.`,
        confirmLabel: "Ya, Terima",
        confirmVariant: "btn-la--success",
        isBusyCheck: () => proposalDetailState.isActionPending,
        onConfirm: () => executeProposalInviteeRespond(myInvitation.invitation_id, "ACCEPT", "", btnAccept),
      });
    });

    const btnDecline = createEl("button", "btn-la btn-la--outline-danger");
    btnDecline.type = "button";
    btnDecline.id = "btnDeclineProposalInvite";
    btnDecline.dataset.proposalAction = "decline";
    btnDecline.appendChild(createIcon("bi-x-circle-fill"));
    btnDecline.appendChild(createEl("span", "", "Tolak Undangan (Decline)"));
    btnDecline.addEventListener("click", () => {
      if (proposalDetailState.isActionPending) return;
      openSharedConfirmModal({
        title: "Tolak Undangan Kelompok?",
        message: `Apakah kamu yakin ingin menolak undangan dari ${hostName}? Keputusan ini tidak dapat diubah kembali.`,
        confirmLabel: "Ya, Tolak",
        confirmVariant: "btn-la--danger",
        showReasonInput: true,
        reasonPlaceholder: "Alasan penolakan (opsional)...",
        isBusyCheck: () => proposalDetailState.isActionPending,
        onConfirm: (reasonText) => executeProposalInviteeRespond(myInvitation.invitation_id, "DECLINE", reasonText, btnDecline),
      });
    });

    container.appendChild(btnAccept);
    container.appendChild(btnDecline);
    return;
  }

  // 2. Invitee ACCEPTED
  if (invStatus === "ACCEPTED") {
    if ((proposalStatus === "SESSION_EXECUTED" || proposal.session_id) && proposal.session_id) {
      const link = createEl("a", "btn-la btn-la--primary");
      link.id = "btnOpenExecutedSession";
      link.href = `session-detail.html?id=${encodeURIComponent(proposal.session_id)}`;
      link.appendChild(createIcon("bi-calendar2-check-fill"));
      link.appendChild(createEl("span", "", "Buka Detail Sesi"));
      container.appendChild(link);
      return;
    }

    let note = "Keputusanmu (Diterima) sudah tercatat.";
    if (proposalStatus === "PENDING_RESPONSES") {
      note = "Keputusanmu (Diterima) sudah tercatat. Menunggu anggota lain merespons agar kuorum kelompok tercapai.";
    } else if (proposalStatus === "QUORUM_REACHED") {
      note = "Kuorum telah tercapai! Menunggu Host memfinalisasi proposal.";
    } else if (proposalStatus === "READY_FOR_SESSION") {
      note = "Proposal telah difinalisasi. Menunggu Host mengeksekusi pembentukan sesi belajar.";
    } else if (proposalStatus === "CANCELLED") {
      note = "Proposal ini telah dibatalkan oleh Host.";
    } else if (proposalStatus === "NOT_FORMED") {
      note = "Kelompok tidak terbentuk karena kuorum gagal terpenuhi.";
    } else if (proposalStatus === "EXPIRED") {
      note = "Proposal telah kedaluwarsa sebelum difinalisasi.";
    }
    container.appendChild(createEl("div", "lifecycle-status-note", note));
    return;
  }

  // 3. Invitee REJECTED / WITHDRAWN / EXPIRED pada status proposal apa pun -> tanpa tombol respons
  if (invStatus === "REJECTED") {
    container.appendChild(createEl("div", "lifecycle-status-note", "Status undanganmu: Ditolak. Tidak ada tindakan lanjutan yang tersedia."));
    return;
  }
  if (invStatus === "WITHDRAWN") {
    container.appendChild(createEl("div", "lifecycle-status-note", "Status undanganmu: Ditarik. Undangan tidak lagi aktif."));
    return;
  }
  if (invStatus === "EXPIRED") {
    container.appendChild(createEl("div", "lifecycle-status-note", "Status undanganmu: Kedaluwarsa. Undangan tidak lagi menerima respons."));
    return;
  }

  // 4. Fallback aman untuk kombinasi tak terduga -> read-only tanpa tombol mutasi
  container.appendChild(createEl("div", "lifecycle-status-note", "Tidak ada tindakan yang tersedia untuk status undangan saat ini."));
}

async function executeProposalInviteeRespond(invitationId, decision, reason, triggerBtn) {
  if (proposalDetailState.isActionPending) return;
  const alertBox = document.getElementById("proposalAlertContainer");
  proposalDetailState.isActionPending = true;
  setProposalActionButtonsDisabled(true, triggerBtn);

  const payload = { decision };
  if (reason && reason.trim()) {
    payload.reason = reason.trim();
  }

  try {
    const invRes = await app.invitations.respond(invitationId, payload);
    const finalStatus = (invRes && invRes.status ? invRes.status : "").toUpperCase();
    const msg =
      finalStatus === "ACCEPTED"
        ? "Undangan berhasil diterima! Memuat pembaruan kuorum terbaru dari server."
        : "Undangan berhasil ditolak.";
    renderInlineAlert(alertBox, "success", msg);
    await loadProposalDetail({ preserveAlert: true });
  } catch (err) {
    await handleProposalActionError(err);
  } finally {
    proposalDetailState.isActionPending = false;
    setProposalActionButtonsDisabled(false);
  }
}

async function handleProposalActionError(err) {
  const alertBox = document.getElementById("proposalAlertContainer");
  if (err.status === 401) {
    app.handleUnauthorized();
    return;
  }
  if (err.status === 403) {
    renderInlineAlert(alertBox, "danger", err.message || "Kamu tidak memiliki izin untuk melakukan tindakan ini.");
    await loadProposalDetail({ preserveAlert: true });
    return;
  }
  if (err.status === 404) {
    renderInlineAlert(alertBox, "warning", err.message || "Proposal atau undangan tidak ditemukan.");
    await loadProposalDetail({ preserveAlert: true });
    return;
  }
  if (err.status === 409) {
    renderInlineAlert(
      alertBox,
      "warning",
      `${err.message || "Terjadi konflik status proposal."} Menampilkan kondisi terbaru dari server.`
    );
    await loadProposalDetail({ preserveAlert: true });
    return;
  }
  if (err.status === 400 || err.status === 422) {
    renderInlineAlert(alertBox, "danger", err.message || "Tindakan tidak dapat diproses pada status proposal saat ini.");
    await loadProposalDetail({ preserveAlert: true });
    return;
  }
  if (err.isNetworkError || err.status === 0) {
    renderInlineAlert(alertBox, "warning", "Koneksi ke server terputus. Periksa jaringanmu lalu coba lagi.");
    return;
  }
  renderInlineAlert(alertBox, "danger", "Terjadi kesalahan pada server saat memproses permintaan. Silakan coba lagi.");
}

function formatProposalScore(val) {
  const num = Number(val);
  return Number.isFinite(num) ? num.toFixed(1) : "0.0";
}
