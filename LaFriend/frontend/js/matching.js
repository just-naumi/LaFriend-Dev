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
  const paramsSection = document.getElementById("previewParamsSection");
  const resultContainer = document.getElementById("previewResultContainer");
  const alertBox = document.getElementById("matchingAlertContainer");
  if (!container) return;

  renderInlineAlert(alertBox, "info", "");
  renderStatePanel(container, {
    icon: "spinner",
    title: "Memuat Study Intent...",
    description: "Mengambil daftar Study Intent aktif milikmu.",
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
      if (paramsSection) paramsSection.classList.add("d-none");
      if (resultContainer) {
        resultContainer.textContent = "";
        resultContainer.classList.add("d-none");
      }

      const hasNonActive = list.length > 0;
      renderStatePanel(container, {
        icon: "bi-journal-plus",
        title: hasNonActive ? "Tidak Ada Study Intent Aktif" : "Belum Ada Study Intent",
        description: hasNonActive
          ? "Seluruh Study Intent kamu saat ini tidak berstatus ACTIVE (sudah MATCHED/CANCELLED). Buat Study Intent baru untuk mencari partner belajar."
          : "Kamu belum memiliki Study Intent aktif. Buat kebutuhan belajarmu terlebih dahulu sebelum menjalankan matching.",
        actions: [
          { label: "Buat Study Intent", href: "create-intent.html", variantClass: "btn-la--primary" },
          { label: "Lihat Sesi Belajarku", href: "sessions.html", variantClass: "btn-la--secondary" },
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
    if (paramsSection) paramsSection.classList.remove("d-none");
  } catch (err) {
    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }
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
    topRow.appendChild(createEl("div", "intent-select-course", courseCode ? `${courseCode} — ${courseName}` : courseName));
    topRow.appendChild(createEl("span", `s-badge ${isSelected ? "s-badge--you" : "s-badge--confirmed"}`, isSelected ? "Dipilih" : "ACTIVE"));
    cardBtn.appendChild(topRow);

    if (intent.topics) {
      cardBtn.appendChild(createEl("div", "intent-select-topics", intent.topics));
    }

    const metaGrid = createEl("div", "session-meta-grid");
    const goalLabel = LEARNING_GOAL_LABELS[(intent.learning_goal || "").toUpperCase()] || intent.learning_goal || "-";
    const styleLabel = COLLAB_STYLE_LABELS[(intent.collaboration_style || "").toUpperCase()] || intent.collaboration_style || "-";
    const modeLabel = LEARNING_MODE_LABELS[(intent.learning_mode || "").toUpperCase()] || intent.learning_mode || "-";

    [
      { icon: "bi-bullseye", text: goalLabel },
      { icon: "bi-chat-dots", text: styleLabel },
      { icon: "bi-geo-alt", text: modeLabel },
      { icon: "bi-people", text: `${intent.min_group_size}–${intent.max_group_size} orang` },
    ].forEach((m) => {
      const chip = createEl("div", "session-meta-chip");
      chip.appendChild(createIcon(m.icon));
      chip.appendChild(createEl("span", "", m.text));
      metaGrid.appendChild(chip);
    });

    if (intent.earliest_date && intent.latest_date) {
      const dateChip = createEl("div", "session-meta-chip");
      dateChip.appendChild(createIcon("bi-calendar-range"));
      dateChip.appendChild(createEl("span", "", `${intent.earliest_date} s/d ${intent.latest_date}`));
      metaGrid.appendChild(dateChip);
    }

    const avails = Array.isArray(intent.availabilities) ? intent.availabilities : [];
    if (avails.length > 0) {
      const firstSlot = avails[0];
      const extra = avails.length > 1 ? ` (+${avails.length - 1})` : "";
      const slotChip = createEl("div", "session-meta-chip");
      slotChip.appendChild(createIcon("bi-clock"));
      slotChip.appendChild(
        createEl("span", "", `${firstSlot.day_or_date} ${firstSlot.start_time}–${firstSlot.end_time}${extra}`)
      );
      metaGrid.appendChild(slotChip);
    }

    cardBtn.appendChild(metaGrid);

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
  const statusMeta = getFormationStatusMeta(status);
  const fragment = document.createDocumentFragment();

  // --- KARTU HASIL STATUS FORMASI ---
  const summaryCard = createEl("section", "detail-section-card");
  summaryCard.setAttribute("aria-label", "Hasil Matching Preview");

  const head = createEl("div", "detail-section-header");
  const titleWrap = createEl("div", "detail-section-title");
  titleWrap.appendChild(createIcon("bi-stars"));
  titleWrap.appendChild(createEl("span", "", "3. Hasil Preview"));
  head.appendChild(titleWrap);
  head.appendChild(createEl("span", `s-badge ${statusMeta.badgeClass}`, statusMeta.label));
  summaryCard.appendChild(head);

  if (preview.course_name) {
    summaryCard.appendChild(createEl("div", "detail-course-line", preview.course_name));
  }

  // Kondisi BUKAN READY (INSUFFICIENT_MEMBERS / NO_COMPATIBLE_GROUP / fallback)
  if (status !== "READY") {
    const warnBox = createEl("div", `session-alert ${status === "INSUFFICIENT_MEMBERS" ? "session-alert--warning" : "session-alert--danger"}`);
    warnBox.appendChild(createIcon(status === "INSUFFICIENT_MEMBERS" ? "bi-people" : "bi-exclamation-circle-fill"));
    warnBox.appendChild(
      createEl(
        "span",
        "",
        preview.message || "Belum ditemukan kelompok belajar yang memenuhi seluruh kriteria kecocokan."
      )
    );
    summaryCard.appendChild(warnBox);

    const suggestionText =
      status === "INSUFFICIENT_MEMBERS"
        ? "Saran: coba turunkan Skor Minimal, kosongkan Target Grup, atau tambahkan slot ketersediaan jadwal pada Study Intent baru."
        : "Saran: coba sesuaikan Skor Minimal atau periksa kembali mode belajar (Online/Offline/Hybrid) serta jadwal ketersediaanmu.";
    summaryCard.appendChild(createEl("div", "lifecycle-status-note", suggestionText));

    if (preview.candidate_pruning_stats) {
      summaryCard.appendChild(buildPruningStatsElement(preview.candidate_pruning_stats));
    }

    fragment.appendChild(summaryCard);
    container.appendChild(fragment);
    return;
  }

  // --- KONDISI READY ---
  if (preview.message) {
    const infoBox = createEl("div", "session-alert session-alert--info");
    infoBox.appendChild(createIcon("bi-info-circle-fill"));
    infoBox.appendChild(createEl("span", "", preview.message));
    summaryCard.appendChild(infoBox);
  }

  // KPI Skor (GQ, APS, MPS) murni dari backend
  const kpiGrid = createEl("div", "score-kpi-grid");
  [
    { label: "Group Quality", sub: "GQ Score", val: formatScore(preview.group_quality_score), highlight: true },
    { label: "Avg Pair", sub: "APS", val: formatScore(preview.average_pair_score), highlight: false },
    { label: "Min Pair", sub: "MPS", val: formatScore(preview.minimum_pair_score), highlight: false },
  ].forEach((kpi) => {
    const box = createEl("div", `score-kpi-box${kpi.highlight ? " score-kpi-box--highlight" : ""}`);
    box.appendChild(createEl("div", "score-kpi-label", kpi.label));
    box.appendChild(createEl("div", "score-kpi-val", kpi.val));
    box.appendChild(createEl("div", "score-kpi-sub", kpi.sub));
    kpiGrid.appendChild(box);
  });
  summaryCard.appendChild(kpiGrid);

  summaryCard.appendChild(
    createEl(
      "div",
      "la-helper-text",
      `Ukuran kelompok hasil preview: ${preview.group_size} mahasiswa (rentang kompatibel ${preview.min_group_size_bound}–${preview.max_group_size_bound} orang).`
    )
  );
  fragment.appendChild(summaryCard);

  // --- DAFTAR ANGGOTA KANDIDAT (PRIVACY-SAFE: tanpa email, NIM, atau intent_id) ---
  const members = Array.isArray(preview.members) ? preview.members : [];
  const nameByStudentId = new Map();
  const membersCard = createEl("section", "detail-section-card");
  membersCard.setAttribute("aria-label", "Kandidat Anggota Kelompok");

  const memHeader = createEl("div", "detail-section-header");
  const memTitle = createEl("div", "detail-section-title");
  memTitle.appendChild(createIcon("bi-people-fill"));
  memTitle.appendChild(createEl("span", "", "Kandidat Anggota"));
  memHeader.appendChild(memTitle);
  memHeader.appendChild(createEl("span", "s-badge s-badge--neutral", `${members.length} mahasiswa`));
  membersCard.appendChild(memHeader);

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
    if (m.academic_year) subParts.push(`Angkatan ${m.academic_year}`);
    if (subParts.length > 0) {
      info.appendChild(createEl("div", "invitation-sub-meta", subParts.join(" · ")));
    }

    const badges = createEl("div", "badge-row");
    badges.appendChild(createEl("span", `s-badge ${isHostRole ? "s-badge--host" : "s-badge--member"}`, isHostRole ? "HOST" : "MEMBER"));
    if (m.learning_goal) {
      badges.appendChild(
        createEl("span", "s-badge s-badge--neutral", LEARNING_GOAL_LABELS[m.learning_goal.toUpperCase()] || m.learning_goal)
      );
    }
    info.appendChild(badges);

    left.appendChild(info);
    row.appendChild(left);
    memList.appendChild(row);
  });
  membersCard.appendChild(memList);
  fragment.appendChild(membersCard);

  // --- PAIRWISE BREAKDOWN ---
  const pairs = Array.isArray(preview.pairwise_scores) ? preview.pairwise_scores : [];
  if (pairs.length > 0) {
    const pairCard = createEl("section", "detail-section-card");
    pairCard.setAttribute("aria-label", "Skor Kecocokan Pasangan");
    const pairHead = createEl("div", "detail-section-header");
    const pairTitle = createEl("div", "detail-section-title");
    pairTitle.appendChild(createIcon("bi-diagram-3-fill"));
    pairTitle.appendChild(createEl("span", "", "Pairwise Compatibility"));
    pairHead.appendChild(pairTitle);
    pairHead.appendChild(createEl("span", "s-badge s-badge--neutral", `${pairs.length} pasangan`));
    pairCard.appendChild(pairHead);

    const pairList = createEl("div", "pairwise-list");
    pairs.forEach((pair) => {
      const nameA = nameByStudentId.get(pair.student_a_id) || "Anggota A";
      const nameB = nameByStudentId.get(pair.student_b_id) || "Anggota B";

      const pItem = createEl("div", "pairwise-item");
      const pTop = createEl("div", "pairwise-top");
      pTop.appendChild(createEl("div", "pairwise-names", `${nameA} ↔ ${nameB}`));
      pTop.appendChild(createEl("span", "s-badge s-badge--confirmed", `${formatScore(pair.compatibility_score)}`));
      pItem.appendChild(pTop);

      if (pair.breakdown) {
        const chipsWrap = createEl("div", "pairwise-breakdown-chips");
        [
          { key: "topic", label: "Topik" },
          { key: "goal", label: "Tujuan" },
          { key: "style", label: "Gaya" },
          { key: "date", label: "Jadwal" },
          { key: "mode", label: "Mode" },
        ].forEach((comp) => {
          const detail = pair.breakdown[comp.key];
          if (detail && detail.score !== undefined) {
            chipsWrap.appendChild(createEl("span", "pairwise-chip", `${comp.label}: ${formatScore(detail.score)}`));
          }
        });
        pItem.appendChild(chipsWrap);
      }

      if (pair.explanation) {
        pItem.appendChild(createEl("div", "pairwise-explanation", pair.explanation));
      }

      pairList.appendChild(pItem);
    });
    pairCard.appendChild(pairList);
    fragment.appendChild(pairCard);
  }

  // --- REKOMENDASI JADWAL (READ-ONLY) ---
  const schedCard = createEl("section", "detail-section-card");
  schedCard.setAttribute("aria-label", "Rekomendasi Jadwal Hasil Matching");
  const schedHead = createEl("div", "detail-section-header");
  const schedTitle = createEl("div", "detail-section-title");
  schedTitle.appendChild(createIcon("bi-calendar3"));
  schedTitle.appendChild(createEl("span", "", "Rekomendasi Jadwal"));
  schedHead.appendChild(schedTitle);
  schedHead.appendChild(createEl("span", "s-badge s-badge--neutral", "Read-Only"));
  schedCard.appendChild(schedHead);

  if (preview.selected_schedule) {
    const selBox = createEl("div", "schedule-primary-box");
    selBox.appendChild(createEl("div", "schedule-readonly-tag", "Rekomendasi Jadwal Utama Hasil Matching"));
    selBox.appendChild(
      createEl("div", "slot-item-date", formatSessionDateIndo(preview.selected_schedule.date))
    );
    selBox.appendChild(
      createEl(
        "div",
        "slot-item-time",
        `${preview.selected_schedule.start_time} – ${preview.selected_schedule.end_time} (${preview.selected_schedule.duration_minutes} menit)`
      )
    );
    schedCard.appendChild(selBox);
  }

  const opts = Array.isArray(preview.schedule_options) ? preview.schedule_options : [];
  if (opts.length > 0) {
    const optList = createEl("div", "slot-list");
    opts.forEach((opt, idx) => {
      const row = createEl("div", "slot-item-row");
      const info = createEl("div", "slot-item-info");
      info.appendChild(createEl("div", "slot-item-date", formatSessionDateIndo(opt.date)));
      info.appendChild(
        createEl("div", "slot-item-time", `${opt.start_time} – ${opt.end_time} · ${opt.duration_minutes} menit`)
      );
      row.appendChild(info);
      row.appendChild(createEl("span", "s-badge s-badge--neutral", `Opsi ${idx + 1}`));
      optList.appendChild(row);
    });
    schedCard.appendChild(optList);
  }

  schedCard.appendChild(
    createEl(
      "div",
      "la-helper-text",
      "Jadwal di atas merupakan rekomendasi hasil perhitungan backend dan belum merupakan jadwal sesi final sampai proposal disetujui dan dieksekusi."
    )
  );
  fragment.appendChild(schedCard);

  // --- CANDIDATE PRUNING STATS (OPSIONAL) ---
  if (preview.candidate_pruning_stats) {
    const statsCard = createEl("section", "detail-section-card");
    statsCard.setAttribute("aria-label", "Statistik Penyaringan Kandidat");
    const stHead = createEl("div", "detail-section-header");
    const stTitle = createEl("div", "detail-section-title");
    stTitle.appendChild(createIcon("bi-funnel-fill"));
    stTitle.appendChild(createEl("span", "", "Statistik Kandidat"));
    stHead.appendChild(stTitle);
    statsCard.appendChild(stHead);
    statsCard.appendChild(buildPruningStatsElement(preview.candidate_pruning_stats));
    fragment.appendChild(statsCard);
  }

  // --- BAGIAN D: BUAT GROUP PROPOSAL RESMI (HANYA UNTUK READY) ---
  const createCard = createEl("section", "detail-section-card");
  createCard.id = "createProposalSection";
  createCard.setAttribute("aria-label", "Ajukan Group Proposal");

  const cHead = createEl("div", "detail-section-header");
  const cTitle = createEl("div", "detail-section-title");
  cTitle.appendChild(createIcon("bi-send-check-fill"));
  cTitle.appendChild(createEl("span", "", "4. Ajukan Proposal Kelompok"));
  cHead.appendChild(cTitle);
  createCard.appendChild(cHead);

  createCard.appendChild(
    createEl(
      "div",
      "la-helper-text",
      "Preview bersifat sementara. Saat kamu menekan Buat Proposal, backend akan menghitung ulang kecocokan secara independen dan mengirimkan undangan resmi ke calon anggota."
    )
  );

  const msgField = createEl("div", "la-field");
  const msgLabel = createEl("label", "la-label", "Pesan Undangan (Opsional)");
  msgLabel.setAttribute("for", "inputProposalMessage");
  const msgInput = createEl("textarea", "la-textarea");
  msgInput.id = "inputProposalMessage";
  msgInput.placeholder = "Contoh: Yuk belajar bareng persiapan kuis minggu depan!";
  msgField.appendChild(msgLabel);
  msgField.appendChild(msgInput);
  createCard.appendChild(msgField);

  const durField = createEl("div", "la-field");
  const durLabel = createEl("label", "la-label", "Batas Waktu Respons Undangan (1–168 jam)");
  durLabel.setAttribute("for", "inputProposalDuration");
  const durInput = createEl("input", "la-input");
  durInput.id = "inputProposalDuration";
  durInput.type = "number";
  durInput.min = "1";
  durInput.max = "168";
  durInput.value = "24";
  durField.appendChild(durLabel);
  durField.appendChild(durInput);
  createCard.appendChild(durField);

  const btnCreate = createEl("button", "btn-la btn-la--success");
  btnCreate.type = "button";
  btnCreate.id = "btnCreateProposal";
  btnCreate.appendChild(createIcon("bi-send-fill"));
  btnCreate.appendChild(createEl("span", "", "Buat Proposal Kelompok"));
  btnCreate.addEventListener("click", () => handleCreateProposalClick(btnCreate));
  createCard.appendChild(btnCreate);

  fragment.appendChild(createCard);
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
