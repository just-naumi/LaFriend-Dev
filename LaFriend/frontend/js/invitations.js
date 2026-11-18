// ==============================================================================
// invitations.js - Logika Halaman Undangan Masuk & Undangan Terkirim (Day 24.2)
// ==============================================================================
// Bertanggung jawab atas:
// 1. Tab Undangan Masuk (GET /api/v1/invitations/inbox) + filter status lokal.
// 2. Aksi Terima (ACCEPT) & Tolak (DECLINE -> backend menyimpan status REJECTED)
//    melalui POST /api/v1/invitations/{invitation_id}/respond.
// 3. Tab Undangan Terkirim (GET /api/v1/invitations/sent) dikelompokkan berdasarkan
//    proposal_id dengan tautan ke proposal-detail.html?id=...
//    CATATAN KONTRAK: Tab ini BUKAN daftar lengkap seluruh proposal host dan tidak
//    mengasumsikan status proposal atau kuorum dari objek InvitationResponse.
// 4. Privasi ketat: tidak pernah merender email, NIM, student_id, atau intent_id.
// ==============================================================================

const _RESPONSIVE_PROPOSAL_STATUSES = new Set(["PENDING_RESPONSES", "QUORUM_REACHED"]);

const invitationsPageState = {
  user: null,
  activeTab: "inbox", // "inbox" | "sent"
  inboxStatusFilter: "",
  inboxItems: [],
  sentItems: [],
  proposalStatusById: {},
  isLoading: false,
  isRespondPending: false,
  requestSeq: 0,
};

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("invitationsPageRoot")) {
    initInvitationsPage();
  }
});

function initInvitationsPage() {
  const user = app.requireAuth();
  if (!user) return;
  invitationsPageState.user = user;

  const userNameEl = document.getElementById("invitationsUserName");
  const avatarEl = document.getElementById("invitationsUserAvatar");
  if (userNameEl) userNameEl.textContent = user.full_name || "Mahasiswa";
  if (avatarEl) {
    avatarEl.textContent = ((user.full_name || "M").trim().charAt(0) || "M").toUpperCase();
  }

  // Cek query param ?tab=sent
  const initialTab = (new URLSearchParams(window.location.search).get("tab") || "").trim().toLowerCase();
  if (initialTab === "sent") {
    invitationsPageState.activeTab = "sent";
  }

  const tabBar = document.getElementById("invitationsTabBar");
  if (tabBar) {
    tabBar.addEventListener("click", (e) => {
      const btn = e.target.closest(".la-tab-btn");
      if (!btn || invitationsPageState.isRespondPending) return;
      const nextTab = btn.dataset.tab === "sent" ? "sent" : "inbox";
      if (nextTab === invitationsPageState.activeTab && !invitationsPageState.isLoading) return;
      invitationsPageState.activeTab = nextTab;
      syncTabButtonsUI();
      loadCurrentInvitationsTab();
    });
  }

  const filterBar = document.getElementById("invitationStatusFilterBar");
  if (filterBar) {
    filterBar.addEventListener("click", (e) => {
      const btn = e.target.closest(".filter-pill-btn");
      if (!btn || invitationsPageState.activeTab !== "inbox") return;
      invitationsPageState.inboxStatusFilter = btn.dataset.status || "";
      filterBar.querySelectorAll(".filter-pill-btn").forEach((pill) => {
        pill.classList.toggle("active", pill === btn);
      });
      renderInboxList();
    });
  }

  const btnRefresh = document.getElementById("btnRefreshInvitations");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      if (!invitationsPageState.isRespondPending) {
        loadCurrentInvitationsTab({ preserveAlert: false });
      }
    });
  }

  syncTabButtonsUI();
  loadCurrentInvitationsTab({ preserveAlert: false });
}

function syncTabButtonsUI() {
  const tabInbox = document.getElementById("tabInbox");
  const tabSent = document.getElementById("tabSent");
  const filterBar = document.getElementById("invitationStatusFilterBar");
  const isInbox = invitationsPageState.activeTab === "inbox";

  if (tabInbox) {
    tabInbox.classList.toggle("active", isInbox);
    tabInbox.setAttribute("aria-selected", String(isInbox));
  }
  if (tabSent) {
    tabSent.classList.toggle("active", !isInbox);
    tabSent.setAttribute("aria-selected", String(!isInbox));
  }
  if (filterBar) {
    filterBar.classList.toggle("d-none", !isInbox);
  }
}

async function loadCurrentInvitationsTab({ preserveAlert = false } = {}) {
  const container = document.getElementById("invitationsListContainer");
  const alertBox = document.getElementById("invitationsAlertContainer");
  const countPill = document.getElementById("invitationsCountPill");
  if (!container) return;

  if (!preserveAlert && alertBox) {
    renderInlineAlert(alertBox, "info", "");
  }

  const seq = ++invitationsPageState.requestSeq;
  invitationsPageState.isLoading = true;
  const isInbox = invitationsPageState.activeTab === "inbox";

  renderStatePanel(container, {
    icon: "spinner",
    title: isInbox ? "Memuat Undangan Masuk..." : "Memuat Undangan Terkirim...",
    description: "Mengambil data terbaru dari server.",
  });

  try {
    if (isInbox) {
      const data = await app.invitations.getInbox("");
      if (seq !== invitationsPageState.requestSeq) return;
      const items = Array.isArray(data) ? data : [];
      const syncRes = await syncPendingInboxProposalStatuses(items, seq);
      if (seq !== invitationsPageState.requestSeq) return;
      if (syncRes.unauthorized) return;
      invitationsPageState.inboxItems = items;
      invitationsPageState.proposalStatusById = syncRes.statusMap;
      renderInboxList();
    } else {
      const data = await app.invitations.getSent("");
      if (seq !== invitationsPageState.requestSeq) return;
      invitationsPageState.sentItems = Array.isArray(data) ? data : [];
      renderSentGroupedList();
    }
  } catch (err) {
    if (seq !== invitationsPageState.requestSeq) return;
    if (countPill) countPill.textContent = "0 item";

    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }

    if (err.isNetworkError || err.status === 0) {
      renderStatePanel(container, {
        icon: "bi-wifi-off",
        iconVariant: "warning",
        title: "Koneksi Bermasalah",
        description: "Tidak dapat terhubung ke server untuk memuat undangan.",
        actions: [{ label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadCurrentInvitationsTab() }],
      });
      return;
    }

    renderStatePanel(container, {
      icon: "bi-exclamation-octagon",
      iconVariant: "danger",
      title: "Gagal Memuat Undangan",
      description: err.status >= 500
        ? "Terjadi kesalahan pada server. Silakan coba beberapa saat lagi."
        : (err.message || "Terjadi kesalahan saat mengambil daftar undangan."),
      actions: [{ label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadCurrentInvitationsTab() }],
    });
  } finally {
    if (seq === invitationsPageState.requestSeq) {
      invitationsPageState.isLoading = false;
    }
  }
}

// Day 24.5: Sinkronisasi status proposal untuk setiap proposal_id unik pada undangan PENDING
// agar undangan PENDING pada proposal NOT_FORMED / CANCELLED / EXPIRED / READY_FOR_SESSION /
// SESSION_EXECUTED tidak menampilkan tombol Terima/Tolak (tetap zero backend changes).
async function syncPendingInboxProposalStatuses(inboxItems, seq) {
  const statusMap = {};
  const uniqueProposalIds = [
    ...new Set(
      inboxItems
        .filter((inv) => (inv.status || "").toUpperCase() === "PENDING" && Boolean(inv.proposal_id))
        .map((inv) => inv.proposal_id)
    ),
  ];

  if (uniqueProposalIds.length === 0) {
    return { statusMap, unauthorized: false };
  }

  const settled = await Promise.allSettled(
    uniqueProposalIds.map(async (pid) => {
      const proposal = await app.proposals.getDetail(pid);
      return { pid, proposal };
    })
  );

  if (seq !== invitationsPageState.requestSeq) {
    return { statusMap, unauthorized: false };
  }

  for (let i = 0; i < settled.length; i += 1) {
    const pid = uniqueProposalIds[i];
    const outcome = settled[i];
    if (outcome.status === "fulfilled") {
      const prop = outcome.value.proposal || {};
      const propStatus = (prop.status || "").toUpperCase();
      statusMap[pid] = {
        status: propStatus,
        sessionId: prop.session_id || null,
      };
      // Jika backend melakukan lazy-expire pada GET detail proposal, sinkronkan status undangan terbaru
      if (Array.isArray(prop.invitations)) {
        const updatedById = new Map(prop.invitations.map((pInv) => [pInv.invitation_id, pInv.status]));
        inboxItems.forEach((item) => {
          if (item.proposal_id === pid && updatedById.has(item.invitation_id)) {
            item.status = updatedById.get(item.invitation_id);
          }
        });
      }
    } else {
      const err = outcome.reason || {};
      if (err.status === 401) {
        app.handleUnauthorized();
        return { statusMap, unauthorized: true };
      }
      // Fail-closed: jika status proposal gagal diverifikasi, jangan tampilkan tombol mutasi
      statusMap[pid] = {
        status: "UNAVAILABLE",
        errorStatus: err.status || 0,
      };
    }
  }

  return { statusMap, unauthorized: false };
}

function renderInboxList() {
  const container = document.getElementById("invitationsListContainer");
  const countPill = document.getElementById("invitationsCountPill");
  if (!container) return;

  const filter = (invitationsPageState.inboxStatusFilter || "").toUpperCase();
  const filtered = filter
    ? invitationsPageState.inboxItems.filter((inv) => (inv.status || "").toUpperCase() === filter)
    : invitationsPageState.inboxItems;

  if (countPill) {
    countPill.textContent = `${filtered.length} undangan`;
  }

  if (filtered.length === 0) {
    const isFiltered = Boolean(filter);
    const label = isFiltered ? getInvitationStatusMeta(filter).label : "";
    renderStatePanel(container, {
      icon: "bi-envelope-open",
      title: isFiltered ? `Tidak Ada Undangan "${label}"` : "Belum Ada Undangan Masuk",
      description: isFiltered
        ? `Tidak ditemukan undangan masuk dengan status "${label}".`
        : "Belum ada undangan belajar yang ditujukan kepadamu saat ini.",
      actions: isFiltered
        ? [
            {
              label: "Lihat Semua Undangan",
              variantClass: "btn-la--secondary",
              onClick: () => {
                const allBtn = document.querySelector('#invitationStatusFilterBar .filter-pill-btn[data-status=""]');
                if (allBtn) allBtn.click();
              },
            },
          ]
        : [{ label: "Cari Partner & Matching", href: "matching.html", variantClass: "btn-la--primary" }],
    });
    return;
  }

  container.textContent = "";
  const fragment = document.createDocumentFragment();

  filtered.forEach((inv) => {
    const invStatus = (inv.status || "").toUpperCase();
    const statusMeta = getInvitationStatusMeta(invStatus);
    const senderName = (inv.sender && inv.sender.full_name) ? inv.sender.full_name : "Mahasiswa";
    const senderSubParts = [];
    if (inv.sender && inv.sender.study_program) senderSubParts.push(inv.sender.study_program);
    if (inv.sender && inv.sender.academic_year) senderSubParts.push(`Angkatan ${inv.sender.academic_year}`);

    const card = createEl("article", "invitation-card");
    card.dataset.invitationId = inv.invitation_id || "";

    const head = createEl("div", "invitation-card-head");
    const left = createEl("div", "");
    left.appendChild(createEl("div", "invitation-sender-name", `Dari: ${senderName}`));
    if (senderSubParts.length > 0) {
      left.appendChild(createEl("div", "invitation-sub-meta", senderSubParts.join(" · ")));
    }
    left.appendChild(createEl("div", "invitation-sub-meta", `Dikirim: ${formatDateTimeIndo(inv.created_at)}`));
    head.appendChild(left);
    head.appendChild(createEl("span", `s-badge ${statusMeta.badgeClass}`, statusMeta.label));
    card.appendChild(head);

    if (inv.message && inv.message.trim()) {
      card.appendChild(createEl("div", "invitation-message-box", inv.message.trim()));
    }

    // Evaluasi apakah undangan PENDING benar-benar masih dapat direspons berdasarkan status proposal
    const proposalMeta = inv.proposal_id ? invitationsPageState.proposalStatusById[inv.proposal_id] : null;
    const isStandalonePending = invStatus === "PENDING" && !inv.proposal_id;
    const isResponsiveProposal = Boolean(proposalMeta && _RESPONSIVE_PROPOSAL_STATUSES.has(proposalMeta.status));
    const canRespondPending = invStatus === "PENDING" && (isStandalonePending || isResponsiveProposal);

    if (invStatus === "PENDING" && inv.proposal_id && !canRespondPending) {
      const propStatusCode = proposalMeta ? proposalMeta.status : "UNAVAILABLE";
      const propMetaBadge =
        propStatusCode === "UNAVAILABLE"
          ? { label: "Status Proposal Belum Terverifikasi", badgeClass: "s-badge--neutral" }
          : getProposalStatusMeta(propStatusCode);

      const propBadgeRow = createEl("div", "badge-row");
      propBadgeRow.appendChild(createEl("span", `s-badge ${propMetaBadge.badgeClass}`, `Proposal: ${propMetaBadge.label}`));
      card.appendChild(propBadgeRow);

      const readOnlyMsg =
        propStatusCode === "UNAVAILABLE"
          ? "Status proposal terkait tidak dapat diverifikasi saat ini. Buka Lihat Proposal untuk memeriksa status terbaru."
          : `Proposal ini sudah berstatus ${propMetaBadge.label} dan tidak lagi menerima respons undangan.`;
      card.appendChild(createEl("div", "la-helper-text", readOnlyMsg));
    } else if (invStatus === "ACCEPTED") {
      card.appendChild(
        createEl(
          "div",
          "la-helper-text",
          "Keputusanmu (Diterima) sudah tercatat. Buka detail proposal untuk memantau perkembangan kuorum dan status sesi."
        )
      );
    } else if (invStatus === "REJECTED") {
      card.appendChild(createEl("div", "la-helper-text", "Undangan ini telah kamu tolak."));
    }

    const actionsRow = createEl("div", "invitation-actions-row");

    if (canRespondPending) {
      const btnAccept = createEl("button", "btn-la btn-la--success btn-la--sm");
      btnAccept.type = "button";
      btnAccept.dataset.invAction = "accept";
      btnAccept.appendChild(createIcon("bi-check-lg"));
      btnAccept.appendChild(createEl("span", "", "Terima"));
      btnAccept.addEventListener("click", () => {
        if (invitationsPageState.isRespondPending) return;
        openSharedConfirmModal({
          title: "Terima Undangan Belajar?",
          message: `Kamu akan menerima undangan kelompok belajar dari ${senderName}. Backend akan memperbarui status kuorum proposal.`,
          confirmLabel: "Ya, Terima",
          confirmVariant: "btn-la--success",
          isBusyCheck: () => invitationsPageState.isRespondPending,
          onConfirm: () => executeInvitationResponse(inv.invitation_id, "ACCEPT", "", btnAccept),
        });
      });

      const btnDecline = createEl("button", "btn-la btn-la--outline-danger btn-la--sm");
      btnDecline.type = "button";
      btnDecline.dataset.invAction = "decline";
      btnDecline.appendChild(createIcon("bi-x-lg"));
      btnDecline.appendChild(createEl("span", "", "Tolak"));
      btnDecline.addEventListener("click", () => {
        if (invitationsPageState.isRespondPending) return;
        openSharedConfirmModal({
          title: "Tolak Undangan Belajar?",
          message: `Apakah kamu yakin ingin menolak undangan dari ${senderName}? Keputusan ini tidak dapat diubah kembali.`,
          confirmLabel: "Ya, Tolak",
          confirmVariant: "btn-la--danger",
          showReasonInput: true,
          reasonPlaceholder: "Alasan penolakan (opsional), mis. Jadwal kurang sesuai...",
          isBusyCheck: () => invitationsPageState.isRespondPending,
          onConfirm: (reasonText) => executeInvitationResponse(inv.invitation_id, "DECLINE", reasonText, btnDecline),
        });
      });

      actionsRow.appendChild(btnAccept);
      actionsRow.appendChild(btnDecline);
    }

    if (inv.proposal_id) {
      const detailLink = createEl("a", "btn-detail-link");
      detailLink.href = `proposal-detail.html?id=${encodeURIComponent(inv.proposal_id)}`;
      detailLink.appendChild(createEl("span", "", "Lihat Proposal"));
      detailLink.appendChild(createIcon("bi-arrow-right"));
      actionsRow.appendChild(detailLink);
    }

    if (actionsRow.childNodes.length > 0) {
      card.appendChild(actionsRow);
    }

    fragment.appendChild(card);
  });

  container.appendChild(fragment);
}

function renderSentGroupedList() {
  const container = document.getElementById("invitationsListContainer");
  const countPill = document.getElementById("invitationsCountPill");
  if (!container) return;

  const sent = invitationsPageState.sentItems;
  if (countPill) {
    countPill.textContent = `${sent.length} terkirim`;
  }

  if (sent.length === 0) {
    renderStatePanel(container, {
      icon: "bi-send",
      title: "Belum Ada Undangan Terkirim",
      description: "Kamu belum mengirimkan undangan kelompok belajar. Jalankan Matching Preview untuk mengajukan proposal baru.",
      actions: [{ label: "Cari Partner & Matching", href: "matching.html", variantClass: "btn-la--primary" }],
    });
    return;
  }

  // Kelompokkan undangan terkirim berdasarkan proposal_id
  const groups = new Map();
  sent.forEach((inv) => {
    const key = inv.proposal_id || `standalone:${inv.invitation_id}`;
    if (!groups.has(key)) {
      groups.set(key, {
        proposalId: inv.proposal_id || null,
        createdAt: inv.created_at,
        message: inv.message || "",
        invitations: [],
      });
    }
    groups.get(key).invitations.push(inv);
  });

  container.textContent = "";
  const fragment = document.createDocumentFragment();

  // Catatan transparansi discoverability: ini adalah daftar undangan terkirim, bukan seluruh proposal host
  const infoBanner = createEl("div", "session-alert session-alert--info");
  infoBanner.appendChild(createIcon("bi-info-circle-fill"));
  infoBanner.appendChild(
    createEl(
      "span",
      "",
      "Menampilkan undangan yang telah kamu kirim dikelompokkan per proposal. Buka Detail Proposal untuk melihat status proposal & kuorum terbaru dari server."
    )
  );
  fragment.appendChild(infoBanner);

  let groupIdx = 0;
  groups.forEach((group) => {
    groupIdx += 1;
    const card = createEl("article", "invitation-card");
    if (group.proposalId) card.dataset.proposalId = group.proposalId;

    const head = createEl("div", "invitation-card-head");
    const left = createEl("div", "");
    left.appendChild(
      createEl(
        "div",
        "invitation-sender-name",
        group.proposalId ? `Undangan Proposal #${groupIdx}` : "Undangan Terkirim"
      )
    );
    left.appendChild(createEl("div", "invitation-sub-meta", `Dikirim: ${formatDateTimeIndo(group.createdAt)}`));
    head.appendChild(left);
    head.appendChild(createEl("span", "s-badge s-badge--host", `${group.invitations.length} undangan`));
    card.appendChild(head);

    // Ringkasan jumlah per status undangan (bukan tebakan status proposal)
    const counts = { PENDING: 0, ACCEPTED: 0, REJECTED: 0, WITHDRAWN: 0, EXPIRED: 0 };
    group.invitations.forEach((inv) => {
      const st = (inv.status || "").toUpperCase();
      if (st in counts) counts[st] += 1;
    });

    const summaryBadges = createEl("div", "badge-row");
    Object.entries(counts).forEach(([stKey, num]) => {
      if (num > 0) {
        const meta = getInvitationStatusMeta(stKey);
        summaryBadges.appendChild(createEl("span", `s-badge ${meta.badgeClass}`, `${meta.label}: ${num}`));
      }
    });
    card.appendChild(summaryBadges);

    if (group.message && group.message.trim()) {
      card.appendChild(createEl("div", "invitation-message-box", group.message.trim()));
    }

    // Daftar penerima (privacy-safe: nama + status undangan saja)
    const recList = createEl("div", "sent-recipients-list");
    group.invitations.forEach((inv) => {
      const recName = (inv.recipient && inv.recipient.full_name) ? inv.recipient.full_name : "Calon Anggota";
      const stMeta = getInvitationStatusMeta(inv.status);
      const row = createEl("div", "sent-recipient-row");
      row.appendChild(createEl("span", "sent-recipient-name", recName));
      row.appendChild(createEl("span", `s-badge ${stMeta.badgeClass}`, stMeta.label));
      recList.appendChild(row);
    });
    card.appendChild(recList);

    if (group.proposalId) {
      const footer = createEl("div", "invitation-actions-row");
      const link = createEl("a", "btn-detail-link");
      link.href = `proposal-detail.html?id=${encodeURIComponent(group.proposalId)}`;
      link.appendChild(createEl("span", "", "Lihat Proposal"));
      link.appendChild(createIcon("bi-arrow-right"));
      footer.appendChild(link);
      card.appendChild(footer);
    }

    fragment.appendChild(card);
  });

  container.appendChild(fragment);
}

function setInvitationActionButtonsDisabled(disabled, activeBtn) {
  document.querySelectorAll("#invitationsListContainer button[data-inv-action], #btnRefreshInvitations").forEach((btn) => {
    btn.disabled = Boolean(disabled);
    if (disabled && btn === activeBtn) {
      btn.dataset.loading = "true";
    } else if (!disabled) {
      delete btn.dataset.loading;
    }
  });
}

async function executeInvitationResponse(invitationId, decision, reason, triggerBtn) {
  if (invitationsPageState.isRespondPending) return;
  const alertBox = document.getElementById("invitationsAlertContainer");
  invitationsPageState.isRespondPending = true;
  setInvitationActionButtonsDisabled(true, triggerBtn);

  const payload = { decision };
  if (reason && reason.trim()) {
    payload.reason = reason.trim();
  }

  try {
    const updatedInv = await app.invitations.respond(invitationId, payload);
    const finalStatus = (updatedInv && updatedInv.status ? updatedInv.status : "").toUpperCase();
    const msg =
      finalStatus === "ACCEPTED"
        ? "Undangan berhasil diterima! Keputusanmu sudah tercatat; buka Lihat Proposal untuk memantau kuorum kelompok."
        : "Undangan telah ditolak dan tercatat di server.";
    renderInlineAlert(alertBox, "success", msg);
    // Ambil ulang daftar undangan dari server (jangan hitung kuorum lokal)
    await loadCurrentInvitationsTab({ preserveAlert: true });
  } catch (err) {
    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }
    if (err.status === 403) {
      renderInlineAlert(alertBox, "danger", err.message || "Kamu tidak memiliki izin untuk merespons undangan ini.");
    } else if (err.status === 400 || err.status === 409 || err.status === 422) {
      renderInlineAlert(alertBox, "warning", err.message || "Status undangan atau proposal sudah berubah.");
      await loadCurrentInvitationsTab({ preserveAlert: true });
    } else if (err.isNetworkError || err.status === 0) {
      renderInlineAlert(alertBox, "warning", "Koneksi ke server terputus. Periksa jaringanmu lalu coba lagi.");
    } else {
      renderInlineAlert(alertBox, "danger", "Terjadi kesalahan pada server saat memproses respons undangan.");
    }
  } finally {
    invitationsPageState.isRespondPending = false;
    setInvitationActionButtonsDisabled(false);
  }
}

