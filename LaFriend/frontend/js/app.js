// ==============================================================================
// app.js - Logika Frontend LaFriend (Interaksi dengan Backend API)
// ==============================================================================
// File ini bertugas untuk:
// 1. Menyimpan dan mengelola token login mahasiswa di localStorage browser.
// 2. Mengirim request ke Backend FastAPI (login, register, courses, study-intents).
// 3. Menangani tampilan dan aksi pengguna di setiap halaman HTML.
// ==============================================================================

// Alamat dasar (Base URL) API backend
const API_BASE_URL = "/api/v1";

// Kunci penyimpanan data di browser (localStorage)
const STORAGE_TOKEN = "lafriend_token";
const STORAGE_USER = "lafriend_user";

// Objek helper untuk komunikasi dengan API
const app = {
  // Mengambil token login yang tersimpan
  getToken() {
    return localStorage.getItem(STORAGE_TOKEN);
  },

  // Mengambil data profil mahasiswa yang tersimpan
  getUser() {
    const data = localStorage.getItem(STORAGE_USER);
    try {
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  },

  // Menyimpan token dan data user saat login berhasil
  setAuth(token, user) {
    localStorage.setItem(STORAGE_TOKEN, token);
    localStorage.setItem(STORAGE_USER, JSON.stringify(user));
  },

  // Menghapus data login saat pengguna logout
  clearAuth() {
    localStorage.removeItem(STORAGE_TOKEN);
    localStorage.removeItem(STORAGE_USER);
  },

  // Memastikan pengguna telah login; jika belum, alihkan ke halaman login
  requireAuth() {
    const token = this.getToken();
    const user = this.getUser();
    if (!token || !user) {
      window.location.replace("login.html");
      return null;
    }
    return user;
  },

  // Penanganan khusus HTTP 401 (token tidak valid / kedaluwarsa).
  // PENTING: Jangan dipanggil untuk HTTP 403 karena 403 berarti terautentikasi namun tanpa hak akses.
  handleUnauthorized() {
    this.clearAuth();
    window.location.replace("login.html");
  },

  // Mengekstrak pesan error yang aman dan mudah dibaca dari response backend FastAPI
  extractErrorMessage(responseData, status) {
    if (responseData && typeof responseData.detail === "string" && responseData.detail.trim()) {
      return responseData.detail.trim();
    }
    if (responseData && Array.isArray(responseData.detail) && responseData.detail.length > 0) {
      const msgs = responseData.detail
        .map((item) => (item && item.msg ? item.msg : ""))
        .filter(Boolean);
      if (msgs.length > 0) {
        return msgs.join("; ");
      }
    }
    return `Terjadi kesalahan status ${status}`;
  },

  // Fungsi umum untuk memanggil endpoint API backend menggunakan fetch()
  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;

    // Header default
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    // Jika pengguna sudah login, sertakan Bearer Token di header
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    let response;
    try {
      response = await fetch(url, {
        ...options,
        headers: headers,
      });
    } catch (networkErr) {
      const error = new Error("Tidak dapat terhubung ke server. Periksa koneksi internet kamu lalu coba lagi.");
      error.status = 0;
      error.data = null;
      error.endpoint = endpoint;
      error.isNetworkError = true;
      error.cause = networkErr;
      console.error(`[API Network Error] ${endpoint}:`, error);
      throw error;
    }

    const responseData = await response.json().catch(() => ({}));

    // Jika server mengembalikan status error (bukan 2xx), simpan HTTP status & payload error
    if (!response.ok) {
      const error = new Error(this.extractErrorMessage(responseData, response.status));
      error.status = response.status;
      error.data = responseData;
      error.endpoint = endpoint;
      error.isNetworkError = false;
      console.error(`[API Error ${response.status}] ${endpoint}:`, error.message);
      throw error;
    }

    return responseData;
  },

  // ============================================================================
  // DAY 23: FRONTEND INTEGRATION LAYER — STUDY SESSION & LIFECYCLE API CONTRACT
  // ============================================================================
  // Seluruh aturan bisnis (otorisasi, state transition, quorum Option A, provenance)
  // tetap dikendalikan penuh oleh backend Day 21-22.
  sessions: {
    listMySessions(statusFilter = "") {
      const cleanStatus = (statusFilter || "").trim().toUpperCase();
      const qs = cleanStatus ? `?status=${encodeURIComponent(cleanStatus)}` : "";
      return app.request(`/sessions/my-sessions${qs}`, { method: "GET" });
    },

    getDetail(sessionId) {
      return app.request(`/sessions/${encodeURIComponent(sessionId)}`, { method: "GET" });
    },

    complete(sessionId) {
      return app.request(`/sessions/${encodeURIComponent(sessionId)}/complete`, { method: "POST" });
    },

    cancel(sessionId) {
      return app.request(`/sessions/${encodeURIComponent(sessionId)}/cancel`, { method: "POST" });
    },

    // Mengembalikan SessionWithdrawResponse minimal { session_id, session_status, membership_status }
    withdraw(sessionId) {
      return app.request(`/sessions/${encodeURIComponent(sessionId)}/withdraw`, { method: "POST" });
    },

    removeMember(sessionId, studentId) {
      return app.request(
        `/sessions/${encodeURIComponent(sessionId)}/members/${encodeURIComponent(studentId)}/remove`,
        { method: "POST" }
      );
    },
  },

  // ============================================================================
  // DAY 24: FRONTEND INTEGRATION LAYER — STUDY INTENTS, MATCHING, PROPOSALS & INVITATIONS
  // ============================================================================
  // Satu-satunya pintu komunikasi halaman Day 24 dengan 11 endpoint kanonis backend.
  studyIntents: {
    list() {
      return app.request("/study-intents", { method: "GET" });
    },
  },

  courses: {
    getDetail(courseId) {
      return app.request(`/courses/${encodeURIComponent(courseId)}`, { method: "GET" });
    },
  },

  matching: {
    // GroupProposalPreviewRequest: { host_intent_id, min_score?, target_group_size?, max_candidate_pool? }
    preview(payload) {
      return app.request("/matching/group-proposals/preview", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  },

  proposals: {
    // GroupProposalCreateRequest: { host_intent_id, min_score?, target_group_size?, max_candidate_pool?, message?, duration_hours? }
    create(payload) {
      return app.request("/group-proposals", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    getDetail(proposalId) {
      return app.request(`/group-proposals/${encodeURIComponent(proposalId)}`, { method: "GET" });
    },

    finalize(proposalId) {
      return app.request(`/group-proposals/${encodeURIComponent(proposalId)}/finalize`, { method: "POST" });
    },

    cancel(proposalId, payload = null) {
      const opts = { method: "POST" };
      if (payload && typeof payload === "object") {
        opts.body = JSON.stringify(payload);
      }
      return app.request(`/group-proposals/${encodeURIComponent(proposalId)}/cancel`, opts);
    },

    // Endpoint kanonis Day 21 untuk eksekusi proposal READY_FOR_SESSION -> StudySessionResponse (HTTP 201)
    executeSession(proposalId) {
      return app.request(`/sessions/from-proposal/${encodeURIComponent(proposalId)}`, { method: "POST" });
    },
  },

  invitations: {
    getInbox(statusFilter = "") {
      const cleanStatus = (statusFilter || "").trim().toUpperCase();
      const qs = cleanStatus ? `?status=${encodeURIComponent(cleanStatus)}` : "";
      return app.request(`/invitations/inbox${qs}`, { method: "GET" });
    },

    getSent(statusFilter = "") {
      const cleanStatus = (statusFilter || "").trim().toUpperCase();
      const qs = cleanStatus ? `?status=${encodeURIComponent(cleanStatus)}` : "";
      return app.request(`/invitations/sent${qs}`, { method: "GET" });
    },

    // InvitationRespondRequest: { decision: "ACCEPT" | "DECLINE", reason? }
    respond(invitationId, payload) {
      return app.request(`/invitations/${encodeURIComponent(invitationId)}/respond`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  },
};


// ==============================================================================
// DETEKSI HALAMAN OTOMATIS SAAT DOKUMEN HTML SELESAI DIMUAT
// ==============================================================================
document.addEventListener("DOMContentLoaded", () => {
  // 1. Jika membuka halaman Index (Routing pintar)
  if (document.getElementById("indexLoadingBox")) {
    initIndexPage();
  }

  // 2. Jika membuka halaman Login
  if (document.getElementById("loginForm")) {
    initLoginPage();
  }

  // 3. Jika membuka halaman Register
  if (document.getElementById("registerForm")) {
    initRegisterPage();
  }

  // 4. Jika membuka halaman Dashboard
  if (document.getElementById("aiNeedInput") || document.getElementById("intentsListContainer")) {
    initDashboardPage();
  }

  // 5. Jika membuka halaman Create Study Intent
  if (document.getElementById("createIntentForm")) {
    initCreateIntentPage();
  }

  // 6. Jika membuka halaman Sesi Saya (Day 23.2)
  if (document.getElementById("sessionsPageRoot") && typeof initSessionsPage === "function") {
    initSessionsPage();
  }

  // 7. Jika membuka halaman Detail Sesi (Day 23.3)
  if (document.getElementById("sessionDetailPageRoot") && typeof initSessionDetailPage === "function") {
    initSessionDetailPage();
  }
});


// ==============================================================================
// 1. HALAMAN INDEX (index.html)
// ==============================================================================
function initIndexPage() {
  const token = app.getToken();
  const user = app.getUser();

  // Jika sudah login, langsung lempar ke Dashboard. Jika belum, lempar ke Login.
  if (token && user) {
    window.location.replace("dashboard.html");
  } else {
    window.location.replace("login.html");
  }
}


// ==============================================================================
// 2. HALAMAN LOGIN (login.html)
// ==============================================================================
function initLoginPage() {
  // Jika sudah ada sesi login, langsung alihkan ke dashboard
  if (app.getToken() && app.getUser()) {
    window.location.replace("dashboard.html");
    return;
  }

  const form = document.getElementById("loginForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const btn = document.getElementById("btnSubmitLogin");
    const alertBox = document.getElementById("authAlert");
    const email = document.getElementById("inputEmail").value.trim();
    const password = document.getElementById("inputPassword").value;

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Memverifikasi...`;

    try {
      // Panggil API Login
      const res = await app.request("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      // Simpan token & profil ke localStorage
      app.setAuth(res.access_token, res.student);

      // Pindah ke dashboard
      window.location.replace("dashboard.html");
    } catch (err) {
      alertBox.innerHTML = `
        <div class="alert alert-danger py-2 small mb-3">
          ${escapeHtml(err.message || "Email atau password salah.")}
        </div>
      `;
      btn.disabled = false;
      btn.innerHTML = `Masuk ke Akun`;
    }
  });
}


// ==============================================================================
// 3. HALAMAN REGISTER (register.html)
// ==============================================================================
function initRegisterPage() {
  const form = document.getElementById("registerForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const btn = document.getElementById("btnSubmitRegister");
    const alertBox = document.getElementById("authAlert");

    const payload = {
      full_name: document.getElementById("regName").value.trim(),
      student_number: document.getElementById("regNim").value.trim(),
      academic_year: parseInt(document.getElementById("regYear").value, 10),
      study_program: document.getElementById("regProdi").value,
      email: document.getElementById("regEmail").value.trim(),
      password: document.getElementById("regPassword").value,
      is_discoverable: true,
    };

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Mendaftarkan...`;

    try {
      // Panggil API Register
      const res = await app.request("/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      // Simpan token otomatis dan pindah ke dashboard
      app.setAuth(res.access_token, res.student);
      window.location.replace("dashboard.html");
    } catch (err) {
      alertBox.innerHTML = `
        <div class="alert alert-danger py-2 small mb-3">
          ${escapeHtml(err.message || "Gagal mendaftarkan akun.")}
        </div>
      `;
      btn.disabled = false;
      btn.innerHTML = `Daftarkan Akun`;
    }
  });
}


// ==============================================================================
// 4. HALAMAN DASHBOARD (dashboard.html)
// ==============================================================================
let dashboardIntents = [];
let dashboardCourses = [];

async function initDashboardPage() {
  const user = app.getUser();
  const token = app.getToken();

  // Wajib login untuk membuka dashboard
  if (!token || !user) {
    window.location.replace("login.html");
    return;
  }

  // Tampilkan nama dan inisial avatar pengguna
  const nameEl = document.getElementById("dashUserName");
  const avatarEl = document.getElementById("userAvatarText");
  if (nameEl) nameEl.innerText = user.full_name;
  if (avatarEl) avatarEl.innerText = user.full_name.charAt(0).toUpperCase();

  // Tombol Logout
  const btnLogout = document.getElementById("btnLogout");
  if (btnLogout) {
    btnLogout.addEventListener("click", () => {
      if (confirm("Apakah kamu yakin ingin keluar dari akun?")) {
        app.clearAuth();
        window.location.replace("login.html");
      }
    });
  }

  // Muat data Study Intent dan Katalog Mata Kuliah dari server
  await loadDashboardIntents();
  await loadDashboardCourses();

  // Elemen Header & Input Search
  const aiNeedInput = document.getElementById("aiNeedInput");
  const btnHeaderVoice = document.getElementById("btnHeaderVoice");
  const btnDashboardAiSubmit = document.getElementById("btnDashboardAiSubmit");

  // ==============================================================
  // SPEECH RECOGNITION (VOICE INPUT BAHASA INDONESIA PADA SEARCH BAR)
  // Jeda hening lebih panjang (4 detik) agar tidak cepat berhenti
  // ==============================================================
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isListening = false;
  let silenceTimer = null;
  const SILENCE_TIMEOUT_MS = 4000; // 4 detik jeda hening sebelum otomatis berhenti

  function resetSilenceTimer() {
    if (silenceTimer) clearTimeout(silenceTimer);
    silenceTimer = setTimeout(() => {
      if (isListening) {
        stopVoiceRecognition();
      }
    }, SILENCE_TIMEOUT_MS);
  }

  function toggleVoiceRecognition() {
    if (isListening) {
      stopVoiceRecognition();
    } else {
      startVoiceRecognition();
    }
  }

  function startVoiceRecognition() {
    if (!SpeechRecognition) {
      alert("Browser kamu belum mendukung Web Speech Recognition. Silakan gunakan Google Chrome atau Microsoft Edge untuk fitur suara.");
      return;
    }
    if (isListening) return;

    try {
      recognition = new SpeechRecognition();
      recognition.lang = "id-ID";
      recognition.interimResults = true;
      recognition.continuous = true; // Mengizinkan bicara bersambung dengan jeda hening panjang

      recognition.onstart = () => {
        isListening = true;
        if (btnHeaderVoice) btnHeaderVoice.classList.add("listening");
        if (aiNeedInput) {
          aiNeedInput.placeholder = "Mendengarkan... Silakan berbicara...";
        }
        resetSilenceTimer();
      };

      recognition.onresult = (e) => {
        let fullTranscript = "";
        for (let i = 0; i < e.results.length; i++) {
          fullTranscript += e.results[i][0].transcript + " ";
        }
        const cleanTranscript = fullTranscript.trim();
        if (cleanTranscript && aiNeedInput) {
          aiNeedInput.value = cleanTranscript;
        }
        resetSilenceTimer();
      };

      recognition.onerror = (e) => {
        console.warn("Speech error:", e.error);
        if (e.error === "not-allowed") {
          alert("Izin mikrofon belum aktif. Silakan izinkan akses mikrofon di browser.");
          stopVoiceRecognition();
        } else if (e.error === "no-speech") {
          // Abaikan kesalahan no-speech sesaat agar tidak langsung tertutup sebelum timeout
        }
      };

      recognition.onend = () => {
        // Jika recognition tertutup prematur padahal pengguna masih dalam mode rekam, pertahankan
        if (isListening) {
          try {
            recognition.start();
          } catch (e) {
            stopVoiceRecognition();
          }
        } else {
          stopVoiceRecognition();
        }
      };

      recognition.start();
    } catch (err) {
      console.error("SpeechRecognition error:", err);
      stopVoiceRecognition();
    }
  }

  function stopVoiceRecognition() {
    isListening = false;
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
    if (btnHeaderVoice) btnHeaderVoice.classList.remove("listening");
    if (aiNeedInput) {
      aiNeedInput.placeholder = "Ceritakan kebutuhan belajarmu ke AI...";
    }
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
      recognition = null;
    }
  }

  if (btnHeaderVoice) {
    btnHeaderVoice.addEventListener("click", toggleVoiceRecognition);
  }

  // ==============================================================
  // PROSES PENCARIAN & SUBMIT PROMPT KE TIMELINE + FORM INTENT
  // ==============================================================
  async function submitAiPrompt() {
    stopVoiceRecognition();
    const promptText = aiNeedInput ? aiNeedInput.value.trim() : "";
    if (!promptText) {
      window.location.href = "create-intent.html";
      return;
    }
    await runAiTimelineLoader(promptText);
  }

  if (btnDashboardAiSubmit) {
    btnDashboardAiSubmit.addEventListener("click", submitAiPrompt);
  }

  if (aiNeedInput) {
    aiNeedInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submitAiPrompt();
      }
    });

    // Tetap dukung filter intent lokal jika pengguna mengetik kata kunci singkat
    aiNeedInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      filterDashboardItems(q);
    });
  }

  // Animasi Step Timeline Loader AI (Fallback Kompatibilitas)
  async function runAiTimelineLoader(promptText) {
    const overlay = document.getElementById("aiLoadingModal");
    if (!overlay) {
      sessionStorage.setItem("lafriend_ai_prompt", promptText);
      window.location.href = "create-intent.html";
      return;
    }

    // Tampilkan overlay loading
    overlay.classList.remove("d-none");

    const delay = (ms) => new Promise(r => setTimeout(r, ms));

    function setStepState(stepNum, state) {
      const stepEl = document.getElementById(`step${stepNum}`);
      const nodeEl = document.getElementById(`node${stepNum}`);
      if (stepEl) {
        if (state === "active") {
          stepEl.className = "timeline-step active";
          if (nodeEl) {
            nodeEl.innerHTML = `<svg class="node-spinner-svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12" stroke-linecap="round"></circle></svg>`;
          }
        } else if (state === "completed") {
          stepEl.className = "timeline-step completed";
          if (nodeEl) {
            nodeEl.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
          }
        }
      }
      updateLineProgress(stepNum);
    }

    function updateLineProgress(activeStepNum) {
      const activeNode = document.getElementById(`node${activeStepNum}`);
      const container = document.querySelector(".timeline-container");
      const lineEl = document.getElementById("timelineLineProgress");
      if (activeNode && container && lineEl) {
        const containerRect = container.getBoundingClientRect();
        const nodeRect = activeNode.getBoundingClientRect();
        const heightPx = (nodeRect.top + (nodeRect.height / 2)) - containerRect.top;
        lineEl.style.height = `${Math.max(0, heightPx)}px`;
      }
    }

    // Step 1: Pesan Belajar Diterima
    setStepState(1, "active");
    await delay(380);

    // Jalankan request ekstraksi AI ke backend secara paralel di background
    let extractPromise = app.request("/study-intents/extract-ai", {
      method: "POST",
      body: JSON.stringify({ raw_text: promptText }),
    }).catch(err => {
      console.error("Gagal ekstraksi AI di background:", err);
      return null;
    });

    // Step 2: Ekstraksi Span NLP (GLiNER)
    setStepState(1, "completed");
    setStepState(2, "active");
    await delay(420);

    // Step 3: Validasi Kurikulum Telkom University
    setStepState(2, "completed");
    setStepState(3, "active");
    await delay(450);

    // Tunggu hasil ekstraksi dari backend jika belum selesai
    const extractionResult = await extractPromise;

    // Step 4: Normalisasi Waktu & Lokasi
    setStepState(3, "completed");
    setStepState(4, "active");
    await delay(380);

    // Step 5: Formulir Siap Digunakan
    setStepState(4, "completed");
    setStepState(5, "active");
    await delay(350);
    setStepState(5, "completed");
    await delay(300);

    // Simpan hasil ekstraksi ke sessionStorage agar form create-intent langsung terisi instan
    if (extractionResult) {
      sessionStorage.setItem("lafriend_ai_extraction_result", JSON.stringify(extractionResult));
    }
    sessionStorage.setItem("lafriend_ai_prompt", promptText);

    // Fade out overlay halus sebelum redirect
    overlay.style.transition = "opacity 0.22s ease";
    overlay.style.opacity = "0";
    await delay(220);

    // Alihkan mulus ke formulir create-intent
    window.location.href = "create-intent.html";
  }




  // Fungsi helper untuk quick chip suggestion
  window.quickFillPrompt = function(text) {
    if (aiNeedInput) {
      aiNeedInput.value = text;
      aiNeedInput.focus();
    }
  };

  window.quickFillAndFocus = function(text) {
    if (aiNeedInput) {
      aiNeedInput.value = text;
      aiNeedInput.focus();
      // Scroll perlahan ke atas pada mobile
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };
}

// Mengambil daftar Study Intent milik pengguna dari backend
async function loadDashboardIntents() {
  const container = document.getElementById("intentsListContainer");
  const countBadge = document.getElementById("intentsCountBadge");

  try {
    dashboardIntents = await app.request("/study-intents");
    if (countBadge) countBadge.innerText = `${dashboardIntents.length} Intent`;

    if (!container) return; // Jika halaman sedang dalam mode fokus search tanpa list container

    if (dashboardIntents.length === 0) {
      container.innerHTML = `
        <div class="text-center py-5 px-3 bg-white rounded-4 border">
          <div class="d-inline-flex p-3 rounded-circle mb-3" style="background: var(--primary-subtle); color: var(--primary);">
            <i class="bi bi-journal-plus fs-2"></i>
          </div>
          <h6 class="fw-bold text-dark mb-1">Belum Ada Study Intent</h6>
          <p class="small text-muted mb-0">Kamu belum menentukan topik belajar. Buat kebutuhan belajarmu sekarang!</p>
        </div>
      `;
      const topCard = document.getElementById("featuredTopCard");
      if (topCard) topCard.style.display = "none";
      return;
    }

    // Tampilkan intent paling baru di kartu banner header jika ada elemennya
    const latest = dashboardIntents[0];
    const topCard = document.getElementById("featuredTopCard");
    if (topCard) {
      topCard.style.display = "flex";
      const titleEl = document.getElementById("topCardTitle");
      const subEl = document.getElementById("topCardSub");
      if (titleEl) titleEl.innerText = latest.course ? latest.course.course_name : "Mata Kuliah";
      if (subEl) subEl.innerText = `${latest.topics} • Status: ${latest.status}`;
    }

    renderDashboardIntents(dashboardIntents);
  } catch (err) {
    if (container) {
      container.innerHTML = `
        <div class="alert alert-danger py-2 small">
          Gagal memuat Study Intent: ${escapeHtml(err.message)}
        </div>
      `;
    }
  }
}

// Menampilkan kartu-kartu Study Intent
function renderDashboardIntents(intents) {
  const container = document.getElementById("intentsListContainer");
  if (!container) return;

  if (intents.length === 0) {
    container.innerHTML = `<div class="text-center py-4 text-muted small">Tidak ada intent yang cocok dengan pencarian.</div>`;
    return;
  }

  container.innerHTML = intents.map(intent => {
    const isActive = intent.status === "ACTIVE";
    const courseName = intent.course ? intent.course.course_name : "Mata Kuliah";
    const courseCode = intent.course ? intent.course.course_code : "MK";

    const slotText = intent.availabilities.length > 0
      ? `${intent.availabilities[0].day_or_date} (${intent.availabilities[0].start_time}-${intent.availabilities[0].end_time})`
      : "Waktu Fleksibel";

    const extraSlots = intent.availabilities.length > 1 ? ` +${intent.availabilities.length - 1} slot lain` : "";

    return `
      <div class="item-card">
        <div class="item-card-inner">
          <div class="item-thumb-box">
            <i class="bi bi-journal-bookmark-fill"></i>
          </div>
          <div class="item-content">
            <div class="d-flex justify-content-between align-items-start mb-1">
              <h6 class="item-title mb-0">${escapeHtml(courseName)}</h6>
              <span class="badge-purple">${escapeHtml(courseCode)}</span>
            </div>
            
            <div class="small fw-semibold text-primary mb-2 text-truncate" style="max-width: 260px;">
              ${escapeHtml(intent.topics)}
            </div>

            <div class="item-meta-chips">
              <div class="item-meta-chip">
                <i class="bi bi-clock-fill"></i>
                <span>${escapeHtml(slotText)}${extraSlots}</span>
              </div>
              <div class="item-meta-chip">
                <i class="bi bi-people-fill"></i>
                <span>${intent.min_group_size}-${intent.max_group_size} Mahasiswa</span>
              </div>
            </div>

            <div class="item-progress-bar">
              <div class="item-progress-fill" style="width: ${isActive ? '80%' : '100%'}; background: ${isActive ? 'var(--primary)' : '#9CA3AF'};"></div>
            </div>

            <div class="item-footer-status">
              <span class="${isActive ? 'text-success fw-bold' : 'text-muted'}">
                <i class="bi ${isActive ? 'bi-check-circle-fill' : 'bi-x-circle'} me-1"></i>
                ${isActive ? 'Aktif Menunggu Partner' : intent.status}
              </span>
              ${isActive ? `
                <button class="btn btn-sm btn-link text-danger p-0 text-decoration-none fw-bold" onclick="cancelStudyIntent('${intent.intent_id}')" style="font-size:0.75rem;">
                  Batalkan Intent
                </button>
              ` : ''}
            </div>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// Mengambil daftar mata kuliah dari backend
async function loadDashboardCourses() {
  try {
    dashboardCourses = await app.request("/courses");
    const countBadge = document.getElementById("coursesCountBadge");
    if (countBadge) countBadge.innerText = `${dashboardCourses.length} MK`;
    renderDashboardCourses(dashboardCourses);
  } catch (err) {
    console.error("Gagal memuat mata kuliah:", err);
  }
}

// Menampilkan kartu katalog mata kuliah
function renderDashboardCourses(courses) {
  const grid = document.getElementById("coursesListGrid");
  if (!grid) return;

  grid.innerHTML = courses.map(c => `
    <div class="grid-choice-card" onclick="window.location.href='create-intent.html?course_id=${c.course_id}'">
      <div class="grid-icon-circle">
        <i class="bi bi-book-half"></i>
      </div>
      <div class="badge-purple mb-1 d-inline-block">${escapeHtml(c.course_code)}</div>
      <div class="grid-card-title text-truncate">${escapeHtml(c.course_name)}</div>
      <div class="grid-card-sub text-truncate">${escapeHtml(c.study_program)}</div>
      <div class="small fw-bold text-primary">
        + Buat Sesi &rarr;
      </div>
    </div>
  `).join("");
}

// Fungsi filter pencarian
function filterDashboardItems(query) {
  const filteredIntents = dashboardIntents.filter(i =>
    (i.topics && i.topics.toLowerCase().includes(query)) ||
    (i.course && i.course.course_name.toLowerCase().includes(query)) ||
    (i.course && i.course.course_code.toLowerCase().includes(query))
  );
  renderDashboardIntents(filteredIntents);

  const filteredCourses = dashboardCourses.filter(c =>
    c.course_name.toLowerCase().includes(query) ||
    c.course_code.toLowerCase().includes(query)
  );
  renderDashboardCourses(filteredCourses);
}

// Fungsi tab switcher (Study Intent vs Katalog MK)
function switchTab(tab) {
  const tabIntents = document.getElementById("tabIntents");
  const tabCourses = document.getElementById("tabCourses");
  const viewIntents = document.getElementById("viewIntents");
  const viewCourses = document.getElementById("viewCourses");

  if (tab === "intents") {
    tabIntents.classList.add("active");
    tabCourses.classList.remove("active");
    viewIntents.style.display = "block";
    viewCourses.style.display = "none";
  } else {
    tabCourses.classList.add("active");
    tabIntents.classList.remove("active");
    viewCourses.style.display = "block";
    viewIntents.style.display = "none";
  }
}

// Membatalkan Study Intent
async function cancelStudyIntent(intentId) {
  if (!confirm("Apakah kamu yakin ingin membatalkan Study Intent ini?")) return;
  try {
    await app.request(`/study-intents/${intentId}/cancel`, { method: "PATCH" });
    await loadDashboardIntents();
  } catch (err) {
    alert("Gagal membatalkan intent: " + err.message);
  }
}


// ==============================================================================
// 5. HALAMAN CREATE STUDY INTENT (create-intent.html)
// ==============================================================================
let slotCounter = 0;

async function initCreateIntentPage() {
  const user = app.getUser();
  const token = app.getToken();

  // Wajib login
  if (!token || !user) {
    window.location.replace("login.html");
    return;
  }

  // DAY 11.1: HILANGKAN DEFAULT PALSU PADA FORM
  // Tanggal dan slot waktu TIDAK DIISI OTOMATIS jika belum ada data riil dari pengguna/AI!
  const earliestInput = document.getElementById("earliestDate");
  const latestInput = document.getElementById("latestDate");
  if (earliestInput) earliestInput.value = "";
  if (latestInput) latestInput.value = "";

  // Muat daftar mata kuliah ke dropdown
  await loadCoursesDropdown();

  // Kosongkan container slot waktu awal (tidak ada slot palsu Rabu 09:00 / Kamis 13:00)
  const slotsContainer = document.getElementById("slotsContainer");
  const emptyNotice = document.getElementById("emptySlotsNotice");
  if (slotsContainer) slotsContainer.innerHTML = "";
  slotCounter = 0;

  // Cek apakah data sudah diekstrak dari proses loading Dashboard
  const cachedResultStr = sessionStorage.getItem("lafriend_ai_extraction_result");
  const storedPrompt = sessionStorage.getItem("lafriend_ai_prompt");

  if (cachedResultStr) {
    sessionStorage.removeItem("lafriend_ai_extraction_result");
    if (storedPrompt) sessionStorage.removeItem("lafriend_ai_prompt");
    try {
      const res = JSON.parse(cachedResultStr);
      applyAIExtractionResult(res);
    } catch (e) {
      console.error("Gagal parse cached result:", e);
    }
  } else if (storedPrompt) {
    sessionStorage.removeItem("lafriend_ai_prompt");
    extractWithTimelineAnimation(storedPrompt);
  } else {
    // Mode manual murni: beri panduan penambahan slot
    if (emptyNotice) {
      emptyNotice.innerHTML = `
        <div class="slot-warning-notice">
          <i class="bi bi-info-circle-fill me-1 text-primary"></i>
          Belum ada jadwal belajar. Silakan tentukan rentang tanggal di atas dan klik <strong>+ Tambah Slot</strong> untuk mengatur hari & jam ketersediaanmu.
        </div>
      `;
      emptyNotice.classList.remove("d-none");
    }
  }

  // Tombol tambah slot waktu
  const btnAddSlot = document.getElementById("btnAddSlot");
  if (btnAddSlot) {
    btnAddSlot.addEventListener("click", () => {
      const emptyNoticeEl = document.getElementById("emptySlotsNotice");
      if (emptyNoticeEl) emptyNoticeEl.classList.add("d-none");
      addTimeSlotRow("", "", "", Math.min(slotCounter + 1, 3));
    });
  }

  // Handle submit form
  const form = document.getElementById("createIntentForm");
  if (form) {
    form.addEventListener("submit", handleCreateIntentSubmit);
  }
}

// ==============================================================================
// LOGIKA EKSTRAKSI AI DENGAN ANIMATED STEP TIMELINE LOADER (REFERENSI LAQRIS)
// ==============================================================================
async function extractWithTimelineAnimation(rawText) {
  const formEl = document.getElementById("createIntentForm");
  const loaderEl = document.getElementById("loadingTimelineBox");

  // Jika elemen timeline ada di halaman, sembunyikan form dan jalankan transisi animasi
  if (loaderEl && formEl) {
    formEl.classList.add("d-none");
    loaderEl.classList.remove("d-none");

    const delay = (ms) => new Promise(r => setTimeout(r, ms));

    function setStepState(stepNum, state) {
      const stepEl = document.getElementById(`step${stepNum}`);
      const nodeEl = document.getElementById(`node${stepNum}`);
      if (stepEl) {
        if (state === "active") {
          stepEl.className = "timeline-step active";
          if (nodeEl) {
            nodeEl.innerHTML = `<svg class="node-spinner-svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12" stroke-linecap="round"></circle></svg>`;
          }
        } else if (state === "completed") {
          stepEl.className = "timeline-step completed";
          if (nodeEl) {
            nodeEl.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
          }
        }
      }
      updateLineProgress(stepNum);
    }

    function updateLineProgress(activeStepNum) {
      const activeNode = document.getElementById(`node${activeStepNum}`);
      const container = document.querySelector(".timeline-container");
      const lineEl = document.getElementById("timelineLineProgress");
      if (activeNode && container && lineEl) {
        const containerRect = container.getBoundingClientRect();
        const nodeRect = activeNode.getBoundingClientRect();
        const heightPx = (nodeRect.top + (nodeRect.height / 2)) - containerRect.top;
        lineEl.style.height = `${Math.max(0, heightPx)}px`;
      }
    }

    // Step 1: Pesan Belajar Diterima
    setStepState(1, "active");
    await delay(380);

    // Jalankan request ke backend AI secara paralel di background
    let extractPromise = app.request("/study-intents/extract-ai", {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText }),
    }).catch(err => {
      console.error("Gagal mengekstrak otomatis:", err);
      return null;
    });

    // Step 2: Ekstraksi Span NLP (GLiNER)
    setStepState(1, "completed");
    setStepState(2, "active");
    await delay(420);

    // Step 3: Validasi Kurikulum Tel-U
    setStepState(2, "completed");
    setStepState(3, "active");
    await delay(450);

    // Tunggu hasil ekstraksi dari backend jika belum selesai
    const res = await extractPromise;

    // Step 4: Normalisasi Waktu & Lokasi
    setStepState(3, "completed");
    setStepState(4, "active");
    await delay(380);

    // Step 5: Formulir Siap Digunakan
    setStepState(4, "completed");
    setStepState(5, "active");
    await delay(350);
    setStepState(5, "completed");
    await delay(300);

    // Terapkan hasil ekstraksi ke formulir
    if (res) {
      applyAIExtractionResult(res);
    }

    // Fade out loader dan munculkan formulir
    loaderEl.style.transition = "opacity 0.22s ease";
    loaderEl.style.opacity = "0";
    await delay(220);

    loaderEl.classList.add("d-none");
    formEl.classList.remove("d-none");
    formEl.style.opacity = "0";
    formEl.style.transition = "opacity 0.25s ease";
    requestAnimationFrame(() => {
      formEl.style.opacity = "1";
    });

    // Scroll halus ke formulir
    formEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    // Fallback jika elemen loader tidak ada
    extractAndApplyPrompt(rawText);
  }
}

async function extractAndApplyPrompt(rawText) {
  try {
    const res = await app.request("/study-intents/extract-ai", {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText }),
    });

    applyAIExtractionResult(res);
  } catch (err) {
    console.error("Gagal mengekstrak otomatis:", err);
  }
}

// ==============================================================================
// KOMPONEN AUDIT TRANSPARANSI HASIL EKSTRAKSI AI (ENAK DIBACA & USER-FRIENDLY)
// ==============================================================================
function renderAiExtractionReviewBox(res) {
  const box = document.getElementById("aiExtractionReviewBox");
  if (!box) return;

  const statuses = res.extraction_status || {};

  // Helper untuk menentukan badge tampilan yang bersahabat bagi pengguna
  function resolveStatusBadge(statusKey, hasValue, isNeedsReview = false) {
    const rawStatus = (statuses[statusKey] || (hasValue ? "EXTRACTED" : "MISSING")).toUpperCase();
    if (isNeedsReview || rawStatus === "NEEDS_REVIEW") {
      return {
        badgeClass: "needs-review",
        badgeLabel: "Cek Ulang"
      };
    }
    if (rawStatus === "EXTRACTED" && hasValue) {
      return {
        badgeClass: "extracted",
        badgeLabel: "Terisi"
      };
    }
    return {
      badgeClass: "missing",
      badgeLabel: "Belum Ada"
    };
  }

  // 1. Mata Kuliah
  const hasCourse = Boolean(res.course_id || res.course_name);
  const courseBadge = resolveStatusBadge("course", hasCourse);
  const courseDisplay = hasCourse
    ? (res.course_name ? `${escapeHtml(res.course_name)} (${escapeHtml(res.course_code || 'Tel-U')})` : escapeHtml(res.course_id))
    : `<span class="empty-val">Belum ditentukan</span>`;

  // 2. Topik
  const hasTopic = Boolean(res.topics && res.topics.trim());
  const topicBadge = resolveStatusBadge("topic", hasTopic);
  const topicDisplay = hasTopic
    ? escapeHtml(res.topics)
    : `<span class="empty-val">Belum ditentukan</span>`;

  // 3. Tujuan Belajar
  const goalMap = {
    "EXAM_PREP": "Persiapan Ujian / Latihan Soal",
    "ASSIGNMENT": "Pengerjaan Tugas / Praktikum",
    "CONCEPT": "Pemahaman Konsep & Teori",
    "UNDERSTAND": "Pemahaman Materi & Diskusi",
    "PROJECT": "Pengerjaan Proyek Belajar"
  };
  const hasGoal = Boolean(res.learning_goal);
  const goalBadge = resolveStatusBadge("learning_goal", hasGoal);
  const goalDisplay = hasGoal
    ? escapeHtml(goalMap[(res.learning_goal || "").toUpperCase()] || res.learning_goal)
    : `<span class="empty-val">Belum ditentukan</span>`;

  // 4. Mode & Lokasi
  const modeStatusKey = statuses.learning_mode ? "learning_mode" : "study_mode";
  const hasMode = Boolean(res.learning_mode || res.physical_location || res.online_platform);
  let modeParts = [];
  if (res.learning_mode === "ONLINE") modeParts.push("Daring (Online)");
  else if (res.learning_mode === "OFFLINE") modeParts.push("Tatap Muka (Offline)");
  else if (res.learning_mode === "HYBRID" || res.learning_mode === "BOTH") modeParts.push("Fleksibel (Online / Offline)");
  else if (res.learning_mode) modeParts.push(escapeHtml(String(res.learning_mode)));

  let locDetails = [];
  if (res.physical_location) locDetails.push(escapeHtml(res.physical_location));
  if (res.online_platform) locDetails.push(escapeHtml(res.online_platform));
  if (locDetails.length > 0) {
    modeParts.push(`(${locDetails.join(", ")})`);
  }
  const modeBadge = resolveStatusBadge(modeStatusKey, hasMode);
  const modeDisplay = hasMode
    ? modeParts.join(" ")
    : `<span class="empty-val">Belum ditentukan</span>`;

  // 5. Jadwal Belajar
  const schedStatus = (statuses.availability || statuses.schedule || "").toUpperCase();
  const hasSchedule = Boolean(res.availabilities && res.availabilities.length > 0);
  let isSchedReview = schedStatus === "NEEDS_REVIEW";
  let schedFormatted = "";

  if (hasSchedule) {
    schedFormatted = res.availabilities.map(s => {
      const day = escapeHtml(s.day_or_date || s.day || "Hari belum ditentukan");
      let time = "";
      if (s.start_time && s.end_time) {
        time = `${escapeHtml(s.start_time)}–${escapeHtml(s.end_time)}`;
      } else if (s.start_time) {
        time = `${escapeHtml(s.start_time)}`;
      } else {
        time = "Waktu belum spesifik";
        isSchedReview = true;
      }
      return `${day} (${time})`;
    }).join(", ");
  }

  const schedBadge = resolveStatusBadge("availability", hasSchedule, isSchedReview);
  const schedDisplay = hasSchedule
    ? schedFormatted
    : `<span class="empty-val">Belum ditentukan</span>`;

  // 6. Ukuran Kelompok
  const hasGroup = Boolean(res.min_group_size || res.max_group_size);
  const groupBadge = resolveStatusBadge("group_size", hasGroup);
  let groupDisplay = `<span class="empty-val">Belum ditentukan</span>`;
  if (hasGroup) {
    if (res.min_group_size && res.max_group_size) {
      groupDisplay = res.min_group_size === res.max_group_size
        ? `${Number(res.min_group_size)} Orang`
        : `${Number(res.min_group_size)} – ${Number(res.max_group_size)} Orang`;
    } else if (res.max_group_size) {
      groupDisplay = `Maks. ${Number(res.max_group_size)} Orang`;
    } else if (res.min_group_size) {
      groupDisplay = `Min. ${Number(res.min_group_size)} Orang`;
    }
  }

  box.innerHTML = `
    <div class="ai-review-card">
      <div class="ai-review-header">
        <div class="ai-review-title">
          <i class="bi bi-stars" style="color: #7C3AED;"></i> Ringkasan Kebutuhan Belajar
        </div>
        <p class="ai-review-sub">Informasi di bawah terisi otomatis dari pesanmu. Silakan periksa atau lengkapi bagian yang belum ada.</p>
      </div>

      <div class="ai-status-table">
        <div class="ai-status-row">
          <div class="ai-status-info">
            <div class="ai-status-label"><i class="bi bi-book me-1 text-primary"></i> Mata Kuliah</div>
            <div class="ai-status-val">${courseDisplay}</div>
          </div>
          <span class="badge-tag-status ${courseBadge.badgeClass}">${courseBadge.badgeLabel}</span>
        </div>

        <div class="ai-status-row">
          <div class="ai-status-info">
            <div class="ai-status-label"><i class="bi bi-tag me-1 text-primary"></i> Topik Belajar</div>
            <div class="ai-status-val">${topicDisplay}</div>
          </div>
          <span class="badge-tag-status ${topicBadge.badgeClass}">${topicBadge.badgeLabel}</span>
        </div>

        <div class="ai-status-row">
          <div class="ai-status-info">
            <div class="ai-status-label"><i class="bi bi-bullseye me-1 text-primary"></i> Tujuan Belajar</div>
            <div class="ai-status-val">${goalDisplay}</div>
          </div>
          <span class="badge-tag-status ${goalBadge.badgeClass}">${goalBadge.badgeLabel}</span>
        </div>

        <div class="ai-status-row">
          <div class="ai-status-info">
            <div class="ai-status-label"><i class="bi bi-geo-alt me-1 text-primary"></i> Mode & Lokasi</div>
            <div class="ai-status-val">${modeDisplay}</div>
          </div>
          <span class="badge-tag-status ${modeBadge.badgeClass}">${modeBadge.badgeLabel}</span>
        </div>

        <div class="ai-status-row">
          <div class="ai-status-info">
            <div class="ai-status-label"><i class="bi bi-calendar-event me-1 text-primary"></i> Jadwal Belajar</div>
            <div class="ai-status-val">${schedDisplay}</div>
          </div>
          <span class="badge-tag-status ${schedBadge.badgeClass}">${schedBadge.badgeLabel}</span>
        </div>

        <div class="ai-status-row">
          <div class="ai-status-info">
            <div class="ai-status-label"><i class="bi bi-people me-1 text-primary"></i> Ukuran Kelompok</div>
            <div class="ai-status-val">${groupDisplay}</div>
          </div>
          <span class="badge-tag-status ${groupBadge.badgeClass}">${groupBadge.badgeLabel}</span>
        </div>
      </div>
    </div>
  `;

  box.classList.remove("d-none");
}

// Memasukkan hasil ekstraksi AI ke dalam input form secara transparan tanpa default palsu
function applyAIExtractionResult(res) {
  // 0. Render kartu transparansi 3 status (EXTRACTED, NEEDS_REVIEW, MISSING)
  renderAiExtractionReviewBox(res);

  // 1. Isi Mata Kuliah jika terdeteksi
  if (res.course_id) {
    const selectCourse = document.getElementById("selectCourse");
    if (selectCourse) {
      selectCourse.value = res.course_id;
    }
  }

  // 2. Isi Topik Belajar
  if (res.topics) {
    const inputTopics = document.getElementById("inputTopics");
    if (inputTopics) {
      inputTopics.value = res.topics;
    }
  }

  // 3. Pilih Tujuan Belajar HANYA jika ada nilai dari hasil ekstraksi
  if (res.learning_goal) {
    const goalRadioMap = {
      "UNDERSTAND": "gUnderstand",
      "PRACTICE": "gPractice",
      "EXAM_PREP": "gExam",
      "ASSIGNMENT": "gAssignment",
      "DISCUSSION": "gDiscussion",
    };
    const radioId = goalRadioMap[res.learning_goal];
    if (radioId && document.getElementById(radioId)) {
      document.getElementById(radioId).checked = true;
    }
  }

  // 4. Pilih Gaya Kolaborasi HANYA jika ada nilai dari hasil ekstraksi
  if (res.collaboration_style) {
    const styleRadioMap = {
      "DISCUSSION": "cDiscussion",
      "PRACTICE": "cPractice",
      "TEACHING": "cTeaching",
      "FOCUS_STUDY": "cFocus",
    };
    const radioId = styleRadioMap[res.collaboration_style];
    if (radioId && document.getElementById(radioId)) {
      document.getElementById(radioId).checked = true;
    }
  }

  // 5. Pilih Mode Belajar HANYA jika ada nilai dari hasil ekstraksi
  if (res.learning_mode) {
    const modeRadioMap = {
      "OFFLINE": "mOffline",
      "ONLINE": "mOnline",
      "HYBRID": "mHybrid",
    };
    const modeKey = Array.isArray(res.learning_mode) ? "HYBRID" : res.learning_mode;
    const radioId = modeRadioMap[modeKey];
    if (radioId && document.getElementById(radioId)) {
      document.getElementById(radioId).checked = true;
    }
  }

  // 6. Ukuran Grup
  if (res.min_group_size && document.getElementById("minGroupSize")) {
    document.getElementById("minGroupSize").value = res.min_group_size;
  }
  if (res.max_group_size && document.getElementById("maxGroupSize")) {
    document.getElementById("maxGroupSize").value = res.max_group_size;
  }

  // 7. Rentang Tanggal: JANGAN ISI TANGGAL PALSU jika AI mengembalikan null!
  const earliestInput = document.getElementById("earliestDate");
  const latestInput = document.getElementById("latestDate");
  if (res.earliest_date && earliestInput) earliestInput.value = res.earliest_date;
  if (res.latest_date && latestInput) latestInput.value = res.latest_date;

  // 8. Slot Waktu Ketersediaan
  const container = document.getElementById("slotsContainer");
  const emptyNotice = document.getElementById("emptySlotsNotice");

  if (res.availabilities && res.availabilities.length > 0) {
    if (emptyNotice) emptyNotice.classList.add("d-none");
    if (container) {
      container.innerHTML = "";
      slotCounter = 0;
      res.availabilities.forEach((slot, idx) => {
        const day = slot.day_or_date || slot.day || "";
        addTimeSlotRow(day, slot.start_time || "", slot.end_time || "", slot.priority_rank || (idx + 1));
      });
    }
  } else {
    // JADWAL KOSONG: Jangan karang slot palsu! Kosongkan dan beri peringatan instruktif
    if (container) container.innerHTML = "";
    slotCounter = 0;
    if (emptyNotice) {
      emptyNotice.innerHTML = `
        <div class="slot-warning-notice">
          <i class="bi bi-exclamation-triangle-fill me-1 text-warning"></i>
          <strong>Jadwal belajar belum terdeteksi dari kalimatmu.</strong><br>
          Silakan tentukan rentang tanggal di atas dan klik <strong>+ Tambah Slot</strong> untuk mengatur hari & jam ketersediaanmu.
        </div>
      `;
      emptyNotice.classList.remove("d-none");
    }
  }

  // Gulir halus ke formulir agar mahasiswa langsung melihat hasilnya
  const formElement = document.getElementById("createIntentForm");
  if (formElement) {
    formElement.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

// Memuat daftar mata kuliah ke tag <select> (Dikelompokkan per Semester)
async function loadCoursesDropdown() {
  const select = document.getElementById("selectCourse");
  if (!select) return;

  const urlParams = new URLSearchParams(window.location.search);
  const preselectedCourseId = urlParams.get("course_id");

  try {
    const courses = await app.request("/courses");
    
    // Kelompokkan mata kuliah berdasarkan semester / program studi
    const groups = {};
    courses.forEach(c => {
      const groupKey = c.study_program || "S1 Teknik Komputer";
      if (!groups[groupKey]) groups[groupKey] = [];
      groups[groupKey].push(c);
    });

    let html = `<option value="" disabled ${!preselectedCourseId ? 'selected' : ''}>Pilih mata kuliah...</option>`;
    for (const [groupName, list] of Object.entries(groups)) {
      html += `<optgroup label="${escapeHtml(groupName)}">`;
      list.forEach(c => {
        html += `
          <option value="${c.course_id}" ${preselectedCourseId === c.course_id ? 'selected' : ''}>
            ${c.course_code} — ${c.course_name}
          </option>
        `;
      });
      html += `</optgroup>`;
    }

    select.innerHTML = html;
  } catch (err) {
    select.innerHTML = `<option value="" disabled>Gagal memuat katalog mata kuliah</option>`;
  }
}

// Menambahkan baris slot waktu ketersediaan baru (Desain Lega, Rapi & Tanpa Default Palsu)
function addTimeSlotRow(day = "", start = "", end = "", priority = 1) {
  slotCounter++;
  const rowId = `slotRow_${slotCounter}`;
  const container = document.getElementById("slotsContainer");
  if (!container) return;

  const daysList = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];
  const isCustomDay = day && !daysList.includes(day);

  const html = `
    <div class="slot-row-card" id="${rowId}">
      <!-- Header Slot: Label Slot, Prioritas & Tombol Hapus -->
      <div class="d-flex justify-content-between align-items-center mb-2 pb-2" style="border-bottom: 1px solid #F1F5F9;">
        <div class="d-flex align-items-center gap-2">
          <span class="badge" style="background: rgba(124, 58, 237, 0.1); color: #7C3AED; font-weight: 700; font-size: 0.72rem; padding: 4px 8px; border-radius: 6px;">
            Slot #${slotCounter}
          </span>
          <select class="form-select-clean slot-priority" style="width: auto; font-size: 0.76rem; padding: 4px 10px; height: auto; border-radius: 8px; font-weight: 600; color: #475569; background-color: #F8FAFC; border-color: #E2E8F0;">
            <option value="1" ${priority === 1 ? 'selected' : ''}>P1 (Prioritas Utama)</option>
            <option value="2" ${priority === 2 ? 'selected' : ''}>P2 (Cadangan)</option>
            <option value="3" ${priority === 3 ? 'selected' : ''}>P3 (Fleksibel)</option>
          </select>
        </div>
        <button type="button" class="slot-delete-btn" onclick="removeTimeSlotRow('${rowId}')" title="Hapus Slot">
          <i class="bi bi-trash3-fill"></i>
        </button>
      </div>

      <!-- Baris 1: Pilihan Hari -->
      <div class="mb-2">
        <label class="form-label-clean mb-1" style="font-size: 0.74rem; color: #64748B; font-weight: 600;">
          <i class="bi bi-calendar3 me-1 text-primary"></i> Hari Belajar
        </label>
        <select class="form-select-clean slot-day" style="font-size: 0.88rem; padding: 9px 12px; font-weight: 600; border-radius: 10px; background-color: #F8FAFC;" required>
          <option value="" disabled ${!day ? 'selected' : ''}>Pilih Hari...</option>
          ${daysList.map(d => `<option value="${d}" ${day === d ? 'selected' : ''}>${d}</option>`).join("")}
          ${isCustomDay ? `<option value="${escapeHtml(day)}" selected>${escapeHtml(day)}</option>` : ''}
        </select>
      </div>

      <!-- Baris 2: Jam Mulai & Jam Selesai (2 Kolom Lebar & Lega) -->
      <div class="row g-2">
        <div class="col-6">
          <label class="form-label-clean mb-1" style="font-size: 0.74rem; color: #64748B; font-weight: 600;">
            <i class="bi bi-clock me-1 text-primary"></i> Jam Mulai
          </label>
          <input type="time" class="slot-time-input slot-start" value="${start || ''}" required>
        </div>
        <div class="col-6">
          <label class="form-label-clean mb-1" style="font-size: 0.74rem; color: #64748B; font-weight: 600;">
            <i class="bi bi-clock-history me-1 text-primary"></i> Jam Selesai
          </label>
          <input type="time" class="slot-time-input slot-end" value="${end || ''}" required>
        </div>
      </div>
    </div>
  `;

  container.insertAdjacentHTML("beforeend", html);
}

// Menghapus baris slot waktu
function removeTimeSlotRow(rowId) {
  const el = document.getElementById(rowId);
  if (el) el.remove();
  const remainingRows = document.querySelectorAll(".slot-row-card");
  if (remainingRows.length === 0) {
    const emptyNoticeEl = document.getElementById("emptySlotsNotice");
    if (emptyNoticeEl) {
      emptyNoticeEl.innerHTML = `
        <div class="slot-warning-notice">
          <i class="bi bi-exclamation-triangle-fill me-1 text-warning"></i>
          <strong>Belum ada slot waktu belajar yang ditambahkan.</strong><br>
          Silakan klik <strong>+ Tambah Slot</strong> untuk mengatur hari & jam ketersediaanmu.
        </div>
      `;
      emptyNoticeEl.classList.remove("d-none");
    }
  }
}

// Menangani pengiriman form Create Study Intent (DAY 11.1 - Validasi Ketat Tanpa Default Palsu)
async function handleCreateIntentSubmit(e) {
  e.preventDefault();
  const alertBox = document.getElementById("formAlert");
  const btn = document.getElementById("btnSubmitIntent");

  const courseId = document.getElementById("selectCourse").value;
  if (!courseId) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan pilih mata kuliah terlebih dahulu!</div>`;
    return;
  }

  const topicsVal = (document.getElementById("inputTopics").value || "").trim();
  if (!topicsVal) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan isi topik materi belajar yang ingin dipelajari!</div>`;
    return;
  }

  // Validasi: Wajib memilih tujuan belajar (tidak ada silent default!)
  const goalChecked = document.querySelector('input[name="learningGoal"]:checked');
  if (!goalChecked) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan pilih <b>Tujuan Belajar (Learning Goal)</b> pada Bagian 3!</div>`;
    return;
  }

  // Validasi: Wajib memilih gaya kolaborasi (tidak ada silent default!)
  const styleChecked = document.querySelector('input[name="collabStyle"]:checked');
  if (!styleChecked) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan pilih <b>Gaya Belajar (Collaboration Style)</b> pada Bagian 4!</div>`;
    return;
  }

  // Validasi: Wajib memilih mode belajar (tidak ada silent default!)
  const modeChecked = document.querySelector('input[name="learningMode"]:checked');
  if (!modeChecked) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan pilih <b>Mode Belajar</b> (Offline, Online, atau Hybrid) pada Bagian 5!</div>`;
    return;
  }

  // Validasi: Wajib menentukan rentang tanggal riil dan tanggal awal <= tanggal akhir
  const earliestVal = (document.getElementById("earliestDate").value || "").trim();
  const latestVal = (document.getElementById("latestDate").value || "").trim();
  if (!earliestVal || !latestVal) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan tentukan <b>Rentang Tanggal Belajar</b> (Mulai Dari & Sampai) pada Bagian 6!</div>`;
    return;
  }
  if (earliestVal > latestVal) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Tanggal awal (${earliestVal}) tidak boleh melewati tanggal akhir (${latestVal})!</div>`;
    return;
  }

  // Kumpulkan data ketersediaan waktu dari form & validasi setiap baris slot
  const slotCards = document.querySelectorAll(".slot-row-card");
  if (slotCards.length === 0) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Minimal harus ada <b>1 Slot Waktu Ketersediaan</b>! Klik tombol <b>+ Tambah Slot</b> pada Bagian 7.</div>`;
    return;
  }

  const availabilities = [];
  for (let i = 0; i < slotCards.length; i++) {
    const c = slotCards[i];
    const day = (c.querySelector(".slot-day")?.value || "").trim();
    const start = (c.querySelector(".slot-start")?.value || "").trim();
    const end = (c.querySelector(".slot-end")?.value || "").trim();
    const prio = parseInt(c.querySelector(".slot-priority")?.value, 10) || 1;

    if (!day) {
      if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan pilih hari untuk <b>Slot #${i + 1}</b>!</div>`;
      return;
    }
    if (!start || !end) {
      if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan lengkapi jam mulai dan selesai untuk <b>Slot #${i + 1}</b>!</div>`;
      return;
    }
    if (start >= end) {
      if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Jam selesai (${end}) harus lebih besar daripada jam mulai (${start}) pada <b>Slot #${i + 1}</b>!</div>`;
      return;
    }
    availabilities.push({
      day_or_date: day,
      start_time: start,
      end_time: end,
      priority_rank: prio
    });
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Menyimpan ke SQLite...`;

  // Bungkus data payload murni dari pilihan pengguna
  const payload = {
    course_id: courseId,
    topics: topicsVal,
    learning_goal: goalChecked.value,
    collaboration_style: styleChecked.value,
    learning_mode: modeChecked.value,
    earliest_date: earliestVal,
    latest_date: latestVal,
    min_group_size: parseInt(document.getElementById("minGroupSize").value, 10),
    max_group_size: parseInt(document.getElementById("maxGroupSize").value, 10),
    availabilities: availabilities,
  };

  try {
    // Kirim data ke API backend
    await app.request("/study-intents", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (alertBox) {
      alertBox.innerHTML = `
        <div class="alert alert-success py-2 small mb-3">
          <i class="bi bi-check-circle-fill me-1"></i> Study Intent berhasil disimpan! Mengalihkan ke dashboard...
        </div>
      `;
    }

    // Alihkan kembali ke dashboard
    setTimeout(() => {
      window.location.replace("dashboard.html");
    }, 800);
  } catch (err) {
    if (alertBox) {
      alertBox.innerHTML = `
        <div class="alert alert-danger py-2 small mb-3">
          Gagal: ${escapeHtml(err.message)}
        </div>
      `;
    }
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-check-circle-fill"></i> Simpan & Buat Study Intent`;
  }
}


// ==============================================================================
// FUNGSI PENCEGAHAN XSS (SANITASI TEKS)
// ==============================================================================
function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[tag] || tag));
}


// ==============================================================================
// 6. DAY 23 — STUDY SESSION LIST & DETAIL PRESENTATION LAYER
// ==============================================================================
const SESSION_FLASH_KEY = "lafriend_session_flash";

const SESSION_STATUS_META = {
  CONFIRMED: { label: "Terkonfirmasi", badgeClass: "s-badge--confirmed" },
  COMPLETED: { label: "Selesai", badgeClass: "s-badge--completed" },
  CANCELLED: { label: "Dibatalkan", badgeClass: "s-badge--cancelled" },
  EXPIRED: { label: "Kedaluwarsa", badgeClass: "s-badge--expired" },
  DRAFT: { label: "Draf", badgeClass: "s-badge--neutral" },
  OPEN: { label: "Terbuka", badgeClass: "s-badge--pending" },
  CONFIRMATION_PENDING: { label: "Menunggu Konfirmasi", badgeClass: "s-badge--pending" },
};

const SLOT_STATUS_META = {
  PROPOSED: { label: "Menunggu persetujuan", badgeClass: "s-badge--pending" },
  APPROVED: { label: "Disetujui", badgeClass: "s-badge--confirmed" },
  REJECTED: { label: "Ditolak", badgeClass: "s-badge--cancelled" },
  SUPERSEDED: { label: "Digantikan", badgeClass: "s-badge--neutral" },
};

const MEMBERSHIP_STATUS_META = {
  INVITED: { label: "Diundang", badgeClass: "s-badge--pending" },
  ACCEPTED: { label: "Menerima undangan", badgeClass: "s-badge--member" },
  CONFIRMED: { label: "Aktif", badgeClass: "s-badge--confirmed" },
  DECLINED: { label: "Menolak", badgeClass: "s-badge--neutral" },
  WITHDRAWN: { label: "Mengundurkan diri", badgeClass: "s-badge--cancelled" },
  REMOVED: { label: "Dikeluarkan", badgeClass: "s-badge--cancelled" },
};

const LEARNING_GOAL_LABELS = {
  UNDERSTAND: "Pemahaman Materi",
  PRACTICE: "Latihan Soal",
  EXAM_PREP: "Persiapan Ujian",
  ASSIGNMENT: "Pengerjaan Tugas",
  DISCUSSION: "Diskusi",
  KNOWLEDGE_SHARING: "Berbagi Ilmu",
};

const COLLAB_STYLE_LABELS = {
  DISCUSSION: "Diskusi Aktif",
  PRACTICE: "Latihan Bersama",
  TEACHING: "Saling Mengajar",
  FOCUS_STUDY: "Fokus Mandiri Bersama",
};

const LEARNING_MODE_LABELS = {
  ONLINE: "Online",
  OFFLINE: "Offline",
  HYBRID: "Hybrid",
};

// Day 24: Dua State Machine Terpisah — ProposalStatus (7 nilai) & InvitationStatus (5 nilai)
const PROPOSAL_STATUS_META = {
  PENDING_RESPONSES: { label: "Menunggu Respons", badgeClass: "s-badge--pending" },
  QUORUM_REACHED: { label: "Kuorum Tercapai", badgeClass: "s-badge--confirmed" },
  READY_FOR_SESSION: { label: "Siap Dieksekusi", badgeClass: "s-badge--host" },
  SESSION_EXECUTED: { label: "Sesi Terbentuk", badgeClass: "s-badge--completed" },
  NOT_FORMED: { label: "Tidak Terbentuk", badgeClass: "s-badge--cancelled" },
  CANCELLED: { label: "Dibatalkan", badgeClass: "s-badge--cancelled" },
  EXPIRED: { label: "Kedaluwarsa", badgeClass: "s-badge--expired" },
};

const INVITATION_STATUS_META = {
  PENDING: { label: "Menunggu", badgeClass: "s-badge--pending" },
  ACCEPTED: { label: "Diterima", badgeClass: "s-badge--confirmed" },
  REJECTED: { label: "Ditolak", badgeClass: "s-badge--cancelled" },
  WITHDRAWN: { label: "Ditarik", badgeClass: "s-badge--neutral" },
  EXPIRED: { label: "Kedaluwarsa", badgeClass: "s-badge--expired" },
};

const FORMATION_STATUS_META = {
  READY: { label: "Kelompok Siap Dibentuk", badgeClass: "s-badge--confirmed" },
  INSUFFICIENT_MEMBERS: { label: "Kandidat Belum Mencukupi", badgeClass: "s-badge--pending" },
  NO_COMPATIBLE_GROUP: { label: "Belum Ada Kelompok Kompatibel", badgeClass: "s-badge--cancelled" },
};

function getProposalStatusMeta(statusCode) {
  const key = (statusCode || "").toUpperCase();
  return PROPOSAL_STATUS_META[key] || { label: key || "Tidak Diketahui", badgeClass: "s-badge--neutral" };
}

function getInvitationStatusMeta(statusCode) {
  const key = (statusCode || "").toUpperCase();
  return INVITATION_STATUS_META[key] || { label: key || "Tidak Diketahui", badgeClass: "s-badge--neutral" };
}

function getFormationStatusMeta(statusCode) {
  const key = (statusCode || "").toUpperCase();
  return FORMATION_STATUS_META[key] || { label: key || "Tidak Diketahui", badgeClass: "s-badge--neutral" };
}

function formatDateTimeIndo(isoStr) {
  if (!isoStr || typeof isoStr !== "string") return "-";
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return isoStr;
  const day = d.getDate();
  const month = ID_MONTHS[d.getMonth()] || "";
  const year = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${day} ${month} ${year}, ${hh}:${mm}`;
}

function openSharedConfirmModal({
  title,
  message,
  confirmLabel,
  confirmVariant,
  showReasonInput = false,
  reasonPlaceholder = "Alasan (opsional)...",
  isBusyCheck = () => false,
  onConfirm,
}) {
  const modal = document.getElementById("confirmActionModal");
  const titleEl = document.getElementById("confirmModalTitle");
  const msgEl = document.getElementById("confirmModalMessage");
  const reasonWrap = document.getElementById("confirmModalReasonWrap");
  const reasonInput = document.getElementById("confirmModalReasonInput");
  const btnCancel = document.getElementById("btnConfirmCancel");
  const btnProceed = document.getElementById("btnConfirmProceed");

  if (!modal || !titleEl || !msgEl || !btnCancel || !btnProceed) {
    if (window.confirm(message)) {
      onConfirm("");
    }
    return;
  }

  titleEl.textContent = title || "Konfirmasi Tindakan";
  msgEl.textContent = message || "";
  if (reasonWrap && reasonInput) {
    reasonInput.value = "";
    reasonInput.placeholder = reasonPlaceholder;
    reasonWrap.classList.toggle("d-none", !showReasonInput);
  }
  btnProceed.className = `btn-la ${confirmVariant || "btn-la--primary"} btn-la--sm`;
  btnProceed.textContent = confirmLabel || "Lanjutkan";
  btnProceed.disabled = false;
  btnCancel.disabled = false;
  modal.classList.remove("d-none");

  let modalSubmitting = false;

  function cleanup() {
    modal.classList.add("d-none");
    btnCancel.removeEventListener("click", handleCancel);
    btnProceed.removeEventListener("click", handleProceed);
    modal.removeEventListener("click", handleBackdrop);
    document.removeEventListener("keydown", handleEsc);
  }

  function handleCancel() {
    if (modalSubmitting || isBusyCheck()) return;
    cleanup();
  }

  function handleBackdrop(e) {
    if (e.target === modal && !modalSubmitting && !isBusyCheck()) {
      cleanup();
    }
  }

  function handleEsc(e) {
    if (e.key === "Escape" && !modalSubmitting && !isBusyCheck()) {
      cleanup();
    }
  }

  async function handleProceed() {
    if (modalSubmitting || isBusyCheck()) return;
    modalSubmitting = true;
    const reasonText = showReasonInput && reasonInput ? reasonInput.value.trim() : "";
    btnCancel.disabled = true;
    btnProceed.disabled = true;
    btnProceed.dataset.loading = "true";
    btnProceed.textContent = "";
    btnProceed.appendChild(createEl("span", "la-spinner la-spinner--sm"));
    btnProceed.appendChild(createEl("span", "", "Memproses..."));

    try {
      await onConfirm(reasonText);
    } finally {
      modalSubmitting = false;
      delete btnProceed.dataset.loading;
      cleanup();
    }
  }

  btnCancel.addEventListener("click", handleCancel);
  btnProceed.addEventListener("click", handleProceed);
  modal.addEventListener("click", handleBackdrop);
  document.addEventListener("keydown", handleEsc);
}

const ID_MONTHS = [
  "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember",
];

// Helper pembuat elemen DOM aman (seluruh teks database melalui textContent)
function createEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = String(text);
  return el;
}

function createIcon(iconClass) {
  const i = document.createElement("i");
  i.className = `bi ${iconClass}`;
  i.setAttribute("aria-hidden", "true");
  return i;
}

function getSessionStatusMeta(statusCode) {
  const key = (statusCode || "").toUpperCase();
  return SESSION_STATUS_META[key] || { label: key || "Tidak Diketahui", badgeClass: "s-badge--neutral" };
}

function getSlotStatusMeta(statusCode) {
  const key = (statusCode || "").toUpperCase();
  return SLOT_STATUS_META[key] || { label: key || "Tidak Diketahui", badgeClass: "s-badge--neutral" };
}

function getMembershipStatusMeta(statusCode) {
  const key = (statusCode || "").toUpperCase();
  return MEMBERSHIP_STATUS_META[key] || { label: key || "Tidak Diketahui", badgeClass: "s-badge--neutral" };
}

function formatSessionDateIndo(dateStr) {
  if (!dateStr || typeof dateStr !== "string") return "Jadwal belum ditentukan";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr.trim());
  if (!m) return dateStr;
  const year = parseInt(m[1], 10);
  const monthIdx = parseInt(m[2], 10) - 1;
  const day = parseInt(m[3], 10);
  if (monthIdx < 0 || monthIdx > 11) return dateStr;
  return `${day} ${ID_MONTHS[monthIdx]} ${year}`;
}

function getPrimarySlot(slots) {
  if (!Array.isArray(slots) || slots.length === 0) return null;
  const approved = slots.find((s) => (s.status || "").toUpperCase() === "APPROVED");
  return approved || slots[0];
}

function countActiveMembers(members) {
  if (!Array.isArray(members)) return 0;
  return members.filter((m) => {
    const st = (m.status || "").toUpperCase();
    return st === "CONFIRMED" || st === "ACCEPTED";
  }).length;
}

function countConfirmedMembers(members) {
  if (!Array.isArray(members)) return 0;
  return members.filter((m) => (m.status || "").toUpperCase() === "CONFIRMED").length;
}

function renderInlineAlert(container, variant, message) {
  if (!container) return;
  container.textContent = "";
  if (!message) {
    container.classList.add("d-none");
    return;
  }
  const iconMap = {
    success: "bi-check-circle-fill",
    warning: "bi-exclamation-triangle-fill",
    danger: "bi-x-circle-fill",
    info: "bi-info-circle-fill",
  };
  const box = createEl("div", `session-alert session-alert--${variant || "info"}`);
  box.appendChild(createIcon(iconMap[variant] || "bi-info-circle-fill"));
  box.appendChild(createEl("span", "", message));
  container.appendChild(box);
  container.classList.remove("d-none");
}

function renderStatePanel(container, { icon, iconVariant, title, description, actions = [] }) {
  container.textContent = "";
  const card = createEl("div", "state-card");

  if (icon === "spinner") {
    card.appendChild(createEl("div", "la-spinner"));
  } else {
    const circle = createEl(
      "div",
      `state-icon-circle${iconVariant ? ` state-icon-circle--${iconVariant}` : ""}`
    );
    circle.appendChild(createIcon(icon || "bi-info-circle"));
    card.appendChild(circle);
  }

  card.appendChild(createEl("div", "state-title", title));
  if (description) {
    card.appendChild(createEl("p", "state-desc", description));
  }

  if (actions.length > 0) {
    const actionsWrap = createEl("div", "state-actions");
    actions.forEach((act) => {
      if (act.href) {
        const link = createEl("a", `btn-la ${act.variantClass || "btn-la--primary"} btn-la--sm`, act.label);
        link.href = act.href;
        actionsWrap.appendChild(link);
      } else {
        const btn = createEl("button", `btn-la ${act.variantClass || "btn-la--primary"} btn-la--sm`, act.label);
        btn.type = "button";
        if (typeof act.onClick === "function") {
          btn.addEventListener("click", act.onClick);
        }
        actionsWrap.appendChild(btn);
      }
    });
    card.appendChild(actionsWrap);
  }

  container.appendChild(card);
}


// ==============================================================================
// 6A. HALAMAN DAFTAR SESI SAYA (sessions.html — Day 23.2)
// ==============================================================================
const sessionsPageState = {
  activeStatus: "",
  isLoading: false,
  requestSeq: 0,
};

function initSessionsPage() {
  const user = app.requireAuth();
  if (!user) return;

  const userNameEl = document.getElementById("sessionsUserName");
  const avatarEl = document.getElementById("sessionsUserAvatar");
  if (userNameEl) userNameEl.textContent = user.full_name || "Mahasiswa";
  if (avatarEl) {
    const initial = (user.full_name || "M").trim().charAt(0).toUpperCase() || "M";
    avatarEl.textContent = initial;
  }

  // Tampilkan flash message bila baru kembali dari aksi withdraw
  const flashContainer = document.getElementById("sessionsFlashContainer");
  const flashRaw = sessionStorage.getItem(SESSION_FLASH_KEY);
  if (flashRaw) {
    sessionStorage.removeItem(SESSION_FLASH_KEY);
    try {
      const parsed = JSON.parse(flashRaw);
      renderInlineAlert(flashContainer, parsed.variant || "success", parsed.message || "");
    } catch {
      renderInlineAlert(flashContainer, "success", flashRaw);
    }
  }

  // Bind status filter pills
  const filterBar = document.getElementById("sessionStatusFilterBar");
  if (filterBar) {
    filterBar.addEventListener("click", (e) => {
      const btn = e.target.closest(".filter-pill-btn");
      if (!btn) return;
      const newStatus = btn.dataset.status || "";
      if (newStatus === sessionsPageState.activeStatus && !sessionsPageState.isLoading) {
        return;
      }
      sessionsPageState.activeStatus = newStatus;
      filterBar.querySelectorAll(".filter-pill-btn").forEach((pill) => {
        pill.classList.toggle("active", pill === btn);
      });
      loadMySessionsList(user);
    });
  }

  // Tombol segarkan
  const btnRefresh = document.getElementById("btnRefreshSessions");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => loadMySessionsList(user));
  }

  loadMySessionsList(user);
}

async function loadMySessionsList(user) {
  const container = document.getElementById("sessionsListContainer");
  const countPill = document.getElementById("sessionsCountPill");
  if (!container) return;

  const seq = ++sessionsPageState.requestSeq;
  sessionsPageState.isLoading = true;

  renderStatePanel(container, {
    icon: "spinner",
    title: "Memuat Sesi Belajar...",
    description: "Mengambil daftar sesi terbarumu dari server.",
  });

  try {
    const sessions = await app.sessions.listMySessions(sessionsPageState.activeStatus);
    if (seq !== sessionsPageState.requestSeq) return; // Abaikan response usang

    const list = Array.isArray(sessions) ? sessions : [];
    if (countPill) {
      countPill.textContent = `${list.length} sesi`;
    }

    if (list.length === 0) {
      const isFiltered = Boolean(sessionsPageState.activeStatus);
      const statusLabel = isFiltered ? getSessionStatusMeta(sessionsPageState.activeStatus).label : "";
      renderStatePanel(container, {
        icon: "bi-calendar2-x",
        title: isFiltered ? `Belum Ada Sesi ${statusLabel}` : "Belum Ada Sesi Belajar",
        description: isFiltered
          ? `Tidak ditemukan sesi belajar dengan status "${statusLabel}". Coba lihat filter lain atau buat Study Intent baru.`
          : "Kamu belum tergabung dalam sesi belajar aktif maupun riwayat sesi. Buat Study Intent sekarang untuk mulai berkolaborasi!",
        actions: isFiltered
          ? [
              {
                label: "Lihat Semua Sesi",
                variantClass: "btn-la--secondary",
                onClick: () => {
                  const allBtn = document.querySelector('#sessionStatusFilterBar .filter-pill-btn[data-status=""]');
                  if (allBtn) allBtn.click();
                },
              },
              { label: "Buat Study Intent", href: "create-intent.html", variantClass: "btn-la--primary" },
            ]
          : [{ label: "Buat Study Intent", href: "create-intent.html", variantClass: "btn-la--primary" }],
      });
      return;
    }

    renderMySessionsCards(container, list, user);
  } catch (err) {
    if (seq !== sessionsPageState.requestSeq) return;
    if (countPill) countPill.textContent = "0 sesi";

    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }

    if (err.isNetworkError || err.status === 0) {
      renderStatePanel(container, {
        icon: "bi-wifi-off",
        iconVariant: "warning",
        title: "Koneksi Bermasalah",
        description: "Tidak dapat terhubung ke server LaFriend. Periksa koneksi jaringanmu lalu coba lagi.",
        actions: [{ label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadMySessionsList(user) }],
      });
      return;
    }

    renderStatePanel(container, {
      icon: "bi-exclamation-octagon",
      iconVariant: "danger",
      title: "Gagal Memuat Daftar Sesi",
      description: err.status >= 500
        ? "Terjadi kesalahan pada server saat memuat daftar sesi. Silakan coba beberapa saat lagi."
        : (err.message || "Terjadi kesalahan saat mengambil daftar sesi belajar."),
      actions: [{ label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadMySessionsList(user) }],
    });
  } finally {
    if (seq === sessionsPageState.requestSeq) {
      sessionsPageState.isLoading = false;
    }
  }
}

function renderMySessionsCards(container, sessions, user) {
  container.textContent = "";
  const fragment = document.createDocumentFragment();

  sessions.forEach((session) => {
    const isHost = session.host_id === user.student_id;
    const statusMeta = getSessionStatusMeta(session.status);
    const primarySlot = getPrimarySlot(session.slots);
    const activeCount = countActiveMembers(session.members);

    const card = createEl("article", "session-card");
    card.dataset.sessionId = session.session_id || "";

    // Baris atas: badge status + badge role
    const topRow = createEl("div", "session-card-top");
    const badgesLeft = createEl("div", "badge-row");
    badgesLeft.appendChild(createEl("span", `s-badge ${statusMeta.badgeClass}`, statusMeta.label));
    badgesLeft.appendChild(
      createEl("span", `s-badge ${isHost ? "s-badge--host" : "s-badge--member"}`, isHost ? "HOST" : "MEMBER")
    );
    topRow.appendChild(badgesLeft);
    card.appendChild(topRow);

    // Judul & Mata Kuliah
    card.appendChild(createEl("h2", "session-card-title", session.title || "Sesi Belajar"));

    const courseParts = [];
    if (session.course && session.course.course_code) courseParts.push(session.course.course_code);
    if (session.course && session.course.course_name) courseParts.push(session.course.course_name);
    const modeLabel = LEARNING_MODE_LABELS[(session.learning_mode || "").toUpperCase()] || session.learning_mode || "-";
    const styleLabel = COLLAB_STYLE_LABELS[(session.collaboration_style || "").toUpperCase()] || session.collaboration_style || "-";
    const courseLine = courseParts.length > 0
      ? `${courseParts.join(" · ")} · ${modeLabel}`
      : `${styleLabel} · ${modeLabel}`;
    card.appendChild(createEl("div", "session-card-course", courseLine));

    // Meta chips: tanggal, jam, mode
    const metaGrid = createEl("div", "session-meta-grid");

    const dateChip = createEl("div", "session-meta-chip");
    dateChip.appendChild(createIcon("bi-calendar-event"));
    dateChip.appendChild(
      createEl("span", "", primarySlot ? formatSessionDateIndo(primarySlot.session_date) : "Jadwal belum tersedia")
    );
    metaGrid.appendChild(dateChip);

    if (primarySlot && primarySlot.start_time && primarySlot.end_time) {
      const timeChip = createEl("div", "session-meta-chip");
      timeChip.appendChild(createIcon("bi-clock"));
      const extraSlots = Array.isArray(session.slots) && session.slots.length > 1
        ? ` (+${session.slots.length - 1} slot)`
        : "";
      timeChip.appendChild(createEl("span", "", `${primarySlot.start_time}–${primarySlot.end_time}${extraSlots}`));
      metaGrid.appendChild(timeChip);
    }

    const modeChip = createEl("div", "session-meta-chip");
    modeChip.appendChild(createIcon(session.learning_mode === "ONLINE" ? "bi-camera-video" : "bi-geo-alt"));
    modeChip.appendChild(createEl("span", "", modeLabel));
    metaGrid.appendChild(modeChip);

    card.appendChild(metaGrid);

    // Footer: jumlah anggota + tombol Lihat Detail
    const footer = createEl("div", "session-card-footer");
    const memberSummary = createEl("div", "session-member-summary");
    memberSummary.appendChild(createIcon("bi-people-fill"));
    memberSummary.appendChild(
      createEl("span", "", `${activeCount} anggota aktif · ${isHost ? "Host" : "Member"}`)
    );
    footer.appendChild(memberSummary);

    const detailBtn = createEl("a", "btn-detail-link");
    detailBtn.href = `session-detail.html?id=${encodeURIComponent(session.session_id)}`;
    detailBtn.appendChild(createEl("span", "", "Lihat Detail"));
    detailBtn.appendChild(createIcon("bi-arrow-right"));
    footer.appendChild(detailBtn);

    card.appendChild(footer);
    fragment.appendChild(card);
  });

  container.appendChild(fragment);
}


// ==============================================================================
// 6B. HALAMAN DETAIL SESI & VISUALISASI KEANGGOTAAN (session-detail.html — Day 23.3)
// ==============================================================================
const sessionDetailState = {
  sessionId: "",
  user: null,
  session: null,
  isActionPending: false,
  requestSeq: 0,
};

function initSessionDetailPage() {
  const user = app.requireAuth();
  if (!user) return;

  sessionDetailState.user = user;
  const params = new URLSearchParams(window.location.search);
  const sessionId = (params.get("id") || "").trim();
  sessionDetailState.sessionId = sessionId;

  const btnRefresh = document.getElementById("btnRefreshDetail");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      if (!sessionDetailState.isActionPending) {
        loadSessionDetail({ preserveAlert: false });
      }
    });
  }

  if (!sessionId) {
    const headerSub = document.getElementById("detailHeaderSub");
    if (headerSub) headerSub.textContent = "ID sesi tidak valid";
    const container = document.getElementById("sessionDetailContent");
    if (container) {
      renderStatePanel(container, {
        icon: "bi-search",
        iconVariant: "warning",
        title: "Sesi Tidak Ditemukan",
        description: "Tautan detail sesi tidak menyertakan ID sesi yang valid.",
        actions: [{ label: "Kembali ke Sesi Belajarku", href: "sessions.html", variantClass: "btn-la--primary" }],
      });
    }
    return;
  }

  loadSessionDetail({ preserveAlert: false });
}

async function loadSessionDetail({ preserveAlert = false } = {}) {
  const container = document.getElementById("sessionDetailContent");
  const alertContainer = document.getElementById("detailAlertContainer");
  const headerSub = document.getElementById("detailHeaderSub");
  if (!container) return;

  if (!preserveAlert && alertContainer) {
    renderInlineAlert(alertContainer, "info", "");
  }

  const seq = ++sessionDetailState.requestSeq;
  renderStatePanel(container, {
    icon: "spinner",
    title: "Memuat Detail Sesi...",
    description: "Mengambil informasi terbaru dari server.",
  });

  try {
    const session = await app.sessions.getDetail(sessionDetailState.sessionId);
    if (seq !== sessionDetailState.requestSeq) return;

    sessionDetailState.session = session;
    renderSessionDetail(session);
  } catch (err) {
    if (seq !== sessionDetailState.requestSeq) return;
    sessionDetailState.session = null;

    if (err.status === 401) {
      app.handleUnauthorized();
      return;
    }

    if (err.status === 403) {
      // PENTING: HTTP 403 bukan logout; jangan hapus token!
      // Jangan pula mencoba membaca detail melalui endpoint alternatif.
      if (headerSub) headerSub.textContent = "Akses ditolak";
      renderStatePanel(container, {
        icon: "bi-shield-lock",
        iconVariant: "danger",
        title: "Akses Ditolak",
        description: err.message || "Kamu tidak lagi memiliki hak akses untuk melihat detail sesi belajar ini.",
        actions: [{ label: "Kembali ke Sesi Belajarku", href: "sessions.html", variantClass: "btn-la--primary" }],
      });
      return;
    }

    if (err.status === 404) {
      if (headerSub) headerSub.textContent = "Sesi tidak ditemukan";
      renderStatePanel(container, {
        icon: "bi-question-circle",
        iconVariant: "warning",
        title: "Sesi Tidak Ditemukan",
        description: err.message || "Sesi belajar yang kamu cari tidak ditemukan atau sudah tidak tersedia.",
        actions: [{ label: "Kembali ke Sesi Belajarku", href: "sessions.html", variantClass: "btn-la--primary" }],
      });
      return;
    }

    if (err.isNetworkError || err.status === 0) {
      if (headerSub) headerSub.textContent = "Koneksi bermasalah";
      renderStatePanel(container, {
        icon: "bi-wifi-off",
        iconVariant: "warning",
        title: "Koneksi Bermasalah",
        description: "Tidak dapat terhubung ke server. Periksa koneksimu lalu coba muat ulang.",
        actions: [
          { label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadSessionDetail({ preserveAlert: false }) },
          { label: "Kembali ke Sesi Belajarku", href: "sessions.html", variantClass: "btn-la--secondary" },
        ],
      });
      return;
    }

    if (headerSub) headerSub.textContent = "Gagal memuat sesi";
    renderStatePanel(container, {
      icon: "bi-exclamation-octagon",
      iconVariant: "danger",
      title: "Gagal Memuat Detail Sesi",
      description: err.status >= 500
        ? "Terjadi kesalahan pada server. Silakan coba beberapa saat lagi."
        : (err.message || "Terjadi kesalahan saat mengambil detail sesi belajar."),
      actions: [
        { label: "Coba Lagi", variantClass: "btn-la--primary", onClick: () => loadSessionDetail({ preserveAlert: false }) },
        { label: "Kembali ke Sesi Belajarku", href: "sessions.html", variantClass: "btn-la--secondary" },
      ],
    });
  }
}

function renderSessionDetail(session) {
  const container = document.getElementById("sessionDetailContent");
  const headerSub = document.getElementById("detailHeaderSub");
  const user = sessionDetailState.user;
  if (!container || !session || !user) return;

  const members = Array.isArray(session.members) ? session.members : [];
  const slots = Array.isArray(session.slots) ? session.slots : [];
  const isHost = session.host_id === user.student_id;
  const myMembership = members.find((m) => m.student_id === user.student_id) || null;
  const statusMeta = getSessionStatusMeta(session.status);
  const confirmedCount = countConfirmedMembers(members);

  if (headerSub) {
    headerSub.textContent = `${statusMeta.label} · ${isHost ? "Host" : "Member"}`;
  }

  container.textContent = "";
  const fragment = document.createDocumentFragment();

  // --- BAGIAN A: SESSION OVERVIEW ---
  const overviewCard = createEl("section", "detail-section-card");
  overviewCard.setAttribute("aria-label", "Ringkasan Sesi");

  const badgeRow = createEl("div", "badge-row");
  badgeRow.appendChild(createEl("span", `s-badge ${statusMeta.badgeClass}`, statusMeta.label));
  badgeRow.appendChild(
    createEl("span", `s-badge ${isHost ? "s-badge--host" : "s-badge--member"}`, isHost ? "Kamu adalah HOST" : "Kamu adalah MEMBER")
  );
  overviewCard.appendChild(badgeRow);

  overviewCard.appendChild(createEl("h2", "detail-hero-title", session.title || "Sesi Belajar"));

  if (session.course) {
    const cLabel = [session.course.course_code, session.course.course_name].filter(Boolean).join(" — ");
    if (cLabel) {
      overviewCard.appendChild(createEl("div", "detail-course-line", cLabel));
    }
  }

  if (session.description && session.description.trim()) {
    overviewCard.appendChild(createEl("p", "detail-description", session.description.trim()));
  }

  const kvGrid = createEl("div", "detail-kv-grid");
  const kvItems = [
    {
      label: "Tujuan Belajar",
      value: LEARNING_GOAL_LABELS[(session.learning_goal || "").toUpperCase()] || session.learning_goal || "-",
    },
    {
      label: "Gaya Kolaborasi",
      value: COLLAB_STYLE_LABELS[(session.collaboration_style || "").toUpperCase()] || session.collaboration_style || "-",
    },
    {
      label: "Mode Belajar",
      value: LEARNING_MODE_LABELS[(session.learning_mode || "").toUpperCase()] || session.learning_mode || "-",
    },
    {
      label: "Ukuran Grup",
      value: `${session.min_group_size}–${session.max_group_size} mahasiswa (${confirmedCount} aktif)`,
    },
  ];
  if (session.location && session.location.trim()) {
    kvItems.push({ label: "Lokasi / Tautan", value: session.location.trim(), full: true });
  }

  kvItems.forEach((item) => {
    const box = createEl("div", `detail-kv-item${item.full ? " detail-kv-item--full" : ""}`);
    box.appendChild(createEl("div", "detail-kv-label", item.label));
    box.appendChild(createEl("div", "detail-kv-value", item.value));
    kvGrid.appendChild(box);
  });
  overviewCard.appendChild(kvGrid);
  fragment.appendChild(overviewCard);

  // --- BAGIAN B: SCHEDULE INFORMATION ---
  const scheduleCard = createEl("section", "detail-section-card");
  scheduleCard.setAttribute("aria-label", "Informasi Jadwal");

  const schedHeader = createEl("div", "detail-section-header");
  const schedTitle = createEl("div", "detail-section-title");
  schedTitle.appendChild(createIcon("bi-calendar3"));
  schedTitle.appendChild(createEl("span", "", "Jadwal Sesi"));
  schedHeader.appendChild(schedTitle);
  schedHeader.appendChild(createEl("span", "s-badge s-badge--neutral", `${slots.length} slot`));
  scheduleCard.appendChild(schedHeader);

  if (slots.length === 0) {
    scheduleCard.appendChild(createEl("div", "lifecycle-status-note", "Belum ada slot jadwal tercatat untuk sesi ini."));
  } else {
    const slotList = createEl("div", "slot-list");
    slots.forEach((slot) => {
      const slotMeta = getSlotStatusMeta(slot.status);
      const row = createEl("div", "slot-item-row");

      const info = createEl("div", "slot-item-info");
      info.appendChild(createEl("div", "slot-item-date", formatSessionDateIndo(slot.session_date)));
      info.appendChild(createEl("div", "slot-item-time", `${slot.start_time || "--:--"} – ${slot.end_time || "--:--"}`));
      row.appendChild(info);

      row.appendChild(createEl("span", `s-badge ${slotMeta.badgeClass}`, slotMeta.label));
      slotList.appendChild(row);
    });
    scheduleCard.appendChild(slotList);
  }
  fragment.appendChild(scheduleCard);

  // --- BAGIAN C: MEMBERS (STRICT PRIVACY: tanpa intent_id, email, atau NIM) ---
  const membersCard = createEl("section", "detail-section-card");
  membersCard.setAttribute("aria-label", "Daftar Anggota");

  const memHeader = createEl("div", "detail-section-header");
  const memTitle = createEl("div", "detail-section-title");
  memTitle.appendChild(createIcon("bi-people-fill"));
  memTitle.appendChild(createEl("span", "", "Anggota Sesi"));
  memHeader.appendChild(memTitle);
  memHeader.appendChild(createEl("span", "s-badge s-badge--neutral", `${members.length} tercatat`));
  membersCard.appendChild(memHeader);

  if (members.length === 0) {
    membersCard.appendChild(createEl("div", "lifecycle-status-note", "Belum ada anggota tercatat."));
  } else {
    const memberList = createEl("div", "member-list");
    members.forEach((member) => {
      const memberStatus = (member.status || "").toUpperCase();
      const memberRole = (member.role || "MEMBER").toUpperCase();
      const memMeta = getMembershipStatusMeta(memberStatus);
      const isMe = member.student_id === user.student_id;
      const isMemberHost = memberRole === "HOST" || member.student_id === session.host_id;
      const displayName = (member.student && member.student.full_name) ? member.student.full_name : "Mahasiswa";
      const isInactive = memberStatus === "WITHDRAWN" || memberStatus === "REMOVED" || memberStatus === "DECLINED";

      const row = createEl("div", `member-item-row${isInactive ? " member-item-row--inactive" : ""}`);
      row.dataset.studentId = member.student_id || "";

      const left = createEl("div", "member-item-left");
      left.appendChild(createEl("div", "member-avatar", displayName.trim().charAt(0).toUpperCase() || "M"));

      const info = createEl("div", "member-info");
      const nameRow = createEl("div", "member-name-row");
      nameRow.appendChild(createEl("span", "member-name", displayName));
      if (isMe) {
        nameRow.appendChild(createEl("span", "s-badge s-badge--you", "Kamu"));
      }
      info.appendChild(nameRow);

      const memBadges = createEl("div", "badge-row");
      memBadges.appendChild(
        createEl("span", `s-badge ${isMemberHost ? "s-badge--host" : "s-badge--member"}`, isMemberHost ? "HOST" : "MEMBER")
      );
      memBadges.appendChild(createEl("span", `s-badge ${memMeta.badgeClass}`, memMeta.label));
      info.appendChild(memBadges);

      left.appendChild(info);
      row.appendChild(left);

      // Slot tombol aksi tingkat anggota (diisi pada Day 23.4 untuk Host Remove)
      const actionsSlot = createEl("div", "member-item-actions");
      if (typeof attachMemberRowAction === "function") {
        attachMemberRowAction(actionsSlot, { session, member, isHost, isMemberHost, displayName });
      }
      if (actionsSlot.childNodes.length > 0) {
        row.appendChild(actionsSlot);
      }

      memberList.appendChild(row);
    });
    membersCard.appendChild(memberList);
  }
  fragment.appendChild(membersCard);

  // --- BAGIAN D: LIFECYCLE INFORMATION & CONTROLS ---
  const lifecycleCard = createEl("section", "detail-section-card");
  lifecycleCard.setAttribute("aria-label", "Status dan Pengelolaan Sesi");

  const lcHeader = createEl("div", "detail-section-header");
  const lcTitle = createEl("div", "detail-section-title");
  lcTitle.appendChild(createIcon("bi-sliders"));
  lcTitle.appendChild(createEl("span", "", "Pengelolaan Sesi"));
  lcHeader.appendChild(lcTitle);
  lcHeader.appendChild(createEl("span", `s-badge ${statusMeta.badgeClass}`, statusMeta.label));
  lifecycleCard.appendChild(lcHeader);

  // Informasi kebijakan Quorum Option A (Explicit Host Control):
  // Jika anggota CONFIRMED < min_group_size saat sesi masih CONFIRMED, tampilkan info saja tanpa auto-cancel.
  if (session.status === "CONFIRMED" && confirmedCount < session.min_group_size) {
    const quorumBox = createEl("div", "session-alert session-alert--warning");
    quorumBox.appendChild(createIcon("bi-info-circle-fill"));
    quorumBox.appendChild(
      createEl(
        "span",
        "",
        `Jumlah anggota aktif (${confirmedCount}) saat ini berada di bawah batas minimum grup (${session.min_group_size}). Sesi tetap berstatus Terkonfirmasi sampai Host menentukan tindakan selanjutnya.`
      )
    );
    lifecycleCard.appendChild(quorumBox);
  }

  const actionsContainer = createEl("div", "lifecycle-actions-stack");
  actionsContainer.id = "lifecycleActionsSlot";

  if (typeof renderLifecycleActionControls === "function") {
    renderLifecycleActionControls(actionsContainer, { session, user, isHost, myMembership });
  } else {
    actionsContainer.appendChild(
      createEl(
        "div",
        "lifecycle-status-note",
        `Status sesi saat ini: ${statusMeta.label}.`
      )
    );
  }

  lifecycleCard.appendChild(actionsContainer);
  fragment.appendChild(lifecycleCard);

  container.appendChild(fragment);
}


// ==============================================================================
// 6C. DAY 23.4 & 23.5 — LIFECYCLE ACTION INTEGRATION, MODAL & ERROR HARDENING
// ==============================================================================
function setLifecycleButtonsDisabled(disabled, activeBtn) {
  const buttons = document.querySelectorAll(
    "#sessionDetailContent button[data-lifecycle-action], #btnRefreshDetail"
  );
  buttons.forEach((btn) => {
    btn.disabled = Boolean(disabled);
    if (disabled && btn === activeBtn) {
      btn.dataset.loading = "true";
    } else if (!disabled) {
      delete btn.dataset.loading;
    }
  });
}

function attachMemberRowAction(actionsSlot, { session, member, isHost, isMemberHost, displayName }) {
  const sessionStatus = (session.status || "").toUpperCase();
  const memberStatus = (member.status || "").toUpperCase();

  // Aturan visibilitas Host Remove:
  // Hanya tampil jika pengguna adalah Host, sesi CONFIRMED, target bukan Host, dan target CONFIRMED.
  if (!isHost || sessionStatus !== "CONFIRMED" || isMemberHost || memberStatus !== "CONFIRMED") {
    return;
  }

  const btnRemove = createEl("button", "btn-la btn-la--outline-danger btn-la--sm");
  btnRemove.type = "button";
  btnRemove.dataset.lifecycleAction = "remove";
  btnRemove.dataset.targetStudentId = member.student_id || "";
  btnRemove.appendChild(createIcon("bi-person-dash-fill"));
  btnRemove.appendChild(createEl("span", "", "Keluarkan"));

  btnRemove.addEventListener("click", () => {
    if (sessionDetailState.isActionPending) return;
    openConfirmActionModal({
      title: "Keluarkan Anggota?",
      message: `Apakah kamu yakin ingin mengeluarkan ${displayName} dari sesi belajar ini? Anggota yang dikeluarkan tidak lagi dapat mengakses detail sesi.`,
      confirmLabel: "Ya, Keluarkan",
      confirmVariant: "btn-la--danger",
      onConfirm: () => executeRemoveMemberAction(session.session_id, member.student_id, displayName, btnRemove),
    });
  });

  actionsSlot.appendChild(btnRemove);
}

function renderLifecycleActionControls(container, { session, isHost, myMembership }) {
  container.textContent = "";
  const sessionStatus = (session.status || "").toUpperCase();
  const myStatus = myMembership ? (myMembership.status || "").toUpperCase() : "";

  // 1. HOST pada sesi CONFIRMED -> Complete & Cancel
  if (isHost && sessionStatus === "CONFIRMED") {
    const btnComplete = createEl("button", "btn-la btn-la--success");
    btnComplete.type = "button";
    btnComplete.id = "btnCompleteSession";
    btnComplete.dataset.lifecycleAction = "complete";
    btnComplete.appendChild(createIcon("bi-check-circle-fill"));
    btnComplete.appendChild(createEl("span", "", "Selesaikan Sesi (Complete)"));
    btnComplete.addEventListener("click", () => {
      if (sessionDetailState.isActionPending) return;
      openConfirmActionModal({
        title: "Selesaikan Sesi Belajar?",
        message: "Apakah kamu yakin ingin menyelesaikan sesi belajar ini? Setelah selesai, sesi tidak dapat dibatalkan kembali.",
        confirmLabel: "Ya, Selesaikan",
        confirmVariant: "btn-la--success",
        onConfirm: () => executeCompleteSessionAction(session.session_id, btnComplete),
      });
    });

    const btnCancel = createEl("button", "btn-la btn-la--outline-danger");
    btnCancel.type = "button";
    btnCancel.id = "btnCancelSession";
    btnCancel.dataset.lifecycleAction = "cancel";
    btnCancel.appendChild(createIcon("bi-x-circle-fill"));
    btnCancel.appendChild(createEl("span", "", "Batalkan Sesi (Cancel)"));
    btnCancel.addEventListener("click", () => {
      if (sessionDetailState.isActionPending) return;
      openConfirmActionModal({
        title: "Batalkan Sesi Belajar?",
        message: "Apakah kamu yakin ingin membatalkan sesi belajar ini? Setelah dibatalkan, sesi tidak dapat diaktifkan kembali dan riwayat anggota tetap tersimpan.",
        confirmLabel: "Ya, Batalkan",
        confirmVariant: "btn-la--danger",
        onConfirm: () => executeCancelSessionAction(session.session_id, btnCancel),
      });
    });

    container.appendChild(btnComplete);
    container.appendChild(btnCancel);
    return;
  }

  // 2. MEMBER CONFIRMED (non-Host) pada sesi CONFIRMED -> Withdraw
  if (!isHost && myStatus === "CONFIRMED" && sessionStatus === "CONFIRMED") {
    const btnWithdraw = createEl("button", "btn-la btn-la--outline-danger");
    btnWithdraw.type = "button";
    btnWithdraw.id = "btnWithdrawSession";
    btnWithdraw.dataset.lifecycleAction = "withdraw";
    btnWithdraw.appendChild(createIcon("bi-box-arrow-left"));
    btnWithdraw.appendChild(createEl("span", "", "Mengundurkan Diri (Withdraw)"));
    btnWithdraw.addEventListener("click", () => {
      if (sessionDetailState.isActionPending) return;
      openConfirmActionModal({
        title: "Mengundurkan Diri dari Sesi?",
        message: "Apakah kamu yakin ingin mengundurkan diri dari sesi belajar ini? Setelah mengundurkan diri, kamu tidak lagi dapat mengakses detail sesi ini.",
        confirmLabel: "Ya, Mengundurkan Diri",
        confirmVariant: "btn-la--danger",
        onConfirm: () => executeWithdrawSessionAction(session.session_id, btnWithdraw),
      });
    });

    container.appendChild(btnWithdraw);
    return;
  }

  // 3. Kondisi informasional tanpa tombol mutasi (sesuai matriks visibilitas Day 23.4)
  let noteText = "Tidak ada tindakan pengelolaan yang tersedia untuk status sesi saat ini.";
  if (sessionStatus === "COMPLETED") {
    noteText = "Sesi belajar ini telah selesai. Seluruh informasi dan histori anggota tetap dipertahankan.";
  } else if (sessionStatus === "CANCELLED") {
    noteText = "Sesi belajar ini telah dibatalkan oleh Host. Seluruh informasi dan histori anggota tetap dipertahankan.";
  } else if (sessionStatus === "EXPIRED") {
    noteText = "Sesi belajar ini telah kedaluwarsa dan tidak dapat diubah lagi.";
  } else if (!isHost && myStatus === "ACCEPTED" && sessionStatus === "CONFIRMED") {
    noteText = "Status keanggotaanmu saat ini adalah Menerima undangan (ACCEPTED). Aksi pengunduran diri hanya tersedia untuk anggota berstatus Aktif (CONFIRMED).";
  }

  container.appendChild(createEl("div", "lifecycle-status-note", noteText));
}

function openConfirmActionModal({ title, message, confirmLabel, confirmVariant, onConfirm }) {
  const modal = document.getElementById("confirmActionModal");
  const titleEl = document.getElementById("confirmModalTitle");
  const msgEl = document.getElementById("confirmModalMessage");
  const btnCancel = document.getElementById("btnConfirmCancel");
  const btnProceed = document.getElementById("btnConfirmProceed");

  if (!modal || !titleEl || !msgEl || !btnCancel || !btnProceed) {
    if (window.confirm(message)) {
      onConfirm();
    }
    return;
  }

  titleEl.textContent = title || "Konfirmasi Tindakan";
  msgEl.textContent = message || "";
  btnProceed.className = `btn-la ${confirmVariant || "btn-la--primary"} btn-la--sm`;
  btnProceed.textContent = confirmLabel || "Lanjutkan";
  btnProceed.disabled = false;
  btnCancel.disabled = false;
  modal.classList.remove("d-none");

  function cleanup() {
    modal.classList.add("d-none");
    btnCancel.removeEventListener("click", handleCancel);
    btnProceed.removeEventListener("click", handleProceed);
    modal.removeEventListener("click", handleBackdrop);
    document.removeEventListener("keydown", handleEsc);
  }

  function handleCancel() {
    if (sessionDetailState.isActionPending) return;
    cleanup();
  }

  function handleBackdrop(e) {
    if (e.target === modal && !sessionDetailState.isActionPending) {
      cleanup();
    }
  }

  function handleEsc(e) {
    if (e.key === "Escape" && !sessionDetailState.isActionPending) {
      cleanup();
    }
  }

  async function handleProceed() {
    if (sessionDetailState.isActionPending) return;
    btnCancel.disabled = true;
    btnProceed.disabled = true;
    btnProceed.dataset.loading = "true";
    btnProceed.textContent = "";
    btnProceed.appendChild(createEl("span", "la-spinner la-spinner--sm"));
    btnProceed.appendChild(createEl("span", "", "Memproses..."));

    try {
      await onConfirm();
    } finally {
      delete btnProceed.dataset.loading;
      cleanup();
    }
  }

  btnCancel.addEventListener("click", handleCancel);
  btnProceed.addEventListener("click", handleProceed);
  modal.addEventListener("click", handleBackdrop);
  document.addEventListener("keydown", handleEsc);
}

async function executeCompleteSessionAction(sessionId, triggerBtn) {
  if (sessionDetailState.isActionPending) return;
  const alertContainer = document.getElementById("detailAlertContainer");
  sessionDetailState.isActionPending = true;
  setLifecycleButtonsDisabled(true, triggerBtn);

  try {
    const updatedSession = await app.sessions.complete(sessionId);
    sessionDetailState.session = updatedSession;
    renderInlineAlert(alertContainer, "success", "Sesi belajar berhasil ditandai sebagai selesai (COMPLETED).");
    renderSessionDetail(updatedSession);
  } catch (err) {
    await handleLifecycleActionError(err);
  } finally {
    sessionDetailState.isActionPending = false;
    setLifecycleButtonsDisabled(false);
  }
}

async function executeCancelSessionAction(sessionId, triggerBtn) {
  if (sessionDetailState.isActionPending) return;
  const alertContainer = document.getElementById("detailAlertContainer");
  sessionDetailState.isActionPending = true;
  setLifecycleButtonsDisabled(true, triggerBtn);

  try {
    const updatedSession = await app.sessions.cancel(sessionId);
    sessionDetailState.session = updatedSession;
    renderInlineAlert(alertContainer, "success", "Sesi belajar berhasil dibatalkan (CANCELLED).");
    renderSessionDetail(updatedSession);
  } catch (err) {
    await handleLifecycleActionError(err);
  } finally {
    sessionDetailState.isActionPending = false;
    setLifecycleButtonsDisabled(false);
  }
}

async function executeWithdrawSessionAction(sessionId, triggerBtn) {
  if (sessionDetailState.isActionPending) return;
  const detailContainer = document.getElementById("sessionDetailContent");
  const alertContainer = document.getElementById("detailAlertContainer");
  const headerSub = document.getElementById("detailHeaderSub");
  sessionDetailState.isActionPending = true;
  setLifecycleButtonsDisabled(true, triggerBtn);
  let withdrewSuccessfully = false;

  try {
    // PENTING (Day 22 & 23.4 Privacy Contract):
    // Response withdraw adalah SessionWithdrawResponse minimal:
    // { session_id, session_status, membership_status }
    // JANGAN memperlakukannya sebagai StudySessionResponse!
    const withdrawRes = await app.sessions.withdraw(sessionId);
    const membershipStatus = (withdrawRes && withdrawRes.membership_status) || "WITHDRAWN";
    withdrewSuccessfully = true;

    // Hapus state detail privat dari memori & DOM frontend segera
    sessionDetailState.session = null;
    if (headerSub) headerSub.textContent = "Pengunduran diri berhasil";
    renderInlineAlert(alertContainer, "success", "");

    if (detailContainer) {
      renderStatePanel(detailContainer, {
        icon: "bi-check-circle-fill",
        title: "Berhasil Mengundurkan Diri",
        description: `Status keanggotaanmu kini ${getMembershipStatusMeta(membershipStatus).label}. Mengalihkan kembali ke Sesi Belajarku...`,
        actions: [{ label: "Kembali ke Sesi Belajarku", href: "sessions.html", variantClass: "btn-la--primary" }],
      });
    }

    sessionStorage.setItem(
      SESSION_FLASH_KEY,
      JSON.stringify({
        variant: "success",
        message: "Kamu berhasil mengundurkan diri dari sesi belajar.",
      })
    );

    setTimeout(() => {
      window.location.replace("sessions.html");
    }, 650);
  } catch (err) {
    await handleLifecycleActionError(err);
  } finally {
    if (!withdrewSuccessfully) {
      sessionDetailState.isActionPending = false;
      setLifecycleButtonsDisabled(false);
    }
  }
}

async function executeRemoveMemberAction(sessionId, targetStudentId, displayName, triggerBtn) {
  if (sessionDetailState.isActionPending) return;
  const alertContainer = document.getElementById("detailAlertContainer");
  sessionDetailState.isActionPending = true;
  setLifecycleButtonsDisabled(true, triggerBtn);

  try {
    const updatedSession = await app.sessions.removeMember(sessionId, targetStudentId);
    sessionDetailState.session = updatedSession;
    renderInlineAlert(alertContainer, "success", `${displayName} berhasil dikeluarkan dari sesi belajar.`);
    renderSessionDetail(updatedSession);
  } catch (err) {
    await handleLifecycleActionError(err);
  } finally {
    sessionDetailState.isActionPending = false;
    setLifecycleButtonsDisabled(false);
  }
}

async function handleLifecycleActionError(err) {
  const alertContainer = document.getElementById("detailAlertContainer");

  // 401 -> Token tidak valid/kedaluwarsa -> bersihkan auth dan kembali ke login
  if (err.status === 401) {
    app.handleUnauthorized();
    return;
  }

  // 403 -> Akses ditolak (JANGAN hapus token!)
  if (err.status === 403) {
    renderInlineAlert(
      alertContainer,
      "danger",
      err.message || "Kamu tidak memiliki izin untuk melakukan tindakan ini."
    );
    await loadSessionDetail({ preserveAlert: true });
    return;
  }

  // 404 -> Resource tidak ditemukan
  if (err.status === 404) {
    renderInlineAlert(
      alertContainer,
      "warning",
      err.message || "Sesi atau anggota yang dimaksud tidak ditemukan."
    );
    await loadSessionDetail({ preserveAlert: true });
    return;
  }

  // 409 -> Konflik state (mis. concurrent Complete vs Cancel, atau Cancel vs Withdraw)
  // JANGAN ulangi mutasi secara otomatis; segarkan detail terbaru dari backend.
  if (err.status === 409) {
    renderInlineAlert(
      alertContainer,
      "warning",
      `${err.message || "Status sesi telah berubah."} Menampilkan data terbaru dari server.`
    );
    await loadSessionDetail({ preserveAlert: true });
    return;
  }

  // 400 / 422 -> Aturan bisnis atau input tidak valid
  if (err.status === 400 || err.status === 422) {
    renderInlineAlert(
      alertContainer,
      "danger",
      err.message || "Permintaan tidak valid untuk kondisi sesi saat ini."
    );
    return;
  }

  // Network error
  if (err.isNetworkError || err.status === 0) {
    renderInlineAlert(
      alertContainer,
      "warning",
      "Koneksi ke server terputus. Periksa jaringan internetmu lalu coba lagi."
    );
    return;
  }

  // 500+ -> Pesan generik tanpa detail internal server
  renderInlineAlert(
    alertContainer,
    "danger",
    "Terjadi kesalahan pada server saat memproses tindakan. Silakan coba beberapa saat lagi."
  );
}



