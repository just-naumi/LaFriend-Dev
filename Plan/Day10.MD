Gas bro! Kita masuk ke Day 10: Status Management & Exception Handling.

Ini salah satu bagian penting sebelum LaFriend mulai diimplementasikan.

Selama Day 1–9, kita sudah merancang bagaimana mahasiswa mencari teman belajar, mendapatkan rekomendasi, membentuk kelompok, menyepakati jadwal, sampai memberikan feedback.

Tetapi, sistem nyata tidak selalu berjalan sesuai rencana.

Contohnya:

- Andi sudah membuat Study Intent, tetapi tiba-tiba membatalkannya.
- Budi sudah menerima undangan, tetapi kemudian ingin keluar.
- Host membatalkan sesi setelah semua anggota menyetujuinya.
- Dua mahasiswa mencoba mengambil satu tempat terakhir secara bersamaan.
- Jadwal sesi berubah setelah kelompok dikonfirmasi.
  Kalau kita tidak menentukan aturan untuk kondisi seperti ini, sistem bisa mengalami masalah: status tidak konsisten, mahasiswa terjebak dalam proses matching, atau kapasitas kelompok melebihi batas.

Target Day 10: kita menentukan seluruh status, perpindahan status, aturan pembatalan, dan cara sistem menangani kondisi gagal.

1. Pahami dahulu konsep status di LaFriend
   Dalam LaFriend, ada beberapa objek yang memiliki perjalanan status masing-masing.

Kita tidak boleh mencampuradukkan status mahasiswa, Study Intent, undangan, dan Study Session.

Contohnya:

Andi membuat Study Intent. Kemudian sistem menemukan Budi. Budi menerima undangan. Setelah itu, mereka membentuk Study Session.

Berarti ada beberapa status berbeda:

- Study Intent Andi: CONVERTED
- Invitation kepada Budi: ACCEPTED
- Study Session: CONFIRMED
- Membership Andi: CONFIRMED
- Membership Budi: CONFIRMED
  Kenapa dipisahkan?

Karena setiap objek memiliki fungsi berbeda. Study Intent menunjukkan kebutuhan belajar, Invitation menunjukkan proses mengajak anggota, sedangkan Study Session menunjukkan kegiatan belajar yang dibentuk. 2. Status Study Intent
Study Intent adalah kebutuhan belajar yang dibuat mahasiswa.

Kita sudah punya beberapa status dari Day 1. Sekarang kita rapikan dan tentukan aturan perpindahannya.
Status Arti sederhana
DRAFT Mahasiswa sedang membuat kebutuhan belajar
ACTIVE Kebutuhan belajar sedang mencari teman atau sesi
GROUP_FORMING Sedang dalam proses membentuk kelompok
JOIN_PENDING Sedang menunggu keputusan host pada permintaan bergabung ke sesi
CONVERTED Kebutuhan belajar sudah berhasil menjadi bagian dari sesi
CANCELLED Mahasiswa membatalkan kebutuhan belajar
EXPIRED Batas waktu pencarian sudah lewat

Bagaimana perpindahan statusnya?
Study Intent Lifecycle
DRAFT
Mahasiswa mengisi kebutuhan belajar

ACTIVE
Kebutuhan belajar siap dicocokkan
Proses kelompok
GROUP_FORMING

CONVERTED

Permintaan bergabung
JOIN_PENDING

CONVERTED

Dari DRAFT atau ACTIVE, mahasiswa juga dapat membatalkan atau sistem dapat mengakhiri pencarian ketika batas waktunya lewat.
CANCELLED
EXPIRED

Ada satu aturan yang harus kita perbaiki dari rancangan sebelumnya.

Jika mahasiswa sedang dalam GROUP_FORMING, lalu calon anggota menolak undangan, Study Intent tidak harus langsung menjadi ACTIVE.

Sistem harus memeriksa dahulu:

- Apakah kelompok masih memenuhi syarat?
- Apakah masih ada kandidat pengganti?
- Apakah proses pembentukan kelompok masih berlangsung?
  Jika masih bisa dilanjutkan, status tetap GROUP_FORMING. Jika proses dihentikan, status dapat kembali menjadi ACTIVE.

Begitu juga dengan JOIN_PENDING. Status ini digunakan ketika mahasiswa mengirim permintaan bergabung ke sesi dan menunggu host. Jika ditolak atau ditarik, Study Intent dapat kembali ke ACTIVE, selama masih dalam masa pencarian. 3. Status Study Session
Study Session adalah kelompok atau sesi belajar yang dibentuk oleh LaFriend.

Kita perlu membedakan antara sesi yang masih berupa rancangan dan sesi yang benar-benar sudah dikonfirmasi.
Status Arti
DRAFT Rancangan kelompok sedang dibuat
OPEN Sesi tersedia dan menerima permintaan bergabung
CONFIRMATION_PENDING Menunggu persetujuan anggota atau jadwal
CONFIRMED Semua persyaratan konfirmasi sudah terpenuhi
COMPLETED Sesi sudah dilaksanakan
CANCELLED Sesi dibatalkan
EXPIRED Sesi tidak lagi berlaku karena batas waktu atau ketentuan tertentu

Alur perpindahan status
Study Session Lifecycle
DRAFT
Kelompok baru dibuat sebagai proposal

OPEN
Sesi siap menerima anggota

CONFIRMATION_PENDING
Menunggu persetujuan akhir

CONFIRMED
Anggota dan jadwal sudah disepakati

COMPLETED
Kegiatan belajar selesai

CANCELLED
EXPIRED

Pembatalan dan kedaluwarsa dapat terjadi pada tahap tertentu sesuai aturan di bawah.
Ada satu hal yang harus diperhatikan.

OPEN tidak berarti sesi sudah dikonfirmasi. Artinya, sesi masih tersedia untuk menerima anggota.

Sedangkan CONFIRMATION_PENDING berarti kelompok sudah memiliki calon anggota, tetapi masih ada persetujuan yang belum selesai.

Untuk PoC, saya menyarankan sesi yang dibuat melalui Partner Matching menggunakan DRAFT terlebih dahulu. Setelah proposal diterima dan jadwal disepakati, sesi menjadi CONFIRMED. Sesi yang memang dibuka oleh host untuk menerima mahasiswa lain dapat menggunakan OPEN. 4. Status Invitation dan Membership
Dua status ini juga harus dibedakan.

Invitation adalah proses mengundang seseorang.

Membership adalah status seseorang sebagai anggota dalam sebuah Study Session.

Contoh:

Andi mengundang Budi untuk bergabung.

Budi menerima undangan. Berarti Invitation menjadi ACCEPTED.

Namun, Budi belum tentu langsung menjadi anggota yang sudah dikonfirmasi karena jadwal kelompok masih harus disetujui.
Status Invitation
Status Arti
PENDING Menunggu jawaban
ACCEPTED Undangan diterima
REJECTED Undangan ditolak
WITHDRAWN Undangan ditarik oleh pengirim
EXPIRED Tidak dijawab sampai batas waktu

Status Membership
Status Arti
REQUESTED Mahasiswa meminta bergabung
INVITED Mahasiswa diundang
ACCEPTED Mahasiswa menerima undangan
CONFIRMED Keanggotaan sudah dikonfirmasi
DECLINED Mahasiswa menolak
WITHDRAWN Mahasiswa mengundurkan diri
REMOVED Anggota dikeluarkan oleh host atau sistem berdasarkan aturan

Jadi, misalnya:

- Budi menerima undangan.
- Invitation = ACCEPTED.
- Membership = ACCEPTED.
- Budi belum CONFIRMED sampai seluruh proses persetujuan jadwal selesai.
  Dengan begitu, tidak ada anggota yang dianggap sudah resmi bergabung sebelum persyaratannya terpenuhi.

5. Aturan menangani kondisi ketika sesuatu gagal
   Sekarang kita bahas bagian paling penting dari Day 10: apa yang harus dilakukan sistem ketika terjadi masalah?

Saya sudah menyusun beberapa skenario yang kemungkinan besar terjadi ketika LaFriend digunakan.
Kasus A — Mahasiswa membatalkan Study Intent
Contoh:

- Andi membuat Study Intent untuk belajar Binary Tree.
- Status Andi ACTIVE.
- Andi berubah pikiran dan tidak ingin mencari teman belajar lagi.
  Tindakan sistem:

1. Andi memilih tombol Batalkan Pencarian.
2. Sistem meminta konfirmasi.
3. Status Study Intent berubah menjadi CANCELLED.
4. Sistem menghentikan pencarian rekomendasi untuk intent tersebut.
5. Jika ada undangan yang masih menunggu respons, undangan tersebut ditarik atau dibatalkan.
6. Jika sudah ada proses kelompok yang melibatkan anggota lain, sistem harus mengevaluasi ulang proses tersebut.
   Jangan sampai Andi sudah membatalkan pencarian, tetapi masih muncul sebagai calon teman belajar.
   Kasus B — Calon anggota menolak undangan
   Contoh:

- Andi membuat kelompok.
- Budi menerima undangan.
- Citra menolak undangan.
  Tindakan sistem:

1. Citra berubah menjadi DECLINED.
2. Sistem mengeluarkan Citra dari proposal kelompok.
3. Sistem menghitung ulang kecocokan kelompok.
4. Sistem memeriksa apakah jumlah anggota masih memenuhi kebutuhan minimum.
5. Jika belum, sistem mencari kandidat pengganti.
6. Jika tidak ada kandidat, proses kelompok dihentikan dan Study Intent yang masih berlaku dikembalikan ke ACTIVE.
   Catatan: penolakan satu orang tidak otomatis membatalkan seluruh kelompok.
   Kasus C — Host membatalkan kelompok
   Contoh:

- Andi adalah host.
- Andi, Budi, dan Citra sudah menyetujui kelompok.
- Sebelum sesi dilaksanakan, Andi membatalkan sesi.
  Tindakan sistem:

1. Study Session berubah menjadi CANCELLED.
2. Semua anggota mendapatkan pemberitahuan.
3. Membership yang sudah dikonfirmasi ditandai sebagai dibatalkan atau ditutup melalui catatan riwayat.
4. Sistem memeriksa apakah Budi dan Citra masih ingin mencari kelompok.
5. Jika masih ingin mencari, mereka dapat membuat Study Intent baru atau mengaktifkan kembali kebutuhan belajar yang sebelumnya belum kedaluwarsa.
   Penting: jangan mengubah semua Study Intent anggota kembali menjadi ACTIVE secara otomatis. Bisa saja mereka sudah tidak membutuhkan sesi tersebut. Minta konfirmasi terlebih dahulu.
   Kasus D — Anggota keluar setelah sesi dikonfirmasi
   Contoh:

- Kelompok Andi, Budi, dan Citra sudah dikonfirmasi.
- Budi tiba-tiba mengundurkan diri.
- Jumlah anggota menjadi dua orang.
  Tindakan sistem:

1. Membership Budi menjadi WITHDRAWN.
2. Sistem memeriksa jumlah anggota tersisa.
3. Sistem memeriksa apakah kelompok masih memenuhi minimum anggota.
4. Jika masih memenuhi, sesi dapat tetap berjalan.
5. Jika tidak memenuhi, host diberi pilihan mencari pengganti atau membatalkan sesi.
   Jika jadwal sudah dekat, sistem tidak boleh otomatis mencari anggota baru tanpa persetujuan host dan anggota yang tersisa.
   Kasus E — Jadwal berubah setelah sesi dikonfirmasi
   Contoh:

- Andi, Budi, dan Citra sudah menyepakati Rabu pukul 11.00.
- Citra ternyata memiliki kegiatan mendadak.
  Tindakan sistem:

1. Citra mengajukan perubahan jadwal.
2. Sistem mencari waktu alternatif yang tersedia bagi seluruh anggota.
3. Host memilih jadwal alternatif.
4. Sistem meminta persetujuan semua anggota.
5. Jadwal baru hanya berlaku setelah seluruh anggota menyetujuinya.
   Selama proses perubahan berlangsung, jadwal lama tetap menjadi jadwal resmi sampai jadwal baru disetujui. Jika jadwal lama sudah tidak memungkinkan, sesi dapat ditandai RESCHEDULE_PENDING melalui status perubahan terpisah.
   Kasus F — Sesi sudah dijadwalkan tetapi tidak terlaksana
   Contoh:

- Sesi seharusnya berlangsung Rabu pukul 11.00.
- Tidak ada anggota yang hadir.
  Tindakan sistem:

1. Sistem meminta konfirmasi pelaksanaan dari host atau anggota.
2. Jika tidak terlaksana, status sesi tidak boleh diubah menjadi COMPLETED.
3. Sistem mencatat alasan, misalnya NO_SHOW atau CANCELLED_BY_HOST.
4. Sistem memberikan kesempatan kepada anggota untuk memberikan keterangan.
5. Data ini digunakan dalam evaluasi Day 9.
   Saya menyarankan NO_SHOW dan alasan pembatalan disimpan sebagai hasil pelaksanaan atau reason code, bukan dicampur dengan status utama Study Session.
6. Bagaimana jika dua mahasiswa mengambil satu tempat terakhir secara bersamaan?
   Ini adalah masalah teknis yang sangat penting.

Bayangkan sebuah sesi memiliki kapasitas empat orang.

Saat ini sudah ada tiga anggota.
Kapasitas sesi belajar
Anggota saat ini

3 dari 4

Tersisa 1 tempat

Budi meminta bergabung
Request A

Citra meminta bergabung
Request B

Kedua permintaan masuk hampir bersamaan.
Kalau sistem tidak berhati-hati, Budi dan Citra bisa sama-sama mendapatkan persetujuan meskipun hanya tersisa satu tempat.

Solusinya adalah menggunakan database transaction dan penguncian saat memperbarui kapasitas.

Logika sederhananya:

1. Budi mengirim permintaan.
2. Citra mengirim permintaan hampir bersamaan.
3. Sistem memeriksa kapasitas di database.
4. Permintaan pertama yang berhasil diproses mendapatkan tempat.
5. Sistem memeriksa ulang kapasitas sebelum memproses permintaan kedua.
6. Permintaan kedua ditolak jika kapasitas sudah penuh.
   Pseudocode:
   def approve_join_request(session_id, request_id): with database_transaction(): # Kunci sesi selama kapasitas diperiksa session = get_session_for_update(session_id) if session.status != "OPEN": return "SESSION_NOT_OPEN" current_members = count_confirmed_members(session_id) if current_members >= session.max_group_size: return "SESSION_FULL" # Periksa kembali permintaan request = get_pending_request(request_id) if request is None: return "REQUEST_NOT_AVAILABLE" approve_request(request_id) return "REQUEST_APPROVED"

Dengan cara ini, database menjadi penentu akhir kapasitas, bukan hanya tampilan aplikasi.

Satu hal lagi: jika host masih harus menyetujui permintaan, kapasitas harus dipertimbangkan saat menyetujui permintaan tersebut. Sistem dapat menggunakan batas reservasi sementara untuk menghindari beberapa permintaan yang menunggu persetujuan menghabiskan tempat yang sama. 7. Aturan jika mahasiswa memiliki beberapa Study Intent
Ini juga harus kita tetapkan.

Contoh:

- Andi membuat Study Intent untuk Struktur Data.
- Andi membuat Study Intent lain untuk Basis Data.
- Kedua kebutuhan tersebut masih aktif.
  Apakah boleh?

Menurut saya, boleh. Karena mahasiswa memang bisa memiliki beberapa kebutuhan belajar yang berbeda.

Namun, kita harus membedakan dua kondisi:

Kondisi pertama: beberapa Study Intent aktif, tetapi belum terikat kelompok.

Boleh. Andi masih dapat mencari kelompok untuk dua mata kuliah.

Kondisi kedua: mahasiswa sudah masuk dalam proses pembentukan kelompok untuk satu Study Intent.

Untuk PoC, saya menyarankan mahasiswa tidak boleh memiliki dua proses pembentukan kelompok aktif yang berjalan bersamaan.

Alasannya sederhana: agar mahasiswa tidak menerima banyak undangan dan proposal yang saling bertabrakan.

Aturannya:

- Boleh memiliki beberapa Study Intent berstatus ACTIVE.
- Hanya boleh terlibat dalam satu Group Formation aktif pada satu waktu.
- Jika sudah masuk dalam Study Session yang dikonfirmasi, mahasiswa tetap boleh memiliki Study Intent lain untuk mata kuliah berbeda.
- Sistem harus memeriksa benturan jadwal sebelum mengonfirmasi sesi kedua.
  Ini membuat LaFriend lebih fleksibel tanpa membuat proses matching terlalu rumit.

8. Bagaimana sistem menangani waktu kedaluwarsa?
   Setiap Study Intent harus mempunyai batas waktu pencarian.

Contoh:

Andi ingin belajar Binary Tree dalam rentang 12–20 November.

Jika sampai 20 November tidak menemukan kelompok, sistem mengubah status menjadi EXPIRED.

Aturan yang saya sarankan:
Kondisi Tindakan
Hari ini masih dalam rentang pencarian Intent tetap aktif
Sudah melewati tanggal terakhir Intent menjadi EXPIRED
Sudah masuk kelompok terkonfirmasi Intent menjadi CONVERTED
Mahasiswa membatalkan Intent menjadi CANCELLED
Proses pembentukan kelompok gagal Intent kembali ACTIVE jika masih berlaku

Untuk Study Session, masa berlaku juga harus ditentukan.

Contohnya:

- Sesi OPEN memiliki batas waktu penerimaan anggota.
- Sesi CONFIRMATION_PENDING memiliki batas waktu persetujuan.
- Sesi CONFIRMED memiliki tanggal pelaksanaan.
- Sesi yang tidak pernah dikonfirmasi tidak boleh dibiarkan menggantung selamanya.
  Untuk PoC, batas respons undangan bisa menggunakan asumsi 24 jam dan batas konfirmasi proposal 24 jam. Angka tersebut harus menjadi konfigurasi yang bisa diubah, bukan aturan permanen.

9. Aturan khusus untuk perubahan jadwal
   Saya ingin menetapkan satu aturan yang cukup penting: perubahan jadwal tidak boleh langsung mengubah jadwal resmi sebelum semua anggota menyetujuinya.

Kita bisa menggunakan proses berikut:

1. Salah satu anggota mengajukan perubahan.
2. Sistem mencari waktu yang tersedia untuk seluruh anggota.
3. Host memilih salah satu waktu alternatif.
4. Sistem mengirim permintaan persetujuan kepada semua anggota.
5. Jika semua setuju, jadwal resmi diperbarui.
6. Jika ada yang menolak, jadwal lama tetap berlaku atau host mengajukan pilihan baru.
   Untuk menyimpan proses tersebut, kita tidak perlu menambah status utama baru pada Study Session. Kita bisa menggunakan tabel session_slots dengan kolom status, misalnya:

- PROPOSED: jadwal alternatif yang diajukan.
- APPROVED: jadwal yang disetujui.
- REJECTED: jadwal yang ditolak.
- SUPERSEDED: jadwal lama yang sudah digantikan.
  Dengan begitu, kita bisa menyimpan riwayat perubahan jadwal tanpa membuat status Study Session terlalu banyak.

10. Aturan penting agar status database tidak bertabrakan
    Sekarang kita rapikan hubungan antara seluruh objek.

Misalnya, ketika sesi berhasil dikonfirmasi, sistem harus melakukan beberapa perubahan secara bersamaan:

1. Study Session menjadi CONFIRMED.
2. Semua anggota yang menyetujui menjadi CONFIRMED.
3. Study Intent yang sudah berhasil dipenuhi menjadi CONVERTED.
4. Jadwal terpilih menjadi APPROVED.
5. Undangan yang sudah disetujui tetap tercatat sebagai ACCEPTED.
6. Sistem mencatat aktivitas SESSION_CONFIRMED.
   Semua perubahan penting tersebut sebaiknya dijalankan dalam satu database transaction.

Artinya, jika salah satu proses gagal, perubahan lainnya tidak boleh tertinggal dalam kondisi setengah jadi.

Contoh masalah yang harus dicegah:

- Study Session sudah CONFIRMED, tetapi anggota belum dikonfirmasi.
- Study Intent sudah CONVERTED, tetapi ternyata tidak ada sesi yang terbentuk.
- Kapasitas sudah bertambah, tetapi undangan gagal disimpan.
  Untuk menjaga konsistensi, kita harus punya beberapa aturan database:
  Aturan Tujuan
  Foreign Key Mencegah hubungan data yang tidak valid
  Unique Constraint Mencegah keanggotaan ganda pada sesi yang sama
  Transaction Memastikan beberapa perubahan berhasil bersama
  Row Locking Mencegah dua proses mengambil tempat yang sama
  Check Constraint Mencegah nilai atau rentang data yang tidak masuk akal

Ada satu aturan tambahan yang penting untuk sistem matching: ketika mahasiswa sedang terlibat dalam proses pembentukan kelompok, sistem harus memeriksa status tersebut lagi sebelum menerima undangan lain. Pemeriksaan di backend tetap wajib meskipun tombol di frontend sudah dinonaktifkan. 11. Ringkasan aturan status seluruh sistem
Berikut tabel yang bisa kita jadikan acuan implementasi.
Objek Status utama
Study Intent DRAFT, ACTIVE, GROUP_FORMING, JOIN_PENDING, CONVERTED, CANCELLED, EXPIRED
Study Session DRAFT, OPEN, CONFIRMATION_PENDING, CONFIRMED, COMPLETED, CANCELLED, EXPIRED
Invitation PENDING, ACCEPTED, REJECTED, WITHDRAWN, EXPIRED
Membership REQUESTED, INVITED, ACCEPTED, CONFIRMED, DECLINED, WITHDRAWN, REMOVED
Session Slot PROPOSED, APPROVED, REJECTED, SUPERSEDED

Perlu diingat, status di atas bukan berarti semua objek bisa berpindah ke status mana pun secara bebas.

Contohnya:

- COMPLETED tidak boleh kembali menjadi OPEN.
- CANCELLED tidak boleh kembali menjadi CONFIRMED.
- EXPIRED tidak boleh langsung aktif kembali tanpa proses baru.
- CONVERTED tidak boleh berubah kembali menjadi ACTIVE hanya karena sesi dibatalkan.
  Jika sesi dibatalkan setelah Study Intent menjadi CONVERTED, sistem harus meminta anggota yang terdampak untuk membuat Study Intent baru atau mengaktifkan kembali kebutuhan belajarnya melalui proses yang jelas. Jangan mengubah riwayat lama seolah-olah sesi tersebut tidak pernah terbentuk.

12. Pengujian Day 10
    Sekarang kita buat daftar pengujian yang harus berhasil.
    No. Skenario Hasil yang diharapkan
    1 Mahasiswa membatalkan Study Intent Status menjadi CANCELLED
    2 Batas pencarian terlewati Status menjadi EXPIRED
    3 Undangan ditolak Kandidat dikeluarkan dari proposal
    4 Host membatalkan proposal Proses kelompok dihentikan
    5 Host membatalkan sesi terkonfirmasi Semua anggota mendapat pemberitahuan
    6 Anggota keluar dari sesi Jumlah anggota dihitung ulang
    7 Jadwal berubah Semua anggota harus menyetujui jadwal baru
    8 Dua mahasiswa mengambil satu tempat terakhir Hanya satu yang berhasil mendapatkan tempat
    9 Mahasiswa memiliki dua Study Intent Boleh selama tidak ada konflik proses atau jadwal
    10 Mahasiswa sedang dalam Group Formation lain Tidak boleh masuk proses Group Formation kedua
    11 Undangan tidak dijawab sampai batas waktu Undangan menjadi EXPIRED
    12 Sesi belum dilaksanakan Tidak boleh menjadi COMPLETED
    13 Salah satu perubahan database gagal Seluruh perubahan dalam transaksi dibatalkan
    14 Sesi dibatalkan setelah intent dikonversi Riwayat tetap tersimpan; kebutuhan baru diproses secara eksplisit
    15 Sesi sudah selesai Tidak boleh menerima anggota baru

13. Keputusan akhir Day 10
    Hasil rancangan Day 10
    Selesai — rancangan awal

14. Setiap objek memiliki status dan aturan perpindahan masing-masing.
15. Study Intent dapat memiliki beberapa kebutuhan aktif, tetapi hanya satu proses pembentukan kelompok aktif pada satu waktu.
16. Penolakan anggota tidak otomatis membatalkan seluruh kelompok.
17. Pembatalan sesi tidak otomatis mengaktifkan kembali seluruh Study Intent.
18. Perubahan jadwal membutuhkan persetujuan seluruh anggota.
19. Kapasitas kelompok harus diperiksa ulang di database ketika permintaan disetujui.
20. Proses penting menggunakan database transaction.
21. Setiap pembatalan dan kegagalan harus memiliki catatan riwayat.
22. Undangan dan proposal harus memiliki batas waktu agar tidak menggantung.
23. Sesi hanya menjadi COMPLETED setelah pelaksanaannya dikonfirmasi.

24. Posisi LaFriend setelah Day 10
    Kita sudah menyelesaikan sepuluh bagian rancangan sistem.
    Hari Fokus Hasil utama
    1 Aturan dasar Business Rules
    2 Struktur data Database & ERD
    3 Input pengguna Study Intent
    4 Rumus pencocokan Compatibility Score
    5 Pencarian kandidat Session & Partner Matching
    6 Alur keseluruhan Integrated Matching Flow
    7 Pembentukan kelompok Group Quality Score
    8 Penjelasan rekomendasi Explainable Matching
    9 Evaluasi hasil Feedback & Evaluation Metrics
    10 Penanganan kondisi Status Management & Exception Handling

25. Target Day 11: Finalisasi Database & ERD
    Menurut saya, sekarang kita sudah waktunya merapikan semua rancangan database.

Kenapa tidak langsung coding?

Karena selama Day 1–10 kita sudah menemukan beberapa kebutuhan data baru:

- preference_rank untuk prioritas jadwal.
- Rincian skor pada match_results.
- Riwayat aktivitas melalui matching_events.
- Alasan kegagalan atau pembatalan.
- Persetujuan jadwal.
- Riwayat perubahan sesi.
- Aturan keanggotaan dan kapasitas.
  Kalau langsung coding tanpa menyatukan semua itu, kemungkinan besar kita harus berulang kali mengubah database.

Target Day 11 adalah menghasilkan satu rancangan database final yang sudah terhubung dengan seluruh logika LaFriend.

Output yang harus kita hasilkan nanti:

1. Daftar tabel final.
2. Kolom dan tipe data setiap tabel.
3. Primary Key dan Foreign Key.
4. Relasi antar-tabel.
5. ERD keseluruhan.
6. Aturan validasi database.
7. Contoh data untuk simulasi LaFriend.
   Setelah Day 11 selesai, kita akan punya fondasi database yang jauh lebih siap untuk mulai diimplementasikan menggunakan PostgreSQL.

Menurut saya, ini langkah yang tepat sebelum masuk ke tahap coding, bro.

You're using the free version of ChatGPT. Upgrade for advanced models, better memory, and higher-quality image creation.
Upgrade to Plus
