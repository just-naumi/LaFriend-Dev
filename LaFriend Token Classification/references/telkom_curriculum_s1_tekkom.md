# Domain Knowledge: S1 Teknik Komputer (Fakultas Teknik Elektro - Telkom University)

Dokumen ini memetakan kurikulum resmi, mata kuliah, sub-bab materi, dan kosakata mahasiswa Telkom University untuk keperluan pelatihan model **Token Classification / Span NER (GLiNER)** pada platform **LaFriend**.

---

## 1. Daftar Mata Kuliah & Silabus Sub-Bab Materi

| No | Kode MK | Nama Mata Kuliah | Singkatan / Alias Gaul | Sub-Bab / Topik Materi Spesifik |
|---|---|---|---|---|
| 1 | **TC2043** | **Struktur Data** | *strukdat* | Singly & Doubly Linked List, Stack dan Queue, Binary Search Tree (BST), AVL Tree, Red-Black Tree, Heap Sort & Priority Queue, Graph Traversal (BFS & DFS), Shortest Path Dijkstra, Hash Table & Hashing Collision |
| 2 | **TC1023** | **Algoritma dan Pemrograman** | *alpro*, *algoritma* | Struktur Kontrol & Percabangan If-Else, Looping For/While/Do-While, Fungsi & Prosedur Parameter By Value/Reference, Rekursif, Array 1D & 2D, Linear & Binary Searching, Sorting (Bubble, Selection, Insertion, Merge Sort), Pointer C/C++ |
| 3 | **TC2033** | **Basis Data** | *basdat* | Konseptual & Logical Data Model, Desain ERD (Entity Relationship Diagram), Relational Model, Normalisasi 1NF sampai BCNF, DDL & DML SQL, Query JOIN (Inner, Left, Right), Subquery & Aggregation (GROUP BY, HAVING), Indexing & Transaksi ACID |
| 4 | **TC3023** | **Sistem Operasi** | *sisop* | Process & Thread Management, CPU Scheduling (FCFS, SJF, Round Robin), Inter-process Communication (IPC), Sinkronisasi Process & Semaphore, Mutex & Critical Section, Deadlock Avoidance (Banker's Algorithm), Memory Paging & Segmentation, Virtual Memory Page Replacement (FIFO, LRU), File System |
| 5 | **TC3013** | **Jaringan Komputer** | *jarkom* | Model OSI 7 Layer & TCP/IP, IP Addressing & Subnetting IPv4/VLSM, Static & Dynamic Routing (OSPF, RIP), Switching & VLAN, Protokol Transport TCP vs UDP 3-Way Handshake, DNS, DHCP, HTTP/HTTPS, Analisis Paket Wireshark, Simulasi Cisco Packet Tracer |
| 6 | **TC2023** | **Organisasi dan Arsitektur Komputer** | *orkom*, *arkom* | Arsitektur Von Neumann vs Harvard, Register & ALU, Instruksi Mesin MIPS, Instruction Pipeline & Hazard, Cache Memory (Direct, Associative, Hit/Miss), Main Memory RAM/ROM, I/O Interfacing & Interrupt, Bus System |
| 7 | **TC1043** | **Sistem Digital** | *sisdig* | Sistem Bilangan Biner & Heksadesimal, Gerbang Logika Dasar & Universal (NAND/NOR), Aljabar Boolean, Karnaugh Map (K-Map), Rangkaian Kombinasional (Multiplexer, Decoder, Adder, ALU), Rangkaian Sekuensial (Flip-Flop JK/D/T), Register & Counter, Perancangan VHDL / Verilog |
| 8 | **TC3033** | **Sistem Mikroprosesor** | *sismin*, *mikroprosesor*, *mikrokontroler* | Arsitektur Mikroprosesor x86 / 8086, Arsitektur Mikrokontroler AVR ATMega / ARM Cortex, Pemrograman Assembly, GPIO Input/Output, Timer & Counter, External Interrupt, Komunikasi Serial UART/USART, ADC & DAC, Interfacing Sensor & Motor Driver |
| 9 | **TC3043** | **Sistem Tertanam** | *sisbed*, *embedded* | Real-Time Operating System (RTOS), Task Scheduling & Priority Inversion, FreeRTOS, Pemrograman Mikrokontroler STM32 / ESP32, Protokol Bus I2C & SPI, Low Power Modes & Watchdog Timer, Hardware-in-the-Loop (HIL) |
| 10 | **TC2013** | **Matematika Diskrit** | *matdis* | Logika Matematika & Tabel Kebenaran, Teori Himpunan, Relasi Ekuivalensi & Fungsi, Induksi Matematika, Teori Graf (Pohon Rentang Minimum Kruskal/Prim, Euler, Hamilton), Kombinatorika & Permutasi, Aljabar Boolean |
| 11 | **TC1013** | **Kalkulus** | *kalkulus*, *kalkul* | Limit Fungsi & Kekontinuan, Turunan & Aturan Rantai, Aplikasi Turunan (Maksimum/Minimum, L'Hopital), Integral Tak Tentu & Teknik Substitusi/Parsial, Integral Tentu & Luas Daerah, Volume Benda Putar, Barisan & Deret Tak Hingga |
| 12 | **TC4013** | **Internet of Things** | *iot* | Arsitektur IoT 3-Tier, Protokol MQTT, CoAP, HTTP, Sensor Interfacing ESP8266/ESP32, Cloud IoT Dashboard (ThingsBoard, Blynk, AWS IoT), Edge Computing & Gateway, Keamanan Komunikasi IoT |

---

## 2. Pemetaan Kosakata 6 Entitas Target

### A. `course` (Nama Mata Kuliah & Singkatan Kampus)
- *Struktur Data, Basis Data, Algoritma Pemrograman, Sistem Operasi, Jaringan Komputer, Organisasi dan Arsitektur Komputer, Sistem Digital, Sistem Mikroprosesor, Sistem Tertanam, Matematika Diskrit, Kalkulus, Internet of Things*
- *strukdat, basdat, alpro, sisop, jarkom, orkom, arkom, sisdig, sismin, sisbed, embedded, matdis, kalkul, iot, mikrokontroler*

### B. `topic` (Sub-Bab Topik Materi Belajar)
- Frasa topik spesifik yang dipelajari mahasiswa pada mata kuliah di atas (misal: *Binary Tree, AVL Tree, Normalisasi 1NF sampai BCNF, Desain ERD, Subquery JOIN, CPU Scheduling Round Robin, Deadlock Banker's Algorithm, Subnetting IPv4 VLSM, VLAN Cisco, K-Map, Flip-Flop JK, Pemrograman Assembly 8086, FreeRTOS STM32, Induksi Matematika, Integral Parsial, MQTT ESP32*).

### C. `exam_prep` (Target Evaluasi & Ujian Akademik Telkom University)
- *persiapan UAS, persiapan UTS, kuis praktikum, tes awal lab, jurnal praktikum, responsi lab, pengerjaan tubes (tugas besar), persiapan ujian akhir semester, persiapan ujian tengah semester, asessment 1, asessment 2, remedial, kuis minggu depan, tugas mingguan, kuis teori*

### D. `schedule` (Jadwal & Waktu Belajar Mahasiswa)
- **Hari**: *Senin, Selasa, Rabu, Kamis, Jumat, Sabtu, Minggu, weekend, hari kerja*
- **Jam / Waktu Spesifik**: *jam 9 sampai 12, pukul 13:00 - 15:00, jam 10 pagi, abis ashar, abis maghrib, siang jam 1 sampai 3, sore jam 4-6, malam jam 7 sampai 9, pagi jam 8, jam kosong kuliah, pas jeda kelas kuliah*

### E. `group_size` (Jumlah Anggota Kelompok)
- *bareng 2 sampai 4 orang, kelompok 3 orang, berdua aja, bertiga, berempat, maksimal 4 mahasiswa, butuh 2 orang lagi, cari partner 1 orang, rame-rame 3-4 orang, belajar berdua, kelompok 2-3 orang*

### F. `study_mode` (Spot Lokasi Telkom University & Mode Belajar)
- **Spot Kampus Tel-U**: *tatap muka di Open Library, nongkrong di Mezzanine Oplib, Discussion Room Open Library Lt 5, TULT lantai 5, selasar FTE, selasar Gd B Cacuk, MSU Manterawu, selasar Lab Komputer, kantin TULT*
- **Kawasan Hunian Mahasiswa**: *kosan Sukabirus, kosan Sukapura, cafe Sukabirus, daerah PGA*
- **Online / Hybrid**: *online via Google Meet, online Discord, Zoom meeting, hybrid bebas, bisa online bisa offline*

