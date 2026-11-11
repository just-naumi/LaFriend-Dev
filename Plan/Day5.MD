lanjut bro day 5
Siap bro! Kita lanjut ke Day 5 — Mekanisme Pencarian dan Pembentukan Kelompok Belajar (Session Matching & Partner Matching).

Menurut saya, Day 5 ini sangat penting karena ada satu hal yang belum diselesaikan pada Day 4.

Kemarin kita sudah membuat formula untuk menghitung kecocokan dua mahasiswa. Tetapi, LaFriend bukan hanya bertugas mencari dua orang yang cocok. LaFriend harus bisa membantu mahasiswa menemukan sesi belajar yang sudah tersedia atau membentuk kelompok baru yang seluruh anggotanya benar-benar bisa belajar bersama.

Jadi, hari ini kita akan merancang logika dari awal sampai terbentuknya Study Session.

DAY 5 — Session Matching & Group Formation

1. Menentukan dua jalur pencarian LaFriend
   Kita sudah menyepakati bahwa LaFriend memiliki dua jalur pencarian:

Session Matching: mencari sesi belajar yang sudah dibuat mahasiswa lain.

Partner Matching: mencari mahasiswa lain untuk membentuk kelompok belajar baru.

Urutannya harus seperti ini:

Sistem mencari sesi belajar yang sudah tersedia terlebih dahulu.

Jika tidak ada sesi yang memenuhi kebutuhan mahasiswa, sistem mencari calon teman belajar.

Jika ada calon yang cocok, sistem membantu proses pembentukan kelompok.

Kelompok baru dibuat menjadi Study Session setelah proses persetujuan selesai.

Kenapa harus mencari sesi yang sudah tersedia terlebih dahulu?

Karena kalau sudah ada kelompok yang membahas materi yang dibutuhkan mahasiswa, kita tidak perlu membuat kelompok baru dari nol.

2. Alur utama sistem
   Mahasiswa membuat Study Intent

Contoh: ingin belajar Binary Tree

Session Matching

Mencari Study Session yang sudah tersedia

Apakah ada sesi yang memenuhi syarat?

Ada
Tampilkan sesi

Mahasiswa mengajukan permintaan bergabung

Tidak ada
Partner Matching

Mencari mahasiswa yang cocok

Pemeriksaan kelayakan kelompok

Cek kecocokan dan jadwal seluruh anggota

Persetujuan seluruh anggota

Study Session CONFIRMED

Kelompok siap melaksanakan sesi belajar

Catatan: jika mahasiswa menemukan sesi yang cocok tetapi permintaan bergabung ditolak atau sesi sudah penuh, sistem boleh mengembalikan Study Intent ke proses pencarian Partner Matching. Jadi, jalur pertama tidak harus berakhir buntu.

3. Jalur pertama: Session Matching
   Misalnya Andi ingin belajar Binary Tree.

LaFriend menemukan tiga sesi yang sudah dibuat mahasiswa lain.

Sesi

Materi

Jadwal

Kapasitas

Session A

Binary Tree

Rabu, 10.00

2/4

Session B

Sorting

Rabu, 10.00

2/4

Session C

Binary Tree

Jumat, 14.00

4/4

Bagaimana sistem memutuskan?

Langkah 1 — Periksa mata kuliah.

Sesi harus membahas mata kuliah yang sama dengan Study Intent Andi.

Langkah 2 — Periksa materi.

Materi sesi harus relevan dengan kebutuhan Andi. Kita bisa menggunakan Topic Similarity dari Day 4.

Langkah 3 — Periksa jadwal.

Harus ada waktu sesi yang cocok dengan ketersediaan Andi.

Langkah 4 — Periksa kapasitas.

Sesi harus memiliki tempat kosong dan tidak melebihi batas anggota.

Langkah 5 — Hitung skor kecocokan.

Sesi yang lolos syarat wajib diurutkan berdasarkan kesesuaian materi, tujuan, jadwal, gaya belajar, dan metode.

Hasil contoh:

Hasil Session Matching

Session A — Binary Tree

Direkomendasikan
92/100
Masih tersedia 2 tempat dari kapasitas 4 anggota.

Session B: Gugur karena materinya tidak relevan.

Session C: Gugur karena sudah penuh.

Andi kemudian dapat mengajukan permintaan bergabung kepada host Session A.

Hal penting: Session Matching tidak langsung memasukkan Andi ke sesi. Host tetap harus menyetujui permintaannya.

4. Jalur kedua: Partner Matching
   Sekarang bagaimana jika tidak ada Study Session yang cocok?

LaFriend akan mencari mahasiswa lain yang juga memiliki Study Intent aktif.

Contoh:

Andi membuat permintaan belajar Binary Tree. Sistem menemukan:

Mahasiswa

Kebutuhan

Skor dengan Andi

Budi

Binary Tree

85

Citra

Binary Tree dan BST

90

Deni

Sorting

40

Setelah melewati Hard Constraint, Deni tidak ikut dipertimbangkan jika materi dan kebutuhan belajarnya memang tidak relevan menurut aturan yang ditetapkan.

Budi dan Citra menjadi calon anggota kelompok.

Namun, ada satu hal penting: jangan langsung mengambil dua orang dengan skor tertinggi tanpa memeriksa kecocokan mereka satu sama lain.

Kita sudah melihat masalah ini pada Day 4.

Andi mungkin cocok dengan Budi, dan Andi juga cocok dengan Citra. Tetapi belum tentu Budi cocok dengan Citra.

Karena itu, proses Partner Matching harus memiliki dua tahap:

Mencari kandidat yang cocok dengan mahasiswa pembuat Study Intent.

Memeriksa apakah kandidat-kandidat tersebut juga bisa membentuk kelompok yang layak.

5. Bagaimana menentukan anggota kelompok?
   Untuk PoC, saya menyarankan kita menggunakan pendekatan sederhana: Host-Based Group Formation.

Artinya, mahasiswa yang pertama kali membuat Study Intent menjadi calon host atau penginisiasi kelompok.

Contoh:

Andi membuat Study Intent.

Budi dan Citra ditemukan sebagai kandidat.

Andi menjadi penginisiasi kelompok.

LaFriend memeriksa apakah Andi, Budi, dan Citra bisa belajar bersama.

Kita tidak perlu membuat algoritma optimasi kelompok yang rumit terlebih dahulu.

Langkah 1 — Tentukan kebutuhan jumlah anggota
Misalnya Andi menginginkan kelompok berisi 2–4 orang.

Artinya:

Minimal 2 orang termasuk Andi.

Maksimal 4 orang termasuk Andi.

Sistem mencari kandidat sampai jumlah kelompok yang layak dapat dibentuk, tanpa harus selalu memenuhi kapasitas maksimum.

Langkah 2 — Urutkan calon anggota
Kandidat yang sudah lolos Hard Constraint diurutkan berdasarkan Compatibility Score terhadap Andi.

Misalnya:

Urutan

Kandidat

Skor dengan Andi

1

Citra

90

2

Budi

85

3

Deni

78

Ini hanya urutan awal. Belum berarti ketiganya otomatis dimasukkan.

Langkah 3 — Periksa kecocokan antaranggota
Misalnya:

Pasangan

Compatibility Score

Andi–Citra

90

Andi–Budi

85

Citra–Budi

75

Kelompok berisi tiga orang tersebut memiliki:

G
r
o
u
p
S
c
o
r
e
=
90

- 85
- 75
  3
  GroupScore=
  3
  90+85+75
  ​

G
r
o
u
p
S
c
o
r
e
=
83.33
GroupScore=83.33
Nilai tersebut memberikan gambaran kecocokan kelompok secara keseluruhan.

Saya juga menyarankan kita menyimpan nilai pasangan terendah sebagai informasi tambahan:

M
i
n
i
m
u
m
P
a
i
r
S
c
o
r
e
=
min
⁡
(
90
,
85
,
75
)
=
75
MinimumPairScore=min(90,85,75)=75
Kenapa?

Karena rata-rata yang tinggi bisa menyembunyikan satu pasangan yang sangat tidak cocok. Nilai terendah membantu kita melihat apakah ada hubungan antaranggota yang perlu diperhatikan.

Untuk PoC, kita gunakan GroupScore dan MinimumPairScore sebagai bahan evaluasi, bukan langsung membuat batas penolakan yang belum diuji.

6. Pemeriksaan jadwal seluruh anggota
   Ini adalah bagian yang paling penting dalam pembentukan kelompok.

Pada Day 4, kita menghitung kecocokan dua mahasiswa. Namun, kelompok harus memiliki waktu yang bisa digunakan oleh semua anggotanya.

Contoh:

Mahasiswa

Waktu tersedia

Andi

Rabu 09.00–12.00

Budi

Rabu 10.00–13.00

Citra

Rabu 11.00–14.00

Bagaimana menentukan jadwal kelompok?

Kita cari waktu yang sama-sama tersedia.

Irisan jadwal kelompok

Andi

09.00–12.00

Budi

10.00–13.00

Citra

11.00–14.00

Waktu bersama
11.00–12.00
Ketiganya tersedia pada jam tersebut.

Rumus sederhananya:

S
t
a
r
t
g
r
o
u
p
=
max
⁡
(
S
t
a
r
t
1
,
S
t
a
r
t
2
,
…
,
S
t
a
r
t
n
)
Start
group
​
=max(Start
1
​
,Start
2
​
,…,Start
n
​
)
E
n
d
g
r
o
u
p
=
min
⁡
(
E
n
d
1
,
E
n
d
2
,
…
,
E
n
d
n
)
End
group
​
=min(End
1
​
,End
2
​
,…,End
n
​
)
Kelompok memiliki waktu bersama jika:

E
n
d
g
r
o
u
p
−
S
t
a
r
t
g
r
o
u
p
≥
D
u
r
a
t
i
o
n
m
i
n
End
group
​
−Start
group
​
≥Duration
min
​

Untuk rancangan awal, kita gunakan durasi minimal 60 menit, sesuai asumsi PoC sebelumnya.

Pada contoh tadi:

12.00
−
11.00
=
60
menit
12.00−11.00=60 menit
Berarti kelompok memenuhi durasi minimum.

Tetapi kalau Citra hanya tersedia sampai pukul 10.30, kelompok tersebut tidak memiliki waktu bersama selama 60 menit. Kelompok harus mencari slot lain atau mengganti kandidat.

Kesimpulannya: jadwal harus diperiksa untuk seluruh anggota sekaligus, bukan hanya berdasarkan kecocokan host dengan masing-masing kandidat.

7. Bagaimana jika kandidat terbaik tidak cocok dengan anggota lain?
   Kita gunakan contoh berikut:

Kandidat

Skor dengan Andi

Skor dengan Budi

Jadwal kelompok

Citra

90

40

Cocok

Deni

85

80

Cocok

Eka

82

78

Tidak cocok

Kalau hanya mengurutkan berdasarkan skor dengan Andi, Citra akan menjadi kandidat pertama.

Namun, Citra memiliki skor 40 dengan Budi. Kita tidak boleh langsung menganggap kelompok Andi–Budi–Citra ideal.

Deni justru berpotensi membentuk kelompok yang lebih seimbang.

Untuk PoC, saya menyarankan aturan berikut:

Ambil kandidat berdasarkan skor terhadap host.

Tambahkan kandidat secara bertahap.

Periksa jadwal bersama seluruh anggota.

Hitung kecocokan seluruh pasangan.

Jika penambahan kandidat membuat kelompok tidak layak, jangan tambahkan kandidat tersebut.

Coba kandidat berikutnya.

Dengan pendekatan ini, kita tidak perlu menggunakan algoritma optimasi yang terlalu kompleks.

8. Bagaimana menentukan host kelompok?
   Untuk tahap awal, saya menyarankan:

Host adalah mahasiswa yang membuat Study Intent terlebih dahulu.

Alasannya:

Dia yang memulai kebutuhan belajar.

Dia yang menentukan tujuan awal kelompok.

Dia menjadi pihak yang menginisiasi undangan.

Proses sistem menjadi lebih sederhana.

Host bukan berarti paling pintar atau memiliki kemampuan akademik paling tinggi. Host hanya bertanggung jawab menginisiasi dan mengelola pembentukan sesi.

Untuk PoC, kita belum perlu membuat sistem pemilihan host otomatis.

9. Bagaimana proses persetujuan anggota?
   Setelah sistem menemukan kelompok yang layak, kelompok belum langsung berstatus CONFIRMED.

Contoh kelompok:

Andi sebagai host.

Budi sebagai calon anggota.

Citra sebagai calon anggota.

Prosesnya:

LaFriend membuat rancangan kelompok.

Andi melihat daftar calon anggota dan jadwal yang memungkinkan.

Andi mengirim undangan kepada Budi dan Citra.

Budi menerima atau menolak undangan.

Citra menerima atau menolak undangan.

Jika keduanya menerima, sistem meminta persetujuan jadwal.

Jika seluruh anggota menyetujui jadwal, Study Session dikonfirmasi.

Bagaimana jika salah satu menolak?

Misalnya Budi menerima, tetapi Citra menolak.

Maka:

Budi tetap menjadi calon anggota yang menerima.

Citra dikeluarkan dari rancangan kelompok.

Sistem memeriksa kembali apakah jumlah anggota masih memenuhi batas minimum.

Jika masih memenuhi, proses dapat dilanjutkan.

Jika tidak, Andi perlu mencari kandidat pengganti.

Untuk menjaga kesederhanaan PoC, kita tidak perlu mempertahankan kelompok yang belum memenuhi jumlah anggota minimum.

Status proses pembentukan kelompok
Kondisi

Status

Host membuat rancangan

DRAFT

Undangan dikirim

GROUP_FORMING

Anggota menyetujui undangan

CONFIRMATION_PENDING

Semua anggota menyetujui jadwal

CONFIRMED

Anggota tidak mencukupi

GROUP_FORMING atau kembali ACTIVE

Host membatalkan

CANCELLED

Status tersebut adalah gambaran alur bisnis. Kita tetap perlu menghubungkannya dengan lifecycle Study Intent, Study Session, dan Session Membership yang sudah dirancang pada Day 1 dan Day 2.

10. Bagaimana jika kelompok tidak berhasil terbentuk?
    Ini juga harus kita pikirkan.

Misalnya Andi sudah membuat Study Intent, tetapi:

Tidak ada kandidat yang cocok.

Kandidat menolak undangan.

Jadwal seluruh anggota tidak pernah bertemu.

Jumlah anggota tidak mencapai batas minimum.

Apa yang harus dilakukan LaFriend?

Menurut saya, Study Intent Andi jangan langsung dihapus.

Kita gunakan tiga kemungkinan:

Kondisi

Tindakan sistem

Belum menemukan kandidat

Intent tetap ACTIVE

Kandidat menolak

Cari kandidat lain

Intent melewati batas tanggal

Status EXPIRED

Dengan begitu, mahasiswa tidak perlu mengulang pengisian Study Intent dari awal setiap kali proses pencarian gagal.

Kita juga perlu mencegah satu Study Intent membuat banyak proses pembentukan kelompok yang berjalan bersamaan. Untuk PoC, satu intent hanya boleh memiliki satu proses pembentukan kelompok aktif pada satu waktu.

11. Pseudocode logika utama LaFriend
    Sekarang kita rangkum seluruh rancangan menjadi logika yang nantinya dapat diterjemahkan ke Python atau JavaScript.

Berikut versi sederhana agar alurnya mudah dipahami:

def process_study_intent(intent):

    # 1. Cari sesi belajar yang sudah tersedia
    sessions = find_existing_sessions(intent)

    # 2. Buang sesi yang tidak memenuhi syarat
    valid_sessions = []

    for session in sessions:
        if not pass_session_constraints(intent, session):
            continue

        score = calculate_session_score(intent, session)

        valid_sessions.append({
            "session": session,
            "score": score
        })

    # 3. Jika ada sesi yang cocok
    if valid_sessions:
        return sorted(
            valid_sessions,
            key=lambda x: x["score"],
            reverse=True
        )

    # 4. Jika tidak ada sesi, cari calon teman belajar
    candidates = find_active_student_intents(intent)

    valid_candidates = []

    for candidate in candidates:
        if not pass_pair_constraints(intent, candidate):
            continue

Perlu dicatat, ini pseudocode untuk menjelaskan alur, belum kode siap produksi. Fungsi seperti build_feasible_group() masih harus kita definisikan secara rinci pada tahap implementasi.

12. Apakah rancangan database Day 2 perlu berubah?
    Ada beberapa penyesuaian kecil yang saya sarankan agar proses Day 5 bisa didukung database.

Tabel

Penyesuaian

study_intents

Tambahkan group_process_status jika diperlukan untuk melacak proses pembentukan

study_sessions

Tambahkan session_topic dan informasi tujuan sesi

session_slots

Menyimpan kandidat tanggal dan waktu sesi

session_members

Menyimpan status undangan, penerimaan, dan konfirmasi anggota

invitations

Menyimpan pengirim, penerima, intent tujuan, dan status undangan

match_results

Menyimpan skor, rincian faktor, dan penjelasan rekomendasi

Satu catatan desain: kita tidak perlu menambah tabel khusus Group Formation dulu. Proses pembentukan kelompok dapat dikelola menggunakan entitas yang sudah ada selama satu proses aktif per intent bisa dijamin dan statusnya tercatat dengan baik.

Namun, jika nanti satu intent bisa menjalankan beberapa percobaan kelompok secara paralel atau kita perlu menyimpan riwayat setiap percobaan, tabel khusus untuk group_formation_attempts akan lebih tepat.

13. Keputusan akhir Day 5
    Bro, berikut keputusan desain yang saya rekomendasikan untuk LaFriend.

No.

Keputusan

Status

1

Session Matching dilakukan terlebih dahulu

Tetapkan

2

Partner Matching berjalan jika tidak ada sesi yang layak

Tetapkan

3

Host adalah pembuat Study Intent

Tetapkan

4

Kandidat diurutkan menggunakan Compatibility Score

Tetapkan

5

Kecocokan seluruh pasangan anggota diperiksa

Tetapkan

6

Jadwal harus memiliki irisan untuk seluruh anggota

Tetapkan

7

Jumlah kelompok awal 2–4 orang

Asumsi PoC

8

Durasi minimal sesi 60 menit

Asumsi PoC

9

Kelompok tidak dikonfirmasi secara otomatis

Tetapkan

10

Intent tetap aktif jika pencarian belum berhasil

Tetapkan

Hasil yang sudah kita miliki
Fondasi sistem LaFriend

Day 1–5
Day 1 — Business Logic: menentukan fungsi, aktor, dan aturan LaFriend.

Day 2 — Database Design: menentukan tabel dan hubungan data.

Day 3 — Study Intent: menentukan input mahasiswa dan parameter matching.

Day 4 — Compatibility Score: merancang formula kecocokan mahasiswa.

Day 5 — Group Formation: merancang pencarian sesi dan pembentukan kelompok.

14. Berikutnya: Day 6 — Menyatukan seluruh algoritma
    Menurut saya, Day 6 sebaiknya menjadi tahap untuk menyatukan semua yang sudah kita buat.

Kita akan merancang:

Alur algoritma LaFriend secara keseluruhan dari mahasiswa membuat Study Intent sampai sesi selesai.

Urutan pemanggilan setiap proses matching.

Hubungan antara Session Matching, Partner Matching, Compatibility Score, dan Group Formation.

Penanganan kasus khusus: kandidat tidak tersedia, jadwal berubah, undangan ditolak, sesi penuh, dan intent kedaluwarsa.

Pseudocode lengkap yang menjadi acuan implementasi backend.

Target Day 6: kita sudah mempunyai satu rancangan algoritma utuh yang bisa diterjemahkan menjadi kode, bukan lagi kumpulan formula dan aturan yang berdiri sendiri.

Menurut saya, jangan mulai coding matching engine sebelum alur utuh ini selesai. Dengan begitu, kita mengurangi risiko harus membongkar ulang logika ketika backend sudah terlanjur dibuat.
