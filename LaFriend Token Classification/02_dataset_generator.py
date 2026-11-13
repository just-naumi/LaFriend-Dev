"""
==============================================================================
02_dataset_generator.py - Pembuat Dataset Token Classification (NER) LaFriend
Domain Fokus: S1 Teknik Komputer - Semester 1 s/d 8 (Telkom University)
==============================================================================
Script ini menyusun dataset token classification / span-level NER lengkap
untuk seluruh mata kuliah S1 Teknik Komputer Fakultas Teknik Elektro (FTE)
Universitas Telkom dari Semester 1 hingga Semester 8 beserta mata kuliah peminatan.
==============================================================================
"""

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
        "aliases": ["logika matematika", "logmat", "logika mat"],
        "topics": [
            "Tabel Kebenaran Proposisi", "Tautologi dan Kontradiksi", "Hukum Ekuivalensi Logika",
            "Kuantor Universal Eksistensial", "Aturan Inferensi Modus Ponens", "Pembuktian Matematis Kontradiksi"
        ]
    },
    {
        "semester": 1,
        "name": "Pengantar Rekayasa dan Desain",
        "aliases": ["prd", "rekayasa dan desain", "pengantar rekayasa"],
        "topics": [
            "Engineering Design Process", "Problem Definition Need Analysis", "Pembuatan Prototipe Produk",
            "Analisis Kelayakan Teknis", "Dokumentasi Teknis Capstone"
        ]
    },

    # --- SEMESTER 2 ---
    {
        "semester": 2,
        "name": "Kalkulus 2",
        "aliases": ["kalkulus 2", "kalkul 2"],
        "topics": [
            "Integral Parsial dan Substitusi", "Pecahan Parsial Aljabar", "Integral Luas Daerah",
            "Volume Benda Putar Cakram Tabung", "Integral Tak Wajar", "Uji Konvergensi Deret Tak Hingga",
            "Deret Taylor dan Maclaurin"
        ]
    },
    {
        "semester": 2,
        "name": "Fisika 2",
        "aliases": ["fisika 2", "fisdas 2", "fisika dasar 2"],
        "topics": [
            "Hukum Coulomb dan Gaya Elektrostatik", "Medan Listrik dan Hukum Gauss", "Potensial Listrik dan Kapasitor",
            "Hukum Ohm dan Hukum Kirchhoff", "Medan Magnetik dan Gaya Lorentz", "Hukum Faraday Induksi Elektromagnetik",
            "Rangkaian Arus Bolak Balik RLC"
        ]
    },
    {
        "semester": 2,
        "name": "Algoritma dan Pemrograman",
        "aliases": ["alpro", "algoritma pemrograman", "algoritma"],
        "topics": [
            "Percabangan dan Looping", "Fungsi dan Prosedur Parameter", "Rekursif C++",
            "Array 1D dan 2D Multidimensi", "Binary Search", "Bubble dan Selection Sort",
            "Merge Sort dan Quick Sort", "Pointer dan Alokasi Memori"
        ]
    },
    {
        "semester": 2,
        "name": "Matematika Diskrit",
        "aliases": ["matdis", "matematika diskrit", "diskrit"],
        "topics": [
            "Relasi Ekuivalensi dan Fungsi", "Prinsip Induksi Matematika", "Kombinatorika dan Permutasi",
            "Pigeonhole Principle", "Teori Graf Lintasan Euler Hamilton", "Pohon Rentang Spanning Tree"
        ]
    },
    {
        "semester": 2,
        "name": "Jaringan Komputer dan Data",
        "aliases": ["jarkom data", "pengantar jarkom", "dasar jarkom"],
        "topics": [
            "Model OSI 7 Layer TCP IP", "Media Transmisi dan Topologi", "Pengalamatan IPv4 Subnetting",
            "Data Link Layer Framing", "Protokol DNS HTTP FTP", "Analisis Paket Jaringan"
        ]
    },

    # --- SEMESTER 3 ---
    {
        "semester": 3,
        "name": "Struktur Data",
        "aliases": ["strukdat", "struktur data"],
        "topics": [
            "Singly dan Doubly Linked List", "Stack dan Evaluasi Postfix", "Queue dan Priority Queue",
            "Binary Search Tree BST", "AVL Tree Rotation", "Red-Black Tree",
            "Heap Sort Max Min Heap", "Graph Dijkstra Shortest Path", "Hash Table dan Collision Handling"
        ]
    },
    {
        "semester": 3,
        "name": "Keamanan Jaringan",
        "aliases": ["kamjar", "keamanan jaringan", "kamsib"],
        "topics": [
            "Prinsip Keamanan CIA Triad", "Kriptografi Simetris AES", "Kriptografi Asimetris RSA ECC",
            "Hash SHA-256 Digital Signature", "Arsitektur Firewall iptables", "Sistem IDS IPS Snort",
            "Virtual Private Network VPN IPsec"
        ]
    },
    {
        "semester": 3,
        "name": "Rangkaian Listrik",
        "aliases": ["rl", "rangkaian listrik"],
        "topics": [
            "Hukum Kirchhoff KCL KVL", "Analisis Node dan Mesh", "Teorema Thevenin Norton Superposisi",
            "Rangkaian Transien RC RL", "Rangkaian Transien RLC", "Analisis Fasor AC dan Impedansi",
            "Perhitungan Faktor Daya"
        ]
    },
    {
        "semester": 3,
        "name": "Persamaan Diferensial",
        "aliases": ["persamaan diferensial", "pdl", "pers diff"],
        "topics": [
            "PD Pemisahan Variabel", "PD Eksak dan Faktor Integrasi", "PD Linier Orde Dua Homogen",
            "Metode Koefisien Tak Tentu", "Transformasi Laplace Rangkaian Listrik", "Invers Laplace"
        ]
    },
    {
        "semester": 3,
        "name": "Probabilitas dan Statistika",
        "aliases": ["probstat", "probabilitas statistika"],
        "topics": [
            "Peluang Bersyarat Teorema Bayes", "Distribusi Binomial dan Poisson", "Distribusi Normal Gaussian",
            "Nilai Harapan dan Variansi", "Teorema Limit Pusat", "Uji Hipotesis t-Test", "Regresi Linier"
        ]
    },
    {
        "semester": 3,
        "name": "Aljabar Linier",
        "aliases": ["alin", "aljabar linier"],
        "topics": [
            "Eliminasi Gauss Jordan SPL", "Operasi Matriks dan Determinan", "Invers Matriks Kofaktor",
            "Vektor Bebas Linier Basis Dimensi", "Transformasi Linier Matriks", "Nilai Eigen dan Vektor Eigen"
        ]
    },

    # --- SEMESTER 4 ---
    {
        "semester": 4,
        "name": "Sistem Digital",
        "aliases": ["sisdig", "sistem digital", "teknik digital"],
        "topics": [
            "Penyederhanaan Karnaugh Map K-Map", "Rangkaian Multiplexer Decoder", "Flip-Flop JK D Flip-Flop",
            "Perancangan FSM Mealy Moore", "Register Geser Shift Register", "Synchronous Counter Biner",
            "Perancangan Hardware VHDL"
        ]
    },
    {
        "semester": 4,
        "name": "Elektronika",
        "aliases": ["elka", "elektronika"],
        "topics": [
            "Karakteristik Dioda Penyearah", "Dioda Zener Regulator", "Transistor BJT Bias Penguat",
            "MOSFET Switching Digital", "Operational Amplifier Op-Amp Inverting", "Komparator Tegangan"
        ]
    },
    {
        "semester": 4,
        "name": "Komputasi Awan",
        "aliases": ["komputasi awan", "cloud computing", "cloud"],
        "topics": [
            "Layanan IaaS PaaS SaaS", "Deployment Public Private Hybrid", "Virtualisasi Hypervisor",
            "Kontainerisasi Dockerfile", "Docker Compose Multi-Container", "Layanan AWS EC2 S3 VPC",
            "Serverless Lambda Computing"
        ]
    },
    {
        "semester": 4,
        "name": "Pengolahan Sinyal Waktu Kontinu",
        "aliases": ["sinyal kontinu", "pengolahan sinyal", "sinsis"],
        "topics": [
            "Sistem LTI dan Linieritas", "Integral Konvolusi Kontinu", "Deret Fourier Sinyal Periodik",
            "Transformasi Fourier CTFT Spektrum", "Respons Frekuensi Filter Analog"
        ]
    },
    {
        "semester": 4,
        "name": "Analisis dan Desain Sistem",
        "aliases": ["ads", "analisis desain sistem", "rpl"],
        "topics": [
            "SDLC Agile Scrum Sprint", "UML Use Case Diagram", "Sequence Diagram dan Class Diagram",
            "Arsitektur Microservices", "Perancangan UI UX Wireframe", "Pengujian Blackbox Whitebox"
        ]
    },
    {
        "semester": 4,
        "name": "Perancangan Catu Daya",
        "aliases": ["catu daya", "power supply"],
        "topics": [
            "Penyearah Gelombang Penuh", "Regulator Tegangan Linier LM7805", "SMPS Buck Boost Converter",
            "Proteksi Overcurrent Short Circuit", "Desain Layout PCB KiCAD"
        ]
    },

    # --- SEMESTER 5 ---
    {
        "semester": 5,
        "name": "Organisasi dan Arsitektur Komputer",
        "aliases": ["orkom", "arkom", "arsitektur komputer"],
        "topics": [
            "Arsitektur Von Neumann Harvard", "CPU Datapath dan Control Unit", "Set Instruksi MIPS RISC-V",
            "Instruction Pipelining Hazard", "Branch Prediction", "Cache Memory Direct Set-Associative",
            "Memori Paging TLB Virtual", "Interrupt DMA Interfacing"
        ]
    },
    {
        "semester": 5,
        "name": "Sistem Mikroprosesor",
        "aliases": ["sismin", "mikroprosesor", "mikrokontroler"],
        "topics": [
            "Arsitektur Register 8086", "Segmentasi Memori 20-bit", "Pemrograman Assembly x86",
            "Arsitektur AVR ATMega ARM", "Register Port DDR PORT PIN", "Timer Counter PWM Hardware",
            "External Interrupt ISR", "Interfacing Keypad LCD 16x2"
        ]
    },
    {
        "semester": 5,
        "name": "Basis Data",
        "aliases": ["basdat", "basis data"],
        "topics": [
            "Desain ERD Notasi Crow Foot", "Normalisasi 1NF sampai BCNF", "Query SQL JOIN Inner Left",
            "Subquery Correlated", "Fungsi Agregasi GROUP BY HAVING", "Indexing B-Tree",
            "Transaksi ACID DBMS", "NoSQL MongoDB Dokumen"
        ]
    },
    {
        "semester": 5,
        "name": "Sistem Jaringan Lanjut",
        "aliases": ["jarkom lanjut", "routing switching", "jarkom 2"],
        "topics": [
            "Protokol Spanning Tree STP RSTP", "Link Aggregation EtherChannel", "Inter-VLAN Routing Router Stick",
            "Dynamic Routing OSPF Multi-Area", "Konfigurasi BGP EIGRP", "NAT Overload PAT",
            "Manajemen Jaringan SNMP"
        ]
    },
    {
        "semester": 5,
        "name": "Pengolahan Sinyal Digital",
        "aliases": ["dsp", "sinyal digital", "pengolahan sinyal digital"],
        "topics": [
            "Sampling Nyquist Shannon Aliasing", "Konvolusi Diskrit Sinyal", "Transformasi Z dan ROC",
            "Discrete Fourier Transform DFT", "Fast Fourier Transform FFT", "Perancangan Filter Digital FIR IIR"
        ]
    },

    # --- SEMESTER 6 ---
    {
        "semester": 6,
        "name": "Sistem Tertanam & IoT",
        "aliases": ["sisbed", "embedded", "sistem tertanam", "embedded iot"],
        "topics": [
            "Arsitektur SoC STM32 ESP32", "Protokol Bus I2C Master-Slave", "Protokol SPI Full Duplex",
            "Perekaman ADC Sensor Analog", "Aktuator Relay Motor DC PWM", "Protokol IoT MQTT Publish Subscribe",
            "Komunikasi CoAP RESTful", "Sleep Mode Deep Sleep ESP32", "Dashboard ThingsBoard Node-RED"
        ]
    },
    {
        "semester": 6,
        "name": "Sistem Operasi & RTOS",
        "aliases": ["sisop", "rtos", "sistem operasi rtos", "sistem operasi"],
        "topics": [
            "Hard Soft Real-Time Operating System", "Penjadwalan RMS dan EDF", "Task Management FreeRTOS",
            "Task Synchronization Message Queue", "Counting Semaphore dan Mutex", "Masalah Priority Inversion Protocol",
            "Software Timers FreeRTOS", "Manajemen Memori Heap FreeRTOS"
        ]
    },
    {
        "semester": 6,
        "name": "Kecerdasan Buatan & Machine Learning",
        "aliases": ["ai", "machine learning", "ml", "kecerdasan buatan"],
        "topics": [
            "Algoritma Pencarian A Star Heuristik", "Supervised Learning Linear Regression", "Klasifikasi Decision Tree Random Forest",
            "Support Vector Machine SVM", "Unsupervised Learning K-Means Clustering", "Neural Network Multi-Layer Perceptron",
            "Backpropagation Gradient Descent", "Metrik Evaluasi F1-Score Confusion Matrix"
        ]
    },
    {
        "semester": 6,
        "name": "Sistem Kendali dan Robotika",
        "aliases": ["robotika", "sistem kendali", "kendali robotika"],
        "topics": [
            "Fungsi Alih Transfer Function", "Analisis Kestabilan Routh-Hurwitz", "Tuning Kontroler PID Ziegler Nichols",
            "Kinematika Robot Mobile Differential Drive", "Sensor Odometri LiDAR Navigasi", "Robot Operating System ROS Nodes Topics"
        ]
    },

    # --- SEMESTER 7 & 8 ---
    {
        "semester": 7,
        "name": "Manajemen Proyek TI",
        "aliases": ["manpro", "manajemen proyek", "project management"],
        "topics": [
            "Project Charter Scope Management", "Work Breakdown Structure WBS", "Jadwal Critical Path Method CPM",
            "Gantt Chart Manajemen Biaya", "Analisis Risiko Proyek Kualitatif", "Agile Scrum Sprint Backlog Jira"
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

    # --- MATA KULIAH PILIHAN / PEMINATAN KHUSUS ---
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

# Kosakata Hari & Waktu Khas Mahasiswa Tel-U
DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
TIMES = [
    "jam 9 sampai 12",
    "jam 09:00 - 12:00",
    "pukul 13:00 - 15:00",
    "jam 10 sampai 12",
    "jam 14:00 s/d 16:30",
    "pukul 8 pagi sampai 11",
    "jam 13 sampai 15",
    "jam 16 sampai 18 sore",
    "jam 19 sampai 21 malam",
    "pas jam kosong jam 10",
    "pukul 08:30 - 11:30"
]

# Evaluasi Akademik Khas Tel-U
EXAMS = [
    "persiapan UAS",
    "persiapan UTS",
    "persiapan kuis minggu depan",
    "kuis praktikum lab",
    "pengerjaan tubes",
    "persiapan ujian akhir",
    "responsi lab",
    "asessment 1",
    "asessment 2",
    "tes awal praktikum",
    "latihan soal ujian",
    "persiapan sidang proposal"
]

# Spot Belajar Kampus Telkom University & Mode
SPOTS_AND_MODES = [
    "tatap muka di Open Library",
    "nongkrong di Mezzanine Oplib",
    "Discussion Room Open Library",
    "tatap muka di TULT lantai 5",
    "selasar FTE",
    "selasar Gd B Cacuk",
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

# Ukuran Kelompok
GROUP_SIZES = [
    "bareng 2 sampai 4 orang",
    "kelompok 3 orang",
    "bareng 2 orang",
    "maksimal 4 mahasiswa",
    "berdua aja",
    "kelompok 3-4 orang",
    "bareng 4 orang",
    "butuh 2 orang lagi",
    "cari partner 1 orang",
    "belajar berdua"
]

# Pola Kalimat Variatif Mahasiswa
TEMPLATES = [
    "Saya mau belajar {topic} buat {exam} {course} hari {day} {time} {group} {mode}.",
    "Mau diskusi materi {topic} mata kuliah {course} kelompok {group} secara {mode} hari {day} {time}.",
    "Ada yang mau ngoding bareng {topic} untuk {course} {exam}? Yuk kumpul {mode} {day} {time} {group}.",
    "Latihan soal {topic} persiapan kuis {course} yuk, jadwalnya hari {day} {time} bareng {group} {mode}.",
    "Cari temen belajar {course} bab {topic} buat {exam}, preferensi {mode} hari {day} {time} {group}.",
    "Butuh partner diskusi {topic} mata kuliah {course} hari {day} {time} {mode} untuk {group}.",
    "Yuk bedah materi {topic} {course} {exam} hari {day} {time} {mode} {group}.",
    "Bahas tuntas {topic} matkul {course} buat {exam} kelompok {group} {mode} hari {day} {time}.",
    "Mau nyicil {exam} {course} khususnya bab {topic} hari {day} {time} bareng {group} di {mode}.",
    "Siapa yang mau belajar bareng {topic} {course} hari {day} {time} {group} {mode}?"
]

def generate_sample(template_idx=None):
    mk_info = random.choice(COURSES_DATA)
    # Pilih apakah nama resmi atau alias gaul
    course_name = mk_info["name"] if random.random() > 0.45 else random.choice(mk_info["aliases"])
    topic = random.choice(mk_info["topics"])
    day = random.choice(DAYS)
    time = random.choice(TIMES)
    schedule = f"{day} {time}"
    group = random.choice(GROUP_SIZES)
    mode = random.choice(SPOTS_AND_MODES)
    exam = random.choice(EXAMS)

    tmpl = random.choice(TEMPLATES) if template_idx is None else TEMPLATES[template_idx % len(TEMPLATES)]
    text = tmpl.format(
        course=course_name,
        topic=topic,
        day=day,
        time=time,
        schedule=schedule,
        group=group,
        mode=mode,
        exam=exam
    )

    entities = []
    
    def find_span(substring, label):
        idx = text.find(substring)
        if idx != -1:
            entities.append({
                "start": idx,
                "end": idx + len(substring),
                "text": substring,
                "label": label
            })

    find_span(topic, "topic")
    find_span(course_name, "course")
    find_span(exam, "exam_prep")
    find_span(f"hari {day} {time}" if f"hari {day} {time}" in text else f"{day} {time}", "schedule")
    find_span(group, "group_size")
    find_span(mode, "study_mode")

    entities.sort(key=lambda x: x["start"])

    return {
        "text": text,
        "ner": [[ent["start"], ent["end"], ent["label"]] for ent in entities],
        "spans": entities
    }

def build_dataset(num_train=600, num_val=120):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f">> [1/3] Membuat {num_train} sampel training kurikulum S1 Teknik Komputer Semester 1-8...")
    train_data = [generate_sample() for _ in range(num_train)]
    
    print(f">> [2/3] Membuat {num_val} sampel validasi kurikulum S1 Teknik Komputer Semester 1-8...")
    val_data = [generate_sample() for _ in range(num_val)]

    # Simpan dataset
    train_path = DATA_DIR / "train_data.json"
    val_path = DATA_DIR / "val_data.json"
    labels_path = DATA_DIR / "labels.json"

    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train_data, f, indent=2, ensure_ascii=False)

    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(val_data, f, indent=2, ensure_ascii=False)

    labels = ["course", "topic", "exam_prep", "schedule", "group_size", "study_mode"]
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump({
            "labels": labels,
            "target_major": "S1 Teknik Komputer (Fakultas Teknik Elektro, Telkom University)",
            "coverage": "Semester 1 s/d Semester 8 + Mata Kuliah Peminatan",
            "total_courses": len(COURSES_DATA),
            "total_train": num_train,
            "total_val": num_val
        }, f, indent=2)

    print(f">> [3/3] SUKSES! Dataset 1-8 lengkap tersimpan di:")
    print(f"   - {train_path}")
    print(f"   - {val_path}")
    print(f"   - {labels_path}")

if __name__ == "__main__":
    build_dataset(600, 120)
