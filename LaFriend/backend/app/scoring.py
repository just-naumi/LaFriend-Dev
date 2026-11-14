# scoring.py - Modul Soft Constraint Scoring & Compatibility Ranking Engine (Day 15)
# Bertanggung jawab menghitung tingkat kecocokan kandidat yang lolos Hard Constraint Day 14.

import re
import math
from typing import Any, Dict, List, Optional, Tuple, Union

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


