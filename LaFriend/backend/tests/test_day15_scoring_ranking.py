# test_day15_scoring_ranking.py - Automated Test Suite untuk Scoring Engine LaFriend (Day 15)
# Tahap 15.1: Canonicalizer, Matriks Kompatibilitas, Priority, Duration, Date Scoring
# Tahap 15.2: Topic Similarity (Normalisasi, Tokenisasi, Jaccard, Vector Validation, Cosine, Fallback)

import sys
import math
from pathlib import Path

# Setup path agar dapat mengimpor app
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

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
    _round_half_up,
    calculate_compatibility_score,
    calculate_compatibility_breakdown,
    # Tahap 15.5
    _get_field,
    priority_pair_key,
    _validate_common_slot,
    select_best_session_schedule,
    select_best_partner_schedule,
    calculate_session_score,
    calculate_partner_score,
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

    # 13.6 Tolak integer raksasa 10**400 dengan ValueError (Temuan Audit Reviewer P2)
    try:
        calculate_compatibility_score(10**400, 1.0, 1.0, 1.0, 1.0)
        report("CS Validation: Tolak integer raksasa 10**400 dengan ValueError", False, "Harusnya raise ValueError")
    except ValueError as e:
        report("CS Validation: Tolak integer raksasa 10**400 dengan ValueError", "overflow numerik" in str(e))
    except OverflowError:
        report("CS Validation: Tolak integer raksasa 10**400 dengan ValueError", False, "Memicu unhandled OverflowError")

    # 13.7 Anti Double-Rounding: 1.234999996 -> tepat 1.23 (Temuan Audit Reviewer P1)
    val_raw = 1.234999996
    res_half_up = _round_half_up(val_raw, 2)
    report("CS Rounding: _round_half_up(1.234999996, 2) tepat 1.23 (tanpa double-rounding)", math.isclose(res_half_up, 1.23))

    score_audit_p1 = calculate_compatibility_score(0.04116666653333333, 0.0, 0.0, 0.0, 0.0)
    report("CS Rounding: calculate_compatibility_score(0.04116666653333333, 0, 0, 0, 0) tepat 1.23", math.isclose(score_audit_p1, 1.23))


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

    # 14.6 Benchmark Rekonsiliasi Pembulatan (Temuan Audit Reviewer P1)
    # T=0.35991, G=0.51916, S=0.86274, D=0.50660, M=0.16717
    # Raw total = 46.82395 -> Total Score = 46.82
    # Unreconciled sum = 10.80 + 12.98 + 12.94 + 7.60 + 2.51 = 46.83
    # Reconciled: Topic dialokasikan -0.01 sehingga contribution = 10.79
    # Final sum = 10.79 + 12.98 + 12.94 + 7.60 + 2.51 = 46.82 == Total Score!
    bd_audit = calculate_compatibility_breakdown(0.35991, 0.51916, 0.86274, 0.50660, 0.16717)
    report("Breakdown Audit P1: total_score tepat 46.82", math.isclose(bd_audit["total_score"], 46.82))
    report("Breakdown Audit P1: rounding_reconciliation tercatat -0.01", math.isclose(bd_audit["rounding_reconciliation"], -0.01))
    report("Breakdown Audit P1: Topic contribution terekonsiliasi 10.79", math.isclose(bd_audit["components"]["topic"]["contribution"], 10.79))
    report("Breakdown Audit P1: Topic raw_contribution transparan 10.7973", math.isclose(bd_audit["components"]["topic"]["raw_contribution"], 10.7973))
    report("Breakdown Audit P1: Topic rounding_adjustment tercatat -0.01", math.isclose(bd_audit["components"]["topic"]["rounding_adjustment"], -0.01))
    sum_audit = sum(c["contribution"] for c in bd_audit["components"].values())
    report("Breakdown Audit P1: Jumlah kontribusi identik dengan total_score (46.82 == 46.82)", math.isclose(sum_audit, bd_audit["total_score"]))

    # 14.7 Fuzzing Numerik: 50 kombinasi acak desimal selalu memenuhi sum(contributions) == total_score
    import random
    all_fuzz_passed = True
    for seed in range(50):
        random.seed(seed)
        t_rnd, g_rnd, s_rnd, d_rnd, m_rnd = [random.random() for _ in range(5)]
        bd_rnd = calculate_compatibility_breakdown(t_rnd, g_rnd, s_rnd, d_rnd, m_rnd)
        sum_rnd = sum(c["contribution"] for c in bd_rnd["components"].values())
        if not math.isclose(sum_rnd, bd_rnd["total_score"]):
            all_fuzz_passed = False
            break
    report("Breakdown Fuzzing: 50 kombinasi acak desimal selalu memiliki sum(contrib) == total_score", all_fuzz_passed)

    # 14.8 Tolak input invalid pada breakdown
    try:
        calculate_compatibility_breakdown(None, 1.0, 1.0, 1.0, 1.0)
        report("Breakdown: Tolak input None", False, "Harusnya raise ValueError")
    except ValueError:
        report("Breakdown: Tolak input None", True)

    # 14.9 Tolak integer raksasa 10**400 dengan ValueError (Temuan Audit Reviewer P2)
    try:
        calculate_compatibility_breakdown(10**400, 1.0, 1.0, 1.0, 1.0)
        report("Breakdown: Tolak integer raksasa 10**400 dengan ValueError", False, "Harusnya raise ValueError")
    except ValueError as e:
        report("Breakdown: Tolak integer raksasa 10**400 dengan ValueError", "overflow numerik" in str(e))
    except OverflowError:
        report("Breakdown: Tolak integer raksasa 10**400 dengan ValueError", False, "Memicu unhandled OverflowError")

    # 14.10 Presisi Decimal murni tanpa early float conversion (Temuan Audit Reviewer P1 Tahap 15.5)
    # topic_score = 0.9001666666666666, other components = 0.0
    # 100 * 0.30 * 0.9001666666666666 = 27.004999999999998 -> 27.00, reconciliation 0.00
    bd_prec = calculate_compatibility_breakdown(0.9001666666666666, 0.0, 0.0, 0.0, 0.0)
    report("Breakdown Precision: total_score tepat 27.00", math.isclose(bd_prec["total_score"], 27.00))
    report("Breakdown Precision: topic contribution tepat 27.00", math.isclose(bd_prec["components"]["topic"]["contribution"], 27.00))
    report("Breakdown Precision: rounding_reconciliation tepat 0.00", math.isclose(bd_prec["rounding_reconciliation"], 0.00))


# ==============================================================================
# DUMMY MODELS FOR TESTING ORM & PYDANTIC COMPATIBILITY
# ==============================================================================

class DummyORMIntent:
    def __init__(self, intent_id, student_id, topics, learning_goal, collaboration_style, learning_mode):
        self.intent_id = intent_id
        self.student_id = student_id
        self.topics = topics
        self.learning_goal = learning_goal
        self.collaboration_style = collaboration_style
        self.learning_mode = learning_mode


class DummyORMSession:
    def __init__(self, session_id, title, description, learning_goal, collaboration_style, learning_mode):
        self.session_id = session_id
        self.title = title
        self.description = description
        self.learning_goal = learning_goal
        self.collaboration_style = collaboration_style
        self.learning_mode = learning_mode


class DummyPydanticIntent(BaseModel):
    intent_id: str
    student_id: str
    topics: str
    learning_goal: str
    collaboration_style: str
    learning_mode: str


class DummyPydanticSession(BaseModel):
    session_id: str
    title: str
    description: Optional[str] = None
    learning_goal: str
    collaboration_style: str
    learning_mode: str


# ==============================================================================
# SUITE 15: SESSION SCORING ENGINE (TAHAP 15.5)
# ==============================================================================

def test_session_scoring():
    print("\n--- SUITE 15: Session Scoring Engine (Tahap 15.5) ---")

    # 15.1 Skor Sempurna 100
    intent_perf = {
        "intent_id": "int_perf",
        "student_id": "std_andi",
        "topics": "Struktur Data Pohon Biner",
        "learning_goal": "PRACTICE",
        "collaboration_style": "PRACTICE",
        "learning_mode": "ONLINE",
    }
    session_perf = {
        "session_id": "ses_perf",
        "title": "Struktur Data Pohon Biner",
        "description": "",
        "learning_goal": "PRACTICE",
        "collaboration_style": "PRACTICE",
        "learning_mode": "ONLINE",
    }
    slot_perf = [{
        "date": "2026-11-16",
        "start_time": "10:00",
        "end_time": "12:00",
        "duration_minutes": 120,
        "priority_a": 1,
        "priority_b": 1,
    }]
    res_perf = calculate_session_score(intent_perf, session_perf, slot_perf)
    report("Session Score: Skor sempurna 100.00", math.isclose(res_perf["total_score"], 100.00))
    report("Session Score: candidate_type == 'SESSION'", res_perf["candidate_type"] == "SESSION")
    report("Session Score: candidate_session_id sesuai", res_perf["candidate_session_id"] == "ses_perf")
    report("Session Score: rounding_reconciliation 0.0", math.isclose(res_perf["rounding_reconciliation"], 0.0))
    report("Session Score: 5 komponen sempurna bernilai 1.0", all(
        math.isclose(res_perf["components"][k]["score"], 1.0)
        for k in ["topic", "goal", "style", "date", "mode"]
    ))

    # 15.2 Benchmark 99.10 (Andi & Sesi A)
    # T=1.0, G=1.0, S=1.0, D=0.94 (90m, prio 1), M=1.0 -> 99.10
    intent_andi = {
        "intent_id": "intent-andi",
        "student_id": "student-andi",
        "topics": "Kalkulus Lanjut Integral",
        "learning_goal": "UNDERSTAND",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "HYBRID",
    }
    session_a = {
        "session_id": "session-123",
        "title": "Kalkulus Lanjut Integral",
        "description": None,
        "learning_goal": "UNDERSTAND",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "HYBRID",
    }
    slots_a = [{
        "date": "2026-11-16",
        "start_time": "10:00",
        "end_time": "11:30",
        "duration_minutes": 90,
        "priority_a": 1,
        "priority_b": 1,
    }]
    res_a = calculate_session_score(intent_andi, session_a, slots_a)
    report("Session Benchmark: Total score tepat 99.10", math.isclose(res_a["total_score"], 99.10))
    report("Session Benchmark: rounding_reconciliation tepat 0.0", math.isclose(res_a["rounding_reconciliation"], 0.0))
    sched_a = res_a["selected_schedule"]
    report("Session Benchmark: selected_schedule durasi 90 menit", sched_a["duration_minutes"] == 90)
    report("Session Benchmark: selected_schedule priority_score 1.0", math.isclose(sched_a["priority_score"], 1.0))
    report("Session Benchmark: selected_schedule duration_score 0.8", math.isclose(sched_a["duration_score"], 0.8))
    report("Session Benchmark: selected_schedule date_score 0.94", math.isclose(sched_a["date_score"], 0.94))

    # 15.3 Topic dengan vs tanpa Description
    # Kasus A: Tanpa description -> title saja
    ses_no_desc = {
        "session_id": "ses_nodesc",
        "title": "Fisika Dasar Gelombang",
        "description": "",
        "learning_goal": "UNDERSTAND",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "ONLINE",
    }
    # Kasus B: Dengan description -> title. description
    ses_with_desc = {
        "session_id": "ses_desc",
        "title": "Fisika Dasar Gelombang",
        "description": "Interferensi dan Difraksi Cahaya",
        "learning_goal": "UNDERSTAND",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "ONLINE",
    }
    intent_detailed = {
        "intent_id": "int_det",
        "student_id": "std_1",
        "topics": "Interferensi dan Difraksi Cahaya",
        "learning_goal": "UNDERSTAND",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "ONLINE",
    }
    slot_std = [{
        "date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1
    }]
    res_no_desc = calculate_session_score(intent_detailed, ses_no_desc, slot_std)
    res_with_desc = calculate_session_score(intent_detailed, ses_with_desc, slot_std)
    report("Session Topic: Deskripsi memperluas konteks pencocokan topik", res_with_desc["total_score"] > res_no_desc["total_score"])
    report("Session Topic: Nilai topic similarity lebih tinggi dengan deskripsi", (
        res_with_desc["components"]["topic"]["score"] > res_no_desc["components"]["topic"]["score"]
    ))

    # 15.4 Integrasi Matriks Goal, Style, dan Mode (termasuk Alias)
    intent_alias = {
        "intent_id": "int_alias",
        "student_id": "std_1",
        "topics": "Kalkulus Lanjut Integral",
        "learning_goal": "CONCEPT",        # Alias UNDERSTAND
        "collaboration_style": "TEACHING", # Alias PEER_TUTORING
        "learning_mode": "CAMPURAN",       # Alias HYBRID
    }
    ses_alias = {
        "session_id": "ses_alias",
        "title": "Kalkulus Lanjut Integral",
        "description": "",
        "learning_goal": "EXAM_PREP",      # Alias EXAM_PREPARATION
        "collaboration_style": "DISCUSSION",
        "learning_mode": "LURING",         # Alias OFFLINE
    }
    res_alias = calculate_session_score(intent_alias, ses_alias, slot_std)
    # UNDERSTAND x EXAM_PREPARATION = 0.80
    report("Session Matrices: Goal UNDERSTAND x EXAM_PREP == 0.80", math.isclose(res_alias["components"]["goal"]["score"], 0.80))
    # PEER_TUTORING x DISCUSSION = 0.85
    report("Session Matrices: Style PEER_TUTORING x DISCUSSION == 0.85", math.isclose(res_alias["components"]["style"]["score"], 0.85))
    # HYBRID x OFFLINE = 0.85
    report("Session Matrices: Mode HYBRID x OFFLINE == 0.85", math.isclose(res_alias["components"]["mode"]["score"], 0.85))

    # 15.5 Prioritas Sesi (priority_b default 1 atau nilai spesifik)
    slot_no_priob = [{
        "date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1
    }]
    res_no_pb = calculate_session_score(intent_perf, session_perf, slot_no_priob)
    report("Session Priority: priority_b default ke 1 jika tidak disediakan", res_no_pb["selected_schedule"]["priority_b"] == 1)

    slot_with_pb = [{
        "date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 2
    }]
    res_with_pb = calculate_session_score(intent_perf, session_perf, slot_with_pb)
    report("Session Priority: priority_b dipertahankan jika disediakan", res_with_pb["selected_schedule"]["priority_b"] == 2)

    # 15.6 Multi-Slot Schedule Selection & 4-Tier Deterministic Tie-Breaker
    # Kasus A: Tier 1 - Date Score tertinggi
    slots_tier1 = [
        {"date": "2026-11-16", "start_time": "10:00", "end_time": "11:00", "duration_minutes": 60, "priority_a": 1},  # D=0.85
        {"date": "2026-11-16", "start_time": "14:00", "end_time": "16:00", "duration_minutes": 120, "priority_a": 1}, # D=1.00
    ]
    res_t1 = calculate_session_score(intent_perf, session_perf, slots_tier1)
    report("Session Tie-Breaker: Tier 1 Date Score tertinggi dipilih", res_t1["selected_schedule"]["duration_minutes"] == 120)

    # Kasus B: Tier 2 - Durasi terpanjang saat Date Score sama
    # Slot 1: 120 menit, prio 1 (D=1.00) vs Slot 2: 150 menit, prio 1 (D=1.00)
    slots_tier2 = [
        {"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1},
        {"date": "2026-11-16", "start_time": "14:00", "end_time": "16:30", "duration_minutes": 150, "priority_a": 1},
    ]
    res_t2 = calculate_session_score(intent_perf, session_perf, slots_tier2)
    report("Session Tie-Breaker: Tier 2 Durasi terpanjang (150 vs 120 menit) dipilih saat Date Score sama (1.00)", (
        res_t2["selected_schedule"]["duration_minutes"] == 150 and math.isclose(res_t2["selected_schedule"]["date_score"], 1.00)
    ))

    # Kasus C: Tier 3 - Priority_a terbaik saat durasi sama (prio 1 > prio 2)
    slots_tier3 = [
        {"date": "2026-11-16", "start_time": "10:00", "end_time": "11:30", "duration_minutes": 90, "priority_a": 2}, # prio 2 (D=0.73)
        {"date": "2026-11-16", "start_time": "14:00", "end_time": "15:30", "duration_minutes": 90, "priority_a": 1}, # prio 1 (D=0.94)
    ]
    res_t3 = calculate_session_score(intent_perf, session_perf, slots_tier3)
    report("Session Tie-Breaker: Tier 3 Priority_a terbaik (1 vs 2) dipilih", res_t3["selected_schedule"]["priority_a"] == 1)

    # Kasus D: Tier 4 - Tanggal lebih awal saat date_score, durasi, dan priority sama
    slots_tier4_date = [
        {"date": "2026-11-20", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1},
        {"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1},
    ]
    res_t4d = calculate_session_score(intent_perf, session_perf, slots_tier4_date)
    report("Session Tie-Breaker: Tier 4 Tanggal paling awal (16 vs 20) dipilih", res_t4d["selected_schedule"]["date"] == "2026-11-16")

    # Kasus E: Tier 4 - Jam mulai lebih awal pada tanggal yang sama
    slots_tier4_time = [
        {"date": "2026-11-16", "start_time": "14:00", "end_time": "16:00", "duration_minutes": 120, "priority_a": 1},
        {"date": "2026-11-16", "start_time": "09:00", "end_time": "11:00", "duration_minutes": 120, "priority_a": 1},
    ]
    res_t4t = calculate_session_score(intent_perf, session_perf, slots_tier4_time)
    report("Session Tie-Breaker: Tier 4 Jam mulai paling awal (09:00 vs 14:00) dipilih", res_t4t["selected_schedule"]["start_time"] == "09:00")

    # 15.7 Common Slots Kosong & Format Invalid Ditolak (ValueError)
    def assert_session_error(slots, label):
        try:
            calculate_session_score(intent_perf, session_perf, slots)
            report(f"Session Validation: {label}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Session Validation: {label}", True)

    assert_session_error([], "Tolak common_slots kosong")
    assert_session_error(["bukan dict"], "Tolak slot bukan Mapping")
    assert_session_error([{"date": "2026-11-16"}], "Tolak slot tanpa field wajib")
    assert_session_error([{"date": "2026-13-40", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1}], "Tolak format tanggal invalid")
    assert_session_error([{"date": "2026-1-6", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1}], "Tolak format tanggal tanpa zero padding bulan (2026-1-6)")
    assert_session_error([{"date": "2026-01-6", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1}], "Tolak format tanggal tanpa zero padding hari (2026-01-6)")
    assert_session_error([{"date": "2026-02-30", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1}], "Tolak tanggal kalender fiktif (2026-02-30)")
    assert_session_error([{"date": "2026-11-16", "start_time": "25:00", "end_time": "26:00", "duration_minutes": 60, "priority_a": 1}], "Tolak format jam invalid")
    assert_session_error([{"date": "2026-11-16", "start_time": "9:00", "end_time": "11:00", "duration_minutes": 120, "priority_a": 1}], "Tolak start_time tanpa zero padding (9:00)")
    assert_session_error([{"date": "2026-11-16", "start_time": "09:0", "end_time": "11:00", "duration_minutes": 120, "priority_a": 1}], "Tolak start_time tanpa zero padding menit (09:0)")
    assert_session_error([{"date": "2026-11-16", "start_time": "09:00", "end_time": "11:0", "duration_minutes": 120, "priority_a": 1}], "Tolak end_time tanpa zero padding menit (11:0)")
    assert_session_error([{"date": "2026-11-16", "start_time": "14:00", "end_time": "10:00", "duration_minutes": 60, "priority_a": 1}], "Tolak waktu selesai lebih awal dari mulai")
    assert_session_error([{"date": "2026-11-16", "start_time": "10:00", "end_time": "10:59", "duration_minutes": 59, "priority_a": 1}], "Tolak durasi < 60 menit")
    assert_session_error([{"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 90, "priority_a": 1}], "Tolak duration_minutes tidak konsisten dengan selisih waktu")
    assert_session_error([{"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 4}], "Tolak priority_a di luar {1, 2, 3}")
    assert_session_error([{"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": True}], "Tolak priority_a bertipe boolean")
    assert_session_error([{"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 0}], "Tolak priority_b di luar {1, 2, 3}")

    # 15.8 Dukungan Format Objek ORM, Dict, dan Pydantic
    orm_intent = DummyORMIntent("int_orm", "std_1", "Struktur Data Pohon Biner", "PRACTICE", "PRACTICE", "ONLINE")
    orm_session = DummyORMSession("ses_orm", "Struktur Data Pohon Biner", "", "PRACTICE", "PRACTICE", "ONLINE")
    res_orm = calculate_session_score(orm_intent, orm_session, slot_perf)
    report("Session Object Support: ORM model menghasilkan skor 100", math.isclose(res_orm["total_score"], 100.00))

    pyd_intent = DummyPydanticIntent(
        intent_id="int_pyd", student_id="std_1", topics="Struktur Data Pohon Biner",
        learning_goal="PRACTICE", collaboration_style="PRACTICE", learning_mode="ONLINE"
    )
    pyd_session = DummyPydanticSession(
        session_id="ses_pyd", title="Struktur Data Pohon Biner", description="",
        learning_goal="PRACTICE", collaboration_style="PRACTICE", learning_mode="ONLINE"
    )
    res_pyd = calculate_session_score(pyd_intent, pyd_session, slot_perf)
    report("Session Object Support: Pydantic model menghasilkan skor 100", math.isclose(res_pyd["total_score"], 100.00))
    report("Session Object Support: ORM, Dict, dan Pydantic identik", res_perf["total_score"] == res_orm["total_score"] == res_pyd["total_score"])

    # 15.9 Penolakan Mandatory Objek & Field Kosong
    def assert_obj_error(i, s, label):
        try:
            calculate_session_score(i, s, slot_perf)
            report(f"Session Mandatory: {label}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Session Mandatory: {label}", True)

    assert_obj_error(None, session_perf, "Tolak intent None")
    assert_obj_error(intent_perf, None, "Tolak session None")
    assert_obj_error(dict(intent_perf, topics=""), session_perf, "Tolak intent topics kosong")
    assert_obj_error(intent_perf, dict(session_perf, title=""), "Tolak session title kosong")
    assert_obj_error(dict(intent_perf, learning_goal=None), session_perf, "Tolak intent tanpa goal")
    assert_obj_error(intent_perf, dict(session_perf, learning_goal=None), "Tolak session tanpa goal")
    assert_obj_error(dict(intent_perf, collaboration_style=None), session_perf, "Tolak intent tanpa style")
    assert_obj_error(intent_perf, dict(session_perf, collaboration_style=None), "Tolak session tanpa style")
    assert_obj_error(dict(intent_perf, learning_mode=None), session_perf, "Tolak intent tanpa mode")
    assert_obj_error(intent_perf, dict(session_perf, learning_mode=None), "Tolak session tanpa mode")

    # 15.10 Konsistensi Breakdown
    sum_contrib = sum(comp["contribution"] for comp in res_a["components"].values())
    report("Session Breakdown: sum(contributions) tepat sama dengan total_score (99.10)", math.isclose(sum_contrib, res_a["total_score"]))


# ==============================================================================
# SUITE 16: PARTNER SCORING ENGINE (TAHAP 15.5)
# ==============================================================================

def test_partner_scoring():
    print("\n--- SUITE 16: Partner Scoring Engine (Tahap 15.5) ---")

    # 16.1 Skor Sempurna 100
    intent_perf_a = {
        "intent_id": "int_perf_a",
        "student_id": "std_andi",
        "topics": "Pemrograman Web React",
        "learning_goal": "PRACTICE",
        "collaboration_style": "PRACTICE",
        "learning_mode": "ONLINE",
    }
    intent_perf_b = {
        "intent_id": "int_perf_b",
        "student_id": "std_budi",
        "topics": "Pemrograman Web React",
        "learning_goal": "PRACTICE",
        "collaboration_style": "PRACTICE",
        "learning_mode": "ONLINE",
    }
    slot_perf_p = [{
        "date": "2026-11-16",
        "start_time": "10:00",
        "end_time": "12:00",
        "duration_minutes": 120,
        "priority_a": 1,
        "priority_b": 1,
    }]
    res_perf = calculate_partner_score(intent_perf_a, intent_perf_b, slot_perf_p)
    report("Partner Score: Skor sempurna 100.00", math.isclose(res_perf["total_score"], 100.00))
    report("Partner Score: candidate_type == 'PARTNER'", res_perf["candidate_type"] == "PARTNER")
    report("Partner Score: target_intent_id == 'int_perf_b'", res_perf["target_intent_id"] == "int_perf_b")
    report("Partner Score: student_id == 'std_budi'", res_perf["student_id"] == "std_budi")
    report("Partner Score: rounding_reconciliation 0.0", math.isclose(res_perf["rounding_reconciliation"], 0.0))
    report("Partner Score: 5 komponen sempurna bernilai 1.0", all(
        math.isclose(res_perf["components"][k]["score"], 1.0)
        for k in ["topic", "goal", "style", "date", "mode"]
    ))

    # 16.2 Benchmark 90.18 (Andi & Budi) dengan Nilai Komponen Eksplisit
    # T=1.00, G=0.85 (UNDERSTAND x PRACTICE), S=0.85 (DISCUSSION x PEER_TUTORING),
    # D=0.895 (120m, prio 1x2 -> 0.70*0.85 + 0.30*1.0), M=0.85 (HYBRID x OFFLINE)
    # Total = 100 * (0.30*1.0 + 0.25*0.85 + 0.15*0.85 + 0.15*0.895 + 0.15*0.85) = 90.175 -> 90.18
    intent_andi = {
        "intent_id": "intent-andi",
        "student_id": "student-andi",
        "topics": "Kalkulus Lanjut Integral",
        "learning_goal": "UNDERSTAND",
        "collaboration_style": "DISCUSSION",
        "learning_mode": "HYBRID",
    }
    intent_budi = {
        "intent_id": "intent-budi",
        "student_id": "student-budi",
        "topics": "Kalkulus Lanjut Integral",
        "learning_goal": "PRACTICE",
        "collaboration_style": "PEER_TUTORING",
        "learning_mode": "OFFLINE",
    }
    slots_budi = [{
        "date": "2026-11-16",
        "start_time": "10:00",
        "end_time": "12:00",
        "duration_minutes": 120,
        "priority_a": 1,
        "priority_b": 2,
    }]
    res_budi = calculate_partner_score(intent_andi, intent_budi, slots_budi)
    report("Partner Benchmark: Total score tepat 90.18", math.isclose(res_budi["total_score"], 90.18))
    report("Partner Benchmark: rounding_reconciliation tepat 0.0", math.isclose(res_budi["rounding_reconciliation"], 0.0))
    report("Partner Benchmark: Topic score tepat 1.00", math.isclose(res_budi["components"]["topic"]["score"], 1.00))
    report("Partner Benchmark: Goal score tepat 0.85", math.isclose(res_budi["components"]["goal"]["score"], 0.85))
    report("Partner Benchmark: Style score tepat 0.85", math.isclose(res_budi["components"]["style"]["score"], 0.85))
    report("Partner Benchmark: Date score tepat 0.895", math.isclose(res_budi["components"]["date"]["score"], 0.895))
    report("Partner Benchmark: Mode score tepat 0.85", math.isclose(res_budi["components"]["mode"]["score"], 0.85))
    report("Partner Benchmark: Date contribution terekonsiliasi tepat 13.43", math.isclose(res_budi["components"]["date"]["contribution"], 13.43))
    sum_budi = sum(comp["contribution"] for comp in res_budi["components"].values())
    report("Partner Benchmark: Jumlah kontribusi tepat 90.18", math.isclose(sum_budi, 90.18))

    # 16.3 Prioritas Pasangan & priority_pair_key (Minimax)
    # Slot 1: prio_a=1, prio_b=3 -> minimax=3, priority_score = 0.55
    # Slot 2: prio_a=2, prio_b=2 -> minimax=2, priority_score = 0.70
    slots_minimax = [
        {"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 3},
        {"date": "2026-11-16", "start_time": "14:00", "end_time": "16:00", "duration_minutes": 120, "priority_a": 2, "priority_b": 2},
    ]
    res_mm = calculate_partner_score(intent_perf_a, intent_perf_b, slots_minimax)
    report("Partner Minimax: Slot dengan minimax lebih baik (2, 2) dipilih dibanding (1, 3)", (
        res_mm["selected_schedule"]["priority_a"] == 2 and res_mm["selected_schedule"]["priority_b"] == 2
    ))

    # 16.4 Multi-Slot Schedule Selection & 4-Tier Tie-Breaker
    # Tier 2: Durasi terpanjang saat Date Score sama
    # Slot 1: 120 menit, prio (1, 2) -> D=0.895 vs Slot 2: 150 menit, prio (1, 2) -> D=0.895
    slots_tier2_p = [
        {"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 2},
        {"date": "2026-11-16", "start_time": "14:00", "end_time": "16:30", "duration_minutes": 150, "priority_a": 1, "priority_b": 2},
    ]
    res_t2_p = calculate_partner_score(intent_perf_a, intent_perf_b, slots_tier2_p)
    report("Partner Tie-Breaker: Tier 2 Durasi terpanjang (150 vs 120 menit) dipilih saat Date Score sama (0.895)", (
        res_t2_p["selected_schedule"]["duration_minutes"] == 150 and math.isclose(res_t2_p["selected_schedule"]["date_score"], 0.895)
    ))

    # Tier 3: priority_pair_key pemecah seri (1, 2) vs (2, 1) -> (1, 2) menang karena prio_a lebih kecil
    slots_tie_prio = [
        {"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 2, "priority_b": 1},
        {"date": "2026-11-16", "start_time": "14:00", "end_time": "16:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 2},
    ]
    res_tp = calculate_partner_score(intent_perf_a, intent_perf_b, slots_tie_prio)
    report("Partner Tie-Breaker: priority_pair_key memilih (1, 2) dibanding (2, 1)", (
        res_tp["selected_schedule"]["priority_a"] == 1 and res_tp["selected_schedule"]["priority_b"] == 2
    ))

    # Tier 4: Tanggal paling awal saat Date Score, durasi, dan pasangan prioritas identik
    slots_tie_date = [
        {"date": "2026-11-20", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 1},
        {"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 1},
    ]
    res_td = calculate_partner_score(intent_perf_a, intent_perf_b, slots_tie_date)
    report("Partner Tie-Breaker: Tanggal paling awal (16 vs 20) dipilih", res_td["selected_schedule"]["date"] == "2026-11-16")

    # 16.5 Penilaian Terpisah 2 Intent dari Mahasiswa yang Sama
    cand_budi_intent1 = {
        "intent_id": "int_budi_1",
        "student_id": "std_budi",
        "topics": "Kalkulus Lanjut Integral",
        "learning_goal": "PRACTICE",
        "collaboration_style": "PEER_TUTORING",
        "learning_mode": "OFFLINE",
    }
    cand_budi_intent2 = {
        "intent_id": "int_budi_2",
        "student_id": "std_budi",
        "topics": "Fisika Dasar Termodinamika",
        "learning_goal": "PROJECT",
        "collaboration_style": "FOCUS_STUDY",
        "learning_mode": "OFFLINE",
    }
    res_b1 = calculate_partner_score(intent_andi, cand_budi_intent1, slots_budi)
    res_b2 = calculate_partner_score(intent_andi, cand_budi_intent2, slots_budi)
    report("Partner Multi-Intent: Kedua intent dinilai secara independen", res_b1["target_intent_id"] != res_b2["target_intent_id"])
    report("Partner Multi-Intent: Kedua hasil memiliki student_id yang sama", res_b1["student_id"] == res_b2["student_id"] == "std_budi")
    report("Partner Multi-Intent: Intent relevan menghasilkan skor lebih tinggi (90.18 vs <50)", res_b1["total_score"] > res_b2["total_score"])
    report("Partner Multi-Intent: Skor intent 1 tepat 90.18", math.isclose(res_b1["total_score"], 90.18))

    # 16.6 Validasi Input & Penolakan Mandatory (ValueError)
    def assert_partner_error(ia, ib, slots, label):
        try:
            calculate_partner_score(ia, ib, slots)
            report(f"Partner Validation: {label}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Partner Validation: {label}", True)

    assert_partner_error(None, intent_perf_b, slot_perf_p, "Tolak intent_a None")
    assert_partner_error(intent_perf_a, None, slot_perf_p, "Tolak intent_b None")
    assert_partner_error(intent_perf_a, intent_perf_b, [], "Tolak common_slots kosong")
    assert_partner_error(
        intent_perf_a, intent_perf_b,
        [{"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1}],
        "Tolak slot tanpa priority_b untuk partner"
    )
    assert_partner_error(
        intent_perf_a, intent_perf_b,
        [{"date": "2026-11-16", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 4}],
        "Tolak priority_b di luar {1, 2, 3}"
    )
    assert_partner_error(
        intent_perf_a, intent_perf_b,
        [{"date": "2026-1-6", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 1}],
        "Tolak partner slot tanpa zero padding bulan (2026-1-6)"
    )
    assert_partner_error(
        intent_perf_a, intent_perf_b,
        [{"date": "2026-01-6", "start_time": "10:00", "end_time": "12:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 1}],
        "Tolak partner slot tanpa zero padding hari (2026-01-6)"
    )
    assert_partner_error(
        intent_perf_a, intent_perf_b,
        [{"date": "2026-11-16", "start_time": "9:00", "end_time": "11:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 1}],
        "Tolak start_time partner tanpa zero padding (9:00)"
    )
    assert_partner_error(
        intent_perf_a, intent_perf_b,
        [{"date": "2026-11-16", "start_time": "09:0", "end_time": "11:00", "duration_minutes": 120, "priority_a": 1, "priority_b": 1}],
        "Tolak start_time partner tanpa zero padding menit (09:0)"
    )
    assert_partner_error(
        intent_perf_a, dict(intent_perf_b, student_id=None), slot_perf_p, "Tolak intent_b tanpa student_id"
    )
    assert_partner_error(
        dict(intent_perf_a, topics=""), intent_perf_b, slot_perf_p, "Tolak intent_a topics kosong"
    )
    assert_partner_error(
        intent_perf_a, dict(intent_perf_b, topics=""), slot_perf_p, "Tolak intent_b topics kosong"
    )
    assert_partner_error(
        dict(intent_perf_a, learning_goal=None), intent_perf_b, slot_perf_p, "Tolak intent_a tanpa goal"
    )
    assert_partner_error(
        intent_perf_a, dict(intent_perf_b, learning_goal=None), slot_perf_p, "Tolak intent_b tanpa goal"
    )
    assert_partner_error(
        dict(intent_perf_a, collaboration_style=None), intent_perf_b, slot_perf_p, "Tolak intent_a tanpa style"
    )
    assert_partner_error(
        intent_perf_a, dict(intent_perf_b, collaboration_style=None), slot_perf_p, "Tolak intent_b tanpa style"
    )
    assert_partner_error(
        dict(intent_perf_a, learning_mode=None), intent_perf_b, slot_perf_p, "Tolak intent_a tanpa mode"
    )
    assert_partner_error(
        intent_perf_a, dict(intent_perf_b, learning_mode=None), slot_perf_p, "Tolak intent_b tanpa mode"
    )

    # 16.7 Dukungan Format ORM, Dict, dan Pydantic
    orm_ia = DummyORMIntent("int_orm_a", "std_andi", "Pemrograman Web React", "PRACTICE", "PRACTICE", "ONLINE")
    orm_ib = DummyORMIntent("int_orm_b", "std_budi", "Pemrograman Web React", "PRACTICE", "PRACTICE", "ONLINE")
    res_orm_p = calculate_partner_score(orm_ia, orm_ib, slot_perf_p)
    report("Partner Object Support: ORM model menghasilkan skor 100", math.isclose(res_orm_p["total_score"], 100.00))

    pyd_ia = DummyPydanticIntent(
        intent_id="int_pyd_a", student_id="std_andi", topics="Pemrograman Web React",
        learning_goal="PRACTICE", collaboration_style="PRACTICE", learning_mode="ONLINE"
    )
    pyd_ib = DummyPydanticIntent(
        intent_id="int_pyd_b", student_id="std_budi", topics="Pemrograman Web React",
        learning_goal="PRACTICE", collaboration_style="PRACTICE", learning_mode="ONLINE"
    )
    res_pyd_p = calculate_partner_score(pyd_ia, pyd_ib, slot_perf_p)
    report("Partner Object Support: Pydantic model menghasilkan skor 100", math.isclose(res_pyd_p["total_score"], 100.00))
    report("Partner Object Support: ORM, Dict, dan Pydantic identik", res_perf["total_score"] == res_orm_p["total_score"] == res_pyd_p["total_score"])

    # 16.8 Invariansi Bobot & Formula Tahap 15.4
    report("Partner Invariance: Bobot Topic == 0.30", math.isclose(WEIGHT_TOPIC, 0.30))
    report("Partner Invariance: Bobot Goal == 0.25", math.isclose(WEIGHT_GOAL, 0.25))
    report("Partner Invariance: Bobot Style == 0.15", math.isclose(WEIGHT_STYLE, 0.15))
    report("Partner Invariance: Bobot Date == 0.15", math.isclose(WEIGHT_DATE, 0.15))
    report("Partner Invariance: Bobot Mode == 0.15", math.isclose(WEIGHT_MODE, 0.15))

    # 16.9 Konsistensi Breakdown
    sum_contrib_p = sum(comp["contribution"] for comp in res_budi["components"].values())
    report("Partner Breakdown: sum(contributions) tepat sama dengan total_score (90.18)", math.isclose(sum_contrib_p, res_budi["total_score"]))


def run_tests():
    print("=" * 70)
    print("RUNNING DAY 15: SOFT CONSTRAINT SCORING TEST SUITE (TAHAP 15.1 - 15.5)")
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
    test_session_scoring()
    test_partner_scoring()

    print("\n" + "=" * 70)
    print(f"TEST RESULT SUMMARY: {passed_count}/{total_count} TESTS PASSED (100% SUCCESS)")
    print("=" * 70)
    assert passed_count == total_count, f"Some tests failed! ({passed_count}/{total_count})"


if __name__ == "__main__":
    run_tests()
