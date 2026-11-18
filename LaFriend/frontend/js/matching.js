// ==============================================================================
// matching.js - Logika Halaman Cari Partner & Matching (Day 24.1)
// ==============================================================================
// Bertanggung jawab atas:
// 1. Memuat StudyIntent milik pengguna (GET /api/v1/study-intents) & filter ACTIVE.
// 2. Menjalankan Group Formation Preview (POST /api/v1/matching/group-proposals/preview).
// 3. Menampilkan hasil preview (READY, INSUFFICIENT_MEMBERS, NO_COMPATIBLE_GROUP)
//    secara read-only (jadwal & skor murni dari backend).
// 4. Mengajukan GroupProposal resmi (POST /api/v1/group-proposals -> HTTP 201)
//    dengan hanya mengirim parameter kontrak GroupProposalCreateRequest dan memakai
//    response backend sebagai satu-satunya sumber kebenaran proposal baru.
// ==============================================================================

const matchingPageState = {
  user: null,
  activeIntents: [],
  totalIntentsCount: 0,
  selectedIntentId: "",
  lastPreviewParams: null,
  lastPreviewResponse: null,
  isPreviewLoading: false,
  isCreatePending: false,
  previewSeq: 0,
};

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("matchingPageRoot")) {
    initMatchingPage();
  }
});

function initMatchingPage() {
  const user = app.requireAuth();
  if (!user) return;
  matchingPageState.user = user;

  const userNameEl = document.getElementById("matchingUserName");
  const avatarEl = document.getElementById("matchingUserAvatar");
  if (userNameEl) userNameEl.textContent = user.full_name || "Mahasiswa";
  if (avatarEl) {
    avatarEl.textContent = ((user.full_name || "M").trim().charAt(0) || "M").toUpperCase();
  }

  const btnRefresh = document.getElementById("btnRefreshIntents");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      if (!matchingPageState.isPreviewLoading && !matchingPageState.isCreatePending) {
        loadUserActiveIntents();
      }
    });
  }

  const previewForm = document.getElementById("matchingPreviewForm");
  if (previewForm) {
    previewForm.addEventListener("submit", (e) => {
      e.preventDefault();
      runMatchingPreview();
    });
  }

  loadUserActiveIntents();
}

async function loadUserActiveIntents() {
  const container = document.getElementById("matchingIntentsContainer");
  const badge = document.getElementById("activeIntentsCountBadge");
  const previewForm = document.getElementById("matchingPreviewForm");
  const paramsSection = document.getElementById("previewParamsSection");
  const resultContainer = document.getElementById("previewResultContainer");
  const alertBox = document.getElementById("matchingAlertContainer");
  if (!container) return;

  renderInlineAlert(alertBox, "info", "");
  renderStatePanel(container, {
    icon: "spinner",
    title: "Memuat rencana belajar...",
    description: "Sebentar ya, kami sedang mengambil jadwal aktifmu.",
  });

  try {
    const allIntents = await app.studyIntents.list();
    const list = Array.isArray(allIntents) ? allIntents : [];
    const activeList = list.filter((it) => (it.status || "").toUpperCase() === "ACTIVE");

    matchingPageState.totalIntentsCount = list.length;
    matchingPageState.activeIntents = activeList;

    if (badge) {
      badge.textContent = `${activeList.length} aktif`;
    }

    if (activeList.length === 0) {
      matchingPageState.selectedIntentId = "";
      matchingPageState.lastPreviewResponse = null;
      if (previewForm) previewForm.classList.add("d-none");
      if (paramsSection) paramsSection.classList.add("d-none");
      if (resultContainer) {
        resultContainer.textContent = "";
        resultContainer.classList.add("d-none");
      }

      const hasNonActive = list.length > 0;
      renderStatePanel(container, {
        icon: "bi-journal-plus",
        title: hasNonActive ? "Belum Ada Rencana Aktif" : "Belum Ada Rencana Belajar",
        description: hasNonActive
          ? "Rencana belajarmu sebelumnya sudah selesai atau terpakai. Buat rencana baru untuk mencari teman belajar."
          : "Buat rencana belajarmu dulu agar kami bisa mencarikan teman yang cocok.",
        actions: [
          { label: "Buat Rencana Belajar", href: "create-intent.html", variantClass: "btn-la--primary" },
          { label: "Sesi Belajarku", href: "sessions.html", variantClass: "btn-la--secondary" },
        ],
      });
      return;
    }

    // Dukung pre-select ?intent_id=... HANYA jika intent tersebut milik pengguna & berstatus ACTIVE
    const urlIntentId = (new URLSearchParams(window.location.search).get("intent_id") || "").trim();
    const matchedFromUrl = urlIntentId && activeList.some((it) => it.intent_id === urlIntentId);
    const keepExisting =
      matchingPageState.selectedIntentId &&
      activeList.some((it) => it.intent_id === matchingPageState.selectedIntentId);

    if (matchedFromUrl) {
      matchingPageState.selectedIntentId = urlIntentId;
    } else if (!keepExisting) {
      matchingPageState.selectedIntentId = activeList[0].intent_id;
    }

    renderActiveIntentSelector(container, activeList);
    if (previewForm) previewForm.classList.remove("d-none");
    if (paramsSection) paramsSection.classList.remove("d-none");
  } catch (err) {
    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }
    if (previewForm) previewForm.classList.add("d-none");
    if (paramsSection) paramsSection.classList.add("d-none");
    if (err.isNetworkError || err.status === 0) {
      renderStatePanel(container, {
        icon: "bi-wifi-off",
        iconVariant: "warning",
        title: "Koneksi Bermasalah",
        description: "Tidak dapat terhubung ke server untuk memuat Study Intent.",
        actions: [{ label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadUserActiveIntents() }],
      });
      return;
    }
    renderStatePanel(container, {
      icon: "bi-exclamation-octagon",
      iconVariant: "danger",
      title: "Gagal Memuat Study Intent",
      description: err.status >= 500
        ? "Terjadi kesalahan pada server. Silakan coba beberapa saat lagi."
        : (err.message || "Gagal mengambil daftar Study Intent."),
      actions: [{ label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadUserActiveIntents() }],
    });
  }
}

function renderActiveIntentSelector(container, activeIntents) {
  container.textContent = "";
  const listWrap = createEl("div", "intent-select-list");

  activeIntents.forEach((intent) => {
    const isSelected = intent.intent_id === matchingPageState.selectedIntentId;
    const cardBtn = createEl("button", `intent-select-card${isSelected ? " selected" : ""}`);
    cardBtn.type = "button";
    cardBtn.dataset.intentId = intent.intent_id;
    cardBtn.setAttribute("aria-pressed", String(isSelected));

    const courseCode = intent.course && intent.course.course_code ? intent.course.course_code : "";
    const courseName = intent.course && intent.course.course_name ? intent.course.course_name : "Mata Kuliah";

    const topRow = createEl("div", "intent-select-top");
    topRow.appendChild(createEl("div", "intent-select-course", courseName));
    if (isSelected) {
      topRow.appendChild(createEl("span", "s-badge s-badge--you", "Dipilih"));
    }
    cardBtn.appendChild(topRow);

    if (intent.topics) {
      cardBtn.appendChild(createEl("div", "intent-select-topics", intent.topics));
    }

    const modeLabel = LEARNING_MODE_LABELS[(intent.learning_mode || "").toUpperCase()] || intent.learning_mode || "";
    const avails = Array.isArray(intent.availabilities) ? intent.availabilities : [];
    const summaryParts = [];
    if (modeLabel) summaryParts.push(modeLabel);
    summaryParts.push(`${intent.min_group_size}–${intent.max_group_size} orang`);
    if (avails.length > 0) {
      const s = avails[0];
      summaryParts.push(`${s.day_or_date} ${s.start_time}–${s.end_time}`);
    }
    cardBtn.appendChild(createEl("div", "la-helper-text", summaryParts.join(" · ")));

    cardBtn.addEventListener("click", () => {
      if (matchingPageState.isPreviewLoading || matchingPageState.isCreatePending) return;
      if (matchingPageState.selectedIntentId === intent.intent_id) return;
      matchingPageState.selectedIntentId = intent.intent_id;
      matchingPageState.lastPreviewResponse = null;
      matchingPageState.lastPreviewParams = null;
      renderActiveIntentSelector(container, activeIntents);

      const resBox = document.getElementById("previewResultContainer");
      if (resBox) {
        resBox.textContent = "";
        resBox.classList.add("d-none");
      }
      renderInlineAlert(document.getElementById("matchingAlertContainer"), "info", "");
    });

    listWrap.appendChild(cardBtn);
  });

  container.appendChild(listWrap);
}

function readPreviewParameters() {
  const minScoreRaw = (document.getElementById("inputMinScore")?.value ?? "60").trim();
  const targetSizeRaw = (document.getElementById("inputTargetGroupSize")?.value ?? "").trim();
  const maxPoolRaw = (document.getElementById("inputMaxCandidatePool")?.value ?? "20").trim();

  const minScore = Number(minScoreRaw);
  if (minScoreRaw === "" || Number.isNaN(minScore) || minScore < 0 || minScore > 100) {
    return { error: "Skor minimal (min_score) wajib berupa angka antara 0 sampai 100." };
  }

  let targetGroupSize = null;
  if (targetSizeRaw !== "") {
    const parsedTarget = Number(targetSizeRaw);
    if (!Number.isInteger(parsedTarget) || parsedTarget < 2) {
      return { error: "Target ukuran grup (target_group_size) harus bilangan bulat minimal 2 atau dikosongkan." };
    }
    targetGroupSize = parsedTarget;
  }

  const maxPool = Number(maxPoolRaw);
  if (maxPoolRaw === "" || !Number.isInteger(maxPool) || maxPool < 1 || maxPool > 100) {
    return { error: "Batas pool kandidat (max_candidate_pool) wajib berupa bilangan bulat antara 1 sampai 100." };
  }

  return {
    payload: {
      host_intent_id: matchingPageState.selectedIntentId,
      min_score: minScore,
      target_group_size: targetGroupSize,
      max_candidate_pool: maxPool,
    },
  };
}

async function runMatchingPreview() {
  if (matchingPageState.isPreviewLoading || matchingPageState.isCreatePending) return;

  const alertBox = document.getElementById("matchingAlertContainer");
  const resultContainer = document.getElementById("previewResultContainer");
  const btnPreview = document.getElementById("btnRunPreview");

  if (!matchingPageState.selectedIntentId) {
    renderInlineAlert(alertBox, "warning", "Silakan pilih salah satu Study Intent aktif terlebih dahulu.");
    return;
  }

  const { payload, error } = readPreviewParameters();
  if (error) {
    renderInlineAlert(alertBox, "danger", error);
    return;
  }

  renderInlineAlert(alertBox, "info", "");
  const seq = ++matchingPageState.previewSeq;
  matchingPageState.isPreviewLoading = true;
  if (btnPreview) {
    btnPreview.disabled = true;
    btnPreview.dataset.loading = "true";
  }

  if (resultContainer) {
    resultContainer.classList.remove("d-none");
    renderStatePanel(resultContainer, {
      icon: "spinner",
      title: "Menghitung Formasi Kelompok...",
      description: "Mesin matching backend sedang mengevaluasi kandidat dan jadwal terbaik.",
    });
  }

  try {
    const previewRes = await app.matching.preview(payload);
    if (seq !== matchingPageState.previewSeq) return;

    // Simpan hasil preview HANYA sebagai state tampilan sementara (bukan proposal resmi)
    matchingPageState.lastPreviewParams = payload;
    matchingPageState.lastPreviewResponse = previewRes;
    renderMatchingPreviewResult(resultContainer, previewRes);
    if (resultContainer && typeof resultContainer.scrollIntoView === "function") {
      resultContainer.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (err) {
    if (seq !== matchingPageState.previewSeq) return;
    matchingPageState.lastPreviewResponse = null;

    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }

    if (resultContainer) {
      resultContainer.classList.remove("d-none");
      if (err.status === 403) {
        // Jangan hapus token saat 403
        renderStatePanel(resultContainer, {
          icon: "bi-shield-lock",
          iconVariant: "danger",
          title: "Akses Ditolak",
          description: err.message || "Kamu tidak diizinkan menjalankan preview untuk Study Intent ini.",
        });
      } else if (err.status === 404) {
        renderStatePanel(resultContainer, {
          icon: "bi-search",
          iconVariant: "warning",
          title: "Study Intent Tidak Ditemukan",
          description: err.message || "Study Intent yang dipilih tidak ditemukan di server.",
          actions: [{ label: "Muat Ulang Intent", variantClass: "btn-la--primary", onClick: () => loadUserActiveIntents() }],
        });
      } else if (err.isNetworkError || err.status === 0) {
        renderStatePanel(resultContainer, {
          icon: "bi-wifi-off",
          iconVariant: "warning",
          title: "Koneksi Bermasalah",
          description: "Tidak dapat terhubung ke server saat menjalankan preview matching.",
          actions: [{ label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => runMatchingPreview() }],
        });
      } else {
        renderStatePanel(resultContainer, {
          icon: "bi-exclamation-triangle",
          iconVariant: err.status >= 500 ? "danger" : "warning",
          title: err.status >= 500 ? "Kesalahan Server" : "Preview Tidak Dapat Dijalankan",
          description: err.status >= 500
            ? "Terjadi kesalahan pada server saat menghitung preview. Silakan coba lagi."
            : (err.message || "Permintaan preview tidak dapat diproses."),
          actions: [{ label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => runMatchingPreview() }],
        });
      }
    }
  } finally {
    if (seq === matchingPageState.previewSeq) {
      matchingPageState.isPreviewLoading = false;
      if (btnPreview) {
        btnPreview.disabled = false;
        delete btnPreview.dataset.loading;
      }
    }
  }
}

function renderMatchingPreviewResult(container, preview) {
  if (!container || !preview) return;
  container.textContent = "";
  container.classList.remove("d-none");

  const status = (preview.formation_status || "").toUpperCase();
  const fragment = document.createDocumentFragment();

  // --- KONDISI BELUM KETEMU KELOMPOK (INSUFFICIENT_MEMBERS / NO_COMPATIBLE_GROUP) ---
  if (status !== "READY") {
    const emptySection = createEl("section", "detail-section-card");
    emptySection.setAttribute("aria-label", "Hasil Pencarian Teman");

    const title = status === "INSUFFICIENT_MEMBERS" ? "Belum Cukup Teman yang Cocok" : "Belum Ada Kelompok yang Cocok";
    emptySection.appendChild(createEl("div", "detail-hero-title", title));
    emptySection.appendChild(
      createEl(
        "div",
        "lifecycle-status-note",
        preview.message || "Belum ditemukan teman belajar dengan jadwal dan preferensi yang cocok."
      )
    );
    emptySection.appendChild(
      createEl(
        "div",
        "la-helper-text",
        "Coba longgarkan minimal kecocokan di Pengaturan pencarian, atau tambahkan slot waktu luang lain."
      )
    );
    fragment.appendChild(emptySection);
    container.appendChild(fragment);
    return;
  }

  // --- KONDISI READY: RINGKAS, BERSIH, MANUSIAWI ---
  const members = Array.isArray(preview.members) ? preview.members : [];
  const nameByStudentId = new Map();

  // Bagian 1: Ringkasan Hasil + Daftar Teman + Jadwal Rekomendasi (1 aliran bersih, bukan 5 card)
  const matchSection = createEl("section", "detail-section-card");
  matchSection.setAttribute("aria-label", "Rekomendasi Kelompok Belajar");

  const strip = createEl("div", "match-summary-strip");
  const stripLeft = createEl("div", "");
  stripLeft.appendChild(createEl("div", "detail-section-title", preview.course_name || "Kelompok Ditemukan"));
  stripLeft.appendChild(
    createEl("div", "match-summary-label", `${members.length} mahasiswa cocok untuk belajar bersama`)
  );
  strip.appendChild(stripLeft);
  const scoreBox = createEl("div", "");
  scoreBox.style.textAlign = "right";
  scoreBox.appendChild(createEl("div", "match-summary-score", `${Math.round(Number(preview.group_quality_score) || 0)}%`));
  scoreBox.appendChild(createEl("div", "match-summary-label", "cocok"));
  strip.appendChild(scoreBox);
  matchSection.appendChild(strip);

  // Jadwal Rekomendasi (Read-only, ringkas 1 baris)
  if (preview.selected_schedule) {
    const schedBox = createEl("div", "schedule-primary-box");
    schedBox.appendChild(createIcon("bi-calendar-event"));
    const schedInfo = createEl("div", "slot-item-info");
    schedInfo.appendChild(
      createEl(
        "div",
        "slot-item-date",
        `${formatSessionDateIndo(preview.selected_schedule.date)} · ${preview.selected_schedule.start_time}–${preview.selected_schedule.end_time}`
      )
    );
    schedInfo.appendChild(createEl("div", "slot-item-time", "Jadwal rekomendasi otomatis"));
    schedBox.appendChild(schedInfo);
    matchSection.appendChild(schedBox);
  }

  // Daftar Anggota Kandidat (Privacy-safe: tanpa email, NIM, atau ID internal)
  const memList = createEl("div", "member-list");
  members.forEach((m) => {
    const displayName = m.student_name || "Mahasiswa";
    nameByStudentId.set(m.student_id, displayName);
    const isMe = matchingPageState.user && m.student_id === matchingPageState.user.student_id;
    const isHostRole = (m.role || "").toUpperCase() === "HOST";

    const row = createEl("div", "member-item-row");
    const left = createEl("div", "member-item-left");
    left.appendChild(createEl("div", "member-avatar", displayName.trim().charAt(0).toUpperCase() || "M"));

    const info = createEl("div", "member-info");
    const nameRow = createEl("div", "member-name-row");
    nameRow.appendChild(createEl("span", "member-name", displayName));
    if (isMe) nameRow.appendChild(createEl("span", "s-badge s-badge--you", "Kamu"));
    info.appendChild(nameRow);

    const subParts = [];
    if (m.study_program) subParts.push(m.study_program);
    if (m.academic_year) subParts.push(`'${String(m.academic_year).slice(-2)}`);
    subParts.push(isHostRole ? "Host" : "Calon Anggota");
    info.appendChild(createEl("div", "invitation-sub-meta", subParts.join(" · ")));

    left.appendChild(info);
    row.appendChild(left);
    memList.appendChild(row);
  });
  matchSection.appendChild(memList);

  // Rincian Teknis (GQ/APS/MPS, Pairwise, Opsi Jadwal, Statistik) disembunyikan rapi di <details>
  const detailsEl = createEl("details", "la-disclosure");
  const summaryEl = createEl("summary", "");
  summaryEl.appendChild(createEl("span", "", "Lihat rincian kecocokan"));
  summaryEl.appendChild(createIcon("bi-chevron-down"));
  detailsEl.appendChild(summaryEl);

  const detailsBody = createEl("div", "la-disclosure-body");
  const kpiGrid = createEl("div", "score-kpi-grid");
  [
    { label: "Skor Grup", val: formatScore(preview.group_quality_score) },
    { label: "Rata-rata", val: formatScore(preview.average_pair_score) },
    { label: "Terendah", val: formatScore(preview.minimum_pair_score) },
  ].forEach((kpi) => {
    const box = createEl("div", "score-kpi-box");
    box.appendChild(createEl("div", "score-kpi-label", kpi.label));
    box.appendChild(createEl("div", "score-kpi-val", kpi.val));
    kpiGrid.appendChild(box);
  });
  detailsBody.appendChild(kpiGrid);

  const pairs = Array.isArray(preview.pairwise_scores) ? preview.pairwise_scores : [];
  if (pairs.length > 0) {
    const pairList = createEl("div", "pairwise-list");
    pairs.forEach((pair) => {
      const nameA = nameByStudentId.get(pair.student_a_id) || "Anggota A";
      const nameB = nameByStudentId.get(pair.student_b_id) || "Anggota B";
      const pItem = createEl("div", "pairwise-item");
      const pTop = createEl("div", "pairwise-top");
      pTop.appendChild(createEl("div", "pairwise-names", `${nameA} & ${nameB}`));
      pTop.appendChild(createEl("span", "s-badge s-badge--confirmed", `${formatScore(pair.compatibility_score)}`));
      pItem.appendChild(pTop);
      if (pair.explanation) {
        pItem.appendChild(createEl("div", "pairwise-explanation", pair.explanation));
      }
      pairList.appendChild(pItem);
    });
    detailsBody.appendChild(pairList);
  }

  const opts = Array.isArray(preview.schedule_options) ? preview.schedule_options : [];
  if (opts.length > 1) {
    const altLabel = createEl("div", "la-label", `Alternatif jadwal lain (${opts.length} opsi, read-only)`);
    detailsBody.appendChild(altLabel);
    opts.forEach((opt) => {
      detailsBody.appendChild(
        createEl("div", "la-helper-text", `• ${formatSessionDateIndo(opt.date)}, ${opt.start_time}–${opt.end_time}`)
      );
    });
  }

  detailsEl.appendChild(detailsBody);
  matchSection.appendChild(detailsEl);
  fragment.appendChild(matchSection);

  // Bagian 2: Ajak Belajar (Buat Proposal Kelompok)
  const createSection = createEl("section", "detail-section-card");
  createSection.id = "createProposalSection";
  createSection.setAttribute("aria-label", "Kirim Undangan Kelompok");

  createSection.appendChild(createEl("div", "detail-section-title", "Undang Mereka Belajar"));

  const msgField = createEl("div", "la-field");
  const msgLabel = createEl("label", "la-label", "Pesan ajakan (opsional)");
  msgLabel.setAttribute("for", "inputProposalMessage");
  const msgInput = createEl("textarea", "la-textarea");
  msgInput.id = "inputProposalMessage";
  msgInput.placeholder = "Misal: Yuk belajar bareng persiapan kuis!";
  msgField.appendChild(msgLabel);
  msgField.appendChild(msgInput);
  createSection.appendChild(msgField);

  const durDetails = createEl("details", "la-disclosure");
  const durSum = createEl("summary", "");
  durSum.appendChild(createEl("span", "", "Batas waktu balas undangan (default 24 jam)"));
  durSum.appendChild(createIcon("bi-chevron-down"));
  durDetails.appendChild(durSum);
  const durBody = createEl("div", "la-disclosure-body");
  const durField = createEl("div", "la-field");
  const durLabel = createEl("label", "la-label", "Durasi berlaku (1–168 jam)");
  durLabel.setAttribute("for", "inputProposalDuration");
  const durInput = createEl("input", "la-input");
  durInput.id = "inputProposalDuration";
  durInput.type = "number";
  durInput.min = "1";
  durInput.max = "168";
  durInput.value = "24";
  durField.appendChild(durLabel);
  durField.appendChild(durInput);
  durBody.appendChild(durField);
  durDetails.appendChild(durBody);
  createSection.appendChild(durDetails);

  const btnCreate = createEl("button", "btn-la btn-la--success");
  btnCreate.type = "button";
  btnCreate.id = "btnCreateProposal";
  btnCreate.appendChild(createIcon("bi-send"));
  btnCreate.appendChild(createEl("span", "", "Kirim Undangan Kelompok"));
  btnCreate.addEventListener("click", () => handleCreateProposalClick(btnCreate));
  createSection.appendChild(btnCreate);

  fragment.appendChild(createSection);
  container.appendChild(fragment);
}

function buildPruningStatsElement(stats) {
  const grid = createEl("div", "pruning-grid");
  [
    { label: "Total Diperiksa", val: stats.total_candidates_examined },
    { label: "Lolos Pool", val: stats.candidates_in_pool },
    { label: "Gugur Hard Constraints", val: stats.candidates_pruned_hard_constraints },
    { label: "Di Bawah Min Score", val: stats.candidates_pruned_min_score },
  ].forEach((row) => {
    const box = createEl("div", "pruning-item");
    box.appendChild(createEl("div", "pruning-label", row.label));
    box.appendChild(createEl("div", "pruning-value", String(row.val ?? 0)));
    grid.appendChild(box);
  });
  return grid;
}

function formatScore(val) {
  const num = Number(val);
  return Number.isFinite(num) ? num.toFixed(1) : "0.0";
}

function handleCreateProposalClick(triggerBtn) {
  if (matchingPageState.isCreatePending || matchingPageState.isPreviewLoading) return;
  const alertBox = document.getElementById("matchingAlertContainer");

  const preview = matchingPageState.lastPreviewResponse;
  const params = matchingPageState.lastPreviewParams;
  if (!preview || (preview.formation_status || "").toUpperCase() !== "READY" || !params) {
    renderInlineAlert(alertBox, "warning", "Proposal hanya dapat dibuat setelah preview berstatus READY.");
    return;
  }

  const durRaw = (document.getElementById("inputProposalDuration")?.value ?? "24").trim();
  const durHours = Number(durRaw);
  if (!Number.isInteger(durHours) || durHours < 1 || durHours > 168) {
    renderInlineAlert(alertBox, "danger", "Durasi proposal (duration_hours) wajib bilangan bulat antara 1 sampai 168 jam.");
    return;
  }

  const msgRaw = (document.getElementById("inputProposalMessage")?.value ?? "").trim();

  // Kontrak ketat GroupProposalCreateRequest: JANGAN kirim members/scores/schedule hasil preview!
  const createPayload = {
    host_intent_id: params.host_intent_id,
    min_score: params.min_score,
    target_group_size: params.target_group_size,
    max_candidate_pool: params.max_candidate_pool,
    message: msgRaw || null,
    duration_hours: durHours,
  };

  openSharedConfirmModal({
    title: "Ajukan Proposal Kelompok?",
    message: "Backend akan memvalidasi ulang kecocokan terbaru dan mengirim undangan resmi ke seluruh calon anggota. Lanjutkan?",
    confirmLabel: "Ya, Buat Proposal",
    confirmVariant: "btn-la--success",
    isBusyCheck: () => matchingPageState.isCreatePending,
    onConfirm: () => executeCreateProposal(createPayload, triggerBtn),
  });
}

async function executeCreateProposal(createPayload, triggerBtn) {
  if (matchingPageState.isCreatePending) return;
  const alertBox = document.getElementById("matchingAlertContainer");
  const btnPreview = document.getElementById("btnRunPreview");
  matchingPageState.isCreatePending = true;
  if (triggerBtn) {
    triggerBtn.disabled = true;
    triggerBtn.dataset.loading = "true";
  }
  if (btnPreview) btnPreview.disabled = true;

  let createdSuccessfully = false;
  try {
    // Sumber kebenaran proposal baru HANYA dari GroupProposalResponse HTTP 201 backend
    const createdProposal = await app.proposals.create(createPayload);
    if (!createdProposal || !createdProposal.proposal_id) {
      throw new Error("Server tidak mengembalikan proposal_id yang valid.");
    }
    createdSuccessfully = true;
    sessionStorage.setItem(
      SESSION_FLASH_KEY,
      JSON.stringify({
        variant: "success",
        message: "Proposal kelompok berhasil dibuat dan undangan telah dikirim ke calon anggota!",
      })
    );
    window.location.href = `proposal-detail.html?id=${encodeURIComponent(createdProposal.proposal_id)}`;
  } catch (err) {
    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }
    if (err.status === 403) {
      renderInlineAlert(alertBox, "danger", err.message || "Kamu tidak memiliki izin untuk membuat proposal pada intent ini.");
    } else if (err.isNetworkError || err.status === 0) {
      renderInlineAlert(alertBox, "warning", "Koneksi ke server terputus saat membuat proposal. Periksa jaringanmu lalu coba lagi.");
    } else if (err.status >= 500) {
      renderInlineAlert(alertBox, "danger", "Terjadi kesalahan pada server saat menyimpan proposal. Silakan coba lagi.");
    } else {
      // 400 / 404 / 409 / 422 -> tampilkan pesan backend dan JANGAN redirect
      renderInlineAlert(alertBox, "danger", err.message || "Gagal membuat proposal kelompok.");
    }
  } finally {
    if (!createdSuccessfully) {
      matchingPageState.isCreatePending = false;
      if (triggerBtn) {
        triggerBtn.disabled = false;
        delete triggerBtn.dataset.loading;
      }
      if (btnPreview) btnPreview.disabled = false;
    }
  }
}
