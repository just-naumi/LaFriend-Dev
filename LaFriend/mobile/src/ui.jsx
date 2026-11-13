import { useEffect, useId, useRef } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

export const GOAL = { UNDERSTAND: "Memahami materi", PRACTICE: "Latihan soal", EXAM_PREP: "Persiapan ujian", ASSIGNMENT: "Mengerjakan tugas", DISCUSSION: "Diskusi", KNOWLEDGE_SHARING: "Berbagi pengetahuan" };
export const STYLE = { DISCUSSION: "Diskusi", PRACTICE: "Latihan bersama", TEACHING: "Saling mengajari", FOCUS_STUDY: "Belajar fokus" };
export const MODE = { OFFLINE: "Tatap muka", ONLINE: "Online", HYBRID: "Campuran" };
export const FACTOR = [["t", "Materi"], ["g", "Tujuan"], ["s", "Gaya"], ["d", "Waktu"], ["m", "Metode"]];
export const REASON = {
  GROUP_SIZE: "belum ada cukup teman yang jadwal dan ukuran kelompoknya cocok", SCHEDULE_MISMATCH: "jadwalnya tidak disepakati",
  NO_RESPONSE: "undangan tidak dijawab", USER_WITHDRAWAL: "undangan ditolak", TOPIC_MISMATCH: "materinya tidak cocok",
  GOAL_MISMATCH: "tujuannya tidak cocok", STYLE_MISMATCH: "gaya belajarnya tidak cocok", OTHER: "alasan lain",
};
export const WEEKDAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];
export const spring = { type: "spring", stiffness: 420, damping: 32 };

// Satu keluarga ikon garis (viewBox 24, stroke 1.8) supaya semua ikon seragam
const ICONS = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  pen: "M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19l-4 1z",
  users: "M9 11.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4zM3 20c.6-3.4 3-5.5 6-5.5s5.4 2.1 6 5.5M16 4.8a3.2 3.2 0 0 1 0 6.4M18 14.8c1.8.6 3 2.4 3.3 5",
  chart: "M4 20h16M7 20v-7M12 20V5M17 20v-10",
  chat: "M4 5h16v11H9l-5 4z",
  mic: "M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  form: "M5 4h14v16H5zM8 9h8M8 13h8M8 17h5",
  arrow: "M5 12h14M13 6l6 6-6 6",
  send: "M12 19V5M6 11l6-6 6 6",
  x: "M6 6l12 12M18 6L6 18",
  back: "M19 12H5M11 18l-6-6 6-6",
  reset: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
};
export const Icon = ({ name, size = 22 }) => (
  <svg className="ic" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true"><path d={ICONS[name]} /></svg>
);

export function fmtDay(d) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d || "")) return d;
  return new Date(`${d}T00:00:00`).toLocaleDateString("id-ID", { weekday: "short", day: "numeric", month: "short" });
}
export const fmtSlot = s => `${fmtDay(s.day)}, ${s.start_time || s.start}–${s.end_time || s.end}`;

export function Logo({ size = 40, animate = false }) {
  const reduce = useReducedMotion();
  const a = animate && !reduce;
  return (
    <motion.span className="logo" style={{ fontSize: size * 1.25, width: size, height: size }} aria-hidden="true"
      initial={a ? { scale: 2.2, opacity: 0, filter: "blur(12px)", rotate: -8 } : false}
      animate={{ scale: 1, opacity: 1, filter: "blur(0px)", rotate: 0 }} transition={{ ...spring, delay: 0.1 }}>
      L
    </motion.span>
  );
}

export function Button({ kind = "primary", busy, children, className = "", ...rest }) {
  return (
    <motion.button type="button" whileTap={{ scale: 0.96 }} className={`btn ${kind} ${className}`}
      aria-busy={busy || undefined} disabled={busy || rest.disabled} {...rest}>
      {busy ? <span className="dots" aria-label="Memproses"><i /><i /><i /></span> : children}
    </motion.button>
  );
}

export function Chips({ label, options, value, onChange, missing }) {
  const id = useId();
  return (
    <div className={`field${missing ? " missing" : ""}`} role="radiogroup" aria-label={label}>
      <span className="lab">{label}{missing && <em> belum diisi</em>}</span>
      <div className="chips">
        {Object.entries(options).map(([k, text]) => {
          const on = String(value) === String(k);
          return (
            <button key={k} type="button" role="radio" aria-checked={on} className={`chip${on ? " on" : ""}`} onClick={() => onChange(k)}>
              {on && <motion.span layoutId={id} className="chip-bg" transition={spring} />}
              <span>{text}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function Field({ label, hint, missing, children }) {
  return (
    <label className={`field${missing ? " missing" : ""}`}>
      <span className="lab">{label}{missing && <em> belum diisi</em>}</span>
      {children}
      {hint && <small className="hint">{hint}</small>}
    </label>
  );
}

export function Sheet({ open, onClose, title, children }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement;
    const onKey = e => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    setTimeout(() => ref.current?.querySelector("button, input, select, textarea")?.focus(), 50);
    return () => { window.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="sheet-wrap" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div ref={ref} className="sheet" role="dialog" aria-modal="true" aria-label={title}
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }} transition={spring} onClick={e => e.stopPropagation()}>
            <span className="grip" aria-hidden="true" />
            <h2>{title}</h2>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Orb({ active, size = 180 }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={`orb${active ? " live" : ""}`} style={{ width: size, height: size }} aria-hidden="true"
      animate={active && !reduce ? { scale: [1, 1.08, 0.97, 1.05, 1], rotate: [0, 8, -6, 4, 0] } : { scale: 1 }}
      transition={active ? { duration: 2.4, repeat: Infinity, ease: "easeInOut" } : spring}>
      <i className="orb-core" /><i className="orb-shine" />
    </motion.div>
  );
}

export function Confetti({ run }) {
  const reduce = useReducedMotion();
  if (!run || reduce) return null;
  const colors = ["var(--coral)", "var(--sun)", "var(--lime)", "var(--sky)"];
  return (
    <div className="confetti" aria-hidden="true">
      {Array.from({ length: 22 }, (_, i) => (
        <motion.i key={`${run}-${i}`} style={{ background: colors[i % 4] }}
          initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
          animate={{ x: Math.cos(i * 1.7) * (90 + (i % 5) * 30), y: [0, -160 - (i % 4) * 40, 320], opacity: [1, 1, 0], rotate: i * 47 }}
          transition={{ duration: 1.6, ease: "easeOut" }} />
      ))}
    </div>
  );
}

export function Page({ children, k }) {
  return (
    <motion.section key={k} className="page" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.22, ease: "easeOut" }}>
      {children}
    </motion.section>
  );
}
