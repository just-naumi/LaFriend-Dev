Roadmap 10 Hari — Finalisasi Struktur Sistem dan Formula LaFriend
Saya menyarankan kita menggunakan 10 hari kerja perancangan. Selama periode ini, fokus kita bukan menulis kode aplikasi, tetapi memastikan setiap keputusan sistem sudah jelas dan dapat diterjemahkan menjadi kode tanpa banyak mengubah logika di tengah implementasi.

Target akhir hari ke-10: LaFriend mempunyai dokumen System Design Specification yang berisi:

1. Definisi input, parameter, dan struktur data.
2. Formula preprocessing dan normalisasi.
3. Hard constraints dan soft constraints.
4. Compatibility scoring beserta bobot dan dasar perhitungannya.
5. Session-First Matching dan Partner Matching.
6. Group Feasibility dan mekanisme konfirmasi sesi.
7. Feedback, metrik evaluasi, dan mekanisme kalibrasi.
8. Arsitektur modul, alur data, pseudocode, serta test cases.
   Prinsipnya, setiap hari harus menghasilkan artefak yang bisa diperiksa. Kita tidak berpindah ke pekerjaan berikutnya hanya karena sudah membahas teorinya; pekerjaan hari itu harus punya keputusan dan hasil tertulis.
   Hari 1 — Mengunci konsep dan batasan sistem
   Fondasi sistem
   Tujuan: memastikan semua orang memahami bagaimana LaFriend bekerja dan apa yang sebenarnya ingin dioptimalkan.

Hari pertama bukan langsung menyusun formula. Kita harus mengunci definisi setiap objek dan aturan bisnis terlebih dahulu.

Pekerjaan yang harus diselesaikan:

1. Tetapkan aktor sistem:

- Student: pengguna yang membuat Study Intent.
- Session Host: mahasiswa yang membuat sesi.
- Session Member: mahasiswa yang bergabung.
- System: mesin pencarian, matching, rekomendasi, dan evaluasi.

2. Tetapkan objek utama:

- Student Profile.
- Study Intent.
- Study Session.
- Session Invitation.
- Session Membership.
- Session Feedback.
- Matching Result.

3. Kunci alur utama:

- Mahasiswa membuat Study Intent.
- Sistem mencari sesi yang sudah tersedia.
- Jika tidak ada sesi yang cocok, sistem mencari calon partner.
- Sistem memberikan rekomendasi beserta alasannya.
- Mahasiswa menerima atau menolak rekomendasi.
- Sesi dikonfirmasi.
- Sesi dilaksanakan.
- Peserta mengisi feedback.

4. Tentukan kebijakan sistem:

- Satu mahasiswa boleh memiliki lebih dari satu intent atau tidak?
- Apakah satu intent bisa bergabung dengan beberapa sesi?
- Apakah pengguna boleh menjadi host dan member sekaligus?
- Kapan intent dianggap tidak aktif?
- Bagaimana jika peserta membatalkan sesi?

5. Tetapkan definisi target date. Menurut saya, ini perlu dibedakan menjadi:

- preferred_date: tanggal yang paling diinginkan.
- latest_date: batas terakhir sesi boleh dilaksanakan.
  Dengan demikian, sistem bisa membedakan preferensi tanggal dengan batas waktu yang tidak boleh dilanggar.

Output Hari 1:

- System Scope Document.
- Business Rules Document.
- User Flow Diagram.
- Daftar definisi dan istilah sistem.
  Kriteria selesai: tidak ada lagi kebingungan antara Study Intent, rekomendasi, partner, dan Study Session.

Hari 2 — Merancang struktur data dan hubungan antarentitas
Data modeling
Tujuan: menentukan data apa yang disimpan, siapa pemiliknya, dan bagaimana relasi antarobjek.

Kita perlu memastikan sistem tidak hanya bisa melakukan matching, tetapi juga bisa melacak perjalanan satu Study Intent sampai sesi selesai.

Pekerjaan yang harus diselesaikan:

1. Student Profile
   Tentukan atribut:
   Field Tipe data Fungsi
   student_id UUID Identitas pengguna
   name String Nama mahasiswa
   university_email String Verifikasi kampus
   study_program String Program studi
   academic_year Integer Tahun angkatan
   enrolled_courses Array/Relation Mata kuliah yang diambil
   account_status Enum Status akun

2. Study Intent
   Field Tipe data Fungsi
   intent_id UUID Identitas intent
   student_id UUID Pembuat intent
   course_id UUID Mata kuliah
   topics Array Materi yang ingin dipelajari
   learning_goal Enum Tujuan belajar
   preferred_date Date Tanggal pilihan
   latest_date Date Batas waktu
   availability JSON/Relation Waktu tersedia
   collaboration_style Enum Gaya belajar
   learning_mode Enum Online/offline/flexible
   min_group_size Integer Minimal anggota
   max_group_size Integer Maksimal anggota
   status Enum Status intent

3. Study Session
   Field Tipe data Fungsi
   session_id UUID Identitas sesi
   host_id UUID Pembuat sesi
   course_id UUID Mata kuliah
   topics Array Topik sesi
   learning_goal Enum Tujuan sesi
   session_date Date Tanggal pelaksanaan
   start_time Time Waktu mulai
   end_time Time Waktu selesai
   learning_mode Enum Mode sesi
   capacity Integer Kapasitas anggota
   status Enum Status sesi

4. Entitas pendukung
   Kita juga perlu mendefinisikan:

- SessionMember: relasi peserta dan sesi.
- Invitation: undangan bergabung.
- MatchResult: kandidat, nilai skor, komponen skor, dan alasan rekomendasi.
- Feedback: penilaian setelah sesi.
- SessionEvent: riwayat perubahan status.
  Jangan menyimpan seluruh anggota kelompok sebagai satu array yang tidak memiliki identitas relasi. Lebih baik membuat tabel relasi SessionMember, sehingga setiap peserta memiliki status dan histori sendiri.

5. Buat ERD
   Hubungan awal yang perlu digambarkan:
   #chatgpt-mermaid-_r_1hg_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(13, 13, 13);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-_r_1hg_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-_r_1hg_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-_r_1hg_ .error-icon{fill:rgb(243, 243, 243);}#chatgpt-mermaid-_r_1hg_ .error-text{fill:rgb(13, 13, 13);stroke:rgb(13, 13, 13);}#chatgpt-mermaid-_r_1hg_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-_r_1hg_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-_r_1hg_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-_r_1hg_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-_r_1hg_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-_r_1hg_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-_r_1hg_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-_r_1hg_ .marker.cross{stroke:rgb(143, 143, 143);}#chatgpt-mermaid-_r_1hg_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-_r_1hg_ p{margin:0;}#chatgpt-mermaid-_r_1hg_ .entityBox{fill:rgb(222, 234, 251);stroke:rgb(83, 154, 248);}#chatgpt-mermaid-_r_1hg_ .relationshipLabelBox{fill:rgb(243, 243, 243);opacity:0.7;background-color:rgb(243, 243, 243);}#chatgpt-mermaid-_r_1hg_ .relationshipLabelBox rect{opacity:0.5;}#chatgpt-mermaid-_r_1hg_ .labelBkg{background-color:rgba(243, 243, 243, 0.5);}#chatgpt-mermaid-_r_1hg_ .edgeLabel{background-color:rgb(252, 252, 252);}#chatgpt-mermaid-_r_1hg_ .edgeLabel .label rect{fill:rgb(252, 252, 252);}#chatgpt-mermaid-_r_1hg_ .edgeLabel .label text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-_r_1hg_ .edgeLabel .label{fill:rgb(83, 154, 248);font-size:14px;}#chatgpt-mermaid-_r_1hg_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(13, 13, 13);}#chatgpt-mermaid-_r_1hg_ .edge-pattern-dashed{stroke-dasharray:8,8;}#chatgpt-mermaid-_r_1hg_ .node rect,#chatgpt-mermaid-_r_1hg_ .node circle,#chatgpt-mermaid-_r_1hg_ .node ellipse,#chatgpt-mermaid-_r_1hg_ .node polygon{fill:rgb(222, 234, 251);stroke:rgb(83, 154, 248);stroke-width:1px;}#chatgpt-mermaid-_r_1hg_ .relationshipLine{stroke:rgb(143, 143, 143);stroke-width:1px;fill:none;}#chatgpt-mermaid-_r_1hg_ .marker{fill:none!important;stroke:rgb(143, 143, 143)!important;stroke-width:1;}#chatgpt-mermaid-_r_1hg_ [data-look=neo].labelBkg{background-color:rgba(243, 243, 243, 0.5);}#chatgpt-mermaid-_r_1hg_ .node .neo-node{stroke:rgb(83, 154, 248);}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].node rect,#chatgpt-mermaid-_r_1hg_ [data-look="neo"].cluster rect,#chatgpt-mermaid-_r_1hg_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-_r_1hg_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-_r_1hg_-gradient);stroke-width:1px;}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].node .neo-line path{stroke:rgb(83, 154, 248);filter:none;}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-_r_1hg_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-_r_1hg_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1hg_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-_r_1hg_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_1hg_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}STUDENTSTUDY_INTENTSTUDY_SESSIONSESSION_MEMBERMATCH_RESULTINVITATIONFEEDBACKSESSION_EVENTcreateshostscontainsjoinsgeneratesreceivesreceivesofferssubmitsreceivesrecords

Output Hari 2:

- Data Dictionary.
- Entity Relationship Diagram.
- Daftar field, tipe data, relasi, dan constraint database.
  Kriteria selesai: setiap informasi yang dibutuhkan oleh formula matching sudah mempunyai tempat penyimpanan yang jelas.

Hari 3 — Memformulasikan input dan preprocessing
Input engineering
Tujuan: memastikan input mahasiswa bisa diubah menjadi representasi yang konsisten untuk diproses oleh matching engine.

Pekerjaan yang harus diselesaikan:

1. Tentukan seluruh input yang wajib diisi.
2. Tentukan input opsional.
3. Buat daftar kategori dan nilai yang valid.
4. Definisikan normalisasi course.
5. Definisikan normalisasi topic.
6. Definisikan representasi waktu.
7. Definisikan validasi setiap input.
8. Tentukan bagaimana menangani input tidak lengkap atau salah.
   Contohnya, untuk topic:
   raw_topics = [ "Binary Tree", "binary tree", "TREE TRAVERSAL"]

Setelah normalisasi:
normalized_topics = { "binary_tree", "tree_traversal"}

Kita juga harus menetapkan apakah sinonim seperti UTS preparation dan midterm preparation dianggap sama, serta apakah nama mata kuliah harus selalu dipilih dari katalog kampus.
Perancangan representasi waktu
Saya menyarankan menggunakan format interval:
{
"date": "2026-11-20",
"start": "09:00",
"end": "12:00"
}

Tetapkan juga:

- Apakah ketersediaan dapat berulang setiap minggu?
- Apakah interval yang saling bertumpuk digabung?
- Apakah pengguna dapat memiliki beberapa pilihan waktu?
- Apakah perubahan availability memperbarui rekomendasi?
- Apakah jadwal memakai zona waktu Asia/Jakarta?
  Tentukan penggunaan GLiNER
  Kita perlu membatasi perannya.

GLiNER hanya menjadi opsi untuk mengekstrak entitas course dan topic dari kalimat bebas. Parsing tanggal dan waktu diproses secara terpisah. Pengguna tetap mengonfirmasi hasil sebelum menjadi Study Intent.

Output Hari 3:

- Input Specification.
- Enum dan kategori data.
- Normalization Rules.
- Validation Rules.
- Contoh input dan output preprocessing.
  Kriteria selesai: setiap input mempunyai format standar, aturan validasi, dan representasi yang dapat digunakan oleh formula.

Hari 4 — Menentukan Hard Constraint Filtering
Logika kelayakan
Tujuan: mengunci seluruh syarat wajib yang menentukan apakah kandidat boleh masuk ke proses scoring.

Ini hari yang sangat penting karena kesalahan pada tahap ini akan membuat rekomendasi tidak masuk akal.

Pekerjaan yang harus diselesaikan:

1. Kelompokkan constraint
   Saya menyarankan tabel keputusan berikut sebagai titik awal:
   Parameter Hard/Soft Alasan
   Course Hard Harus sesuai mata kuliah
   Latest Date Hard Tidak boleh melewati batas
   Minimum Shared Time Hard Harus memungkinkan sesi
   Session Capacity Hard Tidak boleh melebihi kapasitas
   Account/Safety Status Hard Pengguna harus memenuhi aturan keamanan
   Topic Soft Tidak wajib identik seluruhnya
   Learning Goal Soft Bisa berbeda tetapi kompatibel
   Collaboration Style Soft Preferensi kolaborasi
   Preferred Date Soft Bisa berbeda dalam rentang yang diizinkan
   Learning Mode Conditional Hard jika pilihan eksklusif, soft jika fleksibel

2. Buat formula kelayakan
   \[
   H(i,j)=\prod\_{k=1}^{m}H_k(i,j)
   \]

Nilai akhir harus 0 atau 1. 3. Selesaikan formula availability
Kita perlu menguji:

- Dua mahasiswa dengan satu interval yang sama.
- Dua mahasiswa dengan beberapa interval.
- Availability yang beririsan sebagian.
- Availability yang tidak beririsan.
- Kelompok dengan irisan waktu yang berbeda-beda.
  Untuk pasangan:
  \[
  O*{ij}^{best}=
  \max*{r\in A_i\cap A_j}Duration(r)
  \]

\[
H*A(i,j)=
\mathbb{1}[O*{ij}^{best}\geq\tau]
\]

Untuk kelompok:
\[
A*G=\bigcap*{u\in G}A_u
\]

\[
H*{group,time}=
\mathbb{1}
\left[
\max*{r\in A_G}Duration(r)\geq\tau
\right]
\]

4. Buat tabel kondisi gagal
   Misalnya:
   Kasus Hasil
   Course berbeda Reject
   Sesi melewati deadline Reject
   Waktu bersama hanya 30 menit Reject
   Kapasitas penuh Reject
   Topic kurang cocok tetapi syarat wajib terpenuhi Lanjut scoring
   Style berbeda tetapi masih kompatibel Lanjut scoring

Output Hari 4:

- Hard Constraint Specification.
- Formula filtering.
- Constraint Decision Table.
- Minimal 15 skenario pengujian.
  Kriteria selesai: setiap kandidat dapat dikategorikan secara konsisten sebagai ELIGIBLE atau INELIGIBLE, dengan alasan yang bisa ditelusuri.

Hari 5 — Menyusun formula Soft Constraint dan Compatibility Scoring
Mathematical model
Tujuan: menentukan bagaimana sistem menghitung tingkat kecocokan dari kandidat yang sudah lolos filtering.

Pekerjaan yang harus diselesaikan:

1. Finalisasi parameter scoring
   Kita gunakan enam parameter utama:
   \[
   S(i,j)=
   w_TS_T+
   w_AS_A+
   w_GS_G+
   w_LS_L+
   w_DS_D+
   w_MS_M
   \]

2. Finalisasi formula tiap parameter
   Komponen Formula/metode
   Topic Jaccard Similarity
   Schedule Shared Availability Score
   Goal Goal Compatibility Matrix
   Style Collaboration Compatibility Matrix
   Date Date Proximity Function
   Mode Mode Compatibility Matrix

3. Tentukan formula schedule scoring secara definitif
   Ini harus menjadi fokus khusus karena formula jadwal sebelumnya masih perlu dipastikan.

Saya merekomendasikan memisahkan:

- minimum feasible overlap: syarat minimal agar dapat melakukan sesi.
- schedule flexibility score: ukuran seberapa banyak pilihan waktu yang tersedia.
  Sebagai contoh:
  \[
  S*A=
  \min\left(1,\frac{O*{ij}^{best}}{120}\right)
  \]

Dengan \(O\_{ij}^{best}\) dalam menit dan minimal kelayakan 60 menit.

Artinya, 60 menit memperoleh skor 0,5 dan 120 menit atau lebih memperoleh 1.

Kita perlu menentukan apakah total durasi atau durasi interval terbaik yang paling merepresentasikan fleksibilitas pengguna. Saya menyarankan durasi interval terbaik untuk versi awal agar sistem tidak salah menganggap beberapa waktu pendek yang terpisah sebagai satu waktu belajar panjang. 4. Tentukan compatibility matrix
Buat tabel resmi untuk:

- Learning Goal.
- Collaboration Style.
- Learning Mode.
  Jangan menggunakan angka intuitif tanpa dokumentasi. Setiap angka harus mempunyai alasan dan status: asumsi awal, hasil eksperimen, atau hasil pilot.

5. Definisikan Why This Match
   Setiap komponen scoring yang tinggi harus bisa diterjemahkan menjadi alasan yang dimengerti pengguna.

Contoh:
Kondisi Alasan rekomendasi
Topic tinggi Materi yang dicari memiliki kesamaan
Schedule tinggi Waktu tersedia memiliki banyak irisan
Goal tinggi Tujuan belajar saling sesuai
Style tinggi Gaya kolaborasi sesuai preferensi

Output Hari 5:

- Compatibility Formula Specification.
- Compatibility Matrix.
- Definisi tiap variabel.
- Contoh perhitungan manual.
  Kriteria selesai: satu input dan satu kandidat bisa menghasilkan skor yang dapat dihitung ulang secara manual.

Hari 6 — Kalibrasi bobot dan menentukan aturan ranking
Validasi formula
Tujuan: memastikan sistem tidak menggunakan bobot secara sembarangan dan hasil ranking masuk akal.

Pekerjaan yang harus diselesaikan:

1. Tentukan bobot awal.
2. Buat 10–20 skenario pasangan mahasiswa.
3. Hitung seluruh skor secara manual atau menggunakan spreadsheet.
4. Periksa apakah urutan ranking sudah masuk akal.
5. Buat kasus yang sengaja memiliki konflik preferensi.
6. Bandingkan pengaruh perubahan bobot.
7. Tentukan ambang minimum rekomendasi.
8. Tentukan jumlah rekomendasi yang ditampilkan.
   Bobot eksperimen awal:
   Parameter Bobot
   Topic 30%
   Schedule 30%
   Learning Goal 20%
   Collaboration Style 10%
   Target Date 5%
   Learning Mode 5%

Kita juga harus mencoba beberapa konfigurasi alternatif, misalnya:

- Konfigurasi A: topic lebih dominan.
- Konfigurasi B: schedule lebih dominan.
- Konfigurasi C: keseimbangan topic, schedule, dan goal.
  Contoh analisis sensitivitas
  Misalkan dua kandidat:
  Parameter Kandidat A Kandidat B
  Topic 1,00 0,70
  Schedule 0,60 1,00
  Goal 1,00 0,80
  Style 0,80 1,00
  Date 1,00 0,90
  Mode 1,00 1,00

Kita hitung hasilnya dengan tiga konfigurasi bobot. Apakah kandidat A atau B yang lebih tinggi berubah? Apakah perubahan tersebut logis?

Ini akan memperlihatkan apakah formula terlalu sensitif terhadap satu parameter.

Output Hari 6:

- Weight Configuration.
- Scoring Simulation Spreadsheet.
- Ranking Test Results.
- Rekomendasi bobot awal dan ambang skor.
  Kriteria selesai: sistem mampu mengurutkan kandidat secara konsisten, dan setiap perubahan ranking dapat dijelaskan.

Hari 7 — Merancang Session-First Matching dan Partner Matching
Core algorithm
Tujuan: menyelesaikan mekanisme inti LaFriend.

Di sinilah kita menggabungkan seluruh formula dari Hari 1–6.

1. Session-First Matching
   Susun langkah algoritma:
1. Pengguna mengirim Study Intent.
1. Sistem mengambil Study Session aktif.
1. Filter sesi berdasarkan course.
1. Jalankan hard constraint.
1. Hitung compatibility score.
1. Urutkan dari skor tertinggi.
1. Ambil maksimal lima rekomendasi.
1. Tampilkan alasan kecocokan.
1. Pengguna dapat melihat detail sesi dan mengajukan permintaan bergabung.
1. Tentukan apakah sesi cocok secara keseluruhan
   Kita harus memutuskan bagaimana membandingkan Study Intent dengan Study Session.

Apakah:

- Membandingkan intent dengan host saja?
- Membandingkan intent dengan rata-rata profil anggota sesi?
- Membandingkan intent dengan karakteristik keseluruhan sesi?
  Saya merekomendasikan pendekatan ketiga: sesi memiliki atribut sendiri, lalu sistem mengevaluasi intent terhadap atribut sesi tersebut. Atribut sesi dapat diperbarui ketika komposisi anggota berubah.

3. Partner Matching
   Jika tidak ada sesi yang memenuhi ambang rekomendasi:
1. Cari Study Intent mahasiswa lain.
1. Filter course yang sesuai.
1. Filter jadwal dan syarat wajib.
1. Hitung pair compatibility.
1. Urutkan kandidat.
1. Tampilkan kandidat yang dapat diundang.
1. Setelah persetujuan, sistem mengusulkan pembentukan sesi.
1. Definisikan fallback
   Kita perlu membuat aturan untuk kondisi:

- Tidak ada sesi yang cocok.
- Tidak ada partner yang cocok.
- Ada partner tetapi belum menyetujui undangan.
- Ada kandidat yang cocok, tetapi kapasitas kelompok sudah penuh.
- Ada kandidat yang cocok tetapi belum mempunyai slot waktu bersama.
  Output Hari 7:
- Session-First Matching Pseudocode.
- Partner Matching Pseudocode.
- Sequence Diagram.
- Ranking and Fallback Rules.
  Kriteria selesai: input Study Intent yang sama selalu menghasilkan alur keputusan yang dapat ditelusuri.

Hari 8 — Group Feasibility, Session Formation, dan Lifecycle
Group formation
Tujuan: menyelesaikan bagaimana kandidat individu berkembang menjadi satu kelompok belajar yang benar-benar dapat melaksanakan sesi.

Pekerjaan yang harus diselesaikan:

1. Pairwise compatibility
   Tetapkan formula:
   \[
   S*{avg}(G)=
   \frac{2}{n(n-1)}
   \sum*{i<j}S\_{pair}(i,j)
   \]

\[
S*{min}(G)=\min*{i<j}S\_{pair}(i,j)
\]

\[
S*{group}=0.7S*{avg}+0.3S\_{min}
\]

Evaluasi apakah komposisi 70% dan 30% sudah sesuai untuk baseline atau perlu diuji. 2. Group feasibility
Kelompok harus memenuhi:
\[
H*{group}=
H*{course}
\times H*{time}
\times H*{capacity}
\times H*{deadline}
\times H*{safety}
\]

3. Group size
   Tentukan mekanisme:

- Minimal anggota harus terpenuhi.
- Maksimal anggota tidak boleh terlampaui.
- Host dihitung sebagai anggota.
- Anggota yang menolak undangan tidak dihitung sebagai anggota aktif.

4. Session lifecycle
   Buat status yang jelas:
   Status Makna
   DRAFT Sesi belum siap dipublikasikan
   OPEN Menerima permintaan bergabung
   FULL Kapasitas terpenuhi
   PROPOSED Slot sesi diusulkan
   CONFIRMED Waktu dan peserta terkonfirmasi
   COMPLETED Sesi dinyatakan selesai
   CANCELLED Sesi dibatalkan
   EXPIRED Melewati batas aktif

Untuk Study Intent, definisikan lifecycle terpisah:

ACTIVE → MATCHED → CONVERTED / EXPIRED / CANCELLED

Satu Study Intent yang berubah menjadi sesi harus memiliki keterkaitan yang jelas. Jangan sampai status intent dan status sesi disimpan sebagai satu status yang sama. 5. Approval dan confirmation
Definisikan:

- Siapa yang boleh membuat undangan.
- Siapa yang boleh menyetujui.
- Kapan sesi dapat dikonfirmasi.
- Apa yang terjadi ketika host membatalkan.
- Bagaimana jika salah satu anggota tidak merespons.
  Output Hari 8:
- Group Feasibility Specification.
- Session Lifecycle Diagram.
- Intent Lifecycle Diagram.
- Membership and Invitation Rules.
  Kriteria selesai: sistem tidak mungkin menyatakan sesi sudah terkonfirmasi sebelum semua syarat peserta, waktu, dan kapasitas dipenuhi.

Hari 9 — Merancang Feedback dan Evaluation Model
Evaluation system
Tujuan: memastikan LaFriend dapat mengukur keberhasilan dan mengumpulkan data untuk memperbaiki formula.

Pekerjaan yang harus diselesaikan:

1. Kunci jenis feedback
   Pisahkan tiga kelompok:
   Jenis Waktu pengambilan Data
   Recommendation Feedback Setelah rekomendasi Relevance, schedule fit, join/reject
   Session Feedback Setelah sesi Completion, usefulness, topic relevance
   Operational Feedback Otomatis Timestamp, confirmation, cancellation

2. Tentukan formula metrik
   Time to Confirmation:
   \[
   T=t*{confirmed}-t*{submitted}
   \]

Match-to-Session Conversion:
\[
CR=\frac{N*{confirmed}}{N*{intent\ with\ recommendation}}\times100\%
\]

Session Completion Rate:
\[
SCR=
\frac{N*{completed}}{N*{confirmed,\ elapsed}}\times100\%
\]

Average Session Relevance:
\[
ASR=\frac{\sum r_i}{5n}\times100\%
\]

3. Tentukan aturan pengumpulan feedback
   Contohnya:

- Feedback hanya tersedia kepada anggota sesi.
- Feedback sesi hanya dapat diberikan setelah jadwal pelaksanaan.
- Feedback masing-masing peserta disimpan terpisah.
- Feedback tidak boleh diubah tanpa pencatatan.
- Sesi dengan laporan yang saling bertentangan ditandai untuk peninjauan.

4. Tentukan metode kalibrasi bobot
   Kita harus memisahkan:

- Evaluasi formula awal.
- Pengumpulan feedback pilot.
- Analisis hubungan faktor matching dengan hasil sesi.
- Usulan perubahan bobot.
- Pengujian formula baru.
- Persetujuan untuk mengganti konfigurasi produksi.
  Jangan mengubah bobot secara otomatis hanya karena satu feedback.

5. Tentukan baseline
   Pengukuran sebelum dan sesudah harus memakai definisi yang sebanding.

Contohnya:

- Baseline: waktu mulai mencari partner hingga jadwal sesi dikonfirmasi.
- LaFriend: waktu pengiriman Study Intent hingga jadwal sesi dikonfirmasi.
  Output Hari 9:
- Feedback Data Specification.
- Evaluation Formula.
- Measurement Plan.
- Weight Calibration Procedure.
  Kriteria selesai: kita mempunyai cara objektif untuk mengetahui apakah LaFriend benar-benar meningkatkan proses pencarian partner belajar.

Hari 10 — Integrasi seluruh desain dan validasi sistem
Design freeze
Tujuan: memastikan semua bagian yang sudah dirancang saling terhubung dan tidak saling bertentangan.

Hari kesepuluh adalah hari audit. Jangan menambahkan fitur baru kecuali memang diperlukan untuk menutup kekurangan desain inti.

Pekerjaan yang harus diselesaikan:

1. Susun arsitektur sistem
   Tentukan modul dan tanggung jawabnya:
   Modul Tanggung jawab
   Authentication Login dan verifikasi mahasiswa
   Student Profile Data pengguna
   Study Intent Membuat dan mengelola kebutuhan belajar
   Preprocessing Normalisasi input
   Constraint Engine Hard constraint filtering
   Compatibility Engine Perhitungan skor
   Session Matcher Pencarian sesi
   Partner Matcher Pencarian calon partner
   Group Validator Validasi kelompok
   Session Manager Join, invite, confirmation, lifecycle
   Feedback Manager Pengumpulan feedback
   Evaluation Engine Perhitungan metrik dan kalibrasi

2. Buat end-to-end pseudocode
   Minimal harus mencakup:
   def process_study_intent(intent): normalized_intent = preprocess(intent) available_sessions = find_active_sessions( normalized_intent.course ) eligible_sessions = filter_constraints( normalized_intent, available_sessions ) ranked_sessions = calculate_compatibility( normalized_intent, eligible_sessions ) recommendations = rank_and_select( ranked_sessions ) if recommendations: return recommendations available_intents = find_other_intents( normalized_intent.course ) eligible_partners = filter_constraints( normalized_intent, available_intents ) ranked_partners = calculate_compatibility( normalized_intent,

Ini baru pseudocode alur utama. Pada dokumen final, kita perlu menambahkan validasi status, kapasitas, deduplikasi, dan group feasibility. 3. Buat test scenarios
Minimal siapkan skenario berikut:
No. Skenario Ekspektasi
1 Course sama, semua preferensi cocok Direkomendasikan
2 Course berbeda Ditolak
3 Topic berbeda tetapi course sama Skor lebih rendah
4 Goal berbeda tetapi kompatibel Tetap dapat direkomendasikan
5 Tidak ada waktu bersama Ditolak
6 Waktu bersama di bawah minimum Ditolak
7 Sesi telah penuh Ditolak
8 Sesi melewati deadline Ditolak
9 Tidak ada sesi, tetapi ada partner cocok Partner matching dijalankan
10 Tidak ada sesi maupun partner Intent tetap terbuka
11 Individu cocok tetapi kelompok tidak cocok Kelompok tidak direkomendasikan
12 Seluruh anggota memiliki slot bersama Kelompok layak
13 Satu undangan ditolak Status kelompok diperbarui
14 Host membatalkan sesi Sesi cancelled
15 Sesi terkonfirmasi dan terlaksana Feedback dapat diberikan

Tambahkan juga test kasus batas, seperti jadwal tepat 60 menit, kapasitas tepat maksimum, target date tepat pada deadline, serta dua kandidat dengan skor yang sama. 4. Lakukan audit konsistensi
Periksa:

- Apakah seluruh variabel dalam formula tersedia pada database?
- Apakah seluruh formula mempunyai rentang nilai yang jelas?
- Apakah bobot scoring berjumlah 1?
- Apakah ada parameter yang dihitung dua kali sebagai hard dan soft constraint?
- Apakah formula pasangan konsisten dengan formula kelompok?
- Apakah Session Matching dan Partner Matching memakai definisi kompatibilitas yang konsisten?
- Apakah lifecycle intent dan session tidak saling bertentangan?
- Apakah seluruh hasil rekomendasi bisa dijelaskan?
  Output Hari 10:
- System Architecture Diagram.
- Complete Pseudocode.
- Final Formula Documentation.
- Test Scenario Document.
- System Design Specification versi 1.0.
  Kriteria selesai: desain sudah dapat diberikan kepada developer untuk diterjemahkan menjadi modul backend tanpa perlu menebak aturan bisnis.

10. Dashboard progres harian
    Berikut checklist yang bisa kita gunakan untuk mengontrol penyelesaian setiap hari.
    LaFriend design sprint
    0%

0 dari 49 pekerjaan selesai
Hari 1 — Konsep dan business rules
0/4

[ ] Menentukan aktor dan objek sistem
[ ] Mengunci alur utama LaFriend
[ ] Menentukan definisi target date
[ ] Menyusun business rules dan scope

Hari 2 — Database dan ERD
0/5

[ ] Mendefinisikan Student Profile
[ ] Mendefinisikan Study Intent
[ ] Mendefinisikan Study Session
[ ] Mendefinisikan entitas pendukung
[ ] Menggambar ERD dan data dictionary

Hari 3 — Input dan preprocessing
0/5

[ ] Menentukan input wajib dan opsional
[ ] Membuat enum kategori
[ ] Menetapkan normalisasi topic dan course
[ ] Menetapkan format availability
[ ] Menetapkan validation rules

Hari 4 — Hard constraint
0/5

[ ] Memisahkan hard dan soft constraints
[ ] Menetapkan course dan date filtering
[ ] Memformulasikan availability filtering
[ ] Menetapkan kapasitas dan safety rules
[ ] Membuat test constraint

Hari 5 — Soft constraint dan scoring
0/5

[ ] Menetapkan formula topic
[ ] Menetapkan formula schedule
[ ] Membuat goal compatibility matrix
[ ] Membuat style dan mode matrix
[ ] Menyelesaikan formula final

Hari 6 — Bobot dan ranking
0/5

[ ] Menetapkan bobot awal
[ ] Membuat skenario pasangan
[ ] Menguji sensitivitas bobot
[ ] Menentukan threshold eksperimen
[ ] Menyelesaikan ranking rules

Hari 7 — Matching engine
0/5

[ ] Merancang Session-First Matching
[ ] Merancang Partner Matching
[ ] Membuat ranking pseudocode
[ ] Menetapkan fallback conditions
[ ] Membuat sequence diagram

Hari 8 — Group dan lifecycle
0/5

[ ] Memformulasikan pairwise compatibility
[ ] Menyelesaikan group feasibility
[ ] Menetapkan group size rules
[ ] Membuat session lifecycle
[ ] Membuat invitation dan confirmation rules

Hari 9 — Feedback dan evaluasi
0/5

[ ] Mendesain recommendation feedback
[ ] Mendesain session feedback
[ ] Memformulasikan evaluation metrics
[ ] Menetapkan baseline
[ ] Menetapkan weight calibration procedure

Hari 10 — Finalisasi desain
0/5

[ ] Menyusun architecture diagram
[ ] Menggabungkan pseudocode
[ ] Menyelesaikan test scenarios
[ ] Melakukan audit konsistensi
[ ] Menerbitkan System Design Specification v1.0

Reset checklist

11. Prioritas yang tidak boleh terlewat
    Ada beberapa hal yang menurutku harus kita jaga agar 10 hari ini tidak melebar.
    Prioritas Tingkat
    Ketepatan data dan Study Intent Wajib
    Hard constraint filtering Wajib
    Compatibility scoring Wajib
    Session-First dan Partner Matching Wajib
    Group Feasibility Wajib
    Session lifecycle Wajib
    Feedback dan evaluation metrics Wajib
    GLiNER Intent Parser Opsional
    Machine learning untuk ranking Tidak perlu untuk versi pertama
    Automatic group optimization Di luar scope awal
    Dynamic weight adjustment real-time Di luar scope awal

Saran saya: jangan mulai coding sebelum setidaknya Hari 1–8 selesai dan keputusan intinya sudah disetujui. Khususnya, kita jangan sampai sudah membuat backend matching tetapi ternyata definisi target date, availability, kapasitas kelompok, atau status Study Intent masih berubah.

Setelah roadmap ini, kita mulai dari Hari 1: mengunci business rules dan mendefinisikan perilaku sistem LaFriend secara lengkap, lalu setiap hasilnya kita dokumentasikan sebagai bagian dari System Design Specification.
