Gas bro! Kita lanjut ke Day 7: Menentukan Rumus Pembentukan Kelompok (Group Formation Algorithm).

Sampai Day 6, kita sudah punya alur besar LaFriend: mahasiswa membuat kebutuhan belajar, sistem mencari sesi yang cocok, lalu mencari teman belajar jika belum ada sesi yang sesuai.

Nah, sekarang kita perlu menyelesaikan satu masalah penting:

Bagaimana LaFriend menentukan bahwa beberapa mahasiswa cocok belajar bersama sebagai satu kelompok, bukan hanya cocok secara individu dengan pembuat Study Intent?

Ini penting karena dua mahasiswa bisa sama-sama cocok dengan Andi, tetapi belum tentu cocok satu sama lain. Kalau kita hanya mengambil tiga mahasiswa dengan skor tertinggi, kelompok yang terbentuk bisa jadi tidak nyaman atau bahkan tidak punya jadwal yang sama.

Target Day 7 adalah membuat aturan pembentukan kelompok yang masuk akal, bisa dihitung, dan bisa dijelaskan kepada pengguna.

1. Masalah yang harus diselesaikan
   Bayangkan Andi ingin belajar Binary Tree.

Hasil Partner Matching menemukan:
Calon teman Skor dengan Andi
Budi 95
Citra 90
Deni 88

Kalau sistem hanya mengambil tiga skor tertinggi, Andi, Budi, Citra, dan Deni langsung dijadikan satu kelompok.

Padahal, belum tentu:

- Budi cocok belajar dengan Citra.
- Deni cocok belajar dengan Budi.
- Keempatnya punya waktu kosong yang sama.
- Jumlah anggota sesuai keinginan semua mahasiswa.
  Kesimpulannya: skor kecocokan individu tidak cukup untuk menentukan kualitas kelompok.

Karena itu, LaFriend harus memeriksa kecocokan kelompok secara keseluruhan. 2. Aturan dasar pembentukan kelompok
Kita gunakan aturan berikut untuk versi awal LaFriend.
Aturan Ketentuan
Anggota 2–4 mahasiswa, termasuk host
Host Mahasiswa yang membuat Study Intent pertama
Mata kuliah Semua anggota harus memilih mata kuliah yang sama
Topik Semua anggota harus relevan dengan topik belajar kelompok
Jadwal Harus ada minimal satu waktu yang bisa diikuti semua anggota
Gaya belajar Tidak boleh ada konflik yang membuat kerja sama tidak memungkinkan
Kapasitas Tidak boleh melebihi batas anggota
Persetujuan Semua anggota harus menyetujui undangan dan jadwal akhir

Jumlah 2–4 orang dan ketentuan durasi minimal 60 menit masih merupakan asumsi awal untuk PoC, bukan angka yang sudah terbukti paling ideal.

Ada satu aturan tambahan yang penting: ukuran kelompok harus sesuai dengan keinginan setiap anggota.

Contohnya:

- Andi mau kelompok berisi 2–4 orang.
- Budi mau kelompok berisi 3–4 orang.
- Citra mau kelompok berisi 2–3 orang.
  Artinya, kelompok berisi 3 orang bisa diterima semuanya. Namun, kelompok berisi 4 orang tidak bisa diterima Citra.

Jadi, kita perlu mencari ukuran kelompok yang memenuhi rentang pilihan semua anggota. 3. Bagaimana sistem menilai kualitas kelompok?
Pada Day 4, kita sudah punya rumus kecocokan dua mahasiswa:
\[
CS(A,B)=0.30T+0.25G+0.15S+0.15D+0.15M
\]

Rumus ini tetap digunakan. Tidak perlu membuat ulang rumus kecocokan individu.

Yang kita butuhkan sekarang adalah rumus untuk menilai satu kelompok.

Ada dua hal yang harus diperhatikan:

A. Rata-rata kecocokan semua anggota

Misalnya terdapat tiga mahasiswa:

- Andi dengan Budi: 90
- Andi dengan Citra: 85
- Budi dengan Citra: 75
  Rata-ratanya:
  \[
  AverageScore=\frac{90+85+75}{3}=83.33
  \]

Ini menunjukkan bahwa secara keseluruhan anggota kelompok cukup cocok.

B. Kecocokan pasangan terlemah

Kita juga perlu melihat pasangan yang paling tidak cocok.
\[
MinimumPairScore=\min(90,85,75)=75
\]

Kenapa ini penting?

Karena rata-rata kelompok bisa terlihat tinggi, padahal ada satu pasangan yang sebenarnya kurang cocok.
Rumus akhir kualitas kelompok
Saya menyarankan rumus awal berikut:
\[
\boxed{
GQ=0.70(APS)+0.30(MPS)
}
\]

Keterangan:

- GQ: Group Quality Score, nilai kualitas kelompok.
- APS: Average Pair Score, rata-rata skor seluruh pasangan.
- MPS: Minimum Pair Score, skor pasangan terlemah.
  Dengan contoh Andi, Budi, dan Citra:
  \[
  GQ=0.70(83.33)+0.30(75)
  \]

\[
\boxed{GQ=80.83}
\]

Mengapa rata-rata diberi bobot 70% dan pasangan terlemah 30%? Karena kita ingin menilai kecocokan kelompok secara keseluruhan, tetapi tetap memberikan perhatian pada pasangan yang paling kurang cocok.

Catatan: Bobot 70:30 ini adalah hipotesis desain. Nanti perlu diuji menggunakan beberapa skenario dan feedback pengguna. 4. Mengapa sistem harus memeriksa semua pasangan?
Sekarang kita bandingkan dua kemungkinan kelompok.
Kelompok A — Andi, Budi, Citra
90
Andi–Budi
85
Andi–Citra
75
Budi–Citra

Group Quality Score
80.83

Lebih seimbang

Kelompok B — Andi, Budi, Deni
90
Andi–Budi
95
Andi–Deni
60
Budi–Deni

Group Quality Score
75.17

Ada pasangan yang kurang cocok

Perhatikan: Deni justru memiliki skor 95 dengan Andi, lebih tinggi daripada Citra yang hanya 85.

Tetapi ketika Deni masuk ke kelompok, kecocokannya dengan Budi hanya 60.

Maka, sistem sebaiknya memilih Kelompok A.

Inilah alasan utama LaFriend tidak boleh membentuk kelompok hanya berdasarkan skor tertinggi terhadap host. 5. Bagaimana sistem memastikan semua anggota punya jadwal yang sama?
Ini merupakan pemeriksaan wajib sebelum kelompok ditawarkan.

Misalnya:
Mahasiswa Jadwal tersedia
Andi Rabu, 09.00–12.00
Budi Rabu, 10.00–13.00
Citra Rabu, 11.00–14.00

LaFriend mengambil:

- Waktu mulai paling akhir: 11.00.
- Waktu selesai paling awal: 12.00.
  Rumusnya:
  \[
  StartGroup=\max(Start_1,\ldots,Start_n)
  \]

\[
EndGroup=\min(End_1,\ldots,End_n)
\]

\[
Duration=EndGroup-StartGroup
\]

Hasilnya:
\[
Duration=12.00-11.00=60\text{ menit}
\]

Hasil jadwal kelompok
Rabu, 11.00–12.00
Memenuhi syarat awal

Andi

09.00–12.00

Budi

10.00–13.00

Citra

11.00–14.00

Bagian yang sama-sama tersedia adalah pukul 11.00–12.00.

Kalau tidak ada waktu yang sama-sama tersedia, calon mahasiswa tersebut tidak bisa dimasukkan ke kelompok itu.

Hal penting: pemeriksaan dilakukan untuk setiap tanggal dan pilihan jadwal secara terpisah. Jangan mencampur jadwal hari Senin dengan hari Rabu ketika menghitung irisan waktunya. 6. Alur algoritma pembentukan kelompok
Sekarang kita gabungkan semuanya.
Group Formation Algorithm

1. Mulai dari Andi sebagai host

   Sistem menggunakan Study Intent Andi sebagai kebutuhan utama kelompok.

2. Ambil calon mahasiswa

   Sistem mengambil hasil Partner Matching yang sudah diurutkan berdasarkan Compatibility Score.

3. Periksa calon satu per satu

   Periksa mata kuliah, topik, status akun, ukuran kelompok, dan kecocokan dengan setiap anggota yang sudah ada.

4. Periksa jadwal seluruh kelompok

   Pastikan masih ada setidaknya satu waktu yang bisa diikuti semua anggota.

5. Hitung Group Quality Score

   Hitung rata-rata semua skor pasangan dan skor pasangan terlemah.

6. Pilih tambahan anggota terbaik

   Pilih kandidat yang menghasilkan kualitas kelompok paling baik dan tetap memenuhi semua syarat.

7. Periksa ukuran kelompok

   Jika ukuran kelompok sudah memenuhi kebutuhan minimum semua anggota, sistem dapat membuat Group Proposal. Jika belum, cari anggota berikutnya.

8. Kirim Group Proposal

   Tampilkan daftar anggota, topik, jadwal bersama, dan alasan kecocokannya. Tunggu persetujuan mereka.

Ada satu hal yang perlu ditekankan: algoritma ini menggunakan pendekatan bertahap. Artinya, sistem menambahkan satu kandidat, mengecek ulang kualitas kelompok, kemudian baru mempertimbangkan kandidat berikutnya.

Untuk PoC, pendekatan ini lebih sederhana dan lebih mudah diuji daripada mencoba mencari semua kombinasi kelompok sekaligus. 7. Pseudocode algoritma
Berikut gambaran logikanya dalam bentuk kode sederhana. Ini belum kode produksi, tetapi sudah cukup untuk menjadi acuan implementasi.
def calculate*group_quality(members): pair_scores = [] # Bandingkan setiap pasangan anggota for i in range(len(members)): for j in range(i + 1, len(members)): score = calculate_compatibility( members[i], members[j] ) pair_scores.append(score) if not pair_scores: return None average_score = sum(pair_scores) / len(pair_scores) minimum_score = min(pair_scores) group_quality = ( 0.70 * average*score + 0.30 * minimum_score ) return group_qualitydef build_group(host, candidates): group = [host] for candidate in candidates: # Maksimal 4 anggota termasuk host if len(group) >= 4: break

Perhatikan bahwa fungsi compatible_with_all, has_common_schedule, dan fungsi lainnya masih berupa gambaran fungsi yang harus kita implementasikan. Detailnya akan menjadi spesifikasi teknis berikutnya.

8. Bagaimana jika ada kandidat yang menolak?
   Misalnya sistem membuat kelompok:

- Andi sebagai host.
- Budi menerima undangan.
- Citra menolak undangan.
  LaFriend tidak boleh langsung menganggap kelompok berhasil.

Alurnya:

1. Citra dikeluarkan dari calon anggota kelompok.
2. Sistem memeriksa apakah Andi dan Budi sudah memenuhi ukuran minimum.
3. Jika belum, sistem mencari kandidat pengganti.
4. Sistem menghitung ulang kecocokan kelompok.
5. Sistem mengirim proposal baru jika kelompok masih layak.
   Jika tidak ada pengganti, Study Intent Andi tetap aktif agar dapat mencari kelompok lagi.

Persetujuan undangan juga belum berarti sesi sudah dikonfirmasi. Semua anggota tetap harus menyetujui jadwal akhir. 9. Data yang perlu disimpan
Untuk rancangan database Day 2, kita tidak harus langsung menambah banyak tabel.

Kita bisa memanfaatkan tabel yang sudah ada:
Tabel Fungsi
study_intents Menyimpan kebutuhan belajar setiap mahasiswa
match_results Menyimpan hasil pencocokan dan skor
study_sessions Menyimpan rancangan kelompok/sesi belajar
session_members Menyimpan daftar anggota kelompok
session_slots Menyimpan pilihan waktu kelompok
invitations Menyimpan undangan dan respons anggota

Untuk menyimpan riwayat beberapa percobaan pembentukan kelompok, nantinya kita dapat menambahkan tabel group_formation_attempts. Namun, untuk PoC sederhana, kita bisa menggunakan study_sessions berstatus DRAFT sebagai wadah proposal kelompok, lalu menyimpan anggota dan undangannya sebelum sesi dikonfirmasi. 10. Contoh pengujian yang harus berhasil
Sebelum algoritma ini dianggap selesai, kita perlu menguji beberapa kondisi.
No. Skenario Hasil yang diharapkan
1 Semua pasangan cocok dan punya jadwal bersama Kelompok dapat dibuat
2 Host cocok dengan dua kandidat, tetapi kedua kandidat tidak cocok satu sama lain Kelompok ditolak atau kandidat diganti
3 Skor rata-rata tinggi, tetapi ada pasangan dengan skor rendah Skor kelompok ikut mempertimbangkan pasangan terlemah
4 Tidak ada jadwal yang sama Kandidat tidak dimasukkan
5 Jumlah anggota melebihi batas Kandidat tambahan ditolak
6 Rentang ukuran kelompok antaranggota tidak memiliki irisan Kelompok tidak dapat dibentuk
7 Salah satu anggota menolak undangan Sistem mengevaluasi ulang kelompok
8 Semua anggota menerima undangan dan jadwal Sesi dapat dikonfirmasi
9 Tidak ada kandidat yang memenuhi syarat Study Intent tetap aktif
10 Ada kandidat baru dengan skor individu tinggi, tetapi membuat kualitas kelompok menurun Sistem tidak otomatis memilih kandidat tersebut

Ada dua detail implementasi yang harus kita pegang:

Pertama, rentang ukuran kelompok.

Untuk setiap anggota, ambil nilai minimum dan maksimum yang mereka inginkan.
\[
MinGroup=\max(min_i)
\]

\[
MaxGroup=\min(max_i,4)
\]

Kelompok memungkinkan dibentuk jika:
\[
MinGroup \leq MaxGroup
\]

Sistem boleh menghentikan pencarian ketika jumlah anggota sudah mencapai MinGroup, tanpa harus memenuhi MaxGroup.

Kedua, pemilihan kandidat.

Pseudocode sebelumnya menggambarkan pendekatan sederhana berdasarkan urutan skor individu. Untuk implementasi yang lebih sesuai dengan konsep kita, setiap kandidat yang memenuhi syarat sebaiknya diuji terlebih dahulu dengan kelompok sementara.

Kemudian sistem memilih kandidat yang memberikan Group Quality Score terbaik, bukan otomatis mengambil kandidat dengan skor individu tertinggi.

Pendekatan ini tetap bersifat bertahap dan belum menjamin kombinasi kelompok paling optimal dari seluruh kemungkinan. Itu cukup untuk PoC awal dan lebih mudah dijelaskan.

11. Keputusan akhir Day 7
    Hasil rancangan Day 7
    Selesai — rancangan awal

1. Pembentukan kelompok menggunakan kecocokan semua pasangan anggota.
1. Skor kualitas kelompok menggunakan rata-rata pasangan dan skor pasangan terendah.
1. Rumus awal Group Quality Score adalah 70% rata-rata dan 30% skor terendah.
1. Jadwal harus tersedia untuk seluruh anggota secara bersamaan.
1. Ukuran kelompok harus sesuai dengan kebutuhan semua anggota.
1. Host menjadi anggota pertama dan penginisiasi kelompok.
1. Kandidat yang menolak akan dikeluarkan dan kelompok dihitung ulang.
1. Kelompok baru dikonfirmasi setelah seluruh anggota menyetujui undangan dan jadwal.

Apa yang sudah kita miliki setelah Day 7?

- Day 1: Aturan dasar LaFriend.
- Day 2: Struktur database.
- Day 3: Data yang dimasukkan mahasiswa.
- Day 4: Rumus kecocokan dua mahasiswa.
- Day 5: Session Matching dan Partner Matching.
- Day 6: Alur keseluruhan sistem.
- Day 7: Rumus dan proses pembentukan kelompok.
  Berarti sekarang kita sudah memiliki rancangan logika utama LaFriend, mulai dari mahasiswa memasukkan kebutuhan belajar sampai kelompok terbentuk.

Target Day 8 yang saya sarankan: kita membahas bagaimana LaFriend menjelaskan alasan sebuah rekomendasi muncul kepada pengguna. Jadi, bukan cuma menampilkan skor 85%, tetapi juga menjelaskan kenapa mahasiswa tersebut direkomendasikan, apa kelebihannya, dan apakah ada kekurangan yang perlu diketahui.
