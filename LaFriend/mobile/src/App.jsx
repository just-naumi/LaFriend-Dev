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
    beranda: <Home st={st} act={act} go={setTab} />,
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
            {/* bukan motion layoutId: itu menahan animasi keluar Shell sehingga tombol Keluar macet setelah pindah tab */}
            {tab === k && <span className="tab-bg" />}
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

const IDEAS = [["Basis Data", "latihan soal SQL"], ["Algoritma dan Pemrograman", "memahami rekursi"], ["Jaringan Komputer dan Data", "diskusi subnetting"]];

function Home({ st, act, go }) {
  const [to, title, sub, cta] = next(st);
  const hour = new Date().getHours();
  const hello = hour < 11 ? "Selamat pagi" : hour < 15 ? "Selamat siang" : hour < 19 ? "Selamat sore" : "Selamat malam";
  const upcoming = st.sessions.filter(s => !s.finished);
  const recs = st.intent?.status === "ACTIVE" ? st.recommendations : [];
  const start = (course, topic) => act(() => api("/api/assistant", { text: `${course}, ${topic}` })).then(ok => ok && go("belajar"));
  return (
    <Page>
      <h1 className="display">Halo, {st.me.name}</h1>
      <p className="lead">{hello}. Belajar bareng siapa hari ini?</p>
      <div className="tiles">
        <motion.button type="button" className="tile tall" onClick={() => go(to)} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
          <span className="next-label">Langkah berikutnya</span>
          <span><strong>{title}</strong><small>{sub}</small></span>
          <span className="cta">{cta}</span>
          <span className="go" aria-hidden="true"><Icon name="arrow" size={18} /></span>
        </motion.button>
        <div className="tile butter stat"><span className="stat-n">{st.intent ? recs.length : "–"}</span><small>{st.intent ? `teman cocok untuk ${st.intent.course}` : "belum ada permintaan belajar"}</small></div>
        <div className="tile dark stat"><span className="stat-n">{upcoming.length}</span><small>sesi terjadwal</small></div>
      </div>

      {recs.length > 0 && <>
        <div className="sec"><h2 className="h2">Teman yang cocok</h2><button type="button" className="link" onClick={() => go("belajar")}>Lihat semua</button></div>
        <ul className="feed">
          {recs.slice(0, 3).map(r => (
            <li key={r.id}><button type="button" className="feed-card" onClick={() => go("belajar")}>
              <span className="avatar">{r.name[0]}</span>
              <span className="grow"><strong>{r.name}</strong><span className="tags"><span className="tag">Skor {Math.round(r.total)}</span><span className="tag">{fmtSlot(r.slot)}</span></span></span>
              <span className="go" aria-hidden="true"><Icon name="arrow" size={18} /></span>
            </button></li>
          ))}
        </ul>
      </>}
      {!recs.length && upcoming.length > 0 && <>
        <div className="sec"><h2 className="h2">Sesi berikutnya</h2></div>
        <ul className="feed">
          {upcoming.slice(0, 3).map(s => (
            <li key={s.id}><button type="button" className="feed-card" onClick={() => go("kelompok")}>
              <span className="grow"><strong>{s.course}</strong><span className="tags"><span className="tag">{fmtSlot(s.slot)}</span><span className="tag">{s.members.length} orang</span></span></span>
              <span className="go" aria-hidden="true"><Icon name="arrow" size={18} /></span>
            </button></li>
          ))}
        </ul>
      </>}
      {!st.intent && !upcoming.length && <>
        <div className="sec"><h2 className="h2">Ide untuk memulai</h2></div>
        <ul className="feed">
          {IDEAS.filter(([c]) => st.courses.includes(c)).map(([c, t]) => (
            <li key={c}><button type="button" className="feed-card" onClick={() => start(c, t)}>
              <span className="grow"><strong>{c}</strong><span className="tags"><span className="tag">{t}</span><span className="tag">lewat asisten</span></span></span>
              <span className="go" aria-hidden="true"><Icon name="chat" size={18} /></span>
            </button></li>
          ))}
        </ul>
      </>}
    </Page>
  );
}
