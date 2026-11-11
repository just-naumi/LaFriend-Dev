Bro, menurutku LaFriend perlu dibangun dengan prinsip constraint-first, score-second, feedback-driven.

Artinya, sistem tidak langsung memberi skor kepada semua mahasiswa atau sesi. Sistem harus memastikan kandidat memang layak terlebih dahulu, baru menghitung tingkat kecocokannya. Setelah sesi dilaksanakan, feedback digunakan untuk mengevaluasi apakah sistem berhasil mempertemukan mahasiswa dengan kelompok belajar yang tepat.

Kita bisa memodelkan keseluruhan sistem dalam enam tahap:

1. Input

Study Intent + Student Profile

2. Preprocessing

Normalisasi course, topic, goal, dan availability

3. Hard Constraint Filtering

Membuang kandidat yang tidak memenuhi syarat wajib

4. Compatibility Scoring

Menghitung kecocokan sesi atau calon partner

5. Recommendation & Confirmation

Rekomendasi → join/invite → validasi kelompok → konfirmasi

6. Feedback & Evaluation

Session completion, relevance, schedule fit, dan matching evaluation

Alur utama sistem LaFriend yang akan kita formulasikan.

1. Input: parameter apa saja yang dibutuhkan?
   Hal pertama yang harus kita tetapkan adalah representasi matematis dari kebutuhan belajar mahasiswa.

Saya menyarankan setiap permintaan belajar direpresentasikan sebagai sebuah Study Intent.

Misalkan mahasiswa \(u_i\) membuat Study Intent \(I_i\):
\[
I_i = (C_i,T_i,G_i,D_i,A_i,L_i,M_i,N_i)
\]

Berikut penjelasan setiap parameter.
Parameter Simbol Bentuk data Keterangan
Course \(C_i\) ID/kategori Mata kuliah yang ingin dipelajari
Topic \(T_i\) Set of tags Materi atau topik spesifik
Learning Goal \(G_i\) Kategori Tujuan sesi belajar
Target Date \(D_i\) Date Tanggal target sesi
Availability \(A_i\) Interval waktu Waktu ketika mahasiswa tersedia
Collaboration Style \(L_i\) Kategori/preferensi Gaya belajar yang disukai
Learning Mode \(M_i\) Kategori Online, offline, atau fleksibel
Group Size \(N_i\) Min–max Ukuran kelompok yang diinginkan

Kita breakdown satu per satu.
A. Course \((C_i)\)
Mata kuliah sebaiknya menggunakan ID atau data terstandarisasi, bukan teks bebas.

Contoh:
C_i = TC2043
Course = Struktur Data

Dua mahasiswa hanya dianggap memiliki course yang sama apabila ID mata kuliahnya sama.
\[
CourseMatch(i,j)=
\begin{cases}
1 & C_i=C_j\\
0 & C_i\neq C_j
\end{cases}
\]

Untuk versi awal, saya sarankan course menjadi hard constraint, bukan sekadar komponen skor. Mahasiswa yang mencari partner Struktur Data tidak seharusnya mendapatkan rekomendasi sesi Pemrograman Web hanya karena topiknya mirip.
B. Topic \((T_i)\)
Topic berisi kumpulan materi yang ingin dipelajari.

Contoh:
T_i = {
"Binary Tree",
"Graph",
"Tree Traversal"
}

Mahasiswa lain mungkin memiliki:
T_j = {
"Binary Tree",
"Graph",
"Hash Table"
}

Kita dapat menghitung kesamaan topik menggunakan Jaccard Similarity:
\[
S\_{topic}(i,j)=
\frac{|T_i\cap T_j|}{|T_i\cup T_j|}
\]

Hasilnya berada pada rentang 0–1.

Contoh di atas:

- Irisan: 2 topik.
- Gabungan: 4 topik.
  \[
  S\_{topic}=\frac{2}{4}=0.5
  \]

Artinya, kesamaan topik kedua Study Intent adalah 50%.

Jaccard cocok sebagai baseline karena sederhana, transparan, dan mudah dijelaskan kepada pengguna.
C. Learning Goal \((G_i)\)
Learning Goal menjelaskan untuk apa mahasiswa ingin belajar.

Saya menyarankan kategori awal:
Kode Learning goal
G1 Exam preparation
G2 Understanding concepts
G3 Problem solving
G4 Assignment discussion
G5 Peer teaching

Kecocokan tujuan tidak harus selalu identik. Misalnya, mahasiswa yang ingin memahami konsep bisa cocok dengan mahasiswa yang ingin mengajar atau menjelaskan konsep tersebut.

Karena itu, kita menggunakan matriks kompatibilitas:
\[
S\_{goal}(i,j)=M_G[G_i,G_j]
\]

Contoh nilai awal:
Goal A Goal B Skor
Exam preparation Exam preparation 1.00
Understanding concepts Peer teaching 0.85
Problem solving Problem solving 1.00
Assignment discussion Exam preparation 0.50
Understanding concepts Assignment discussion 0.65

Nilai tersebut merupakan hipotesis desain awal, bukan hasil penelitian. Nanti perlu divalidasi melalui pilot.
D. Availability \((A_i)\)
Ini salah satu parameter paling penting dalam LaFriend.

Availability harus direpresentasikan sebagai interval waktu, bukan hanya label seperti pagi, siang, atau malam.

Contoh:
A_i = {
Monday: [09:00, 12:00],
Tuesday: [13:00, 17:00],
Wednesday: [10:00, 12:00]
}

Dengan representasi ini, sistem dapat menghitung waktu yang benar-benar beririsan dengan mahasiswa lain.
E. Collaboration Style \((L_i)\)
Kategori yang bisa digunakan:

- Discussion-based learning
- Problem-solving together
- Peer teaching
- Focused individual study
  Kecocokannya dihitung menggunakan matriks yang serupa dengan Learning Goal:
  \[
  S\_{style}(i,j)=M_L[L_i,L_j]
  \]

Contohnya, mahasiswa yang memilih problem-solving together mungkin cocok dengan mahasiswa yang memilih gaya yang sama, tetapi belum tentu cocok dengan mahasiswa yang lebih menyukai belajar secara individual.
F. Target Date, Mode, dan Group Size
Target date menentukan kapan sesi diharapkan berlangsung. Mode menentukan preferensi online/offline, sementara group size menentukan batas jumlah peserta.

Contoh:
Target Date : 20 November 2026
Mode : Offline
Group Size : 2–4 students

Ketiga parameter ini nantinya digunakan untuk memastikan bahwa sesi yang direkomendasikan memang sesuai kebutuhan mahasiswa.

2. Preprocessing: mengubah input menjadi data yang bisa dihitung
   Sebelum matching dilakukan, seluruh input perlu distandarisasi.

Sebagai contoh:
Input pengguna Hasil normalisasi
Struktur Data TC2043
Binary tree binary_tree
Binary Tree binary_tree
Belajar buat UTS exam_preparation
Offline OFFLINE

Jika pengguna memasukkan deskripsi bebas, GLiNER dapat digunakan secara opsional untuk membantu mengidentifikasi entitas seperti nama course atau topik.

Namun, untuk jadwal dan tanggal, gunakan parser tanggal/waktu yang memang dirancang untuk memproses informasi temporal. Hasil ekstraksi tetap harus bisa diedit dan dikonfirmasi pengguna.

Prinsipnya: preprocessing hanya mempersiapkan representasi data. Keputusan matching tetap dilakukan oleh rule-based engine. 3. Hard Constraint Filtering: menentukan kandidat yang layak
Ini tahap yang sangat penting.

Kita perlu membedakan dua hal:

- Hard constraint: syarat yang wajib dipenuhi. Jika gagal, kandidat tidak boleh direkomendasikan.
- Soft constraint: preferensi yang boleh berbeda, tetapi memengaruhi skor kecocokan.
  Misalkan sistem sedang mencari kandidat sesi \(S_j\) untuk Study Intent \(I_i\).

Kita definisikan fungsi kelayakan:
\[
H(i,j)=
H_C \times H_D \times H_A \times H_M \times H_S \times H_N
\]

Masing-masing komponen bernilai 0 atau 1.
Constraint Kondisi agar bernilai 1
\(H_C\) Course sama
\(H_D\) Tanggal sesi masih sesuai target
\(H_A\) Ada waktu bersama yang cukup
\(H_M\) Mode belajar kompatibel
\(H_S\) Kandidat aktif, tidak diblokir, dan lolos pemeriksaan keamanan
\(H_N\) Kapasitas kelompok masih tersedia

Hasil akhirnya:
\[
H(i,j)=
\begin{cases}
1 & \text{Semua constraint terpenuhi}\\
0 & \text{Minimal satu constraint gagal}
\end{cases}
\]

Dengan demikian, kandidat yang memperoleh nilai \(H(i,j)=0\) langsung dieliminasi tanpa perlu menghitung compatibility score.

Contoh: dua mahasiswa memiliki topik dan tujuan belajar yang sangat cocok, tetapi tidak mempunyai waktu belajar yang beririsan. Sistem tidak boleh merekomendasikan mereka sebagai partner untuk sesi yang sama.
3.1. Formula khusus untuk availability
Misalkan:

- \(A_i\): kumpulan interval waktu mahasiswa pertama.
- \(A_j\): kumpulan interval waktu mahasiswa kedua.
- \(\tau\): durasi minimum sesi belajar.
  Kita hitung irisan waktu keduanya:
  \[
  A\_{ij}=A_i\cap A_j
  \]

Kemudian, cari durasi interval bersama terpanjang:
\[
O*{ij}=\max*{r\in A\_{ij}} Duration(r)
\]

Constraint waktu:
\[
H*A(i,j)=
\begin{cases}
1 & O*{ij}\geq \tau\\
0 & O\_{ij}<\tau
\end{cases}
\]

Sebagai nilai awal untuk PoC, kita bisa menggunakan:
\[
\tau=60\text{ menit}
\]

Contoh:
Mahasiswa Availability
A 09.00–12.00
B 10.00–11.30
C 11.00–13.00

Untuk A dan B, waktu bersama terpanjang adalah 90 menit. Mereka lolos constraint 60 menit.

Untuk A dan C, waktu bersama hanya 60 menit. Mereka juga lolos.

Akan tetapi, jika B tersedia pukul 13.00–14.00, sementara A hanya tersedia pukul 09.00–12.00, keduanya tidak lolos.

Penting untuk group matching: jangan hanya memeriksa irisan waktu antara pembuat intent dengan satu calon partner. Seluruh anggota harus memiliki waktu bersama.

Untuk kelompok \(G\):
\[
A*G=\bigcap*{u\in G}A_u
\]

Kelompok dinyatakan layak apabila:
\[
\max\_{r\in A_G}Duration(r)\geq\tau
\]

Ini akan menjadi salah satu pembeda LaFriend dibandingkan sistem pencarian partner biasa.

4. Compatibility Scoring: menghitung tingkat kecocokan
   Setelah kandidat lolos hard constraint, barulah sistem menghitung skor.

Saya menyarankan menggunakan Weighted Linear Scoring untuk versi pertama. Metode ini cocok karena mudah dijelaskan, mudah diimplementasikan, dan bobotnya dapat disesuaikan setelah pilot.

Kita definisikan enam komponen:
\[
Score(i,j)=100\sum\_{k=1}^{6}w_kS_k(i,j)
\]

Dengan:

- \(w_k\): bobot setiap parameter.
- \(S_k\): nilai kecocokan parameter, berada pada rentang 0–1.
- Total seluruh bobot harus sama dengan 1.
  4.1. Rancangan bobot awal
  Berikut bobot awal yang saya rekomendasikan untuk diuji:
  Parameter Simbol Bobot
  Topic Similarity \(S_T\) 30%
  Schedule Compatibility \(S_A\) 30%
  Learning Goal Compatibility \(S_G\) 20%
  Collaboration Style \(S_L\) 10%
  Target Date Compatibility \(S_D\) 5%
  Learning Mode Compatibility \(S_M\) 5%
  Total 100%

Mengapa bobotnya seperti ini?

Topic (30%) dan Schedule (30%) menjadi prioritas karena LaFriend bertujuan mempertemukan orang yang ingin mempelajari materi yang relevan dan benar-benar memiliki waktu untuk belajar bersama.

Learning Goal (20%) berada di urutan berikutnya karena mahasiswa dengan topik sama belum tentu memiliki tujuan belajar yang sama.

Sementara itu, collaboration style dan mode belajar membantu memperhalus kecocokan. Target date tetap diperhitungkan, tetapi ketepatan tanggal juga sudah dilindungi oleh hard constraint.
4.2. Rumus masing-masing komponen
A. Topic Similarity
\[
S_T=\frac{|T_i\cap T_j|}{|T_i\cup T_j|}
\]

B. Schedule Compatibility

Untuk tahap scoring, kita dapat menggunakan durasi irisan waktu terpanjang:
\[
S*A=\min\left(1,\frac{O*{ij}}{\tau}\right)
\]

Namun, ada satu catatan: jika \(\tau\) juga digunakan sebagai hard constraint, kandidat yang lolos akan memiliki \(S_A=1\). Itu membuat komponen jadwal tidak lagi membedakan kandidat.

Karena itu, ada dua pilihan desain:

- Pilihan sederhana: gunakan minimum 60 menit sebagai hard constraint dan jadikan kualitas jadwal sebagai skor berdasarkan banyaknya pilihan slot yang tersedia.
- Pilihan yang saya rekomendasikan: gunakan hard constraint untuk memastikan terdapat setidaknya satu slot yang layak, lalu gunakan jumlah atau luas irisan waktu untuk mengukur fleksibilitas jadwal.
  Untuk pilihan kedua:
  \[
  S*A=\min\left(1,\frac{O^{total}*{ij}}{\tau\_{ref}}\right)
  \]

Di sini \(O^{total}_{ij}\) adalah total durasi waktu yang beririsan dalam rentang tanggal pencarian, sedangkan \(\tau_{ref}\) adalah target total waktu bersama. Misalnya, jika target fleksibilitas adalah 180 menit, mahasiswa yang memiliki total overlap 90 menit memperoleh skor 0,5.

Kita tetap perlu memastikan minimal ada satu interval kontinu yang cukup panjang untuk melaksanakan sesi.

C. Learning Goal Compatibility
\[
S_G=M_G[G_i,G_j]
\]

Nilai diperoleh dari matriks kompatibilitas tujuan belajar yang telah disusun.

D. Collaboration Style Compatibility
\[
S_L=M_L[L_i,L_j]
\]

Nilai diperoleh dari matriks kompatibilitas gaya kolaborasi.

E. Target Date Compatibility

Misalkan tanggal target intent adalah \(D_i\), sedangkan tanggal sesi yang ditawarkan adalah \(D_j\).

Jika sesi melewati deadline, kandidat tidak lolos hard constraint. Untuk sesi yang masih sesuai:
\[
S_D=e^{-\frac{|D_i-D_j|}{7}}
\]

Selisih tanggal dihitung dalam hari. Angka 7 merupakan skala awal satu minggu, yang nantinya bisa dievaluasi melalui pilot.

F. Learning Mode Compatibility
\[
S_M=M_M[M_i,M_j]
\]

Contohnya, offline dengan offline memperoleh nilai 1. Jika salah satu pengguna memilih fleksibel, sistem dapat menganggap mode tersebut kompatibel.
4.3. Contoh perhitungan
Misalkan mahasiswa A mencari partner dan sistem menemukan mahasiswa B.

Nilai kecocokan yang diperoleh:
Parameter Nilai Bobot Kontribusi
Topic 1,00 0,30 0,300
Schedule 0,80 0,30 0,240
Goal 1,00 0,20 0,200
Collaboration style 0,75 0,10 0,075
Target date 0,90 0,05 0,045
Mode 1,00 0,05 0,050
Total 1,00 0,910

Maka:
\[
Score(A,B)=100(0.910)=91
\]

Compatibility Score
91/100

Highly compatible — contoh ambang awal
Mengapa direkomendasikan?

- Materi yang dicari sama.
- Waktu belajar memiliki irisan yang baik.
- Tujuan belajar sama.
- Gaya kolaborasi cukup sesuai.

Angka 91 bukan berarti probabilitas keberhasilan sesi sebesar 91%. Angka ini adalah indeks kecocokan berdasarkan parameter dan bobot yang telah ditentukan.

Itu penting agar LaFriend tidak memberikan interpretasi statistik yang tidak didukung oleh datanya.

5. Recommendation Engine: bagaimana sistem memilih hasil?
   Di tahap ini kita harus menerapkan konsep utama LaFriend, yaitu Session-First Matching.

Jangan langsung mencari mahasiswa satu per satu. Sistem harus terlebih dahulu mencari sesi belajar yang sudah tersedia.

Ada dua jalur.
Jalur A — Session Matching
Prioritas pertama

1. Ambil seluruh sesi aktif yang sesuai dengan course.
2. Jalankan hard constraint filtering.
3. Hitung compatibility score untuk setiap sesi yang lolos.
4. Urutkan dari skor tertinggi.
5. Tampilkan kandidat sesi yang memenuhi ambang rekomendasi.

Jalur B — Partner Matching
Fallback

1. Jalankan ketika tidak ada sesi aktif yang cukup cocok.
2. Cari Study Intent lain dengan course yang sama.
3. Jalankan hard constraint filtering terhadap calon partner.
4. Hitung dan urutkan compatibility score.
5. Berikan rekomendasi mahasiswa yang bisa diajak membentuk sesi baru.

Untuk PoC, kita dapat menggunakan konfigurasi awal seperti ini:
Parameter keputusan Nilai awal
Minimum recommendation score 70/100
Jumlah rekomendasi yang ditampilkan Maksimal 5
Minimum continuous shared availability 60 menit
Maksimal ukuran kelompok Ditentukan dalam Study Intent

Ambang 70 dan jumlah rekomendasi 5 merupakan konfigurasi eksperimen, bukan nilai universal. Kita perlu mengevaluasinya pada data pilot.

Jika tidak ada kandidat yang mencapai ambang, sistem tidak boleh memaksakan rekomendasi. Intent tetap berstatus OPEN atau UNMATCHED.
5.1. Group Feasibility: memastikan satu kelompok benar-benar bisa terbentuk
Ini bagian yang menurutku jangan sampai terlewat.

Misalkan A ingin membentuk kelompok bersama B dan C. Masing-masing memiliki kecocokan individual yang tinggi dengan A, tetapi belum tentu B dan C cocok satu sama lain.

Karena itu, kita perlu menguji kompatibilitas seluruh kelompok.

Misalkan anggota kelompok adalah:
\[
G=\{u_1,u_2,\ldots,u_n\}
\]

Hitung skor rata-rata seluruh pasangan:
\[
S*{avg}(G)=
\frac{2}{n(n-1)}
\sum*{i<j}S\_{pair}(i,j)
\]

Tetapi rata-rata saja belum cukup. Bisa saja sebagian besar anggota cocok, sementara satu anggota memiliki kecocokan yang sangat rendah.

Karena itu, saya mengusulkan:
\[
S*{group}=0.7S*{avg}+0.3S\_{min}
\]

Dengan:
\[
S*{min}=\min*{i<j}S\_{pair}(i,j)
\]

Hasilnya mempertimbangkan kecocokan rata-rata sekaligus pasangan dengan kecocokan terendah.

Kelompok tetap harus lolos constraint kapasitas dan waktu bersama:
\[
H*{group}=H*{capacity}\times H*{common\ time}\times H*{safety}
\]

Jika \(H\_{group}=0\), kelompok tidak layak dibentuk meskipun skor rata-ratanya tinggi.

Catatan implementasi: sistem hanya menyarankan komposisi kelompok. Setiap anggota tetap harus menerima undangan atau menyetujui sesi. Jangan otomatis memasukkan mahasiswa ke dalam kelompok.

6. Feedback System: bagaimana sistem belajar dari hasil sesi?
   Setelah sesi terbentuk, pekerjaan LaFriend belum selesai.

Kita perlu mengetahui apakah rekomendasi yang diberikan benar-benar menghasilkan sesi belajar yang bermanfaat.

Menurutku feedback sebaiknya dibagi menjadi tiga kategori.
A. Recommendation Feedback
Diberikan ketika mahasiswa melihat rekomendasi, tetapi belum tentu bergabung.
Parameter Bentuk feedback
Topic relevance Sesuai / Tidak sesuai
Schedule fit Cocok / Tidak cocok
Learning goal Sesuai / Tidak sesuai
Collaboration style Cocok / Tidak cocok
Recommendation decision Join / Ignore / Reject

Feedback ini membantu mengidentifikasi mengapa mahasiswa tertarik atau tidak tertarik pada suatu rekomendasi.
B. Session Feedback
Diberikan setelah jadwal sesi terlewati.
Parameter Skala
Apakah sesi benar-benar terlaksana? Yes / No
Relevansi materi 1–5
Kesesuaian jadwal 1–5
Kesesuaian gaya kolaborasi 1–5
Kebermanfaatan sesi 1–5

Untuk mengurangi bias, sistem dapat meminta setiap anggota memberikan feedback masing-masing.
C. Operational Feedback
Ini bukan feedback yang diisi secara manual, melainkan data aktivitas sistem.

Misalnya:

- Waktu intent dibuat.
- Waktu rekomendasi ditampilkan.
- Waktu pengguna bergabung.
- Waktu sesi dikonfirmasi.
- Status sesi.
- Jumlah anggota yang hadir atau mengonfirmasi sesi selesai.
  Data ini penting karena kita tidak hanya ingin mengetahui apakah pengguna menyukai LaFriend, tetapi juga apakah sistem benar-benar mengurangi waktu pencarian partner belajar.
  6.1. Rumus evaluasi sistem
  Saya menyarankan empat indikator utama.

1. Time to Session Confirmation

Mengukur durasi dari pembuatan Study Intent hingga sesi dikonfirmasi.
\[
T*{confirm}=t*{confirm}-t\_{submit}
\]

Gunakan median sebagai metrik utama agar beberapa kasus yang sangat lama tidak terlalu mendistorsi hasil.
\[
T*{median}=Median(T*{confirm,1},\ldots,T\_{confirm,n})
\]

Bandingkan dengan kondisi sebelum menggunakan LaFriend:
\[
Improvement=
\frac{T*{baseline}-T*{LaFriend}}{T\_{baseline}}
\times100\%
\]

Definisi awal dan akhir pengukuran harus sama untuk kedua kondisi.

2. Match-to-Session Conversion Rate

Mengukur berapa banyak Study Intent yang berhasil menjadi sesi terkonfirmasi.
\[
ConversionRate=
\frac{N*{confirmed}}{N*{intent\ with\ recommendation}}
\times100\%
\]

Penyebutnya adalah jumlah intent yang benar-benar memperoleh rekomendasi, bukan jumlah seluruh kartu rekomendasi yang ditampilkan.

3. Session Completion Rate

Mengukur berapa banyak sesi terkonfirmasi yang benar-benar terlaksana.
\[
CompletionRate=
\frac{N*{completed}}{N*{confirmed,\ elapsed}}
\times100\%
\]

\(N\_{confirmed,\ elapsed}\) adalah sesi terkonfirmasi yang jadwalnya sudah lewat. Sesi yang belum mencapai tanggal pelaksanaan tidak masuk penyebut.

Untuk menyatakan sesi selesai, kita dapat menggunakan konfirmasi dari host dan setidaknya satu anggota lain. Jika konfirmasi bertentangan, tandai sebagai disputed untuk dievaluasi, bukan otomatis dianggap selesai.

4. Average Session Relevance

Mengukur apakah sesi yang terjadi sesuai dengan kebutuhan awal.

Jika setiap peserta memberikan rating 1–5:
\[
Relevance=
\frac{\sum\_{i=1}^{n}r_i}{5n}
\times100\%
\]

Dengan \(r_i\) sebagai rating relevansi dari masing-masing peserta.

Contoh: jika terdapat empat peserta dengan rating 5, 4, 4, dan 3:
\[
Relevance=\frac{5+4+4+3}{20}\times100\%=80\%
\]

7. Bagaimana feedback memengaruhi formula matching?
   Bagian ini perlu dirancang dengan hati-hati.

Jangan langsung mengubah bobot setiap kali seseorang memberikan rating. Satu atau dua feedback belum cukup untuk menyimpulkan bahwa bobot topic, schedule, atau learning goal harus diubah.

Saya menyarankan pendekatan berikut:
Feedback → Analysis → Weight Calibration
Step 1. Collect feedback

Simpan skor relevansi, kecocokan jadwal, dan gaya kolaborasi.

Step 2. Analyze matching factors

Periksa faktor mana yang sering berkaitan dengan sesi berhasil dan relevansi tinggi.

Step 3. Calibrate weights

Evaluasi apakah bobot saat ini sudah mencerminkan faktor yang benar-benar penting.

Step 4. Update rule-based engine

Bobot diperbarui secara terkontrol, kemudian diuji kembali menggunakan data pilot.

Secara matematis, misalkan:

- \(x\_{ik}\): nilai kecocokan faktor ke-\(k\) untuk rekomendasi ke-\(i\).
- \(y_i\): hasil sesi, misalnya 1 jika sesi berhasil dan 0 jika tidak.
- \(w_k\): bobot faktor ke-\(k\).
  Kita dapat mengevaluasi hubungan masing-masing faktor dengan hasil sesi menggunakan korelasi:
  \[
  \rho_k=Corr(x_k,y)
  \]

Hasil analisis dapat digunakan untuk mengusulkan perubahan bobot. Namun, jangan langsung menganggap korelasi sebagai bukti sebab-akibat.

Untuk prototype, kalibrasi bobot secara offline dan terkontrol lebih aman daripada membuat sistem mengubah bobot secara otomatis setiap kali ada feedback. Dengan begitu, LaFriend tetap rule-based, transparan, dan tidak membutuhkan model machine learning untuk proses matching-nya.

Selain itu, feedback laporan, pemblokiran, atau perilaku tidak aman harus masuk ke proses moderasi dan safety. Jangan mencampurkannya dengan compatibility score.

8. Rangkuman spesifikasi matematika LaFriend
   Supaya nanti mudah diterjemahkan menjadi backend, berikut rancangan yang saya rekomendasikan sebagai baseline versi pertama.
   Komponen Formula/metode Keputusan
   Representasi intent \(I_i=(C_i,T_i,G_i,D_i,A_i,L_i,M_i,N_i)\) Setiap kebutuhan belajar menjadi satu Study Intent
   Course filtering Exact matching Hard constraint
   Availability filtering Irisan interval waktu Minimal 60 menit kontinu
   Topic matching Jaccard Similarity Soft constraint
   Goal matching Compatibility Matrix Soft constraint
   Style matching Compatibility Matrix Soft constraint
   Schedule scoring Total shared availability Soft constraint setelah lolos minimum waktu
   Date scoring Exponential decay Soft constraint selama tanggal masih valid
   Mode matching Compatibility Matrix Soft constraint, dengan mode yang tidak kompatibel dieliminasi
   Final score Weighted Linear Scoring Skala 0–100
   Session matching Ranking berdasarkan score Prioritas pertama
   Partner matching Ranking berdasarkan score Fallback
   Group feasibility Common availability + pairwise compatibility Sebelum kelompok dikonfirmasi
   Feedback Completion, relevance, dan operational metrics Evaluasi dan kalibrasi bobot

Nilai awal untuk eksperimen:
Parameter Nilai
Topic weight 0,30
Schedule weight 0,30
Goal weight 0,20
Collaboration style weight 0,10
Target date weight 0,05
Learning mode weight 0,05
Minimum continuous overlap 60 menit
Referensi total shared availability 180 menit
Recommendation threshold 70/100
Rekomendasi yang ditampilkan Maksimal 5

Nilai-nilai tersebut adalah konfigurasi awal untuk diuji, bukan angka final yang sudah terbukti optimal. 9. Hal yang harus kita pastikan sebelum implementasi
Ada empat keputusan desain yang menurutku penting:

Pertama, jangan mencampur hard constraint dengan scoring. Course, batas waktu, kapasitas, keamanan, dan kelayakan jadwal harus menentukan apakah kandidat boleh masuk ke proses ranking. Skor tinggi tidak boleh mengalahkan syarat wajib.

Kedua, jangan mencampur Session Matching dengan Partner Matching. Keduanya bisa memakai dasar kompatibilitas yang sama, tetapi objek yang dinilai berbeda. Session Matching membandingkan Study Intent dengan sesi yang sudah ada, sedangkan Partner Matching membandingkan dua atau lebih Study Intent mahasiswa.

Ketiga, jangan menjadikan feedback sebagai model pembelajaran otomatis sejak awal. Kumpulkan datanya terlebih dahulu, evaluasi hasilnya, lalu kalibrasi bobot secara terkontrol. Ini mempertahankan transparansi sistem.

Keempat, jangan menganggap recommendation sebagai keberhasilan. Keberhasilan LaFriend baru terbukti ketika mahasiswa benar-benar mendapatkan sesi, mengonfirmasinya, dan melaksanakannya.
Target akhir desain matematis
\[
\boxed{
\text{Study Intent}
\rightarrow
\text{Feasible Candidates}
\rightarrow
\text{Compatibility Ranking}
\rightarrow
\text{Confirmed Session}
\rightarrow
\text{Measured Outcome}
}
\]

Sistem dinilai bukan dari seberapa banyak rekomendasi yang dihasilkan, tetapi dari seberapa efektif rekomendasi tersebut menghasilkan sesi belajar yang benar-benar terlaksana.

Rekomendasi saya: kita tetapkan dulu formulasi matematis ini sebagai baseline LaFriend. Setelah itu, bagian yang paling perlu kita perdalam adalah algoritma Session-First Matching dan Group Feasibility, karena di situlah nilai pembeda LaFriend paling nyata sekaligus bagian yang paling menentukan apakah sistemnya benar-benar bisa bekerja.
