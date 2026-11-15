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


def _round_half_up(val: float, decimals: int = 2) -> float:
    """Pembulatan presisi desimal standar (ROUND_HALF_UP) untuk mengatasi artefak biner IEEE 754."""
    s_val = f"{val:.8f}"
    d = Decimal(s_val).quantize(Decimal("10") ** -decimals, rounding=ROUND_HALF_UP)
    return float(d)


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
    - Skor dibatasi pada rentang [0.0, 100.0] dan dibulatkan 2 desimal (round half-up).
    """
    t = validate_component_score(topic_score, "topic")
    g = validate_component_score(goal_score, "goal")
    s = validate_component_score(style_score, "style")
    d = validate_component_score(date_score, "date")
    m = validate_component_score(mode_score, "mode")

    raw_score = 100.0 * (
        WEIGHT_TOPIC * t +
        WEIGHT_GOAL * g +
        WEIGHT_STYLE * s +
        WEIGHT_DATE * d +
        WEIGHT_MODE * m
    )
    clamped = max(0.0, min(100.0, raw_score))
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
    - rounding_reconciliation: selisih total pembulatan yang dialokasikan (+/- 0.01 atau 0.00)
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

    raw_contribs = {
        "topic": 100.0 * WEIGHT_TOPIC * t,
        "goal": 100.0 * WEIGHT_GOAL * g,
        "style": 100.0 * WEIGHT_STYLE * s,
        "date": 100.0 * WEIGHT_DATE * d,
        "mode": 100.0 * WEIGHT_MODE * m,
    }

    total_score = calculate_compatibility_score(t, g, s, d, m)

    # Pembulatan awal 2 desimal dengan ROUND_HALF_UP
    rounded_contribs = {k: _round_half_up(v, 2) for k, v in raw_contribs.items()}
    adjustments = {k: 0.0 for k in raw_contribs}

    diff = round(total_score - sum(rounded_contribs.values()), 2)

    # Jika terdapat selisih pembulatan, lakukan alokasi sisa terbesar (Largest Remainder Reconciliation)
    if not math.isclose(diff, 0.0, abs_tol=1e-5):
        steps = int(round(diff * 100))
        sign = 1 if steps > 0 else -1
        # Urutkan secara deterministik berdasarkan delta pembulatan terbesar, lalu bobot komponen
        component_keys = ["topic", "goal", "style", "date", "mode"]
        order = sorted(
            component_keys,
            key=lambda k: (
                (raw_contribs[k] - rounded_contribs[k]) if sign > 0 else (rounded_contribs[k] - raw_contribs[k]),
                SCORING_WEIGHTS[k]
            ),
            reverse=True
        )
        for i in range(abs(steps)):
            target_key = order[i % len(order)]
            adj = round(sign * 0.01, 2)
            rounded_contribs[target_key] = round(rounded_contribs[target_key] + adj, 2)
            adjustments[target_key] = round(adjustments[target_key] + adj, 2)

    return {
        "total_score": total_score,
        "rounding_reconciliation": round(diff, 2),
        "components": {
            "topic": {
                "score": round(t, 4),
                "weight": WEIGHT_TOPIC,
                "raw_contribution": round(raw_contribs["topic"], 4),
                "contribution": rounded_contribs["topic"],
                "rounding_adjustment": adjustments["topic"],
            },
            "goal": {
                "score": round(g, 4),
                "weight": WEIGHT_GOAL,
                "raw_contribution": round(raw_contribs["goal"], 4),
                "contribution": rounded_contribs["goal"],
                "rounding_adjustment": adjustments["goal"],
            },
            "style": {
                "score": round(s, 4),
                "weight": WEIGHT_STYLE,
                "raw_contribution": round(raw_contribs["style"], 4),
                "contribution": rounded_contribs["style"],
                "rounding_adjustment": adjustments["style"],
            },
            "date": {
                "score": round(d, 4),
                "weight": WEIGHT_DATE,
                "raw_contribution": round(raw_contribs["date"], 4),
                "contribution": rounded_contribs["date"],
                "rounding_adjustment": adjustments["date"],
            },
            "mode": {
                "score": round(m, 4),
                "weight": WEIGHT_MODE,
                "raw_contribution": round(raw_contribs["mode"], 4),
                "contribution": rounded_contribs["mode"],
                "rounding_adjustment": adjustments["mode"],
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

    # Validasi format tanggal YYYY-MM-DD
    date_val = slot["date"]
    if not isinstance(date_val, str) or not date_val.strip():
        raise ValueError("Field 'date' pada slot harus berupa string non-kosong")
    try:
        datetime.strptime(date_val.strip(), "%Y-%m-%d")
    except (ValueError, TypeError):
        raise ValueError(f"Format tanggal invalid: '{date_val}', harus YYYY-MM-DD")

    # Validasi format waktu HH:MM
    start_str = slot["start_time"]
    end_str = slot["end_time"]
    if not isinstance(start_str, str) or not isinstance(end_str, str):
        raise ValueError("Field 'start_time' dan 'end_time' harus berupa string")

    try:
        s_parts = start_str.strip().split(":")
        e_parts = end_str.strip().split(":")
        if len(s_parts) != 2 or len(e_parts) != 2:
            raise ValueError
        sh, sm = int(s_parts[0]), int(s_parts[1])
        eh, em = int(e_parts[0]), int(e_parts[1])
        if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
            raise ValueError
    except Exception:
        raise ValueError(f"Format waktu invalid: '{start_str}' atau '{end_str}', harus HH:MM")

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


