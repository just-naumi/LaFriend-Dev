import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api } from "./api.js";
import { Button, Chips, FACTOR, Field, GOAL, Icon, Logo, MODE, Orb, Page, STYLE, WEEKDAYS, fmtDay, fmtSlot, spring } from "./ui.jsx";

const Speech = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

export default function Request({ st, act, go }) {
  const [view, setView] = useState(st.chat.messages.length ? "chat" : "pick");
  const [manual, setManual] = useState(false);
  if (st.intent) return <Running st={st} act={act} go={go} />;
  const review = isManual => { setManual(isManual); setView("review"); };
  return (
    <AnimatePresence mode="wait">
      {view === "pick" && <Pick key="pick" st={st} onPick={v => (v === "review" ? review(true) : setView(v))} />}
      {view === "chat" && <Chat key="chat" st={st} act={act} onBack={() => setView("pick")} onReview={() => review(false)} onVoice={() => setView("voice")} />}
      {view === "voice" && <Voice key="voice" act={act} onBack={() => setView("pick")} onSent={() => setView("chat")} />}
      {view === "review" && <Review key="review" st={st} act={act} start={manual ? {} : st.chat.fields} onBack={() => setView(manual ? "pick" : "chat")} />}
    </AnimatePresence>
  );
}

function Pick({ st, onPick }) {
  const h = st.habits;
  const usual = [h.collaboration_style && STYLE[h.collaboration_style], h.learning_mode && MODE[h.learning_mode],
    h.group_size && `${h.group_size[0]}–${h.group_size[1]} orang`].filter(Boolean);
  // Urutan tile: satu tinggi di kiri (cara utama), dua kecil di kanan
  const ways = [
    ["chat", "Ngobrol dengan asisten", "Ceritakan dengan kalimatmu sendiri. Asisten menanyakan yang kurang.", "chat", "tall"],
    ["review", "Isi sendiri", "Form biasa, semua kamu pilih.", "form", "butter"],
    ["voice", "Bicara saja", Speech ? "Rekam, cek transkrip, kirim." : "Belum didukung browser ini.", "mic", "dark"],
  ];
  return (
    <Page>
      <h1 className="display sm">Mau belajar apa?</h1>
      <p className="lead">Pilih cara yang paling enak. Semuanya berakhir di layar periksa sebelum disimpan.</p>
      <div className="tiles">
        {ways.map(([k, title, sub, icon, look]) => (
          <button key={k} type="button" className={`tile ${look}`} onClick={() => onPick(k)} disabled={k === "voice" && !Speech}>
            <span className="tile-ic"><Icon name={icon} size={22} /></span>
            <span><strong>{title}</strong><small>{sub}</small></span>
            {look === "tall" && <span className="go"><Icon name="arrow" size={18} /></span>}
          </button>
        ))}
      </div>
      {usual.length > 0 && <p className="habit">Kebiasaanmu: <b>{usual.join(" · ")}</b>. Asisten akan menawarkannya.</p>}
    </Page>
  );
}

function Chat({ st, act, onBack, onReview, onVoice }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  const c = st.chat;
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [c.messages.length, busy]);

  async function send(t) {
    const value = (t ?? text).trim();
    if (!value) return;
    setBusy(true); setText("");
    await act(() => api("/api/assistant", { text: value }));
    setBusy(false);
  }
  const quick = c.confirm || c.suggest ? ["Ya", "Bukan"] : c.ask === "date_range" ? ["Minggu ini", "Minggu depan", "Dua minggu ke depan"] : [];

  return (
    <Page>
      <div className="chat-top">
        <button type="button" className="icon" onClick={onBack} aria-label="Kembali ke pilihan cara"><Icon name="back" size={20} /></button>
        <span className="chat-title"><Logo size={22} />Asisten LaFriend</span>
        <button type="button" className="icon" onClick={() => act(() => api("/api/assistant/reset", {}))} disabled={!c.messages.length}
          aria-label="Mulai ulang percakapan"><Icon name="reset" size={20} /></button>
      </div>
      <div className="chat" aria-live="polite">
        <span className="day-pill">Hari ini</span>
        <Bubble from="bot" text="Halo! Ceritakan mau belajar apa dan kapan kamu kosong. Contoh: “Strukdat materi Binary Tree buat UTS, Senin jam 7-9 malam.”" />
        {c.messages.map((m, i) => <Bubble key={i} {...m} />)}
        {busy && <div className="bubble bot typing" aria-label="Asisten mengetik"><span className="dots"><i /><i /><i /></span></div>}
      </div>
      <AnimatePresence>
        {c.done && (
          <motion.div key="done" className="done-bar" initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 10, opacity: 0 }}>
            <Button onClick={onReview}>Periksa lalu simpan</Button>
          </motion.div>
        )}
      </AnimatePresence>
      {quick.length > 0 && !busy && (
        <div className="quick">{quick.map(q => <button key={q} type="button" className="chip" onClick={() => send(q)}>{q}</button>)}</div>
      )}
      <span ref={end} className="chat-end" />
      <form className="composer" onSubmit={e => { e.preventDefault(); send(); }}>
        <input aria-label="Tulis pesan" value={text} onChange={e => setText(e.target.value)} placeholder="Tulis di sini…" maxLength={500} />
        {Speech && <button type="button" className="icon" onClick={onVoice} aria-label="Bicara"><Icon name="mic" size={20} /></button>}
        <button type="submit" className="icon send" disabled={!text.trim() || busy} aria-label="Kirim"><Icon name="send" size={20} /></button>
      </form>
      {!c.done && c.messages.length > 0 && <button type="button" className="link center" onClick={onReview}>Lanjut isi di form saja</button>}
    </Page>
  );
}

function Bubble({ from, text }) {
  return (
    <motion.p className={`bubble ${from}`} initial={{ opacity: 0, y: 10, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={spring}>
      {text}
    </motion.p>
  );
}

function Voice({ act, onBack, onSent }) {
  const [listening, setListening] = useState(false);
  const [final, setFinal] = useState("");
  const [interim, setInterim] = useState("");
  const [err, setErr] = useState("");
  const rec = useRef(null);
  useEffect(() => () => rec.current?.abort(), []);

  function toggle() {
    if (listening) { rec.current?.stop(); return; }
    const r = new Speech();
    r.lang = "id-ID"; r.interimResults = true; r.continuous = true;
    r.onresult = e => {
      let fin = "", mid = "";
      for (let i = e.resultIndex; i < e.results.length; i++) (e.results[i].isFinal ? (fin += e.results[i][0].transcript) : (mid += e.results[i][0].transcript));
      if (fin) setFinal(f => `${f} ${fin}`.trim());
      setInterim(mid);
    };
    r.onerror = e => setErr(e.error === "not-allowed" ? "Izin mikrofon ditolak. Aktifkan di pengaturan browser." : "Suara tidak tertangkap. Coba lagi.");
    r.onend = () => { setListening(false); setInterim(""); };
    rec.current = r; setErr(""); r.start(); setListening(true);
  }
  async function send() {
    if (await act(() => api("/api/assistant", { text: final.trim() }))) onSent();
  }

  return (
    <Page>
      <button type="button" className="back" onClick={onBack}>← Cara lain</button>
      <div className="voice">
        <button type="button" className="orb-btn" onClick={toggle} aria-pressed={listening} aria-label={listening ? "Berhenti merekam" : "Mulai merekam"}>
          <Orb active={listening} />
        </button>
        <p className="voice-state" aria-live="polite">{listening ? "Mendengarkan… ketuk bola untuk berhenti" : final ? "Cek transkripnya, ubah kalau ada yang salah" : "Ketuk bola, lalu ceritakan mau belajar apa dan kapan kosong"}</p>
        {interim && <p className="interim">{interim}</p>}
        {err && <p className="error" role="alert">{err}</p>}
      </div>
      <Field label="Transkrip">
        <textarea rows={4} value={final} onChange={e => setFinal(e.target.value)} placeholder="Transkrip muncul di sini" />
      </Field>
      <Button disabled={!final.trim() || listening} onClick={send}>Kirim ke asisten</Button>
    </Page>
  );
}

const EMPTY_SLOT = { day_or_date: "", start_time: "19:00", end_time: "21:00", priority_rank: 1 };

function dayOptions(from, to, today, max = 21) {
  const start = new Date(`${from || today}T00:00:00`);
  const stop = to ? new Date(`${to}T00:00:00`) : new Date(start.getTime() + 13 * 864e5);
  const out = [];
  for (let d = start; d <= stop && out.length < max; d = new Date(d.getTime() + 864e5)) {
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`);
  }
  return out;
}

function Review({ st, act, start, onBack }) {
  const h = st.habits;
  const [f, setF] = useState(() => ({
    course_id: "", topics: "", learning_goal: "", collaboration_style: h.collaboration_style || "", learning_mode: h.learning_mode || "",
    earliest_date: st.today, latest_date: "", min_group_size: h.group_size?.[0] || 2, max_group_size: h.group_size?.[1] || 4,
    availabilities: [], ...start,
  }));
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  const set = (k, v) => setF(x => ({ ...x, [k]: v }));
  const slots = f.availabilities.length ? f.availabilities : [];
  const setSlot = (i, k, v) => set("availabilities", slots.map((s, n) => (n === i ? { ...s, [k]: v } : s)));
  const days = [...WEEKDAYS, ...dayOptions(f.earliest_date, f.latest_date, st.today)];
  const miss = k => tried && !String(f[k] ?? "").trim();
  // Hari yang tidak muncul di rentang tanggal tidak akan pernah cocok dengan siapa pun
  const inRange = dayOptions(f.earliest_date, f.latest_date, st.today, 400);
  const names = new Set(inRange.map(d => WEEKDAYS[(new Date(`${d}T00:00:00`).getDay() + 6) % 7]));
  const outside = f.latest_date ? slots.map(s => s.day_or_date).filter(d => d && (WEEKDAYS.includes(d) ? !names.has(d) : !inRange.includes(d))) : [];

  async function save() {
    setTried(true);
    setBusy(true);
    await act(() => api("/api/intent", { ...f, min_group_size: Number(f.min_group_size), max_group_size: Number(f.max_group_size) }));
    setBusy(false);
  }

  return (
    <Page>
      <button type="button" className="back" onClick={onBack}>← Kembali</button>
      <h1 className="display sm">Periksa dulu</h1>
      <p className="lead">{Object.keys(start).length ? "Ini yang ditangkap asisten. Ubah yang kurang pas." : "Isi semuanya, lalu simpan."}</p>
      <div className="form">
        <Field label="Mata kuliah" missing={miss("course_id")}>
          <select value={f.course_id} onChange={e => set("course_id", e.target.value)}>
            <option value="">Pilih mata kuliah</option>
            {st.courses.map(c => <option key={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Topik atau bab" hint="Pisahkan dengan koma, misalnya: Binary Tree, AVL" missing={miss("topics")}>
          <input value={f.topics} onChange={e => set("topics", e.target.value)} />
        </Field>
        <Chips label="Tujuan" options={GOAL} value={f.learning_goal} onChange={v => set("learning_goal", v)} missing={miss("learning_goal")} />
        <div className="field">
          <span className="lab">Waktu kosong{tried && !slots.length && <em> belum diisi</em>}</span>
          {slots.map((s, i) => (
            <div className="slot" key={i}>
              <select aria-label="Hari atau tanggal" value={s.day_or_date} onChange={e => setSlot(i, "day_or_date", e.target.value)}>
                <option value="">Hari</option>
                {[...new Set([s.day_or_date, ...days].filter(Boolean))].map(d => <option key={d} value={d}>{fmtDay(d)}</option>)}
              </select>
              <input type="time" aria-label="Mulai" value={s.start_time} onChange={e => setSlot(i, "start_time", e.target.value)} />
              <input type="time" aria-label="Selesai" value={s.end_time} onChange={e => setSlot(i, "end_time", e.target.value)} />
              <button type="button" className="icon" aria-label="Hapus waktu ini" onClick={() => set("availabilities", slots.filter((_, n) => n !== i))}><Icon name="x" size={18} /></button>
            </div>
          ))}
          <button type="button" className="link" onClick={() => set("availabilities", [...slots, { ...EMPTY_SLOT, priority_rank: slots.length + 1 }])}>+ Tambah waktu</button>
        </div>
        <div className="two">
          <Field label="Dari tanggal"><input type="date" value={f.earliest_date} min={st.today} onChange={e => set("earliest_date", e.target.value)} /></Field>
          <Field label="Sampai tanggal" missing={miss("latest_date")}><input type="date" value={f.latest_date} min={f.earliest_date} onChange={e => set("latest_date", e.target.value)} /></Field>
        </div>
        {outside.length > 0 && <p className="warn" role="status">{outside.map(fmtDay).join(", ")} tidak ada di rentang tanggal ini. Ubah harinya atau rentangnya.</p>}
        <Chips label="Cara belajar" options={STYLE} value={f.collaboration_style} onChange={v => set("collaboration_style", v)} missing={miss("collaboration_style")} />
        <Chips label="Bertemu" options={MODE} value={f.learning_mode} onChange={v => set("learning_mode", v)} missing={miss("learning_mode")} />
        <Chips label="Kelompok paling sedikit" options={{ 2: "2", 3: "3", 4: "4" }} value={f.min_group_size} onChange={v => set("min_group_size", v)} />
        <Chips label="Kelompok paling banyak" options={{ 2: "2", 3: "3", 4: "4" }} value={f.max_group_size} onChange={v => set("max_group_size", v)} />
        <Button busy={busy} onClick={save}>Simpan permintaan</Button>
      </div>
    </Page>
  );
}

function Running({ st, act, go }) {
  const i = st.intent;
  const [open, setOpen] = useState(null);
  const [busy, setBusy] = useState(false);
  async function group() {
    setBusy(true);
    if (await act(() => api("/api/group", {}))) go("kelompok");
    setBusy(false);
  }
  return (
    <Page>
      <p className="eyebrow">Permintaanmu {i.status === "ACTIVE" ? "aktif" : "sedang diproses kelompok"}</p>
      <h1 className="display sm">{i.course}</h1>
      <p className="lead">{i.topics} · {GOAL[i.goal]} · {STYLE[i.style]} · {MODE[i.mode]} · {i.min}–{i.max} orang</p>
      <p className="slots">{i.slots.map((s, n) => <span key={n} className="tag">{fmtSlot(s)}</span>)}</p>

      {i.status === "ACTIVE" && <>
        <h2 className="h2">Teman yang cocok <small>{st.recommendations.length}</small></h2>
        {st.recommendations.length === 0 && <p className="muted">Belum ada yang cocok. Coba tambah waktu kosong atau perlebar rentang tanggal.</p>}
        <ol className="people">
          {st.recommendations.map(r => (
            <motion.li key={r.id} layout>
              <button type="button" className="person" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>
                <span className="avatar">{r.name[0]}</span>
                <span className="grow"><strong>{r.name}</strong><small>{r.topics} · {fmtSlot(r.slot)}</small></span>
                <span className="score" aria-label={`Skor ${Math.round(r.total)} dari 100`}>{Math.round(r.total)}</span>
              </button>
              <span className="stackbar" aria-hidden="true">
                {FACTOR.map(([k]) => <i key={k} className={`f-${k}`} style={{ flexGrow: r.scores[k] * st.weights[k] }} />)}
              </span>
              <AnimatePresence>
                {open === r.id && (
                  <motion.dl className="factors" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                    {FACTOR.map(([k, label]) => (
                      <div key={k}><dt><i className={`dot f-${k}`} />{label}</dt><dd>{Math.round(r.scores[k])}</dd></div>
                    ))}
                    <p className="muted">{r.shared_topics.length ? `Materi sama: ${r.shared_topics.join(", ")}.` : "Materinya berbeda."} {STYLE[r.style]}, {MODE[r.mode]}.</p>
                  </motion.dl>
                )}
              </AnimatePresence>
            </motion.li>
          ))}
        </ol>
        <div className="stack-btn">
          <Button busy={busy} disabled={!st.recommendations.length} onClick={group}>Bentuk kelompok</Button>
          <Button kind="ghost" onClick={() => act(() => api("/api/intent/cancel", {}))}>Batalkan permintaan</Button>
        </div>
        <p className="muted small">Skor kecocokan adalah indeks dari lima faktor, bukan peluang berhasil.</p>
      </>}
      {i.status !== "ACTIVE" && <Button onClick={() => go("kelompok")}>Lihat kelompok</Button>}
    </Page>
  );
}
