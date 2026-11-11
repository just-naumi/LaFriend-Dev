Oke bro. Sekarang kita masuk Day 2: Merancang Struktur Database dan Hubungan Antar Data (ERD).

Saya akan mengerjakan rancangan Day 2 untuk LaFriend dari awal sampai selesai dengan bahasa sederhana. Kita tidak perlu langsung membahas kode SQL atau istilah teknis yang rumit. Kita pahami dulu logikanya.

Kalau Day 1 kemarin kita menjawab:
LaFriend itu sistem apa, siapa penggunanya, dan bagaimana aturan kerjanya?

Maka Day 2 menjawab:
Data apa saja yang harus disimpan LaFriend, di mana data tersebut disimpan, dan bagaimana hubungan antar-data tersebut?

DAY 2 — Perancangan Database dan ERD

1. Memahami data yang dibutuhkan LaFriend
   Bayangkan ada mahasiswa bernama Andi.

Andi ingin belajar Struktur Data, khususnya Binary Tree, untuk persiapan UTS. Dia bisa belajar hari Jumat pukul 09.00–12.00.

Andi membuka LaFriend dan membuat permintaan belajar.

Sistem kemudian:

1. Menyimpan data Andi.
2. Menyimpan kebutuhan belajar Andi.
3. Mencari sesi belajar Struktur Data yang sudah tersedia.
4. Jika tidak ada, mencari mahasiswa lain dengan kebutuhan serupa.
5. Menyimpan hasil rekomendasi.
6. Menyimpan permintaan bergabung atau undangan.
7. Jika berhasil, menyimpan kelompok dan jadwal belajar.
8. Setelah belajar, menyimpan feedback.
   Artinya, LaFriend tidak cukup hanya menyimpan data mahasiswa. Sistem juga harus menyimpan perjalanan kebutuhan belajar sampai menjadi sesi belajar.
9. Menentukan tabel yang dibutuhkan
   Saya menyarankan kita menggunakan 10 tabel utama untuk versi awal LaFriend.

Setiap tabel mempunyai tugas yang berbeda.

1. Students

Menyimpan data mahasiswa.

Contoh: nama, email kampus, program studi, angkatan, dan status verifikasi.

2. Courses

Menyimpan daftar mata kuliah yang tersedia.

Contoh: Struktur Data, Basis Data, Jaringan Komputer.

3. Study Intents

Menyimpan kebutuhan belajar yang dibuat mahasiswa.

Contoh: Andi ingin belajar Binary Tree untuk persiapan UTS.

4. Intent Availabilities

Menyimpan waktu kosong mahasiswa untuk setiap Study Intent.

Contoh: Jumat 09.00–12.00 dan Sabtu 13.00–15.00.

5. Study Sessions

Menyimpan sesi belajar yang sudah dibuat atau ditawarkan.

Contoh: Belajar Struktur Data, Jumat 10.00–12.00, host Andi.

6. Session Slots

Menyimpan pilihan waktu yang ditawarkan untuk sebuah sesi.

Contoh: Jumat 10.00–12.00 atau Sabtu 13.00–15.00.

7. Session Members

Menyimpan siapa saja yang menjadi anggota sesi belajar.

Contoh: Andi sebagai host, Budi dan Citra sebagai anggota.

8. Invitations / Join Requests

Menyimpan undangan atau permintaan mahasiswa untuk bergabung.

Contoh: Budi meminta bergabung dengan sesi milik Andi.

9. Match Results

Menyimpan hasil pencarian dan perhitungan kecocokan.

Contoh: Sesi A mendapatkan skor 90, sesi B mendapatkan skor 82.

10. Feedbacks

Menyimpan penilaian mahasiswa setelah menerima rekomendasi atau mengikuti sesi.

3. Memahami hubungan antar-tabel
   Sekarang kita bahas bagaimana tabel-tabel tersebut saling berhubungan.

Contoh paling sederhana:

- Satu mahasiswa bisa membuat banyak Study Intent.
- Satu mata kuliah bisa memiliki banyak Study Intent.
- Satu Study Intent bisa memiliki beberapa pilihan waktu.
- Satu Study Session bisa memiliki banyak anggota.
- Satu mahasiswa bisa mengikuti banyak Study Session.
  Hubungan ini penting agar data tidak berantakan atau harus ditulis berulang-ulang.
  Gambaran ERD LaFriend
  Berikut hubungan yang saya rekomendasikan. Perhatikan bahwa satu mahasiswa bisa memiliki banyak kebutuhan belajar, tetapi satu kebutuhan belajar hanya dimiliki oleh satu mahasiswa.
  #chatgpt-mermaid-_r_1ul_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(13, 13, 13);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-_r_1ul_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-_r_1ul_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-_r_1ul_ .error-icon{fill:rgb(243, 243, 243);}#chatgpt-mermaid-_r_1ul_ .error-text{fill:rgb(13, 13, 13);stroke:rgb(13, 13, 13);}#chatgpt-mermaid-_r_1ul_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-_r_1ul_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-_r_1ul_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-_r_1ul_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-_r_1ul_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-_r_1ul_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-_r_1ul_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-_r_1ul_ .marker.cross{stroke:rgb(143, 143, 143);}#chatgpt-mermaid-_r_1ul_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-_r_1ul_ p{margin:0;}#chatgpt-mermaid-_r_1ul_ .entityBox{fill:rgb(222, 234, 251);stroke:rgb(83, 154, 248);}#chatgpt-mermaid-_r_1ul_ .relationshipLabelBox{fill:rgb(243, 243, 243);opacity:0.7;background-color:rgb(243, 243, 243);}#chatgpt-mermaid-_r_1ul_ .relationshipLabelBox rect{opacity:0.5;}#chatgpt-mermaid-_r_1ul_ .labelBkg{background-color:rgba(243, 243, 243, 0.5);}#chatgpt-mermaid-_r_1ul_ .edgeLabel{background-color:rgb(252, 252, 252);}#chatgpt-mermaid-_r_1ul_ .edgeLabel .label rect{fill:rgb(252, 252, 252);}#chatgpt-mermaid-_r_1ul_ .edgeLabel .label text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-_r_1ul_ .edgeLabel .label{fill:rgb(83, 154, 248);font-size:14px;}#chatgpt-mermaid-_r_1ul_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(13, 13, 13);}#chatgpt-mermaid-_r_1ul_ .edge-pattern-dashed{stroke-dasharray:8,8;}#chatgpt-mermaid-_r_1ul_ .node rect,#chatgpt-mermaid-_r_1ul_ .node circle,#chatgpt-mermaid-_r_1ul_ .node ellipse,#chatgpt-mermaid-_r_1ul_ .node polygon{fill:rgb(222, 234, 251);stroke:rgb(83, 154, 248);stroke-width:1px;}#chatgpt-mermaid-_r_1ul_ .relationshipLine{stroke:rgb(143, 143, 143);stroke-width:1px;fill:none;}#chatgpt-mermaid-_r_1ul_ .marker{fill:none!important;stroke:rgb(143, 143, 143)!important;stroke-width:1;}#chatgpt-mermaid-_r_1ul_ [data-look=neo].labelBkg{background-color:rgba(243, 243, 243, 0.5);}#chatgpt-mermaid-_r_1ul_ .node .neo-node{stroke:rgb(83, 154, 248);}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].node rect,#chatgpt-mermaid-_r_1ul_ [data-look="neo"].cluster rect,#chatgpt-mermaid-_r_1ul_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-_r_1ul_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-_r_1ul_-gradient);stroke-width:1px;}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].node .neo-line path{stroke:rgb(83, 154, 248);filter:none;}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-_r_1ul_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-_r_1ul_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1ul_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-_r_1ul_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1ul_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}STUDENTSSTUDY_INTENTSCOURSESINTENT_AVAILABILITIESSTUDY_SESSIONSSESSION_SLOTSSESSION_MEMBERSINVITATIONSMATCH_RESULTSFEEDBACKScreatesbelongs_tohashostsbelongs_tooffersparticipatescontainssends_or_receivesreceives_requestrelates_togeneratescandidate_studentcandidate_sessionsubmitsreceivesevaluates

Cara membaca simbolnya:

- || berarti satu.
- o{ berarti nol atau banyak.
- o| berarti boleh tidak ada atau satu.
  Contohnya, STUDENTS ||--o{ STUDY_INTENTS berarti satu mahasiswa dapat membuat banyak Study Intent, sedangkan setiap Study Intent dimiliki satu mahasiswa.

4. Menentukan isi setiap tabel
   Sekarang kita tentukan data apa yang harus disimpan. Ini penting karena nanti akan menjadi dasar pembuatan database PostgreSQL.

Saya gunakan istilah sederhana:

- PK (Primary Key): kode unik untuk setiap data.
- FK (Foreign Key): kode yang menghubungkan data dengan tabel lain.
  Tabel 1 — Students
  Nama kolom Fungsi
  student_id (PK) ID unik mahasiswa
  full_name Nama mahasiswa
  email Email kampus
  student_number NIM
  study_program Program studi
  academic_year Tahun angkatan
  verification_status Status verifikasi
  created_at Waktu pendaftaran

Contoh:
student_id full_name academic_year
ST001 Andi 2025
ST002 Budi 2025
ST003 Citra 2024

Tabel 2 — Courses
Nama kolom Fungsi
course_id (PK) ID mata kuliah
course_name Nama mata kuliah
course_code Kode mata kuliah
study_program Program studi terkait

Contoh: CS101 — Struktur Data.

Mengapa dibuat tabel terpisah? Karena kita tidak ingin setiap mahasiswa mengetik nama mata kuliah secara bebas. Jika tidak, "Struktur Data", "Strukturdata", dan "Data Structure" bisa dianggap berbeda oleh sistem.
Tabel 3 — Study Intents
Ini tabel paling penting karena merupakan titik awal matching.
Nama kolom Fungsi
intent_id (PK) ID kebutuhan belajar
student_id (FK) Pemilik kebutuhan
course_id (FK) Mata kuliah
topics Topik yang ingin dipelajari
learning_goal Tujuan belajar
collaboration_style Gaya belajar yang diinginkan
learning_mode Online, offline, atau fleksibel
earliest_date Tanggal paling awal
preferred_date Tanggal yang diinginkan
latest_date Batas akhir
min_group_size Jumlah anggota minimal
max_group_size Jumlah anggota maksimal
status Status kebutuhan belajar
created_at Waktu dibuat

Contoh data:
Kolom Isi
intent_id INT001
student_id ST001
course_id CS101
topics Binary Tree, Graph
learning_goal Persiapan UTS
collaboration_style Problem Solving
learning_mode Offline
earliest_date 20 November
preferred_date 21 November
latest_date 23 November
min_group_size 2
max_group_size 4
status ACTIVE

Artinya, Andi ingin belajar Binary Tree dan Graph, paling ingin belajar pada 21 November, dan bersedia belajar bersama 2–4 orang.
Tabel 4 — Intent Availabilities
Mengapa waktu kosong tidak langsung dimasukkan ke Study Intents?

Karena satu mahasiswa bisa mempunyai beberapa pilihan waktu.
Nama kolom Fungsi
availability_id (PK) ID waktu
intent_id (FK) Pemilik Study Intent
available_date Tanggal tersedia
start_time Jam mulai
end_time Jam selesai

Contoh:
availability_id intent_id available_date Waktu
AV001 INT001 20 Nov 09.00–12.00
AV002 INT001 21 Nov 13.00–16.00
AV003 INT001 22 Nov 10.00–12.00

Jadi, sistem dapat membandingkan waktu Andi dengan waktu mahasiswa lain.
Tabel 5 — Study Sessions
Tabel ini menyimpan sesi belajar yang sudah dibuat oleh host.
Nama kolom Fungsi
session_id (PK) ID sesi
host_id (FK) Mahasiswa pembuat sesi
course_id (FK) Mata kuliah
session_topic Topik pembelajaran
learning_goal Tujuan sesi
collaboration_style Gaya belajar
learning_mode Online/offline
min_group_size Minimal peserta
max_group_size Maksimal peserta
status Status sesi
created_at Waktu dibuat

Contoh:
Kolom Isi
session_id SES001
host_id ST001
course_id CS101
session_topic Binary Tree
learning_goal Persiapan UTS
learning_mode Offline
min_group_size 2
max_group_size 4
status OPEN

Sesi ini bisa ditemukan oleh mahasiswa lain yang memiliki kebutuhan belajar sesuai.
Tabel 6 — Session Slots
Tabel ini menyimpan pilihan waktu untuk sebuah sesi.
Nama kolom Fungsi
slot_id (PK) ID slot
session_id (FK) Sesi terkait
session_date Tanggal
start_time Jam mulai
end_time Jam selesai
status Status slot

Contohnya, host menawarkan Jumat pukul 10.00–12.00 atau Sabtu pukul 13.00–15.00.

Ketika semua peserta sudah menyetujui satu waktu, slot tersebut menjadi jadwal final sesi.
Tabel 7 — Session Members
Tabel ini menjawab pertanyaan: siapa saja yang ikut sesi?
Nama kolom Fungsi
membership_id (PK) ID keanggotaan
session_id (FK) Sesi yang diikuti
student_id (FK) Mahasiswa yang ikut
member_role Host atau member
status Status keanggotaan
joined_at Waktu bergabung

Contoh:
session_id student_id member_role
SES001 ST001 HOST
SES001 ST002 MEMBER
SES001 ST003 MEMBER

Dengan demikian, satu sesi memiliki tiga peserta.
Tabel 8 — Invitations / Join Requests
Tabel ini menyimpan proses saling mengundang atau meminta bergabung.
Nama kolom Fungsi
request_id (PK) ID permintaan
request_type JOIN_SESSION atau PARTNER_INVITE
sender_id (FK) Pengirim
receiver_id (FK) Penerima
session_id (FK) Sesi tujuan, jika ada
target_intent_id (FK) Intent tujuan, jika undangan partner
status Pending, accepted, rejected, withdrawn
created_at Waktu dibuat
responded_at Waktu dijawab

Contoh:

Andi mengirim undangan kepada Budi untuk membentuk kelompok belajar.

Budi menerima undangan tersebut. Sistem kemudian dapat melanjutkan pemeriksaan kelayakan kelompok.
Tabel 9 — Match Results
Tabel ini menyimpan hasil perhitungan matching.
Nama kolom Fungsi
match_id (PK) ID hasil matching
intent_id (FK) Intent yang sedang dicari
candidate_type SESSION atau PARTNER
candidate_session_id (FK) Sesi yang direkomendasikan
candidate_student_id (FK) Mahasiswa yang direkomendasikan
compatibility_score Skor kecocokan
score_details Rincian skor
explanation Alasan rekomendasi
created_at Waktu perhitungan

Contoh:
intent_id candidate_type Kandidat Skor
INT001 SESSION SES003 91
INT001 SESSION SES004 85
INT001 PARTNER ST004 88

Perlu diingat, rekomendasi partner baru dibuat jika tidak ada sesi yang memenuhi ketentuan rekomendasi.
Tabel 10 — Feedbacks
Tabel ini menyimpan evaluasi dari mahasiswa.
Nama kolom Fungsi
feedback_id (PK) ID feedback
student_id (FK) Pengirim feedback
session_id (FK) Sesi yang dinilai, jika ada
match_id (FK) Rekomendasi yang dinilai, jika ada
feedback_type RECOMMENDATION atau SESSION
relevance_rating Penilaian relevansi
schedule_rating Penilaian jadwal
session_held Apakah sesi terlaksana
comments Komentar
created_at Waktu dibuat

Kita memisahkan feedback rekomendasi dengan feedback sesi karena mahasiswa bisa saja merasa rekomendasinya cocok, tetapi sesi akhirnya tidak terlaksana.

5. Simulasi: Bagaimana seluruh tabel bekerja?
   Sekarang kita uji rancangan database tersebut dengan satu kasus sederhana.
   Kasus: Andi mencari teman belajar Struktur Data
1. Andi mendaftar

   Data Andi masuk ke tabel Students dengan ID ST001.

1. Andi membuat kebutuhan belajar

   INT001 disimpan di Study Intents, sedangkan waktu kosongnya disimpan di Intent Availabilities.

1. Sistem mencari sesi yang tersedia

   Sistem membaca Study Sessions, Session Slots, dan Session Members.

1. Tidak ada sesi yang cocok

   Sistem beralih mencari kebutuhan belajar mahasiswa lain melalui Study Intents.

1. Sistem menemukan Budi

   Hasil kecocokan disimpan di Match Results. Andi mengirim undangan melalui Invitations / Join Requests.

1. Budi menerima undangan

   Sistem mengecek kecocokan waktu dan ukuran kelompok. Jika layak, dibuat sesi baru di Study Sessions.

1. Andi dan Budi menyetujui jadwal

   Keanggotaan mereka dicatat di Session Members, dan sesi berubah menjadi CONFIRMED.

1. Mereka selesai belajar

   Sistem menyimpan hasil sesi dan feedback di Feedbacks.

Nah, sekarang terlihat bahwa setiap tabel punya fungsi. Tidak ada tabel yang dibuat hanya untuk menambah jumlah database. 6. Aturan penting supaya database tidak berantakan
Ada beberapa aturan tambahan yang harus kita terapkan ketika membuat database nanti.
Aturan Tujuan
Email mahasiswa harus unik Tidak ada akun dengan email sama.
Satu intent hanya dimiliki satu mahasiswa Kepemilikan kebutuhan jelas.
Satu sesi hanya memiliki satu host Tanggung jawab pengelolaan jelas.
Mahasiswa tidak boleh terdaftar dua kali dalam sesi yang sama Mencegah data anggota duplikat.
Jumlah anggota tidak boleh melebihi kapasitas Menjaga kelayakan kelompok.
Satu sesi hanya boleh memiliki satu jadwal final Menghindari jadwal yang bertentangan.
Hasil matching harus terhubung dengan intent asal Kita bisa melacak alasan rekomendasi muncul.
Feedback hanya bisa diberikan oleh peserta yang berhak Mengurangi feedback palsu.

Ada satu hal teknis yang perlu kita perhatikan: candidate_session_id dan candidate_student_id pada tabel Match Results tidak boleh terisi bersamaan. Satu hasil harus mewakili rekomendasi sesi atau rekomendasi mahasiswa, bukan keduanya sekaligus. 7. Apakah 10 tabel ini sudah cukup?
Cukup untuk rancangan awal PoC
Menurut saya, sepuluh tabel tersebut sudah mencakup alur utama LaFriend.

Namun, ada beberapa fitur tambahan yang belum perlu kita masukkan sekarang:

- Tabel notifikasi.
- Tabel laporan dan pemblokiran.
- Tabel riwayat perubahan jadwal.
- Tabel percakapan.
- Tabel evaluasi bobot algoritma.
  Kita bisa menambahkannya ketika kebutuhan implementasi sudah jelas. Jangan membuat database terlalu rumit sebelum fitur intinya berjalan.

8. Hasil pekerjaan Day 2
   Day 2 — Database Design
   Rancangan selesai

10 tabel utama
Rancangan awal untuk mendukung alur LaFriend.

Entitas mahasiswa dan mata kuliah
Selesai

Entitas kebutuhan belajar
Selesai

Entitas sesi dan jadwal
Selesai

Entitas anggota dan undangan
Selesai

Entitas hasil matching dan feedback
Selesai

Yang dihasilkan:

- Struktur tabel dan kolom.
- Hubungan antar-tabel.
- Gambaran ERD.
- Aturan dasar penyimpanan data.
- Simulasi aliran data dari awal hingga feedback.

Catatan: ini sudah menjadi rancangan konseptual Day 2, tetapi belum ERD final yang siap langsung diimplementasikan. Kita masih perlu memeriksa struktur relasi, tipe data, dan aturan database sebelum membuat SQL. 9. Berikutnya kita mengerjakan apa?
Untuk Day 3, saya menyarankan kita membahas struktur input Study Intent secara lebih mendalam.

Mengapa? Karena Study Intent merupakan sumber utama seluruh proses matching.

Kita harus memastikan sistem mengetahui:

1. Mata kuliah apa yang ingin dipelajari?
2. Topik apa yang ingin dibahas?
3. Apa tujuan belajarnya?
4. Kapan mahasiswa ingin belajar?
5. Kapan mahasiswa tersedia?
6. Bagaimana gaya belajar yang disukai?
7. Berapa jumlah anggota yang diinginkan?
   Setelah itu, kita baru dapat menentukan bagaimana setiap input diubah menjadi angka atau parameter yang bisa dihitung oleh algoritma.

Jadi urutan pekerjaan kita:

- Day 1: Menentukan cara kerja dan aturan LaFriend.
- Day 2: Menentukan tempat penyimpanan dan hubungan data.
- Day 3: Menentukan input dan parameter Study Intent.
- Day 4: Menentukan aturan penyaringan kandidat.
- Day 5: Menentukan rumus kecocokan.
- Day 6: Menentukan rumus kelayakan kelompok.
- Day 7: Menentukan feedback dan evaluasi algoritma.
  Dengan urutan ini, kita tidak asal membuat formula. Kita tahu dulu data yang masuk, bagaimana data diproses, dan hasil apa yang ingin dicapai.

Target saya: ketika Day 7 selesai, kita sudah mempunyai rancangan logika dan matematika LaFriend yang cukup lengkap untuk mulai diimplementasikan.
