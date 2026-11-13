import { useState } from "react";
import { motion } from "motion/react";
import { api } from "./api.js";
import { Button, Chips, Field, Page, REASON, Sheet, fmtSlot, spring } from "./ui.jsx";

export function Group({ st, act, go, testMode }) {
  const f = st.formation;
  const upcoming = st.sessions.filter(s => !s.finished);
  const [busy, setBusy] = useState("");
  const run = async (key, fn) => { setBusy(key); await act(fn); setBusy(""); };

  if (!f) {
    return (
      <Page>
        <h1 className="display sm">Kelompok</h1>
        {upcoming.map(s => <SessionLine key={s.id} s={s} />)}
        {!upcoming.length && <p className="lead">{st.intent ? "Belum ada kelompok. Bentuk dari daftar teman yang cocok." : "Buat permintaan belajar dulu, lalu bentuk kelompok dari teman yang cocok."}</p>}
        <Button kind={upcoming.length ? "ghost" : "primary"} onClick={() => go("belajar")}>{st.intent ? "Lihat teman yang cocok" : "Buat permintaan"}</Button>
      </Page>
    );
  }

  const me = st.me.id;
  const pending = f.members.filter(m => m.id !== me && (f.status === "DRAFT" ? !m.accepted : m.approved == null));
  const headline = {
    DRAFT: f.my_invite_pending ? "Kamu diundang belajar bareng" : "Menunggu teman menerima undangan",
    CONFIRMATION_PENDING: f.my_approval == null ? "Setujui jadwalnya" : "Menunggu teman menyetujui jadwal",
    FAILED: "Kelompok belum terbentuk",
  }[f.status];

  return (
    <Page>
      <p className="eyebrow">{f.is_host ? "Kamu yang memulai" : "Undangan kelompok"}</p>
      <h1 className="display sm">{headline}</h1>
      {f.status === "FAILED" ? <>
        <p className="lead">Alasannya: {REASON[f.reason_code] || f.reason_code}. Permintaanmu masih aktif, jadi kamu bisa mencoba lagi.</p>
        <Button onClick={() => go("belajar")}>Coba bentuk lagi</Button>
      </> : <>
        <motion.div className="when" initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={spring}>
          <span className="when-day">{fmtSlot(f.slot)}</span>
          <small>Jadwal {f.slot_number} dari {f.slot_count} · kecocokan kelompok {Math.round(f.gq)}</small>
        </motion.div>
        <ol className="members">
          {f.members.map(m => (
            <li key={m.id}>
              <span className="avatar">{m.name[0]}</span>
              <span className="grow">{m.name}{m.id === me && " (kamu)"}{m.host && <small> · pemula</small>}</span>
              <span className={`state ${status(f, m)}`}>{label(f, m)}</span>
            </li>
          ))}
        </ol>
        {f.status === "DRAFT" && f.my_invite_pending && (
          <div className="stack-btn">
            <Button busy={busy === "yes"} onClick={() => run("yes", () => api("/api/invite", { answer: "ACCEPTED" }))}>Terima undangan</Button>
            <Button kind="ghost" busy={busy === "no"} onClick={() => run("no", () => api("/api/invite", { answer: "REJECTED" }))}>Tolak</Button>
          </div>
        )}
        {f.status === "CONFIRMATION_PENDING" && f.my_approval == null && (
          <div className="stack-btn">
            <Button busy={busy === "yes"} onClick={() => run("yes", () => api("/api/schedule", { approve: true }))}>Jadwal ini cocok</Button>
            <Button kind="ghost" busy={busy === "no"} onClick={() => run("no", () => api("/api/schedule", { approve: false }))}>Tidak bisa</Button>
          </div>
        )}
        {testMode && pending.length > 0 && (
          <div className="test">
            <p className="test-title">Mode uji · jawab sebagai teman</p>
            {pending.map(m => (
              <div className="test-row" key={m.id}>
                <span>{m.name}</span>
                {[true, false].map(yes => (
                  <button key={String(yes)} type="button" className={`chip${yes ? " on-soft" : ""}`}
                    onClick={() => run("", () => api("/api/test/act", { as_id: m.id, action: f.status === "DRAFT" ? "invite" : "schedule", yes }))}>
                    {f.status === "DRAFT" ? (yes ? "Terima" : "Tolak") : (yes ? "Setuju" : "Tidak bisa")}
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}
      </>}
    </Page>
  );
}

const status = (f, m) => (f.status === "DRAFT" ? (m.accepted ? "ok" : "wait") : m.approved == null ? "wait" : m.approved ? "ok" : "no");
const label = (f, m) => (f.status === "DRAFT" ? (m.host ? "memulai" : m.accepted ? "menerima" : "menunggu") : m.approved == null ? "menunggu" : m.approved ? "setuju" : "tidak bisa");

function SessionLine({ s, children }) {
  return (
    <div className="session">
      <span className="grow"><strong>{s.course}</strong><small>{s.topics} · {fmtSlot(s.slot)} · {s.members.join(", ")}</small></span>
      {children}
    </div>
  );
}

const METRICS = [
  ["rar", "Rekomendasi yang ditindaklanjuti", "%"], ["gfr", "Kelompok yang jadi", "%"], ["scr", "Sesi yang terlaksana", "%"],
  ["mss", "Kepuasan rata-rata", " / 5"], ["rsi", "Mau belajar bareng lagi", "%"],
];

export function Results({ st, act, testMode }) {
  const [fb, setFb] = useState(null);
  const m = st.metrics;
  return (
    <Page>
      <h1 className="display sm">Hasil belajar</h1>
      <h2 className="h2">Sesimu</h2>
      {!st.sessions.length && <p className="muted">Belum ada sesi. Sesi muncul di sini setelah jadwal kelompok disetujui semua anggota.</p>}
      {st.sessions.map(s => (
        <SessionLine key={s.id} s={s}>
          {s.feedback_given ? <span className="state ok">dinilai</span>
            : s.finished ? <Button className="sm" onClick={() => setFb(s)}>Beri penilaian</Button>
              : testMode ? <button type="button" className="chip" onClick={() => act(() => api("/api/test/end", { session_id: s.id }))}>Anggap sudah selesai</button>
                : <span className="state wait">akan datang</span>}
        </SessionLine>
      ))}

      <h2 className="h2">Apakah LaFriend membantu?</h2>
      <p className="muted small">Lima angka ini sengaja tidak digabung. Dihitung dari semua pengguna.</p>
      <ul className="metrics">
        {METRICS.map(([k, name, unit]) => {
          const none = !m[k].denominator;
          const pct = none ? 0 : k === "mss" ? (m[k].value / 5) * 100 : m[k].value;
          return (
            <li key={k}>
              <span className="grow">{name}<small>{none ? "belum ada data" : k === "mss" ? `${m[k].denominator} jawaban` : `${m[k].numerator} dari ${m[k].denominator}`}</small></span>
              <strong>{none ? "–" : `${String(m[k].value).replace(".", ",")}${unit}`}</strong>
              <span className="meter"><motion.i style={{ width: `${pct}%` }} initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }} /></span>
            </li>
          );
        })}
      </ul>
      {!m.data_sufficient && <p className="muted small">Bobot skor baru diuji ulang setelah {m.min_completed_for_weight_test} sesi selesai dengan penilaian. Sekarang baru {m.completed_with_feedback}.</p>}
      <Feedback s={fb} onClose={() => setFb(null)} act={act} />
    </Page>
  );
}

function Stars({ label, value, onChange }) {
  return (
    <div className="field" role="radiogroup" aria-label={label}>
      <span className="lab">{label}</span>
      <div className="stars">
        {[1, 2, 3, 4, 5].map(n => (
          <motion.button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} dari 5`} whileTap={{ scale: 1.3 }}
            className={n <= (value || 0) ? "on" : ""} onClick={() => onChange(n)}>★</motion.button>
        ))}
      </div>
    </div>
  );
}

function Feedback({ s, onClose, act }) {
  const [d, setD] = useState({ session_held: true, overall_satisfaction: null, repeat_intention: null });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setD(x => ({ ...x, [k]: v }));
  async function send() {
    setBusy(true);
    const body = d.session_held ? d : { session_held: false, reason_code: d.reason_code || "OTHER", comments: d.comments };
    if (await act(() => api("/api/feedback", { session_id: s.id, data: body }))) { onClose(); setD({ session_held: true }); }
    setBusy(false);
  }
  return (
    <Sheet open={!!s} onClose={onClose} title={s ? `Sesi ${s.course}` : ""}>
      <Chips label="Sesinya jadi?" options={{ yes: "Jadi", no: "Tidak jadi" }} value={d.session_held ? "yes" : "no"} onChange={v => set("session_held", v === "yes")} />
      {d.session_held ? <>
        <Stars label="Puas secara keseluruhan" value={d.overall_satisfaction} onChange={v => set("overall_satisfaction", v)} />
        <Stars label="Semua ikut aktif" value={d.participation_rating} onChange={v => set("participation_rating", v)} />
        <Stars label="Gaya belajarnya cocok" value={d.style_fit_rating} onChange={v => set("style_fit_rating", v)} />
        <Stars label="Materinya jadi lebih paham" value={d.learning_benefit_rating} onChange={v => set("learning_benefit_rating", v)} />
        <Chips label="Mau belajar bareng lagi?" options={{ yes: "Mau", no: "Tidak" }} value={d.repeat_intention == null ? "" : d.repeat_intention ? "yes" : "no"} onChange={v => set("repeat_intention", v === "yes")} />
      </> : (
        <Chips label="Kenapa tidak jadi?" options={{ SCHEDULE_MISMATCH: "Jadwal bentrok", NO_RESPONSE: "Teman tidak datang", USER_WITHDRAWAL: "Saya batal", OTHER: "Lainnya" }}
          value={d.reason_code} onChange={v => set("reason_code", v)} />
      )}
      <Field label="Catatan (boleh kosong)"><textarea rows={2} maxLength={500} value={d.comments || ""} onChange={e => set("comments", e.target.value)} /></Field>
      <Button busy={busy} onClick={send}>Kirim penilaian</Button>
    </Sheet>
  );
}
