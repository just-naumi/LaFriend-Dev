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

    try {
      const response = await fetch(url, {
        ...options,
        headers: headers,
      });

      const responseData = await response.json().catch(() => ({}));

      // Jika server mengembalikan status error (bukan 2xx)
      if (!response.ok) {
        throw new Error(responseData.detail || `Terjadi kesalahan status ${response.status}`);
      }

      return responseData;
    } catch (err) {
      console.error(`[API Error] ${endpoint}:`, err);
      throw err;
    }
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

  // KOTAK INPUT AI: Menceritakan kebutuhan belajar ke AI
  const aiNeedInput = document.getElementById("aiNeedInput");
  const btnDashboardAiSubmit = document.getElementById("btnDashboardAiSubmit");

  async function submitAiPrompt() {
    const promptText = aiNeedInput ? aiNeedInput.value.trim() : "";
    if (!promptText) {
      window.location.href = "create-intent.html";
      return;
    }
    // Jalankan animasi timeline loading turun ke bawah seperti di LaQris
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

  // Animasi Step Timeline Loader AI (Referensi LaQris)
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

    // Mulai Step 1: Pesan Belajar Diterima
    setStepState(1, "active");
    await delay(350);

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
    await delay(450);

    // Step 3: Validasi Kurikulum Telkom University
    setStepState(2, "completed");
    setStepState(3, "active");
    await delay(450);

    // Tunggu hasil ekstraksi dari backend jika belum selesai
    const extractionResult = await extractPromise;

    // Step 4: Normalisasi Waktu & Lokasi
    setStepState(3, "completed");
    setStepState(4, "active");
    await delay(400);

    // Step 5: Formulir Siap Digunakan
    setStepState(4, "completed");
    setStepState(5, "completed");
    await delay(350);

    // Simpan hasil ekstraksi ke sessionStorage agar form create-intent langsung terisi instan
    if (extractionResult) {
      sessionStorage.setItem("lafriend_ai_extraction_result", JSON.stringify(extractionResult));
    }
    sessionStorage.setItem("lafriend_ai_prompt", promptText);

    // Alihkan ke formulir create-intent
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

  // Isi tanggal default: hari ini s/d 7 hari ke depan
  const today = new Date().toISOString().split("T")[0];
  const nextWeek = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
  const earliestInput = document.getElementById("earliestDate");
  const latestInput = document.getElementById("latestDate");
  if (earliestInput) earliestInput.value = today;
  if (latestInput) latestInput.value = nextWeek;

  // Muat daftar mata kuliah ke dropdown
  await loadCoursesDropdown();

  // Tambahkan 2 baris slot waktu ketersediaan awal
  addTimeSlotRow("Rabu", "09:00", "12:00", 1);
  addTimeSlotRow("Kamis", "13:00", "16:00", 2);

  // Jika ada hasil ekstraksi AI yang sudah disiapkan dari Dashboard
  const cachedResultStr = sessionStorage.getItem("lafriend_ai_extraction_result");
  const storedPrompt = sessionStorage.getItem("lafriend_ai_prompt");

  if (cachedResultStr) {
    sessionStorage.removeItem("lafriend_ai_extraction_result");
    if (storedPrompt) sessionStorage.removeItem("lafriend_ai_prompt");
    try {
      const res = JSON.parse(cachedResultStr);
      applyAIExtractionResult(res);
    } catch (e) {
      console.error("Gagal parse cached AI result:", e);
    }
  } else if (storedPrompt) {
    sessionStorage.removeItem("lafriend_ai_prompt");
    extractAndApplyPrompt(storedPrompt);
  }


  // Tombol tambah slot waktu
  const btnAddSlot = document.getElementById("btnAddSlot");
  if (btnAddSlot) {
    btnAddSlot.addEventListener("click", () => {
      addTimeSlotRow("Jumat", "10:00", "12:00", Math.min(slotCounter + 1, 3));
    });
  }

  // Handle submit form
  const form = document.getElementById("createIntentForm");
  if (form) {
    form.addEventListener("submit", handleCreateIntentSubmit);
  }
}

// ==============================================================================
// LOGIKA EKSTRAKSI AI OTOMATIS DARI PROMPT DASHBOARD
// ==============================================================================
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

// Memasukkan hasil ekstraksi AI ke dalam input form secara langsung
function applyAIExtractionResult(res) {
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

  // 3. Pilih Tujuan Belajar
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

  // 4. Pilih Gaya Kolaborasi
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

  // 5. Pilih Mode Belajar
  if (res.learning_mode) {
    const modeRadioMap = {
      "OFFLINE": "mOffline",
      "ONLINE": "mOnline",
      "HYBRID": "mHybrid",
    };
    const radioId = modeRadioMap[res.learning_mode];
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

  // 7. Slot Waktu Ketersediaan
  if (res.availabilities && res.availabilities.length > 0) {
    const container = document.getElementById("slotsContainer");
    if (container) {
      container.innerHTML = "";
      slotCounter = 0;
      res.availabilities.forEach((slot, idx) => {
        const day = slot.day_or_date || slot.day || "Rabu";
        addTimeSlotRow(day, slot.start_time, slot.end_time, slot.priority_rank || (idx + 1));
      });
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

// Menambahkan baris slot waktu ketersediaan baru (Desain Lega, Rapi & Tidak Menumpuk)
function addTimeSlotRow(day = "Rabu", start = "09:00", end = "12:00", priority = 1) {
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
        <select class="form-select-clean slot-day" style="font-size: 0.88rem; padding: 9px 12px; font-weight: 600; border-radius: 10px; background-color: #F8FAFC;">
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
          <input type="time" class="slot-time-input slot-start" value="${start}" required>
        </div>
        <div class="col-6">
          <label class="form-label-clean mb-1" style="font-size: 0.74rem; color: #64748B; font-weight: 600;">
            <i class="bi bi-clock-history me-1 text-primary"></i> Jam Selesai
          </label>
          <input type="time" class="slot-time-input slot-end" value="${end}" required>
        </div>
      </div>
    </div>
  `;

  container.insertAdjacentHTML("beforeend", html);
}

// Menghapus baris slot waktu
function removeTimeSlotRow(rowId) {
  const rows = document.querySelectorAll(".slot-row-card");
  if (rows.length <= 1) {
    alert("Minimal harus ada 1 slot waktu ketersediaan!");
    return;
  }
  const el = document.getElementById(rowId);
  if (el) el.remove();
}

// Menangani pengiriman form Create Study Intent
async function handleCreateIntentSubmit(e) {
  e.preventDefault();
  const alertBox = document.getElementById("formAlert");
  const btn = document.getElementById("btnSubmitIntent");

  const courseId = document.getElementById("selectCourse").value;
  if (!courseId) {
    if (alertBox) alertBox.innerHTML = `<div class="alert alert-danger py-2 small mb-3">Silakan pilih mata kuliah terlebih dahulu!</div>`;
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Menyimpan ke SQLite...`;

  // Kumpulkan data ketersediaan waktu dari form
  const slotCards = document.querySelectorAll(".slot-row-card");
  const availabilities = [];
  slotCards.forEach(c => {
    availabilities.push({
      day_or_date: c.querySelector(".slot-day").value.trim(),
      start_time: c.querySelector(".slot-start").value,
      end_time: c.querySelector(".slot-end").value,
      priority_rank: parseInt(c.querySelector(".slot-priority").value, 10),
    });
  });

  // Bungkus data payload
  const payload = {
    course_id: courseId,
    topics: document.getElementById("inputTopics").value.trim(),
    learning_goal: document.querySelector('input[name="learningGoal"]:checked')?.value || "UNDERSTAND",
    collaboration_style: document.querySelector('input[name="collabStyle"]:checked')?.value || "DISCUSSION",
    learning_mode: document.querySelector('input[name="learningMode"]:checked')?.value || "OFFLINE",
    earliest_date: document.getElementById("earliestDate").value,
    latest_date: document.getElementById("latestDate").value,
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

