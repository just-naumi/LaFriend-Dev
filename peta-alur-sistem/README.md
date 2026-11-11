# Peta Alur Sistem LaFriend

Peta interaktif cara sistem LaFriend berpikir, disusun dari dokumen di folder `Plan/` (Day3, Day4, Day5, Day7, Day9, Day10). Belum ada kode.

Buka `index.html` di browser. Klik sekali pada kotak untuk melihat penjelasannya, klik dua kali untuk membuka pohon keputusannya.

## Isi

- **Fitur 1, Intent-Based Matching.** Parameter A sampai F adalah syarat wajib. Parameter E dan G sampai J memberi nilai. Rumus: CS = 0,30T + 0,25G + 0,15S + 0,15D + 0,15M. Sistem mencari sesi yang sudah ada lebih dulu, lalu partner.
- **Fitur 2, Feasibility-Aware Group Formation.** Mencakup rentang ukuran kelompok dan irisan jadwal seluruh anggota (minimal 60 menit). Rumus: GQ = 0,70 x rata-rata pasangan + 0,30 x pasangan terendah. Undangan dan persetujuan jadwal masing-masing diberi batas 24 jam.
- **Fitur 3, Outcome-Oriented Matching.** Memakai lima metrik: RAR, GFR, SCR, MSS, dan RSI. Kegagalan dicatat dengan delapan kode alasan. Bobot hanya diubah setelah diuji pada data terpisah.

## File

- `index.html`: peta, bisa dibuka tanpa server.
- `plan.json`, `architecture.json`: sumber peta. Berisi kartu, sambungan, asumsi, dan 9 pertanyaan yang belum diputuskan.

Rumus di `Struktur_Sistem.MD` dan `Formula_Sistem.MD` tidak dipakai di peta ini karena berbeda dengan Day4.
