let token = null;
try { token = localStorage.getItem("lf-token"); } catch { /* penyimpanan diblokir: tetap jalan tanpa ingat login */ }

export const hasToken = () => !!token;
export function setToken(t) {
  token = t;
  try { t ? localStorage.setItem("lf-token", t) : localStorage.removeItem("lf-token"); } catch { /* sama */ }
}

// Pesan validasi server (bahasa Inggris) diganti kalimat yang dimengerti mahasiswa
const FRIENDLY = {
  email: "Format email belum benar.", password: "Password minimal 8 karakter.", name: "Nama minimal 2 huruf.",
  nim: "NIM berisi 6 sampai 15 angka.", cohort: "Angkatan berupa tahun, misalnya 2025.", topics: "Topik belum diisi.",
  availabilities: "Tambahkan minimal satu waktu kosong.", university: "Universitas belum diisi.", program: "Program studi belum diisi.",
};

export async function api(path, body, method) {
  const r = await fetch(path, {
    method: method || (body === undefined ? "GET" : "POST"),
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    const msg = Array.isArray(d)
      ? [...new Set(d.map(x => FRIENDLY[x.loc?.find(k => FRIENDLY[k])] || String(x.msg).replace(/^Value error, /, "")))].join(" ")
      : d || "Ada yang salah. Coba lagi.";
    const e = new Error(msg);
    e.status = r.status;
    throw e;
  }
  return data;
}
