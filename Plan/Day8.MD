lanjut bro ke day 8
Gas bro! Kita lanjut ke Day 8: Explainable Matching — Bagaimana LaFriend Menjelaskan Alasan Rekomendasi?

Sampai Day 7, kita sudah membangun logika untuk menentukan siapa yang cocok belajar bersama. Kita sudah punya:

Compatibility Score untuk membandingkan dua mahasiswa.

Session Score untuk mencari sesi belajar yang cocok.

Group Quality Score untuk menilai kecocokan satu kelompok.

Namun, ada satu masalah yang belum kita selesaikan.

Bayangkan Andi membuka LaFriend dan melihat rekomendasi:

Rekomendasi teman belajar

Direkomendasikan
Budi

Teknik Komputer · Tahun pertama

90/100
Cocok dengan kebutuhan belajarmu!
Pertanyaannya: Kenapa Budi mendapatkan skor 90?

Apakah karena topiknya sama? Jadwalnya cocok? Gaya belajarnya sesuai? Atau karena faktor lainnya?

Kalau LaFriend hanya menampilkan angka, mahasiswa tidak benar-benar tahu alasan sistem merekomendasikan seseorang.

Karena itu, Day 8 akan merancang sistem yang bisa menjelaskan hasil pencocokan menggunakan data yang memang menjadi dasar perhitungan.

1. Prinsip utama Explainable Matching
   Menurut saya, LaFriend harus bisa menjawab tiga pertanyaan pengguna:

Kenapa orang atau sesi ini direkomendasikan?

Bagian mana yang paling cocok dengan kebutuhan saya?

Apakah ada hal yang perlu saya pertimbangkan sebelum bergabung?

Contohnya, Budi direkomendasikan kepada Andi karena:

Sama-sama mengambil mata kuliah Struktur Data.

Memiliki topik belajar Binary Tree.

Memiliki tujuan belajar yang sama.

Memiliki jadwal kosong pada hari Rabu.

Memilih gaya belajar diskusi.

Informasi tersebut harus berasal dari hasil pencocokan yang benar-benar dilakukan sistem, bukan kalimat AI yang dibuat tanpa dasar.

Keputusan desain: versi awal LaFriend menggunakan penjelasan berbasis aturan (rule-based explanation), bukan AI generatif. Dengan begitu, alasan rekomendasi lebih mudah diperiksa dan tidak mengarang informasi.

2. Dari mana alasan rekomendasi berasal?
   Kita gunakan kembali lima faktor Compatibility Score dari Day 4.

Faktor

Bobot

Hal yang dijelaskan

Topic Similarity

30%

Kesamaan topik belajar

Goal Compatibility

25%

Kesesuaian tujuan belajar

Study Style

15%

Kesesuaian gaya belajar

Date Preference

15%

Kesesuaian pilihan jadwal

Mode Compatibility

15%

Kesesuaian metode belajar

Misalnya hasil pencocokan Andi dan Budi seperti berikut:

Faktor

Nilai

Kontribusi

Topic Similarity

100

30

Goal Compatibility

100

25

Study Style

100

15

Date Preference

80

12

Mode Compatibility

100

15

Total

97

Rumusnya:

C
S
=
30

- 25
- 15
- 12
- # 15
  97
  CS=30+25+15+12+15=97
  Jadi, skor Budi adalah 97, bukan 90.

Dari hasil tersebut, kita sudah tahu faktor mana yang berkontribusi paling besar dan mana yang masih kurang.

3. Membuat aturan penjelasan untuk setiap faktor
   Sekarang kita tentukan bagaimana nilai angka diterjemahkan menjadi kalimat yang mudah dipahami.

A. Topic Similarity
Contoh:

Andi: Binary Tree.

Budi: Binary Tree, Binary Search Tree.

Sistem membandingkan topik keduanya.

Jika terdapat topik yang sama, sistem bisa menjelaskan:

Nilai tinggi: "Kalian memiliki topik belajar yang sama, yaitu Binary Tree."

Nilai sedang: "Ada beberapa topik yang berkaitan dengan kebutuhan belajar kalian."

Nilai rendah: "Topik belajar kalian hanya memiliki sedikit kesamaan."

Jangan menulis bahwa topiknya sama jika hasil normalisasi sebenarnya hanya menemukan topik yang berkaitan.

B. Goal Compatibility
Contoh:

Andi ingin memahami konsep Binary Tree.

Budi ingin memahami konsep Binary Tree.

Penjelasan:

"Tujuan belajar kalian sama-sama berfokus pada pemahaman konsep."

Kalau Andi ingin memahami konsep sedangkan Budi ingin latihan soal, penjelasannya bisa:

"Tujuan belajar kalian berbeda, tetapi dapat saling melengkapi melalui pembahasan konsep dan latihan soal."

C. Study Style Compatibility
Contoh:

Andi: DISCUSSION.

Budi: DISCUSSION.

Penjelasan:

"Kalian sama-sama memilih metode belajar melalui diskusi."

Jika satu mahasiswa memilih TEACHING dan lainnya PRACTICE:

"Gaya belajar kalian berpotensi saling melengkapi melalui penjelasan materi dan latihan."

D. Date Preference
Contoh:

Andi memilih Rabu sebagai pilihan pertama.

Budi memilih Rabu sebagai pilihan kedua.

Penjelasan:

"Kalian memiliki waktu kosong yang sama pada hari Rabu."

Namun, jangan menyebut jadwal sebagai waktu yang sudah disepakati. Pada tahap rekomendasi, itu baru waktu yang tersedia bersama.

E. Mode Compatibility
Contoh:

Andi: OFFLINE.

Budi: OFFLINE.

Penjelasan:

"Kalian sama-sama memilih belajar secara langsung (offline)."

Jika Andi memilih offline sebagai prioritas pertama, sedangkan Budi memilih online sebagai prioritas pertama tetapi masih bersedia offline:

"Kalian memiliki pilihan metode belajar yang sama, meskipun prioritasnya berbeda."

4. Bagaimana cara menentukan alasan utama rekomendasi?
   Tidak semua faktor harus ditampilkan dengan panjang yang sama.

Misalnya:

Topic Similarity = 100.

Goal Compatibility = 100.

Study Style = 100.

Date Preference = 80.

Mode Compatibility = 100.

Maka sistem bisa memilih alasan terkuat dari faktor-faktor tersebut.

Saya menyarankan aturan berikut sebagai rancangan awal:

Nilai faktor

Kategori penjelasan

80–100

Sangat sesuai

60–79

Cukup sesuai

40–59

Sebagian sesuai

Di bawah 40

Kurang sesuai

Batas tersebut hanya untuk mengubah angka menjadi bahasa yang mudah dimengerti. Bukan batas untuk menentukan apakah seseorang boleh direkomendasikan atau tidak.

Contohnya:

Mengapa Budi direkomendasikan?

Skor kecocokan

97/100
Topik belajar

100 — Sangat sesuai
Kalian mempelajari topik yang sama, yaitu Binary Tree.

Tujuan belajar

100 — Sangat sesuai
Kalian sama-sama ingin memahami konsep materi.

Gaya belajar

100 — Sangat sesuai
Kalian sama-sama menyukai metode diskusi.

Jadwal

80 — Sangat sesuai
Kalian memiliki waktu kosong yang sama pada hari Rabu, tetapi prioritas waktunya berbeda.

Metode belajar

100 — Sangat sesuai
Kalian sama-sama memilih belajar secara offline.

Dengan cara ini, pengguna tidak perlu memahami rumus matematika untuk mengerti hasil rekomendasi.

5. Jangan hanya menjelaskan kelebihan, jelaskan juga kekurangannya
   Menurut saya, ini salah satu bagian penting yang bisa menjadi pembeda LaFriend.

Sistem tidak boleh hanya menampilkan hal-hal positif. Kalau ada faktor yang kurang cocok, pengguna juga perlu mengetahuinya.

Misalnya:

Contoh rekomendasi dengan kecocokan sebagian

Citra

78/100
Masih layak dipertimbangkan
Hal yang cocok

Memiliki topik belajar yang berkaitan.

Memiliki waktu kosong yang sama pada hari Kamis.

Sama-sama memilih belajar offline.

Hal yang perlu dipertimbangkan

- Citra lebih berfokus pada latihan soal, sedangkan kamu ingin memahami konsep.

Artinya, LaFriend tidak perlu menyembunyikan perbedaan.

Perbedaan tujuan belajar tidak selalu berarti tidak cocok. Bisa saja kedua mahasiswa justru saling membantu.

Tetapi, sistem harus bisa membedakan:

Perbedaan yang masih bisa saling melengkapi.

Perbedaan yang benar-benar bertentangan.

Aturan ini harus berasal dari tabel kompatibilitas Day 4, bukan dibuat secara bebas saat menampilkan rekomendasi.

6. Explainable Matching untuk Session Matching
   Jangan lupa, LaFriend punya dua jenis rekomendasi:

Rekomendasi sesi belajar yang sudah tersedia.

Rekomendasi teman belajar untuk membentuk kelompok baru.

Keduanya harus memiliki penjelasan yang berbeda.

Contohnya, Andi menemukan sesi belajar yang dibuat oleh mahasiswa lain.

Sesi belajar Binary Tree

Sesuai dengan kebutuhanmu
Struktur Data · Offline · 2 dari 4 anggota

92/100
Mengapa sesi ini direkomendasikan?

Topik sesi membahas Binary Tree.

Tujuan sesi adalah memahami konsep.

Gaya belajar yang digunakan adalah diskusi.

Ada waktu bersama pada hari Rabu.

Metode belajar sesuai dengan pilihanmu.

Skor ini adalah Session Score, yaitu kecocokan Study Intent dengan Study Session, bukan kecocokan dua mahasiswa.

Perhatikan bahwa sistem juga bisa menjelaskan kapasitas sesi:

Kapasitas maksimum: 4 mahasiswa.

Anggota saat ini: 2 mahasiswa.

Sisa tempat: 2 mahasiswa.

Informasi kapasitas bukan bagian dari skor kecocokan. Itu merupakan informasi ketersediaan sesi.

Keputusan desain: penjelasan kecocokan dan informasi operasional harus dipisahkan agar pengguna tidak mengira kapasitas memengaruhi nilai kompatibilitas.

7. Explainable Matching untuk Group Formation
   Day 7 sudah menghasilkan Group Quality Score.

Sekarang kita perlu menjelaskan mengapa satu kelompok dipilih.

Contohnya:

Usulan kelompok belajar

Group Quality Score

80.83/100
Anggota kelompok

Andi Host

Budi

Citra

Mengapa kelompok ini dipilih?

Semua anggota memiliki kebutuhan belajar pada mata kuliah Struktur Data.

Topik belajar anggota saling berkaitan.

Rata-rata kecocokan antaranggota adalah 83.33.

Pasangan dengan kecocokan terendah memperoleh skor 75.

Semua anggota memiliki jadwal bersama pada hari Rabu.

Jadwal yang tersedia bersama

Rabu, 11.00–12.00

Memenuhi durasi minimum awal
Ini masih berupa usulan kelompok. Belum menjadi sesi yang dikonfirmasi.
Ada satu hal yang harus kita jaga: Group Quality Score tidak boleh dianggap sebagai jaminan bahwa kelompok akan berhasil. Angka itu hanya menunjukkan hasil perhitungan berdasarkan informasi yang tersedia.

8. Bagaimana sistem menghasilkan penjelasan secara otomatis?
   Sekarang kita masuk ke logika internalnya.

Sistem sebenarnya tidak perlu menggunakan AI untuk membuat semua kalimat tersebut.

Kita cukup menyiapkan aturan sederhana.

Contohnya:

Kondisi

Kalimat yang dihasilkan

Topic Score ≥ 80

Topik belajar kalian sangat berkaitan.

Topic Score 60–79

Kalian memiliki beberapa topik belajar yang sama.

Topic Score 40–59

Ada sedikit kesamaan pada topik belajar kalian.

Goal Score = 100

Tujuan belajar kalian sama.

Goal Score 80–99

Tujuan belajar kalian saling melengkapi.

Style Score = 100

Kalian memiliki gaya belajar yang sama.

Date Score ≥ 80

Pilihan waktu kalian cukup sesuai.

Mode Score = 100

Kalian memiliki pilihan metode belajar yang sama.

Angka dan kategori tersebut masih perlu disesuaikan dengan tabel kompatibilitas yang kita tetapkan pada Day 4.

Alurnya seperti ini:

Hasil perhitungan matching

97/100
Topic, Goal, Style, Date, Mode
Periksa nilai setiap faktor

Cocokkan nilai dengan aturan penjelasan
Pilih alasan utama dan hal yang perlu dipertimbangkan

Ambil alasan dari data yang benar-benar tersedia
Tampilkan penjelasan kepada mahasiswa

Bahasa sederhana, transparan, dan mudah dipahami
Dengan mekanisme ini, ketika rumus berubah, penjelasan akan mengikuti hasil perhitungan terbaru. Kita tidak perlu menulis penjelasan secara manual untuk setiap rekomendasi.

9. Data apa yang perlu disimpan di database?
   Pada Day 2, kita sudah memiliki tabel match_results dengan beberapa kolom:

match_id

intent_id

candidate_type

candidate_session_id

candidate_student_id

compatibility_score

score_details

explanation

created_at

Struktur ini sebenarnya sudah cukup untuk mendukung Explainable Matching.

Namun, kita perlu menentukan isi score_details dan explanation.

A. score_details

Berisi rincian perhitungan setiap faktor.

Contoh data:

{
"topic_similarity": 100,
"goal_compatibility": 100,
"study_style": 100,
"date_preference": 80,
"mode_compatibility": 100,
"weights": {
"topic": 0.30,
"goal": 0.25,
"style": 0.15,
"date": 0.15,
"mode": 0.15
}
}

B. explanation

Berisi alasan yang akan ditampilkan kepada pengguna.

Contoh:

{
"positive_reasons": [
"Topik belajar kalian sama-sama Binary Tree.",
"Tujuan belajar kalian sama.",
"Kalian sama-sama memilih metode diskusi.",
"Kalian memiliki jadwal kosong pada hari Rabu."
],
"considerations": [
"Prioritas pilihan waktu kalian berbeda."
]
}

Dengan begitu, kita bisa memisahkan data perhitungan dan kalimat penjelasan.

Untuk Group Formation, kita juga perlu menyimpan:

Average Pair Score.

Minimum Pair Score.

Group Quality Score.

Daftar anggota.

Jadwal bersama yang ditemukan.

Alasan kelompok dipilih.

Semua itu dapat disimpan pada data proposal/sesi kelompok. Tidak perlu langsung membuat tabel baru khusus penjelasan.

10. Bagaimana jika data tidak lengkap?
    Ini penting agar sistem tidak memberikan informasi yang salah.

Contohnya:

Mahasiswa belum mengisi gaya belajar.

Mahasiswa belum mengisi prioritas jadwal.

Sistem belum memiliki data topik yang cukup untuk dibandingkan.

LaFriend tidak boleh mengarang alasan.

Aturan yang saya sarankan:

Kondisi

Tindakan

Data wajib tidak lengkap

Minta mahasiswa melengkapi data

Data opsional tidak tersedia

Tampilkan bahwa faktor tersebut belum diketahui

Topik tidak dapat dibandingkan

Jangan mengklaim topik sama

Jadwal belum dikonfirmasi

Sebut sebagai jadwal yang tersedia, bukan jadwal yang disepakati

Skor berubah setelah data diperbarui

Hitung ulang dan perbarui penjelasan

Satu keputusan penting: jangan mengubah bobot faktor secara diam-diam hanya karena data opsional kosong.

Untuk PoC, lebih aman jika kita menentukan data apa saja yang wajib diisi sebelum matching. Faktor yang memang tidak tersedia harus ditandai sebagai tidak diketahui, bukan diberi nilai 100 atau 0 secara sembarangan.

11. Pengujian Day 8
    Berikut skenario yang perlu kita uji sebelum fitur penjelasan dianggap benar.

No.

Skenario

Hasil yang diharapkan

1

Semua faktor bernilai tinggi

Alasan utama menunjukkan kecocokan yang kuat

2

Topik sangat cocok, tetapi jadwal kurang sesuai

Kedua kondisi dijelaskan

3

Tujuan belajar berbeda tetapi saling melengkapi

Penjelasan menyebutkan sifat saling melengkapi

4

Tidak ada kesamaan topik

Sistem tidak mengklaim topiknya sama

5

Data gaya belajar kosong

Sistem tidak membuat alasan tentang gaya belajar

6

Dua sesi memiliki skor sama

Penjelasan masing-masing tetap sesuai datanya

7

Group Quality Score tinggi, tetapi ada pasangan yang kurang cocok

Pasangan terlemah tetap ditampilkan

8

Jadwal baru sebatas pilihan tersedia

Sistem tidak menyebut jadwal sudah disepakati

9

Pengguna mengubah Study Intent

Hasil dan penjelasan dihitung ulang

10

Host belum menerima seluruh persetujuan

Sistem menyebut kelompok masih berupa usulan

12. Keputusan akhir Day 8
    Hasil rancangan Day 8

Selesai — rancangan awal
LaFriend menggunakan Explainable Matching berbasis aturan.

Setiap rekomendasi harus memiliki alasan yang berasal dari hasil perhitungan.

Penjelasan mencakup kecocokan dan hal yang perlu dipertimbangkan.

Session Matching dan Partner Matching memiliki penjelasan berbeda.

Group Formation menjelaskan rata-rata kecocokan dan pasangan terlemah.

Skor dan penjelasan disimpan secara terpisah.

Data yang tidak tersedia tidak boleh menghasilkan klaim yang dibuat-buat.

Skor kecocokan bukan jaminan keberhasilan belajar bersama.

13. Posisi LaFriend setelah Day 8
    Sekarang kita sudah memiliki delapan bagian rancangan sistem:

Hari

Fokus

Hasil

Day 1

Aturan dasar sistem

Business Rules

Day 2

Struktur data

Database & ERD

Day 3

Input pengguna

Study Intent

Day 4

Rumus pencocokan

Compatibility Score

Day 5

Pencarian kandidat

Session & Partner Matching

Day 6

Alur keseluruhan

Integrated Matching Flow

Day 7

Pembentukan kelompok

Group Quality Score

Day 8

Penjelasan rekomendasi

Explainable Matching

Target Day 9 yang saya rekomendasikan: Feedback System & Matching Evaluation.

Kenapa ini penting?

Karena setelah LaFriend memberikan rekomendasi dan membentuk kelompok, kita perlu mengetahui apakah rekomendasi tersebut benar-benar membantu mahasiswa.

Misalnya:

Apakah mahasiswa menerima rekomendasi?

Apakah mereka berhasil membentuk kelompok?

Apakah sesi belajar benar-benar terlaksana?

Apakah anggota merasa cocok setelah belajar bersama?

Apakah hasil feedback bisa digunakan untuk mengevaluasi rumus matching?

Dengan Day 9, kita mulai menghubungkan hasil rekomendasi dengan keberhasilan nyata kegiatan belajar. Ini juga akan menjadi dasar untuk membuktikan bahwa LaFriend bukan sekadar aplikasi pencari teman, tetapi sistem pencocokan yang dapat dievaluasi berdasarkan hasilnya.
