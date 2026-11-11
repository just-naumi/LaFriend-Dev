I. DEFINISI PRODUK DAN LOGIKA UTAMA

1. Apa sebenarnya LaFriend?
   LaFriend adalah platform yang mengubah kebutuhan akademik mahasiswa menjadi peluang kolaborasi belajar yang dapat diwujudkan melalui pencocokan sesi, partner, dan pembentukan kelompok secara terstruktur.

Perhatikan perbedaannya.

Platform pencarian teman biasa:
Saya mencari teman belajar
↓
Menampilkan daftar mahasiswa
↓
Saya menghubungi mereka
↓
Saya mengatur kelompok sendiri

LaFriend:
Saya memiliki kebutuhan belajar
↓
Saya membuat Study Intent
↓
Sistem memahami kebutuhan tersebut
↓
Sistem mengevaluasi peluang kolaborasi
↓
┌──────────────────────────────┐
│ Existing Study Session │
│ Compatible Study Partners │
│ Optimized Study Groups │
└──────────────────────────────┘
↓
Rekomendasi + Alasan Kecocokan
↓
Join / Invite / Reschedule
↓
Confirmation
↓
Confirmed Study Session
↓
Study Completion

Ada tiga objek penting dalam sistem ini.
Objek Pertanyaan yang dijawab
Study Intent Apa yang ingin dipelajari mahasiswa?
Study Match Dengan siapa atau sesi apa kebutuhan tersebut cocok?
Study Session Aktivitas belajar apa yang akhirnya terbentuk?

Tujuan akhir LaFriend bukan menghasilkan banyak match, melainkan menghasilkan study session yang relevan dan benar-benar terlaksana. 2. Arsitektur fitur keseluruhan
Saya akan membangun LaFriend menggunakan sembilan modul utama.

1. STUDENT MANAGEMENT

Registration · Verification · Profile · Preferences

2. STUDY INTENT MANAGEMENT

Manual Input · AI Intent Parser · Availability · Lifecycle

3. MATCHING ENGINE
   Session Matcher

Existing sessions

Partner Matcher

Compatible students

Compatibility Scorer

Eligibility + ranking

Group Optimizer

Best combinations

4. RECOMMENDATION MANAGEMENT

Ranked Sessions · Partners · Suggested Groups · Why This Match

5. GROUP & SESSION MANAGEMENT

Invitation · Join Request · Confirmation · Membership · Capacity

6. SCHEDULE OPTIMIZATION

Common Availability · Alternative Slots · Rescheduling

7. STUDY EXECUTION

Scheduled · Ongoing · Completed · Feedback

8. ANALYTICS & CONTINUOUS IMPROVEMENT

Time-to-Match · Conversion · Completion · Relevance

9. BACKGROUND SERVICES

Persistent Matching · Notifications · Expiration · Event Processing

Modul 9 bekerja mendukung seluruh modul lain. Jadi, notifikasi dan pemrosesan ulang matching tidak harus menunggu pengguna membuka halaman aplikasi.

II. STEP 1 — STUDENT REGISTRATION AND PROFILE
Ini merupakan fondasi seluruh sistem.

LaFriend harus mengetahui siapa penggunanya sebelum mempertemukan mahasiswa dengan pengguna lain.
1.1. User registration
Alur:
Open LaFriend
↓
Register
↓
Email Verification
↓
Campus Verification
↓
Create Student Profile
↓
Complete Preferences
↓
Enter Dashboard

Untuk PoC Telkom University, identitas mahasiswa dapat diverifikasi menggunakan email kampus atau mekanisme verifikasi kampus yang disediakan.

Jangan menganggap sekadar memasukkan email sebagai bukti identitas jika email tersebut belum diverifikasi.
1.2. Student Profile
Saya menyarankan data profil dibagi menjadi tiga bagian.

A. Academic identity
Field Contoh
Student ID 12000001
Full Name Nadia
University Telkom University
Program S1 Teknik Komputer
Cohort 2025

B. Persistent preferences

Informasi yang relatif tetap.
Field Contoh
Preferred study mode Offline
Preferred collaboration Problem Solving
Preferred group size 3–5
Preferred language Indonesian
Preferred campus area TULT

C. Discovery and privacy settings

Pengaturan apakah mahasiswa bersedia:

- Ditemukan melalui Study Intent.
- Mendapatkan undangan kelompok.
- Mendapatkan rekomendasi dari mahasiswa di luar angkatan.
- Menerima notifikasi ketika terdapat match baru.
  Tidak semua informasi profil harus ditampilkan kepada mahasiswa lain. Sistem hanya perlu menampilkan informasi yang relevan untuk proses kolaborasi.
  1.3. Mengapa persistent preference dipisahkan dari Study Intent?
  Misalnya Nadia selalu menyukai offline learning.

Tetapi hari ini Nadia ingin belajar online karena sedang berada di luar kampus.

Maka:
Student Profile:
preferred_mode: OFFLINE

Study Intent:
mode: ONLINE

Preferensi profil berfungsi sebagai default, bukan aturan yang tidak bisa diubah.

Keputusan desain: Study Intent selalu menjadi sumber kebenaran untuk kebutuhan belajar saat ini.

III. STEP 2 — CREATE STUDY INTENT
Ini adalah fitur terpenting LaFriend.

Sistem harus mengubah kebutuhan mahasiswa yang masih berbentuk deskripsi menjadi data terstruktur yang dapat diproses oleh matching engine.

Saya merekomendasikan dua cara input.
2.1. Manual Study Intent
Pengguna mengisi form secara langsung.
Create Study Intent
Tell us what you want to study.

Course
Data Structures

Topic
Graph Algorithm

Learning Goal
Quiz Preparation

Collaboration Style
Problem Solving

Study Mode
Offline

Group Size
3–5 Students

Illustration of the form, not an active submission.

Data yang harus disediakan:
Parameter Wajib? Kegunaan
Course Ya Menentukan ruang lingkup akademik
Topic Dianjurkan Menentukan kesesuaian materi
Learning goal Ya Menentukan tujuan aktivitas
Availability Ya Menemukan waktu bersama
Preferred duration Ya Menentukan durasi minimum/ideal
Study mode Ya Online/offline
Collaboration style Ya Kesesuaian cara belajar
Group size Ya Menentukan ukuran kelompok
Location Conditional Jika offline
Additional notes Tidak Informasi pendukung

Jangan biarkan pengguna menentukan mata kuliah dan topik secara bebas tanpa katalog sama sekali. Kita perlu menyimpan referensi mata kuliah agar Data Structure, Data Structures, dan Struktur Data tidak dianggap tiga mata kuliah berbeda.
2.2. AI Intent Parser
Ini fitur yang saya rekomendasikan untuk meningkatkan kenyamanan pengguna.

Mahasiswa dapat menulis:
Saya mau belajar Graph Algorithm untuk persiapan kuis besok. Saya tersedia Selasa jam 7 malam selama dua jam, di kampus, lebih suka mengerjakan soal bersama 3 sampai 5 orang.

AI tidak langsung melakukan matching.

AI hanya mengubah deskripsi tersebut menjadi struktur data.

Contoh hasil:
{
"course": "Data Structures",
"topic": "Graph Algorithm",
"learning_goal": "QUIZ_PREPARATION",
"availability": [
{
"date": "2026-11-10",
"start_time": "19:00",
"end_time": "21:00"
}
],
"study_mode": "OFFLINE",
"collaboration_style": "PROBLEM_SOLVING",
"min_group_size": 3,
"max_group_size": 5,
"preferred_duration": 120,
"location": "Telkom University"
}

Tanggal di atas hanya contoh format data; sistem sesungguhnya memakai tanggal yang dipilih atau dikonfirmasi pengguna.
Bagaimana AI bekerja?
Natural Language Input
↓
LLM Intent Extraction
↓
Structured JSON
↓
Schema Validation
↓
Course/Topic Resolution
↓
Missing Field Detection
↓
User Confirmation
↓
Create Study Intent

Ada empat aturan yang menurut saya wajib.

1. AI tidak boleh mengarang jadwal yang tidak diberikan.
2. AI tidak boleh mengubah nama mata kuliah menjadi mata kuliah lain tanpa konfirmasi.
3. Jika informasi penting belum tersedia, sistem meminta pengguna melengkapinya.
4. Pengguna harus bisa mengedit hasil parsing sebelum disimpan.
   Contohnya, jika pengguna menulis:
   Besok malam mau belajar kalkulus.

AI dapat memperoleh:

- Course: Calculus.
- Availability: Besok malam.
- Topic: belum ditentukan.
- Goal: belum ditentukan.
- Duration: belum ditentukan.
  AI tidak boleh mengarang pukul 19.00–21.00. Sistem harus meminta pengguna menentukan waktu dan durasinya.
  Teknologi AI
  Kita dapat membuat sebuah IntentParserService yang memanggil LLM dengan output schema JSON.

Di backend Express:
async function parseStudyIntent(text) {
const extracted = await llm.extractStructuredData({
input: text,
schema: STUDY_INTENT_SCHEMA
});

const validated = validateStudyIntent(extracted);

return {
data: validated.data,
missingFields: validated.missingFields,
requiresConfirmation: true
};
}

llm.extractStructuredData di atas merupakan abstraksi service, bukan nama API provider tertentu.

AI harus bisa dinonaktifkan tanpa membuat LaFriend berhenti berfungsi. Form manual tetap menjadi jalur utama yang selalu tersedia.
2.3. Intent type
Saya menyarankan pengguna memilih satu di antara dua tipe Study Intent.

One-time Intent

Untuk satu kebutuhan belajar dengan tanggal tertentu.

Contoh:
Type: ONE_TIME
Course: Calculus
Topic: Integral
Date: Tuesday
Time: 19.00–21.00

Ongoing Intent

Untuk kebutuhan belajar yang dapat berlangsung beberapa hari.

Contoh:
Type: ONGOING
Course: Calculus
Topic: Integral

Availability:
Monday 19.00–21.00
Tuesday 19.00–21.00
Wednesday 18.00–20.00

Expires: 14 days

Masa berlaku 14 hari merupakan nilai awal konfigurasi yang perlu diuji. Pengguna dapat memperpanjang atau memperbarui intent.

IV. STEP 3 — AVAILABILITY AND SCHEDULE MANAGEMENT
Setelah Study Intent dibuat, LaFriend harus mengetahui kapan pengguna dapat belajar.

Saya menyarankan availability disimpan secara terpisah dari Student Profile dan Study Intent utama.

Alasannya, seseorang bisa memiliki banyak waktu kosong, tetapi hanya sebagian yang cocok untuk satu kebutuhan akademik tertentu.
3.1. Availability input
Pengguna dapat memasukkan lebih dari satu waktu.

Contoh:
Hari Mulai Selesai
Senin 19.00 21.00
Selasa 18.00 21.00
Rabu 19.00 22.00
Kamis Tidak tersedia —

Kemudian pengguna menentukan:

- Minimum study duration: 60 menit.
- Preferred duration: 120 menit.
- Flexible scheduling: Yes.
- Timezone: Asia/Jakarta.
  Perhatikan perbedaannya:

Minimum duration adalah waktu terpendek yang masih dianggap layak.

Preferred duration adalah waktu ideal yang diinginkan pengguna.

Misalnya, Nadia bisa belajar minimal 60 menit, tetapi menginginkan sesi selama 120 menit.
3.2. Bagaimana data availability disimpan?
Saya menyarankan tabel terpisah:
CREATE TABLE intent_availabilities (
id UUID PRIMARY KEY,
intent_id UUID NOT NULL,
date DATE,
day_of_week SMALLINT,
start_time TIME NOT NULL,
end_time TIME NOT NULL,
is_recurring BOOLEAN DEFAULT FALSE
);

Contoh:
intent_id day_of_week start_time end_time
INT001 1 19:00 21:00
INT001 2 18:00 21:00
INT001 3 19:00 22:00

Untuk jadwal tertentu, gunakan date. Untuk jadwal berulang, gunakan day_of_week.

Aturannya:

- date digunakan untuk jadwal pada tanggal tertentu.
- day_of_week digunakan untuk jadwal mingguan berulang.
- Jangan mengisi keduanya secara ambigu.
- Jangan menganggap slot mingguan terus berlaku tanpa batas; tetap gunakan expiry intent.
  3.3. Schedule intersection
  Ini adalah mekanisme yang akan digunakan Matching Engine.

Misalnya:
Mahasiswa Availability
Nadia 19.00–21.00
Fadly 19.30–21.30
Raka 20.00–22.00

Irisan waktunya:
\[
Start=\max(19.00,19.30,20.00)=20.00
\]

\[
End=\min(21.00,21.30,22.00)=21.00
\]

\[
Overlap=End-Start=60\text{ menit}
\]

Jadi ketiganya dapat belajar bersama selama pukul 20.00–21.00.

Tetapi kita harus menangani multiple availability.

Misalnya:

Nadia:

- Senin 19.00–21.00.
- Selasa 19.00–21.00.
  Fadly:
- Senin 20.00–22.00.
- Rabu 19.00–21.00.
  Hasil intersection bukan hanya menghitung jam, tetapi harus mempertimbangkan tanggal atau hari yang sama.

Nadia dan Fadly memiliki waktu bersama pada Senin pukul 20.00–21.00.

Mereka tidak memiliki irisan pada Selasa maupun Rabu.

Dengan demikian, sistem harus menghitung intersection berdasarkan pasangan tanggal dan interval, bukan hanya membandingkan jam.

V. STEP 4 — MATCHING ENGINE
Sekarang kita masuk ke inti sistem.

Matching Engine menerima Study Intent dan mencari berbagai peluang kolaborasi.

Saya menyarankan prosesnya dibagi menjadi enam tahap.
STUDY INTENT

1. Candidate Retrieval

Mengambil calon sesi dan mahasiswa

2. Eligibility Filtering

Membuang kandidat yang tidak layak

3. Compatibility Scoring

Menghitung nilai kecocokan

4. Recommendation Ranking

Mengurutkan sesi dan individu

5. Group Optimization

Menyusun kombinasi kelompok terbaik

6. WHY THIS MATCH

Menjelaskan alasan rekomendasi

4.1. Candidate Retrieval
Pertama, sistem mengambil kandidat berdasarkan kebutuhan akademik.

Misalnya Nadia mempunyai intent:
Course: Data Structures
Topic: Graph Algorithm
Goal: Quiz Preparation

Backend mencari:

1. Sesi belajar Data Structures yang masih aktif.
2. Mahasiswa yang memiliki Study Intent Data Structures yang masih aktif.
3. Mahasiswa yang mengizinkan intent-nya ditemukan.
4. Kandidat yang belum menjadi anggota sesi yang akan direkomendasikan.
   Contoh query sederhana untuk session retrieval:
   SELECT \*
   FROM study_sessions
   WHERE course_id = $1
   AND status = 'OPEN'
   AND start_at > NOW()
   AND current_members < max_members;

Untuk partner retrieval:
SELECT si.\*, s.id AS student_id
FROM study_intents si
JOIN students s ON s.id = si.student_id
WHERE si.course_id = $1
AND si.status = 'ACTIVE'
AND si.student_id <> $2
AND s.is_discoverable = TRUE;

Query ini baru mengambil kandidat awal. Jadwal, topik, mode, dan kondisi lainnya tetap diperiksa setelahnya.

Jangan langsung menghitung skor seluruh pengguna di database. Ambil kandidat yang memenuhi kriteria akademik dasar terlebih dahulu agar lebih efisien.
4.2. Eligibility Filtering
Tahap ini menentukan apakah kandidat boleh masuk ke proses ranking.

Saya merekomendasikan enam hard constraints.
Hard constraint Aturan
Course compatibility Mata kuliah sama atau sudah dipetakan sebagai ekuivalen
Minimum availability Ada waktu bersama yang mencukupi
Capacity Sesi masih mempunyai kapasitas
Session status Sesi belum ditutup atau dibatalkan
Study mode Tidak bertentangan dengan kebutuhan
User eligibility Intent aktif, pengguna discoverable, tidak diblokir, belum menjadi anggota

Mari gunakan contoh.

Nadia ingin:

- Data Structures.
- Graph Algorithm.
- Selasa 19.00–21.00.
- Offline.
- Minimal 60 menit.
  Kandidat:
  Kandidat Course Overlap Mode Hasil
  S1 Data Structures 90 menit Offline Pass
  S2 Data Structures 0 menit Offline Reject
  S3 Calculus 120 menit Offline Reject
  S4 Data Structures 90 menit Online Reject
  S5 Data Structures 60 menit Offline Pass

S1 dan S5 masuk ke scoring.

S2, S3, dan S4 tidak perlu diberi compatibility score sebagai rekomendasi langsung.

Catatan penting: untuk kebutuhan yang bersedia dijadwalkan ulang, S2 bisa dievaluasi dalam jalur Flexible Rescheduling, tetapi belum boleh ditampilkan sebagai sesi yang langsung dapat diikuti.
4.3. Compatibility Scoring
Saya menyarankan menggunakan tujuh parameter dengan bobot awal berikut.
Parameter Bobot
Topic Compatibility 25%
Learning Goal 15%
Collaboration Style 15%
Schedule Compatibility 20%
Study Mode & Location 10%
Group Size Compatibility 10%
Academic Level Compatibility 5%
Total 100%

Course tidak dimasukkan sebagai bobot karena sudah diperiksa melalui hard constraint.

Ini penting agar mata kuliah yang tidak relevan tidak bisa mendapatkan skor tinggi hanya karena aspek lainnya cocok.
A. Topic Compatibility
Kita membutuhkan hierarki topik.

Contoh:
Data Structures
├── Tree
│ ├── Binary Tree
│ └── AVL Tree
├── Graph
│ ├── BFS
│ ├── DFS
│ └── Dijkstra
└── Sorting
├── Merge Sort
└── Quick Sort

Nilai awal:
Hubungan topik Skor
Sama persis 1.00
Parent-child 0.85
Sibling 0.65
Related topic 0.40
Tidak berhubungan 0.00

Contoh:

- Nadia memilih Graph Algorithm.
- Fadly memilih BFS.
  Karena BFS merupakan subtopik Graph, skor = 0.85.

Namun, jika Nadia memilih Graph dan Fadly memilih Sorting, nilainya 0.

Untuk MVP, gunakan katalog hierarkis yang dikelola tim. Tidak perlu langsung menggunakan vector database atau embedding model hanya untuk mengidentifikasi kesamaan nama topik.
B. Learning Goal Compatibility
Kita bisa membangun compatibility matrix.
Goal A Goal B Skor awal
Quiz Preparation Quiz Preparation 1.00
Quiz Preparation Exam Preparation 0.85
Learn from Scratch Peer Explanation 0.80
Problem Practice Assignment Discussion 0.75
Learn from Scratch Project Collaboration 0.30

Contoh:

Nadia ingin persiapan kuis, Fadly juga ingin persiapan kuis.
\[
C\_{goal}=1.00
\]

Artinya kontribusi learning goal:
\[
15\%\times1.00=15
\]

C. Collaboration Style Compatibility
Saya menyarankan menyimpan gaya kolaborasi dalam bentuk kategori yang jelas.
Style Deskripsi
Quiet Co-study Belajar bersama dengan interaksi minimal
Discussion Berdiskusi dan bertukar pemahaman
Problem Solving Mengerjakan soal bersama
Peer Explanation Saling menjelaskan materi
Assignment Discussion Membahas tugas akademik
Project Collaboration Mengerjakan proyek bersama

Contoh compatibility matrix:
Kombinasi Skor
Problem Solving – Problem Solving 1.00
Problem Solving – Peer Explanation 0.85
Discussion – Peer Explanation 0.90
Discussion – Assignment Discussion 0.85
Quiet Co-study – Discussion 0.40
Quiet Co-study – Quiet Co-study 1.00

Nilai ini sebaiknya divalidasi melalui survei atau feedback pilot. Jangan menyimpulkan bahwa dua gaya yang berbeda otomatis tidak cocok.
D. Schedule Compatibility
Tahap pertama adalah minimum overlap check.

Misalnya:

- Nadia: 19.00–21.00.
- Fadly: 19.30–21.30.
- Preferred duration Nadia: 120 menit.
  Overlap = 90 menit.
  \[
  C\_{schedule}=
  \min\left(1,\frac{90}{120}\right)
  \]

\[
C\_{schedule}=0.75
\]

Kontribusi:
\[
20\%\times0.75=15
\]

Perlu diingat: overlap di bawah minimum duration akan ditolak sebelum scoring.
E. Study Mode & Location
Contoh nilai:
User Candidate Skor
Offline Offline, lokasi sama 1.00
Offline Offline, lokasi satu kampus 0.85
Offline Online 0.00
Online Online 1.00
Either Offline 1.00
Either Online 1.00

Untuk offline, sistem juga bisa menggunakan lokasi yang tersedia dalam katalog kampus.

Tidak perlu langsung menggunakan GPS tracking. Untuk LaFriend tahap awal, lokasi kampus seperti TULT, GKU, dan area belajar lainnya sudah mencukupi.
F. Group Size Compatibility
Misalnya:

- Nadia menginginkan kelompok 3–5 orang.
- Sesi memiliki 3 anggota.
- Jika Nadia bergabung, jumlahnya menjadi 4.
  Karena ukuran akhirnya masih berada di preferensi Nadia, nilai = 1.00.

Untuk mencocokkan rentang preferensi dua mahasiswa, kita bisa menggunakan:
\[
C\_{size} =
\frac{|A\cap B|}{|A\cup B|}
\]

dengan A dan B adalah himpunan ukuran kelompok yang mereka inginkan.

Contoh:

- Nadia: 5.
- Fadly: 4.
  \[
  C\_{size}=\frac{2}{4}=0.5
  \]

Untuk group formation, ukuran kelompok final harus memenuhi rentang minimum dan maksimum seluruh anggota, bukan hanya host.
G. Academic Level Compatibility
Kita dapat mempertimbangkan perbedaan tingkat akademik sebagai preferensi ringan.

Contoh:
Kondisi Skor awal
Tingkat akademik sejalan 1.00
Berdekatan 0.90
Perbedaan cukup jauh 0.75

Namun, jangan menjadikan angkatan sebagai hard constraint. Mahasiswa semester lebih tinggi justru bisa berperan sebagai peer explainer bagi mahasiswa semester awal.
4.4. Contoh perhitungan lengkap
Nadia memiliki intent:
Course: Data Structures
Topic: Graph Algorithm
Goal: Quiz Preparation
Schedule: 19.00–21.00
Mode: Offline
Location: TULT
Collaboration: Problem Solving
Group Size: 3–5
Preferred Duration: 120 minutes

Sesi S1:
Course: Data Structures
Topic: Graph Algorithm
Goal: Quiz Preparation
Schedule: 19.30–21.30
Mode: Offline
Location: TULT
Collaboration: Peer Explanation
Members: 3
Capacity: 5

Skor:
Parameter Bobot Nilai Kontribusi
Topic 25 1.00 25
Goal 15 1.00 15
Collaboration 15 0.85 12.75
Schedule 20 0.75 15
Mode & Location 10 1.00 10
Group Size 10 1.00 10
Academic Level 5 0.90 4.5
Total 100 92.25

\[
S=92.25\%
\]

Artinya sesi tersebut memiliki skor kompatibilitas 92.25 berdasarkan aturan yang kita definisikan.

Nilai ini bukan probabilitas keberhasilan pertemuan.
4.5. Missing data dan skor yang adil
Satu hal yang tidak boleh dilupakan: tidak semua pengguna akan mengisi semua preferensi dengan lengkap.

Misalnya, Nadia tidak memilih preferred collaboration style.

Kita tidak boleh otomatis memberikan skor 0 untuk collaboration.

Solusinya adalah melakukan normalisasi terhadap bobot yang tersedia:
\[
S=100\times
\frac{\sum w_i c_i}
{\sum w_i}
\]

Hanya kriteria yang mempunyai data valid yang dimasukkan.

Dengan demikian, sistem tidak menghukum pengguna karena tidak memberikan preferensi opsional.

Namun, sistem harus menunjukkan berapa banyak kriteria yang digunakan untuk menghitung skor tersebut.
4.6. Score interpretation
Untuk tahap awal, kita dapat menggunakan kategori berikut:
Skor Kategori
85–100 Highly Compatible
70–84.99 Compatible
55–69.99 Potentially Compatible
Di bawah 55 Tidak direkomendasikan

Threshold ini merupakan konfigurasi awal, bukan batas ilmiah. Nantinya perlu dievaluasi menggunakan data feedback dan keberhasilan sesi aktual.

VI. STEP 5 — SESSION MATCHING
Setelah Compatibility Scoring, sistem mengurutkan existing sessions.
5.1. Logika Session Matcher
Get active Study Intent
↓
Retrieve existing sessions
↓
Check course
↓
Check schedule
↓
Check session status
↓
Check capacity
↓
Calculate compatibility
↓
Rank sessions
↓
Display top recommendations

5.2. Contoh
Nadia mendapatkan:
Session Score Members Overlap
Graph Study A 92.25% 3/5 90 min
Graph Study B 88.50% 2/5 120 min
Graph Study C 76.00% 4/5 90 min

Urutan rekomendasi adalah A, B, C.

Namun, sistem dapat menerapkan tie-breaker jika skornya hampir sama, dengan mempertimbangkan:

- Durasi bersama.
- Sisa kapasitas.
- Waktu sesi.
- Status sesi.
  Hasil yang ditampilkan harus mencakup:
- Nama sesi.
- Course dan topic.
- Tujuan belajar.
- Waktu dan lokasi.
- Anggota saat ini.
- Kapasitas.
- Compatibility score.
- Alasan rekomendasi.
- Join policy.
  Session Matching tidak otomatis memasukkan pengguna ke sesi. Hasilnya tetap berupa rekomendasi yang harus disetujui pengguna.

VII. STEP 6 — PARTNER MATCHING
Apabila sesi yang tersedia belum cukup memenuhi kebutuhan pengguna, sistem tetap mencari potensi partner.

Namun, saya merekomendasikan Partner Matching tetap berjalan bersamaan dengan Session Matching. Dengan begitu, pengguna memiliki alternatif, tetapi urutan tampilan tetap mengutamakan sesi yang sudah tersedia.
6.1. Logika Partner Matcher
Get Study Intent
↓
Find active compatible intents
↓
Remove own intent
↓
Check user eligibility
↓
Check course and availability
↓
Calculate pair compatibility
↓
Rank partners
↓
Display recommendations

6.2. Contoh
Nadia membuat intent.

Matching menemukan:
Candidate Topic Goal Time overlap Score
Fadly Graph Quiz Prep 90 min 94%
Raka BFS Quiz Prep 120 min 91%
Kevin Graph Learn from Scratch 90 min 84%
Dimas Sorting Quiz Prep 120 min Reject

Dimas ditolak karena topiknya tidak memenuhi kriteria akademik.

Fadly, Raka, dan Kevin menjadi kandidat partner.
6.3. Jangan menyamakan partner match dengan friendship match
Pengguna tidak harus saling menyukai atau membangun hubungan sosial terlebih dahulu.

Mereka hanya perlu memiliki tujuan akademik dan kondisi kolaborasi yang kompatibel.

Ini penting untuk menjaga scope LaFriend tetap fokus.

VIII. STEP 7 — AUTOMATIC GROUP OPTIMIZATION
Ini salah satu fitur yang saya ingin jadikan pembeda teknis LaFriend.

Sistem tidak hanya menampilkan individu dengan skor tertinggi, melainkan mencoba menemukan kombinasi kelompok yang paling memungkinkan belajar bersama.
7.1. Problem yang ingin diselesaikan
Misalnya Nadia mempunyai tiga kandidat:

- Fadly: 94%.
- Raka: 91%.
- Kevin: 84%.
  Apakah kita langsung membentuk kelompok:

Nadia + Fadly + Raka + Kevin?

Belum tentu.

Kita harus memeriksa:

1. Apakah setiap pasangan mempunyai tingkat kompatibilitas minimum?
2. Apakah seluruh anggota memiliki waktu bersama?
3. Apakah ukuran kelompok sesuai keinginan seluruh anggota?
4. Apakah lokasi dan mode belajar memungkinkan?
5. Apakah tidak ada anggota yang sudah mengonfirmasi sesi lain yang bentrok?
   7.2. Pairwise compatibility matrix
   Misalnya diperoleh:
   Nadia Fadly Raka Kevin
   Nadia — 94 91 84
   Fadly 94 — 88 75
   Raka 91 88 — 82
   Kevin 84 75 82 —

Meskipun semuanya cocok dengan Nadia, kita tetap harus mengevaluasi kecocokan Fadly, Raka, dan Kevin satu sama lain.
7.3. Group availability
Misalnya:
Anggota Jadwal
Nadia 19.00–21.00
Fadly 19.30–21.30
Raka 20.00–22.00
Kevin 20.00–21.30

Irisan:
\[
Start=\max(19.00,19.30,20.00,20.00)=20.00
\]

\[
End=\min(21.00,21.30,22.00,21.30)=21.00
\]

\[
Overlap=60\text{ menit}
\]

Kelompok mempunyai 60 menit waktu bersama.

Jika durasi minimum setiap anggota terpenuhi, kandidat kelompok lolos.
7.4. Group compatibility score
Untuk menghindari satu pasangan yang sangat buruk tertutupi oleh rata-rata, kita bisa menggunakan:
\[
G*{cohesion}=0.7G*{avg}+0.3G\_{min}
\]

Keterangan:

- \(G\_{avg}\): rata-rata semua skor kompatibilitas pasangan.
- \(G*{min}\): skor pasangan terendah.
  Kemudian group score:
  \[
  G=0.65G*{cohesion}+0.25G*{schedule}+0.10G*{size}
  \]

Kita menggunakan komponen schedule dan group size secara terpisah agar tidak menghitung faktor yang sama berkali-kali.

Misalnya:

- Average pair score = 86%.
- Minimum pair score = 75%.
  \[
  G\_{cohesion}=0.7(86)+0.3(75)
  \]

\[
=82.7\%
\]

Misalkan:

- Schedule score = 100%.
- Group size score = 100%.
  \[
  G=0.65(82.7)+0.25(100)+0.10(100)
  \]

\[
G=88.755\%
\]

Optimized group
Graph Algorithm Study Group
88.76%
Illustrative group compatibility

Nadia · Fadly · Raka · Kevin

Tuesday, 20.00–21.00

4 members

Untuk kelompok yang lebih besar, tambahkan batas minimum pairwise compatibility. Contoh, seluruh pasangan harus memiliki nilai minimal 60%. Angka tersebut menjadi parameter awal yang harus diuji.
7.5. Group optimization algorithm
Saya menyarankan pendekatan constrained group search.

Alur:
Get Top Partner Candidates
↓
Limit Candidate Pool
↓
Generate Possible Groups
↓
Check Group Size
↓
Check Pairwise Compatibility
↓
Check Shared Availability
↓
Check Session Feasibility
↓
Calculate Group Score
↓
Rank Top Groups

Contoh pembatasan:

- Maksimum 20 kandidat teratas.
- Ukuran kelompok 3–5 orang termasuk pembuat intent.
- Hasil yang ditampilkan maksimal tiga grup terbaik.
- Setiap kelompok harus memenuhi waktu bersama minimum.
- Setiap anggota harus memberikan persetujuan.
  Untuk ukuran kandidat ini, kombinasi masih dapat dihitung secara eksplisit. Misalnya, dengan satu pengguna sebagai anggota tetap dan 19 kandidat lain, sistem menguji kombinasi dua sampai empat tambahan anggota:
  \[
  \binom{19}{2}+\binom{19}{3}+\binom{19}{4}
  =5.016
  \]

Itu masih masuk akal untuk pencarian terbatas dalam PoC. Ketika jumlah pengguna meningkat, kita dapat menggunakan pruning, greedy search, atau beam search untuk mengurangi kombinasi yang diperiksa.

IX. STEP 8 — RECOMMENDATION PAGE
Hasil dari ketiga pencarian sebaiknya ditampilkan dalam satu halaman, tetapi dibagi berdasarkan jenis peluang.

Saya mengusulkan:
Your Study Opportunities
Based on your Graph Algorithm study intent

Priority 1 · Existing session
Graph Algorithm Quiz Preparation
92.25%
Compatibility score
Tuesday · 19.30–21.30

TULT

3/5 members

Why this match?

✓ Same course and topic

✓ Same learning goal

✓ Compatible collaboration

✓ 90-minute schedule overlap

✓ Available capacity
Join Existing Session

Priority 2 · Study partners
Compatible students
Fadly · Graph Algorithm
94%

Raka · BFS
91%

Kevin · Graph Algorithm
84%

Suggested group formation
4 compatible students · 88.76%

Tuesday · 20.00–21.00

View group suggestion

Ini ilustrasi informasi dan skor, bukan hasil pencocokan data pengguna nyata.

Keputusan desain yang penting:

- Existing sessions diletakkan paling atas.
- Partner matching ditampilkan sebagai alternatif.
- Suggested groups menjadi rekomendasi tambahan.
- Jangan menggabungkan ketiganya menjadi satu daftar angka yang tidak sebanding.
  Dengan demikian, konsep Session-First tetap terlihat tanpa membatasi kemampuan sistem.

X. STEP 9 — FLEXIBLE RESCHEDULING
Sekarang kita masuk ke fitur yang membuat LaFriend lebih fleksibel.

Masalah umum dalam pembentukan kelompok adalah tidak semua mahasiswa mempunyai waktu yang sama.

Flexible Rescheduling membantu mencari waktu alternatif ketika jadwal awal tidak memungkinkan.
10.1. Kondisi pertama: terdapat overlap
Misalnya:
Anggota Jadwal awal
Nadia Senin 19.00–21.00
Fadly Senin 20.00–22.00
Raka Selasa 19.00–21.00

Tidak ada waktu bersama untuk ketiganya.

Namun, mereka juga mengisi alternatif:
Anggota Alternatif
Nadia Selasa 18.00–22.00
Fadly Selasa 19.00–22.00
Raka Selasa 19.30–22.00

Sistem menemukan irisan:
\[
Start=\max(18.00,19.00,19.30)=19.30
\]

\[
End=\min(22.00,22.00,22.00)=22.00
\]

\[
Overlap=150\text{ menit}
\]

Sistem mengusulkan:

Tuesday, 19.30–22.00.
10.2. Bagaimana sistem memilih jadwal terbaik?
Kalau terdapat lebih dari satu pilihan, kita perlu menghitung time preference score.

Misalnya terdapat tiga opsi:
Slot Nadia Fadly Raka
Tuesday 19.30 1.00 0.90 1.00
Tuesday 20.00 1.00 1.00 1.00
Wednesday 19.00 0.90 0.80 1.00

Sistem menghitung rata-rata preferensi:
\[
T*{slot}=\frac{\sum*{i=1}^{n}P_i}{n}
\]

Untuk slot Selasa pukul 20.00:
\[
T\_{slot}=\frac{1+1+1}{3}=1.00
\]

Slot tersebut menjadi rekomendasi pertama.

Nilai preferensi awal dapat berasal dari pilihan yang diberikan setiap mahasiswa, bukan hasil tebakan sistem.
10.3. Konfirmasi jadwal
Sistem tidak boleh otomatis mengubah jadwal anggota.

Flow-nya:
No shared initial schedule
↓
Search alternative availability
↓
Generate candidate slots
↓
Rank alternative slots
↓
Propose best schedule
↓
Ask all members to confirm
↓
Everyone accepts?
/ \
 YES NO
| |
v v
Confirm Suggest another
Session available slot

Jika salah satu anggota tidak menyetujui, sistem dapat menawarkan jadwal berikutnya.

Jika tidak ada slot yang layak, sistem menyampaikan bahwa penjadwalan ulang belum berhasil.
10.4. Teknologi
Flexible Rescheduling membutuhkan:

- Availability Engine.
- Time Interval Intersection.
- Scheduling Proposal Service.
- Confirmation Management.
- Notification Service.
  Kita tidak perlu integrasi Google Calendar pada tahap pertama. Sistem bisa mengoptimalkan slot berdasarkan availability yang dimasukkan pengguna.

XI. STEP 10 — PERSISTENT INTENT NOTIFICATIONS
Satu fitur penting lainnya adalah kemampuan menemukan match ketika pengguna sedang tidak membuka LaFriend.

Misalnya:

- Nadia membuat Study Intent hari Senin.
- Tidak ditemukan partner.
- Hari Selasa Fadly membuat intent yang cocok.
- Sistem mendeteksi keduanya.
- Nadia dan Fadly menerima pemberitahuan.
  11.1. Event yang memicu matching ulang
  Matching ulang harus berjalan ketika:

1. Study Intent baru dibuat.
2. Study Intent diubah.
3. Availability berubah.
4. Study Session baru dibuat.
5. Session dibuka kembali.
6. Kapasitas sesi berubah.
7. Ada mahasiswa baru yang cocok.
8. Ada jadwal alternatif yang disetujui.
   Ini berarti matching tidak hanya dipanggil saat pengguna menekan tombol Find Match.
   11.2. Event-driven architecture
   Untuk MVP, gunakan event-driven workflow di dalam modular monolith.

Contoh:
Student creates new intent
|
v
Save intent in PostgreSQL
|
v
Publish matching event
|
v
Background worker processes event
|
v
Find compatible intents
|
v
Create new match records
|
v
Generate notifications
|
v
Notify relevant students

Saya merekomendasikan PostgreSQL sebagai database utama dan pg-boss sebagai background job queue agar kita tidak perlu langsung menambahkan Redis ke arsitektur.

Jika nantinya membutuhkan distributed workers dan throughput lebih tinggi, Redis + BullMQ dapat dipertimbangkan.
11.3. Persistent Intent lifecycle
Saya menyarankan status berikut:
Status Arti
Draft Belum selesai dibuat
Active Sedang mencari peluang
Matched Sudah memiliki kandidat
Converted Sudah menjadi bagian sesi
Paused Untuk sementara tidak dicari
Expired Masa berlaku berakhir
Cancelled Dibatalkan

Satu intent juga perlu mempunyai:

- created_at
- updated_at
- expires_at
- last_matched_at
- last_notified_at
  11.4. Notification management
  Contoh notifikasi:
  New Study Opportunity
  New

Nadia, ada mahasiswa yang memiliki kebutuhan belajar kompatibel dengan intent Graph Algorithm Anda.

Fadly — 94% Compatibility

Tuesday · 19.30–21.00

Kecocokan berdasarkan mata kuliah, topik, tujuan, dan jadwal.

Kita juga harus mempunyai sistem anti-spam:

- Jangan mengirim notifikasi berulang untuk match yang sama.
- Gunakan unique key untuk setiap kombinasi intent dan kandidat.
- Terapkan cooldown.
- Sediakan opsi pause.
- Berikan kontrol pengguna terhadap jenis notifikasi.
  Notifikasi baru dikirim ketika ada kesempatan baru atau perubahan yang signifikan, bukan setiap kali worker berjalan.

XII. STEP 11 — GROUP INVITATION AND SESSION JOIN
Setelah pengguna mendapatkan rekomendasi, mereka harus bisa mengambil tindakan.

Ada tiga mekanisme utama.
12.1. Join Existing Session
Untuk sesi yang sudah dibuat:
View Session
↓
Check Join Policy
↓
OPEN or APPROVAL

Open Session

Pengguna langsung menjadi anggota selama kapasitas masih tersedia.

Approval Session

Pengguna mengirim permintaan dan host memutuskan menerima atau menolak.

Saya menyarankan host dapat menentukan join policy pada saat membuat sesi.
12.2. Group Invitation
Untuk kelompok baru:
Select Suggested Group
↓
Send Invitations
↓
Members Receive Notifications
↓
Accept / Reject
↓
Check Group Requirements
↓
All Required Members Confirm?
↓
Create Confirmed Session

Contoh:

Nadia membuat grup dengan Fadly, Raka, dan Kevin.

Status undangan:
Student Invitation
Nadia Host
Fadly Accepted
Raka Accepted
Kevin Pending

Kelompok belum menjadi sesi terkonfirmasi selama syarat minimum anggota belum terpenuhi.

Sistem dapat memberi batas waktu kepada undangan. Contohnya, 12 jam atau sampai waktu tertentu sebelum jadwal. Nilainya harus disesuaikan dengan waktu kegiatan.

Jika jumlah peserta yang menerima undangan kurang dari minimum group size, sistem dapat menawarkan:

- Mengundang kandidat lain.
- Mencari rekomendasi kelompok lain.
- Menurunkan ukuran kelompok apabila seluruh pihak menyetujui.
- Membatalkan pembentukan kelompok.
  12.3. Group confirmation
  Setelah syarat anggota dan jadwal terpenuhi:
  Session:
  Graph Algorithm Quiz Preparation

Host:
Nadia

Members:
Nadia
Fadly
Raka

Date:
Tuesday

Time:
20.00–21.30

Status:
SCHEDULED

Baru pada tahap inilah kita mencatat bahwa sesi belajar sudah berhasil terbentuk.

XIII. STEP 12 — STUDY SESSION MANAGEMENT
Study Session mempunyai lifecycle tersendiri.
Status Penjelasan
OPEN Menerima anggota baru
FULL Kapasitas terpenuhi
SCHEDULED Anggota dan jadwal sudah dikonfirmasi
ONGOING Sesi sedang berlangsung
COMPLETED Sesi selesai
CANCELLED Sesi dibatalkan
EXPIRED Sesi tidak lagi berlaku

Perlu dibedakan antara FULL dan SCHEDULED.

Sesi bisa penuh tetapi belum tentu jadwalnya sudah dikonfirmasi seluruh anggota. Sebaliknya, sesi yang sudah terjadwal mungkin masih memiliki kapasitas tambahan.

Jadi status dan kapasitas harus diperlakukan sebagai dua dimensi yang berbeda.
13.1. Session detail
Halaman detail minimal menampilkan:

- Nama sesi.
- Course dan topic.
- Learning goal.
- Waktu.
- Lokasi atau platform online.
- Host.
- Daftar anggota.
- Kapasitas.
- Join policy.
- Status.
- Informasi kebutuhan belajar.
  13.2. Menangani anggota yang keluar
  Jika mahasiswa keluar:

1. Membership diubah menjadi LEFT.
2. Kapasitas diperbarui.
3. Sesi diperiksa kembali.
4. Jika masih menerima anggota, status kembali OPEN.
5. Matching Engine dapat mencari kandidat baru.
   Jika jumlah anggota di bawah minimum kelompok, sistem dapat mengirim notifikasi kepada host untuk menentukan apakah sesi tetap berlangsung atau dibatalkan.

XIV. STEP 13 — STUDY COMPLETION AND FEEDBACK
Jangan berhenti setelah sesi dibuat.

LaFriend harus mengukur apakah aktivitas belajar benar-benar terjadi.
13.1. Completion confirmation
Setelah waktu sesi berakhir, sistem meminta konfirmasi kepada setiap anggota:
Did this study session happen?

Pilihan:

- Yes, it happened.
- No, it did not happen.
  Sistem sebaiknya tidak langsung menganggap sesi berhasil hanya karena waktu sudah lewat.
  13.2. Relevance feedback
  Setelah pengguna mengonfirmasi bahwa sesi terjadi:
  How relevant was this session to your study need?

Rating:

1–5.

Feedback tambahan:

- Apakah sesi sesuai dengan tujuan awal?
- Apakah kelompok cukup produktif?
- Apakah ingin belajar bersama anggota tersebut kembali?
  Feedback ini bukan untuk menilai kemampuan atau karakter seseorang secara mutlak. Tujuannya mengevaluasi kualitas matching dan pengalaman sesi.
  13.3. Feedback analytics
  Contoh:
  Metric Result
  Average relevance 4.3/5
  Completed sessions 18
  Confirmed sessions 22
  Completion rate 81.82%

Jika 18 sesi selesai dari 22 sesi terkonfirmasi yang telah jatuh tempo:
\[
CompletionRate=
\frac{18}{22}\times100\%
\]

\[
=81.82\%
\]

Jangan masukkan sesi yang belum waktunya berlangsung ke dalam denominator.

XV. STEP 14 — MATCHING ENGINE IMPROVEMENT
Setelah mendapatkan feedback, LaFriend dapat memperbaiki kualitas rekomendasi.

Di sini ada fitur Adaptive Weight Optimization yang sebelumnya kita sebut bobot adaptif.

Saya ingin membedakan dua hal:

- Bobot awal ditetapkan melalui desain produk.
- Bobot berikutnya diperbaiki berdasarkan data hasil penggunaan.
  Jangan langsung menggunakan machine learning untuk mengubah bobot secara otomatis pada jumlah data yang masih sedikit.
  14.1. Bobot awal
  Contoh:
  Kriteria Bobot awal
  Topic 25%
  Goal 15%
  Collaboration 15%
  Schedule 20%
  Mode & Location 10%
  Group Size 10%
  Academic Level 5%

  14.2. Bagaimana bobot adaptif bekerja?
  Misalnya setelah pilot:

- Mahasiswa sangat memperhatikan kesamaan topik.
- Mahasiswa cukup fleksibel terhadap learning goal.
- Schedule menjadi faktor yang paling menentukan.
- Collaboration style mempunyai pengaruh terhadap relevance feedback.
  Tim mengumpulkan:

1. Skor rekomendasi.
2. Kapan pengguna melakukan join.
3. Apakah sesi benar-benar terbentuk.
4. Apakah sesi terlaksana.
5. Nilai relevansi dari pengguna.
   Kemudian tim melakukan evaluasi bobot.

Contoh perubahan:
Kriteria Awal Hasil eksperimen
Topic 25% 28%
Goal 15% 14%
Collaboration 15% 17%
Schedule 20% 21%
Mode & Location 10% 9%
Group Size 10% 7%
Academic Level 5% 4%
Total 100% 100%

Ini hanyalah simulasi perubahan, bukan kesimpulan bahwa bobot tersebut lebih baik.

Evaluasi harus menggunakan data yang cukup dan perbandingan yang adil, misalnya membandingkan konfigurasi bobot A dengan B menggunakan test set atau pilot berikutnya.

Rekomendasi saya: gunakan controlled weight optimization, bukan self-learning tanpa kontrol.

Perubahan bobot harus:

- Dapat ditinjau administrator.
- Memiliki versi konfigurasi.
- Bisa dikembalikan.
- Dievaluasi berdasarkan metrik.
- Tidak mengubah hard constraints secara otomatis.

XVI. STEP 15 — DATABASE ARCHITECTURE LENGKAP
Setelah seluruh logic ditetapkan, berikut struktur database yang saya sarankan.
Tabel Fungsi
students Identitas mahasiswa
student_preferences Preferensi default
programs Program studi
courses Katalog mata kuliah
course_equivalencies Mata kuliah ekuivalen
topics Hierarki topik
learning_goals Katalog tujuan
collaboration_styles Katalog gaya kolaborasi
study_intents Study Intent utama
intent_availabilities Jadwal intent
study_sessions Sesi belajar
session_members Anggota sesi
join_requests Permintaan masuk
group_suggestions Rekomendasi grup
group_suggestion_members Anggota rekomendasi grup
group_invitations Undangan grup
schedule_proposals Usulan jadwal
schedule_responses Konfirmasi jadwal
match_records Hasil matching
match_explanations Alasan rekomendasi
notifications Notifikasi
session_feedback Feedback sesi
intent_events Riwayat perubahan intent
matching_configurations Konfigurasi bobot dan aturan

16.1. Hubungan utama database
STUDENTS

STUDY INTENTS

Belongs to one student

AVAILABILITIES

Multiple slots

MATCH RECORDS

Many recommendations

GROUP SUGGESTIONS

Generated combinations

STUDY SESSIONS

Confirmed activity

SESSION MEMBERS

Membership of students

SESSION FEEDBACK

Diagram tersebut merupakan ringkasan hubungan logis, bukan representasi seluruh foreign key. Secara implementasi, group_suggestions dan study_sessions tetap harus dipisahkan karena rekomendasi kelompok belum tentu disetujui.

XVII. STEP 16 — TECH STACK AND SYSTEM IMPLEMENTATION
Untuk keseluruhan fitur tadi, saya menyarankan arsitektur berikut.
Layer Teknologi Fungsi
Frontend Next.js, JavaScript Web application
Backend Express.js, Node.js REST API dan business logic
Database PostgreSQL Persistent storage
ORM Prisma Database access dan schema
Matching JavaScript Filtering, scoring, ranking
Group optimization JavaScript Constrained group search
AI parser LLM API via provider adapter Natural-language extraction
Background jobs pg-boss Expiry, re-matching, notifications
Validation Zod Validasi payload dan output parser
Authentication Secure session/JWT approach Authentication dan authorization
Testing Vitest/Jest + API integration tests Unit dan integration tests

Saya sengaja belum memasukkan Kafka, Kubernetes, microservices, dan vector database.

Untuk skala awal LaFriend, teknologi tersebut belum memberikan nilai yang sebanding dengan kompleksitas tambahan.
17.1. Backend architecture
Saya menyarankan modular monolith:
backend/
└── src/
├── modules/
│ ├── auth/
│ ├── students/
│ ├── preferences/
│ ├── courses/
│ ├── topics/
│ ├── intents/
│ ├── availability/
│ ├── matching/
│ │ ├── candidate-retrieval/
│ │ ├── eligibility/
│ │ ├── schedule/
│ │ ├── scoring/
│ │ ├── session-matcher/
│ │ ├── partner-matcher/
│ │ ├── group-optimizer/
│ │ └── explanation/
│ ├── sessions/
│ ├── invitations/
│ ├── rescheduling/
│ ├── notifications/
│ ├── feedback/
│ └── analytics/
├── jobs/
├── database/
├── middleware/
└── app.js

17.2. Frontend pages
Halaman Fungsi
Login/Register Autentikasi
Onboarding Profil dan preferensi
Dashboard Ringkasan kebutuhan aktif
Create Intent Membuat kebutuhan belajar
Intent Parser Input bahasa alami
My Intents Mengelola kebutuhan
Study Opportunities Rekomendasi
Suggested Groups Rekomendasi kelompok
Session Details Informasi sesi
Invitations Permintaan dan undangan
My Sessions Sesi yang diikuti
Rescheduling Mengelola alternatif jadwal
Feedback Evaluasi sesi
Notifications Pemberitahuan
Profile & Settings Identitas dan privasi

XVIII. STEP 17 — SECURITY, PRIVACY, AND DATA INTEGRITY
Ada beberapa hal yang wajib disiapkan karena LaFriend mempertemukan orang yang belum tentu saling mengenal.

1. Campus verification

Pengguna harus melewati proses verifikasi identitas kampus sesuai kemampuan integrasi yang tersedia.

2. Discovery privacy

Mahasiswa dapat mengatur apakah Study Intent mereka dapat ditemukan pengguna lain.

3. Blocking and reporting

Pengguna dapat memblokir akun lain dan melaporkan perilaku yang tidak sesuai. Akun yang diblokir tidak boleh muncul dalam rekomendasi satu sama lain.

4. Authorization

Host hanya dapat mengelola sesi yang menjadi tanggung jawabnya. Pengguna tidak boleh mengubah membership milik orang lain.

5. Database integrity

Gunakan unique constraints, foreign keys, transactions, dan idempotency untuk menghindari anggota ganda, undangan ganda, atau overcapacity.

6. AI privacy

Hanya kirim informasi yang diperlukan untuk parsing intent. Jangan mengirim informasi profil pribadi atau identitas mahasiswa jika tidak diperlukan.

7. Notification control

Pengguna dapat pause intent dan mengatur notifikasi. Status tersebut harus dihormati oleh background worker.

XIX. STEP 18 — TESTING AND PERFORMANCE EVALUATION
Menurut saya, bagian ini sangat menentukan kualitas PoC STACK.

Kita tidak cukup hanya menunjukkan aplikasi bisa menemukan mahasiswa.

Kita harus membuktikan bahwa mekanisme matching benar-benar berfungsi.
18.1. Functional testing
Berikut contoh skenario yang wajib diuji.
Test case Expected result
Course tidak relevan Kandidat ditolak
Jadwal tidak beririsan Tidak direkomendasikan untuk join langsung
Jadwal memenuhi minimum Kandidat lolos
Sesi penuh Tidak dapat join
Sesi sudah dibatalkan Tidak muncul sebagai rekomendasi
Partner diblokir Tidak muncul
Duplicate join Ditolak
Dua pengguna berebut satu tempat Kapasitas tetap valid
Semua anggota setuju jadwal Sesi terjadwal
Satu anggota menolak Proposal tidak dikonfirmasi
Intent kedaluwarsa Tidak lagi dicari
AI menghasilkan data tidak valid Meminta koreksi pengguna

18.2. Matching evaluation
Selain functional testing, kita perlu menguji apakah ranking-nya masuk akal.

Contoh:

Tim menyiapkan 50 kasus Study Intent dan menentukan kandidat yang dianggap relevan melalui penilaian manual beberapa mahasiswa atau evaluator.

Kemudian hitung:

- Precision@K: dari K rekomendasi teratas, berapa yang relevan?
- Recall@K: dari seluruh kandidat relevan, berapa yang berhasil ditemukan?
- NDCG@K: apakah kandidat yang paling relevan berada di urutan teratas?
  Ini lebih baik daripada sekadar menyatakan algoritma mempunyai accuracy 95% tanpa mendefinisikan ground truth.
  18.3. Product evaluation
  Metrik Rumus
  Time-to-Match Waktu rekomendasi relevan − waktu intent dibuat
  Match-to-Session Conversion Intent yang menjadi sesi terkonfirmasi / intent yang memperoleh rekomendasi relevan
  Session Completion Rate Sesi selesai / sesi terkonfirmasi yang sudah jatuh tempo
  User-Rated Relevance Rata-rata penilaian relevansi
  Recommendation Precision@K Rekomendasi relevan dalam K teratas / K
  Group Formation Success Grup yang terkonfirmasi / grup yang disarankan dan dipilih

Untuk menguji manfaat LaFriend, lakukan perbandingan pencarian konvensional dengan pencarian menggunakan LaFriend pada tugas dan kondisi yang sebanding.

Misalnya, peserta diminta menemukan partner untuk topik dan jadwal tertentu melalui dua metode tersebut. Ukur waktu, jumlah interaksi, keberhasilan membentuk kelompok, dan penilaian relevansi.

XX. MASTER WORKFLOW — CONTOH LAQFRIEND DARI AWAL SAMPAI AKHIR
Sekarang mari kita gabungkan seluruh fitur tadi dalam satu simulasi penggunaan.

Kita menggunakan empat mahasiswa:

- Nadia: ingin mempersiapkan kuis Graph Algorithm.
- Fadly: ingin berlatih BFS dan DFS.
- Raka: ingin memahami Graph Algorithm dari dasar.
- Kevin: ingin mengerjakan latihan soal Graph Algorithm.
  20.1. Nadia membuat Study Intent
  Nadia login, kemudian memasukkan kebutuhan belajar menggunakan AI Intent Parser.

Input:
Saya ingin belajar Graph Algorithm untuk persiapan kuis. Saya bisa Selasa pukul 19.00–21.00 secara offline di TULT. Saya lebih suka problem solving dengan 3–5 orang.

AI menghasilkan structured intent.

Nadia memeriksa hasilnya dan menekan Confirm.

Database menyimpan:
intent_id: INT001
student_id: NADIA
course: DATA_STRUCTURES
topic: GRAPH_ALGORITHM
goal: QUIZ_PREPARATION
availability:

- date: TUESDAY
  start: 19:00
  end: 21:00
  mode: OFFLINE
  location: TULT
  collaboration: PROBLEM_SOLVING
  min_group_size: 3
  max_group_size: 5
  min_duration: 60
  preferred_duration: 120
  intent_type: ONE_TIME
  status: ACTIVE

  20.2. Matching Engine mulai bekerja
  Sistem menjalankan dua pencarian sekaligus:
  NADIA INTENT
  |
  +---------------------+
  | |
  v v
  SESSION MATCHER PARTNER MATCHER
  | |
  v v
  Existing Sessions Active Intents
  | |
  v v
  Eligibility Filter Eligibility Filter
  | |
  v v
  Scoring Scoring
  | |
  v v
  Ranking Ranking
  | |
  +----------+----------+
  |
  v
  GROUP OPTIMIZER
  |
  v
  RECOMMENDATION

Hasil pencarian:
Recommendation Score Availability
Existing Session A 92.25% 90 menit
Fadly 94% 90 menit
Raka 91% 120 menit
Kevin 84% 90 menit

Kemudian Group Optimizer mencoba mengombinasikan Nadia, Fadly, Raka, dan Kevin.

Hasilnya:

- Group A: Nadia + Fadly + Raka.
- Group B: Nadia + Fadly + Kevin.
- Group C: Nadia + Raka + Kevin.
  Masing-masing dihitung berdasarkan kompatibilitas antaranggota, waktu bersama, dan ukuran kelompok.

Sistem mengurutkan kelompok yang paling layak.
20.3. Tidak ada sesi yang cocok? Flexible Rescheduling bekerja
Misalnya ternyata tidak ada satu pun existing session yang memiliki overlap minimal 60 menit.

Namun, ada tiga mahasiswa yang memiliki jadwal alternatif.

Sistem mencari common availability dari seluruh calon anggota.

Jika ditemukan, LaFriend mengusulkan waktu alternatif.

Jika seluruh anggota menyetujui, sistem membuat jadwal baru.

Jika tidak ditemukan jadwal alternatif, intent tetap dapat aktif untuk mencari kesempatan lain selama masa berlakunya belum habis.
20.4. Pengguna memilih rekomendasi
Nadia mempunyai tiga pilihan:

1. Join Existing Session.
2. Invite Compatible Partners.
3. Select Suggested Group.
   Nadia memilih Suggested Group A.

LaFriend mengirimkan invitation kepada Fadly dan Raka.

Status:
Nadia: HOST
Fadly: PENDING
Raka: PENDING

Fadly menerima.

Raka menerima.

Kelompok memenuhi minimum anggota dan jadwal sudah disepakati.
20.5. Study Session terbentuk
Backend membuat satu Study Session baru.
session_id: SES001
title: Graph Algorithm Quiz Preparation
host: Nadia
members:

- Nadia
- Fadly
- Raka
  date: Tuesday
  start_time: 20:00
  end_time: 21:30
  location: TULT
  status: SCHEDULED

Study Intent masing-masing anggota kemudian ditandai sebagai CONVERTED atau ditautkan ke sesi tersebut.

Apabila anggota ingin mencari kelompok lain untuk kebutuhan akademik berbeda, mereka tetap dapat membuat Study Intent baru.
20.6. Sesi selesai dan memperoleh feedback
Setelah jadwal belajar:

- Nadia mengonfirmasi sesi berlangsung.
- Fadly mengonfirmasi sesi berlangsung.
- Raka mengonfirmasi sesi berlangsung.
  Sesi ditandai Completed berdasarkan aturan konfirmasi yang ditetapkan.

Masing-masing memberikan penilaian relevansi.

Data tersebut masuk ke Analytics Engine.
20.7. Sistem memperoleh data untuk perbaikan
LaFriend sekarang memiliki data:
Study Intent
↓
Recommendations
↓
Join / Invitation
↓
Confirmed Session
↓
Completed Session
↓
User Feedback

Data ini dapat digunakan untuk mengevaluasi:

- Apakah rekomendasi yang memiliki skor tinggi benar-benar relevan?
- Apakah jadwal menjadi faktor yang paling menentukan?
- Apakah mahasiswa lebih sering bergabung ke existing session atau membentuk kelompok baru?
- Apakah automatic group suggestion menghasilkan lebih banyak sesi?
- Apakah flexible rescheduling meningkatkan conversion?
  Inilah yang akan menjadikan LaFriend produk yang dapat dievaluasi secara nyata, bukan sekadar aplikasi dengan banyak fitur.

XXI. URUTAN IMPLEMENTASI DEVELOPMENT
Meskipun semua fitur menjadi bagian dari rancangan produk, saya tetap menyarankan pengembangan berdasarkan dependency antarmodul.

Jadi bukan menunda fitur, melainkan memastikan setiap fitur dibangun di atas fondasi yang benar.
LaFriend Development Roadmap

1. Foundation & Authentication

   Student registration, verification, profile, preference, privacy, dan course catalog.
   Foundation

2. Study Intent Management

   Manual form, AI Intent Parser, structured intent, availability, one-time dan ongoing intent.

3. Schedule Engine

   Interval intersection, recurring availability, minimum duration, dan timezone handling.

4. Core Matching Engine

   Candidate retrieval, hard constraints, compatibility matrix, scoring, ranking, dan explanation.

5. Session & Partner Matching

   Existing session search, compatible student search, serta rekomendasi gabungan.

6. Group Optimization

   Pairwise matrix, group availability, constrained group search, dan automatic group suggestion.

7. Session Creation & Management

   Join policy, invitation, approval, membership, capacity, dan session lifecycle.

8. Flexible Rescheduling

   Alternative availability, slot ranking, scheduling proposals, dan confirmation.

9. Persistent Matching & Notifications

   Event-driven matching, expiry worker, re-matching, notification deduplication, dan user preferences.

10. Study Completion & Feedback

    Completion tracking, relevance rating, feedback collection, dan analytics.

11. Optimization & Evaluation

    Adaptive weighting experiments, ranking evaluation, performance testing, dan pilot implementation.

XXII. HAL YANG MENURUT SAYA HARUS MENJADI KEKUATAN UTAMA LaFriend
Setelah seluruh sistem dijabarkan, saya ingin menekankan tiga diferensiasi yang menurut saya paling layak dibawa ke kompetisi.

1. Intent-Based Matching
   Mahasiswa tidak perlu mencari secara manual satu per satu.

Mereka cukup menyampaikan apa yang ingin dipelajari, kapan tersedia, dan bagaimana mereka ingin berkolaborasi.

AI membantu mengubah bahasa alami menjadi informasi terstruktur, sementara matching engine memproses kebutuhan tersebut. 2. Feasibility-Aware Group Formation
Ini yang menurut saya paling menarik secara teknis.

LaFriend tidak hanya mencari mahasiswa dengan kebutuhan yang mirip.

Sistem juga mengevaluasi apakah kombinasi mereka benar-benar memungkinkan untuk membentuk satu kelompok.

Aspek yang dipertimbangkan meliputi:

- Kesesuaian akademik.
- Kompatibilitas antaranggota.
- Irisan jadwal seluruh anggota.
- Durasi belajar minimum.
- Ukuran kelompok.
- Kapasitas sesi.
- Ketersediaan alternatif waktu.
  Hal ini membuat hasil matching lebih berorientasi pada kelayakan aktivitas, bukan sekadar similarity.

3. Outcome-Oriented Matching
   LaFriend mengukur keberhasilan berdasarkan hasil akhir.

Bukan hanya:
How many students did we match?

Namun:
How many compatible study opportunities successfully became completed study sessions?

Inilah yang menghubungkan matching engine dengan manfaat nyata produk.

XXIII. REKOMENDASI FINAL SYSTEM DESIGN
Berikut seluruh keputusan yang saya rekomendasikan untuk dijadikan baseline system specification LaFriend.
Komponen Keputusan final
Product approach Intent-Based Academic Collaboration
Input Manual + AI Intent Parser
Intent lifecycle One-Time + Ongoing
Availability Multiple slots
Matching approach Hybrid Matching
Session matching Prioritas tampilan pertama
Partner matching Berjalan bersamaan
Filtering Hard Constraint Filtering
Ranking Explainable Weighted Scoring
Topic matching Hierarchical Topic Taxonomy
Collaboration matching Compatibility Matrix
Schedule matching Interval Intersection
Group formation Automatic Group Optimization
Group score Pairwise Compatibility + Group Feasibility
Rescheduling Flexible Schedule Proposal
Joining Configurable Open / Approval
Notifications Persistent Event-Driven Notifications
Feedback Session Completion + Relevance
Weight optimization Data-driven, controlled experiments
Backend Express.js Modular Monolith
Frontend Next.js
Database PostgreSQL
Background jobs pg-boss
AI Natural-language parsing, bukan penentu final match

Satu koreksi kecil atas contoh tanggal sebelumnya: apabila pengguna menulis "besok" pada 10 November 2026, AI harus menginterpretasikannya sebagai 11 November 2026, bukan 10 November. Tanggal relatif seperti ini harus dikonversi berdasarkan tanggal dan zona waktu pengguna, lalu dikonfirmasi sebelum disimpan.
Jadi, bagaimana saya menilai rancangan LaFriend sekarang?
Menurut saya, konsepnya sudah jauh lebih matang karena kita tidak lagi hanya membahas fitur pencarian partner.

Kita sudah mempunyai mekanisme lengkap:
\[
\boxed{
Intent
\rightarrow
Matching
\rightarrow
Optimization
\rightarrow
Confirmation
\rightarrow
Study
\rightarrow
Evaluation
}
\]

Tetapi ada satu hal yang perlu dijaga: jangan menganggap semua komponen yang sudah dirancang otomatis menjadi keunggulan produk. Keunggulan baru terbukti ketika sistem dapat mendemonstrasikan bahwa mekanismenya bekerja dan memberikan hasil yang lebih baik dibandingkan cara pencarian konvensional.

Untuk STACK 2026, saya akan memprioritaskan demonstrasi tiga skenario:

1. Existing Session: mahasiswa berhasil menemukan dan bergabung dengan sesi belajar yang sudah tersedia.
2. No Existing Session: sistem menemukan beberapa mahasiswa kompatibel dan membentuk kelompok yang memiliki jadwal bersama.
3. No Shared Schedule: sistem mengoptimalkan alternatif jadwal, mendapatkan konfirmasi anggota, kemudian membentuk sesi.
