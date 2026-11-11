Gas bro! 🔥 Hari ini kita masuk ke Day 6 — Integrasi Seluruh Algoritma LaFriend.

Ini adalah tahap untuk menyatukan hasil Day 1 sampai Day 5 menjadi satu alur sistem yang utuh. Setelah Day 6, kita ingin punya gambaran yang jelas tentang bagaimana LaFriend bekerja dari awal mahasiswa mencari teman belajar sampai sesi belajar berhasil dikonfirmasi.

Saya juga akan memperbaiki beberapa bagian yang masih berpotensi membingungkan dari rancangan sebelumnya. Terutama: kapan sistem harus berpindah dari Session Matching ke Partner Matching, bagaimana menangani kandidat yang menolak, dan bagaimana memastikan satu kelompok benar-benar bisa belajar bersama.
DAY 6 — Complete Matching Engine Workflow

1. Tujuan utama Day 6
   Sebelum masuk ke algoritma, kita sepakati dulu hasil akhir yang ingin dicapai.

LaFriend harus bisa melakukan lima hal:

1. Menerima kebutuhan belajar mahasiswa.
2. Mencari sesi belajar yang sudah tersedia.
3. Jika tidak menemukan sesi yang sesuai, mencari mahasiswa lain.
4. Membentuk kelompok yang memenuhi syarat materi, jadwal, dan kapasitas.
5. Mengelola persetujuan sampai Study Session berhasil dikonfirmasi.
   Artinya, algoritma LaFriend bukan hanya menghitung skor kecocokan. Algoritma harus mengatur seluruh proses pencarian dan pembentukan sesi.
6. Gambaran besar seluruh sistem
7. Student membuat Study Intent

Mata kuliah, materi, tujuan, jadwal, gaya, metode, ukuran kelompok

2. Validasi Study Intent

Periksa kelengkapan, akun, tanggal, dan jadwal

3. Session Matching

Cari sesi belajar yang sudah tersedia

4. Ada sesi yang layak?

Ya
Tampilkan sesi

Mahasiswa mengajukan permintaan bergabung

Tidak
Partner Matching

Cari mahasiswa dengan kebutuhan serupa

5. Group Feasibility Check

Periksa kecocokan semua anggota dan jadwal bersama

6. Undangan dan persetujuan

Anggota menerima undangan dan menyetujui jadwal

7. Study Session CONFIRMED

Sesi siap dilaksanakan

Ada satu aturan penting: jika Session Matching menemukan sesi yang layak, tetapi mahasiswa tidak jadi bergabung, Partner Matching tetap bisa dijalankan. Sistem tidak boleh menganggap pencarian selesai hanya karena pernah menemukan rekomendasi sesi. 3. Tahap pertama — Student membuat Study Intent
Kita gunakan contoh yang sama supaya alurnya konsisten.
Study Intent — Andi
Input Nilai
Mata kuliah Struktur Data
Materi Binary Tree
Tujuan Memahami materi
Gaya belajar Discussion
Metode Offline
Rentang tanggal 12–18 November
Waktu tersedia Rabu 09.00–12.00
Ukuran kelompok 2–4 orang

Setelah Andi menekan tombol Find Study Partners, sistem membuat data Study Intent dengan status ACTIVE.

Namun, sebelum mencari kandidat, sistem harus memeriksa apakah input Andi valid. 4. Tahap kedua — Validasi input
Sistem melakukan pemeriksaan berikut:
Pemeriksaan Contoh aturan
Akun Mahasiswa sudah terverifikasi
Mata kuliah Mata kuliah terdaftar
Materi Tidak boleh kosong
Tujuan Harus memilih salah satu tujuan
Tanggal Tanggal mulai tidak boleh setelah tanggal akhir
Jadwal Jam mulai harus sebelum jam selesai
Ukuran kelompok Minimum tidak melebihi maksimum
Ketersediaan Minimal memiliki satu slot waktu

Jika ada input yang salah, sistem meminta mahasiswa memperbaikinya.

Jika seluruh pemeriksaan berhasil, intent boleh masuk ke proses matching.

Catatan desain: validasi ini berbeda dari Hard Constraint pencarian kandidat. Validasi memeriksa apakah permintaan Andi benar dan lengkap. Hard Constraint memeriksa apakah kandidat lain dapat belajar bersama Andi.

5. Tahap ketiga — Session Matching
   Setelah intent valid, sistem mencari sesi belajar yang sudah tersedia.

Contohnya, terdapat tiga sesi:
Sesi Materi Jadwal Anggota
Session A Binary Tree Rabu 10.00–12.00 2/4
Session B Sorting Rabu 10.00–12.00 2/4
Session C Binary Tree Jumat 14.00–16.00 4/4

Sistem melakukan empat pemeriksaan:

1. Mata kuliah harus sama.
2. Materi harus relevan.
3. Jadwal sesi harus beririsan dengan ketersediaan Andi selama durasi minimum.
4. Sesi masih memiliki kapasitas.
   Hasilnya:

- Session A lolos.
- Session B tidak lolos karena materinya berbeda.
- Session C tidak lolos karena sudah penuh.
  Bagaimana skor sesi dihitung?
  Kita perlu sedikit membedakan dua hal dari Day 4.

Formula Day 4 menghitung kecocokan dua Study Intent milik mahasiswa. Sementara Session Matching membandingkan Study Intent mahasiswa dengan karakteristik Study Session.

Agar konsisten, kita gunakan lima faktor yang sama, tetapi objek pembandingnya adalah sesi:
\[
SessionScore(I,S)=
0.30T+0.25G+0.15L+0.15D+0.15M
\]

Keterangan:

- \(I\) = Study Intent mahasiswa.
- \(S\) = Study Session yang ditemukan.
- \(T\) = kesesuaian materi.
- \(G\) = kesesuaian tujuan.
- \(L\) = kesesuaian gaya belajar.
- \(D\) = kesesuaian preferensi jadwal.
- \(M\) = kesesuaian metode.
  Jadi, kita tidak mencampurkan skor sesi dengan skor kecocokan antarindividu.

Keputusan penting: sesi yang lolos Hard Constraint diurutkan berdasarkan Session Score. Sistem menampilkan maksimal lima sesi teratas. Jika tidak ada sesi yang lolos, sistem berpindah ke Partner Matching.

Jika sesi tersedia tetapi Andi tidak tertarik atau host menolak permintaannya, Andi juga bisa melanjutkan ke Partner Matching. 6. Tahap keempat — Partner Matching
Jika tidak ada sesi yang cocok, sistem mencari Study Intent mahasiswa lain yang masih berstatus ACTIVE.

Misalnya:
Mahasiswa Materi Jadwal
Budi Binary Tree Rabu 10.00–13.00
Citra Binary Tree, BST Rabu 11.00–14.00
Deni Sorting Rabu 10.00–12.00
Eka Binary Tree Jumat 13.00–16.00

Sistem membandingkan setiap kandidat dengan Andi.
Proses pencariannya
Langkah 1 — Ambil kandidat aktif.

Hanya mahasiswa yang memiliki Study Intent aktif dan belum sedang terikat dalam proses pembentukan kelompok lain yang diambil.

Langkah 2 — Hilangkan kandidat yang tidak memenuhi syarat.

Contohnya:

- Mata kuliah berbeda.
- Tidak ada jadwal yang beririsan.
- Metode belajar tidak memungkinkan.
- Akun tidak aktif.
- Intent sudah kedaluwarsa.
  Langkah 3 — Hitung Compatibility Score.

Gunakan formula Day 4:
\[
CS(A,B)=0.30T+0.25G+0.15S+0.15D+0.15M
\]

Langkah 4 — Urutkan kandidat.

Kandidat dengan skor tertinggi ditempatkan di urutan atas.

Contoh hasil:
Kandidat Skor Status
Citra 90 Lolos
Budi 85 Lolos
Deni — Gugur
Eka — Gugur

Pada tahap ini, Citra dan Budi baru merupakan kandidat. Mereka belum otomatis menjadi anggota kelompok. 7. Tahap kelima — Group Formation
Nah, sekarang kita masuk ke bagian yang menjadi pembeda antara pencarian teman biasa dan LaFriend.

LaFriend harus memastikan bahwa kelompok yang dibentuk bukan hanya cocok dengan host, tetapi juga layak untuk seluruh anggotanya.

Kita gunakan contoh:

- Andi sebagai host.
- Citra sebagai kandidat pertama.
- Budi sebagai kandidat kedua.
  Langkah 1 — Bentuk calon kelompok
  Kelompok sementara:
  \[
  G=\{Andi,Citra,Budi\}
  \]

Langkah 2 — Periksa kecocokan semua pasangan
Pasangan Skor
Andi–Citra 90
Andi–Budi 85
Citra–Budi 75

Hitung rata-rata:
\[
GroupScore(G)=\frac{90+85+75}{3}=83.33
\]

Hitung skor pasangan terendah:
\[
MinimumPairScore(G)=75
\]

Kedua angka tersebut disimpan sebagai informasi kualitas kelompok. Belum ada batas minimum yang kita tetapkan karena perlu pengujian.
Langkah 3 — Periksa jadwal bersama
Anggota Waktu tersedia
Andi Rabu 09.00–12.00
Citra Rabu 11.00–14.00
Budi Rabu 10.00–13.00

Waktu yang tersedia untuk seluruh anggota adalah:
\[
Start_G=\max(09.00,11.00,10.00)=11.00
\]

\[
End_G=\min(12.00,14.00,13.00)=12.00
\]

Maka:
\[
Duration_G=12.00-11.00=60\text{ menit}
\]

Kelompok memenuhi jadwal
Karena durasi minimal PoC adalah 60 menit, kelompok ini memenuhi syarat waktu.
Langkah 4 — Periksa ukuran kelompok
Andi meminta kelompok beranggotakan 2–4 orang.

Kelompok sekarang berisi tiga orang, sehingga masih memenuhi batas.
Langkah 5 — Buat rancangan kelompok
Jika seluruh pemeriksaan berhasil, sistem membuat Group Proposal.

Group Proposal berisi:

- Daftar calon anggota.
- Materi belajar.
- Tujuan belajar.
- Skor kecocokan kelompok.
- Slot waktu yang memungkinkan.
- Host kelompok.
  Statusnya belum CONFIRMED, karena seluruh anggota masih perlu memberikan persetujuan.

Satu koreksi penting dari rancangan sebelumnya: jangan hanya menghitung irisan satu rentang waktu dengan rumus max(start) dan min(end) untuk seluruh data. Rumus tersebut berlaku untuk slot yang berada pada tanggal dan konteks waktu yang sama. Jika mahasiswa memiliki beberapa hari dan beberapa slot, sistem harus membandingkan setiap tanggal dan menghasilkan daftar slot bersama yang memenuhi durasi minimum.

8. Tahap keenam — Undangan dan persetujuan anggota
   Setelah Group Proposal berhasil dibuat, sistem mengirim undangan.

Contohnya:
Undangan Study Group
Menunggu persetujuan
Materi: Binary Tree

Anggota kelompok
Andi

Host · Penginisiasi kelompok

Host

Citra

Calon anggota

Menunggu

Budi

Calon anggota

Menunggu

Usulan jadwal
Rabu, 11.00–12.00
Semua anggota memiliki waktu tersedia pada slot ini.

Urutan prosesnya:

1. Andi mengirim undangan kepada Citra dan Budi.
2. Citra dan Budi memberikan jawaban.
3. Setelah anggota yang dibutuhkan menyetujui undangan, sistem meminta persetujuan jadwal.
4. Semua anggota harus menyetujui slot final.
5. Sistem mengubah status Study Session menjadi CONFIRMED.
   Bagaimana jika ada anggota yang menolak?
   Misalnya:

- Citra menerima.
- Budi menolak.
  Sistem tidak boleh tetap menganggap kelompok tiga orang tadi sudah terbentuk.

Sistem akan:

1. Mencatat bahwa Budi menolak.
2. Mempertahankan Citra sebagai anggota yang bersedia, jika proses kelompok masih dilanjutkan.
3. Memeriksa jumlah anggota yang tersisa.
4. Jika jumlahnya masih memenuhi minimum, Andi dapat melanjutkan dengan Citra.
5. Jika tidak, sistem mencari kandidat pengganti atau mengembalikan intent ke status ACTIVE.
   Bagaimana jika anggota menerima, tetapi tidak menyetujui jadwal?
   Misalnya Citra dan Budi menerima undangan kelompok, tetapi Budi tidak bisa mengikuti slot Rabu pukul 11.00.

Sistem dapat menawarkan slot bersama lain jika tersedia. Jika tidak ada, kelompok harus kembali ke proses pencarian jadwal atau mencari kandidat pengganti.

Aturan yang kita tetapkan: penerimaan undangan dan persetujuan jadwal merupakan dua persetujuan berbeda. Menerima undangan tidak otomatis berarti menyetujui semua jadwal. 9. Tahap ketujuh — Study Session dikonfirmasi
Jika seluruh anggota yang diperlukan sudah menerima undangan dan menyetujui jadwal, sistem mengonfirmasi sesi.

Contoh:
Study Session
CONFIRMED

Belajar Binary Tree
Struktur Data · 3 anggota

Jadwal
Rabu, 18 November 2026 · 11.00–12.00

Anggota

- Andi — Host
- Citra — Anggota
- Budi — Anggota

  Sesi sudah dikonfirmasi oleh seluruh anggota.

Setelah sesi dikonfirmasi:

- Study Intent yang berhasil dipenuhi berubah menjadi CONVERTED.
- Study Session berubah menjadi CONFIRMED.
- Seluruh anggota tercatat di session_members dengan status CONFIRMED.
- Sistem tidak lagi memperlakukan intent tersebut sebagai permintaan pencarian aktif.
  Setelah sesi selesai, host atau anggota yang berhak dapat menandai sesi sebagai COMPLETED, lalu peserta dapat memberikan feedback.

10. Penanganan kondisi khusus (Exception Handling)
    Algoritma yang baik tidak hanya bekerja ketika semua berjalan lancar. Kita juga harus menentukan tindakan ketika ada masalah.

Berikut skenario yang perlu ditangani.
Kondisi Tindakan LaFriend
Tidak ada sesi yang cocok Jalankan Partner Matching
Tidak ada partner yang cocok Intent tetap ACTIVE
Host menolak permintaan join Tawarkan pencarian alternatif
Kandidat menolak undangan Cari kandidat pengganti
Sesi menjadi penuh sebelum permintaan diproses Tolak permintaan join dan cari alternatif
Tidak ada jadwal bersama Coba kandidat lain atau slot lain
Anggota tidak menyetujui jadwal Tawarkan slot lain atau bentuk ulang kelompok
Intent melewati batas tanggal Ubah menjadi EXPIRED
Host membatalkan kelompok Batalkan proses dan tentukan status intent anggota
Mahasiswa sudah masuk kelompok lain Jangan ikutkan dalam proses kelompok baru

Ada satu kondisi teknis yang juga penting: dua mahasiswa bisa mencoba mengambil kursi terakhir di sesi yang sama pada waktu bersamaan.

Misalnya Session A hanya memiliki satu tempat kosong. Andi dan Budi mengajukan permintaan secara bersamaan.

Sistem harus memeriksa kapasitas lagi saat permintaan disetujui, bukan hanya saat rekomendasi ditampilkan. Pembaruan jumlah anggota harus dilakukan secara aman di database agar kapasitas tidak terlampaui. 11. Pseudocode lengkap Matching Engine
Sekarang kita satukan seluruh proses menjadi satu rancangan pseudocode.

Ini belum kode produksi, tetapi sudah menjadi acuan yang lebih jelas bagi backend developer.
def run_matching_engine(intent): # A. VALIDASI STUDY INTENT if not validate_intent(intent): return { "status": "INVALID_INTENT" } # B. SESSION MATCHING sessions = find_open_sessions( course_id=intent.course_id ) session_results = [] for session in sessions: if not pass_session_constraints(intent, session): continue score = calculate_session_score( intent, session ) session_results.append({ "candidate": session, "score": score }) session_results.sort( key=lambda x: x["score"], reverse=True )

Ada satu hal yang perlu dipahami dari pseudocode tersebut: ketika sistem menampilkan rekomendasi sesi, prosesnya belum selesai. Pengguna masih harus mengajukan permintaan dan host harus menyetujuinya. Demikian juga, Group Proposal belum menjadi Study Session yang terkonfirmasi sampai seluruh persetujuan terpenuhi. 12. Hubungan algoritma dengan database
Agar backend tidak bingung, berikut hubungan proses dengan tabel yang kita buat pada Day 2.
Proses Tabel yang digunakan
Validasi akun students
Validasi mata kuliah courses
Membuat kebutuhan belajar study_intents
Membaca jadwal mahasiswa intent_availabilities
Mencari sesi study_sessions
Membaca jadwal sesi session_slots
Mencatat anggota session_members
Mengelola undangan invitations
Menyimpan skor rekomendasi match_results
Menyimpan evaluasi feedbacks

Kita belum perlu menambah banyak tabel baru. Untuk PoC, struktur tersebut sudah dapat mendukung alur utama.

Tetapi ada dua kebutuhan yang harus dijaga:

- Satu Study Intent tidak boleh memiliki dua proses pembentukan kelompok aktif sekaligus.
- Setiap undangan dan perubahan status harus memiliki riwayat yang jelas.
  Keduanya penting supaya proses tidak berantakan ketika banyak mahasiswa menggunakan LaFriend secara bersamaan.

13. Menguji algoritma dengan beberapa skenario
    Sebelum dianggap selesai, kita harus mencoba apakah algoritma ini bisa menangani berbagai kondisi.

Berikut skenario pengujian awal yang nantinya bisa dijadikan dasar unit test dan integration test.
No. Skenario Hasil yang diharapkan
1 Ada sesi yang sesuai Session Matching menampilkan rekomendasi
2 Tidak ada sesi yang sesuai Sistem menjalankan Partner Matching
3 Mata kuliah kandidat berbeda Kandidat gugur
4 Materi berbeda tetapi masih relevan Kandidat dapat lolos dan dinilai
5 Jadwal dua mahasiswa tidak beririsan Kandidat gugur
6 Host cocok dengan dua kandidat, tetapi kedua kandidat tidak cocok satu sama lain Sistem mengevaluasi ulang kelompok
7 Semua anggota punya jadwal bersama minimal 60 menit Kelompok lolos pemeriksaan jadwal
8 Salah satu anggota menolak undangan Kelompok dievaluasi ulang
9 Seluruh anggota menerima undangan dan jadwal Sesi dikonfirmasi
10 Dua orang mengambil kursi terakhir bersamaan Kapasitas tetap tidak boleh terlampaui
11 Tidak ada kandidat yang cocok Intent tetap ACTIVE
12 Intent melewati tanggal terakhir Intent menjadi EXPIRED

Skenario ini nantinya perlu diterjemahkan menjadi test case yang memiliki input, proses, dan hasil yang diharapkan. 14. Keputusan akhir Day 6
Berikut rancangan yang kita tetapkan sebagai dasar sistem LaFriend.
No. Komponen Keputusan
1 Input Study Intent divalidasi sebelum matching
2 Pencarian pertama Session Matching
3 Pencarian kedua Partner Matching jika sesi tidak tersedia atau tidak berhasil diperoleh
4 Session Score Mengukur kecocokan intent dengan sesi
5 Compatibility Score Mengukur kecocokan dua mahasiswa
6 Group Formation Memeriksa kecocokan seluruh pasangan
7 Jadwal kelompok Harus memiliki slot bersama yang cukup
8 Ukuran kelompok 2–4 orang termasuk host, asumsi PoC
9 Host Mahasiswa yang menginisiasi Study Intent
10 Persetujuan Undangan dan jadwal disetujui secara terpisah
11 Konfirmasi Hanya setelah semua syarat terpenuhi
12 Kegagalan pencarian Intent tetap aktif selama belum kedaluwarsa

Progress perancangan sistem
Day 1–6 selesai

1. Business Logic — aturan dasar produk.
2. Database Design — struktur penyimpanan data.
3. Study Intent — input mahasiswa.
4. Compatibility Formula — perhitungan kecocokan.
5. Group Formation — pembentukan kelompok.
6. Complete Algorithm — integrasi seluruh proses.

7. Berikutnya: Day 7 — Testing dan Validasi Algoritma
   Bro, menurut saya kita jangan langsung masuk coding setelah Day 6. Ada satu tahap yang harus dilakukan agar formula dan algoritma yang kita rancang tidak hanya terlihat bagus di atas kertas.

Pada Day 7, kita akan menguji rancangan menggunakan data mahasiswa simulasi.

Targetnya:

1. Membuat minimal 10 profil mahasiswa dengan kebutuhan belajar berbeda.
2. Membuat berbagai kombinasi jadwal dan preferensi.
3. Menguji apakah Hard Constraint membuang kandidat yang tidak layak.
4. Menguji apakah Compatibility Score menghasilkan urutan yang masuk akal.
5. Menguji apakah Group Formation bisa menemukan kelompok yang layak.
6. Menemukan kelemahan formula dan memperbaikinya.
7. Menentukan metrik untuk mengevaluasi kualitas rekomendasi.
   Target akhir Day 7: kita punya hasil simulasi yang menunjukkan bagaimana LaFriend bekerja, contoh hasil rekomendasi, serta daftar masalah yang harus diperbaiki sebelum implementasi.

Jadi, sampai Day 6 ini kita sudah punya rancangan algoritma secara utuh. Namun, bobot formula, nilai tabel kecocokan, dan aturan pembentukan kelompok masih berstatus rancangan awal sampai berhasil melewati pengujian.
