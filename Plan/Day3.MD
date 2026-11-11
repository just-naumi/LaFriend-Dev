Siap bro! Kita lanjut ke Day 3: Menentukan Input Study Intent dan Parameter Matching LaFriend.

Kalau Day 1 kita menentukan aturan dasar LaFriend, dan Day 2 kita menentukan data apa saja yang perlu disimpan, maka Day 3 kita akan menentukan informasi apa yang harus diisi mahasiswa ketika ingin mencari teman belajar, serta bagaimana informasi tersebut digunakan oleh sistem untuk mencari kecocokan.

Ini penting karena formula matching yang bagus harus berasal dari input yang jelas. Jangan sampai kita membuat rumus yang terlihat canggih, tetapi ternyata data yang digunakan tidak relevan dengan kebutuhan mahasiswa.

Saya akan susun hasil Day 3 secara langsung, lengkap dengan contoh dan keputusan awal yang bisa kita gunakan sebagai dasar pengembangan.
DAY 3 — Study Intent Input & Matching Parameters

1. Memahami alur input Study Intent
   Bayangkan ada mahasiswa bernama Andi.

Andi ingin belajar mata kuliah Struktur Data, khususnya materi Binary Tree. Dia ingin mencari teman belajar karena kesulitan memahami materi tersebut.

Ketika membuka LaFriend, Andi membuat sebuah permintaan belajar (Study Intent).

Informasi yang dimasukkan Andi akan diproses oleh LaFriend untuk mencari:

1. Study Session yang sudah tersedia dan sesuai dengan kebutuhannya.
2. Mahasiswa lain yang memiliki kebutuhan belajar serupa jika tidak ada sesi yang cocok.
   Jadi, kita perlu menentukan informasi apa saja yang dibutuhkan sistem untuk melakukan pencarian tersebut.
3. Menentukan seluruh input Study Intent
   Menurut saya, kita bisa membagi input menjadi enam kelompok.
   A. Informasi mata kuliah dan materi
   Contoh tampilan input

MATA KULIAH
Struktur Data
MATERI YANG INGIN DIPELAJARI
Binary Tree, Binary Search Tree
Mahasiswa dapat memasukkan satu atau beberapa materi.

Input Keterangan Wajib?
Course Mata kuliah yang ingin dipelajari Ya
Topic Materi spesifik yang ingin dipelajari Ya

Logikanya:

- Course digunakan untuk menentukan apakah mahasiswa mempelajari mata kuliah yang sama.
- Topic digunakan untuk mengetahui apakah kebutuhan belajarnya benar-benar mirip.
  Contohnya, dua mahasiswa sama-sama mengambil Struktur Data, tetapi satu ingin belajar Binary Tree dan satu lagi ingin belajar Sorting. Mereka belum tentu cocok meskipun mata kuliahnya sama.
  B. Tujuan belajar
  Apa tujuan kamu mengikuti sesi belajar ini?
  Memahami materi
  Contoh dipilih

Ingin memahami konsep yang belum dimengerti.
Mengerjakan latihan soal

Ingin berlatih menyelesaikan soal bersama.

Persiapan ujian

Ingin mempersiapkan UTS atau UAS.

Mengerjakan tugas

Ingin menyelesaikan tugas mata kuliah bersama.

Diskusi dan berbagi pengetahuan

Ingin berdiskusi dan saling menjelaskan materi.

Menurut saya, tujuan belajar harus menjadi salah satu parameter matching.

Misalnya:

- Andi ingin memahami konsep Binary Tree.
- Budi ingin mengerjakan latihan soal Binary Tree.
- Citra ingin mempersiapkan ujian Struktur Data.
  Ketiganya memiliki mata kuliah yang sama, tetapi tujuan belajarnya berbeda. Perbedaan tersebut tidak harus membuat mereka otomatis tidak cocok, tetapi perlu diperhitungkan.
  C. Jadwal ketersediaan
  Ini merupakan salah satu input paling penting karena mahasiswa yang cocok secara materi belum tentu memiliki waktu belajar yang sama.

Saya menyarankan mahasiswa mengisi beberapa pilihan waktu, bukan hanya satu tanggal.
Contoh ketersediaan Andi
Rentang tanggal
Contoh

Mulai

12 November 2026

Batas akhir

18 November 2026

Pilihan waktu yang tersedia
Hari Waktu
Senin 13.00–16.00
Rabu 09.00–12.00
Jumat 13.00–17.00

Ada dua jenis informasi waktu yang perlu kita bedakan:

- Rentang tanggal: kapan mahasiswa bersedia melakukan sesi belajar.
- Ketersediaan waktu: jam berapa mahasiswa bisa belajar pada tanggal tersebut.
  Kenapa harus dua-duanya?

Karena Andi dan Budi mungkin sama-sama bisa belajar pada minggu ini, tetapi hanya memiliki waktu kosong yang bersamaan pada hari Rabu pukul 10.00.

Sistem harus mencari irisan waktu yang benar-benar bisa digunakan bersama.
D. Gaya belajar bersama
Menurut saya, ini bisa membantu LaFriend membedakan dirinya dari sistem pencarian teman biasa.

Kita bisa menyediakan pilihan berikut:
Gaya belajar Penjelasan
Discussion Berdiskusi dan bertukar pendapat
Practice Mengerjakan latihan bersama
Teaching Saling mengajarkan materi
Focus Study Belajar fokus dengan sedikit diskusi

Contoh:

- Andi lebih suka berdiskusi.
- Budi lebih suka mengerjakan latihan.
- Citra lebih suka saling mengajarkan materi.
  Perbedaan gaya belajar tidak harus menjadi alasan untuk menggugurkan kecocokan. Namun, preferensi yang sama bisa menjadi nilai tambah.
  E. Metode belajar
  Mahasiswa dapat memilih:
- Offline: bertemu langsung.
- Online: belajar melalui platform daring.
- Hybrid: fleksibel antara online dan offline.
  Perlu diperhatikan: jika mahasiswa memilih hanya offline, sistem harus mencari orang yang juga bersedia offline. Jika mahasiswa bersedia online maupun offline, pilihannya lebih fleksibel.
  F. Ukuran kelompok belajar
  Kita perlu mengetahui berapa banyak anggota yang diinginkan mahasiswa.

Untuk PoC awal, saya menyarankan:

- Minimal anggota: 2 orang.
- Maksimal anggota: 4 orang.
- Jumlah anggota termasuk host.
  Contohnya, Andi ingin belajar bersama 2–4 orang. Artinya, Andi bersedia membentuk kelompok dengan total 2, 3, atau 4 mahasiswa termasuk dirinya.

Ini adalah asumsi awal untuk pengujian, bukan batasan permanen LaFriend.

3. Memisahkan input wajib dan input pendukung
   Nah, bro, ini bagian yang sangat penting untuk algoritma LaFriend.

Tidak semua informasi yang diisi mahasiswa harus diperlakukan dengan cara yang sama. Ada informasi yang menentukan apakah dua mahasiswa bisa belajar bersama, dan ada informasi yang hanya membantu menentukan apakah mereka cocok.

Kita bagi menjadi dua kelompok.
A. Hard Constraint — Syarat wajib
Hard Constraint adalah syarat yang harus terpenuhi. Kalau tidak terpenuhi, kandidat tidak akan direkomendasikan meskipun nilai kecocokannya tinggi.

Saya menyarankan aturan awal berikut:
Parameter Aturan
Mata kuliah Harus sama
Status akun Harus terverifikasi dan aktif
Jadwal Harus memiliki waktu yang bisa digunakan bersama
Rentang tanggal Harus memiliki tanggal yang beririsan
Kapasitas sesi Tidak boleh melebihi jumlah anggota maksimum
Metode belajar Harus cocok jika ada pilihan yang bersifat eksklusif

Contoh:

Andi ingin belajar Struktur Data pada 12–18 November. Budi ingin belajar Struktur Data pada 20–25 November.

Walaupun materi dan tujuan belajar mereka sama, sistem tidak akan merekomendasikan mereka karena rentang tanggalnya tidak bertemu.

Kenapa ini penting?

Karena LaFriend tidak boleh merekomendasikan orang yang terlihat cocok di atas kertas, tetapi sebenarnya tidak bisa belajar bersama.
B. Soft Preference — Faktor penambah kecocokan
Soft Preference adalah preferensi yang boleh berbeda. Perbedaan ini tidak langsung menggugurkan kandidat, tetapi akan memengaruhi nilai kecocokan.
Parameter Contoh
Kesamaan materi Sama-sama belajar Binary Tree
Tujuan belajar Sama-sama ingin memahami konsep
Gaya belajar Sama-sama suka berdiskusi
Preferensi tanggal Sama-sama lebih suka hari Rabu
Metode belajar Sama-sama lebih nyaman offline

Contoh:

Andi dan Budi memiliki jadwal yang cocok dan mengambil mata kuliah yang sama. Andi ingin memahami Binary Tree, sedangkan Budi ingin berlatih soal Binary Tree.

Mereka tetap bisa direkomendasikan. Bahkan, mereka berpotensi saling membantu.

Jadi, perbedaan tujuan belajar tidak otomatis berarti tidak cocok. 4. Menentukan parameter yang akan digunakan algoritma
Sekarang kita rangkum input tadi menjadi parameter yang bisa dibaca oleh sistem.
Parameter utama LaFriend
Hard Constraint
H — Feasibility

Apakah kandidat benar-benar bisa mengikuti sesi belajar bersama?

Pengecekan mata kuliah, tanggal, waktu, akun, kapasitas, dan metode belajar.

Soft Preference
T — Topic Similarity

Seberapa mirip materi yang ingin dipelajari?

Soft Preference
G — Goal Compatibility

Seberapa sesuai tujuan belajar kedua mahasiswa?

Soft Preference
S — Study Style Compatibility

Seberapa sesuai gaya belajar mereka?

Soft Preference
D — Date Preference

Seberapa sesuai tanggal pilihan mereka?

Soft Preference
M — Mode Compatibility

Seberapa sesuai preferensi online, offline, atau hybrid mereka?

Ada satu hal yang perlu kita perhatikan: jadwal yang memungkinkan dan preferensi tanggal adalah dua hal berbeda.

Misalnya:

- Andi bisa belajar Senin, Rabu, dan Jumat.
- Budi bisa belajar Rabu dan Jumat.
- Keduanya paling menyukai hari Jumat.
  Mereka sebenarnya bisa belajar pada Rabu maupun Jumat. Namun, Jumat menjadi pilihan yang lebih disukai.

Jadi:

- Jadwal yang beririsan = syarat kelayakan.
- Hari yang paling disukai = nilai tambahan kecocokan.
  Ini akan mencegah algoritma kita menghitung hal yang sama dua kali.

5. Menentukan bentuk data yang disimpan
   Berdasarkan sepuluh tabel yang sudah kita rancang pada Day 2, kita perlu memperjelas data apa saja yang harus masuk ke tabel study_intents.

Berikut rancangan input final sementara:
Nama field Tipe data Contoh
intent_id UUID ID permintaan
student_id UUID ID mahasiswa
course_id UUID ID mata kuliah
topics Text / JSON Binary Tree, BST
learning_goal Enum UNDERSTAND
collaboration_style Enum DISCUSSION
learning_mode Enum OFFLINE
earliest_date Date 2026-11-12
latest_date Date 2026-11-18
min_group_size Integer 2
max_group_size Integer 4
status Enum ACTIVE
created_at Timestamp Waktu dibuat

Sementara itu, pilihan jam dan tanggal yang tersedia tetap disimpan di tabel terpisah, yaitu intent_availabilities.

Kenapa dipisah?

Karena satu mahasiswa bisa memiliki banyak pilihan jadwal. Kalau semuanya dimasukkan ke satu kolom, sistem akan lebih sulit mencari irisan jadwal.

Untuk nilai seperti learning_goal, collaboration_style, dan learning_mode, sebaiknya kita menggunakan pilihan yang sudah ditentukan sistem, bukan teks bebas sepenuhnya. Dengan begitu, data lebih konsisten dan lebih mudah dibandingkan.

Untuk topics, mahasiswa boleh mengetik beberapa materi. Sistem dapat menyimpan materi tersebut sebagai daftar, lalu melakukan normalisasi nama materi sebelum membandingkannya.

6. Contoh bagaimana input diproses oleh LaFriend
   Sekarang kita coba simulasi sederhana supaya alurnya benar-benar jelas.

Andi membuat Study Intent seperti ini:
Study Intent — Andi
Informasi Pilihan
Mata kuliah Struktur Data
Materi Binary Tree
Tujuan Memahami materi
Gaya belajar Discussion
Metode Offline
Rentang tanggal 12–18 November
Jadwal tersedia Rabu 09.00–12.00
Ukuran kelompok 2–4 orang

Kemudian LaFriend menemukan tiga kandidat:
Kandidat Kondisi Keputusan
Budi Mata kuliah sama, materi sama, jadwal cocok Lolos
Citra Mata kuliah sama, materi berbeda, jadwal cocok Lolos
Deni Mata kuliah sama, materi sama, jadwal tidak cocok Gugur

Perhatikan bahwa Budi dan Citra tetap lolos meskipun tingkat kesamaan materinya berbeda.

Setelah itu, sistem baru menghitung nilai kecocokan Budi dan Citra berdasarkan faktor-faktor yang sudah kita tentukan.

Secara sederhana, alurnya seperti ini:
Andi membuat Study Intent

Mata kuliah, materi, tujuan, jadwal, dan preferensi

Pengecekan Hard Constraint

Buang kandidat yang tidak memenuhi syarat wajib

Perhitungan Soft Preference

Hitung kesamaan materi, tujuan, gaya, tanggal, dan metode

Urutkan kandidat

Tampilkan kandidat yang paling sesuai

Andi memilih kandidat

Tidak ada penempatan otomatis

7. Keputusan akhir Day 3
   Saya ingin kita mengunci beberapa keputusan awal agar pada hari berikutnya kita tidak terus mengubah konsep dasarnya.
   No. Keputusan Status
   1 Study Intent menjadi sumber utama kebutuhan belajar Tetapkan
   2 Mata kuliah harus sama Tetapkan
   3 Jadwal harus memiliki irisan waktu Tetapkan
   4 Materi menjadi faktor kecocokan Tetapkan
   5 Tujuan belajar menjadi faktor kecocokan Tetapkan
   6 Gaya belajar menjadi faktor kecocokan Tetapkan
   7 Metode belajar menjadi syarat jika eksklusif Tetapkan
   8 Kelompok beranggotakan 2–4 orang Asumsi PoC
   9 Maksimal 5 rekomendasi yang ditampilkan Asumsi PoC
   10 Bobot setiap parameter Belum ditentukan

Kenapa bobot belum ditentukan?

Karena kita belum membuktikan apakah kesamaan materi lebih penting daripada kesamaan tujuan belajar, atau seberapa besar pengaruh gaya belajar terhadap keberhasilan sesi.

Saya tidak ingin asal memberikan angka seperti 30%, 25%, dan 15% hanya supaya rumusnya terlihat lengkap. Bobot tersebut perlu memiliki alasan yang jelas dan nantinya bisa diuji. 8. Apa yang akan kita kerjakan pada Day 4?
Day 3 sudah menghasilkan daftar input dan parameter yang akan digunakan sistem.

Berikutnya kita masuk ke bagian inti algoritma LaFriend:

Day 4 — Merancang Formula Compatibility Score.

Kita akan mengerjakan secara rinci:

1. Bagaimana menghitung kesamaan materi antara dua mahasiswa.
2. Bagaimana menghitung kecocokan tujuan belajar.
3. Bagaimana menghitung kecocokan gaya belajar.
4. Bagaimana menghitung kecocokan preferensi tanggal dan metode belajar.
5. Bagaimana menggabungkan seluruh nilai menjadi satu skor, misalnya 0–100.
6. Bagaimana menentukan bobot setiap parameter dengan alasan yang masuk akal.
7. Bagaimana memberikan penjelasan mengapa seseorang direkomendasikan.
   Target akhirnya bukan sekadar punya satu rumus, tetapi punya formula yang bisa dijelaskan, dihitung, diuji, dan benar-benar membantu mahasiswa menemukan teman belajar yang sesuai.

Menurut saya, fondasi Day 3 ini sudah cukup untuk mulai merancang algoritma pada Day 4.
