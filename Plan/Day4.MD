Siap bro! Sekarang kita masuk ke bagian yang paling penting dari rancangan LaFriend: Day 4 — Merancang Formula Compatibility Score (Skor Kecocokan).

Pada Day 3, kita sudah menentukan informasi yang dimasukkan mahasiswa, seperti mata kuliah, materi, tujuan belajar, jadwal, gaya belajar, dan metode belajar.

Sekarang kita akan menjawab pertanyaan:

Bagaimana LaFriend menentukan bahwa mahasiswa A cocok belajar bersama mahasiswa B?

Saya akan membangun formulanya dari awal, menggunakan contoh angka, dan menjelaskan alasan setiap perhitungannya. Kita juga akan membedakan mana syarat wajib dan mana faktor penambah skor.
DAY 4 — Compatibility Score Algorithm

1. Tentukan dulu apa yang sebenarnya dihitung
   Misalkan ada dua mahasiswa:
   Mahasiswa A — Andi
   Informasi Pilihan
   Mata kuliah Struktur Data
   Materi Binary Tree
   Tujuan Memahami materi
   Gaya belajar Diskusi
   Metode Offline
   Waktu Rabu, 09.00–12.00

Mahasiswa B — Budi
Informasi Pilihan
Mata kuliah Struktur Data
Materi Binary Tree, BST
Tujuan Memahami materi
Gaya belajar Diskusi
Metode Offline
Waktu Rabu, 10.00–12.00

Dari contoh tersebut, kita bisa melihat bahwa Andi dan Budi punya kebutuhan belajar yang hampir sama dan jadwal yang memungkinkan mereka belajar bersama.

Namun, algoritma tidak boleh hanya mengatakan "mereka mirip".

Kita ingin sistem bisa menjawab:

- Apakah materi mereka sesuai?
- Apakah tujuan belajar mereka sesuai?
- Apakah gaya belajar mereka sesuai?
- Apakah waktu mereka cocok?
- Apakah metode belajar mereka cocok?
  Masing-masing pertanyaan akan menghasilkan nilai, kemudian nilai-nilai tersebut digabungkan.

2. Tahap pertama: pengecekan syarat wajib (Hard Constraint)
   Sebelum menghitung skor, sistem harus memastikan kedua mahasiswa memang bisa belajar bersama.

Saya menyarankan urutannya seperti ini:
Pemeriksaan Hasil contoh
Mata kuliah sama? Ya
Akun aktif dan terverifikasi? Ya
Ada tanggal yang beririsan? Ya
Ada jam yang beririsan? Ya
Metode belajar memungkinkan? Ya

Jika ada syarat wajib yang gagal, kandidat tidak dilanjutkan ke perhitungan skor.

Kita bisa menuliskannya sebagai:
\[
H(A,B)=
\begin{cases}
1,& \text{jika seluruh syarat terpenuhi}\\
0,& \text{jika ada syarat gagal}
\end{cases}
\]

Artinya:

- \(H=1\): boleh dihitung skor kecocokannya.
- \(H=0\): tidak direkomendasikan.
  Penting: skor 95 sekalipun tidak boleh membuat kandidat lolos jika jadwalnya sama sekali tidak bertemu.

3. Tahap kedua: menghitung setiap faktor kecocokan
   Saya menyarankan kita menggunakan lima faktor utama:
   Kode Faktor Bobot awal
   T Kesamaan materi 30%
   G Kesesuaian tujuan belajar 25%
   S Kesesuaian gaya belajar 15%
   D Kesesuaian preferensi tanggal 15%
   M Kesesuaian metode belajar 15%
   Total 100%

Mengapa bobotnya seperti itu?

- Materi mendapat bobot terbesar karena inti LaFriend adalah menemukan teman untuk mempelajari kebutuhan akademik yang relevan.
- Tujuan belajar mendapat bobot besar karena mahasiswa yang ingin memahami konsep bisa memiliki kebutuhan berbeda dari mahasiswa yang hanya ingin menyelesaikan tugas.
- Gaya belajar membantu meningkatkan kenyamanan kolaborasi.
- Preferensi tanggal dan metode membantu memilih kandidat yang lebih sesuai, setelah kelayakan jadwal dipastikan.
  Bobot awal untuk pengujian
  Angka tersebut adalah hipotesis desain, bukan hasil penelitian. Kita harus mengujinya dengan data simulasi dan evaluasi pengguna.

4. Cara menghitung kesamaan materi (Topic Similarity)
   Faktor pertama adalah kesamaan materi yang ingin dipelajari.

Contoh:

- Andi memilih: Binary Tree.
- Budi memilih: Binary Tree dan Binary Search Tree.
  Untuk PoC awal, kita bisa menggunakan metode sederhana bernama Jaccard Similarity.

Jangan khawatir dengan namanya. Intinya, kita menghitung berapa banyak materi yang sama dibandingkan dengan seluruh materi yang dipilih keduanya.

Rumusnya:
\[
T(A,B)=\frac{|A\cap B|}{|A\cup B|}\times100
\]

Keterangan:

- \(A\) = daftar materi Andi.
- \(B\) = daftar materi Budi.
- \(A\cap B\) = materi yang sama.
- \(A\cup B\) = seluruh materi unik dari keduanya.
  Contoh perhitungan:
  Materi Andi Budi
  Binary Tree
  Binary Search Tree —

Hasilnya:
\[
T(A,B)=\frac{1}{2}\times100=50
\]

Hasil: 50/100
Artinya, ada satu materi yang sama dari dua materi unik yang dipilih bersama.

Catatan penting: sebelum dibandingkan, nama materi harus diseragamkan. Misalnya, "BST" dan "Binary Search Tree" harus dikenali sebagai materi yang sama.

Untuk tahap awal, kita tidak perlu langsung menggunakan AI untuk menghitung kesamaan materi. Cukup gunakan daftar materi yang sudah dinormalisasi. Jika nanti dibutuhkan, kita bisa mengembangkan pencocokan berdasarkan hubungan antarmateri. 5. Cara menghitung kesesuaian tujuan belajar (Goal Compatibility)
Faktor kedua adalah tujuan belajar.

Kita tidak boleh hanya menganggap dua mahasiswa cocok jika tujuan mereka sama persis.

Misalnya:

- Andi ingin memahami Binary Tree.
- Budi ingin berlatih soal Binary Tree.
  Mereka justru bisa saling membantu. Andi bisa memahami konsep, sementara Budi bisa mengajak Andi menerapkan konsep tersebut melalui latihan.

Saya menyarankan menggunakan tabel kecocokan tujuan.
Tujuan Andi Tujuan Budi Skor awal
Memahami materi Memahami materi 100
Memahami materi Latihan soal 85
Memahami materi Persiapan ujian 85
Latihan soal Persiapan ujian 85
Mengerjakan tugas Memahami materi 60
Mengerjakan tugas Mengerjakan tugas 100
Tujuan yang tidak berkaitan Tujuan yang tidak berkaitan 30

Angka di atas merupakan contoh penilaian awal. Nanti kita perlu meninjau kembali kombinasi tujuan yang benar-benar saling mendukung.

Dengan pendekatan ini, kita tidak memaksakan semua mahasiswa memiliki tujuan yang identik.

Secara matematis:
\[
G(A,B)=\text{Nilai kecocokan tujuan A dan B}
\]

Nilainya berada pada rentang 0–100 dan diambil dari tabel kecocokan yang ditetapkan sistem. 6. Cara menghitung kesesuaian gaya belajar (Study Style)
Faktor ketiga adalah gaya belajar bersama.

Kita menggunakan empat pilihan yang sudah dirancang pada Day 3:

- Discussion
- Practice
- Teaching
- Focus Study
  Untuk tahap awal, kita bisa menggunakan aturan sederhana:
  Kondisi Skor
  Gaya belajar sama 100
  Gaya belajar saling melengkapi 80
  Gaya belajar berbeda tetapi masih bisa dilakukan bersama 60
  Preferensi saling bertentangan secara jelas 30

Contoh:

- Andi: Discussion.
- Budi: Discussion.
  Maka:
  \[
  S(A,B)=100
  \]

Contoh lainnya:

- Andi: Teaching.
- Budi: Practice.
  Keduanya masih bisa saling melengkapi karena satu mahasiswa dapat menjelaskan materi dan mahasiswa lainnya berlatih.

Maka skor awalnya:
\[
S(A,B)=80
\]

Perlu diingat: skor tersebut merupakan aturan desain awal, bukan fakta bahwa semua mahasiswa dengan gaya tertentu pasti cocok. Nantinya perlu diuji melalui feedback. 7. Cara menghitung preferensi tanggal (Date Preference)
Ini bagian yang perlu kita bedakan dari pengecekan jadwal.

Pada Hard Constraint, kita hanya memastikan bahwa Andi dan Budi memiliki waktu kosong yang bertemu.

Pada Date Preference, kita ingin mengetahui apakah waktu yang sama tersebut juga merupakan waktu yang mereka sukai.

Contoh:
Pilihan Andi Budi
Rabu pukul 10.00 Pilihan pertama Pilihan pertama
Jumat pukul 14.00 Pilihan kedua Pilihan ketiga

Kita dapat memberikan skor berdasarkan prioritas pilihan bersama.
Kondisi Skor
Keduanya menjadikan waktu tersebut pilihan pertama 100
Salah satu pilihan pertama, lainnya pilihan kedua 85
Keduanya menjadikan pilihan kedua 75
Salah satu hanya memilih sebagai alternatif terakhir 60

Untuk mendapatkan skor tanggal, sistem mencari waktu yang sama-sama tersedia, lalu membandingkan tingkat prioritasnya.

Dengan begitu, sistem tidak hanya mencari waktu yang memungkinkan, tetapi juga berusaha memilih waktu yang paling disukai.

Perubahan kecil pada rancangan Day 3: tabel intent_availabilities perlu memiliki tambahan field preference_rank untuk menyimpan urutan prioritas waktu. Contohnya, 1 berarti paling disukai, 2 berarti pilihan kedua, dan seterusnya. 8. Cara menghitung kecocokan metode belajar (Mode Compatibility)
Terakhir adalah metode belajar.

Pilihan yang tersedia:

- Online.
- Offline.
- Hybrid.
  Kita perlu mendukung mahasiswa yang memiliki lebih dari satu pilihan.

Contohnya:
Mahasiswa Pilihan metode
Andi Offline (utama), Online (alternatif)
Budi Offline (utama), Hybrid (alternatif)

Keduanya sama-sama mengutamakan Offline.

Maka:
\[
M(A,B)=100
\]

Aturan awal yang bisa digunakan:
Kondisi Skor
Metode sama dan menjadi pilihan utama 100
Metode sama tetapi salah satu pilihan alternatif 85
Memiliki metode bersama tetapi prioritas berbeda 70
Tidak memiliki metode yang bisa digunakan bersama 0

Jika tidak ada metode yang bisa digunakan bersama karena keduanya menetapkan pilihan secara eksklusif, kandidat harus gugur pada Hard Constraint. Skor 0 di sini bukan cara untuk meloloskan kandidat yang sebenarnya tidak bisa belajar bersama.

9. Menggabungkan semua faktor menjadi satu rumus
   Sekarang kita sudah memiliki lima nilai:

- T = Topic Similarity
- G = Goal Compatibility
- S = Study Style Compatibility
- D = Date Preference
- M = Mode Compatibility
  Kita gabungkan menggunakan metode Weighted Sum, yaitu setiap faktor dikalikan dengan bobotnya masing-masing.

Rumus utama LaFriend:
\[
\boxed{
CS(A,B)=0.30T+0.25G+0.15S+0.15D+0.15M
}
\]

Keterangan:
Faktor Bobot
Topic Similarity 0,30
Goal Compatibility 0,25
Study Style 0,15
Date Preference 0,15
Mode Compatibility 0,15

Hasil akhirnya berada pada rentang 0–100.
Simulasi perhitungan Andi dan Budi
Kita gunakan hasil perhitungan sebelumnya.
Faktor Nilai Bobot Hasil
Materi (T) 50 30% 15
Tujuan (G) 100 25% 25
Gaya belajar (S) 100 15% 15
Preferensi tanggal (D) 100 15% 15
Metode (M) 100 15% 15
Total 100% 85

Perhitungannya:
\[
CS=15+25+15+15+15
\]

\[
\boxed{CS=85}
\]

HASIL SIMULASI KECocokan
85
/ 100

Andi dan Budi memiliki kecocokan yang tinggi dalam simulasi ini.

Hasil ini belum merupakan penilaian empiris atau jaminan keberhasilan sesi belajar.

10. Bagaimana sistem menentukan urutan rekomendasi?
    Misalnya, Andi memiliki tiga kandidat yang lolos Hard Constraint.
    Kandidat Skor
    Budi 85
    Citra 78
    Deni 65

LaFriend mengurutkan kandidat berdasarkan skor tertinggi.
Rekomendasi teman belajar Andi
1
Budi

Materi, tujuan, gaya belajar, dan jadwal sangat sesuai.

85

2
Citra

Materi dan jadwal sesuai, tetapi tujuan belajar sedikit berbeda.

78

3
Deni

Kebutuhan belajar masih relevan, tetapi beberapa preferensi berbeda.

65

Untuk PoC, kita bisa membatasi tampilan maksimal lima rekomendasi.

Namun, ada dua hal yang harus kita tetapkan:

1. Skor digunakan untuk mengurutkan kandidat, bukan untuk otomatis memasangkan mahasiswa.
2. Mahasiswa tetap bisa melihat alasan rekomendasi dan memutuskan sendiri apakah ingin mengirim undangan.
   Apakah perlu ambang batas skor?
   Menurut saya, jangan langsung membuat aturan seperti skor di bawah 70 otomatis ditolak.

Alasannya, bisa saja kandidat memiliki skor 68 tetapi merupakan satu-satunya mahasiswa yang benar-benar memiliki jadwal dan kebutuhan belajar yang sesuai.

Untuk awal, lebih baik:

- Gunakan Hard Constraint untuk menentukan kandidat yang layak.
- Gunakan Compatibility Score untuk mengurutkan kandidat.
- Evaluasi kualitas rekomendasi melalui pengujian dan feedback.
  Jika nanti data pengujian sudah cukup, barulah kita menentukan ambang skor berdasarkan hasil evaluasi.

11. Bagaimana kalau satu kelompok terdiri dari lebih dari dua orang?
    Ini bagian yang jangan sampai terlewat, bro.

Formula sebelumnya menghitung kecocokan dua mahasiswa. Padahal LaFriend ingin mendukung kelompok beranggotakan 2–4 orang.

Misalnya:

- Andi cocok dengan Budi: 85.
- Andi cocok dengan Citra: 90.
- Budi cocok dengan Citra: 55.
  Apakah berarti Andi, Budi, dan Citra otomatis cocok belajar bersama?

Belum tentu.

Karena kecocokan Andi–Budi dan Andi–Citra tidak menjamin Budi–Citra juga cocok.

Untuk itu, ketika membentuk kelompok, kita perlu mengecek kecocokan seluruh pasangan anggota.

Untuk kelompok berisi \(n\) mahasiswa:
\[
GroupScore=
\frac{
\sum\_{i<j}CS(i,j)
}{
\frac{n(n-1)}{2}
}
\]

Contoh kelompok Andi, Budi, dan Citra:
\[
GroupScore=
\frac{85+90+55}{3}
\]

\[
\boxed{GroupScore=76.67}
\]

Nilai tersebut adalah rata-rata kecocokan seluruh pasangan.

Tetapi ingat: ini baru salah satu ukuran. Kelompok juga tetap harus memiliki jadwal bersama dan memenuhi kapasitas. Kita belum boleh menggunakan rata-rata tersebut sebagai satu-satunya penentu kelompok layak.

Untuk sekarang, cukup jadikan ini rancangan awal. Mekanisme pembentukan kelompok akan kita bahas lebih dalam pada tahap berikutnya.

12. Rangkuman hasil Day 4
    Berikut hasil rancangan formula yang sudah kita susun.
    Komponen Hasil rancangan
    Hard Constraint Filter kelayakan sebelum scoring
    Topic Similarity Jaccard Similarity
    Goal Compatibility Tabel kecocokan tujuan
    Study Style Tabel kecocokan gaya belajar
    Date Preference Prioritas waktu yang sama-sama tersedia
    Mode Compatibility Kesesuaian pilihan metode
    Compatibility Score Weighted Sum
    Ranking Urutkan skor tertinggi
    Group Score Rata-rata kecocokan antaranggota

Rumus utama sementara:
\[
CS(A,B)=
0.30T+
0.25G+
0.15S+
0.15D+
0.15M
\]

Rancangan formula awal selesai
Namun, saya ingin menegaskan tiga hal yang belum boleh kita anggap final:

1. Bobot 30%, 25%, dan seterusnya masih perlu diuji.
2. Nilai kecocokan pada tabel tujuan dan gaya belajar masih berupa asumsi desain.
3. Jaccard hanya membandingkan materi yang sudah diseragamkan, belum memahami hubungan semantik antarmateri.
4. Berikutnya: Day 5
   Menurut saya, setelah Day 4 kita jangan langsung masuk ke coding.

Kita harus menyelesaikan satu masalah besar terlebih dahulu: bagaimana LaFriend membentuk kelompok belajar yang benar-benar layak?

Day 5 akan membahas:

1. Bagaimana sistem mencari Study Session yang sudah tersedia.
2. Kapan sistem harus beralih ke Partner Matching.
3. Bagaimana menggabungkan beberapa mahasiswa menjadi satu kelompok.
4. Bagaimana mengecek apakah seluruh anggota memiliki jadwal yang sama.
5. Bagaimana menentukan siapa yang menjadi host.
6. Bagaimana proses undangan, persetujuan, dan konfirmasi kelompok.
   Dengan begitu, LaFriend tidak hanya pintar menghitung kecocokan dua mahasiswa, tetapi juga mampu mengubah hasil pencarian tersebut menjadi sesi belajar yang benar-benar bisa dilaksanakan.
