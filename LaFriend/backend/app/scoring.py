# scoring.py - Modul Soft Constraint Scoring & Compatibility Ranking Engine (Day 15)
# Bertanggung jawab menghitung tingkat kecocokan kandidat yang lolos Hard Constraint Day 14.

import re
import math
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

# ==============================================================================
# 1. ENUM KANONIS & CANONICALIZER
# ==============================================================================

CANONICAL_LEARNING_GOALS = {
    "UNDERSTAND",
    "PRACTICE",
    "EXAM_PREPARATION",
    "ASSIGNMENT",
    "PROJECT",
    "KNOWLEDGE_SHARING",
}

LEARNING_GOAL_ALIASES = {
    "CONCEPT": "UNDERSTAND",
    "EXAM_PREP": "EXAM_PREPARATION",
    "DISCUSSION": "KNOWLEDGE_SHARING",  # Khusus learning goal, diskusi bermakna berbagi pengetahuan
}

CANONICAL_COLLABORATION_STYLES = {
    "DISCUSSION",
    "PRACTICE",
    "PEER_TUTORING",
    "FOCUS_STUDY",
}

COLLABORATION_STYLE_ALIASES = {
    "TEACHING": "PEER_TUTORING",
    "SILENT": "FOCUS_STUDY",
    # Catatan: "DISCUSSION" pada style tetap bermakna "DISCUSSION" (diskusi interaktif aktif)
}

CANONICAL_LEARNING_MODES = {
    "ONLINE",
    "OFFLINE",
    "HYBRID",
}

LEARNING_MODE_ALIASES = {
    "DARING": "ONLINE",
    "LURING": "OFFLINE",
    "CAMPURAN": "HYBRID",
}


def normalize_learning_goal(value: Any) -> str:
    """
    Menormalisasi nilai Learning Goal menjadi standar kanonis Day 15:
    - UNDERSTAND (termasuk alias CONCEPT)
    - PRACTICE
    - EXAM_PREPARATION (termasuk alias EXAM_PREP)
    - ASSIGNMENT
    - PROJECT
    - KNOWLEDGE_SHARING (termasuk alias DISCUSSION)

    Sifat:
    - Case-insensitive & whitespace-stripped.
    - Idempotent: normalize_learning_goal(normalize_learning_goal(x)) == normalize_learning_goal(x).
    - Menolak None, string kosong, atau nilai yang tidak dikenali dengan ValueError.
    """
    if not isinstance(value, str):
        raise ValueError(f"Learning goal harus berupa string, diterima: {type(value).__name__}")
    
    clean = value.strip().upper()
    if not clean:
        raise ValueError("Learning goal tidak boleh kosong")

    # Cek alias terlebih dahulu
    if clean in LEARNING_GOAL_ALIASES:
        return LEARNING_GOAL_ALIASES[clean]

    # Cek apakah sudah merupakan nilai kanonis
    if clean in CANONICAL_LEARNING_GOALS:
        return clean

    raise ValueError(
        f"Learning goal '{value}' tidak valid. Pilihan kanonis: {sorted(CANONICAL_LEARNING_GOALS)}"
    )


def normalize_collaboration_style(value: Any) -> str:
    """
    Menormalisasi nilai Collaboration Style menjadi standar kanonis Day 15:
    - DISCUSSION
    - PRACTICE
    - PEER_TUTORING (termasuk alias TEACHING)
    - FOCUS_STUDY (termasuk alias SILENT)

    Sifat:
    - Case-insensitive & whitespace-stripped.
    - Idempotent: normalize_collaboration_style(normalize_collaboration_style(x)) == normalize_collaboration_style(x).
    - Menolak None, string kosong, atau nilai yang tidak dikenali dengan ValueError.
    """
    if not isinstance(value, str):
        raise ValueError(f"Collaboration style harus berupa string, diterima: {type(value).__name__}")
    
    clean = value.strip().upper()
    if not clean:
        raise ValueError("Collaboration style tidak boleh kosong")

    # Cek alias terlebih dahulu
    if clean in COLLABORATION_STYLE_ALIASES:
        return COLLABORATION_STYLE_ALIASES[clean]

    # Cek apakah sudah merupakan nilai kanonis
    if clean in CANONICAL_COLLABORATION_STYLES:
        return clean

    raise ValueError(
        f"Collaboration style '{value}' tidak valid. Pilihan kanonis: {sorted(CANONICAL_COLLABORATION_STYLES)}"
    )


def normalize_learning_mode(value: Any) -> str:
    """
    Menormalisasi nilai Learning Mode menjadi standar kanonis Day 15:
    - ONLINE (termasuk alias DARING)
    - OFFLINE (termasuk alias LURING)
    - HYBRID (termasuk alias CAMPURAN)

    Sifat:
    - Case-insensitive & whitespace-stripped.
    - Idempotent: normalize_learning_mode(normalize_learning_mode(x)) == normalize_learning_mode(x).
    - Menolak None, string kosong, atau nilai yang tidak dikenali dengan ValueError.
    """
    if not isinstance(value, str):
        raise ValueError(f"Learning mode harus berupa string, diterima: {type(value).__name__}")
    
    clean = value.strip().upper()
    if not clean:
        raise ValueError("Learning mode tidak boleh kosong")

    # Cek alias terlebih dahulu
    if clean in LEARNING_MODE_ALIASES:
        return LEARNING_MODE_ALIASES[clean]

    # Cek apakah sudah merupakan nilai kanonis
    if clean in CANONICAL_LEARNING_MODES:
        return clean

    raise ValueError(
        f"Learning mode '{value}' tidak valid. Pilihan kanonis: {sorted(CANONICAL_LEARNING_MODES)}"
    )


# ==============================================================================
# 2. MATRIKS KOMPATIBILITAS (GOAL & STYLE)
# ==============================================================================

# Matriks Simetris Kompatibilitas Tujuan Belajar (Goal)
# Sifat: G(A, B) == G(B, A), Diagonal == 1.00, Range 0.0 - 1.0
GOAL_COMPATIBILITY: Dict[str, Dict[str, float]] = {
    "UNDERSTAND": {
        "UNDERSTAND": 1.00,
        "PRACTICE": 0.85,
        "EXAM_PREPARATION": 0.80,
        "ASSIGNMENT": 0.70,
        "PROJECT": 0.40,
        "KNOWLEDGE_SHARING": 0.90,
    },
    "PRACTICE": {
        "UNDERSTAND": 0.85,
        "PRACTICE": 1.00,
        "EXAM_PREPARATION": 0.90,
        "ASSIGNMENT": 0.80,
        "PROJECT": 0.60,
        "KNOWLEDGE_SHARING": 0.75,
    },
    "EXAM_PREPARATION": {
        "UNDERSTAND": 0.80,
        "PRACTICE": 0.90,
        "EXAM_PREPARATION": 1.00,
        "ASSIGNMENT": 0.65,
        "PROJECT": 0.30,
        "KNOWLEDGE_SHARING": 0.70,
    },
    "ASSIGNMENT": {
        "UNDERSTAND": 0.70,
        "PRACTICE": 0.80,
        "EXAM_PREPARATION": 0.65,
        "ASSIGNMENT": 1.00,
        "PROJECT": 0.80,
        "KNOWLEDGE_SHARING": 0.60,
    },
    "PROJECT": {
        "UNDERSTAND": 0.40,
        "PRACTICE": 0.60,
        "EXAM_PREPARATION": 0.30,
        "ASSIGNMENT": 0.80,
        "PROJECT": 1.00,
        "KNOWLEDGE_SHARING": 0.50,
    },
    "KNOWLEDGE_SHARING": {
        "UNDERSTAND": 0.90,
        "PRACTICE": 0.75,
        "EXAM_PREPARATION": 0.70,
        "ASSIGNMENT": 0.60,
        "PROJECT": 0.50,
        "KNOWLEDGE_SHARING": 1.00,
    },
}

# Matriks Simetris Kompatibilitas Gaya Kolaborasi (Style)
# Sifat: S(A, B) == S(B, A), Diagonal == 1.00, Range 0.0 - 1.0
STYLE_COMPATIBILITY: Dict[str, Dict[str, float]] = {
    "DISCUSSION": {
        "DISCUSSION": 1.00,
        "PRACTICE": 0.80,
        "PEER_TUTORING": 0.85,
        "FOCUS_STUDY": 0.15,
    },
    "PRACTICE": {
        "DISCUSSION": 0.80,
        "PRACTICE": 1.00,
        "PEER_TUTORING": 0.80,
        "FOCUS_STUDY": 0.30,
    },
    "PEER_TUTORING": {
        "DISCUSSION": 0.85,
        "PRACTICE": 0.80,
        "PEER_TUTORING": 1.00,
        "FOCUS_STUDY": 0.20,
    },
    "FOCUS_STUDY": {
        "DISCUSSION": 0.15,
        "PRACTICE": 0.30,
        "PEER_TUTORING": 0.20,
        "FOCUS_STUDY": 1.00,
    },
}


def calculate_goal_compatibility(goal_a: Any, goal_b: Any) -> float:
    """
    Menghitung skor kompatibilitas tujuan belajar antara dua entitas.
    Normalisasi kedua input menjadi bentuk kanonis terlebih dahulu.
    """
    norm_a = normalize_learning_goal(goal_a)
    norm_b = normalize_learning_goal(goal_b)
    return GOAL_COMPATIBILITY[norm_a][norm_b]


def calculate_style_compatibility(style_a: Any, style_b: Any) -> float:
    """
    Menghitung skor kompatibilitas gaya kolaborasi antara dua entitas.
    Normalisasi kedua input menjadi bentuk kanonis terlebih dahulu.
    """
    norm_a = normalize_collaboration_style(style_a)
    norm_b = normalize_collaboration_style(style_b)
    return STYLE_COMPATIBILITY[norm_a][norm_b]


# Matriks Simetris Kompatibilitas Mode Belajar (Learning Mode)
# Sifat: M(A, B) == M(B, A), Diagonal == 1.00, Range 0.0 - 1.0
MODE_COMPATIBILITY: Dict[str, Dict[str, float]] = {
    "ONLINE": {
        "ONLINE": 1.00,
        "OFFLINE": 0.00,
        "HYBRID": 0.85,
    },
    "OFFLINE": {
        "ONLINE": 0.00,
        "OFFLINE": 1.00,
        "HYBRID": 0.85,
    },
    "HYBRID": {
        "ONLINE": 0.85,
        "OFFLINE": 0.85,
        "HYBRID": 1.00,
    },
}


def calculate_mode_compatibility(mode_a: Any, mode_b: Any) -> float:
    """
    Menghitung skor kompatibilitas Mode Belajar M(A, B) dalam rentang [0.0, 1.0].
    Sifat:
    - Simetris: M(A, B) == M(B, A).
    - Normalisasi kedua input menjadi bentuk kanonis terlebih dahulu.
    - Melempar ValueError jika salah satu mode tidak valid.
    """
    norm_a = normalize_learning_mode(mode_a)
    norm_b = normalize_learning_mode(mode_b)
    return MODE_COMPATIBILITY[norm_a][norm_b]


# ==============================================================================
# 3. DATE & DURATION SCORING (70% PRIORITY + 30% DURATION)
# ==============================================================================

# Tabel Pasangan Prioritas Minimax untuk Partner Matching (Simetris)
# Peringkat prioritas: 1 = Utama, 2 = Cadangan, 3 = Fleksibel
PAIR_PRIORITY_SCORES: Dict[Tuple[int, int], float] = {
    (1, 1): 1.00,
    (1, 2): 0.85,
    (2, 1): 0.85,
    (2, 2): 0.70,
    (1, 3): 0.60,
    (3, 1): 0.60,
    (2, 3): 0.45,
    (3, 2): 0.45,
    (3, 3): 0.30,
}

# Tabel Prioritas Tunggal untuk Session Matching
# Berdasarkan prioritas jadwal Study Intent mahasiswa pemohon
SESSION_PRIORITY_SCORES: Dict[int, float] = {
    1: 1.00,
    2: 0.70,
    3: 0.30,
}


def calculate_priority_score(priority_a: int, priority_b: int) -> float:
    """
    Menghitung skor kualitas pasangan prioritas jadwal untuk Partner Matching.
    Hanya menerima prioritas integer {1, 2, 3}.
    Prioritas di luar rentang akan melempar ValueError.
    """
    if not isinstance(priority_a, int) or not isinstance(priority_b, int) or isinstance(priority_a, bool) or isinstance(priority_b, bool):
        raise ValueError(f"Priority harus bertipe integer, diterima: {type(priority_a).__name__}, {type(priority_b).__name__}")

    if priority_a not in {1, 2, 3} or priority_b not in {1, 2, 3}:
        raise ValueError(f"Priority rank harus bernilai 1, 2, atau 3. Diterima: priority_a={priority_a}, priority_b={priority_b}")

    pair = (priority_a, priority_b)
    return PAIR_PRIORITY_SCORES[pair]


def calculate_session_priority_score(priority_rank: int) -> float:
    """
    Menghitung skor prioritas jadwal untuk Session Matching.
    Menggunakan prioritas ketersediaan Study Intent mahasiswa pemohon (1, 2, atau 3).
    """
    if not isinstance(priority_rank, int) or isinstance(priority_rank, bool):
        raise ValueError(f"Priority rank harus bertipe integer, diterima: {type(priority_rank).__name__}")

    if priority_rank not in {1, 2, 3}:
        raise ValueError(f"Priority rank harus bernilai 1, 2, atau 3. Diterima: {priority_rank}")

    return SESSION_PRIORITY_SCORES[priority_rank]


def calculate_duration_score(duration_minutes: int) -> float:
    """
    Menghitung skor durasi irisan waktu belajar L(d) dengan interpolasi bertahap:
    - d < 60  -> 0.00 (double safety floor)
    - 60 <= d <= 90 -> 0.50 + 0.01 * (d - 60)
    - 90 < d < 120  -> 0.80 + (0.20 / 30) * (d - 90)
    - d >= 120 -> 1.00
    
    Menolak durasi negatif dengan ValueError.
    """
    if not isinstance(duration_minutes, (int, float)) or isinstance(duration_minutes, bool):
        raise ValueError(f"Duration minutes harus berupa angka numerik, diterima: {type(duration_minutes).__name__}")

    if math.isnan(duration_minutes) or math.isinf(duration_minutes):
        raise ValueError("Duration minutes harus bernilai finite")

    d = float(duration_minutes)
    if d < 0:
        raise ValueError(f"Duration minutes tidak boleh negatif, diterima: {duration_minutes}")

    if d < 60.0:
        return 0.0
    elif d <= 90.0:
        return 0.50 + 0.01 * (d - 60.0)
    elif d < 120.0:
        return 0.80 + (0.20 / 30.0) * (d - 90.0)
    else:
        return 1.00


def calculate_date_score(priority_score: float, duration_score: float) -> float:
    """
    Menggabungkan skor prioritas (70%) dan durasi (30%):
    D = 0.70 * P + 0.30 * L

    Memvalidasi bahwa priority_score dan duration_score berada pada rentang [0.0, 1.0].
    """
    if not isinstance(priority_score, (int, float)) or isinstance(priority_score, bool):
        raise ValueError(f"priority_score harus berupa float, diterima: {type(priority_score).__name__}")
    if not isinstance(duration_score, (int, float)) or isinstance(duration_score, bool):
        raise ValueError(f"duration_score harus berupa float, diterima: {type(duration_score).__name__}")

    if not (0.0 <= priority_score <= 1.0):
        raise ValueError(f"priority_score harus berada pada rentang 0.0 - 1.0, diterima: {priority_score}")
    if not (0.0 <= duration_score <= 1.0):
        raise ValueError(f"duration_score harus berada pada rentang 0.0 - 1.0, diterima: {duration_score}")

    return 0.70 * float(priority_score) + 0.30 * float(duration_score)


# ==============================================================================
# 4. TOPIC SIMILARITY (TAHAP 15.2: COSINE + JACCARD FALLBACK)
# ==============================================================================

# Daftar kata umum / partikel yang tidak membedakan materi belajar
# Digunakan untuk menyaring noise saat tokenisasi leksikal, namun tetap menjaga istilah teknis
INDONESIAN_TOPIC_STOPWORDS = {
    "dan", "atau", "pada", "di", "ke", "dari", "tentang", "materi", "bab",
    "dengan", "yang", "untuk", "seputar", "mengenai", "dalam"
}

# Kelompok sinonim & singkatan teknis terkurasi untuk normalisasi klaster
# Setiap anggota dalam klaster yang sama akan menghasilkan ekspansi token yang ekuivalen
TECHNICAL_TOPIC_CLUSTERS = [
    # Struktur Data & Algoritma
    {"bst", "binary search tree"},
    {"avl", "avl tree"},
    {"bfs", "breadth first search"},
    {"dfs", "depth first search"},
    {"dp", "dynamic programming"},
    {"dsa", "data structures and algorithms"},
    {"oop", "pbo", "object oriented programming", "pemrograman berorientasi objek"},
    # Mata Kuliah / Bidang Telkom University
    {"alpro", "algoritma dan pemrograman", "algoritma pemrograman"},
    {"matdis", "matematika diskrit"},
    {"sismul", "sistem multimedia"},
    {"jarkom", "jaringan komputer"},
    {"os", "so", "operating system", "sistem operasi"},
    {"bd", "basdat", "basis data", "database"},
    {"ai", "artificial intelligence", "kecerdasan buatan"},
    {"ml", "machine learning", "pembelajaran mesin"},
    {"kalkulus 1", "kalkulus i"},
    {"kalkulus 2", "kalkulus ii"},
]


def normalize_topic_text(text: Any) -> str:
    """
    Menormalisasi teks topik belajar:
    - Memastikan tipe string dan tidak kosong.
    - Menghapus spasi berlebih di awal/akhir dan di antara kata.
    - Mengubah ke huruf kecil (lowercase), tetapi mempertahankan karakter alfanumerik
      dan simbol teknis seperti C++, C#, .NET, Node.js, AVL-Tree, 2D/3D.
    - Menolak None, string kosong, atau tipe selain string dengan ValueError.
    """
    if not isinstance(text, str):
        raise ValueError(f"Topic text harus berupa string, diterima: {type(text).__name__}")

    clean = text.strip()
    if not clean:
        raise ValueError("Topic text tidak boleh kosong")

    # Satukan spasi majemuk
    clean = " ".join(clean.split())
    return clean.lower()


def tokenize_topic(text: Any, remove_stopwords: bool = True, expand_aliases: bool = True) -> set:
    """
    Memecah teks topik menjadi kumpulan token (set of tokens).
    - Memisahkan berdasarkan tanda baca pemisah umum (koma, titik dua, tanda kurung, garis miring).
    - Mempertahankan istilah teknis dan singkatan seperti BFS, DFS, AVL, C++, OOP.
    - Jika expand_aliases=True, memperluas singkatan dan sinonim teknis secara dua arah
      (misal BST <-> Binary Search Tree) sehingga token sets keduanya identik saat Jaccard fallback.
    - Menyaring stop words umum jika kumpulan token yang tersisa tidak kosong.
    """
    norm = normalize_topic_text(text)

    # 1. Ekstrak token dasar
    raw_tokens = re.findall(r"[a-zA-Z0-9+#_]+(?:\.[a-zA-Z0-9+#_]+)*", norm)
    tokens = set()
    for t in raw_tokens:
        clean_t = t.strip("-._")
        if clean_t:
            tokens.add(clean_t)

    # 2. Ekspansi singkatan & sinonim teknis berbasis klaster ekuivalensi
    if expand_aliases:
        for cluster in TECHNICAL_TOPIC_CLUSTERS:
            # Periksa apakah salah satu anggota klaster ada di dalam teks
            matched = False
            for term in cluster:
                pattern = r'\b' + re.escape(term) + r'\b'
                if re.search(pattern, norm):
                    matched = True
                    break
            # Jika cocok, masukkan seluruh token penyusun dari seluruh anggota klaster
            if matched:
                for term in cluster:
                    for sub_t in re.findall(r"[a-zA-Z0-9+#_]+", term):
                        tokens.add(sub_t.lower())

    if remove_stopwords:
        filtered = {t for t in tokens if t not in INDONESIAN_TOPIC_STOPWORDS}
        if filtered:
            return filtered

    return tokens


def calculate_jaccard_similarity(topic_a: Any, topic_b: Any) -> float:
    """
    Menghitung kemiripan leksikal Jaccard antara dua topik:
    J(A, B) = |Tokens_A ∩ Tokens_B| / |Tokens_A ∪ Tokens_B|
    
    Sifat:
    - Jaccard(A, B) == Jaccard(B, A) (Simetris).
    - Range [0.0, 1.0].
    - Token identik -> 1.00.
    - Tidak ada irisan -> 0.00.
    - Mengenali singkatan teknis melalui kamus alias eksplisit.
    """
    tokens_a = tokenize_topic(topic_a, expand_aliases=True)
    tokens_b = tokenize_topic(topic_b, expand_aliases=True)

    if not tokens_a and not tokens_b:
        return 0.0

    union_tokens = tokens_a.union(tokens_b)
    if not union_tokens:
        return 0.0

    intersection_tokens = tokens_a.intersection(tokens_b)
    return len(intersection_tokens) / len(union_tokens)


def validate_embedding_vector(vector: Any, expected_dim: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Memvalidasi kelayakan vektor embedding secara ketat dan stabil secara numerik:
    - Harus berupa list atau tuple angka (float/int, bukan bool).
    - Tidak boleh kosong (panjang > 0).
    - Jika expected_dim diberikan, panjang vektor harus tepat sama.
    - Seluruh elemen harus finite (bukan NaN, bukan Infinity).
    - Menggunakan math.hypot(*coords) untuk mencegah overflow numerik pada angka sangat besar.
    - Norm Euclidean harus positif (> 1e-9, bukan vektor nol).

    Mengembalikan: (is_valid: bool, error_reason: Optional[str])
    """
    if vector is None:
        return False, "Vector bernilai None"

    if not isinstance(vector, (list, tuple)):
        return False, f"Vector harus berupa list/tuple, diterima: {type(vector).__name__}"

    if len(vector) == 0:
        return False, "Vector tidak boleh kosong (dimensi 0)"

    if expected_dim is not None and len(vector) != expected_dim:
        return False, f"Dimensi vector tidak cocok: diharapkan {expected_dim}, diterima {len(vector)}"

    float_vals = []
    for idx, val in enumerate(vector):
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return False, f"Elemen ke-{idx} bukan angka numerik: {type(val).__name__}"
        try:
            f_val = float(val)
        except OverflowError:
            return False, f"Elemen ke-{idx} mengalami overflow numerik (angka integer terlalu besar untuk float)"
        if not math.isfinite(f_val):
            return False, f"Elemen ke-{idx} tidak finite (NaN atau Infinity)"
        float_vals.append(f_val)

    # Perhitungan norm yang aman dari intermediate overflow
    try:
        norm = math.hypot(*float_vals)
    except OverflowError:
        return False, "Perhitungan norm mengalami overflow numerik"

    if not math.isfinite(norm):
        return False, "Norm vektor tidak finite"

    if norm < 1e-9:
        return False, "Norm vektor bernilai nol (vektor kosong/nol)"

    return True, None


def calculate_cosine_similarity(vec_a: Any, vec_b: Any) -> float:
    """
    Menghitung Cosine Similarity antara dua vektor embedding secara stabil:
    Cosine(u, v) = (u_hat . v_hat)

    Dibatasi pada rentang [0.0, 1.0].
    Menggunakan normalisasi unit vector (u_hat) terlebih dahulu untuk mencegah
    overflow pada dot product saat elemen vektor bernilai sangat besar.
    Melempar ValueError jika vektor tidak valid.
    """
    valid_a, err_a = validate_embedding_vector(vec_a)
    if not valid_a:
        raise ValueError(f"Vector A tidak valid: {err_a}")

    valid_b, err_b = validate_embedding_vector(vec_b, expected_dim=len(vec_a))
    if not valid_b:
        raise ValueError(f"Vector B tidak valid: {err_b}")

    vals_a = [float(a) for a in vec_a]
    vals_b = [float(b) for b in vec_b]

    norm_a = math.hypot(*vals_a)
    norm_b = math.hypot(*vals_b)

    if norm_a < 1e-9 or norm_b < 1e-9:
        raise ValueError("Norm vektor tidak boleh nol")

    # Dot product dari unit vectors mencegah overflow numerik
    dot_product = sum((a / norm_a) * (b / norm_b) for a, b in zip(vals_a, vals_b))

    # Batasi pada rentang [0.0, 1.0]
    return max(0.0, min(1.0, float(dot_product)))


def calculate_topic_similarity(
    topic_a: Any,
    topic_b: Any,
    embedding_service: Optional[Any] = None
) -> float:
    """
    Menghitung skor Topic Similarity T(A, B) dalam rentang [0.0, 1.0]:
    - Validasi teks topik (wajib non-kosong, raise ValueError jika kosong).
    - Jika embedding_service tersedia dan menghasilkan vektor valid -> Cosine Similarity.
    - Error eksternal embedding_service (timeout, network, exception) dipisahkan secara ketat
      dari validasi internal dan aman melakukan fallback ke Jaccard.
    - Validasi vektor dilakukan secara bertahap (vec_a sebelum vec_b) untuk mencegah
      TypeError pada len(vec_a) jika service mengembalikan objek non-sequence.
    - Fallback Jaccard diperkuat dengan klaster sinonim teknis.
    """
    # 1. Validasi teks topik (wajib non-kosong, error tidak boleh disamarkan sebagai fallback)
    norm_a = normalize_topic_text(topic_a)
    norm_b = normalize_topic_text(topic_b)

    # 2. Coba ambil embedding jika service disediakan
    vec_a = None
    vec_b = None
    if embedding_service is not None:
        try:
            vec_a = embedding_service.get_embedding(norm_a)
            vec_b = embedding_service.get_embedding(norm_b)
        except Exception:
            # Kegagalan service eksternal (API down, network error) mengaktifkan fallback
            vec_a = None
            vec_b = None

    # 3. Jika kedua vektor diperoleh dari service, validasi secara bertahap dan aman
    if vec_a is not None and vec_b is not None:
        valid_a, _ = validate_embedding_vector(vec_a)
        if valid_a:
            # vec_a dijamin berupa list/tuple berdimensi > 0, sehingga len(vec_a) aman dipanggil
            valid_b, _ = validate_embedding_vector(vec_b, expected_dim=len(vec_a))
            if valid_b:
                return calculate_cosine_similarity(vec_a, vec_b)

    # 4. Fallback leksikal Jaccard Token Similarity (dengan ekspansi klaster teknis)
    return calculate_jaccard_similarity(norm_a, norm_b)


def calculate_topic_similarity_detailed(
    topic_a: Any,
    topic_b: Any,
    embedding_service: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Versi transparan dari calculate_topic_similarity yang mengembalikan detail
    metode yang digunakan (COSINE vs JACCARD_FALLBACK) beserta skornya.
    Token diurutkan (sorted) secara deterministik untuk kepastian pengujian.
    Memisahkan pemanggilan service eksternal dari validasi vektor internal.
    """
    norm_a = normalize_topic_text(topic_a)
    norm_b = normalize_topic_text(topic_b)

    vec_a = None
    vec_b = None
    fallback_err = None

    # 1. Panggil service eksternal (diisolasi ketat dalam blok try/except)
    if embedding_service is not None:
        try:
            vec_a = embedding_service.get_embedding(norm_a)
            vec_b = embedding_service.get_embedding(norm_b)
        except Exception as e:
            fallback_err = f"Service failure: {str(e)}"
    else:
        fallback_err = "No embedding service provided"

    # 2. Jika pemanggilan service tidak memicu exception, lakukan validasi bertahap di luar blok try-except
    if fallback_err is None:
        if vec_a is None or vec_b is None:
            fallback_err = "Invalid embedding vector: Service returned None"
        else:
            valid_a, err_a = validate_embedding_vector(vec_a)
            if not valid_a:
                fallback_err = f"Invalid embedding vector: {err_a}"
            else:
                # vec_a terjamin berupa list/tuple non-kosong, aman memanggil len(vec_a)
                valid_b, err_b = validate_embedding_vector(vec_b, expected_dim=len(vec_a))
                if not valid_b:
                    fallback_err = f"Invalid embedding vector: {err_b}"
                else:
                    score = calculate_cosine_similarity(vec_a, vec_b)
                    return {
                        "score": score,
                        "method": "COSINE",
                        "error": None
                    }

    # 3. Fallback leksikal Jaccard Token Similarity
    score = calculate_jaccard_similarity(norm_a, norm_b)
    return {
        "score": score,
        "method": "JACCARD_FALLBACK",
        "error": fallback_err,
        "tokens_a": sorted(tokenize_topic(norm_a)),
        "tokens_b": sorted(tokenize_topic(norm_b)),
    }


# ==============================================================================
# 8. WEIGHTED COMPATIBILITY SCORE & BREAKDOWN (Tahap 15.4)
# ==============================================================================

# Bobot komponen resmi Day 15: Total = 1.00 (100%)
WEIGHT_TOPIC: float = 0.30  # T (30%)
WEIGHT_GOAL: float = 0.25   # G (25%)
WEIGHT_STYLE: float = 0.15  # S (15%)
WEIGHT_DATE: float = 0.15   # D (15%)
WEIGHT_MODE: float = 0.15   # M (15%)

SCORING_WEIGHTS: Dict[str, float] = {
    "topic": WEIGHT_TOPIC,
    "goal": WEIGHT_GOAL,
    "style": WEIGHT_STYLE,
    "date": WEIGHT_DATE,
    "mode": WEIGHT_MODE,
}


def validate_component_score(score: Any, name: str) -> float:
    """
    Memvalidasi satu nilai skor komponen agar sesuai kontrak Day 15:
    - Harus berupa angka numerik (int atau float, bukan bool).
    - Harus finite (bukan NaN, bukan Infinity).
    - Harus berada dalam rentang [0.0, 1.0].
    - Menolak angka integer raksasa (misal 10**400) yang memicu OverflowError sebagai ValueError.
    - Melempar ValueError jika melanggar kontrak.
    """
    if score is None:
        raise ValueError(f"Komponen {name} tidak boleh bernilai None")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise ValueError(f"Komponen {name} harus berupa angka numerik, diterima: {type(score).__name__}")
    
    try:
        float_val = float(score)
    except OverflowError:
        raise ValueError(f"Komponen {name} mengalami overflow numerik (angka terlalu besar untuk float)")

    if not math.isfinite(float_val):
        raise ValueError(f"Komponen {name} tidak finite (NaN atau Infinity)")
    if not (0.0 <= float_val <= 1.0):
        raise ValueError(f"Komponen {name} ({float_val}) harus berada dalam rentang [0.0, 1.0]")
    return float_val


def _round_half_up(val: Union[float, int, Decimal], decimals: int = 2) -> float:
    """
    Pembulatan presisi desimal standar (ROUND_HALF_UP) tanpa double-rounding.
    Mengkuantisasi representasi nilai langsung ke quantum desimal yang diinginkan.
    """
    quantum = Decimal("1").scaleb(-decimals)
    result = Decimal(str(val)).quantize(quantum, rounding=ROUND_HALF_UP)
    return float(result)


def calculate_compatibility_score(
    topic_score: Any,
    goal_score: Any,
    style_score: Any,
    date_score: Any,
    mode_score: Any
) -> float:
    """
    Menghitung skor kecocokan akhir CS dalam rentang [0.0, 100.0]:
    CS = 100 * (0.30*T + 0.25*G + 0.15*S + 0.15*D + 0.15*M)

    Aturan Day 15:
    - Seluruh 5 komponen (T, G, S, D, M) wajib tersedia dalam rentang [0.0, 1.0].
    - Tidak boleh ada normalisasi ulang bobot jika ada komponen yang hilang/None (wajib raise ValueError).
    - Skor dibatasi pada rentang [0.0, 100.0] dan dibulatkan 2 desimal (ROUND_HALF_UP tanpa double rounding).
    """
    t = validate_component_score(topic_score, "topic")
    g = validate_component_score(goal_score, "goal")
    s = validate_component_score(style_score, "style")
    d = validate_component_score(date_score, "date")
    m = validate_component_score(mode_score, "mode")

    # Akumulasi bobot menggunakan representasi Decimal eksak untuk menghindari truncation IEEE 754
    dec_score = Decimal("100") * (
        Decimal(str(WEIGHT_TOPIC)) * Decimal(str(t)) +
        Decimal(str(WEIGHT_GOAL)) * Decimal(str(g)) +
        Decimal(str(WEIGHT_STYLE)) * Decimal(str(s)) +
        Decimal(str(WEIGHT_DATE)) * Decimal(str(d)) +
        Decimal(str(WEIGHT_MODE)) * Decimal(str(m))
    )
    clamped = max(Decimal("0.0"), min(Decimal("100.0"), dec_score))
    return _round_half_up(clamped, 2)


def calculate_compatibility_breakdown(
    topic_score: Any,
    goal_score: Any,
    style_score: Any,
    date_score: Any,
    mode_score: Any
) -> Dict[str, Any]:
    """
    Menghasilkan rincian transparan dari perhitungan Compatibility Score:
    - total_score: float [0.0, 100.0] identik dengan hasil calculate_compatibility_score
    - rounding_reconciliation: selisih total pembulatan yang dialokasikan (biasanya +/- 0.01, +/- 0.02, atau 0.00)
    - components: kamus kontribusi untuk kelima komponen (topic, goal, style, date, mode)
      Setiap komponen memuat:
        * score: nilai mentah [0.0, 1.0] dibulatkan 4 desimal
        * weight: bobot resmi komponen (0.30, 0.25, 0.15, dll.)
        * raw_contribution: nilai kontribusi sebelum pembulatan (100 * weight * score)
        * contribution: poin kontribusi ke skor total (dibulatkan 2 desimal dengan rekonsiliasi sisa pembulatan)
        * rounding_adjustment: penyesuaian pembulatan yang dialokasikan (misal -0.01, +0.01, atau 0.0)
    """
    t = validate_component_score(topic_score, "topic")
    g = validate_component_score(goal_score, "goal")
    s = validate_component_score(style_score, "style")
    d = validate_component_score(date_score, "date")
    m = validate_component_score(mode_score, "mode")

    quantum = Decimal("1").scaleb(-2)
    raw_contribs = {
        "topic": Decimal("100") * Decimal(str(WEIGHT_TOPIC)) * Decimal(str(t)),
        "goal": Decimal("100") * Decimal(str(WEIGHT_GOAL)) * Decimal(str(g)),
        "style": Decimal("100") * Decimal(str(WEIGHT_STYLE)) * Decimal(str(s)),
        "date": Decimal("100") * Decimal(str(WEIGHT_DATE)) * Decimal(str(d)),
        "mode": Decimal("100") * Decimal(str(WEIGHT_MODE)) * Decimal(str(m)),
    }

    dec_total = sum(raw_contribs.values())
    clamped_total = max(Decimal("0.0"), min(Decimal("100.0"), dec_total))
    total_score_dec = clamped_total.quantize(quantum, rounding=ROUND_HALF_UP)

    # Pembulatan awal 2 desimal secara Decimal murni
    base_contribs = {
        k: v.quantize(quantum, rounding=ROUND_HALF_UP)
        for k, v in raw_contribs.items()
    }
    rounded_contribs = dict(base_contribs)
    adjustments = {k: Decimal("0.00") for k in raw_contribs}

    diff = total_score_dec - sum(rounded_contribs.values())

    # Jika terdapat selisih pembulatan, lakukan alokasi sisa terbesar (Largest Remainder Reconciliation)
    if diff != Decimal("0.00"):
        steps = int(diff * 100)
        sign = Decimal("0.01") if steps > 0 else Decimal("-0.01")
        component_keys = ["topic", "goal", "style", "date", "mode"]
        order = sorted(
            component_keys,
            key=lambda k: (
                (raw_contribs[k] - rounded_contribs[k]) if steps > 0 else (rounded_contribs[k] - raw_contribs[k]),
                Decimal(str(SCORING_WEIGHTS[k]))
            ),
            reverse=True
        )
        for i in range(abs(steps)):
            target_key = order[i % len(order)]
            rounded_contribs[target_key] += sign
            adjustments[target_key] += sign

    return {
        "total_score": float(total_score_dec),
        "rounding_reconciliation": float(diff),
        "components": {
            "topic": {
                "score": round(t, 4),
                "weight": WEIGHT_TOPIC,
                "raw_contribution": round(float(raw_contribs["topic"]), 4),
                "base_contribution": float(base_contribs["topic"]),
                "contribution": float(rounded_contribs["topic"]),
                "rounding_adjustment": float(adjustments["topic"]),
            },
            "goal": {
                "score": round(g, 4),
                "weight": WEIGHT_GOAL,
                "raw_contribution": round(float(raw_contribs["goal"]), 4),
                "base_contribution": float(base_contribs["goal"]),
                "contribution": float(rounded_contribs["goal"]),
                "rounding_adjustment": float(adjustments["goal"]),
            },
            "style": {
                "score": round(s, 4),
                "weight": WEIGHT_STYLE,
                "raw_contribution": round(float(raw_contribs["style"]), 4),
                "base_contribution": float(base_contribs["style"]),
                "contribution": float(rounded_contribs["style"]),
                "rounding_adjustment": float(adjustments["style"]),
            },
            "date": {
                "score": round(d, 4),
                "weight": WEIGHT_DATE,
                "raw_contribution": round(float(raw_contribs["date"]), 4),
                "base_contribution": float(base_contribs["date"]),
                "contribution": float(rounded_contribs["date"]),
                "rounding_adjustment": float(adjustments["date"]),
            },
            "mode": {
                "score": round(m, 4),
                "weight": WEIGHT_MODE,
                "raw_contribution": round(float(raw_contribs["mode"]), 4),
                "base_contribution": float(base_contribs["mode"]),
                "contribution": float(rounded_contribs["mode"]),
                "rounding_adjustment": float(adjustments["mode"]),
            },
        },
    }


# ==============================================================================
# 5. TAHAP 15.5: SESSION SCORING & PARTNER SCORING ENGINE
# ==============================================================================

def _get_field(obj: Any, field: str, default: Any = None) -> Any:
    """
    Membaca nilai field secara seragam dari objek SQLAlchemy ORM, Pydantic Schema, atau Mapping/dict.
    Tidak melakukan query database dan aman terhadap objek None.
    """
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        val = obj.get(field, default)
        return val if val is not None else default
    val = getattr(obj, field, default)
    return val if val is not None else default


def priority_pair_key(priority_a: int, priority_b: int) -> Tuple[int, int, int, int]:
    """
    Kriteria pemilihan pasangan prioritas jadwal terbaik secara holistik (bukan independen):
    1. Minimalkan nilai prioritas terburuk (minimax: max(prio_a, prio_b)).
    2. Minimalkan total prioritas (prio_a + prio_b).
    3. Pemecah seri prioritas A, lalu prioritas B.
    Peringkat angka lebih kecil = prioritas lebih tinggi (1 = Utama, 2 = Cadangan, 3 = Fleksibel).
    """
    return (
        max(priority_a, priority_b),
        priority_a + priority_b,
        priority_a,
        priority_b,
    )


DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _validate_common_slot(slot: Mapping[str, Any], for_partner: bool = False) -> None:
    """
    Memvalidasi integritas struktur dan nilai dari satu slot jadwal (common slot).
    Menolak slot dengan field tidak lengkap, format salah, durasi < 60 menit,
    atau prioritas tidak valid.
    """
    if not isinstance(slot, Mapping):
        raise ValueError("Setiap slot dalam common_slots harus berupa Mapping/dict")

    required_keys = ["date", "start_time", "end_time", "duration_minutes", "priority_a"]
    if for_partner:
        required_keys.append("priority_b")

    for key in required_keys:
        if key not in slot or slot[key] is None:
            raise ValueError(f"Slot jadwal tidak memiliki field wajib '{key}'")

    # Validasi format tanggal YYYY-MM-DD ketat (4 digit tahun, 2 digit bulan, 2 digit hari)
    date_val = slot["date"]
    if not isinstance(date_val, str) or not date_val.strip():
        raise ValueError("Field 'date' pada slot harus berupa string non-kosong")
    date_str = date_val.strip()
    if not DATE_PATTERN.fullmatch(date_str):
        raise ValueError(f"Format tanggal invalid: '{date_val}', harus persis YYYY-MM-DD dengan zero padding")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise ValueError(f"Tanggal kalender invalid: '{date_val}', harus YYYY-MM-DD")

    # Validasi format waktu HH:MM ketat (2 digit jam 00..23, 2 digit menit 00..59)
    start_val = slot["start_time"]
    end_val = slot["end_time"]
    if not isinstance(start_val, str) or not isinstance(end_val, str):
        raise ValueError("Field 'start_time' dan 'end_time' harus berupa string")

    start_str = start_val.strip()
    end_str = end_val.strip()
    if not TIME_PATTERN.fullmatch(start_str):
        raise ValueError(f"Format start_time invalid: '{start_val}', harus persis HH:MM dengan zero padding")
    if not TIME_PATTERN.fullmatch(end_str):
        raise ValueError(f"Format end_time invalid: '{end_val}', harus persis HH:MM dengan zero padding")

    sh, sm = map(int, start_str.split(":"))
    eh, em = map(int, end_str.split(":"))
    start_mins = sh * 60 + sm
    end_mins = eh * 60 + em
    calc_dur = end_mins - start_mins
    if calc_dur <= 0:
        raise ValueError(f"Waktu selesai '{end_str}' harus lebih besar dari waktu mulai '{start_str}'")

    # Validasi duration_minutes
    dur = slot["duration_minutes"]
    if isinstance(dur, bool) or not isinstance(dur, int):
        raise ValueError("Field 'duration_minutes' harus bertipe integer")
    if dur < 60:
        raise ValueError(f"Durasi irisan jadwal minimal 60 menit, diterima {dur} menit")
    if dur != calc_dur:
        raise ValueError(
            f"Field 'duration_minutes' ({dur}) tidak konsisten dengan selisih waktu ({calc_dur} menit)"
        )

    # Validasi priority_a
    prio_a = slot["priority_a"]
    if isinstance(prio_a, bool) or not isinstance(prio_a, int) or prio_a not in (1, 2, 3):
        raise ValueError(f"Nilai priority_a harus 1, 2, atau 3, diterima: {prio_a}")

    # Validasi priority_b
    prio_b = slot.get("priority_b")
    if for_partner:
        if isinstance(prio_b, bool) or not isinstance(prio_b, int) or prio_b not in (1, 2, 3):
            raise ValueError(f"Nilai priority_b harus 1, 2, atau 3 untuk partner slot, diterima: {prio_b}")
    else:
        if prio_b is not None:
            if isinstance(prio_b, bool) or not isinstance(prio_b, int) or prio_b not in (1, 2, 3):
                raise ValueError(f"Nilai priority_b harus 1, 2, atau 3 jika disediakan, diterima: {prio_b}")


def select_best_session_schedule(
    common_slots: Sequence[Mapping[str, Any]]
) -> Tuple[Dict[str, Any], float]:
    """
    Memilih jadwal terbaik untuk Study Session berdasarkan 4 tingkat penentu (tie-breaker):
    1. Date Score tertinggi.
    2. Durasi irisan terpanjang (duration_minutes lebih besar).
    3. Prioritas terbaik (priority_a terkecil: 1 > 2 > 3).
    4. Waktu paling awal (tanggal paling awal, jam mulai paling awal).
    """
    if not common_slots:
        raise ValueError("common_slots untuk Session tidak boleh kosong")

    evaluated_slots = []
    for slot in common_slots:
        _validate_common_slot(slot, for_partner=False)
        dur = slot["duration_minutes"]
        prio_a = slot["priority_a"]
        prio_b = slot.get("priority_b", 1)
        if prio_b is None:
            prio_b = 1

        p_score = calculate_session_priority_score(prio_a)
        l_score = calculate_duration_score(dur)
        d_score = calculate_date_score(p_score, l_score)

        sched_info = {
            "date": str(slot["date"]).strip(),
            "start_time": str(slot["start_time"]).strip(),
            "end_time": str(slot["end_time"]).strip(),
            "duration_minutes": dur,
            "priority_a": prio_a,
            "priority_b": prio_b,
            "priority_score": round(p_score, 4),
            "duration_score": round(l_score, 4),
            "date_score": round(d_score, 4),
        }
        # Sort key: (-d_score, -dur, prio_a, date, start_time)
        sort_key = (
            -d_score,
            -dur,
            prio_a,
            sched_info["date"],
            sched_info["start_time"],
        )
        evaluated_slots.append((sort_key, sched_info, d_score))

    evaluated_slots.sort(key=lambda item: item[0])
    best = evaluated_slots[0]
    return best[1], best[2]


def select_best_partner_schedule(
    common_slots: Sequence[Mapping[str, Any]]
) -> Tuple[Dict[str, Any], float]:
    """
    Memilih jadwal terbaik untuk Study Partner berdasarkan 4 tingkat penentu (tie-breaker):
    1. Date Score tertinggi.
    2. Durasi irisan terpanjang (duration_minutes lebih besar).
    3. Prioritas pasangan terbaik via priority_pair_key (minimax, sum, prio_a, prio_b).
    4. Waktu paling awal (tanggal paling awal, jam mulai paling awal).
    """
    if not common_slots:
        raise ValueError("common_slots untuk Partner tidak boleh kosong")

    evaluated_slots = []
    for slot in common_slots:
        _validate_common_slot(slot, for_partner=True)
        dur = slot["duration_minutes"]
        prio_a = slot["priority_a"]
        prio_b = slot["priority_b"]

        p_score = calculate_priority_score(prio_a, prio_b)
        l_score = calculate_duration_score(dur)
        d_score = calculate_date_score(p_score, l_score)

        sched_info = {
            "date": str(slot["date"]).strip(),
            "start_time": str(slot["start_time"]).strip(),
            "end_time": str(slot["end_time"]).strip(),
            "duration_minutes": dur,
            "priority_a": prio_a,
            "priority_b": prio_b,
            "priority_score": round(p_score, 4),
            "duration_score": round(l_score, 4),
            "date_score": round(d_score, 4),
        }
        # Sort key: (-d_score, -dur, priority_pair_key(prio_a, prio_b), date, start_time)
        sort_key = (
            -d_score,
            -dur,
            priority_pair_key(prio_a, prio_b),
            sched_info["date"],
            sched_info["start_time"],
        )
        evaluated_slots.append((sort_key, sched_info, d_score))

    evaluated_slots.sort(key=lambda item: item[0])
    best = evaluated_slots[0]
    return best[1], best[2]


def calculate_session_score(
    intent: Any,
    session: Any,
    common_slots: Sequence[Mapping[str, Any]],
    embedding_service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Menghitung skor kompatibilitas antara StudyIntent pengguna dengan kandidat StudySession.
    Memadukan lima dimensi penilaian: Topic, Goal, Style, Date (jadwal terbaik), dan Mode.
    Mengembalikan dictionary hasil penilaian kompatibel dengan schema MatchResult.
    """
    if intent is None:
        raise ValueError("Objek intent tidak boleh None")
    if session is None:
        raise ValueError("Objek session tidak boleh None")

    intent_id = _get_field(intent, "intent_id") or _get_field(intent, "id")
    if not intent_id:
        raise ValueError("Objek intent harus memiliki 'intent_id' atau 'id'")

    session_id = _get_field(session, "session_id") or _get_field(session, "id")
    if not session_id:
        raise ValueError("Objek session harus memiliki 'session_id' atau 'id'")

    # 1. Topic Similarity: intent.topics vs session.title (+ description)
    intent_topics = _get_field(intent, "topics")
    if not intent_topics or not str(intent_topics).strip():
        raise ValueError("StudyIntent harus memiliki 'topics' yang tidak kosong")
    intent_topic_text = str(intent_topics).strip()

    session_title = _get_field(session, "title")
    if not session_title or not str(session_title).strip():
        raise ValueError("StudySession harus memiliki 'title' yang tidak kosong")
    title_text = str(session_title).strip()

    session_desc = _get_field(session, "description")
    desc_text = str(session_desc).strip() if session_desc else ""
    session_topic_text = f"{title_text}. {desc_text}" if desc_text else title_text

    topic_score = calculate_topic_similarity(
        intent_topic_text, session_topic_text, embedding_service=embedding_service
    )

    # 2. Learning Goal Compatibility
    intent_goal = _get_field(intent, "learning_goal")
    session_goal = _get_field(session, "learning_goal")
    if not intent_goal:
        raise ValueError("StudyIntent harus memiliki 'learning_goal'")
    if not session_goal:
        raise ValueError("StudySession harus memiliki 'learning_goal'")
    goal_score = calculate_goal_compatibility(intent_goal, session_goal)

    # 3. Collaboration Style Compatibility
    intent_style = _get_field(intent, "collaboration_style")
    session_style = _get_field(session, "collaboration_style")
    if not intent_style:
        raise ValueError("StudyIntent harus memiliki 'collaboration_style'")
    if not session_style:
        raise ValueError("StudySession harus memiliki 'collaboration_style'")
    style_score = calculate_style_compatibility(intent_style, session_style)

    # 4. Learning Mode Compatibility
    intent_mode = _get_field(intent, "learning_mode")
    session_mode = _get_field(session, "learning_mode")
    if not intent_mode:
        raise ValueError("StudyIntent harus memiliki 'learning_mode'")
    if not session_mode:
        raise ValueError("StudySession harus memiliki 'learning_mode'")
    mode_score = calculate_mode_compatibility(intent_mode, session_mode)

    # 5. Date & Schedule Compatibility (Best Schedule Selection)
    selected_sched, date_score = select_best_session_schedule(common_slots)

    # 6. Compatibility Breakdown & Total Score
    breakdown = calculate_compatibility_breakdown(
        topic_score=topic_score,
        goal_score=goal_score,
        style_score=style_score,
        date_score=date_score,
        mode_score=mode_score,
    )

    return {
        "intent_id": str(intent_id),
        "candidate_type": "SESSION",
        "candidate_session_id": str(session_id),
        "total_score": breakdown["total_score"],
        "rounding_reconciliation": breakdown["rounding_reconciliation"],
        "components": breakdown["components"],
        "selected_schedule": selected_sched,
    }


def calculate_partner_score(
    intent_a: Any,
    intent_b: Any,
    common_slots: Sequence[Mapping[str, Any]],
    embedding_service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Menghitung skor kompatibilitas antara dua StudyIntent (pengguna dan kandidat partner).
    Memadukan lima dimensi penilaian: Topic, Goal, Style, Date (jadwal terbaik pasangan), dan Mode.
    Mengembalikan dictionary hasil penilaian kompatibel dengan schema MatchResult.
    """
    if intent_a is None:
        raise ValueError("Objek intent_a tidak boleh None")
    if intent_b is None:
        raise ValueError("Objek intent_b tidak boleh None")

    intent_a_id = _get_field(intent_a, "intent_id") or _get_field(intent_a, "id")
    if not intent_a_id:
        raise ValueError("Objek intent_a harus memiliki 'intent_id' atau 'id'")

    intent_b_id = _get_field(intent_b, "intent_id") or _get_field(intent_b, "id")
    if not intent_b_id:
        raise ValueError("Objek intent_b harus memiliki 'intent_id' atau 'id'")

    student_b_id = _get_field(intent_b, "student_id")
    if not student_b_id:
        cand_student = _get_field(intent_b, "student")
        if cand_student:
            student_b_id = _get_field(cand_student, "student_id") or _get_field(cand_student, "id")
    if not student_b_id:
        raise ValueError("Kandidat partner intent_b harus memiliki 'student_id'")

    # 1. Topic Similarity: intent_a.topics vs intent_b.topics
    topic_a = _get_field(intent_a, "topics")
    if not topic_a or not str(topic_a).strip():
        raise ValueError("StudyIntent intent_a harus memiliki 'topics' yang tidak kosong")
    topic_a_text = str(topic_a).strip()

    topic_b = _get_field(intent_b, "topics")
    if not topic_b or not str(topic_b).strip():
        raise ValueError("StudyIntent intent_b harus memiliki 'topics' yang tidak kosong")
    topic_b_text = str(topic_b).strip()

    topic_score = calculate_topic_similarity(
        topic_a_text, topic_b_text, embedding_service=embedding_service
    )

    # 2. Learning Goal Compatibility
    goal_a = _get_field(intent_a, "learning_goal")
    goal_b = _get_field(intent_b, "learning_goal")
    if not goal_a:
        raise ValueError("StudyIntent intent_a harus memiliki 'learning_goal'")
    if not goal_b:
        raise ValueError("StudyIntent intent_b harus memiliki 'learning_goal'")
    goal_score = calculate_goal_compatibility(goal_a, goal_b)

    # 3. Collaboration Style Compatibility
    style_a = _get_field(intent_a, "collaboration_style")
    style_b = _get_field(intent_b, "collaboration_style")
    if not style_a:
        raise ValueError("StudyIntent intent_a harus memiliki 'collaboration_style'")
    if not style_b:
        raise ValueError("StudyIntent intent_b harus memiliki 'collaboration_style'")
    style_score = calculate_style_compatibility(style_a, style_b)

    # 4. Learning Mode Compatibility
    mode_a = _get_field(intent_a, "learning_mode")
    mode_b = _get_field(intent_b, "learning_mode")
    if not mode_a:
        raise ValueError("StudyIntent intent_a harus memiliki 'learning_mode'")
    if not mode_b:
        raise ValueError("StudyIntent intent_b harus memiliki 'learning_mode'")
    mode_score = calculate_mode_compatibility(mode_a, mode_b)

    # 5. Date & Schedule Compatibility (Best Schedule Selection)
    selected_sched, date_score = select_best_partner_schedule(common_slots)

    # 6. Compatibility Breakdown & Total Score
    breakdown = calculate_compatibility_breakdown(
        topic_score=topic_score,
        goal_score=goal_score,
        style_score=style_score,
        date_score=date_score,
        mode_score=mode_score,
    )

    return {
        "intent_id": str(intent_a_id),
        "candidate_type": "PARTNER",
        "target_intent_id": str(intent_b_id),
        "student_id": str(student_b_id),
        "total_score": breakdown["total_score"],
        "rounding_reconciliation": breakdown["rounding_reconciliation"],
        "components": breakdown["components"],
        "selected_schedule": selected_sched,
    }


# ==============================================================================
# 6. TAHAP 15.6: CANDIDATE RANKING, DEDUPLICATION & EXPLANATION ENGINE
# ==============================================================================

INDONESIAN_MONTHS = [
    "",
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
]


def _format_indonesian_date(date_str: str) -> str:
    """
    Mengonversi tanggal format YYYY-MM-DD menjadi format teks Indonesia (contoh: 16 November 2026).
    Jika parsing gagal, mengembalikan string asli secara aman.
    """
    if not isinstance(date_str, str) or not date_str.strip():
        return str(date_str)
    parts = date_str.strip().split("-")
    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{day} {INDONESIAN_MONTHS[month]} {year}"
    return date_str.strip()


def _extract_and_validate_component_scores(candidate: Any) -> Dict[str, float]:
    """
    Memvalidasi dan mengekstrak skor aktual kelima komponen (topic, goal, style, date, mode).
    Menolak komponen yang hilang, bernilai None, boolean, NaN, Infinity, string,
    atau di luar rentang [0.0, 1.0].
    """
    comps = _get_field(candidate, "components")
    if comps is None or not isinstance(comps, (Mapping, object)):
        raise ValueError("Kandidat harus memiliki kamus 'components' yang memuat kelima komponen")

    required_components = ["topic", "goal", "style", "date", "mode"]
    clean_scores = {}

    for comp_name in required_components:
        comp_data = _get_field(comps, comp_name)
        if comp_data is None or not isinstance(comp_data, (Mapping, object)):
            raise ValueError(f"Komponen '{comp_name}' harus tersedia dalam candidate['components']")

        raw_score = _get_field(comp_data, "score")
        if raw_score is None:
            raise ValueError(f"Komponen '{comp_name}' harus memiliki field 'score'")
        if isinstance(raw_score, bool):
            raise ValueError(f"Score komponen '{comp_name}' tidak boleh bertipe boolean")
        if not isinstance(raw_score, (int, float, Decimal)):
            raise ValueError(f"Score komponen '{comp_name}' harus berupa numerik")

        try:
            val = float(raw_score)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"Score komponen '{comp_name}' tidak dapat dikonversi ke float atau melampaui batas (overflow)")

        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Score komponen '{comp_name}' harus bernilai berhingga (finite)")
        if not (0.0 <= val <= 1.0):
            raise ValueError(
                f"Score komponen '{comp_name}' ({val}) harus berada dalam rentang [0.0, 1.0]"
            )

        clean_scores[comp_name] = round(val, 4)

    return clean_scores


def generate_match_explanation(candidate: Mapping[str, Any]) -> str:
    """
    Menghasilkan ringkasan penjelasan rekomendasi dalam bahasa Indonesia secara rule-based
    dan deterministik berdasarkan komponen skor aktual (skala 0.0–1.0) dan jadwal bersama terbaik.
    Memvalidasi ketersediaan dan keabsahan kelima komponen.
    """
    if candidate is None or not isinstance(candidate, (Mapping, object)):
        raise ValueError("Kandidat untuk generate_match_explanation tidak boleh None")

    # Validasi kelima komponen wajib (menolak komponen hilang, NaN, dsb.)
    clean_scores = _extract_and_validate_component_scores(candidate)

    topic_sc = clean_scores["topic"]
    goal_sc = clean_scores["goal"]
    style_sc = clean_scores["style"]
    mode_sc = clean_scores["mode"]
    date_sc = clean_scores["date"]

    # Identifikasi frasa penilaian per komponen
    phrases = {}
    if topic_sc >= 0.85:
        phrases["topic"] = "Topik belajar sangat relevan"
    elif topic_sc >= 0.65:
        phrases["topic"] = "Topik belajar cukup relevan"

    if goal_sc >= 0.85:
        phrases["goal"] = "tujuan belajar selaras"
    elif goal_sc >= 0.65:
        phrases["goal"] = "tujuan belajar kompatibel"

    if style_sc >= 0.85:
        phrases["style"] = "gaya kolaborasi cocok"
    elif style_sc >= 0.65:
        phrases["style"] = "gaya kolaborasi saling melengkapi"

    if mode_sc >= 0.85:
        phrases["mode"] = "mode pembelajaran cocok"
    elif mode_sc >= 0.65:
        phrases["mode"] = "mode pembelajaran kompatibel"

    if date_sc >= 0.85:
        phrases["date"] = "preferensi jadwal sangat cocok"
    elif date_sc >= 0.65:
        phrases["date"] = "preferensi jadwal sesuai"

    # Komponen terurut berdasarkan nilai tertinggi secara deterministik
    component_priority = [
        ("topic", topic_sc),
        ("goal", goal_sc),
        ("style", style_sc),
        ("mode", mode_sc),
        ("date", date_sc),
    ]
    # Urutkan berdasarkan nilai tertinggi; jika seri, ikuti urutan deterministik di atas
    sorted_factors = sorted(component_priority, key=lambda item: item[1], reverse=True)

    # Ambil 2 hingga 3 faktor terkuat
    strong_factors = []
    for comp_name, score in sorted_factors:
        if comp_name in phrases:
            strong_factors.append(phrases[comp_name])
            if len(strong_factors) == 3:
                break

    # Jika tidak ada faktor >= 0.65, berikan penjelasan umum
    if not strong_factors:
        explanation_body = "Kecocokan sedang pada beberapa aspek kolaborasi"
    elif len(strong_factors) == 1:
        explanation_body = strong_factors[0]
    elif len(strong_factors) == 2:
        explanation_body = f"{strong_factors[0]} dan {strong_factors[1]}"
    else:
        explanation_body = f"{strong_factors[0]}, {strong_factors[1]}, dan {strong_factors[2]}"

    # Kapitalisasi huruf awal
    explanation_body = explanation_body[0].upper() + explanation_body[1:]

    # Tambahkan informasi jadwal bersama terbaik jika tersedia
    sched = _get_field(candidate, "selected_schedule")
    if sched:
        d_val = _get_field(sched, "date")
        s_val = _get_field(sched, "start_time")
        e_val = _get_field(sched, "end_time")
        if d_val and s_val and e_val:
            formatted_date = _format_indonesian_date(str(d_val))
            schedule_text = f" Jadwal bersama terbaik tersedia pada {formatted_date} pukul {s_val}–{e_val}."
            return f"{explanation_body}.{schedule_text}"

    return f"{explanation_body}."


def _validate_ranking_params(min_score: float, limit: Optional[int]) -> None:
    """
    Validasi parameter ambang batas minimum dan limit ranking:
    - min_score: float dalam rentang [0.0, 100.0], bukan bool, finite, aman terhadap OverflowError.
    - limit: integer positif (> 0) atau None, bukan bool.
    """
    if isinstance(min_score, bool):
        raise ValueError("min_score tidak boleh bertipe boolean")
    if not isinstance(min_score, (int, float, Decimal)):
        raise ValueError(f"min_score harus berupa angka, diterima: {type(min_score)}")
    try:
        ms = float(min_score)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("min_score tidak dapat dikonversi ke float atau melampaui batas (overflow)")
    if math.isnan(ms) or math.isinf(ms):
        raise ValueError("min_score harus bernilai berhingga (finite)")
    if ms < 0.0 or ms > 100.0:
        raise ValueError(f"min_score ({ms}) harus berada dalam rentang [0.0, 100.0]")

    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError(f"limit harus berupa integer atau None, diterima: {type(limit)}")
        if limit <= 0:
            raise ValueError(f"limit harus berupa integer positif (> 0), diterima: {limit}")


def _extract_and_validate_candidate(
    candidate: Any,
    expected_type: str,
) -> Dict[str, Any]:
    """
    Mengekstrak dan memvalidasi satu kandidat scoring:
    - Menjamin intent_id non-kosong.
    - Menjamin field identitas tersedia dan valid (candidate_session_id / student_id & target_intent_id).
    - Menjamin total_score berupa numerik finite [0.0, 100.0], bukan boolean, aman terhadap OverflowError.
    - Menjamin selected_schedule divalidasi ketat via _validate_common_slot (kalender valid, format waktu, durasi, prioritas).
    - Menjamin kelima komponen scoring (topic, goal, style, date, mode) tersedia dan valid.
    - Menghasilkan dictionary terisolasi (immutability terhadap objek input).
    """
    if candidate is None:
        raise ValueError("Objek kandidat tidak boleh None")
    if not isinstance(candidate, (Mapping, object)):
        raise ValueError("Kandidat harus berupa Mapping atau objek")

    # Validasi candidate_type jika disediakan
    c_type_raw = _get_field(candidate, "candidate_type")
    if c_type_raw:
        c_type = str(c_type_raw).strip().upper()
        if c_type != expected_type:
            raise ValueError(
                f"Kandidat memiliki candidate_type '{c_type}', diharapkan '{expected_type}'"
            )

    # Validasi intent_id non-kosong
    intent_id = _get_field(candidate, "intent_id")
    if not intent_id or not str(intent_id).strip():
        raise ValueError("Kandidat harus memiliki 'intent_id' non-kosong")
    intent_id_clean = str(intent_id).strip()

    # Validasi total_score
    score_raw = _get_field(candidate, "total_score")
    if score_raw is None or isinstance(score_raw, bool):
        raise ValueError("Kandidat harus memiliki 'total_score' numerik non-boolean")
    try:
        total_score = float(score_raw)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("total_score kandidat harus berupa numerik berhingga")
    if math.isnan(total_score) or math.isinf(total_score):
        raise ValueError("total_score kandidat harus berupa angka berhingga (finite)")
    if not (0.0 <= total_score <= 100.0):
        raise ValueError(f"total_score ({total_score}) harus berada dalam rentang [0.0, 100.0]")

    # Validasi selected_schedule secara ketat menggunakan _validate_common_slot
    sched_raw = _get_field(candidate, "selected_schedule")
    if sched_raw is None:
        raise ValueError("Kandidat harus memiliki 'selected_schedule'")

    if isinstance(sched_raw, Mapping):
        sched_dict = dict(sched_raw)
    elif hasattr(sched_raw, "__dict__"):
        sched_dict = {k: v for k, v in sched_raw.__dict__.items() if not k.startswith("_")}
    else:
        raise ValueError("selected_schedule harus berupa Mapping atau objek")

    is_partner = (expected_type == "PARTNER")
    # Memvalidasi date (kalender riil YYYY-MM-DD), start_time (HH:MM), end_time (HH:MM),
    # durasi >= 60 konsisten dengan selisih waktu, dan priority_a/b
    _validate_common_slot(sched_dict, for_partner=is_partner)

    # Validasi kelima komponen skor aktual
    clean_components = _extract_and_validate_component_scores(candidate)

    # Salin selected_schedule ke dictionary terisolasi
    dur = sched_dict["duration_minutes"]
    prio_a = sched_dict["priority_a"]
    prio_b = sched_dict.get("priority_b")
    if not is_partner and prio_b is None:
        prio_b = 1

    clean_sched = {
        "date": sched_dict["date"].strip(),
        "start_time": sched_dict["start_time"].strip(),
        "end_time": sched_dict["end_time"].strip(),
        "duration_minutes": dur,
        "priority_a": prio_a,
        "priority_b": prio_b,
    }
    for opt_k in ("priority_score", "duration_score", "date_score"):
        val_opt = sched_dict.get(opt_k)
        if val_opt is not None:
            clean_sched[opt_k] = val_opt

    # Rekonstruksi kamus komponen terisolasi dengan mempertahankan integritas kontribusi asli
    raw_comps = _get_field(candidate, "components")
    comps_dict = {}

    for comp_k in ("topic", "goal", "style", "date", "mode"):
        comp_data = _get_field(raw_comps, comp_k) if raw_comps is not None else None
        expected_weight = SCORING_WEIGHTS[comp_k]

        # Validasi ketat bobot: wajib numerik berhingga dan sesuai dengan SCORING_WEIGHTS resmi
        orig_weight = _get_field(comp_data, "weight") if comp_data is not None else None
        if orig_weight is not None:
            if isinstance(orig_weight, bool):
                raise ValueError(f"weight komponen '{comp_k}' tidak boleh bertipe boolean")
            try:
                w_val = float(orig_weight)
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"weight komponen '{comp_k}' harus berupa angka numerik berhingga")
            if math.isnan(w_val) or math.isinf(w_val):
                raise ValueError(f"weight komponen '{comp_k}' harus berupa angka berhingga (finite)")
            if not math.isclose(w_val, expected_weight, rel_tol=1e-5, abs_tol=1e-5):
                raise ValueError(
                    f"weight komponen '{comp_k}' ({w_val}) tidak sesuai dengan bobot resmi SCORING_WEIGHTS ({expected_weight})"
                )
            comp_weight = expected_weight
        else:
            comp_weight = expected_weight

        comp_entry: Dict[str, Any] = {
            "score": clean_components[comp_k],
            "weight": comp_weight,
        }

        # Pertahankan raw_contribution asli tanpa mutasi jika tersedia
        orig_raw = _get_field(comp_data, "raw_contribution") if comp_data is not None else None
        r_val = None
        if orig_raw is not None:
            if isinstance(orig_raw, bool):
                raise ValueError(f"raw_contribution komponen '{comp_k}' tidak boleh bertipe boolean")
            try:
                r_val = float(orig_raw)
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"raw_contribution komponen '{comp_k}' harus berupa angka numerik berhingga")
            if math.isnan(r_val) or math.isinf(r_val):
                raise ValueError(f"raw_contribution komponen '{comp_k}' harus berupa angka berhingga (finite)")
            comp_entry["raw_contribution"] = round(r_val, 4)

        # Pertahankan base_contribution (nilai kontribusi 2 desimal sebelum rekonsiliasi)
        orig_base = _get_field(comp_data, "base_contribution") if comp_data is not None else None
        b_val = None
        if orig_base is not None:
            if isinstance(orig_base, bool):
                raise ValueError(f"base_contribution komponen '{comp_k}' tidak boleh bertipe boolean")
            try:
                b_val = float(orig_base)
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"base_contribution komponen '{comp_k}' harus berupa angka numerik berhingga")
            if math.isnan(b_val) or math.isinf(b_val):
                raise ValueError(f"base_contribution komponen '{comp_k}' harus berupa angka berhingga (finite)")
            comp_entry["base_contribution"] = round(b_val, 2)
        elif r_val is not None:
            base_dec = Decimal(str(r_val)).quantize(Decimal("1").scaleb(-2), rounding=ROUND_HALF_UP)
            comp_entry["base_contribution"] = float(base_dec)

        # Pertahankan rounding_adjustment asli jika tersedia
        orig_adj = _get_field(comp_data, "rounding_adjustment") if comp_data is not None else None
        a_val = None
        if orig_adj is not None:
            if isinstance(orig_adj, bool):
                raise ValueError(f"rounding_adjustment komponen '{comp_k}' tidak boleh bertipe boolean")
            try:
                a_val = float(orig_adj)
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"rounding_adjustment komponen '{comp_k}' harus berupa angka numerik berhingga")
            if math.isnan(a_val) or math.isinf(a_val):
                raise ValueError(f"rounding_adjustment komponen '{comp_k}' harus berupa angka berhingga (finite)")
            comp_entry["rounding_adjustment"] = round(a_val, 4)

        # Pertahankan / Rekonstruksi contribution
        orig_contrib = _get_field(comp_data, "contribution") if comp_data is not None else None
        if orig_contrib is not None:
            if isinstance(orig_contrib, bool):
                raise ValueError(f"contribution komponen '{comp_k}' tidak boleh bertipe boolean")
            try:
                c_val = float(orig_contrib)
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"contribution komponen '{comp_k}' harus berupa angka numerik berhingga")
            if math.isnan(c_val) or math.isinf(c_val):
                raise ValueError(f"contribution komponen '{comp_k}' harus berupa angka berhingga (finite)")
            comp_entry["contribution"] = round(c_val, 2)
        elif "base_contribution" in comp_entry and "rounding_adjustment" in comp_entry:
            # Rekonstruksi presisi Decimal menggunakan base_contribution dan rounding_adjustment tanpa risiko rounding drift
            base_d = Decimal(str(comp_entry["base_contribution"])).quantize(Decimal("1").scaleb(-2))
            adj_d = Decimal(str(comp_entry["rounding_adjustment"])).quantize(Decimal("1").scaleb(-2))
            comp_entry["contribution"] = float(base_d + adj_d)
        else:
            raise ValueError(
                f"Komponen '{comp_k}' harus memiliki 'contribution' atau pasangan metadata rekonsiliasi yang lengkap"
            )

        # Validasi konsistensi per komponen: contribution == base_contribution + rounding_adjustment (P1 & P2)
        if "base_contribution" in comp_entry and "rounding_adjustment" in comp_entry:
            expected_c = Decimal(str(comp_entry["base_contribution"])).quantize(Decimal("1").scaleb(-2)) + \
                         Decimal(str(comp_entry["rounding_adjustment"])).quantize(Decimal("1").scaleb(-2))
            actual_c = Decimal(str(comp_entry["contribution"])).quantize(Decimal("1").scaleb(-2))
            if actual_c != expected_c:
                raise ValueError(
                    f"Inkonsistensi kontribusi komponen '{comp_k}': contribution ({actual_c}) "
                    f"tidak sesuai dengan base_contribution ({comp_entry['base_contribution']}) + "
                    f"rounding_adjustment ({comp_entry['rounding_adjustment']}) = {expected_c}"
                )

        comps_dict[comp_k] = comp_entry

    # Validasi ketat rounding_reconciliation (tidak boleh silent fallback jika input invalid)
    rec_raw = _get_field(candidate, "rounding_reconciliation")
    has_rec = (rec_raw is not None)
    if not has_rec:
        rec_val = 0.0
    elif isinstance(rec_raw, bool):
        raise ValueError("rounding_reconciliation tidak boleh bertipe boolean")
    elif not isinstance(rec_raw, (int, float, Decimal, str)):
        raise ValueError(f"rounding_reconciliation harus berupa angka numerik, diterima: {type(rec_raw).__name__}")
    else:
        try:
            rec_val = float(rec_raw)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"rounding_reconciliation tidak dapat dikonversi ke float atau mengalami overflow: {rec_raw}")
        if math.isnan(rec_val) or math.isinf(rec_val):
            raise ValueError("rounding_reconciliation harus berupa angka berhingga (finite)")
        if not (-1.0 <= rec_val <= 1.0):
            raise ValueError(f"rounding_reconciliation ({rec_val}) harus berada dalam rentang [-1.0, 1.0]")

    # Aturan All-or-None untuk metadata rekonsiliasi (P2)
    comp_has_adj = [("rounding_adjustment" in c) for c in comps_dict.values()]
    num_adj = sum(comp_has_adj)

    # 1. Jika rounding_reconciliation disediakan oleh kandidat, kelima komponen WAJIB memuat rounding_adjustment
    if has_rec and num_adj < 5:
        raise ValueError(
            f"Metadata rekonsiliasi tidak lengkap: 'rounding_reconciliation' ({rec_val}) disediakan, "
            f"tetapi hanya {num_adj}/5 komponen yang memuat 'rounding_adjustment'"
        )

    # 2. Metadata rounding_adjustment tidak boleh parsial (harus 5 komponen atau 0)
    if 0 < num_adj < 5:
        raise ValueError(
            f"Metadata rounding_adjustment parsial tidak diizinkan: {num_adj}/5 komponen memuat penyesuaian. "
            "Seluruh 5 komponen wajib memuat 'rounding_adjustment' atau tidak sama sekali"
        )

    # Validasi silang menggunakan aritmetika Decimal: sum(contribution) == total_score
    quantum_2 = Decimal("1").scaleb(-2)
    dec_total = Decimal(str(round(total_score, 2))).quantize(quantum_2)
    dec_sum_contrib = sum(
        Decimal(str(c["contribution"])).quantize(quantum_2)
        for c in comps_dict.values()
    ).quantize(quantum_2)

    if dec_sum_contrib != dec_total:
        raise ValueError(
            f"Inkonsistensi breakdown: jumlah kontribusi ({dec_sum_contrib}) "
            f"tidak sama dengan total_score ({dec_total})"
        )

    # Validasi konsistensi jumlah penyesuaian komponen dengan rounding_reconciliation (jika lengkap 5 komponen)
    if num_adj == 5:
        dec_sum_adj = sum(
            Decimal(str(c["rounding_adjustment"])).quantize(quantum_2)
            for c in comps_dict.values()
        ).quantize(quantum_2)
        if has_rec:
            dec_rec = Decimal(str(round(rec_val, 2))).quantize(quantum_2)
            if dec_sum_adj != dec_rec:
                raise ValueError(
                    f"Inkonsistensi rekonsiliasi: jumlah rounding_adjustment ({dec_sum_adj}) "
                    f"tidak sama dengan rounding_reconciliation ({dec_rec})"
                )
        else:
            rec_val = float(dec_sum_adj)

    if expected_type == "SESSION":
        sess_id = _get_field(candidate, "candidate_session_id") or _get_field(candidate, "session_id")
        if not sess_id or not str(sess_id).strip():
            raise ValueError("Kandidat SESSION harus memiliki 'candidate_session_id' non-kosong")
        cand_id = str(sess_id).strip()

        clean_item = {
            "intent_id": intent_id_clean,
            "candidate_type": "SESSION",
            "candidate_session_id": cand_id,
            "total_score": round(total_score, 2),
            "rounding_reconciliation": round(rec_val, 4),
            "components": comps_dict,
            "selected_schedule": clean_sched,
        }
        exp = _get_field(candidate, "explanation")
        if exp:
            clean_item["explanation"] = str(exp).strip()
        return clean_item

    else:  # PARTNER
        std_id = _get_field(candidate, "student_id")
        if not std_id or not str(std_id).strip():
            raise ValueError("Kandidat PARTNER harus memiliki 'student_id' non-kosong")
        student_id = str(std_id).strip()

        tgt_id = _get_field(candidate, "target_intent_id") or _get_field(candidate, "intent_b_id")
        if not tgt_id or not str(tgt_id).strip():
            raise ValueError("Kandidat PARTNER harus memiliki 'target_intent_id' non-kosong")
        target_intent_id = str(tgt_id).strip()

        clean_item = {
            "intent_id": intent_id_clean,
            "candidate_type": "PARTNER",
            "student_id": student_id,
            "target_intent_id": target_intent_id,
            "total_score": round(total_score, 2),
            "rounding_reconciliation": round(rec_val, 4),
            "components": comps_dict,
            "selected_schedule": clean_sched,
        }
        exp = _get_field(candidate, "explanation")
        if exp:
            clean_item["explanation"] = str(exp).strip()
        return clean_item


def rank_session_candidates(
    session_scores: Sequence[Any],
    min_score: float = 0.0,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Menyusun peringkat kandidat Study Session berdasarkan lima tingkat hierarki penilaian:
    1. total_score tertinggi (skor kompatibilitas)
    2. duration_minutes terpanjang
    3. priority_a terbaik (1 > 2 > 3)
    4. date dan start_time paling awal (kronologis kalender)
    5. candidate_session_id alfabetis deterministik

    Deduplikasi: satu sesi hanya muncul satu kali dalam rekomendasi akhir.
    Alur: Validasi -> Filter min_score -> Deterministic Sort -> Deduplicate -> Assign Rank & Explanation -> Limit.
    """
    _validate_ranking_params(min_score, limit)
    if session_scores is None:
        raise ValueError("session_scores tidak boleh None")
    if not isinstance(session_scores, Sequence):
        raise ValueError("session_scores harus berupa sequence/list")

    # 1. Validasi & ekstraksi kandidat ke struktur bersih terisolasi
    validated = [
        _extract_and_validate_candidate(item, expected_type="SESSION")
        for item in session_scores
    ]

    # 2. Filter min_score
    filtered = [
        item for item in validated
        if item["total_score"] >= float(min_score)
    ]

    # 3. Deterministic Sorting (5 Tingkat)
    def session_sort_key(c: Dict[str, Any]) -> Tuple[float, int, int, str, str, str]:
        sched = c["selected_schedule"]
        return (
            -float(c["total_score"]),
            -int(sched["duration_minutes"]),
            int(sched["priority_a"]),
            str(sched["date"]),
            str(sched["start_time"]),
            str(c["candidate_session_id"]),
        )

    filtered.sort(key=session_sort_key)

    # 4. Deduplikasi berdasarkan candidate_session_id
    seen_session_ids = set()
    deduped = []
    for item in filtered:
        sid = item["candidate_session_id"]
        if sid not in seen_session_ids:
            seen_session_ids.add(sid)
            deduped.append(item)

    # 5. Penetapan rank & penjelasan (explanation)
    for idx, item in enumerate(deduped):
        item["rank"] = idx + 1
        if "explanation" not in item:
            item["explanation"] = generate_match_explanation(item)

    # 6. Penerapan limit
    if limit is not None:
        deduped = deduped[:limit]

    return deduped


def rank_partner_candidates(
    partner_scores: Sequence[Any],
    min_score: float = 0.0,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Menyusun peringkat calon partner (Study Intent mahasiswa lain) berdasarkan lima tingkat hierarki:
    1. total_score tertinggi (skor kompatibilitas)
    2. duration_minutes terpanjang
    3. priority_pair_key(priority_a, priority_b) terbaik (minimax holistik)
    4. date dan start_time paling awal (kronologis kalender)
    5. target_intent_id alfabetis deterministik

    Deduplikasi: satu mahasiswa (student_id) hanya muncul satu kali dengan Study Intent terbaiknya.
    Alur: Validasi -> Filter min_score -> Deterministic Sort -> Deduplicate Student -> Assign Rank & Explanation -> Limit.
    """
    _validate_ranking_params(min_score, limit)
    if partner_scores is None:
        raise ValueError("partner_scores tidak boleh None")
    if not isinstance(partner_scores, Sequence):
        raise ValueError("partner_scores harus berupa sequence/list")

    # 1. Validasi & ekstraksi kandidat ke struktur bersih terisolasi
    validated = [
        _extract_and_validate_candidate(item, expected_type="PARTNER")
        for item in partner_scores
    ]

    # 2. Filter min_score
    filtered = [
        item for item in validated
        if item["total_score"] >= float(min_score)
    ]

    # 3. Deterministic Sorting (5 Tingkat)
    def partner_sort_key(c: Dict[str, Any]) -> Tuple[float, int, Tuple[int, int, int, int], str, str, str]:
        sched = c["selected_schedule"]
        prio_a = int(sched["priority_a"])
        prio_b = int(sched["priority_b"])
        return (
            -float(c["total_score"]),
            -int(sched["duration_minutes"]),
            priority_pair_key(prio_a, prio_b),
            str(sched["date"]),
            str(sched["start_time"]),
            str(c["target_intent_id"]),
        )

    filtered.sort(key=partner_sort_key)

    # 4. Deduplikasi berdasarkan student_id
    seen_student_ids = set()
    deduped = []
    for item in filtered:
        sid = item["student_id"]
        if sid not in seen_student_ids:
            seen_student_ids.add(sid)
            deduped.append(item)

    # 5. Penetapan rank & penjelasan (explanation)
    for idx, item in enumerate(deduped):
        item["rank"] = idx + 1
        if "explanation" not in item:
            item["explanation"] = generate_match_explanation(item)

    # 6. Penerapan limit
    if limit is not None:
        deduped = deduped[:limit]

    return deduped


def rank_candidates(
    candidates: Sequence[Any],
    candidate_type: Optional[str] = None,
    min_score: float = 0.0,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Dispatcher fungsi ranking kandidat generik.
    Menerima list kandidat bertipe SESSION atau PARTNER, mendeteksi tipe kandidat
    jika candidate_type tidak ditentukan, dan mendelegasikan ke fungsi ranking spesifik.
    Selalu memvalidasi parameter min_score dan limit terlebih dahulu meskipun candidates kosong.
    """
    _validate_ranking_params(min_score, limit)
    if candidates is None:
        raise ValueError("candidates tidak boleh None")
    if not isinstance(candidates, Sequence):
        raise ValueError("candidates harus berupa sequence/list")
    if not candidates:
        return []

    c_type = candidate_type
    if not c_type:
        first = candidates[0]
        c_type = _get_field(first, "candidate_type")
        if not c_type:
            if _get_field(first, "candidate_session_id") or _get_field(first, "session_id"):
                c_type = "SESSION"
            elif _get_field(first, "student_id") or _get_field(first, "target_intent_id"):
                c_type = "PARTNER"

    if not c_type:
        raise ValueError("candidate_type tidak dapat dideteksi secara otomatis dari candidates")

    c_type_clean = str(c_type).strip().upper()
    if c_type_clean == "SESSION":
        return rank_session_candidates(candidates, min_score=min_score, limit=limit)
    elif c_type_clean == "PARTNER":
        return rank_partner_candidates(candidates, min_score=min_score, limit=limit)
    else:
        raise ValueError(f"candidate_type '{c_type}' tidak valid, harus 'SESSION' atau 'PARTNER'")


def format_match_result_payload(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Mengonversi hasil penilaian kandidat (baik Session maupun Partner) menjadi
    dictionary payload yang valid untuk skema Pydantic MatchResultCreate.
    Hanya menyertakan field resmi: intent_id, candidate_type, candidate_session_id,
    target_intent_id, compatibility_score, breakdown, explanation.
    Memvalidasi secara ketat bahwa kelima komponen tersedia dan valid.
    """
    if candidate is None:
        raise ValueError("candidate tidak boleh None")
    if not isinstance(candidate, (Mapping, object)):
        raise ValueError("candidate harus berupa Mapping atau objek")

    c_type_raw = _get_field(candidate, "candidate_type")
    if not c_type_raw or not isinstance(c_type_raw, str):
        raise ValueError("candidate harus memiliki 'candidate_type' berupa string")
    c_type = c_type_raw.strip().upper()
    if c_type not in ("SESSION", "PARTNER"):
        raise ValueError(f"candidate_type '{c_type}' tidak valid, harus 'SESSION' atau 'PARTNER'")

    intent_id = _get_field(candidate, "intent_id")
    if not intent_id or not str(intent_id).strip():
        raise ValueError("candidate harus memiliki 'intent_id' non-kosong")

    total_score = _get_field(candidate, "total_score")
    if total_score is None or isinstance(total_score, bool):
        raise ValueError("candidate harus memiliki 'total_score' numerik non-boolean")
    try:
        score_val = float(total_score)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("total_score harus berupa angka berhingga")
    if math.isnan(score_val) or math.isinf(score_val):
        raise ValueError("total_score harus berupa angka berhingga (finite)")
    if not (0.0 <= score_val <= 100.0):
        raise ValueError(f"total_score ({score_val}) harus berada dalam rentang [0.0, 100.0]")

    if c_type == "SESSION":
        sess_id = _get_field(candidate, "candidate_session_id") or _get_field(candidate, "session_id")
        if not sess_id or not str(sess_id).strip():
            raise ValueError("Kandidat SESSION harus memiliki 'candidate_session_id' non-kosong")
        cand_sess_id = str(sess_id).strip()
        target_intent_id = None
    else:  # PARTNER
        tgt_id = _get_field(candidate, "target_intent_id") or _get_field(candidate, "intent_b_id")
        if not tgt_id or not str(tgt_id).strip():
            raise ValueError("Kandidat PARTNER harus memiliki 'target_intent_id' non-kosong")
        target_intent_id = str(tgt_id).strip()
        cand_sess_id = None

    # Validasi ketat kelima komponen: missing / None / NaN / Inf / boolean / out-of-range ditolak
    clean_scores = _extract_and_validate_component_scores(candidate)
    breakdown = {
        "topic_similarity": clean_scores["topic"],
        "goal_compatibility": clean_scores["goal"],
        "style_compatibility": clean_scores["style"],
        "date_preference": clean_scores["date"],
        "mode_compatibility": clean_scores["mode"],
    }

    explanation = _get_field(candidate, "explanation")
    if not explanation or not str(explanation).strip():
        explanation = generate_match_explanation(candidate)
    else:
        explanation = str(explanation).strip()

    return {
        "intent_id": str(intent_id).strip(),
        "candidate_type": c_type,
        "candidate_session_id": cand_sess_id,
        "target_intent_id": target_intent_id,
        "compatibility_score": round(score_val, 2),
        "breakdown": breakdown,
        "explanation": explanation,
    }



