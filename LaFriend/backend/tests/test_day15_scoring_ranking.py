# test_day15_scoring_ranking.py - Automated Test Suite untuk Scoring Engine LaFriend (Day 15)
# Tahap 15.1: Canonicalizer, Matriks Kompatibilitas, Priority, Duration, Date Scoring
# Tahap 15.2: Topic Similarity (Normalisasi, Tokenisasi, Jaccard, Vector Validation, Cosine, Fallback)

import sys
import math
from pathlib import Path

# Setup path agar dapat mengimpor app
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.scoring import (
    CANONICAL_LEARNING_GOALS,
    CANONICAL_COLLABORATION_STYLES,
    GOAL_COMPATIBILITY,
    STYLE_COMPATIBILITY,
    normalize_learning_goal,
    normalize_collaboration_style,
    calculate_goal_compatibility,
    calculate_style_compatibility,
    calculate_priority_score,
    calculate_session_priority_score,
    calculate_duration_score,
    calculate_date_score,
    # Tahap 15.2
    normalize_topic_text,
    tokenize_topic,
    calculate_jaccard_similarity,
    validate_embedding_vector,
    calculate_cosine_similarity,
    calculate_topic_similarity,
    calculate_topic_similarity_detailed,
    # Tahap 15.3
    CANONICAL_LEARNING_MODES,
    LEARNING_MODE_ALIASES,
    MODE_COMPATIBILITY,
    normalize_learning_mode,
    calculate_mode_compatibility,
    # Tahap 15.4
    WEIGHT_TOPIC,
    WEIGHT_GOAL,
    WEIGHT_STYLE,
    WEIGHT_DATE,
    WEIGHT_MODE,
    SCORING_WEIGHTS,
    validate_component_score,
    calculate_compatibility_score,
    calculate_compatibility_breakdown,
)

passed_count = 0
total_count = 0


def report(name: str, condition: bool, details: str = ""):
    global passed_count, total_count
    total_count += 1
    if condition:
        passed_count += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} - {details}")
        assert condition, f"{name}: {details}"


# ==============================================================================
# PYTEST-COMPATIBLE TEST FUNCTIONS (Catatan Audit 1)
# ==============================================================================

def test_canonicalizers():
    """Menguji normalisasi, idempotensi, dan penolakan nilai tak dikenal."""
    print("\n--- SUITE 1: Canonicalizer Normalization & Idempotence ---")
    for cg in CANONICAL_LEARNING_GOALS:
        res = normalize_learning_goal(cg)
        report(f"Goal: Kanonis '{cg}' dipertahankan", res == cg)
        report(f"Goal: Idempoten untuk '{cg}'", normalize_learning_goal(res) == cg)

    report("Goal: Alias 'CONCEPT' -> 'UNDERSTAND'", normalize_learning_goal("CONCEPT") == "UNDERSTAND")
    report("Goal: Alias 'EXAM_PREP' -> 'EXAM_PREPARATION'", normalize_learning_goal("EXAM_PREP") == "EXAM_PREPARATION")
    report("Goal: Alias 'DISCUSSION' -> 'KNOWLEDGE_SHARING'", normalize_learning_goal("DISCUSSION") == "KNOWLEDGE_SHARING")
    report("Goal: Case insensitivity 'concept' -> 'UNDERSTAND'", normalize_learning_goal("concept") == "UNDERSTAND")
    report("Goal: Whitespace stripped '  exam_prep  ' -> 'EXAM_PREPARATION'", normalize_learning_goal("  exam_prep  ") == "EXAM_PREPARATION")

    for bad_goal in ["UNKNOWN_GOAL", "", "   ", None, 123, []]:
        try:
            normalize_learning_goal(bad_goal)
            report(f"Goal: Tolak nilai invalid ({bad_goal})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Goal: Tolak nilai invalid ({bad_goal})", True)

    for cs in CANONICAL_COLLABORATION_STYLES:
        res = normalize_collaboration_style(cs)
        report(f"Style: Kanonis '{cs}' dipertahankan", res == cs)
        report(f"Style: Idempoten untuk '{cs}'", normalize_collaboration_style(res) == cs)

    report("Style: Alias 'TEACHING' -> 'PEER_TUTORING'", normalize_collaboration_style("TEACHING") == "PEER_TUTORING")
    report("Style: Alias 'SILENT' -> 'FOCUS_STUDY'", normalize_collaboration_style("SILENT") == "FOCUS_STUDY")
    report("Style: DISCUSSION pada style tetap 'DISCUSSION'", normalize_collaboration_style("DISCUSSION") == "DISCUSSION")
    report("Style: Case insensitivity 'teaching' -> 'PEER_TUTORING'", normalize_collaboration_style("teaching") == "PEER_TUTORING")
    report("Style: Whitespace stripped '  silent  ' -> 'FOCUS_STUDY'", normalize_collaboration_style("  silent  ") == "FOCUS_STUDY")

    for bad_style in ["RANDOM_STYLE", "", "   ", None, 456, {}]:
        try:
            normalize_collaboration_style(bad_style)
            report(f"Style: Tolak nilai invalid ({bad_style})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Style: Tolak nilai invalid ({bad_style})", True)


def test_compatibility_matrices_structure_and_bounds():
    """Menguji struktur kelengkapan, simetri, diagonal, dan bounds matriks."""
    print("\n--- SUITE 2: Compatibility Matrices Structure & Bounds ---")
    for g1 in CANONICAL_LEARNING_GOALS:
        report(f"Goal Matrix: '{g1}' memiliki baris lengkap", set(GOAL_COMPATIBILITY[g1].keys()) == CANONICAL_LEARNING_GOALS)
        report(f"Goal Matrix: Diagonal G('{g1}', '{g1}') == 1.00", GOAL_COMPATIBILITY[g1][g1] == 1.00)

    goal_symmetric = True
    goal_bounds = True
    for g1 in CANONICAL_LEARNING_GOALS:
        for g2 in CANONICAL_LEARNING_GOALS:
            v1 = GOAL_COMPATIBILITY[g1][g2]
            v2 = GOAL_COMPATIBILITY[g2][g1]
            if v1 != v2:
                goal_symmetric = False
            if not (0.0 <= v1 <= 1.0):
                goal_bounds = False
    report("Goal Matrix: Simetris sempurna G(A, B) == G(B, A)", goal_symmetric)
    report("Goal Matrix: Seluruh nilai berada dalam rentang [0.0, 1.0]", goal_bounds)

    for s1 in CANONICAL_COLLABORATION_STYLES:
        report(f"Style Matrix: '{s1}' memiliki baris lengkap", set(STYLE_COMPATIBILITY[s1].keys()) == CANONICAL_COLLABORATION_STYLES)
        report(f"Style Matrix: Diagonal S('{s1}', '{s1}') == 1.00", STYLE_COMPATIBILITY[s1][s1] == 1.00)

    style_symmetric = True
    style_bounds = True
    for s1 in CANONICAL_COLLABORATION_STYLES:
        for s2 in CANONICAL_COLLABORATION_STYLES:
            v1 = STYLE_COMPATIBILITY[s1][s2]
            v2 = STYLE_COMPATIBILITY[s2][s1]
            if v1 != v2:
                style_symmetric = False
            if not (0.0 <= v1 <= 1.0):
                style_bounds = False
    report("Style Matrix: Simetris sempurna S(A, B) == S(B, A)", style_symmetric)
    report("Style Matrix: Seluruh nilai berada dalam rentang [0.0, 1.0]", style_bounds)


def test_goal_compatibility_expected_values():
    """Memverifikasi seluruh 36 nilai pada Goal Matrix terhadap spesifikasi final (Catatan Audit 2)."""
    print("\n--- SUITE 2B: Goal Matrix 36/36 Explicit Expected Values ---")
    expected_goals = {
        "UNDERSTAND": {"UNDERSTAND": 1.00, "PRACTICE": 0.85, "EXAM_PREPARATION": 0.80, "ASSIGNMENT": 0.70, "PROJECT": 0.40, "KNOWLEDGE_SHARING": 0.90},
        "PRACTICE": {"UNDERSTAND": 0.85, "PRACTICE": 1.00, "EXAM_PREPARATION": 0.90, "ASSIGNMENT": 0.80, "PROJECT": 0.60, "KNOWLEDGE_SHARING": 0.75},
        "EXAM_PREPARATION": {"UNDERSTAND": 0.80, "PRACTICE": 0.90, "EXAM_PREPARATION": 1.00, "ASSIGNMENT": 0.65, "PROJECT": 0.30, "KNOWLEDGE_SHARING": 0.70},
        "ASSIGNMENT": {"UNDERSTAND": 0.70, "PRACTICE": 0.80, "EXAM_PREPARATION": 0.65, "ASSIGNMENT": 1.00, "PROJECT": 0.80, "KNOWLEDGE_SHARING": 0.60},
        "PROJECT": {"UNDERSTAND": 0.40, "PRACTICE": 0.60, "EXAM_PREPARATION": 0.30, "ASSIGNMENT": 0.80, "PROJECT": 1.00, "KNOWLEDGE_SHARING": 0.50},
        "KNOWLEDGE_SHARING": {"UNDERSTAND": 0.90, "PRACTICE": 0.75, "EXAM_PREPARATION": 0.70, "ASSIGNMENT": 0.60, "PROJECT": 0.50, "KNOWLEDGE_SHARING": 1.00},
    }
    for g1, row in expected_goals.items():
        for g2, exp_v in row.items():
            actual = calculate_goal_compatibility(g1, g2)
            report(f"Goal explicit value: {g1} x {g2} == {exp_v}", math.isclose(actual, exp_v))


def test_style_compatibility_expected_values():
    """Memverifikasi seluruh 16 nilai pada Style Matrix terhadap spesifikasi final (Catatan Audit 2)."""
    print("\n--- SUITE 2C: Style Matrix 16/16 Explicit Expected Values ---")
    expected_styles = {
        "DISCUSSION": {"DISCUSSION": 1.00, "PRACTICE": 0.80, "PEER_TUTORING": 0.85, "FOCUS_STUDY": 0.15},
        "PRACTICE": {"DISCUSSION": 0.80, "PRACTICE": 1.00, "PEER_TUTORING": 0.80, "FOCUS_STUDY": 0.30},
        "PEER_TUTORING": {"DISCUSSION": 0.85, "PRACTICE": 0.80, "PEER_TUTORING": 1.00, "FOCUS_STUDY": 0.20},
        "FOCUS_STUDY": {"DISCUSSION": 0.15, "PRACTICE": 0.30, "PEER_TUTORING": 0.20, "FOCUS_STUDY": 1.00},
    }
    for s1, row in expected_styles.items():
        for s2, exp_v in row.items():
            actual = calculate_style_compatibility(s1, s2)
            report(f"Style explicit value: {s1} x {s2} == {exp_v}", math.isclose(actual, exp_v))


def test_priority_scoring():
    """Menguji skor kualitas pasangan prioritas partner dan validasi rentang {1, 2, 3}."""
    print("\n--- SUITE 3: Priority Scoring ---")
    expected_partner_pairs = {
        (1, 1): 1.00, (1, 2): 0.85, (2, 1): 0.85, (2, 2): 0.70,
        (1, 3): 0.60, (3, 1): 0.60, (2, 3): 0.45, (3, 2): 0.45, (3, 3): 0.30,
    }
    for (p1, p2), exp_score in expected_partner_pairs.items():
        score = calculate_priority_score(p1, p2)
        report(f"Partner Priority: ({p1}, {p2}) == {exp_score}", math.isclose(score, exp_score))

    for bad_p in [(0, 1), (1, 4), (0, 0), (4, 4), (-1, 2), (True, 1), ("1", 2)]:
        try:
            calculate_priority_score(bad_p[0], bad_p[1])
            report(f"Partner Priority: Tolak input invalid {bad_p}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Partner Priority: Tolak input invalid {bad_p}", True)


def test_session_priority_scoring():
    """Menguji skor prioritas sesi dan validasi input."""
    print("\n--- SUITE 3B: Session Priority Scoring ---")
    report("Session Priority: rank 1 == 1.00", math.isclose(calculate_session_priority_score(1), 1.00))
    report("Session Priority: rank 2 == 0.70", math.isclose(calculate_session_priority_score(2), 0.70))
    report("Session Priority: rank 3 == 0.30", math.isclose(calculate_session_priority_score(3), 0.30))

    for bad_sp in [0, 4, -1, 5, "1", None, True]:
        try:
            calculate_session_priority_score(bad_sp)
            report(f"Session Priority: Tolak rank invalid ({bad_sp})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Session Priority: Tolak rank invalid ({bad_sp})", True)


def test_duration_scoring():
    """Menguji formula durasi piecewise bertahap L(d)."""
    print("\n--- SUITE 4: Duration Scoring L(d) ---")
    report("Duration: 59 menit (di bawah batas minimal) bernilai 0.00", calculate_duration_score(59) == 0.0)
    report("Duration: 60 menit bernilai tepat 0.50", math.isclose(calculate_duration_score(60), 0.50))
    report("Duration: 75 menit bernilai tepat 0.65", math.isclose(calculate_duration_score(75), 0.65))
    report("Duration: 90 menit bernilai tepat 0.80", math.isclose(calculate_duration_score(90), 0.80))
    report("Duration: 105 menit bernilai tepat 0.90", math.isclose(calculate_duration_score(105), 0.90))
    report("Duration: 120 menit bernilai tepat 1.00", math.isclose(calculate_duration_score(120), 1.00))
    report("Duration: 150 menit (di atas 120) tetap 1.00", math.isclose(calculate_duration_score(150), 1.00))

    for bad_d in [-1, -60, float("nan"), float("inf"), "60", None, True]:
        try:
            calculate_duration_score(bad_d)
            report(f"Duration: Tolak durasi invalid ({bad_d})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Duration: Tolak durasi invalid ({bad_d})", True)


def test_date_scoring():
    """Menguji penggabungan skor prioritas dan durasi 70:30."""
    print("\n--- SUITE 5: Date Score Integration (70:30) ---")
    report("Date Score: P=1.0, L=1.0 -> 1.00", math.isclose(calculate_date_score(1.0, 1.0), 1.00))
    report("Date Score: P=1.0, L=0.5 -> 0.85", math.isclose(calculate_date_score(1.0, 0.5), 0.85))
    report("Date Score: P=0.6, L=0.8 -> 0.66", math.isclose(calculate_date_score(0.6, 0.8), 0.66))
    report("Date Score: P=0.3, L=0.0 -> 0.21", math.isclose(calculate_date_score(0.3, 0.0), 0.21))

    for bad_ds in [(-0.1, 0.5), (1.1, 0.5), (0.5, -0.1), (0.5, 1.1), ("0.5", 0.5), (None, 0.5), (True, 0.5)]:
        try:
            calculate_date_score(bad_ds[0], bad_ds[1])
            report(f"Date Score: Tolak input di luar batas {bad_ds}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Date Score: Tolak input di luar batas {bad_ds}", True)


# ==============================================================================
# SUITE 6–10: TAHAP 15.2 TOPIC SIMILARITY TESTS
# ==============================================================================

def test_topic_normalization_and_tokenization():
    """Menguji normalisasi teks topik dan tokenisasi pelestari istilah teknis."""
    print("\n--- SUITE 6: Topic Normalization & Technical Tokenization ---")

    # 6.1 Normalisasi umum
    norm1 = normalize_topic_text("  Binary Search Tree  ")
    report("Topic Norm: Spasi dibersihkan & lowercase", norm1 == "binary search tree")

    norm_tech = normalize_topic_text("Pemrograman C++ & Node.js pada Web")
    report("Topic Norm: Karakter teknis C++ dan Node.js dipertahankan", "c++" in norm_tech and "node.js" in norm_tech)

    # 6.2 Penolakan teks kosong/None
    for bad_t in ["", "   ", "\n\t", None, 123, []]:
        try:
            normalize_topic_text(bad_t)
            report(f"Topic Norm: Tolak input invalid ({bad_t})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Topic Norm: Tolak input invalid ({bad_t})", True)

    # 6.3 Tokenisasi istilah teknis
    tokens_raw = tokenize_topic("Binary Search Tree, AVL Tree", expand_aliases=False)
    report("Tokenize: Istilah teknis BST & AVL terpisah bersih (tanpa ekspansi)", tokens_raw == {"binary", "search", "tree", "avl"})

    tokens_bst = tokenize_topic("Binary Search Tree, AVL Tree", expand_aliases=True)
    report("Tokenize: Istilah teknis BST & AVL mencakup singkatan bst", tokens_bst == {"binary", "search", "tree", "avl", "bst"})

    tokens_graph = tokenize_topic("Algoritma Graph: BFS dan DFS")
    report("Tokenize: Istilah BFS, DFS, Graph tidak hilang", {"graph", "bfs", "dfs"}.issubset(tokens_graph))

    tokens_cpp = tokenize_topic("Pemrograman C++ dan OOP")
    report("Tokenize: C++ dan OOP dipertahankan sebagai token", {"c++", "oop"}.issubset(tokens_cpp))

    # 6.4 Stopwords penyaring noise tanpa membuang makna
    tokens_noise = tokenize_topic("Materi bab tentang Integral")
    report("Tokenize: Stopwords disaring sehingga tersisa kata kunci", tokens_noise == {"integral"})


def test_jaccard_similarity():
    """Menguji perhitungan kemiripan leksikal Jaccard termasuk pemahaman singkatan teknis."""
    print("\n--- SUITE 7: Jaccard Lexical Similarity ---")

    # 7.1 Identik -> 1.00
    j_same = calculate_jaccard_similarity("Binary Search Tree", "binary search tree")
    report("Jaccard: Topik identik bernilai 1.00", math.isclose(j_same, 1.00))

    # 7.2 Disjoint -> 0.00
    j_disjoint = calculate_jaccard_similarity("Struktur Data Graph BFS", "Kalkulus Integral Lipat")
    report("Jaccard: Topik tanpa irisan bernilai 0.00", math.isclose(j_disjoint, 0.00))

    # 7.3 Irisan parsial terukur akurat
    # "Binary Search Tree" -> {"binary", "search", "tree", "bst"} (4)
    # "AVL Tree" -> {"avl", "tree"} (2)
    # Irisan: {"tree"} (1), Union: {"binary", "search", "tree", "bst", "avl"} (5) -> 1/5 = 0.20
    j_partial = calculate_jaccard_similarity("Binary Search Tree", "AVL Tree")
    report("Jaccard: Irisan parsial 1/5 terhitung 0.20", math.isclose(j_partial, 0.20))

    # 7.4 Simetri J(A, B) == J(B, A)
    j_ab = calculate_jaccard_similarity("Pengurutan QuickSort dan MergeSort", "QuickSort Algorithm")
    j_ba = calculate_jaccard_similarity("QuickSort Algorithm", "Pengurutan QuickSort dan MergeSort")
    report("Jaccard: Simetris sempurna J(A, B) == J(B, A)", math.isclose(j_ab, j_ba))

    # 7.5 Pemahaman singkatan dan sinonim teknis (P1 Audit)
    report("Jaccard: 'BST' vs 'Binary Search Tree' == 1.00", math.isclose(calculate_jaccard_similarity("BST", "Binary Search Tree"), 1.00))
    report("Jaccard: 'BFS' vs 'Breadth First Search' == 1.00", math.isclose(calculate_jaccard_similarity("BFS", "Breadth First Search"), 1.00))
    report("Jaccard: 'DFS' vs 'Depth First Search' == 1.00", math.isclose(calculate_jaccard_similarity("DFS", "Depth First Search"), 1.00))
    report("Jaccard: 'OOP' vs 'Object Oriented Programming' == 1.00", math.isclose(calculate_jaccard_similarity("OOP", "Object Oriented Programming"), 1.00))
    report("Jaccard: 'Alpro' vs 'Algoritma dan Pemrograman' == 1.00", math.isclose(calculate_jaccard_similarity("Alpro", "Algoritma dan Pemrograman"), 1.00))

    # 7.6 Topik berbeda dengan kata umum sama tidak boleh menghasilkan skor 1.00
    j_bfs_dfs = calculate_jaccard_similarity("BFS", "DFS")
    report("Jaccard: 'BFS' vs 'DFS' tidak bernilai 1.00 (terukur 0.33)", 0.0 < j_bfs_dfs < 1.0 and math.isclose(j_bfs_dfs, 1/3))

    j_sorting_graph = calculate_jaccard_similarity("Algoritma Pemrograman Sorting", "Algoritma Pemrograman Graph")
    report("Jaccard: 'Sorting' vs 'Graph' tidak bernilai 1.00 (terukur 0.60)", 0.0 < j_sorting_graph < 1.0 and math.isclose(j_sorting_graph, 0.60))

    j_turunan_integral = calculate_jaccard_similarity("Kalkulus Turunan", "Kalkulus Integral")
    report("Jaccard: 'Turunan' vs 'Integral' tidak bernilai 1.00 (terukur 0.33)", 0.0 < j_turunan_integral < 1.0 and math.isclose(j_turunan_integral, 1/3))


def test_embedding_vector_validation():
    """Menguji validasi ketat kelayakan vektor embedding dan stabilitas numerik."""
    print("\n--- SUITE 8: Embedding Vector Validation ---")

    # 8.1 Vektor valid
    v_good = [0.1, -0.5, 0.8, 1.2]
    is_v, _ = validate_embedding_vector(v_good)
    report("Vector Validation: Vektor normal dinyatakan valid", is_v)

    # 8.2 Dimensi cocok
    is_dim_ok, _ = validate_embedding_vector(v_good, expected_dim=4)
    report("Vector Validation: Dimensi cocok (4 == 4)", is_dim_ok)

    is_dim_bad, reason_dim = validate_embedding_vector(v_good, expected_dim=8)
    report("Vector Validation: Tolak dimensi tidak cocok (4 != 8)", not is_dim_bad and "tidak cocok" in reason_dim)

    # 8.3 Tolak vektor kosong
    is_empty, _ = validate_embedding_vector([])
    report("Vector Validation: Tolak vektor kosong []", not is_empty)

    # 8.4 Tolak vektor nol (norm == 0)
    is_zero, _ = validate_embedding_vector([0.0, 0.0, 0.0])
    report("Vector Validation: Tolak vektor nol [0, 0, 0]", not is_zero)

    # 8.5 Tolak NaN dan Infinity
    is_nan, _ = validate_embedding_vector([0.5, float("nan"), 0.2])
    report("Vector Validation: Tolak vektor memuat NaN", not is_nan)

    is_inf, _ = validate_embedding_vector([0.5, float("inf"), 0.2])
    report("Vector Validation: Tolak vektor memuat Infinity", not is_inf)

    # 8.6 Tolak tipe bukan angka
    is_str, _ = validate_embedding_vector([0.5, "0.2"])
    report("Vector Validation: Tolak elemen string", not is_str)

    is_bool, _ = validate_embedding_vector([0.5, True])
    report("Vector Validation: Tolak elemen boolean", not is_bool)

    # 8.7 Stabilitas numerik terhadap angka sangat besar (P2 Audit math.hypot)
    v_large = [1e200, 2e200, 3e200]
    is_large_ok, _ = validate_embedding_vector(v_large)
    report("Vector Validation: Angka sangat besar (1e200) tervalidasi stabil tanpa overflow", is_large_ok)

    # 8.8 Ketahanan terhadap integer raksasa (10**400) - Backlog Penguatan Numerik
    is_huge_int_ok, reason_huge = validate_embedding_vector([10**400, 1])
    report("Vector Validation: Integer raksasa (10**400) ditolak aman tanpa crash OverflowError", not is_huge_int_ok and "overflow numerik" in reason_huge)


def test_cosine_similarity():
    """Menguji perhitungan Cosine Similarity antar vektor embedding."""
    print("\n--- SUITE 9: Cosine Similarity Vector Calculation ---")

    # 9.1 Vektor identik arah -> 1.00
    c_same = calculate_cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    report("Cosine: Vektor identik bernilai 1.00", math.isclose(c_same, 1.00))

    # 9.2 Vektor kelipatan skalar (arah sama persis) -> 1.00
    c_scaled = calculate_cosine_similarity([1.0, 0.0, 0.0], [5.0, 0.0, 0.0])
    report("Cosine: Vektor kelipatan skalar bernilai 1.00", math.isclose(c_scaled, 1.00))

    # 9.3 Vektor ortogonal (tegak lurus) -> 0.00
    c_ortho = calculate_cosine_similarity([1.0, 0.0], [0.0, 1.0])
    report("Cosine: Vektor ortogonal bernilai 0.00", math.isclose(c_ortho, 0.00))

    # 9.4 Vektor berlawanan arah -> dibatasi clamped ke 0.00
    c_opposite = calculate_cosine_similarity([1.0, 0.0], [-1.0, 0.0])
    report("Cosine: Vektor berlawanan dibatasi ke 0.00", math.isclose(c_opposite, 0.00))

    # 9.5 Tolak vektor beda dimensi
    try:
        calculate_cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])
        report("Cosine: Tolak vektor beda dimensi", False, "Harusnya raise ValueError")
    except ValueError:
        report("Cosine: Tolak vektor beda dimensi", True)

    # 9.6 Stabilitas numerik Cosine terhadap angka sangat besar (P2 Audit)
    v_huge_a = [1e200, 2e200]
    v_huge_b = [1e200, 2e200]
    c_huge = calculate_cosine_similarity(v_huge_a, v_huge_b)
    report("Cosine: Vektor raksasa (1e200) terhitung 1.00 tanpa OverflowError", math.isclose(c_huge, 1.00))


class MockEmbeddingService:
    """Mock service untuk pengujian unit Topic Similarity."""
    def __init__(
        self,
        vector_map=None,
        should_fail=False,
        return_invalid=False,
        return_value=None,
        return_sequence=None
    ):
        self.vector_map = vector_map or {}
        self.should_fail = should_fail
        self.return_invalid = return_invalid
        self.return_value = return_value
        self.return_sequence = list(return_sequence) if return_sequence is not None else None

    def get_embedding(self, text: str):
        if self.should_fail:
            raise RuntimeError("Embedding API timeout or service unavailable")
        if self.return_sequence is not None and len(self.return_sequence) > 0:
            return self.return_sequence.pop(0)
        if self.return_value is not None:
            return self.return_value
        if self.return_invalid:
            return [float("nan"), 0.5]  # Vector memuat NaN
        return self.vector_map.get(text, [0.5, 0.5, 0.5, 0.5])


def test_topic_similarity_end_to_end():
    """Menguji integrasi Topic Similarity dengan embedding dan fallback Jaccard."""
    print("\n--- SUITE 10: Topic Similarity Integration (Cosine + Fallback) ---")

    # 10.1 Tanpa service -> Menggunakan Jaccard Fallback
    t_no_svc = calculate_topic_similarity("Struktur Data Graph", "Graph BFS DFS", embedding_service=None)
    j_exp = calculate_jaccard_similarity("Struktur Data Graph", "Graph BFS DFS")
    report("Topic Sim: Tanpa service otomatis fallback ke Jaccard", math.isclose(t_no_svc, j_exp))

    det_no_svc = calculate_topic_similarity_detailed("Struktur Data Graph", "Graph BFS DFS", embedding_service=None)
    report("Topic Sim Detailed: Menandai metode JACCARD_FALLBACK", det_no_svc["method"] == "JACCARD_FALLBACK")

    # 10.2 Service valid -> Menggunakan Cosine
    mock_vectors = {
        "binary search tree": [1.0, 0.0, 0.0],
        "bst": [0.95, 0.05, 0.0],  # Sangat mirip semantik
    }
    svc_good = MockEmbeddingService(vector_map=mock_vectors)
    t_cosine = calculate_topic_similarity("Binary Search Tree", "BST", embedding_service=svc_good)
    c_exp = calculate_cosine_similarity(mock_vectors["binary search tree"], mock_vectors["bst"])
    report("Topic Sim: Menggunakan Cosine saat embedding valid", math.isclose(t_cosine, c_exp))

    det_cosine = calculate_topic_similarity_detailed("Binary Search Tree", "BST", embedding_service=svc_good)
    report("Topic Sim Detailed: Menandai metode COSINE", det_cosine["method"] == "COSINE")

    # 10.3 Service melempar error -> Otomatis fallback ke Jaccard tanpa crash & pesan 'Service failure'
    svc_fail = MockEmbeddingService(should_fail=True)
    t_fallback = calculate_topic_similarity("QuickSort", "QuickSort Algorithm", embedding_service=svc_fail)
    report("Topic Sim: Service error otomatis fallback ke Jaccard", math.isclose(t_fallback, 0.50))

    det_fallback = calculate_topic_similarity_detailed("QuickSort", "QuickSort Algorithm", embedding_service=svc_fail)
    report("Topic Sim Detailed: Mencatat error penyebab fallback", det_fallback["method"] == "JACCARD_FALLBACK" and det_fallback["error"] is not None)
    report("Topic Sim Detailed: Mencatat pesan 'Service failure'", "Service failure" in (det_fallback["error"] or ""))
    report("Topic Sim Detailed: Token A terurut deterministik", det_fallback["tokens_a"] == sorted(det_fallback["tokens_a"]))
    report("Topic Sim Detailed: Token B terurut deterministik", det_fallback["tokens_b"] == sorted(det_fallback["tokens_b"]))

    # 10.4 Fallback Jaccard mengenali singkatan teknis (P1 Audit)
    # Kasus A: Tanpa embedding service
    report("Topic Sim Fallback: 'BST' vs 'Binary Search Tree' == 1.00", math.isclose(calculate_topic_similarity("BST", "Binary Search Tree", embedding_service=None), 1.00))
    report("Topic Sim Fallback: 'BFS' vs 'Breadth First Search' == 1.00", math.isclose(calculate_topic_similarity("BFS", "Breadth First Search", embedding_service=None), 1.00))
    report("Topic Sim Fallback: 'DFS' vs 'Depth First Search' == 1.00", math.isclose(calculate_topic_similarity("DFS", "Depth First Search", embedding_service=None), 1.00))

    # Kasus B: Saat service error/gagal
    t_bst_svc_fail = calculate_topic_similarity("BST", "Binary Search Tree", embedding_service=svc_fail)
    report("Topic Sim Fallback: 'BST' vs 'Binary Search Tree' tetap 1.00 saat service gagal", math.isclose(t_bst_svc_fail, 1.00))

    # 10.5 Service mengembalikan vector invalid (NaN) -> Otomatis fallback ke Jaccard
    svc_invalid = MockEmbeddingService(return_invalid=True)
    t_inv_fallback = calculate_topic_similarity("Linear Algebra", "Linear Algebra", embedding_service=svc_invalid)
    report("Topic Sim: Vector invalid otomatis fallback ke Jaccard", math.isclose(t_inv_fallback, 1.00))

    # 10.6 Robustness: Service mengembalikan tipe non-sequence / non-vector (Audit P1 & P2)
    # Kasus A: vec_a integer (123) dan vec_b list -> TIDAK crash len(123)
    svc_int_a = MockEmbeddingService(return_sequence=[123, [0.1, 0.2]])
    t_int_a = calculate_topic_similarity("Aljabar Linier", "Aljabar Linier", embedding_service=svc_int_a)
    report("Topic Sim Robustness: vec_a integer (123) fallback ke Jaccard tanpa crash", math.isclose(t_int_a, 1.00))

    svc_int_a_det = MockEmbeddingService(return_sequence=[123, [0.1, 0.2]])
    det_int_a = calculate_topic_similarity_detailed("Aljabar Linier", "Aljabar Linier", embedding_service=svc_int_a_det)
    report("Topic Sim Robustness Detailed: vec_a integer dicatat 'Invalid embedding vector'", "Invalid embedding vector" in (det_int_a["error"] or ""))

    # Kasus B: vec_a list dan vec_b float (3.14) -> TIDAK crash
    svc_float_b = MockEmbeddingService(return_sequence=[[0.1, 0.2], 3.14])
    t_float_b = calculate_topic_similarity("Aljabar Linier", "Aljabar Linier", embedding_service=svc_float_b)
    report("Topic Sim Robustness: vec_b float (3.14) fallback ke Jaccard tanpa crash", math.isclose(t_float_b, 1.00))

    svc_float_b_det = MockEmbeddingService(return_sequence=[[0.1, 0.2], 3.14])
    det_float_b = calculate_topic_similarity_detailed("Aljabar Linier", "Aljabar Linier", embedding_service=svc_float_b_det)
    report("Topic Sim Robustness Detailed: vec_b float dicatat 'Invalid embedding vector'", "Invalid embedding vector" in (det_float_b["error"] or ""))

    # Kasus C: Service mengembalikan dictionary
    svc_dict = MockEmbeddingService(return_value={"dim": 1})
    t_dict = calculate_topic_similarity("Aljabar Linier", "Aljabar Linier", embedding_service=svc_dict)
    report("Topic Sim Robustness: Dictionary fallback ke Jaccard tanpa crash", math.isclose(t_dict, 1.00))

    svc_dict_det = MockEmbeddingService(return_value={"dim": 1})
    det_dict = calculate_topic_similarity_detailed("Aljabar Linier", "Aljabar Linier", embedding_service=svc_dict_det)
    report("Topic Sim Robustness Detailed: Dictionary dicatat 'Invalid embedding vector'", "Invalid embedding vector" in (det_dict["error"] or ""))

    # Kasus D: Service mengembalikan list kosong []
    svc_empty = MockEmbeddingService(return_value=[])
    t_empty = calculate_topic_similarity("Aljabar Linier", "Aljabar Linier", embedding_service=svc_empty)
    report("Topic Sim Robustness: List kosong [] fallback ke Jaccard tanpa crash", math.isclose(t_empty, 1.00))

    svc_empty_det = MockEmbeddingService(return_value=[])
    det_empty = calculate_topic_similarity_detailed("Aljabar Linier", "Aljabar Linier", embedding_service=svc_empty_det)
    report("Topic Sim Robustness Detailed: List kosong dicatat 'Invalid embedding vector'", "Invalid embedding vector" in (det_empty["error"] or ""))

    # Kasus E: Service mengembalikan dimensi berbeda
    svc_dim = MockEmbeddingService(return_sequence=[[0.1, 0.2], [0.1, 0.2, 0.3]])
    t_dim = calculate_topic_similarity("Aljabar Linier", "Aljabar Linier", embedding_service=svc_dim)
    report("Topic Sim Robustness: Dimensi berbeda fallback ke Jaccard tanpa crash", math.isclose(t_dim, 1.00))

    svc_dim_det = MockEmbeddingService(return_sequence=[[0.1, 0.2], [0.1, 0.2, 0.3]])
    det_dim = calculate_topic_similarity_detailed("Aljabar Linier", "Aljabar Linier", embedding_service=svc_dim_det)
    report("Topic Sim Robustness Detailed: Dimensi berbeda dicatat 'Invalid embedding vector'", "Invalid embedding vector" in (det_dim["error"] or ""))

    # Kasus F: Service mengembalikan string
    svc_str = MockEmbeddingService(return_value="embedding_string")
    t_str = calculate_topic_similarity("Aljabar Linier", "Aljabar Linier", embedding_service=svc_str)
    report("Topic Sim Robustness: String fallback ke Jaccard tanpa crash", math.isclose(t_str, 1.00))

    # Kasus G: Service mengembalikan None
    svc_none = MockEmbeddingService(return_sequence=[[0.1, 0.2], None])
    t_none = calculate_topic_similarity("Aljabar Linier", "Aljabar Linier", embedding_service=svc_none)
    report("Topic Sim Robustness: Service return None fallback ke Jaccard tanpa crash", math.isclose(t_none, 1.00))

    # 10.6 Topik kosong -> Tetap raise ValueError (jangan disamakan dengan fallback)
    for bad_t in ["", "   ", None]:
        try:
            calculate_topic_similarity(bad_t, "Kalkulus", embedding_service=svc_good)
            report(f"Topic Sim: Tolak topik kosong/None ({bad_t})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Topic Sim: Tolak topik kosong/None ({bad_t})", True)


def test_learning_mode_canonicalizer():
    """Menguji normalisasi Learning Mode kanonis, alias, dan penolakan input invalid (Tahap 15.3)."""
    print("\n--- SUITE 11: Learning Mode Canonicalizer & Idempotence ---")

    # 11.1 Nilai kanonis dipertahankan & idempoten
    for mode in CANONICAL_LEARNING_MODES:
        norm = normalize_learning_mode(mode)
        report(f"Mode: Kanonis '{mode}' dipertahankan", norm == mode)
        report(f"Mode: Idempoten untuk '{mode}'", normalize_learning_mode(norm) == norm)

    # 11.2 Alias resmi Day 15
    report("Mode: Alias 'DARING' -> 'ONLINE'", normalize_learning_mode("DARING") == "ONLINE")
    report("Mode: Alias 'LURING' -> 'OFFLINE'", normalize_learning_mode("LURING") == "OFFLINE")
    report("Mode: Alias 'CAMPURAN' -> 'HYBRID'", normalize_learning_mode("CAMPURAN") == "HYBRID")

    # 11.3 Case insensitivity & Whitespace stripping
    report("Mode: Case insensitivity 'daring' -> 'ONLINE'", normalize_learning_mode("daring") == "ONLINE")
    report("Mode: Case insensitivity 'offline' -> 'OFFLINE'", normalize_learning_mode("offline") == "OFFLINE")
    report("Mode: Whitespace stripped '  campuran  ' -> 'HYBRID'", normalize_learning_mode("  campuran  ") == "HYBRID")

    # 11.4 Tolak nilai invalid, kosong, None, atau tipe non-string
    for invalid_val in ["UNKNOWN_MODE", "REMOTE", "VIRTUAL", "", "   ", None, 123, []]:
        try:
            normalize_learning_mode(invalid_val)
            report(f"Mode: Tolak nilai invalid ({invalid_val})", False, "Harusnya melempar ValueError")
        except ValueError:
            report(f"Mode: Tolak nilai invalid ({invalid_val})", True)


def test_learning_mode_compatibility():
    """Menguji matriks dan fungsi kompatibilitas Mode Belajar M(A, B) (Tahap 15.3)."""
    print("\n--- SUITE 12: Learning Mode Compatibility Matrix & Function ---")

    # 12.1 Struktur matriks dan nilai simetris
    for m in CANONICAL_LEARNING_MODES:
        report(f"Mode Matrix: '{m}' memiliki baris lengkap", set(MODE_COMPATIBILITY[m].keys()) == CANONICAL_LEARNING_MODES)
        report(f"Mode Matrix: Diagonal M('{m}', '{m}') == 1.00", math.isclose(MODE_COMPATIBILITY[m][m], 1.00))

    # 12.2 Simetri sempurna M(A, B) == M(B, A)
    is_symmetric = True
    for m1 in CANONICAL_LEARNING_MODES:
        for m2 in CANONICAL_LEARNING_MODES:
            if not math.isclose(MODE_COMPATIBILITY[m1][m2], MODE_COMPATIBILITY[m2][m1]):
                is_symmetric = False
                break
    report("Mode Matrix: Simetris sempurna M(A, B) == M(B, A)", is_symmetric)

    # 12.3 Seluruh nilai dalam rentang [0.0, 1.0]
    in_range = all(
        0.0 <= MODE_COMPATIBILITY[m1][m2] <= 1.0
        for m1 in CANONICAL_LEARNING_MODES
        for m2 in CANONICAL_LEARNING_MODES
    )
    report("Mode Matrix: Seluruh nilai berada dalam rentang [0.0, 1.0]", in_range)

    # 12.4 Nilai eksplisit tabel yang disepakati (9/9 pasangan)
    expected_matrix = {
        ("ONLINE", "ONLINE"): 1.00,
        ("OFFLINE", "OFFLINE"): 1.00,
        ("HYBRID", "HYBRID"): 1.00,
        ("HYBRID", "ONLINE"): 0.85,
        ("ONLINE", "HYBRID"): 0.85,
        ("HYBRID", "OFFLINE"): 0.85,
        ("OFFLINE", "HYBRID"): 0.85,
        ("ONLINE", "OFFLINE"): 0.00,
        ("OFFLINE", "ONLINE"): 0.00,
    }
    for (m_a, m_b), exp_score in expected_matrix.items():
        score = calculate_mode_compatibility(m_a, m_b)
        report(f"Mode explicit value: {m_a} x {m_b} == {exp_score}", math.isclose(score, exp_score))

    # 12.5 Kompatibilitas dengan alias bahasa Indonesia
    report("Mode Function: DARING x CAMPURAN == 0.85", math.isclose(calculate_mode_compatibility("DARING", "CAMPURAN"), 0.85))
    report("Mode Function: LURING x CAMPURAN == 0.85", math.isclose(calculate_mode_compatibility("LURING", "CAMPURAN"), 0.85))
    report("Mode Function: DARING x LURING == 0.00", math.isclose(calculate_mode_compatibility("DARING", "LURING"), 0.00))
    report("Mode Function: DARING x DARING == 1.00", math.isclose(calculate_mode_compatibility("DARING", "DARING"), 1.00))
    report("Mode Function: CAMPURAN x CAMPURAN == 1.00", math.isclose(calculate_mode_compatibility("CAMPURAN", "CAMPURAN"), 1.00))

    # 12.6 Tolak mode tidak valid pada fungsi
    try:
        calculate_mode_compatibility("ONLINE", "REMOTE")
        report("Mode Function: Tolak mode invalid pada fungsi", False, "Harusnya raise ValueError")
    except ValueError:
        report("Mode Function: Tolak mode invalid pada fungsi", True)


def test_weighted_compatibility_score():
    """Menguji formula pembobotan Compatibility Score CS = 100 * (0.30T + 0.25G + 0.15S + 0.15D + 0.15M) (Tahap 15.4)."""
    print("\n--- SUITE 13: Weighted Compatibility Score Calculation & Bounds ---")

    # 13.1 Verifikasi konstanta bobot resmi
    report("Weights: Bobot Topic == 0.30", math.isclose(WEIGHT_TOPIC, 0.30))
    report("Weights: Bobot Goal == 0.25", math.isclose(WEIGHT_GOAL, 0.25))
    report("Weights: Bobot Style == 0.15", math.isclose(WEIGHT_STYLE, 0.15))
    report("Weights: Bobot Date == 0.15", math.isclose(WEIGHT_DATE, 0.15))
    report("Weights: Bobot Mode == 0.15", math.isclose(WEIGHT_MODE, 0.15))
    total_weights = WEIGHT_TOPIC + WEIGHT_GOAL + WEIGHT_STYLE + WEIGHT_DATE + WEIGHT_MODE
    report("Weights: Total bobot tepat 1.00 (100%)", math.isclose(total_weights, 1.00))

    # 13.2 Batas ekstrim: skor minimum (0.0) dan skor maksimum (100.0)
    score_max = calculate_compatibility_score(1.0, 1.0, 1.0, 1.0, 1.0)
    report("CS Calculation: Seluruh komponen 1.0 -> Skor tepat 100.00", math.isclose(score_max, 100.0))

    score_min = calculate_compatibility_score(0.0, 0.0, 0.0, 0.0, 0.0)
    report("CS Calculation: Seluruh komponen 0.0 -> Skor tepat 0.00", math.isclose(score_min, 0.0))

    # 13.3 Contoh perhitungan benchmark (Sesuai Audit Reviewer)
    # T=1.0 (30.0), G=0.9 (22.5), S=0.8 (12.0), D=0.8 (12.0), M=1.0 (15.0) -> Total = 91.50
    score_bench1 = calculate_compatibility_score(1.0, 0.9, 0.8, 0.8, 1.0)
    report("CS Benchmark 1: (1.0, 0.9, 0.8, 0.8, 1.0) -> Tepat 91.50", math.isclose(score_bench1, 91.50))

    # T=0.90 (27.0), G=1.00 (25.0), S=0.85 (12.75), D=0.80 (12.0), M=1.00 (15.0) -> Total = 91.75
    score_bench2 = calculate_compatibility_score(0.90, 1.00, 0.85, 0.80, 1.00)
    report("CS Benchmark 2: (0.90, 1.00, 0.85, 0.80, 1.00) -> Tepat 91.75", math.isclose(score_bench2, 91.75))

    # Seluruh komponen seimbang 0.50 -> Total = 50.00
    score_half = calculate_compatibility_score(0.5, 0.5, 0.5, 0.5, 0.5)
    report("CS Benchmark 3: Seluruh komponen 0.5 -> Tepat 50.00", math.isclose(score_half, 50.00))

    # 13.4 Validasi ketat input: Tolak komponen di luar rentang [0.0, 1.0]
    out_of_bounds_cases = [
        ("topic < 0.0", (-0.1, 1.0, 1.0, 1.0, 1.0)),
        ("topic > 1.0", (1.1, 1.0, 1.0, 1.0, 1.0)),
        ("goal < 0.0", (1.0, -0.1, 1.0, 1.0, 1.0)),
        ("goal > 1.0", (1.0, 1.1, 1.0, 1.0, 1.0)),
        ("style < 0.0", (1.0, 1.0, -0.1, 1.0, 1.0)),
        ("style > 1.0", (1.0, 1.0, 1.1, 1.0, 1.0)),
        ("date < 0.0", (1.0, 1.0, 1.0, -0.1, 1.0)),
        ("date > 1.0", (1.0, 1.0, 1.0, 1.1, 1.0)),
        ("mode < 0.0", (1.0, 1.0, 1.0, 1.0, -0.1)),
        ("mode > 1.0", (1.0, 1.0, 1.0, 1.0, 1.1)),
    ]
    for desc, args in out_of_bounds_cases:
        try:
            calculate_compatibility_score(*args)
            report(f"CS Validation: Tolak {desc}", False, "Harusnya melempar ValueError")
        except ValueError:
            report(f"CS Validation: Tolak {desc}", True)

    # 13.5 Validasi tipe data: Tolak None, boolean, string, NaN, Infinity
    type_invalid_cases = [
        ("None", (None, 1.0, 1.0, 1.0, 1.0)),
        ("Boolean True", (True, 1.0, 1.0, 1.0, 1.0)),
        ("Boolean False", (1.0, False, 1.0, 1.0, 1.0)),
        ("String", ("0.5", 1.0, 1.0, 1.0, 1.0)),
        ("NaN", (float("nan"), 1.0, 1.0, 1.0, 1.0)),
        ("Infinity", (float("inf"), 1.0, 1.0, 1.0, 1.0)),
    ]
    for desc, args in type_invalid_cases:
        try:
            calculate_compatibility_score(*args)
            report(f"CS Validation: Tolak {desc}", False, "Harusnya melempar ValueError")
        except ValueError:
            report(f"CS Validation: Tolak {desc}", True)


def test_compatibility_breakdown():
    """Menguji rincian transparan breakdown skor dan konsistensi matematis (Tahap 15.4)."""
    print("\n--- SUITE 14: Compatibility Breakdown Output & Consistency ---")

    # 14.1 Struktur breakdown benchmark (91.50)
    bd1 = calculate_compatibility_breakdown(1.0, 0.9, 0.8, 0.8, 1.0)
    report("Breakdown: Memiliki total_score", "total_score" in bd1)
    report("Breakdown: total_score tepat 91.50", math.isclose(bd1["total_score"], 91.50))
    report("Breakdown: Memuat tepat 5 komponen", set(bd1["components"].keys()) == {"topic", "goal", "style", "date", "mode"})

    # 14.2 Nilai kontribusi tiap komponen
    c_topic = bd1["components"]["topic"]
    report("Breakdown Topic: weight 0.30", math.isclose(c_topic["weight"], 0.30))
    report("Breakdown Topic: score 1.00", math.isclose(c_topic["score"], 1.00))
    report("Breakdown Topic: contribution tepat 30.0", math.isclose(c_topic["contribution"], 30.0))

    c_goal = bd1["components"]["goal"]
    report("Breakdown Goal: weight 0.25", math.isclose(c_goal["weight"], 0.25))
    report("Breakdown Goal: score 0.90", math.isclose(c_goal["score"], 0.90))
    report("Breakdown Goal: contribution tepat 22.5", math.isclose(c_goal["contribution"], 22.5))

    c_style = bd1["components"]["style"]
    report("Breakdown Style: weight 0.15", math.isclose(c_style["weight"], 0.15))
    report("Breakdown Style: score 0.80", math.isclose(c_style["score"], 0.80))
    report("Breakdown Style: contribution tepat 12.0", math.isclose(c_style["contribution"], 12.0))

    c_date = bd1["components"]["date"]
    report("Breakdown Date: weight 0.15", math.isclose(c_date["weight"], 0.15))
    report("Breakdown Date: score 0.80", math.isclose(c_date["score"], 0.80))
    report("Breakdown Date: contribution tepat 12.0", math.isclose(c_date["contribution"], 12.0))

    c_mode = bd1["components"]["mode"]
    report("Breakdown Mode: weight 0.15", math.isclose(c_mode["weight"], 0.15))
    report("Breakdown Mode: score 1.00", math.isclose(c_mode["score"], 1.00))
    report("Breakdown Mode: contribution tepat 15.0", math.isclose(c_mode["contribution"], 15.0))

    # 14.3 Konsistensi: Jumlah kontribusi identik dengan total_score
    sum_contrib = sum(comp["contribution"] for comp in bd1["components"].values())
    report("Breakdown: Jumlah kontribusi tepat sama dengan total_score (30+22.5+12+12+15 = 91.5)", math.isclose(sum_contrib, bd1["total_score"]))

    # 14.4 Identitas total_score breakdown dengan calculate_compatibility_score
    direct_score = calculate_compatibility_score(1.0, 0.9, 0.8, 0.8, 1.0)
    report("Breakdown: total_score identik dengan calculate_compatibility_score", math.isclose(bd1["total_score"], direct_score))

    # 14.5 Kasus bervariasi dengan pembulatan (63.75)
    bd2 = calculate_compatibility_breakdown(0.75, 0.60, 0.50, 0.40, 0.85)
    # Contrib: 22.5 + 15.0 + 7.5 + 6.0 + 12.75 = 63.75
    report("Breakdown Case 2: total_score tepat 63.75", math.isclose(bd2["total_score"], 63.75))
    sum_contrib2 = sum(comp["contribution"] for comp in bd2["components"].values())
    report("Breakdown Case 2: Jumlah kontribusi tepat sama dengan total_score", math.isclose(sum_contrib2, bd2["total_score"]))

    # 14.6 Tolak input invalid pada breakdown
    try:
        calculate_compatibility_breakdown(None, 1.0, 1.0, 1.0, 1.0)
        report("Breakdown: Tolak input None", False, "Harusnya raise ValueError")
    except ValueError:
        report("Breakdown: Tolak input None", True)


def run_tests():
    print("=" * 70)
    print("RUNNING DAY 15: SOFT CONSTRAINT SCORING TEST SUITE (TAHAP 15.1 - 15.4)")
    print("=" * 70)

    test_canonicalizers()
    test_compatibility_matrices_structure_and_bounds()
    test_goal_compatibility_expected_values()
    test_style_compatibility_expected_values()
    test_priority_scoring()
    test_session_priority_scoring()
    test_duration_scoring()
    test_date_scoring()
    test_topic_normalization_and_tokenization()
    test_jaccard_similarity()
    test_embedding_vector_validation()
    test_cosine_similarity()
    test_topic_similarity_end_to_end()
    test_learning_mode_canonicalizer()
    test_learning_mode_compatibility()
    test_weighted_compatibility_score()
    test_compatibility_breakdown()

    print("\n" + "=" * 70)
    print(f"TEST RESULT SUMMARY: {passed_count}/{total_count} TESTS PASSED (100% SUCCESS)")
    print("=" * 70)
    assert passed_count == total_count, f"Some tests failed! ({passed_count}/{total_count})"


if __name__ == "__main__":
    run_tests()
