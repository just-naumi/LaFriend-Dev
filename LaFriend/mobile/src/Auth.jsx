import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { api } from "./api.js";
import { Button, Chips, Field, Logo, MODE, Page, STYLE, spring } from "./ui.jsx";

export function Splash({ onDone }) {
  const reduce = useReducedMotion();
  useEffect(() => {
    const t = setTimeout(onDone, reduce ? 0 : 2100);
    return () => clearTimeout(t);
  }, [onDone, reduce]);
  const word = "LaFriend".split("");
  return (
    <motion.button type="button" className="splash" onClick={onDone} aria-label="Lewati animasi pembuka"
      exit={{ opacity: 0, scale: 1.04 }} transition={{ duration: 0.35 }}>
      <Logo size={64} animate />
      <span className="splash-word" aria-hidden="true">
        {word.map((ch, i) => (
          <motion.span key={i} initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
            transition={{ ...spring, delay: 0.55 + i * 0.05 }}>{ch}</motion.span>
        ))}
      </span>
      <motion.small initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.2 }}>Teman belajar yang jadwalnya cocok</motion.small>
    </motion.button>
  );
}

export function Auth({ onIn }) {
  const [mode, setMode] = useState("welcome");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = k => e => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const body = mode === "daftar" ? form : { email: form.email, password: form.password };
      onIn(await api(mode === "daftar" ? "/api/register" : "/api/login", body));
    } catch (x) { setErr(x.message); }
    setBusy(false);
  }

  return (
    <main className="auth">
      <AnimatePresence mode="wait">
        {mode === "welcome" ? (
          <Page key="w">
            <div className="hero-orbit" aria-hidden="true"><Logo size={56} /></div>
            <h1 className="display">Belajar bareng,<br /><span className="hl">tanpa ribet</span> cari jadwal.</h1>
            <p className="lead">Tulis mau belajar apa dan kapan kosong. LaFriend mencarikan teman satu mata kuliah yang waktunya cocok, lalu membantu membentuk kelompok.</p>
            <div className="stack-btn">
              <Button onClick={() => setMode("daftar")}>Buat akun</Button>
              <Button kind="ghost" onClick={() => setMode("masuk")}>Saya sudah punya akun</Button>
            </div>
          </Page>
        ) : (
          <Page key={mode}>
            <button type="button" className="back" onClick={() => { setMode("welcome"); setErr(""); }}>← Kembali</button>
            <h1 className="display sm">{mode === "daftar" ? "Buat akun" : "Masuk"}</h1>
            <form className="form" onSubmit={submit} noValidate>
              {mode === "daftar" && (
                <Field label="Nama lengkap"><input autoComplete="name" value={form.name} onChange={set("name")} required /></Field>
              )}
              <Field label="Email"><input type="email" inputMode="email" autoComplete="email" value={form.email} onChange={set("email")} required /></Field>
              <Field label="Password" hint={mode === "daftar" ? "Minimal 8 karakter." : null}>
                <span className="pw">
                  <input type={show ? "text" : "password"} autoComplete={mode === "daftar" ? "new-password" : "current-password"}
                    value={form.password} onChange={set("password")} required />
                  <button type="button" className="link" onClick={() => setShow(!show)} aria-pressed={show}>{show ? "Sembunyikan" : "Lihat"}</button>
                </span>
              </Field>
              {err && <p className="error" role="alert">{err}</p>}
              <Button busy={busy} type="submit">{mode === "daftar" ? "Daftar" : "Masuk"}</Button>
              {mode === "masuk" && (
                <button type="button" className="link center" onClick={() => setForm({ ...form, email: "andi@student.telkomuniversity.ac.id", password: "password123" })}>
                  Isi dengan akun contoh (Andi)
                </button>
              )}
            </form>
          </Page>
        )}
      </AnimatePresence>
    </main>
  );
}

const STEPS = ["gmail", "identity", "campus", "how", "group"];

export function Onboarding({ st, act }) {
  const a = st.account;
  const first = { gmail: 0, profile: 1, prefs: 3 }[a.onboarding] ?? 3;
  const [i, setI] = useState(first);
  const [gmail, setGmail] = useState(a.gmail || (a.email.endsWith("@gmail.com") ? a.email : ""));
  const [p, setP] = useState({ name: a.name || "", nim: a.nim || "", university: a.university || "", program: a.program || "", cohort: a.cohort || "" });
  const [pr, setPr] = useState(a.prefs || { learning_mode: "", collaboration_style: "", group_size: [2, 4], language: "id", campus_area: "" });
  const [busy, setBusy] = useState(false);
  const step = STEPS[i];

  async function next() {
    setBusy(true);
    let ok = true;
    if (step === "gmail") {
      await new Promise(r => setTimeout(r, 700)); // jeda kecil supaya terasa menghubungkan
      ok = await act(() => api("/api/gmail", { email: gmail }), { keep: true });
    }
    if (step === "campus") ok = await act(() => api("/api/profile", { ...p, cohort: Number(p.cohort) }, "PUT"), { keep: true });
    if (step === "group") ok = await act(() => api("/api/prefs", pr, "PUT"));
    setBusy(false);
    if (ok && i < STEPS.length - 1) setI(i + 1);
  }

  const canNext = {
    gmail: gmail.includes("@"), identity: p.name.trim().length > 1 && p.nim.trim(), campus: p.university && p.program && p.cohort,
    how: pr.learning_mode && pr.collaboration_style, group: true,
  }[step];

  return (
    <main className="auth">
      <p className="progress" aria-label={`Langkah ${i + 1} dari ${STEPS.length}`}>
        {STEPS.map((s, n) => <i key={s} className={n <= i ? "on" : ""} />)}
        <span>Langkah {i + 1} dari {STEPS.length}</span>
      </p>
      <AnimatePresence mode="wait">
        <Page key={step}>
          {step === "gmail" && <>
            <h1 className="display sm">Hubungkan akun Gmail</h1>
            <p className="lead">Dipakai untuk memastikan kamu mahasiswa sungguhan. Di versi demo ini tidak ada pengecekan ke Google: akun langsung dianggap terverifikasi.</p>
            <Field label="Alamat Gmail"><input type="email" inputMode="email" value={gmail} onChange={e => setGmail(e.target.value)} placeholder="nama@gmail.com" /></Field>
          </>}
          {step === "identity" && <>
            <h1 className="display sm">Kenalan dulu</h1>
            <Field label="Nama lengkap"><input value={p.name} onChange={e => setP({ ...p, name: e.target.value })} autoComplete="name" /></Field>
            <Field label="NIM" hint="Hanya angka. Tidak ditampilkan ke teman."><input inputMode="numeric" value={p.nim} onChange={e => setP({ ...p, nim: e.target.value.replace(/\D/g, "") })} /></Field>
          </>}
          {step === "campus" && <>
            <h1 className="display sm">Kuliah di mana?</h1>
            <Field label="Universitas"><input value={p.university} onChange={e => setP({ ...p, university: e.target.value })} placeholder="Telkom University" /></Field>
            <Field label="Program studi"><input value={p.program} onChange={e => setP({ ...p, program: e.target.value })} placeholder="S1 Teknik Komputer" /></Field>
            <Field label="Angkatan"><input inputMode="numeric" value={p.cohort} onChange={e => setP({ ...p, cohort: e.target.value.replace(/\D/g, "").slice(0, 4) })} placeholder="2025" /></Field>
          </>}
          {step === "how" && <>
            <h1 className="display sm">Biasanya belajar seperti apa?</h1>
            <p className="lead">Jadi pilihan awal saat kamu membuat permintaan. Selalu bisa diganti.</p>
            <Chips label="Cara belajar" options={STYLE} value={pr.collaboration_style} onChange={v => setPr({ ...pr, collaboration_style: v })} />
            <Chips label="Bertemu" options={MODE} value={pr.learning_mode} onChange={v => setPr({ ...pr, learning_mode: v })} />
          </>}
          {step === "group" && <>
            <h1 className="display sm">Kelompok idealmu</h1>
            <Chips label="Paling sedikit" options={{ 2: "2 orang", 3: "3 orang", 4: "4 orang" }} value={pr.group_size[0]}
              onChange={v => setPr({ ...pr, group_size: [Number(v), Math.max(Number(v), pr.group_size[1])] })} />
            <Chips label="Paling banyak" options={{ 2: "2 orang", 3: "3 orang", 4: "4 orang" }} value={pr.group_size[1]}
              onChange={v => setPr({ ...pr, group_size: [Math.min(Number(v), pr.group_size[0]), Number(v)] })} />
            <Chips label="Bahasa" options={{ id: "Indonesia", en: "English" }} value={pr.language} onChange={v => setPr({ ...pr, language: v })} />
            <Field label="Area kampus (boleh kosong)"><input value={pr.campus_area} onChange={e => setPr({ ...pr, campus_area: e.target.value })} placeholder="Gedung TULT" /></Field>
          </>}
          <div className="stack-btn">
            <Button busy={busy} disabled={!canNext} onClick={next}>
              {step === "gmail" ? "Hubungkan Gmail" : step === "group" ? "Selesai" : "Lanjut"}
            </Button>
            {i > first && <Button kind="ghost" onClick={() => setI(i - 1)}>Kembali</Button>}
          </div>
        </Page>
      </AnimatePresence>
    </main>
  );
}
