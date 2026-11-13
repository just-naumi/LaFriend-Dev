import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api, hasToken, setToken } from "./api.js";
import { Auth, Onboarding, Splash } from "./Auth.jsx";
import { Group, Results } from "./Group.jsx";
import Request from "./Request.jsx";
import { Button, Confetti, Icon, Logo, Page, Sheet, fmtSlot, spring } from "./ui.jsx";

const read = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* tidak wajib */ } };

const TABS = [["beranda", "Beranda", "home"], ["belajar", "Belajar", "pen"], ["kelompok", "Kelompok", "users"], ["hasil", "Hasil", "chart"]];

export default function App() {
  const [intro, setIntro] = useState(read("lf-intro", "") !== "seen");
  const [st, setSt] = useState(hasToken() ? null : false);
  const [toast, setToast] = useState("");
  const [tab, setTab] = useState("beranda");
  const [party, setParty] = useState(0);
  const [testMode, setTestMode] = useState(read("lf-test", "on") === "on");
  const sessions = useRef(null);

  useEffect(() => {
    if (!hasToken()) return;
    api("/api/state").then(setSt).catch(() => { setToken(null); setSt(false); });
  }, []);
  useEffect(() => {
    if (!st) return;
    const confirmed = st.sessions.length;
    if (sessions.current != null && confirmed > sessions.current) setParty(Date.now());
    sessions.current = confirmed;
  }, [st]);
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(""), 4200); return () => clearTimeout(t); } }, [toast]);

  // Semua aksi lewat sini: hasilnya state terbaru dari server, kesalahannya jadi pesan singkat
  const act = useCallback(async fn => {
    try {
      const r = await fn();
      setSt(r.state || r);
      return true;
    } catch (e) {
      if (e.status === 401) { setToken(null); setSt(false); }
      setToast(e.message);
      return false;
    }
  }, []);
  const endIntro = useCallback(() => { write("lf-intro", "seen"); setIntro(false); }, []);

  let body;
  if (intro) body = <Splash key="splash" onDone={endIntro} />;
  else if (st === null) body = <div key="load" className="loading" role="status" aria-label="Memuat"><Logo size={40} /></div>;
  else if (st === false) body = <Auth key="auth" onIn={r => { setToken(r.token); setSt(r.state); setTab("beranda"); }} />;
  else if (!st.account.ready) body = <Onboarding key="onb" st={st} act={act} />;
  else body = <Shell key="app" {...{ st, act, tab, setTab, testMode }} onTest={v => { setTestMode(v); write("lf-test", v ? "on" : "off"); }}
    onOut={async () => { await api("/api/logout", {}).catch(() => {}); setToken(null); setSt(false); }} />;

  return (
    <>
      <div className="aurora" aria-hidden="true"><i /><i /><i /></div>
      <AnimatePresence mode="wait">{body}</AnimatePresence>
      <Confetti run={party} />
      <AnimatePresence>
        {toast && <motion.p className="toast" role="alert" initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }} onClick={() => setToast("")}>{toast}</motion.p>}
      </AnimatePresence>
    </>
  );
}

function Shell({ st, act, tab, setTab, testMode, onTest, onOut }) {
  const [me, setMe] = useState(false);
  const f = st.formation;
  const badge = {
    kelompok: f && ((f.status === "DRAFT" && f.my_invite_pending) || (f.status === "CONFIRMATION_PENDING" && f.my_approval == null)) ? 1 : 0,
    hasil: st.sessions.filter(s => s.finished && !s.feedback_given).length,
  };
  const screens = {
    beranda: <Home st={st} go={setTab} />,
    belajar: <Request st={st} act={act} go={setTab} />,
    kelompok: <Group st={st} act={act} go={setTab} testMode={testMode} />,
    hasil: <Results st={st} act={act} testMode={testMode} />,
  };
  return (
    <div className="shell">
      <header className="top">
        <span className="brand"><Logo size={22} />LaFriend</span>
        {testMode && <span className="test-pill">Mode uji</span>}
        <button type="button" className="me-btn" onClick={() => setMe(true)} aria-label="Akun saya">{st.account.name[0]}</button>
      </header>
      <main className="view" id="view">
        <AnimatePresence mode="wait"><div key={tab}>{screens[tab]}</div></AnimatePresence>
      </main>
      <nav className="tabs" aria-label="Menu utama">
        {TABS.map(([k, name, icon]) => (
          <button key={k} type="button" aria-current={tab === k ? "page" : undefined} onClick={() => setTab(k)}>
            {tab === k && <motion.span layoutId="tab" className="tab-bg" transition={spring} />}
            <span className="tab-icon"><Icon name={icon} /></span>
            <span>{name}</span>
            {badge[k] > 0 && <b className="badge" aria-label={`${badge[k]} menunggu`}>{badge[k]}</b>}
          </button>
        ))}
      </nav>
      <Sheet open={me} onClose={() => setMe(false)} title="Akun saya">
        <dl className="account">
          <div><dt>Nama</dt><dd>{st.account.name}</dd></div>
          <div><dt>Email</dt><dd>{st.account.email}</dd></div>
          <div><dt>Gmail</dt><dd>{st.account.gmail || "akun contoh, sudah terverifikasi"}</dd></div>
          <div><dt>Kampus</dt><dd>{st.account.university} · {st.account.program} · {st.account.cohort}</dd></div>
        </dl>
        <label className="switch">
          <input type="checkbox" checked={testMode} onChange={e => onTest(e.target.checked)} />
          <span><strong>Mode uji</strong><small>Jawab undangan atas nama teman dan lompati waktu sesi, supaya semua fitur bisa dicoba sendirian.</small></span>
        </label>
        <Button kind="ghost" onClick={onOut}>Keluar</Button>
      </Sheet>
    </div>
  );
}

function next(st) {
  const f = st.formation;
  const due = st.sessions.find(s => s.finished && !s.feedback_given);
  const soon = st.sessions.find(s => !s.finished);
  if (due) return ["hasil", `Sesi ${due.course} sudah lewat`, "Beri penilaian singkat. Ini yang membuat rekomendasi berikutnya lebih tepat.", "Beri penilaian"];
  if (f?.status === "DRAFT" && f.my_invite_pending) return ["kelompok", `${f.members[0].name} mengajakmu belajar`, fmtSlot(f.slot), "Lihat undangan"];
  if (f?.status === "CONFIRMATION_PENDING" && f.my_approval == null) return ["kelompok", "Jadwal kelompok menunggu persetujuanmu", fmtSlot(f.slot), "Lihat jadwal"];
  if (f && f.status !== "FAILED") return ["kelompok", "Menunggu jawaban teman", "Kami kabari begitu semua menjawab.", "Lihat kelompok"];
  if (f?.status === "FAILED") return ["kelompok", "Kelompok belum terbentuk", "Permintaanmu masih aktif. Coba lagi dengan teman lain.", "Lihat alasannya"];
  if (st.intent?.status === "ACTIVE") return ["belajar", `${st.recommendations.length} teman cocok untuk ${st.intent.course}`, "Bentuk kelompok dari mereka.", "Lihat teman"];
  if (soon) return ["kelompok", `Sesi ${soon.course} terjadwal`, fmtSlot(soon.slot), "Lihat sesi"];
  return ["belajar", "Mulai cari teman belajar", "Ceritakan mau belajar apa, lewat chat, suara, atau form.", "Mulai"];
}

function Home({ st, go }) {
  const [to, title, sub, cta] = next(st);
  const hour = new Date().getHours();
  const hello = hour < 11 ? "Selamat pagi" : hour < 15 ? "Selamat siang" : hour < 19 ? "Selamat sore" : "Selamat malam";
  const rows = [
    ["Permintaan", st.intent ? `${st.intent.course} · ${st.intent.topics}` : "Belum ada", "belajar"],
    ["Kelompok", st.formation ? { DRAFT: "Menunggu undangan dijawab", CONFIRMATION_PENDING: "Menunggu jadwal disetujui", FAILED: "Belum terbentuk" }[st.formation.status] : "Belum ada", "kelompok"],
    ["Sesi", st.sessions.length ? `${st.sessions.length} sesi, ${st.sessions.filter(s => !s.feedback_given && s.finished).length} belum dinilai` : "Belum ada", "hasil"],
  ];
  return (
    <Page>
      <p className="eyebrow">{hello}, {st.me.name}</p>
      <motion.div className="next" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
        <span className="next-label">Langkah berikutnya</span>
        <h1 className="display">{title}</h1>
        <p className="lead">{sub}</p>
        <Button onClick={() => go(to)}>{cta} →</Button>
      </motion.div>
      <ul className="summary">
        {rows.map(([k, v, t]) => (
          <li key={k}>
            <button type="button" onClick={() => go(t)}><span className="muted">{k}</span><span>{v}</span></button>
          </li>
        ))}
      </ul>
    </Page>
  );
}
