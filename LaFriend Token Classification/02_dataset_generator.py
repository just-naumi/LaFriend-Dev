"""
==============================================================================
02_dataset_generator.py - Pembuat Dataset Span-Level NER / Entity Extraction LaFriend
Domain Fokus: S1 Teknik Komputer - Semester 1 s/d 8 (Telkom University)
==============================================================================
Pembaruan Sesuai Feedback Revisi:
1. Taxonomy Label Terstandarisasi 100% Konsisten:
   ["course", "topic", "learning_goal", "schedule", "group_size", "study_mode"]
2. Pemisahan Total Template Training vs Validation:
   - Template Validasi menggunakan struktur sintaks dan kosakata yang berbeda
     untuk benar-benar menguji generalisasi model terhadap unseen sentence patterns.
3. Zero-Ambiguity Exact Offset Generation:
   - Menggantikan fungsi 'text.find()' dengan token-stream construction.
   - Posisi karakter start & end dihitung secara deterministik saat perakitan string,
     menghilangkan 100% resiko kesalahan anotasi akibat kemunculan ganda sebuah kata.
==============================================================================
"""

import re
import json
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

# Kurikulum Lengkap Semester 1 s/d 8 S1 Teknik Komputer Telkom University
COURSES_DATA = [
    # --- SEMESTER 1 ---
    {
        "semester": 1,
        "name": "Kalkulus 1",
        "aliases": ["kalkulus 1", "kalkul 1", "kalkulus"],
        "topics": [
            "Limit Fungsi dan Kekontinuan", "Aturan Rantai Turunan", "Turunan Implisit",
            "Teorema L'Hopital", "Garis Singgung Kurva", "Titik Ekstrim Maksimum Minimum",
            "Uji Turunan Pertama dan Kedua"
        ]
    },
    {
        "semester": 1,
        "name": "Fisika 1",
        "aliases": ["fisika 1", "fisdas 1", "fisika dasar 1"],
        "topics": [
            "Kinematika Gerak 2D", "Hukum Newton tentang Gerak", "Usaha dan Energi Mekanik",
            "Momentum Linier dan Tumbukan", "Dinamika Rotasi dan Torsi", "Momen Inersia Benda Tegar",
            "Mekanika Fluida Statis Dinamis"
        ]
    },
    {
        "semester": 1,
        "name": "Kimia",
        "aliases": ["kimia", "kimia dasar"],
        "topics": [
            "Konfigurasi Elektron Atom", "Ikatan Kovalen dan Logam", "Stoikiometri Reaksi",
            "Termokimia", "Elektrokimia Sel Volta", "Material Semikonduktor Silikon"
        ]
    },
    {
        "semester": 1,
        "name": "Pengenalan Teknik Komputer",
        "aliases": ["ptk", "pengenalan tekkom", "pengantar teknik komputer"],
        "topics": [
            "Arsitektur CPU Memory IO", "Representasi Data Biner", "Taksonomi Sistem Komputer",
            "Pengenalan Embedded System", "Pengenalan Internet of Things", "Etika Rekayasa Komputer"
        ]
    },
    {
        "semester": 1,
        "name": "Logika Matematika",
        "aliases": ["logmat", "logika matematika", "discrete logic"],
        "topics": [
            "Proposisi dan Tabel Kebenaran", "Ekuivalensi Logis Hukum De Morgan", "Kuantor Universal Eksistensial",
            "Metode Pembuktian Langsung Kontradiksi", "Aljabar Boolean Penyederhanaan Logika", "Gerbang Logika Dasar"
        ]
    },
    {
        "semester": 1,
        "name": "Pengantar Rekayasa dan Desain",
        "aliases": ["prd", "rekayasa dan desain", "pengantar rekayasa"],
        "topics": [
            "Engineering Design Process", "Identifikasi Kebutuhan Pengguna", "Brainstorming Konsep Solusi",
            "Rapid Prototyping Pembuatan Mockup", "Analisis Kelayakan Teknis", "Presentasi Pitching Rekayasa"
        ]
    },

    # --- SEMESTER 2 ---
    {
        "semester": 2,
        "name": "Kalkulus 2",
        "aliases": ["kalkulus 2", "kalkul 2"],
        "topics": [
            "Teknik Integrasi Parsial", "Integrasi Pecahan Parsial", "Integral Tak Wajar",
            "Deret Tak Hingga Uji Konvergensi", "Deret Taylor dan Maclaurin", "Persamaan Parametrik Koordinat Polar"
        ]
    },
    {
        "semester": 2,
        "name": "Fisika 2",
        "aliases": ["fisika 2", "fisdas 2", "fisika dasar 2"],
        "topics": [
            "Hukum Coulomb Medan Listrik", "Hukum Gauss Fluks Listrik", "Potensial Listrik dan Kapasitansi",
            "Arus Hambatan Hukum Ohm", "Medan Magnet Hukum Biot Savart", "Induksi Elektromagnetik Hukum Faraday",
            "Rangkaian Arus Bolak Balik RLC"
        ]
    },
    {
        "semester": 2,
        "name": "Algoritma Pemrograman",
        "aliases": ["alpro", "algoritma pemrograman", "algoritma dan pemrograman"],
        "topics": [
            "Tipe Data Variabel Ekspresi C++", "Percabangan If Else Switch Case", "Perulangan For While Do While",
            "Fungsi Modularitas Pass by Reference", "Array 1 Dimensi dan 2 Dimensi", "Pointer dan Alokasi Memori Dinamis",
            "Rekursi Fibonacci Faktorial", "Sorting Bubble Selection Insertion", "Searching Linear Binary Search"
        ]
    },
    {
        "semester": 2,
        "name": "Matematika Diskrit",
        "aliases": ["matdis", "matematika diskrit", "discrete math"],
        "topics": [
            "Teori Himpunan Kardinalitas", "Relasi Refleksif Simetris Transitif", "Fungsi Injektif Surjektif Bijektif",
            "Prinsip Induksi Matematika", "Kombinatorika Permutasi Kombinasi", "Pigeonhole Principle",
            "Teori Graf Derajat Pohon Merentang Spanning Tree"
        ]
    },
    {
        "semester": 2,
        "name": "Jaringan Komputer dan Data",
        "aliases": ["jarkom data", "jaringan data", "pengantar jaringan"],
        "topics": [
            "Model Referensi OSI 7 Layer TCP IP", "Transmisi Media Fisik Guided Unguided", "Framing Data Link Error Detection CRC",
            "Subnetting IPv4 CIDR VLSM", "Protokol ARP ICMP Ping Traceroute", "Dasar Routing Statis Dinamis"
        ]
    },

    # --- SEMESTER 3 ---
    {
        "semester": 3,
        "name": "Struktur Data",
        "aliases": ["strukdat", "struktur data", "data structures"],
        "topics": [
            "Single dan Double Linked List", "Stack LIFO Evaluasi Polisi Posfix", "Queue FIFO Circular Queue Deque",
            "Binary Tree Traversal Inorder Preorder Postorder", "Binary Search Tree BST Search Insert Delete",
            "AVL Tree Self Balancing Rotation", "Heap Priority Queue HeapSort", "Graph Adjacency List BFS DFS",
            "Algoritma Djikstra Shortest Path", "Hash Table Collision Resolution Chaining Open Addressing"
        ]
    },
    {
        "semester": 3,
        "name": "Keamanan Jaringan",
        "aliases": ["kamjar", "keamanan jaringan", "network security"],
        "topics": [
            "Kriptografi Simetris AES DES", "Kriptografi Asimetris RSA ECC", "Hash Function MD5 SHA Digital Signature",
            "Firewall Packet Filtering Stateful Inspection", "Intrusion Detection System Snort",
            "Virtual Private Network OpenVPN WireGuard", "Analisis Paket Wireshark Network Forensics"
        ]
    },
    {
        "semester": 3,
        "name": "Rangkaian Listrik",
        "aliases": ["rl", "rangkaian listrik", "electric circuits"],
        "topics": [
            "Hukum Kirchhoff KCL KVL", "Metode Analisis Node dan Mesh", "Teorema Thevenin dan Norton",
            "Superposisi dan Transfer Daya Maksimum", "Rangkaian Transien Orde Satu RC RL",
            "Rangkaian Orde Dua RLC Seri Paralel", "Analisis Fasor Daya Nyata Reaktif Kompleks"
        ]
    },
    {
        "semester": 3,
        "name": "Persamaan Diferensial",
        "aliases": ["pdl", "persamaan diferensial", "pers diff"],
        "topics": [
            "PD Orde Satu Variabel Terpisah", "PD Linier Faktor Integrasi", "PD Eksak dan Faktor Pengali",
            "PD Linier Homogen Non Homogen Orde Dua", "Metode Koefisien Tak Tentu Variasi Parameter",
            "Transformasi Laplace Aplikasi Rangkaian Listrik"
        ]
    },
    {
        "semester": 3,
        "name": "Probabilitas dan Statistika",
        "aliases": ["probstat", "probabilitas dan statistika", "statistika"],
        "topics": [
            "Ruang Sampel Probabilitas Bersyarat Teorema Bayes", "Variabel Acak Diskrit Kontinu",
            "Distribusi Binomial Poisson Normal Gaussian", "Nilai Harapan Ekspektasi Variansi",
            "Central Limit Theorem", "Uji Hipotesis Nilai Rata-rata Uji T Z"
        ]
    },
    {
        "semester": 3,
        "name": "Aljabar Linier",
        "aliases": ["alin", "aljabar linier", "linear algebra"],
        "topics": [
            "Sistem Persamaan Linier Eliminasi Gauss Jordan", "Operasi Matriks Determinan Invers",
            "Ruang Vektor Subruang Kombinasi Linier", "Basis dan Dimensi Ruang Vektor",
            "Transformasi Linier Matriks Transformasi", "Eigenvalue Eigenvector Diagonalisasi Matriks",
            "Dekomposisi Nilai Singular SVD"
        ]
    },

    # --- SEMESTER 4 ---
    {
        "semester": 4,
        "name": "Sistem Digital",
        "aliases": ["sisdig", "sistem digital", "teknik digital"],
        "topics": [
            "Penyederhanaan Peta Karnaugh K-Map", "Rangkaian Kombinasional Adder Mux Demux Decoder",
            "Latch dan Flip Flop SR D JK T", "Register Shift Register Penghitung Counter",
            "Finite State Machine FSM Mealy Moore", "Hardware Description Language VHDL Verilog Dasar"
        ]
    },
    {
        "semester": 4,
        "name": "Elektronika",
        "aliases": ["elka", "elektronika", "elektronika analog"],
        "topics": [
            "Karakteristik Dioda P-N Rectifier", "Bipolar Junction Transistor BJT Bias Karakteristik",
            "MOSFET Penguat Pengalih Switching", "Operational Amplifier Op-Amp Inverting Non-Inverting",
            "Filter Aktif Low Pass High Pass", "Rangkaian Regulator Tegangan Linier Switching"
        ]
    },
    {
        "semester": 4,
        "name": "Komputasi Awan",
        "aliases": ["cloud", "komputasi awan", "cloud computing"],
        "topics": [
            "Model Layanan IaaS PaaS SaaS", "Arsitektur Virtualisasi Hypervisor KVM",
            "Containerisasi Docker Dockerfile Container Runtime", "Orkestrasi Container Kubernetes Pods Deployment",
            "Cloud Storage S3 Object Storage", "Serverless Computing AWS Lambda Cloud Function"
        ]
    },
    {
        "semester": 4,
        "name": "Pengolahan Sinyal Waktu Kontinu",
        "aliases": ["sinyal kontinu", "pengolahan sinyal", "sinyal dan sistem"],
        "topics": [
            "Klasifikasi Sinyal Periodik Energi Daya", "Sistem Linier Tak Ubah Waktu LTI Konvolusi Kontinu",
            "Deret Fourier Sinyal Periodik", "Transformasi Fourier Sinyal Waktu Kontinu FT",
            "Respon Frekuensi Filter Analog", "Sampling Teorema Nyquist Rekonstruksi Sinyal"
        ]
    },
    {
        "semester": 4,
        "name": "Analisis dan Desain Sistem",
        "aliases": ["ads", "analisis dan desain sistem", "analisis desain"],
        "topics": [
            "Analisis Kebutuhan Fungsional Non Fungsional", "Pemodelan Use Case Diagram Activity Diagram",
            "Class Diagram Sequence Diagram", "Arsitektur Sistem Microservices Monolith",
            "Desain Database Konseptual Logikal ERD", "Perancangan Antarmuka UI UX Wireframing"
        ]
    },
    {
        "semester": 4,
        "name": "Perancangan Catu Daya",
        "aliases": ["catu daya", "power supply", "perancangan catu daya"],
        "topics": [
            "Penyearah Gelombang Penuh Trafo", "Filter Kapasitor Ripple Voltage",
            "Linear Voltage Regulator 78XX LM317", "Switch Mode Power Supply SMPS Buck Boost Converter",
            "Manajemen Baterai BMS Charging Discharging", "Proteksi Overvoltage Overcurrent Thermal"
        ]
    },

    # --- SEMESTER 5 ---
    {
        "semester": 5,
        "name": "Organisasi dan Arsitektur Komputer",
        "aliases": ["orkom", "arkom", "arsitektur komputer"],
        "topics": [
            "Instruction Set Architecture ISA RISC vs CISC", "Format Instruksi Bahasa Assembly MIPS x86",
            "Datapath Single Cycle Multi Cycle", "Pipelining Hazard Data Control Structural",
            "Hierarki Memori Cache Mapping Hit Rate Miss Penalty", "Virtual Memory Paging TLB Translation",
            "Bus System Interkoneksi Peripheral PCI PCIe"
        ]
    },
    {
        "semester": 5,
        "name": "Sistem Mikroprosesor",
        "aliases": ["sismin", "sistem mikroprosesor", "mikroprosesor", "mikrokontroler"],
        "topics": [
            "Arsitektur Mikrokontroler ARM Cortex STM32 ESP32", "Interfacing GPIO Input Output Button LED",
            "Analog to Digital Converter ADC DAC Sampling", "Timer Counter PWM Motor Control",
            "Komunikasi Serial UART I2C SPI", "Interrupt Service Routine ISR Eksternal Internal"
        ]
    },
    {
        "semester": 5,
        "name": "Basis Data",
        "aliases": ["basdat", "basis data", "database"],
        "topics": [
            "Model Relasional Skema Tabel Kunci Relasi", "Normalisasi Database 1NF 2NF 3NF BCNF",
            "SQL DDL DML DCL Query Kompleks Join Subquery", "Indexing B-Tree Query Optimization",
            "Transaksi Database ACID Concurrency Control Locking", "NoSQL Document Store MongoDB Redis Cache"
        ]
    },
    {
        "semester": 5,
        "name": "Sistem Jaringan Lanjut",
        "aliases": ["jarkom lanjut", "jaringan lanjut", "routing switching"],
        "topics": [
            "Protokol Routing Dinamis OSPF Single Multi Area", "Border Gateway Protocol BGP Interdomain Routing",
            "Virtual LAN VLAN Trunking Inter VLAN Routing", "Spanning Tree Protocol STP RSTP Loop Prevention",
            "Network Address Translation NAT PAT Port Forwarding", "Software Defined Networking SDN OpenFlow Arsitektur"
        ]
    },
    {
        "semester": 5,
        "name": "Pengolahan Sinyal Digital",
        "aliases": ["dsp", "pengolahan sinyal digital", "sinyal digital"],
        "topics": [
            "Transformasi Fourier Diskrit DFT dan FFT", "Transformasi-Z Region of Convergence ROC",
            "Perancangan Filter Digital Finite Impulse Response FIR", "Perancangan Filter Infinite Impulse Response IIR",
            "Kuantisasi Efek Panjang Kata Terbatas", "Implementasi Real Time DSP Audio Filtering"
        ]
    },

    # --- SEMESTER 6 ---
    {
        "semester": 6,
        "name": "Sistem Tertanam",
        "aliases": ["sisbed", "sistem tertanam", "embedded system"],
        "topics": [
            "Real Time Operating System RTOS FreeRTOS Task Scheduling", "Sinkronisasi Task Semaphore Mutex Queue",
            "Device Driver Development SPI I2C Sensor Interfacing", "Power Optimization Sleep Modes Low Power IoT",
            "Protokol IoT MQTT CoAP HTTP REST", "Over The Air OTA Firmware Update ESP32",
            "Hardware Software Co-Design Pembuatan PCB Kicad"
        ]
    },
    {
        "semester": 6,
        "name": "Sistem Operasi",
        "aliases": ["sisop", "sistem operasi", "operating system"],
        "topics": [
            "Manajemen Proses PCB Thread Multithreading", "Algoritma Penjadwalan CPU FCFS SJF Round Robin",
            "Sinkronisasi Proses Critical Section Peterson Semaphor", "Deadlock Prevention Avoidance Banker Algorithm",
            "Manajemen Memori Paging Segmentasi Page Replacement LRU", "Sistem Berkas File System NTFS EXT4 Inode Structure"
        ]
    },
    {
        "semester": 6,
        "name": "Kecerdasan Buatan",
        "aliases": ["ai", "kecerdasan buatan", "artificial intelligence", "ml"],
        "topics": [
            "Algoritma Pencarian A Star Minimax Alpha Beta Pruning", "Supervised Learning Regresi Linier Logistik",
            "Klasifikasi Decision Tree Random Forest SVM", "Unsupervised Learning K-Means Clustering PCA",
            "Dasar Artificial Neural Network Backpropagation", "Evaluasi Model Confusion Matrix Precision Recall F1"
        ]
    },
    {
        "semester": 6,
        "name": "Sistem Kendali dan Robotika",
        "aliases": ["robotika", "sistem kendali", "kontrol sistem"],
        "topics": [
            "Pemodelan Matematis Sistem Fisik State Space", "Pengendali PID Proportional Integral Derivative Tuning",
            "Kinematika Robot Forward Inverse Kinematics DH Parameter", "Sensor Robotika IMU Lidar Ultrasonik Odometri",
            "Robot Operating System ROS Nodes Topics Services", "Algoritma Navigasi Lokalisasi SLAM Gmapping"
        ]
    },

    # --- SEMESTER 7 & 8 ---
    {
        "semester": 7,
        "name": "Manajemen Proyek TI",
        "aliases": ["manpro", "manajemen proyek", "it project management"],
        "topics": [
            "Metodologi Agile Scrum Sprint Planning Daily Standup", "Work Breakdown Structure WBS Gantt Chart",
            "Estimasi Biaya Waktu Critical Path Method CPM", "Manajemen Risiko Mitigasi Proyek TI",
            "Quality Assurance Software Testing Standar ISO", "Project Closure Evaluasi Post Mortem"
        ]
    },
    {
        "semester": 7,
        "name": "Keamanan Sistem Komputer",
        "aliases": ["kamsis", "keamanan sistem", "system security"],
        "topics": [
            "Access Control DAC MAC RBAC", "Kerentanan Buffer Overflow Stack Smashing", "Analisis Malware Statis Dinamis",
            "Reverse Engineering Ghidra GDB", "Vulnerability OWASP SQL Injection XSS", "Penetration Testing Nmap Metasploit"
        ]
    },
    {
        "semester": 7,
        "name": "Proposal Tugas Akhir",
        "aliases": ["pra-ta", "proposal ta", "seminar proposal"],
        "topics": [
            "Perumusan Masalah Penelitian", "Studi Literatur State of The Art", "Perancangan Metodologi Sistem",
            "Parameter Validasi Hasil Uji", "Penulisan Proposal Standar IABEE"
        ]
    },
    {
        "semester": 8,
        "name": "Tugas Akhir",
        "aliases": ["ta", "tugas akhir", "skripsi"],
        "topics": [
            "Implementasi Rancang Bangun Sistem Komputer", "Pengujian Kinerja Throughput Latency Akurasi",
            "Analisis Data Pengujian Laboratorium", "Penulisan Buku Tugas Akhir", "Publikasi Artikel Ilmiah",
            "Sidang Sarjana Yudisium"
        ]
    },

    # --- PEMINATAN KHUSUS ---
    {
        "semester": "Pilihan",
        "name": "Pembelajaran Mendalam",
        "aliases": ["deep learning", "dl", "pembelajaran mendalam"],
        "topics": [
            "Convolutional Neural Network CNN", "Klasifikasi Citra Deteksi Objek", "Recurrent Neural Network LSTM",
            "Arsitektur Transformer Self-Attention", "Framework PyTorch TensorFlow", "Model Quantization Pruning"
        ]
    },
    {
        "semester": "Pilihan",
        "name": "Komputer Forensik",
        "aliases": ["komputer forensik", "digital forensics", "forensik digital"],
        "topics": [
            "Digital Evidence Acquisition", "File System Forensics NTFS EXT", "Volatile Memory Volatility",
            "Network Packet Forensics", "Chain of Custody Barang Bukti"
        ]
    },
    {
        "semester": "Pilihan",
        "name": "DevSecOps",
        "aliases": ["devsecops", "developer security operations"],
        "topics": [
            "CI CD Pipeline Security Integration", "Static Application Security Testing SAST",
            "Dynamic Security Testing DAST", "Secrets Management Kredensial", "Container Security Hardening"
        ]
    },
    {
        "semester": "Pilihan",
        "name": "Perancangan Sistem VLSI",
        "aliases": ["vlsi", "perancangan vlsi", "desain fpga"],
        "topics": [
            "Arsitektur FPGA Xilinx Altera", "Sintesis Hardware VHDL Verilog", "Pipelining Hardware Sirkuit Digital",
            "Simulasi Timing ModelSim", "Implementasi SoC FPGA"
        ]
    },
    {
        "semester": "Pilihan",
        "name": "Teknologi Big Data",
        "aliases": ["big data", "teknologi big data"],
        "topics": [
            "Ekosistem Hadoop HDFS", "MapReduce Programming Model", "Apache Spark Dataframe RDD",
            "Streaming Data Apache Kafka", "Data Warehouse dan Data Lake"
        ]
    }
]

# Entitas Tujuan Belajar (learning_goal)
LEARNING_GOALS = [
    "persiapan UAS", "persiapan UTS", "kuis praktikum", "responsi lab",
    "asessment 1", "asessment 2", "tes awal praktikum", "ujian susulan",
    "latihan soal", "latihan ngoding", "latihan koding bareng", "solve problem",
    "ngerjain tubes", "nyicil tubes", "tugas besar", "laporan praktikum", "tugas mingguan",
    "pahami materi dasar", "belajar konsep awal", "diskusi materi", "bedah konsep"
]

# Hari & Waktu Khas Tel-U (Disatukan sebagai rentang {schedule} utuh)
SCHEDULES = [
    "hari Rabu jam 9 sampai 12",
    "hari Kamis jam 09:00 - 12:00",
    "hari Jumat pukul 13:00 - 15:00",
    "hari Selasa jam 10 sampai 12",
    "hari Senin jam 14:00 s/d 16:30",
    "hari Sabtu jam 8 pagi sampai 11",
    "hari Minggu jam 13 sampai 15",
    "hari Rabu jam 16 sampai 18 sore",
    "hari Kamis jam 19 sampai 21 malam",
    "hari Selasa pas jam kosong jam 10",
    "hari Jumat pukul 08:30 - 11:30"
]

# Spot Belajar Kampus Tel-U & Mode (study_mode)
STUDY_MODES = [
    "tatap muka di Open Library",
    "di Mezzanine Oplib",
    "Discussion Room Open Library",
    "tatap muka di TULT lantai 5",
    "selasar FTE",
    "selasar Gd B",
    "kantin TULT",
    "kosan Sukabirus",
    "kosan Sukapura",
    "cafe Sukabirus",
    "online via Google Meet",
    "online di Discord",
    "online Zoom",
    "hybrid fleksibel",
    "offline langsung di kampus",
    "selasar Lab Komputer FTE"
]

# Ukuran Kelompok (group_size)
GROUP_SIZES = [
    "2 sampai 4 orang",
    "3 orang",
    "2 orang",
    "maksimal 4 mahasiswa",
    "berdua aja",
    "3-4 orang",
    "4 orang",
    "butuh 2 orang lagi",
    "partner 1 orang",
    "berdua"
]

# ==============================================================================
# TEMPLATES UNTUK DATASET LATIH (TRAINING) - 30 Pola Kalimat Alami & Gaul
# ==============================================================================
TRAIN_TEMPLATES = [
    # Pola 1: Kalimat standar lengkap
    "Saya mau belajar {topic} buat {learning_goal} {course} {schedule} bareng {group_size} {study_mode}.",
    "Mau diskusi materi {topic} mata kuliah {course} bareng {group_size} secara {study_mode} {schedule}.",
    "Ada yang mau ngoding bareng {topic} untuk {course} {learning_goal}? Yuk kumpul {study_mode} {schedule} {group_size}.",
    "Latihan soal {topic} persiapan kuis {course} yuk, jadwalnya {schedule} bareng {group_size} {study_mode}.",
    "Cari temen belajar {course} bab {topic} buat {learning_goal}, preferensi {study_mode} {schedule} bareng {group_size}.",
    "Butuh partner diskusi {topic} mata kuliah {course} {schedule} {study_mode} untuk {group_size}.",
    "Yuk bedah materi {topic} {course} buat {learning_goal} {schedule} {study_mode} {group_size}.",
    "Bahas tuntas {topic} matkul {course} buat {learning_goal} kelompok {group_size} {study_mode} {schedule}.",
    "Mau nyicil {learning_goal} {course} khususnya bab {topic} {schedule} bareng {group_size} di {study_mode}.",
    "Siapa yang mau belajar bareng {topic} {course} {schedule} {group_size} {study_mode}?",
    
    # Pola 2: Gaya obrolan santai & tanya rekan
    "Bro, ada yang mau bahas {topic}? Gue masih bingung materi {course} buat {learning_goal} {schedule} {study_mode}.",
    "Gais, besok ada {learning_goal} {course}, pengen belajar bareng {group_size} {study_mode} {schedule}.",
    "Kuy yang mau ngulik {topic} {course} {schedule} kumpul di {study_mode} bareng {group_size}.",
    "Ada yang paham {topic} {course}? Mau diajarin dong {schedule} {study_mode} {group_size}.",
    "Nyari temen buat {learning_goal} {course} bab {topic}, enaknya {study_mode} {schedule} bareng {group_size}.",
    "Lagi butuh partner buat {learning_goal} {course} {schedule} di {study_mode} bareng {group_size}.",
    "Yuk nyicil {learning_goal} {course} {schedule} bareng {group_size} di {study_mode}.",
    
    # Pola 3: Jadwal atau lokasi terlebih dahulu
    "{schedule} ada yang kosong? Mau belajar {topic} {course} buat {learning_goal} {study_mode}.",
    "Lagi di {study_mode} nih, ada yang mau bareng belajar {topic} {course} bareng {group_size}?",
    "Kosong {schedule}, mau fokus {learning_goal} {course} materi {topic} bareng {group_size} {study_mode}.",
    "Ketemu di {study_mode} yuk {schedule} buat bahas {topic} {course} bareng {group_size}.",
    
    # Pola 4: Kalimat tidak lengkap (Hanya matkul + topik + tujuan)
    "Mau belajar {course} khususnya {topic} buat {learning_goal}.",
    "Cari temen ngerjain {learning_goal} {course} bab {topic} bareng {group_size}.",
    "Fokus {learning_goal} matkul {course} materi {topic}.",
    "Bahas soal {topic} {course} bareng {group_size} di {study_mode}.",
    
    # Pola 5: Kalimat ringkas fokus tugas/ujian
    "Persiapan {learning_goal} {course} topik {topic} {schedule} {study_mode}.",
    "Nyicil {learning_goal} {course} {schedule} bareng {group_size} di {study_mode}.",
    "Belajar bareng {topic} {course} {schedule}.",
    "Diskusi {topic} {course} bareng {group_size} {study_mode}."
]

# ==============================================================================
# TEMPLATES UNTUK DATASET VALIDASI (VALIDATION) - 20 Pola Kalimat Sintaks BERBEDA (UNSEEN)
# ==============================================================================
VAL_TEMPLATES = [
    # Struktur pertanyaan & konfirmasi yang belum pernah ada di training
    "Halo teman-teman, apakah ada yang ingin belajar {topic} untuk {course}? Rencananya {schedule} {study_mode} bareng {group_size}.",
    "Teman-teman ada yang mau review bareng materi {topic} {course} buat {learning_goal}? Bisa {schedule} {study_mode}.",
    "Butuh bantuan buat memahami {topic} di matkul {course}. Ada yang free {schedule}? Prefer {study_mode} bareng {group_size}.",
    "Materi {topic} {course} susah banget, yuk latihan {learning_goal} bareng {group_size} {schedule} di {study_mode}.",
    "Aku ada waktu luang {schedule}, barangkali ada yang mau {learning_goal} {course} bab {topic} {study_mode}.",
    "Bisa join belajar {topic} {course}? Buat {learning_goal} bareng {group_size} {schedule} {study_mode}.",
    "Pengen sharing materi {topic} mata kuliah {course} nih, siapa mau gabung bareng {group_size} {schedule} {study_mode}?",
    "Siap-siap menghadapi {learning_goal} {course}, mau ajak {group_size} belajar materi {topic} {schedule} di {study_mode}.",
    "Adakah yang berminat bedah soal {topic} {course}? Agendanya {schedule} {study_mode} bareng {group_size}.",
    "Tolong ajarin dong bab {topic} di {course}, butuh buat {learning_goal} {schedule} bareng {group_size}.",
    
    # Variasi struktur terbalik & informal berbeda
    "Rencana {schedule} mau ngerjain {learning_goal} {course} tentang {topic} {study_mode} bareng {group_size}.",
    "Bagi yang belum paham {topic} {course}, kita kumpul {study_mode} {schedule} bareng {group_size} ya.",
    "Ayo kelompokan {group_size} buat {learning_goal} {course} materi {topic} {schedule} di {study_mode}.",
    "Target kelar {topic} {course} sebelum {learning_goal}, kumpul {schedule} {study_mode} bareng {group_size}.",
    "Nyari teman sekelas yang mau diskusi {topic} {course} {schedule} {study_mode}.",
    "Merapat ke {study_mode} yuk {schedule}, kita bahas tuntas {topic} {course} buat {learning_goal}.",
    "Ada slot untuk {group_size} yang mau {learning_goal} {course} bab {topic} {schedule} {study_mode}.",
    "Belajar santai materi {topic} {course} {schedule} bareng {group_size} di {study_mode}.",
    "Persiapan matang {learning_goal} {course} topik {topic} {schedule} {study_mode}.",
    "Mau perdalam {topic} {course} bareng {group_size} secara {study_mode} {schedule}."
]


def generate_sample_from_template_exact(tmpl: str) -> dict:
    """
    Menghasilkan satu kalimat data teranotasi span secara matematis presisi:
    Menggunakan token-stream parser untuk menghitung karakter offset start & end secara deterministik.
    Tidak ada pencarian 'text.find()' sehingga 100% bebas dari ambiguitas kemunculan ganda.
    """
    mk_info = random.choice(COURSES_DATA)
    course_val = mk_info["name"] if random.random() > 0.40 else random.choice(mk_info["aliases"])
    topic_val = random.choice(mk_info["topics"])
    schedule_val = random.choice(SCHEDULES)
    group_val = random.choice(GROUP_SIZES)
    mode_val = random.choice(STUDY_MODES)
    goal_val = random.choice(LEARNING_GOALS)

    values_map = {
        "course": course_val,
        "topic": topic_val,
        "learning_goal": goal_val,
        "schedule": schedule_val,
        "group_size": group_val,
        "study_mode": mode_val
    }

    # Pisahkan template berdasarkan token placeholder {key}
    parts = re.split(r"(\{[a-zA-Z_]+\})", tmpl)
    
    constructed_text = ""
    spans = []

    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            placeholder_key = part[1:-1]
            if placeholder_key in values_map:
                val = values_map[placeholder_key]
                start_offset = len(constructed_text)
                end_offset = start_offset + len(val)
                spans.append({
                    "start": start_offset,
                    "end": end_offset,
                    "label": placeholder_key,
                    "text": val
                })
                constructed_text += val
        else:
            constructed_text += part

    return {
        "text": constructed_text,
        "spans": spans
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(42)

    print("=" * 70)
    print(">> MEMBANGUN DATASET SPAN-LEVEL GLINER DENGAN EXACT TOKEN BUILDER...")
    print("=" * 70)

    # 1. Buat Training Set (800 sampel unik dari TRAIN_TEMPLATES)
    train_samples = []
    train_texts = set()
    attempts = 0
    while len(train_samples) < 800 and attempts < 4000:
        attempts += 1
        tmpl = random.choice(TRAIN_TEMPLATES)
        sample = generate_sample_from_template_exact(tmpl)
        if sample["text"] not in train_texts:
            train_texts.add(sample["text"])
            train_samples.append(sample)

    # 2. Buat Validation Set (200 sampel unik dari VAL_TEMPLATES - UNSEEN SYNTAX)
    val_samples = []
    val_texts = set()
    attempts = 0
    while len(val_samples) < 200 and attempts < 2000:
        attempts += 1
        tmpl = random.choice(VAL_TEMPLATES)
        sample = generate_sample_from_template_exact(tmpl)
        if sample["text"] not in train_texts and sample["text"] not in val_texts:
            val_texts.add(sample["text"])
            val_samples.append(sample)

    # 3. Simpan dataset
    with open(DATA_DIR / "train_data.json", "w", encoding="utf-8") as f:
        json.dump(train_samples, f, indent=2, ensure_ascii=False)

    with open(DATA_DIR / "val_data.json", "w", encoding="utf-8") as f:
        json.dump(val_samples, f, indent=2, ensure_ascii=False)

    # 4. Simpan labels.json seragam
    labels = ["course", "topic", "learning_goal", "schedule", "group_size", "study_mode"]
    with open(DATA_DIR / "labels.json", "w", encoding="utf-8") as f:
        json.dump({"labels": labels}, f, indent=2)

    print(f">> Dataset Latih (Train Data) Berhasil Dibuat : {len(train_samples)} sampel")
    print(f">> Dataset Validasi (Val Data) Berhasil Dibuat: {len(val_samples)} sampel (Pola Unseen)")
    print(f">> Taxonomy Label Seragam: {labels}")
    print("=" * 70)


if __name__ == "__main__":
    main()
