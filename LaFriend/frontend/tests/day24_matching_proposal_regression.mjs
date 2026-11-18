// ==============================================================================
// day24_matching_proposal_regression.mjs
// Automated Frontend Matching, Invitations, Proposal & Execution Regression Suite
// (Node built-in test runner: `node --test LaFriend/frontend/tests/day24_matching_proposal_regression.mjs`)
// Covers Layer 1 (11 API Contracts) & Layer 2 (Full State Machine, Privacy, Timeout & Race UI).
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

const APP_JS = fs.readFileSync(path.join(FRONTEND_DIR, "js", "app.js"), "utf8");
const MATCHING_JS = fs.readFileSync(path.join(FRONTEND_DIR, "js", "matching.js"), "utf8");
const INVITATIONS_JS = fs.readFileSync(path.join(FRONTEND_DIR, "js", "invitations.js"), "utf8");
const PROPOSAL_DETAIL_JS = fs.readFileSync(path.join(FRONTEND_DIR, "js", "proposal-detail.js"), "utf8");

const DASHBOARD_HTML = fs.readFileSync(path.join(FRONTEND_DIR, "dashboard.html"), "utf8");
const MATCHING_HTML = fs.readFileSync(path.join(FRONTEND_DIR, "matching.html"), "utf8");
const INVITATIONS_HTML = fs.readFileSync(path.join(FRONTEND_DIR, "invitations.html"), "utf8");
const PROPOSAL_DETAIL_HTML = fs.readFileSync(path.join(FRONTEND_DIR, "proposal-detail.html"), "utf8");
const MATCHING_CSS = fs.readFileSync(path.join(FRONTEND_DIR, "css", "matching.css"), "utf8");

// Lightweight DOM & Browser Sandbox
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
    this.style = {};
    this.children = [];
    this.childNodes = this.children;
    this.parentNode = null;
    this._textContent = "";
    this.disabled = false;
    this.href = "";
    this.type = "";
    this.value = "";
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

function bootDay24Sandbox({ pageScript = "", search = "", fetchImpl, elementIds = [], inputValues = {} }) {
  const elementsById = new Map();
  const root = new FakeElement("body");
  elementIds.forEach((id) => {
    const el = new FakeElement(id.startsWith("input") ? "input" : "div");
    el.id = id;
    if (id in inputValues) el.value = inputValues[id];
    elementsById.set(id, el);
    root.appendChild(el);
  });

  const navHistory = [];
  const localStorage = createStorage();
  const sessionStorage = createStorage();

  const document = {
    addEventListener() {},
    removeEventListener() {},
    getElementById: (id) => (elementsById.has(id) ? elementsById.get(id) : root.querySelector(`#${id}`)),
    querySelectorAll: (sel) => root.querySelectorAll(sel),
    querySelector: (sel) => root.querySelector(sel),
    createElement: (tag) => new FakeElement(tag),
    createDocumentFragment: () => new FakeElement("#FRAGMENT"),
  };

  const windowObj = {
    location: {
      search,
      _href: `http://localhost/page.html${search}`,
      get href() {
        return this._href;
      },
      set href(url) {
        navHistory.push({ type: "href", url });
        this._href = url;
      },
      replace(url) {
        navHistory.push({ type: "replace", url });
        this._href = url;
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
  vm.runInContext(APP_JS, sandbox);
  if (pageScript) {
    vm.runInContext(pageScript, sandbox);
  }
  vm.runInContext(
    `;globalThis.__exports = {
      app,
      matchingPageState: typeof matchingPageState !== "undefined" ? matchingPageState : null,
      loadUserActiveIntents: typeof loadUserActiveIntents !== "undefined" ? loadUserActiveIntents : null,
      runMatchingPreview: typeof runMatchingPreview !== "undefined" ? runMatchingPreview : null,
      renderMatchingPreviewResult: typeof renderMatchingPreviewResult !== "undefined" ? renderMatchingPreviewResult : null,
      executeCreateProposal: typeof executeCreateProposal !== "undefined" ? executeCreateProposal : null,
      invitationsPageState: typeof invitationsPageState !== "undefined" ? invitationsPageState : null,
      loadCurrentInvitationsTab: typeof loadCurrentInvitationsTab !== "undefined" ? loadCurrentInvitationsTab : null,
      renderInboxList: typeof renderInboxList !== "undefined" ? renderInboxList : null,
      renderSentGroupedList: typeof renderSentGroupedList !== "undefined" ? renderSentGroupedList : null,
      executeInvitationResponse: typeof executeInvitationResponse !== "undefined" ? executeInvitationResponse : null,
      proposalDetailState: typeof proposalDetailState !== "undefined" ? proposalDetailState : null,
      loadProposalDetail: typeof loadProposalDetail !== "undefined" ? loadProposalDetail : null,
      renderProposalDetail: typeof renderProposalDetail !== "undefined" ? renderProposalDetail : null,
      executeFinalizeProposalAction: typeof executeFinalizeProposalAction !== "undefined" ? executeFinalizeProposalAction : null,
      executeCancelProposalAction: typeof executeCancelProposalAction !== "undefined" ? executeCancelProposalAction : null,
      executeCreateSessionFromProposalAction: typeof executeCreateSessionFromProposalAction !== "undefined" ? executeCreateSessionFromProposalAction : null,
    };`,
    sandbox
  );

  return { ...sandbox.__exports, document, window: windowObj, localStorage, sessionStorage, navHistory, timers };
}

function samplePreviewReady(overrides = {}) {
  return {
    host_intent_id: "SECRET-INTENT-HOST-1",
    course_id: "crs-sd",
    course_name: "Struktur Data",
    formation_status: "READY",
    group_size: 2,
    min_group_size_bound: 2,
    max_group_size_bound: 4,
    group_quality_score: 88.5,
    average_pair_score: 88.5,
    minimum_pair_score: 88.5,
    members: [
      {
        student_id: "SECRET-STU-HOST",
        student_name: "Andi Pratama",
        intent_id: "SECRET-INTENT-HOST-1",
        role: "HOST",
        study_program: "S1 Teknik Komputer",
        academic_year: 2025,
        learning_goal: "UNDERSTAND",
        collaboration_style: "DISCUSSION",
        min_group_size: 2,
        max_group_size: 4,
      },
      {
        student_id: "SECRET-STU-BUDI",
        student_name: "Budi <script>alert(1)</script>",
        intent_id: "SECRET-INTENT-BUDI-2",
        role: "MEMBER",
        study_program: "S1 Teknik Komputer",
        academic_year: 2025,
        learning_goal: "UNDERSTAND",
        collaboration_style: "DISCUSSION",
        min_group_size: 2,
        max_group_size: 4,
      },
    ],
    pairwise_scores: [
      {
        student_a_id: "SECRET-STU-HOST",
        student_b_id: "SECRET-STU-BUDI",
        intent_a_id: "SECRET-INTENT-HOST-1",
        intent_b_id: "SECRET-INTENT-BUDI-2",
        compatibility_score: 88.5,
        breakdown: {
          topic: { score: 90, weight: 0.35, contribution: 31.5, raw_contribution: 31.5, base_contribution: 31.5, rounding_adjustment: 0 },
          goal: { score: 100, weight: 0.25, contribution: 25, raw_contribution: 25, base_contribution: 25, rounding_adjustment: 0 },
          style: { score: 100, weight: 0.15, contribution: 15, raw_contribution: 15, base_contribution: 15, rounding_adjustment: 0 },
          date: { score: 85, weight: 0.15, contribution: 12.75, raw_contribution: 12.75, base_contribution: 12.75, rounding_adjustment: 0 },
          mode: { score: 100, weight: 0.1, contribution: 10, raw_contribution: 10, base_contribution: 10, rounding_adjustment: 0 },
        },
        explanation: "Topik dan jadwal sangat cocok",
      },
    ],
    schedule_options: [
      { date: "2026-11-20", start_time: "09:00", end_time: "11:00", duration_minutes: 120 },
    ],
    selected_schedule: { date: "2026-11-20", start_time: "09:00", end_time: "11:00", duration_minutes: 120 },
    candidate_pruning_stats: {
      total_candidates_examined: 5,
      candidates_pruned_hard_constraints: 1,
      candidates_pruned_min_score: 1,
      candidates_pruned_top_k: 0,
      candidates_in_pool: 3,
    },
    message: "Kelompok siap dibentuk.",
    ...overrides,
  };
}

function sampleProposal(overrides = {}) {
  return {
    proposal_id: "PROP-24-001",
    host_intent_id: "SECRET-INTENT-HOST-1",
    host_student_id: "stu-host",
    course_id: "crs-sd",
    status: "PENDING_RESPONSES",
    min_group_size_bound: 2,
    max_group_size_bound: 4,
    group_quality_score: 88.5,
    average_pair_score: 88.5,
    minimum_pair_score: 88.5,
    selected_schedule: { date: "2026-11-20", start_time: "09:00", end_time: "11:00", duration_minutes: 120 },
    message: "Yuk belajar bareng!",
    expires_at: "2026-11-25T10:00:00Z",
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    finalized_at: null,
    active_member_count: 1,
    quorum_reached: false,
    session_id: null,
    host_student: {
      student_id: "stu-host",
      full_name: "Andi Pratama",
      email: "andi@secret.edu",
      student_number: "1201250001",
      study_program: "S1 Teknik Komputer",
      academic_year: 2025,
    },
    invitations: [
      {
        invitation_id: "INV-24-001",
        invitation_type: "PARTNER_INVITE",
        sender_id: "stu-host",
        recipient_id: "stu-budi",
        target_intent_id: "SECRET-INTENT-BUDI-2",
        proposal_id: "PROP-24-001",
        status: "PENDING",
        message: "Yuk belajar bareng!",
        created_at: "2026-11-18T10:00:00Z",
        recipient: {
          student_id: "stu-budi",
          full_name: "Budi Santoso",
          email: "budi@secret.edu",
          student_number: "1201250002",
          study_program: "S1 Teknik Komputer",
          academic_year: 2025,
        },
      },
    ],
    ...overrides,
  };
}

// ==============================================================================
// 1. STATIC HTML & CSS CONTRACT VERIFICATION
// ==============================================================================
test("24.0–24.3: HTML/CSS pages contain Day 24 containers, dashboard entries & honest Sent tab labeling", () => {
  assert.match(DASHBOARD_HTML, /href="matching\.html"/);
  assert.match(DASHBOARD_HTML, /href="invitations\.html"/);
  assert.match(MATCHING_HTML, /id="matchingPageRoot"/);
  assert.match(MATCHING_HTML, /src="js\/matching\.js/);
  assert.match(INVITATIONS_HTML, /id="invitationsPageRoot"/);
  assert.match(INVITATIONS_HTML, /Undangan Terkirim/);
  assert.doesNotMatch(INVITATIONS_HTML, /Semua Proposal Saya/i);
  assert.match(PROPOSAL_DETAIL_HTML, /id="proposalDetailPageRoot"/);
  assert.match(PROPOSAL_DETAIL_HTML, /id="confirmActionModal"/);
  assert.match(MATCHING_CSS, /@media \(max-width: 359px\)/);
});

// ==============================================================================
// 2. LAYER 1: ALL 11 CANONICAL API WRAPPERS CONTRACT VERIFICATION
// ==============================================================================
test("24.1–24.3 Layer 1: All 11 canonical Day 24 API wrappers match exact HTTP method, path, payload & Bearer token", async () => {
  const calls = [];
  const env = bootDay24Sandbox({
    fetchImpl: async (url, opts) => {
      calls.push({ url, method: opts.method, body: opts.body ? JSON.parse(opts.body) : null, auth: opts.headers.Authorization });
      return { ok: true, status: 200, json: async () => ({ ok: true }) };
    },
  });

  env.app.setAuth("tok-d24", { student_id: "stu-host", full_name: "Andi" });

  await env.app.studyIntents.list();
  await env.app.courses.getDetail("crs-1");
  await env.app.matching.preview({ host_intent_id: "int-1", min_score: 60, target_group_size: null, max_candidate_pool: 20 });
  await env.app.proposals.create({ host_intent_id: "int-1", min_score: 60, target_group_size: null, max_candidate_pool: 20, message: "Hi", duration_hours: 24 });
  await env.app.proposals.getDetail("prop-1");
  await env.app.invitations.getInbox("PENDING");
  await env.app.invitations.getSent("");
  await env.app.invitations.respond("inv-1", { decision: "ACCEPT" });
  await env.app.proposals.finalize("prop-1");
  await env.app.proposals.cancel("prop-1", { reason: "Batal" });
  await env.app.proposals.executeSession("prop-1");

  assert.deepEqual(
    calls.map((c) => `${c.method} ${c.url}`),
    [
      "GET /api/v1/study-intents",
      "GET /api/v1/courses/crs-1",
      "POST /api/v1/matching/group-proposals/preview",
      "POST /api/v1/group-proposals",
      "GET /api/v1/group-proposals/prop-1",
      "GET /api/v1/invitations/inbox?status=PENDING",
      "GET /api/v1/invitations/sent",
      "POST /api/v1/invitations/inv-1/respond",
      "POST /api/v1/group-proposals/prop-1/finalize",
      "POST /api/v1/group-proposals/prop-1/cancel",
      "POST /api/v1/sessions/from-proposal/prop-1",
    ]
  );
  calls.forEach((c) => assert.equal(c.auth, "Bearer tok-d24"));
});

// ==============================================================================
// 3. DAY 24.1: MATCHING PREVIEW, ACTIVE FILTER, READ-ONLY SCHEDULE & CREATE SEPARATION
// ==============================================================================
test("24.1: Active intent filtering, 3 formation statuses, read-only schedule, privacy & preview-vs-create separation", async () => {
  const createBodies = [];
  const env = bootDay24Sandbox({
    pageScript: MATCHING_JS,
    search: "?intent_id=FOREIGN-OR-MATCHED-ID",
    elementIds: [
      "matchingAlertContainer",
      "matchingIntentsContainer",
      "activeIntentsCountBadge",
      "previewParamsSection",
      "previewResultContainer",
      "inputMinScore",
      "inputTargetGroupSize",
      "inputMaxCandidatePool",
      "btnRunPreview",
    ],
    inputValues: { inputMinScore: "60", inputTargetGroupSize: "", inputMaxCandidatePool: "20" },
    fetchImpl: async (url, opts) => {
      if (url.endsWith("/study-intents")) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            { intent_id: "INT-MATCHED", status: "MATCHED", topics: "Old", min_group_size: 2, max_group_size: 4 },
            { intent_id: "INT-ACTIVE-1", status: "ACTIVE", topics: "Binary Tree", min_group_size: 2, max_group_size: 4, course: { course_code: "ACK2AAB3", course_name: "Struktur Data" }, availabilities: [] },
          ],
        };
      }
      if (url.endsWith("/group-proposals")) {
        createBodies.push(JSON.parse(opts.body));
        return { ok: true, status: 201, json: async () => sampleProposal({ proposal_id: "PROP-NEW-201" }) };
      }
      return { ok: true, status: 200, json: async () => samplePreviewReady() };
    },
  });

  env.app.setAuth("tok-host", { student_id: "SECRET-STU-HOST", full_name: "Andi Pratama" });
  env.matchingPageState.user = { student_id: "SECRET-STU-HOST", full_name: "Andi Pratama" };

  await env.loadUserActiveIntents();
  // Non-ACTIVE filtered out & foreign ?intent_id ignored -> selects own ACTIVE intent only
  assert.equal(env.matchingPageState.activeIntents.length, 1);
  assert.equal(env.matchingPageState.selectedIntentId, "INT-ACTIVE-1");

  const resBox = env.document.getElementById("previewResultContainer");

  // READY renders scores, read-only schedule, Create button, and ZERO leaked IDs
  env.renderMatchingPreviewResult(resBox, samplePreviewReady());
  assert.ok(resBox.querySelector("#btnCreateProposal"));
  assert.equal(resBox.querySelectorAll('input[type="radio"]').length, 0); // schedule strictly read-only
  assert.doesNotMatch(resBox.textContent, /SECRET-INTENT-/);
  assert.doesNotMatch(resBox.textContent, /SECRET-STU-/);

  // INSUFFICIENT_MEMBERS & NO_COMPATIBLE_GROUP hide Create Proposal button
  env.renderMatchingPreviewResult(resBox, samplePreviewReady({ formation_status: "INSUFFICIENT_MEMBERS", message: "Kurang anggota" }));
  assert.equal(resBox.querySelector("#btnCreateProposal"), null);
  assert.match(resBox.textContent, /Kurang anggota/);

  env.renderMatchingPreviewResult(resBox, samplePreviewReady({ formation_status: "NO_COMPATIBLE_GROUP", message: "Tidak cocok" }));
  assert.equal(resBox.querySelector("#btnCreateProposal"), null);
  assert.match(resBox.textContent, /Tidak cocok/);

  // Create sends ONLY GroupProposalCreateRequest parameters (never preview members/scores/schedule) and redirects on 201
  await env.executeCreateProposal(
    { host_intent_id: "INT-ACTIVE-1", min_score: 60, target_group_size: null, max_candidate_pool: 20, message: "Ayo!", duration_hours: 24 },
    null
  );
  assert.equal(createBodies.length, 1);
  assert.deepEqual(Object.keys(createBodies[0]).sort(), [
    "duration_hours",
    "host_intent_id",
    "max_candidate_pool",
    "message",
    "min_score",
    "target_group_size",
  ]);
  assert.deepEqual(env.navHistory, [{ type: "href", url: "proposal-detail.html?id=PROP-NEW-201" }]);
});

// ==============================================================================
// 4. DAY 24.2: INVITATIONS INBOX, DECLINE->REJECTED, SENT GROUPING & PRIVACY
// ==============================================================================
test("24.2: Invitations inbox buttons only for PENDING, DECLINE->REJECTED mapping, Sent grouping & strict privacy", async () => {
  const env = bootDay24Sandbox({
    pageScript: INVITATIONS_JS,
    elementIds: ["invitationsAlertContainer", "invitationsListContainer", "invitationsCountPill", "btnRefreshInvitations"],
    fetchImpl: async (url) => {
      if (url.endsWith("/respond")) {
        return { ok: true, status: 200, json: async () => ({ invitation_id: "INV-1", status: "REJECTED" }) };
      }
      return { ok: true, status: 200, json: async () => [] };
    },
  });

  env.invitationsPageState.inboxItems = [
    {
      invitation_id: "INV-1",
      proposal_id: "PROP-1",
      status: "PENDING",
      message: "Gabung yuk",
      created_at: "2026-11-18T10:00:00Z",
      sender: { student_id: "SECRET-S1", full_name: "Andi Host", email: "andi@secret.edu", student_number: "1201250001", study_program: "Teknik Komputer", academic_year: 2025 },
    },
    {
      invitation_id: "INV-2",
      proposal_id: "PROP-2",
      status: "REJECTED",
      created_at: "2026-11-18T09:00:00Z",
      sender: { student_id: "SECRET-S2", full_name: "Citra Host", email: "citra@secret.edu", student_number: "1201250003" },
    },
  ];

  env.invitationsPageState.proposalStatusById = {
    "PROP-1": { status: "PENDING_RESPONSES", sessionId: null },
  };
  env.renderInboxList();
  const listBox = env.document.getElementById("invitationsListContainer");
  assert.equal(listBox.querySelectorAll('button[data-inv-action="accept"]').length, 1);
  assert.equal(listBox.querySelectorAll('button[data-inv-action="decline"]').length, 1);
  assert.match(listBox.textContent, /Ditolak/);
  assert.doesNotMatch(listBox.textContent, /@secret\.edu/);
  assert.doesNotMatch(listBox.textContent, /120125000/);
  assert.doesNotMatch(listBox.textContent, /SECRET-S/);

  // Sent tab groups multiple recipients under same proposal_id without leaking sensitive fields
  env.invitationsPageState.sentItems = [
    { invitation_id: "S-1", proposal_id: "PROP-9", status: "ACCEPTED", created_at: "2026-11-18T10:00:00Z", recipient: { full_name: "Budi", email: "budi@secret.edu", student_number: "1201250002" } },
    { invitation_id: "S-2", proposal_id: "PROP-9", status: "PENDING", created_at: "2026-11-18T10:00:00Z", recipient: { full_name: "Citra", email: "citra@secret.edu", student_number: "1201250003" } },
  ];
  env.renderSentGroupedList();
  assert.equal(listBox.querySelectorAll("article").length, 1); // 2 invitations grouped under 1 proposal card
  assert.match(listBox.textContent, /Diterima: 1/);
  assert.match(listBox.textContent, /Menunggu: 1/);
  assert.doesNotMatch(listBox.textContent, /@secret\.edu/);
});

// ==============================================================================
// 4B. DAY 24.5: INBOX TERMINAL-STATE SYNC (PENDING + NOT_FORMED/CANCELLED/EXPIRED) & DEDUP
// ==============================================================================
test("24.5: Inbox deduplicates proposal detail fetches & hides Accept/Decline for PENDING on NOT_FORMED/terminal proposals", async () => {
  const proposalDetailCalls = [];
  const env = bootDay24Sandbox({
    pageScript: INVITATIONS_JS,
    elementIds: ["invitationsAlertContainer", "invitationsListContainer", "invitationsCountPill", "btnRefreshInvitations"],
    fetchImpl: async (url) => {
      if (url.endsWith("/invitations/inbox")) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            // Dua item PENDING pada proposal NOT_FORMED yang sama -> wajib deduplikasi 1x GET detail
            { invitation_id: "INV-NF-1", proposal_id: "PROP-NOT-FORMED", status: "PENDING", created_at: "2026-11-18T10:00:00Z", sender: { full_name: "Host A" } },
            { invitation_id: "INV-NF-2", proposal_id: "PROP-NOT-FORMED", status: "PENDING", created_at: "2026-11-18T10:01:00Z", sender: { full_name: "Host A" } },
            // PENDING pada proposal CANCELLED -> read-only
            { invitation_id: "INV-CANC", proposal_id: "PROP-CANCELLED", status: "PENDING", created_at: "2026-11-18T09:50:00Z", sender: { full_name: "Host B" } },
            // PENDING pada proposal EXPIRED -> read-only
            { invitation_id: "INV-EXP", proposal_id: "PROP-EXPIRED", status: "PENDING", created_at: "2026-11-18T09:40:00Z", sender: { full_name: "Host C" } },
            // PENDING pada proposal yang gagal di-fetch (500) -> fail-closed read-only
            { invitation_id: "INV-ERR", proposal_id: "PROP-ERR-500", status: "PENDING", created_at: "2026-11-18T09:30:00Z", sender: { full_name: "Host D" } },
            // PENDING pada proposal QUORUM_REACHED -> tombol Terima/Tolak tetap tampil
            { invitation_id: "INV-OK", proposal_id: "PROP-QUORUM", status: "PENDING", created_at: "2026-11-18T10:05:00Z", sender: { full_name: "Host E" } },
          ],
        };
      }
      if (url.includes("/group-proposals/")) {
        const pid = url.split("/group-proposals/")[1];
        proposalDetailCalls.push(pid);
        if (pid === "PROP-NOT-FORMED") {
          return { ok: true, status: 200, json: async () => sampleProposal({ proposal_id: pid, status: "NOT_FORMED" }) };
        }
        if (pid === "PROP-CANCELLED") {
          return { ok: true, status: 200, json: async () => sampleProposal({ proposal_id: pid, status: "CANCELLED" }) };
        }
        if (pid === "PROP-EXPIRED") {
          return { ok: true, status: 200, json: async () => sampleProposal({ proposal_id: pid, status: "EXPIRED" }) };
        }
        if (pid === "PROP-ERR-500") {
          return { ok: false, status: 500, json: async () => ({ detail: "Internal error" }) };
        }
        if (pid === "PROP-QUORUM") {
          return { ok: true, status: 200, json: async () => sampleProposal({ proposal_id: pid, status: "QUORUM_REACHED" }) };
        }
      }
      return { ok: true, status: 200, json: async () => [] };
    },
  });

  env.invitationsPageState.activeTab = "inbox";
  await env.loadCurrentInvitationsTab();

  // Deduplikasi: PROP-NOT-FORMED hanya di-fetch 1 kali meskipun ada 2 item PENDING dengan proposal_id sama
  assert.equal(proposalDetailCalls.filter((id) => id === "PROP-NOT-FORMED").length, 1);
  assert.equal(proposalDetailCalls.length, 5);

  const listBox = env.document.getElementById("invitationsListContainer");
  const cards = listBox.querySelectorAll("article");
  assert.equal(cards.length, 6);

  // Hanya 1 kartu (PROP-QUORUM) yang boleh memiliki tombol Terima & Tolak
  assert.equal(listBox.querySelectorAll('button[data-inv-action="accept"]').length, 1);
  assert.equal(listBox.querySelectorAll('button[data-inv-action="decline"]').length, 1);

  // Kartu NOT_FORMED tampil read-only dengan label Tidak Terbentuk & tetap memiliki link Lihat Proposal
  const nfCard = cards.find((c) => c.dataset.invitationId === "INV-NF-1");
  assert.ok(nfCard);
  assert.equal(nfCard.querySelectorAll("button[data-inv-action]").length, 0);
  assert.match(nfCard.textContent, /Tidak Terbentuk/);
  const detailLink = nfCard.querySelector(".btn-detail-link");
  assert.ok(detailLink);
  assert.equal(detailLink.tagName, "A");
  assert.equal(detailLink.href, "proposal-detail.html?id=PROP-NOT-FORMED");
});

// ==============================================================================
// 5. LAYER 2: COMPLETE PROPOSAL STATUS (7) x INVITEE STATUS (5) STATE MACHINE
// ==============================================================================
test("24.2–24.3 Layer 2: Complete ProposalStatus (7) x InvitationStatus (5) matrix for Host & Invitee + privacy", () => {
  const env = bootDay24Sandbox({
    pageScript: PROPOSAL_DETAIL_JS,
    elementIds: ["proposalDetailContent", "proposalAlertContainer", "proposalHeaderSub", "btnRefreshProposal"],
  });
  const box = env.document.getElementById("proposalDetailContent");
  const course = { course_id: "crs-sd", course_code: "ACK2AAB3", course_name: "Struktur Data" };

  // --- HOST MATRIX ---
  env.proposalDetailState.user = { student_id: "stu-host", full_name: "Andi Pratama" };

  // 1) Host + PENDING_RESPONSES -> Cancel only
  env.renderProposalDetail(sampleProposal({ status: "PENDING_RESPONSES" }), course);
  assert.equal(box.querySelector("#btnFinalizeProposal"), null);
  assert.ok(box.querySelector("#btnCancelProposal"));
  assert.equal(box.querySelector("#btnExecuteSession"), null);
  assert.doesNotMatch(box.textContent, /@secret\.edu/);
  assert.doesNotMatch(box.textContent, /120125000/);
  assert.doesNotMatch(box.textContent, /SECRET-INTENT-/);

  // 2) Host + QUORUM_REACHED -> Finalize + Cancel (no Execute)
  env.renderProposalDetail(sampleProposal({ status: "QUORUM_REACHED", active_member_count: 2, quorum_reached: true }), course);
  assert.ok(box.querySelector("#btnFinalizeProposal"));
  assert.ok(box.querySelector("#btnCancelProposal"));
  assert.equal(box.querySelector("#btnExecuteSession"), null);

  // 3) Host + READY_FOR_SESSION -> Execute ONLY (no Finalize, no Cancel)
  env.renderProposalDetail(sampleProposal({ status: "READY_FOR_SESSION", active_member_count: 2, quorum_reached: true }), course);
  assert.equal(box.querySelector("#btnFinalizeProposal"), null);
  assert.equal(box.querySelector("#btnCancelProposal"), null);
  assert.ok(box.querySelector("#btnExecuteSession"));

  // 4) Host + SESSION_EXECUTED -> Buka Detail Sesi CTA only (0 mutation buttons)
  env.renderProposalDetail(sampleProposal({ status: "SESSION_EXECUTED", session_id: "SESS-FINAL-99" }), course);
  assert.equal(box.querySelectorAll("button[data-proposal-action]").length, 0);
  const openBtn = box.querySelector("#btnOpenExecutedSession");
  assert.ok(openBtn);
  assert.equal(openBtn.href, "session-detail.html?id=SESS-FINAL-99");

  // 5-7) Host + NOT_FORMED / CANCELLED / EXPIRED -> 0 mutation buttons
  for (const terminal of ["NOT_FORMED", "CANCELLED", "EXPIRED"]) {
    env.renderProposalDetail(sampleProposal({ status: terminal }), course);
    assert.equal(box.querySelectorAll("button[data-proposal-action]").length, 0);
  }

  // --- EXHAUSTIVE 35-COMBINATION INVITEE MATRIX (7 ProposalStatus x 5 InvitationStatus) + UNKNOWN FALLBACK ---
  env.proposalDetailState.user = { student_id: "stu-budi", full_name: "Budi Santoso" };

  const ALL_PROPOSAL_STATUSES = [
    "PENDING_RESPONSES",
    "QUORUM_REACHED",
    "READY_FOR_SESSION",
    "SESSION_EXECUTED",
    "NOT_FORMED",
    "CANCELLED",
    "EXPIRED",
  ];
  const ALL_INVITATION_STATUSES = ["PENDING", "ACCEPTED", "REJECTED", "WITHDRAWN", "EXPIRED"];
  let combinationsChecked = 0;

  for (const pStat of ALL_PROPOSAL_STATUSES) {
    for (const invStat of ALL_INVITATION_STATUSES) {
      combinationsChecked += 1;
      const p = sampleProposal({
        status: pStat,
        session_id: pStat === "SESSION_EXECUTED" ? "SESS-FINAL-99" : null,
      });
      p.invitations[0].status = invStat;
      env.renderProposalDetail(p, course);

      // Invitee NEVER receives Host controls in any of the 35 combinations
      assert.equal(box.querySelector("#btnFinalizeProposal"), null, `Host Finalize leaked on ${pStat}+${invStat}`);
      assert.equal(box.querySelector("#btnCancelProposal"), null, `Host Cancel leaked on ${pStat}+${invStat}`);
      assert.equal(box.querySelector("#btnExecuteSession"), null, `Host Execute leaked on ${pStat}+${invStat}`);

      const actionButtons = box.querySelectorAll("button[data-proposal-action]");
      const canRespond = invStat === "PENDING" && (pStat === "PENDING_RESPONSES" || pStat === "QUORUM_REACHED");
      if (canRespond) {
        assert.equal(actionButtons.length, 2, `Expected Accept+Decline on ${pStat}+${invStat}`);
        assert.ok(box.querySelector("#btnAcceptProposalInvite"));
        assert.ok(box.querySelector("#btnDeclineProposalInvite"));
      } else {
        assert.equal(actionButtons.length, 0, `Expected 0 mutation buttons (read-only) on ${pStat}+${invStat}`);
      }

      if (invStat === "ACCEPTED" && pStat === "SESSION_EXECUTED") {
        const openLink = box.querySelector("#btnOpenExecutedSession");
        assert.ok(openLink, "ACCEPTED + SESSION_EXECUTED must display Open Session CTA");
        assert.equal(openLink.href, "session-detail.html?id=SESS-FINAL-99");
      } else {
        assert.equal(box.querySelector("#btnOpenExecutedSession"), null, `Unexpected Open Session CTA on ${pStat}+${invStat}`);
      }

      if (invStat === "ACCEPTED" && pStat === "PENDING_RESPONSES") {
        assert.match(box.textContent, /Menunggu anggota lain/i);
      } else if (invStat === "ACCEPTED" && pStat === "QUORUM_REACHED") {
        assert.match(box.textContent, /Menunggu Host memfinalisasi/i);
      } else if (invStat === "ACCEPTED" && pStat === "READY_FOR_SESSION") {
        assert.match(box.textContent, /Menunggu Host mengeksekusi/i);
      }
    }
  }
  assert.equal(combinationsChecked, 35);

  // Unknown / unexpected status combination -> safe read-only fallback with 0 mutation buttons
  const pUnknown = sampleProposal({ status: "UNKNOWN_PROPOSAL_STATE" });
  pUnknown.invitations[0].status = "UNKNOWN_INV_STATE";
  env.renderProposalDetail(pUnknown, course);
  assert.equal(box.querySelectorAll("button[data-proposal-action]").length, 0);
});

// ==============================================================================
// 6. DAY 24.3: EXECUTE REDIRECT, TIMEOUT RECOVERY, 409 CONFLICT, 403/401 & DOUBLE-SUBMIT
// ==============================================================================
test("24.3: Execute redirect, timeout no-auto-retry + refresh recovery, 409 refresh, 403 token intact, 401 logout & double-submit lock", async () => {
  const baseIds = ["proposalDetailContent", "proposalAlertContainer", "proposalHeaderSub", "btnRefreshProposal"];

  // 1) Execute success -> redirects to session-detail.html?id={session_id} from HTTP 201 response
  const envExec = bootDay24Sandbox({
    pageScript: PROPOSAL_DETAIL_JS,
    elementIds: baseIds,
    fetchImpl: async () => ({ ok: true, status: 201, json: async () => ({ session_id: "SESS-24-EXEC" }) }),
  });
  envExec.proposalDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  await envExec.executeCreateSessionFromProposalAction("PROP-24-001", null);
  assert.equal(envExec.timers.length, 1);
  envExec.timers[0].fn();
  assert.deepEqual(envExec.navHistory, [{ type: "href", url: "session-detail.html?id=SESS-24-EXEC" }]);

  // 2) Execute network timeout -> NO auto-retry; manual refresh sees SESSION_EXECUTED + session_id
  const timeoutHits = [];
  const envTimeout = bootDay24Sandbox({
    pageScript: PROPOSAL_DETAIL_JS,
    elementIds: baseIds,
    fetchImpl: async (url, opts) => {
      timeoutHits.push(`${opts.method} ${url}`);
      if (url.includes("/sessions/from-proposal/")) throw new TypeError("Network timeout");
      if (url.includes("/courses/")) return { ok: true, status: 200, json: async () => ({ course_id: "crs-sd", course_code: "ACK2AAB3", course_name: "Struktur Data" }) };
      return { ok: true, status: 200, json: async () => sampleProposal({ status: "SESSION_EXECUTED", session_id: "SESS-RECOVERED-1" }) };
    },
  });
  envTimeout.proposalDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  envTimeout.proposalDetailState.proposalId = "PROP-24-001";
  await envTimeout.executeCreateSessionFromProposalAction("PROP-24-001", null);
  assert.deepEqual(timeoutHits, ["POST /api/v1/sessions/from-proposal/PROP-24-001"]);
  assert.match(envTimeout.document.getElementById("proposalAlertContainer").textContent, /Jangan kirim ulang secara otomatis/i);
  await envTimeout.loadProposalDetail();
  assert.equal(envTimeout.document.getElementById("proposalDetailContent").querySelector("#btnOpenExecutedSession").href, "session-detail.html?id=SESS-RECOVERED-1");

  // 3) Execute 409 conflict -> 1x GET refresh without auto-retry
  const hits409 = [];
  const env409 = bootDay24Sandbox({
    pageScript: PROPOSAL_DETAIL_JS,
    elementIds: baseIds,
    fetchImpl: async (url, opts) => {
      hits409.push(`${opts.method} ${url}`);
      if (url.includes("/sessions/from-proposal/")) return { ok: false, status: 409, json: async () => ({ detail: "Konflik eksekusi konkuren" }) };
      if (url.includes("/courses/")) return { ok: true, status: 200, json: async () => ({ course_id: "crs-sd", course_code: "ACK2AAB3", course_name: "Struktur Data" }) };
      return { ok: true, status: 200, json: async () => sampleProposal({ status: "SESSION_EXECUTED", session_id: "SESS-RACE-WIN" }) };
    },
  });
  env409.proposalDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  env409.proposalDetailState.proposalId = "PROP-24-001";
  await env409.executeCreateSessionFromProposalAction("PROP-24-001", null);
  assert.equal(hits409.filter((h) => h.startsWith("POST")).length, 1);
  assert.ok(hits409.includes("GET /api/v1/group-proposals/PROP-24-001"));

  // 4) Outsider HTTP 403 preserves token; HTTP 401 clears token & redirects
  const env403 = bootDay24Sandbox({
    pageScript: PROPOSAL_DETAIL_JS,
    elementIds: baseIds,
    fetchImpl: async () => ({ ok: false, status: 403, json: async () => ({ detail: "Tidak diizinkan" }) }),
  });
  env403.app.setAuth("keep-this-token", { student_id: "stu-outsider", full_name: "Doni" });
  env403.proposalDetailState.user = { student_id: "stu-outsider", full_name: "Doni" };
  env403.proposalDetailState.proposalId = "PROP-24-001";
  await env403.loadProposalDetail();
  assert.equal(env403.app.getToken(), "keep-this-token");
  assert.match(env403.document.getElementById("proposalDetailContent").textContent, /Akses Ditolak/);

  const env401 = bootDay24Sandbox({
    pageScript: PROPOSAL_DETAIL_JS,
    elementIds: baseIds,
    fetchImpl: async () => ({ ok: false, status: 401, json: async () => ({ detail: "Token expired" }) }),
  });
  env401.app.setAuth("expired-tok", { student_id: "stu-host", full_name: "Andi" });
  env401.proposalDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  env401.proposalDetailState.proposalId = "PROP-24-001";
  await env401.loadProposalDetail();
  assert.equal(env401.app.getToken(), null);
  assert.deepEqual(env401.navHistory, [{ type: "replace", url: "login.html" }]);

  // 5) Double-submit lock blocks concurrent finalize clicks
  let finalizeCalls = 0;
  let releaseFin;
  const finGate = new Promise((r) => {
    releaseFin = r;
  });
  const envDs = bootDay24Sandbox({
    pageScript: PROPOSAL_DETAIL_JS,
    elementIds: baseIds,
    fetchImpl: async (url) => {
      if (url.endsWith("/finalize")) {
        finalizeCalls += 1;
        await finGate;
        return { ok: true, status: 200, json: async () => sampleProposal({ status: "READY_FOR_SESSION" }) };
      }
      return { ok: true, status: 200, json: async () => ({ course_id: "crs-sd", course_code: "ACK2AAB3", course_name: "Struktur Data" }) };
    },
  });
  envDs.proposalDetailState.user = { student_id: "stu-host", full_name: "Andi" };
  const f1 = envDs.executeFinalizeProposalAction("PROP-24-001", null);
  const f2 = envDs.executeFinalizeProposalAction("PROP-24-001", null);
  releaseFin();
  await Promise.all([f1, f2]);
  assert.equal(finalizeCalls, 1);
});

