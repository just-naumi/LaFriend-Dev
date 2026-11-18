// ==============================================================================
// day23_session_regression.mjs
// Automated Frontend Session Integration & Authorization UI Regression Suite
// (Node built-in test runner: `node --test LaFriend/frontend/tests/day23_session_regression.mjs`)
// Zero external dependencies, zero backend file changes.
// ==============================================================================

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_DIR = path.resolve(__dirname, "..");

const APP_JS_SOURCE = fs.readFileSync(path.join(FRONTEND_DIR, "js", "app.js"), "utf8");
const SESSIONS_HTML = fs.readFileSync(path.join(FRONTEND_DIR, "sessions.html"), "utf8");
const DETAIL_HTML = fs.readFileSync(path.join(FRONTEND_DIR, "session-detail.html"), "utf8");
const DASHBOARD_HTML = fs.readFileSync(path.join(FRONTEND_DIR, "dashboard.html"), "utf8");
const SESSIONS_CSS = fs.readFileSync(path.join(FRONTEND_DIR, "css", "sessions.css"), "utf8");

// Lightweight DOM & Browser Sandbox for testing vanilla JS app.js directly
class FakeClassList {
  constructor(el) {
    this.el = el;
    this.set = new Set();
  }
  _syncFromString(str) {
    this.set = new Set((str || "").split(/\s+/).filter(Boolean));
  }
  add(...names) {
    names.forEach((n) => this.set.add(n));
    this.el._className = [...this.set].join(" ");
  }
  remove(...names) {
    names.forEach((n) => this.set.delete(n));
    this.el._className = [...this.set].join(" ");
  }
  toggle(name, force) {
    const has = this.set.has(name);
    const shouldAdd = force !== undefined ? Boolean(force) : !has;
    if (shouldAdd) this.set.add(name);
    else this.set.delete(name);
    this.el._className = [...this.set].join(" ");
    return shouldAdd;
  }
  contains(name) {
    return this.set.has(name);
  }
}

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.id = "";
    this._className = "";
    this.classList = new FakeClassList(this);
    this.dataset = {};
    this.attributes = {};
    this.children = [];
    this.childNodes = this.children;
    this.parentNode = null;
    this._textContent = "";
    this.disabled = false;
    this.href = "";
    this.type = "";
    this.listeners = {};
  }
  get className() {
    return this._className;
  }
  set className(val) {
    this._className = String(val || "");
    this.classList._syncFromString(this._className);
  }
  get textContent() {
    if (this.children.length === 0) return this._textContent;
    return this._textContent + this.children.map((c) => c.textContent).join("");
  }
  set textContent(val) {
    this.children = [];
    this.childNodes = this.children;
    this._textContent = String(val ?? "");
  }
  appendChild(child) {
    if (child.tagName === "#FRAGMENT") {
      child.children.forEach((c) => this.appendChild(c));
      return child;
    }
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === "id") this.id = String(v);
  }
  getAttribute(k) {
    return this.attributes[k] ?? null;
  }
  addEventListener(type, fn) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(fn);
  }
  removeEventListener(type, fn) {
    if (!this.listeners[type]) return;
    this.listeners[type] = this.listeners[type].filter((f) => f !== fn);
  }
  click() {
    if (this.disabled) return;
    const ev = { target: this, preventDefault() {} };
    (this.listeners.click || []).forEach((fn) => fn(ev));
  }
  querySelectorAll(selector) {
    const results = [];
    const visit = (node) => {
      for (const child of node.children) {
        if (matchesSimpleSelector(child, selector)) results.push(child);
        visit(child);
      }
    };
    visit(this);
    return results;
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

function matchesSimpleSelector(el, selector) {
  const parts = selector.split(",").map((s) => s.trim());
  return parts.some((part) => {
    const tokens = part.split(/\s+/);
    const last = tokens[tokens.length - 1];
    if (last.startsWith("#")) return el.id === last.slice(1);
    if (last.startsWith(".")) return el.classList.contains(last.slice(1));
    const attrMatch = /^([a-z0-9_-]*)\[([a-z0-9_-]+)(?:="([^"]*)")?\]$/i.exec(last);
    if (attrMatch) {
      const [, tag, attr, val] = attrMatch;
      if (tag && el.tagName !== tag.toUpperCase()) return false;
      if (attr.startsWith("data-")) {
        const key = attr.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        const actual = el.dataset[key];
        return val === undefined ? actual !== undefined : actual === val;
      }
      return val === undefined ? attr in el.attributes : el.attributes[attr] === val;
    }
    return el.tagName === last.toUpperCase();
  });
}

function createStorage() {
  const store = new Map();
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };
}

function bootAppSandbox({ search = "", fetchImpl, elementIds = [] }) {
  const elementsById = new Map();
  const root = new FakeElement("body");
  elementIds.forEach((id) => {
    const el = new FakeElement("div");
    el.id = id;
    elementsById.set(id, el);
    root.appendChild(el);
  });

  const navHistory = [];
  const localStorage = createStorage();
  const sessionStorage = createStorage();

  const document = {
    addEventListener() {},
    removeEventListener() {},
    getElementById: (id) => {
      if (elementsById.has(id)) return elementsById.get(id);
      return root.querySelector(`#${id}`);
    },
    querySelectorAll: (sel) => root.querySelectorAll(sel),
    querySelector: (sel) => root.querySelector(sel),
    createElement: (tag) => new FakeElement(tag),
    createDocumentFragment: () => new FakeElement("#FRAGMENT"),
  };

  const windowObj = {
    location: {
      search,
      href: `http://localhost/session-detail.html${search}`,
      replace(url) {
        navHistory.push({ type: "replace", url });
        this.href = url;
      },
    },
    confirm: () => true,
    alert: () => {},
  };

  const timers = [];
  const sandbox = {
    window: windowObj,
    document,
    localStorage,
    sessionStorage,
    URLSearchParams,
    encodeURIComponent,
    fetch: fetchImpl || (async () => ({ ok: true, status: 200, json: async () => ({}) })),
    console: { log() {}, warn() {}, error() {} },
    setTimeout: (fn, ms) => {
      timers.push({ fn, ms });
      return timers.length;
    },
    clearTimeout: () => {},
  };

  vm.createContext(sandbox);
  vm.runInContext(
    APP_JS_SOURCE +
      "\n;globalThis.__exports = { app, renderSessionDetail, renderMySessionsCards, initSessionDetailPage, loadSessionDetail, executeCompleteSessionAction, executeCancelSessionAction, executeWithdrawSessionAction, executeRemoveMemberAction, sessionDetailState, SESSION_FLASH_KEY };",
    sandbox
  );

  return { ...sandbox.__exports, document, window: windowObj, localStorage, sessionStorage, navHistory, timers };
}

function makeSampleSession(overrides = {}) {
  return {
    session_id: "SESS-100",
    host_id: "stu-host",
    course_id: "crs-1",
    title: "Sesi Struktur Data <script>alert(1)</script>",
    description: "Diskusi Binary Tree",
    learning_goal: "UNDERSTAND",
    collaboration_style: "DISCUSSION",
    learning_mode: "ONLINE",
    location: "Google Meet",
    min_group_size: 2,
    max_group_size: 4,
    status: "CONFIRMED",
    course: { course_id: "crs-1", course_code: "ACK2AAB3", course_name: "Struktur Data" },
    slots: [
      { slot_id: "sl-1", session_id: "SESS-100", session_date: "2026-11-20", start_time: "09:00", end_time: "11:00", status: "APPROVED" },
      { slot_id: "sl-2", session_id: "SESS-100", session_date: "2026-11-21", start_time: "14:00", end_time: "16:00", status: "PROPOSED" },
    ],
    members: [
      {
        member_id: "m-1",
        session_id: "SESS-100",
        student_id: "stu-host",
        intent_id: "SECRET-INTENT-HOST-001",
        role: "HOST",
        status: "CONFIRMED",
        student: { student_id: "stu-host", full_name: "Andi Pratama", email: "andi@secret.edu", student_number: "1201250001" },
      },
      {
        member_id: "m-2",
        session_id: "SESS-100",
        student_id: "stu-mem",
        intent_id: "SECRET-INTENT-MEM-002",
        role: "MEMBER",
        status: "CONFIRMED",
        student: { student_id: "stu-mem", full_name: "Budi <b>Santoso</b>", email: "budi@secret.edu", student_number: "1201250002" },
      },
      {
        member_id: "m-3",
        session_id: "SESS-100",
        student_id: "stu-acc",
        intent_id: "SECRET-INTENT-ACC-003",
        role: "MEMBER",
        status: "ACCEPTED",
        student: { student_id: "stu-acc", full_name: "Eka Wijaya", email: "eka@secret.edu", student_number: "1201250003" },
      },
    ],
    ...overrides,
  };
}

// ==============================================================================
// 1. STATIC CONTRACT & HTML/CSS STRUCTURE VERIFICATION
// ==============================================================================
test("23.1–23.3: HTML & CSS pages contain required Day 23 containers and dashboard entry", () => {
  assert.match(DASHBOARD_HTML, /href="sessions\.html"/);
  assert.match(SESSIONS_HTML, /id="sessionsPageRoot"/);
  assert.match(SESSIONS_HTML, /id="sessionStatusFilterBar"/);
  assert.match(SESSIONS_HTML, /data-status="CONFIRMED"/);
  assert.match(SESSIONS_HTML, /data-status="COMPLETED"/);
  assert.match(SESSIONS_HTML, /data-status="CANCELLED"/);
  assert.match(SESSIONS_HTML, /data-status="EXPIRED"/);
  assert.match(DETAIL_HTML, /id="sessionDetailPageRoot"/);
  assert.match(DETAIL_HTML, /id="confirmActionModal"/);
  assert.match(SESSIONS_CSS, /\.sessions-header/);
  assert.match(SESSIONS_CSS, /\.confirm-modal-backdrop/);
  assert.match(SESSIONS_CSS, /@media \(max-width: 359px\)/);
});

// ==============================================================================
// 2. API HELPER ERROR STATUS, NETWORK ERROR & ENDPOINT CONTRACT (Day 23.1)
// ==============================================================================
test("23.1: app.request preserves HTTP status, payload, endpoint, 422 array & network error flag", async () => {
  const calls = [];
  const env = bootAppSandbox({
    fetchImpl: async (url, opts) => {
      calls.push({ url, opts });
      if (url.endsWith("/403")) return { ok: false, status: 403, json: async () => ({ detail: "Akses ditolak" }) };
      if (url.endsWith("/422")) return { ok: false, status: 422, json: async () => ({ detail: [{ msg: "Field invalid" }] }) };
      if (url.endsWith("/net")) throw new TypeError("Failed to fetch");
      return { ok: true, status: 200, json: async () => ({ ok: true }) };
    },
  });

  env.app.setAuth("tok-123", { student_id: "stu-host", full_name: "Andi" });

  await assert.rejects(() => env.app.request("/403"), (err) => {
    assert.equal(err.status, 403);
    assert.equal(err.endpoint, "/403");
    assert.equal(err.isNetworkError, false);
    assert.equal(err.data.detail, "Akses ditolak");
    return true;
  });

  await assert.rejects(() => env.app.request("/422"), (err) => {
    assert.equal(err.status, 422);
    assert.equal(err.message, "Field invalid");
    return true;
  });

  await assert.rejects(() => env.app.request("/net"), (err) => {
    assert.equal(err.status, 0);
    assert.equal(err.isNetworkError, true);
    return true;
  });

  // Verify all 6 frozen Day 21-22 endpoints
  await env.app.sessions.listMySessions("CONFIRMED");
  await env.app.sessions.getDetail("SESS-1");
  await env.app.sessions.complete("SESS-1");
  await env.app.sessions.cancel("SESS-1");
  await env.app.sessions.withdraw("SESS-1");
  await env.app.sessions.removeMember("SESS-1", "stu-2");

  const sessionCalls = calls.slice(3).map((c) => `${c.opts.method} ${c.url}`);
  assert.deepEqual(sessionCalls, [
    "GET /api/v1/sessions/my-sessions?status=CONFIRMED",
    "GET /api/v1/sessions/SESS-1",
    "POST /api/v1/sessions/SESS-1/complete",
    "POST /api/v1/sessions/SESS-1/cancel",
    "POST /api/v1/sessions/SESS-1/withdraw",
    "POST /api/v1/sessions/SESS-1/members/stu-2/remove",
  ]);
  assert.equal(calls[3].opts.headers.Authorization, "Bearer tok-123");
});

// ==============================================================================
// 3. PRIVACY, XSS SAFETY & BUTTON VISIBILITY MATRIX (Day 23.3 & 23.4)
// ==============================================================================
test("23.3–23.4: Privacy (no intent_id/email/NIM), role visibility matrix & Quorum Option A", () => {
  const baseIds = ["sessionDetailContent", "detailAlertContainer", "detailHeaderSub", "btnRefreshDetail"];

  // Case A: HOST + CONFIRMED -> Complete, Cancel, Remove (only for CONFIRMED non-host Budi, NOT ACCEPTED Eka, NOT Host)
  const hostEnv = bootAppSandbox({ elementIds: baseIds });
  hostEnv.sessionDetailState.user = { student_id: "stu-host", full_name: "Andi Pratama" };
  hostEnv.renderSessionDetail(makeSampleSession());
  const content = hostEnv.document.getElementById("sessionDetailContent");
  const fullText = content.textContent;

  // Strict privacy: never render intent_id, email, or NIM
  assert.doesNotMatch(fullText, /SECRET-INTENT-/);
  assert.doesNotMatch(fullText, /@secret\.edu/);
  assert.doesNotMatch(fullText, /120125000/);

  // Complete & Cancel visible, Withdraw NOT visible
  assert.ok(content.querySelector("#btnCompleteSession"));
  assert.ok(content.querySelector("#btnCancelSession"));
  assert.equal(content.querySelector("#btnWithdrawSession"), null);
  const removeBtns = content.querySelectorAll('button[data-lifecycle-action="remove"]');
  assert.equal(removeBtns.length, 1);
  assert.equal(removeBtns[0].dataset.targetStudentId, "stu-mem");

  // Case B: HOST + COMPLETED -> zero mutation buttons
  hostEnv.renderSessionDetail(makeSampleSession({ status: "COMPLETED" }));
  assert.equal(content.querySelectorAll("button[data-lifecycle-action]").length, 0);

  // Case C: HOST + CANCELLED -> zero mutation buttons
  hostEnv.renderSessionDetail(makeSampleSession({ status: "CANCELLED" }));
  assert.equal(content.querySelectorAll("button[data-lifecycle-action]").length, 0);

  // Case D: MEMBER CONFIRMED + CONFIRMED -> ONLY Withdraw visible
  const memEnv = bootAppSandbox({ elementIds: baseIds });
  memEnv.sessionDetailState.user = { student_id: "stu-mem", full_name: "Budi Santoso" };
  memEnv.renderSessionDetail(makeSampleSession());
  const memContent = memEnv.document.getElementById("sessionDetailContent");
  assert.ok(memContent.querySelector("#btnWithdrawSession"));
  assert.equal(memContent.querySelector("#btnCompleteSession"), null);
  assert.equal(memContent.querySelector("#btnCancelSession"), null);
  assert.equal(memContent.querySelectorAll('button[data-lifecycle-action="remove"]').length, 0);

  // Case E: MEMBER ACCEPTED + CONFIRMED -> Withdraw NOT visible (per Day 22 backend rule)
  const accEnv = bootAppSandbox({ elementIds: baseIds });
  accEnv.sessionDetailState.user = { student_id: "stu-acc", full_name: "Eka Wijaya" };
  accEnv.renderSessionDetail(makeSampleSession());
  const accContent = accEnv.document.getElementById("sessionDetailContent");
  assert.equal(accContent.querySelectorAll("button[data-lifecycle-action]").length, 0);

  // Case F: Quorum Option A -> confirmed members < min_group_size shows info, keeps status CONFIRMED
  const quorumSession = makeSampleSession({
    min_group_size: 2,
    members: [
      { member_id: "m-1", session_id: "SESS-100", student_id: "stu-host", role: "HOST", status: "CONFIRMED", student: { full_name: "Andi Pratama" } },
      { member_id: "m-2", session_id: "SESS-100", student_id: "stu-mem", role: "MEMBER", status: "WITHDRAWN", student: { full_name: "Budi Santoso" } },
    ],
  });
  hostEnv.renderSessionDetail(quorumSession);
  assert.match(content.textContent, /di bawah batas minimum grup/i);
  assert.match(content.textContent, /Terkonfirmasi/);
});

// ==============================================================================
// 4. WITHDRAW MINIMAL RESPONSE PRIVACY, 403 TOKEN PRESERVATION & 409 CONFLICT RECOVERY (Day 23.4–23.5)
// ==============================================================================
test("23.4–23.5: Withdraw minimal response clears detail state and redirects without rendering StudySessionResponse", async () => {
  const env = bootAppSandbox({
    search: "?id=SESS-100",
    elementIds: ["sessionDetailContent", "detailAlertContainer", "detailHeaderSub", "btnRefreshDetail"],
    fetchImpl: async (url) => {
      if (url.endsWith("/withdraw")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ session_id: "SESS-100", session_status: "CONFIRMED", membership_status: "WITHDRAWN" }),
        };
      }
      return { ok: true, status: 200, json: async () => makeSampleSession() };
    },
  });

  env.app.setAuth("tok-mem", { student_id: "stu-mem", full_name: "Budi Santoso" });
  env.sessionDetailState.user = { student_id: "stu-mem", full_name: "Budi Santoso" };
  env.sessionDetailState.sessionId = "SESS-100";
  env.sessionDetailState.session = makeSampleSession();

  await env.executeWithdrawSessionAction("SESS-100", null);

  assert.equal(env.sessionDetailState.session, null);
  const contentText = env.document.getElementById("sessionDetailContent").textContent;
  assert.match(contentText, /Berhasil Mengundurkan Diri/);
  assert.doesNotMatch(contentText, /Google Meet/);
  assert.ok(env.sessionStorage.getItem(env.SESSION_FLASH_KEY));

  // Execute redirect timer
  assert.equal(env.timers.length, 1);
  env.timers[0].fn();
  assert.deepEqual(env.navHistory, [{ type: "replace", url: "sessions.html" }]);
});

test("23.5: HTTP 403 preserves auth token; HTTP 401 clears auth & redirects; HTTP 409 refreshes without auto-retry", async () => {
  // 1) HTTP 403 must NOT clear token
  const env403 = bootAppSandbox({
    search: "?id=SESS-100",
    elementIds: ["sessionDetailContent", "detailAlertContainer", "detailHeaderSub", "btnRefreshDetail"],
    fetchImpl: async () => ({ ok: false, status: 403, json: async () => ({ detail: "Bukan anggota aktif" }) }),
  });
  env403.app.setAuth("valid-token-keep", { student_id: "stu-doni", full_name: "Doni" });
  env403.sessionDetailState.user = { student_id: "stu-doni", full_name: "Doni" };
  env403.sessionDetailState.sessionId = "SESS-100";
  await env403.loadSessionDetail();
  assert.equal(env403.app.getToken(), "valid-token-keep");
  assert.equal(env403.navHistory.length, 0);
  assert.match(env403.document.getElementById("sessionDetailContent").textContent, /Akses Ditolak/);

  // 2) HTTP 401 MUST clear token and redirect to login.html
  const env401 = bootAppSandbox({
    search: "?id=SESS-100",
    elementIds: ["sessionDetailContent", "detailAlertContainer", "detailHeaderSub", "btnRefreshDetail"],
    fetchImpl: async () => ({ ok: false, status: 401, json: async () => ({ detail: "Token kedaluwarsa" }) }),
  });
  env401.app.setAuth("expired-token", { student_id: "stu-host", full_name: "Andi" });
  env401.sessionDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  env401.sessionDetailState.sessionId = "SESS-100";
  await env401.loadSessionDetail();
  assert.equal(env401.app.getToken(), null);
  assert.deepEqual(env401.navHistory, [{ type: "replace", url: "login.html" }]);

  // 3) HTTP 409 on Cancel triggers single GET refresh and never auto-retries POST /cancel
  const hitLog = [];
  const env409 = bootAppSandbox({
    search: "?id=SESS-100",
    elementIds: ["sessionDetailContent", "detailAlertContainer", "detailHeaderSub", "btnRefreshDetail"],
    fetchImpl: async (url, opts) => {
      hitLog.push(`${opts.method} ${url}`);
      if (url.endsWith("/cancel")) {
        return { ok: false, status: 409, json: async () => ({ detail: "Sesi sudah COMPLETED" }) };
      }
      return { ok: true, status: 200, json: async () => makeSampleSession({ status: "COMPLETED" }) };
    },
  });
  env409.app.setAuth("tok-host", { student_id: "stu-host", full_name: "Andi" });
  env409.sessionDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  env409.sessionDetailState.sessionId = "SESS-100";
  await env409.executeCancelSessionAction("SESS-100", null);
  assert.deepEqual(hitLog, ["POST /api/v1/sessions/SESS-100/cancel", "GET /api/v1/sessions/SESS-100"]);
  assert.equal(env409.sessionDetailState.session.status, "COMPLETED");
  assert.match(env409.document.getElementById("detailAlertContainer").textContent, /Sesi sudah COMPLETED/);
});

test("23.5: Double-submit protection blocks concurrent mutations, 500 sanitizes error & 409->403 keeps token", async () => {
  // 1) Double-submit protection: second call while first is in-flight is ignored
  let completeCount = 0;
  let releaseFirst;
  const firstGate = new Promise((resolve) => {
    releaseFirst = resolve;
  });

  const envDs = bootAppSandbox({
    search: "?id=SESS-100",
    elementIds: ["sessionDetailContent", "detailAlertContainer", "detailHeaderSub", "btnRefreshDetail"],
    fetchImpl: async () => {
      completeCount += 1;
      await firstGate;
      return { ok: true, status: 200, json: async () => makeSampleSession({ status: "COMPLETED" }) };
    },
  });
  envDs.app.setAuth("tok-host", { student_id: "stu-host", full_name: "Andi" });
  envDs.sessionDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  envDs.sessionDetailState.sessionId = "SESS-100";

  const p1 = envDs.executeCompleteSessionAction("SESS-100", null);
  const p2 = envDs.executeCompleteSessionAction("SESS-100", null); // must be blocked by isActionPending
  releaseFirst();
  await Promise.all([p1, p2]);
  assert.equal(completeCount, 1);
  assert.equal(envDs.sessionDetailState.isActionPending, false);

  // 2) HTTP 500 displays generic message without leaking raw server error
  const env500 = bootAppSandbox({
    search: "?id=SESS-100",
    elementIds: ["sessionDetailContent", "detailAlertContainer", "detailHeaderSub", "btnRefreshDetail"],
    fetchImpl: async () => ({ ok: false, status: 500, json: async () => ({ detail: "SQLITE_INTERNAL_STACK_TRACE" }) }),
  });
  env500.app.setAuth("tok-host", { student_id: "stu-host", full_name: "Andi" });
  env500.sessionDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  env500.sessionDetailState.sessionId = "SESS-100";
  await env500.executeCompleteSessionAction("SESS-100", null);
  const alert500 = env500.document.getElementById("detailAlertContainer").textContent;
  assert.match(alert500, /Terjadi kesalahan pada server/i);
  assert.doesNotMatch(alert500, /SQLITE_INTERNAL_STACK_TRACE/);

  // 3) Concurrent withdraw vs remove: 409 refresh gets 403 -> transitions to Access Denied without clearing token
  const env409To403 = bootAppSandbox({
    search: "?id=SESS-100",
    elementIds: ["sessionDetailContent", "detailAlertContainer", "detailHeaderSub", "btnRefreshDetail"],
    fetchImpl: async (url) => {
      if (url.endsWith("/withdraw")) {
        return { ok: false, status: 409, json: async () => ({ detail: "Keanggotaan sudah REMOVED" }) };
      }
      return { ok: false, status: 403, json: async () => ({ detail: "Akses detail dicabut" }) };
    },
  });
  env409To403.app.setAuth("tok-mem-valid", { student_id: "stu-mem", full_name: "Budi" });
  env409To403.sessionDetailState.user = { student_id: "stu-mem", full_name: "Budi" };
  env409To403.sessionDetailState.sessionId = "SESS-100";
  await env409To403.executeWithdrawSessionAction("SESS-100", null);
  assert.equal(env409To403.app.getToken(), "tok-mem-valid");
  assert.match(env409To403.document.getElementById("sessionDetailContent").textContent, /Akses Ditolak/);
});


