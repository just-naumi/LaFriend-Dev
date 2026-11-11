# Keputusan Review Peta Alur Sistem (12 November 2026)

Keputusan ini menjawab pertanyaan yang belum dijawab dokumen `Plan/`. Semua angka di sini adalah hipotesis desain. Angka-angka ini harus diuji ulang lewat Fitur 3 sebelum dianggap final.

## Fitur 1: Intent-Based Matching

**1. Nilai G untuk semua pasangan tujuan.**
G hanya menilai apakah cara kedua pihak memakai sesi sejalan. Kesamaan materi tidak dinilai di G karena sudah dihitung di T.

| Pasangan tujuan | G | Asal |
|---|---|---|
| Tujuan sama (kelima tujuan) | 100 | Day4, diperluas |
| Memahami + Latihan soal | 85 | Day4 |
| Memahami + Persiapan ujian | 85 | Day4 |
| Latihan soal + Persiapan ujian | 85 | Day4 |
| Diskusi + Persiapan ujian | 75 | baru |
| Latihan soal + Mengerjakan tugas | 75 | baru |
| Memahami + Diskusi | 70 | baru |
| Diskusi + Latihan soal | 70 | baru |
| Mengerjakan tugas + Memahami | 60 | Day4 |
| Diskusi + Mengerjakan tugas | 60 | baru |
| Persiapan ujian + Mengerjakan tugas | 40 | baru |

Alasan Memahami + Diskusi = 70: sisi "berbagi" cocok dengan mahasiswa yang belum paham, tetapi sisi "diskusi" kurang terpenuhi. Pasangan ini cocok sebagian dan lebih menguntungkan satu pihak, jadi nilainya di antara 60 dan 85.

**2. Pasangan gaya belajar.**
Pengelompokan didasarkan pada apakah kedua gaya butuh berbicara.
- Saling melengkapi (80): Teaching + Practice, Discussion + Practice, Discussion + Teaching.
- Masih bisa bersama (60): Practice + Focus Study.
- Bertentangan (30): Discussion + Focus Study, Teaching + Focus Study.

**3. Nilai D bila ada beberapa waktu bersama.**
D diambil dari waktu bersama dengan nilai tertinggi, dan waktu itu juga yang diusulkan sebagai jadwal sesi. Pilihan ketiga atau lebih rendah dianggap "alternatif terakhir" dengan nilai 60. Contoh: pilihan pertama dengan pilihan ketiga bernilai 60.

**4. Metode belajar.**
- 85: satu pihak memakai pilihan utama, pihak lain memakai pilihan alternatif.
- 70: metode bersama hanya ada di pilihan alternatif kedua pihak.
- Hybrid dianggap cocok dengan Offline maupun Online, karena Day3 menyebut Hybrid "fleksibel antara online dan offline".

**5. Skor sesi yang sudah ada.**
Skor sesi memakai GQ kelompok setelah pencari masuk (rumus Day7), supaya pasangan terlemah di dalam sesi ikut terlihat. Untuk sesi yang baru berisi host, GQ sama dengan CS antara pencari dan host.

**6. Durasi minimum dan ukuran kelompok.**
Nilai awalnya 60 menit dan 2 sampai 4 orang. Keduanya dibuat sebagai pengaturan yang bisa diubah admin, sama seperti batas 24 jam di Day10.

## Fitur 2: Feasibility-Aware Group Formation

**7. Anggota tidak menyetujui jadwal akhir.**
1. Sistem mengusulkan waktu bersama berikutnya dengan nilai D tertinggi, lalu meminta persetujuan lagi.
2. Bila tidak ada waktu bersama lagi, anggota yang menolak dikeluarkan. Sisa anggota dicek terhadap MinGroup. Bila jumlahnya kurang, sistem mencari pengganti.

## Fitur 3: Outcome-Oriented Matching

**8. Session Completion Rate (SCR).**
- Sesi yang sudah CONFIRMED lalu dibatalkan tetap masuk penyebut sebagai sesi tidak terlaksana. Kalau dikeluarkan dari penyebut, SCR terlihat lebih bagus dari kenyataannya.
- Sesi dihitung terlaksana bila host dan minimal satu anggota mengonfirmasi, mengikuti Formula_Sistem.MD. Dengan aturan ini satu orang tidak bisa mengklaim sesi terlaksana sendirian. Bila jawaban mereka bertentangan, sesi ditandai `disputed` dan belum dihitung.

**9. Data minimal untuk menguji bobot.**
Bobot baru baru boleh diuji setelah ada minimal 30 sesi COMPLETED yang punya Session Feedback. Angka 30 ini hipotesis, bukan hasil perhitungan ukuran sampel.

## Keputusan di luar peta

**10. Acuan rumus.**
Rumus CS lima faktor dari `Plan/Day4.MD` menjadi acuan. Rumus di `Struktur_Sistem.MD` (7 kriteria) dan `Formula_Sistem.MD` (6 kriteria, ambang 70) tidak dipakai.

**11. Database untuk PoC.**
SQLite tetap dipakai sesuai Step 1. SQLite tidak punya row locking, tetapi penulisan ke database dikunci satu per satu. Karena itu, pemeriksaan kapasitas dan penambahan anggota dijalankan dalam satu transaksi `BEGIN IMMEDIATE` agar dua orang tidak mengambil tempat terakhir bersamaan. Pindah ke PostgreSQL bisa dilakukan setelah PoC.

**12. Teks bebas dan GLiNER.**
Jalur ini tidak dipakai di PoC. Day4 menetapkan bahwa tahap awal memakai daftar materi yang sudah dinormalisasi. Mahasiswa mengisi form biasa.
