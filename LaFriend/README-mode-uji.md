# LaFriend: website mode uji (branch `sistem-analogy`)

Website mobile untuk mencoba Fitur 1, 2, dan 3 dari awal sampai akhir oleh satu orang:
membuat permintaan belajar, mendapat teman yang cocok, membentuk kelompok, lalu menilai sesi.
Tampilan ada di `mobile/` (React). Backend demonya `backend/web.py`, memakai logika yang sama
dengan aplikasi utama di `backend/app/`.

## Menjalankan

Butuh Python 3.10+ dan Node.js 18+.

```bash
pip install -r requirements.txt
cd mobile && npm install && npm run build
cd ../backend && python web.py
```

Buka http://127.0.0.1:8020. Akun contoh: `andi@student.telkomuniversity.ac.id` / `password123`.

Untuk mengubah tampilan dengan hot reload, jalankan `python web.py` lalu `npm run dev` di `mobile/`.
Permintaan `/api` dari Vite diteruskan ke port 8020. Hasil `npm run build` masuk ke `backend/web/dist`
dan disajikan oleh `web.py`.

Data disimpan di memori, jadi kembali ke data contoh setiap server dijalankan ulang.

## Mode uji

Aktif dari awal (bisa dimatikan di menu akun, tombol huruf nama di kanan atas). Dengan mode uji:

- undangan dan persetujuan jadwal bisa dijawab atas nama teman, di tab Kelompok;
- sesi bisa dianggap sudah selesai, di tab Hasil, supaya penilaian bisa langsung diisi.

## Fitur dan letak kodenya

| Fitur | Yang dilakukan | Kode |
|---|---|---|
| Permintaan belajar | Lewat chat, suara, atau form. Semua berakhir di layar Periksa sebelum disimpan. | `app/intent_assistant.py`, `mobile/src/Request.jsx` |
| Fitur 1: teman yang cocok | Skor 5 faktor: materi, tujuan, gaya, waktu, metode. Ada syarat wajib sebelum dinilai. | `app/matching.py` |
| Fitur 2: kelompok | Undangan, usulan jadwal, persetujuan semua anggota, lalu sesi terbentuk. | `app/group_formation.py` |
| Fitur 3: hasil | Penilaian sesi dan 5 metrik yang sengaja tidak digabung jadi satu skor. | `app/outcome.py` |

Keputusan angka dan aturan (tabel skor tujuan, gaya, metode) dicatat di `../peta-alur-sistem/KEPUTUSAN.md` (akar repo).

## Model GLiNER fine-tuning

Asisten chat sudah punya jalur untuk model GLiNER hasil fine-tuning (`LaFriend Token Classification/`).
Jalur ini menyala sendiri bila dua syarat terpenuhi:

1. Bobot model ada di `backend/app/weights/gliner_small` dan `backend/app/weights/deberta_v3_small`.
   Folder ini sengaja tidak masuk git. Isinya hasil `05_export_to_production.py` setelah training.
2. Paket `gliner` (dan `torch`) terpasang: `pip install gliner`.

Cara kerjanya (`gliner_fields` di `backend/web.py`):

- setiap pesan chat dikirim ke `process_chat_for_study_intent` di `app/extraction.py`;
- hanya kolom berstatus `EXTRACTED` yang dipakai; yang `NEEDS_REVIEW` atau `MISSING` dibiarkan;
- hasil model menang atas parser kata kunci asisten, dan kolom yang tidak ditemukan model tetap diisi parser;
- asisten tetap menanyakan kolom yang masih kosong, dan semua hasil tetap lewat layar Periksa.

Tanpa model, asisten berjalan seperti biasa memakai parser kata kunci. Aturan cadangan di `extraction.py`
sengaja tidak dipakai di jalur ini, karena masih salah membaca "jam 19.00-21.00" sebagai kelompok 21 orang.

Untuk memastikan model terbaca: jalankan `python -c "import web; print(web.GLINER)"` di `backend/`.
Hasil `True` berarti model dipakai.

## Tes

Dari folder `backend/`:

```bash
python test_asisten.py
python test_fitur1.py
python test_fitur2.py
python test_fitur3.py
python test_web.py
```

Semua tes berjalan tanpa pytest dan tanpa model GLiNER. `test_web.py` butuh `httpx` (`pip install httpx`). `test_web.py` meniru hasil model untuk
memeriksa pemetaan kolomnya.

## Belum selesai

- Perubahan `main` Day 12–14 (matching hard constraint, validasi jadwal baru) belum digabung ke branch ini.
  Ada konflik di `app/matching.py`, `app/models.py`, dan `app/schemas.py` yang perlu diselesaikan dengan sengaja.
- Mikrofon asli belum diuji; input suara memakai Web Speech API bawaan browser.
