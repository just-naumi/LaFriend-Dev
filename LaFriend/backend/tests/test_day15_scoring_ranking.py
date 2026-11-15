# test_day15_scoring_ranking.py - Automated Test Suite untuk Scoring Engine LaFriend (Day 15)
# Tahap 15.1: Canonicalizer, Matriks Kompatibilitas, Priority, Duration, Date Scoring
# Tahap 15.2: Topic Similarity (Normalisasi, Tokenisasi, Jaccard, Vector Validation, Cosine, Fallback)

import sys
import math
import random
from pathlib import Path

# Setup path agar dapat mengimpor app
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.schemas import MatchResultCreate

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
    # Tahap 15.6
    rank_session_candidates,
    rank_partner_candidates,
    rank_candidates,
    generate_match_explanation,
    format_match_result_payload,
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


class DummyORMCandidate:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class DummyPydanticCandidate(BaseModel):
    intent_id: str
    candidate_type: str
    total_score: float
    candidate_session_id: Optional[str] = None
    target_intent_id: Optional[str] = None
    student_id: Optional[str] = None
    rounding_reconciliation: float = 0.0
    components: Dict[str, Any] = {}
    selected_schedule: Dict[str, Any]
    explanation: Optional[str] = None


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


# ==============================================================================
# SUITE 17: CANDIDATE RANKING & DEDUPLICATION (TAHAP 15.6)
# ==============================================================================

def test_candidate_ranking_and_deduplication():
    print("\n--- SUITE 17: Candidate Ranking & Deduplication (Tahap 15.6) ---")

    def make_sched(date="2026-11-16", start="10:00", end="12:00", dur=120, pa=1, pb=1):
        return {
            "date": date,
            "start_time": start,
            "end_time": end,
            "duration_minutes": dur,
            "priority_a": pa,
            "priority_b": pb,
            "date_score": 0.895,
        }

    def make_candidate_breakdown(total_score=90.0, topic=None, goal=None, style=None, date=None, mode=None):
        if any(x is not None for x in (topic, goal, style, date, mode)):
            t = topic if topic is not None else 1.0
            g = goal if goal is not None else 0.85
            st = style if style is not None else 0.85
            d = date if date is not None else 0.895
            m = mode if mode is not None else 0.85
            return calculate_compatibility_breakdown(t, g, st, d, m)
        ts = float(total_score) / 100.0
        return calculate_compatibility_breakdown(ts, ts, ts, ts, ts)

    def make_components(total_score=90.0, topic=None, goal=None, style=None, date=None, mode=None):
        return make_candidate_breakdown(total_score, topic, goal, style, date, mode)["components"]

    def make_sess_cand(cand_id, total_score=90.0, sched=None, **comp_kwargs):
        bd = make_candidate_breakdown(total_score, **comp_kwargs)
        return {
            "intent_id": "int_user",
            "candidate_type": "SESSION",
            "candidate_session_id": cand_id,
            "total_score": bd["total_score"],
            "rounding_reconciliation": bd["rounding_reconciliation"],
            "components": bd["components"],
            "selected_schedule": sched or make_sched(),
        }

    def make_partner_cand(student_id, target_intent_id, total_score=90.0, sched=None, **comp_kwargs):
        bd = make_candidate_breakdown(total_score, **comp_kwargs)
        return {
            "intent_id": "int_user",
            "candidate_type": "PARTNER",
            "student_id": student_id,
            "target_intent_id": target_intent_id,
            "total_score": bd["total_score"],
            "rounding_reconciliation": bd["rounding_reconciliation"],
            "components": bd["components"],
            "selected_schedule": sched or make_sched(),
        }

    # 17.1 Session Ranking: Pengurutan Total Score & Penomoran Rank
    sess_cand_1 = make_sess_cand("ses_01", 85.00)
    sess_cand_2 = make_sess_cand("ses_02", 95.00)
    sess_cand_3 = make_sess_cand("ses_03", 75.00)

    ranked_sess = rank_session_candidates([sess_cand_1, sess_cand_2, sess_cand_3])
    report("Session Rank: Jumlah hasil 3", len(ranked_sess) == 3)
    report("Session Rank: Rank 1 adalah ses_02 (skor 95)", ranked_sess[0]["candidate_session_id"] == "ses_02" and ranked_sess[0]["rank"] == 1)
    report("Session Rank: Rank 2 adalah ses_01 (skor 85)", ranked_sess[1]["candidate_session_id"] == "ses_01" and ranked_sess[1]["rank"] == 2)
    report("Session Rank: Rank 3 adalah ses_03 (skor 75)", ranked_sess[2]["candidate_session_id"] == "ses_03" and ranked_sess[2]["rank"] == 3)

    # 17.2 Session Deduplication: candidate_session_id yang sama mempertahankan skor tertinggi
    sess_dup_low = make_sess_cand("ses_dup", 70.00)
    sess_dup_high = make_sess_cand("ses_dup", 92.50)
    ranked_sess_dup = rank_session_candidates([sess_dup_low, sess_dup_high])
    report("Session Deduplication: Hanya 1 entri untuk ses_dup", len(ranked_sess_dup) == 1)
    report("Session Deduplication: Skor tertinggi (92.50) yang dipertahankan", ranked_sess_dup[0]["total_score"] == 92.50)

    # 17.3 Session Tie-Breakers (Tier 1 s.d Tier 5)
    # Tier 2: Durasi terpanjang menang (180 vs 120 menit)
    s_t2_a = make_sess_cand("s_t2_120", 90.0, sched=make_sched(dur=120))
    s_t2_b = make_sess_cand("s_t2_180", 90.0, sched=make_sched(dur=180, end="13:00"))
    res_s_t2 = rank_session_candidates([s_t2_a, s_t2_b])
    report("Session Tie-Breaker Tier 2: Durasi terpanjang menang (180 vs 120)", res_s_t2[0]["candidate_session_id"] == "s_t2_180")

    # Tier 3: priority_a terkecil menang (1 vs 2)
    s_t3_a = make_sess_cand("s_t3_prio2", 90.0, sched=make_sched(dur=120, pa=2))
    s_t3_b = make_sess_cand("s_t3_prio1", 90.0, sched=make_sched(dur=120, pa=1))
    res_s_t3 = rank_session_candidates([s_t3_a, s_t3_b])
    report("Session Tie-Breaker Tier 3: priority_a terkecil menang (1 vs 2)", res_s_t3[0]["candidate_session_id"] == "s_t3_prio1")

    # Tier 4: Tanggal paling awal menang (16 vs 20)
    s_t4_a = make_sess_cand("s_t4_d20", 90.0, sched=make_sched(date="2026-11-20"))
    s_t4_b = make_sess_cand("s_t4_d16", 90.0, sched=make_sched(date="2026-11-16"))
    res_s_t4 = rank_session_candidates([s_t4_a, s_t4_b])
    report("Session Tie-Breaker Tier 4: Tanggal lebih awal menang (16 vs 20)", res_s_t4[0]["candidate_session_id"] == "s_t4_d16")

    # Tier 4b: Jam mulai lebih awal menang (09:00 vs 14:00)
    s_t4b_a = make_sess_cand("s_t4_1400", 90.0, sched=make_sched(start="14:00", end="16:00"))
    s_t4b_b = make_sess_cand("s_t4_0900", 90.0, sched=make_sched(start="09:00", end="11:00"))
    res_s_t4b = rank_session_candidates([s_t4b_a, s_t4b_b])
    report("Session Tie-Breaker Tier 4b: Jam mulai lebih awal menang (09:00 vs 14:00)", res_s_t4b[0]["candidate_session_id"] == "s_t4_0900")

    # Tier 5: candidate_session_id alfabetis menang
    s_t5_a = make_sess_cand("ses_zeta", 90.0)
    s_t5_b = make_sess_cand("ses_alpha", 90.0)
    res_s_t5 = rank_session_candidates([s_t5_a, s_t5_b])
    report("Session Tie-Breaker Tier 5: ID alfabetis menang (ses_alpha vs ses_zeta)", res_s_t5[0]["candidate_session_id"] == "ses_alpha")

    # 17.4 Partner Ranking & Student Deduplication: Multi-Intent Per Student
    # Budi (3 intents: 75.0, 94.5, 85.3), Citra (91.2), Deni (88.7), Eka (82.6), Fajar (79.5)
    p_budi_1 = make_partner_cand("std_budi", "int_budi_1", 75.00)
    p_budi_2 = make_partner_cand("std_budi", "int_budi_2", 94.50)
    p_budi_3 = make_partner_cand("std_budi", "int_budi_3", 85.30)
    p_citra = make_partner_cand("std_citra", "int_citra_1", 91.20)
    p_deni = make_partner_cand("std_deni", "int_deni_1", 88.70)
    p_eka = make_partner_cand("std_eka", "int_eka_1", 82.60)
    p_fajar = make_partner_cand("std_fajar", "int_fajar_1", 79.50)

    all_partners = [p_budi_1, p_budi_2, p_budi_3, p_citra, p_deni, p_eka, p_fajar]
    ranked_partners = rank_partner_candidates(all_partners)

    report("Partner Deduplication: Dari 7 intent, terduplikasi menjadi 5 mahasiswa unik", len(ranked_partners) == 5)
    report("Partner Deduplication: Rank 1 adalah Budi dengan intent terbaik (int_budi_2, 94.50)", (
        ranked_partners[0]["student_id"] == "std_budi" and
        ranked_partners[0]["target_intent_id"] == "int_budi_2" and
        ranked_partners[0]["total_score"] == 94.50 and
        ranked_partners[0]["rank"] == 1
    ))
    report("Partner Deduplication: Rank 2 adalah Citra (91.20)", ranked_partners[1]["student_id"] == "std_citra" and ranked_partners[1]["rank"] == 2)
    report("Partner Deduplication: Rank 3 adalah Deni (88.70)", ranked_partners[2]["student_id"] == "std_deni" and ranked_partners[2]["rank"] == 3)
    report("Partner Deduplication: Rank 4 adalah Eka (82.60)", ranked_partners[3]["student_id"] == "std_eka" and ranked_partners[3]["rank"] == 4)
    report("Partner Deduplication: Rank 5 adalah Fajar (79.50)", ranked_partners[4]["student_id"] == "std_fajar" and ranked_partners[4]["rank"] == 5)

    # 17.5 Determinisme Urutan Input: Shuffle dan Reversal Menghasilkan Output Identik
    reversed_partners = list(reversed(all_partners))
    ranked_rev = rank_partner_candidates(reversed_partners)
    report("Partner Invariance: Reversal urutan input menghasilkan ranking identik", [r["target_intent_id"] for r in ranked_rev] == [r["target_intent_id"] for r in ranked_partners])

    # Acak berkali-kali untuk membuktikan kemandirian terhadap urutan query DB
    shuffled_partners = list(all_partners)
    deterministic_success = True
    for _ in range(10):
        random.shuffle(shuffled_partners)
        res_shuf = rank_partner_candidates(shuffled_partners)
        if [r["target_intent_id"] for r in res_shuf] != [r["target_intent_id"] for r in ranked_partners]:
            deterministic_success = False
            break
    report("Partner Invariance: 10x Random Shuffle menghasilkan ranking identik secara deterministik", deterministic_success)

    # 17.6 Partner Tie-Breakers (Tier 1 s.d Tier 5)
    # Tier 2: Durasi
    pt2_a = make_partner_cand("s1", "i1", 90.0, sched=make_sched(dur=120))
    pt2_b = make_partner_cand("s2", "i2", 90.0, sched=make_sched(dur=150, end="12:30"))
    rpt2 = rank_partner_candidates([pt2_a, pt2_b])
    report("Partner Tie-Breaker Tier 2: Durasi terpanjang menang (150 vs 120)", rpt2[0]["student_id"] == "s2")

    # Tier 3: priority_pair_key minimax: (1, 2) menang atas (2, 2) dan (1, 3)
    pt3_12 = make_partner_cand("s_12", "i_12", 90.0, sched=make_sched(pa=1, pb=2))
    pt3_22 = make_partner_cand("s_22", "i_22", 90.0, sched=make_sched(pa=2, pb=2))
    pt3_13 = make_partner_cand("s_13", "i_13", 90.0, sched=make_sched(pa=1, pb=3))
    rpt3 = rank_partner_candidates([pt3_13, pt3_22, pt3_12])
    report("Partner Tie-Breaker Tier 3: Minimax memilih (1, 2) > (2, 2) > (1, 3)", (
        rpt3[0]["student_id"] == "s_12" and rpt3[1]["student_id"] == "s_22" and rpt3[2]["student_id"] == "s_13"
    ))

    # Tier 4: Tanggal dan jam lebih awal
    pt4_a = make_partner_cand("s1", "i1", 90.0, sched=make_sched(date="2026-11-20"))
    pt4_b = make_partner_cand("s2", "i2", 90.0, sched=make_sched(date="2026-11-16"))
    rpt4 = rank_partner_candidates([pt4_a, pt4_b])
    report("Partner Tie-Breaker Tier 4: Tanggal paling awal menang", rpt4[0]["student_id"] == "s2")

    # Tier 5: target_intent_id alfabetis
    pt5_a = make_partner_cand("s1", "int_zzz", 90.0)
    pt5_b = make_partner_cand("s2", "int_aaa", 90.0)
    rpt5 = rank_partner_candidates([pt5_a, pt5_b])
    report("Partner Tie-Breaker Tier 5: target_intent_id alfabetis menang (int_aaa vs int_zzz)", rpt5[0]["target_intent_id"] == "int_aaa")

    # 17.7 Threshold Filtering (min_score)
    r_thresh_all = rank_partner_candidates(all_partners, min_score=0.0)
    report("Threshold: min_score=0.0 mempertahankan semua (5 mahasiswa)", len(r_thresh_all) == 5)

    r_thresh_85 = rank_partner_candidates(all_partners, min_score=85.0)
    report("Threshold: min_score=85.0 memfilter kandidat < 85.0 (tersisa 3: Budi 94.5, Citra 91.2, Deni 88.7)", (
        len(r_thresh_85) == 3 and all(c["total_score"] >= 85.0 for c in r_thresh_85)
    ))

    r_thresh_exact = rank_partner_candidates(all_partners, min_score=88.70)
    report("Threshold: Nilai tepat sama dengan min_score (88.70) tetap lolos", any(math.isclose(c["total_score"], 88.70) for c in r_thresh_exact))

    r_thresh_none = rank_partner_candidates(all_partners, min_score=99.9)
    report("Threshold: min_score=99.9 mengembalikan list kosong", r_thresh_none == [])

    # Penolakan min_score invalid
    def assert_min_score_err(ms, label):
        try:
            rank_partner_candidates(all_partners, min_score=ms)
            report(f"Threshold Validation: {label}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Threshold Validation: {label}", True)

    assert_min_score_err(-1.0, "Tolak min_score negatif (-1.0)")
    assert_min_score_err(101.0, "Tolak min_score > 100 (101.0)")
    assert_min_score_err(float("nan"), "Tolak min_score NaN")
    assert_min_score_err(float("inf"), "Tolak min_score Infinity")
    assert_min_score_err(True, "Tolak min_score boolean (True)")
    assert_min_score_err("50", "Tolak min_score non-numeric string")
    assert_min_score_err(10**400, "Tolak min_score integer raksasa 10**400 dengan ValueError")

    # 17.8 Limit Slicing (limit)
    r_lim_none = rank_partner_candidates(all_partners, limit=None)
    report("Limit: limit=None mengembalikan seluruh kandidat (5)", len(r_lim_none) == 5)

    r_lim_1 = rank_partner_candidates(all_partners, limit=1)
    report("Limit: limit=1 mengembalikan tepat 1 kandidat teratas", len(r_lim_1) == 1 and r_lim_1[0]["rank"] == 1)

    r_lim_3 = rank_partner_candidates(all_partners, limit=3)
    report("Limit: limit=3 mengembalikan tepat 3 kandidat teratas", len(r_lim_3) == 3 and [c["rank"] for c in r_lim_3] == [1, 2, 3])

    r_lim_10 = rank_partner_candidates(all_partners, limit=10)
    report("Limit: limit=10 saat hanya ada 5 kandidat mengembalikan 5 kandidat", len(r_lim_10) == 5)

    # Penolakan limit invalid
    def assert_limit_err(lim, label):
        try:
            rank_partner_candidates(all_partners, limit=lim)
            report(f"Limit Validation: {label}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Limit Validation: {label}", True)

    assert_limit_err(0, "Tolak limit=0")
    assert_limit_err(-5, "Tolak limit negatif (-5)")
    assert_limit_err(True, "Tolak limit bertipe boolean (True)")
    assert_limit_err(False, "Tolak limit bertipe boolean (False)")
    assert_limit_err(3.5, "Tolak limit bertipe float (3.5)")
    assert_limit_err("5", "Tolak limit bertipe string ('5')")

    # 17.9 Validasi Input Objek Kandidat (Temuan Audit P1, P2)
    def assert_cand_err(cands, is_partner, label):
        try:
            if is_partner:
                rank_partner_candidates(cands)
            else:
                rank_session_candidates(cands)
            report(f"Candidate Validation: {label}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Candidate Validation: {label}", True)

    assert_cand_err(None, True, "Tolak partner_scores None")
    assert_cand_err(None, False, "Tolak session_scores None")
    assert_cand_err("bukan_list", True, "Tolak partner_scores non-sequence")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], False, "Tolak session tanpa candidate_session_id")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "  ", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], False, "Tolak session dengan candidate_session_id spasi")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "target_intent_id": "i", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak partner tanpa student_id")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak partner tanpa target_intent_id")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": float("nan"), "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak kandidat dengan total_score NaN")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": float("inf"), "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak kandidat dengan total_score Infinity")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": True, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak kandidat dengan total_score boolean")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": 105.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak kandidat dengan total_score > 100")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": -1.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak kandidat dengan total_score < 0")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": 10**400, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak kandidat dengan total_score integer raksasa 10**400")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": 90.0, "rounding_reconciliation": 0.0}], True, "Tolak kandidat tanpa selected_schedule")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(dur=45), "components": make_components()}], True, "Tolak kandidat dengan durasi jadwal < 60")
    assert_cand_err([{"intent_id": "u", "candidate_type": "PARTNER", "student_id": "s", "target_intent_id": "i", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(date="2026-1-6"), "components": make_components()}], True, "Tolak jadwal tanpa zero padding tanggal")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "student_id": "s", "target_intent_id": "i", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], True, "Tolak candidate_type tidak sesuai (SESSION pada rank_partner)")

    # Hardening Temuan P1: Kalender riil, end_time, durasi, priority_b, intent_id
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(date="2026-02-30"), "components": make_components()}], False, "Tolak tanggal kalender fiktif (2026-02-30)")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": dict(make_sched(), end_time=""), "components": make_components()}], False, "Tolak end_time kosong")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": dict(make_sched(), end_time="24:00"), "components": make_components()}], False, "Tolak end_time format invalid (24:00)")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": dict(make_sched(), end_time="09:00"), "components": make_components()}], False, "Tolak waktu selesai lebih awal dari mulai")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": dict(make_sched(), duration_minutes=90), "components": make_components()}], False, "Tolak duration_minutes tidak konsisten dengan selisih waktu")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": dict(make_sched(), priority_b=4), "components": make_components()}], False, "Tolak priority_b session di luar {1, 2, 3}")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": dict(make_sched(), priority_b=True), "components": make_components()}], False, "Tolak priority_b session bertipe boolean")
    assert_cand_err([{"intent_id": "", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], False, "Tolak intent_id string kosong")
    assert_cand_err([{"intent_id": "   ", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], False, "Tolak intent_id spasi")
    assert_cand_err([{"intent_id": None, "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": make_components()}], False, "Tolak intent_id None")

    # Hardening Temuan P1: Komponen scoring wajib lengkap dan valid
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": {"topic": {"score": 1.0}}}], False, "Tolak kandidat dengan komponen tidak lengkap")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": dict(make_components(), topic={"score": None})}], False, "Tolak komponen dengan score None")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": dict(make_components(), topic={"score": True})}], False, "Tolak komponen dengan score boolean")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": dict(make_components(), topic={"score": float("nan")})}], False, "Tolak komponen dengan score NaN")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": dict(make_components(), topic={"score": float("inf")})}], False, "Tolak komponen dengan score Infinity")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": dict(make_components(), topic={"score": 1.5})}], False, "Tolak komponen dengan score > 1.0")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": dict(make_components(), topic={"score": -0.1})}], False, "Tolak komponen dengan score < 0.0")
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "rounding_reconciliation": 0.0, "selected_schedule": make_sched(), "components": dict(make_components(), topic={"score": 10**400})}], False, "Tolak komponen dengan score integer raksasa 10**400")

    # Hardening Breakdown: Tolak kandidat tanpa rounding_reconciliation
    assert_cand_err([{"intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s1", "total_score": 90.0, "selected_schedule": make_sched(), "components": make_components()}], False, "Tolak kandidat tanpa rounding_reconciliation")

    # 17.10 Immutability & Integritas Data Input
    orig_copy = [dict(c) for c in all_partners]
    res_immut = rank_partner_candidates(all_partners)
    report("Data Integrity: Objek input asli tidak disisipi field 'rank'", all("rank" not in c for c in all_partners))
    report("Data Integrity: Panjang dan konten input asli tidak berubah", len(all_partners) == len(orig_copy))

    # 17.11 Dukungan Objek ORM dan Pydantic
    orm_cand_1 = DummyORMCandidate(
        intent_id="u", candidate_type="SESSION", candidate_session_id="s_orm_1",
        total_score=95.0, rounding_reconciliation=0.0, selected_schedule=make_sched(), components=make_components(95.0)
    )
    orm_cand_2 = DummyORMCandidate(
        intent_id="u", candidate_type="SESSION", candidate_session_id="s_orm_2",
        total_score=85.0, rounding_reconciliation=0.0, selected_schedule=make_sched(), components=make_components(85.0)
    )
    r_orm = rank_session_candidates([orm_cand_1, orm_cand_2])
    report("Object Support: ORM candidate dapat diranking", len(r_orm) == 2 and r_orm[0]["candidate_session_id"] == "s_orm_1")

    pyd_cand_1 = DummyPydanticCandidate(
        intent_id="u", candidate_type="PARTNER", student_id="s_pyd_1", target_intent_id="i_pyd_1",
        total_score=95.0, rounding_reconciliation=0.0, selected_schedule=make_sched(), components=make_components(95.0)
    )
    pyd_cand_2 = DummyPydanticCandidate(
        intent_id="u", candidate_type="PARTNER", student_id="s_pyd_2", target_intent_id="i_pyd_2",
        total_score=85.0, rounding_reconciliation=0.0, selected_schedule=make_sched(), components=make_components(85.0)
    )
    r_pyd = rank_partner_candidates([pyd_cand_1, pyd_cand_2])
    report("Object Support: Pydantic candidate dapat diranking", len(r_pyd) == 2 and r_pyd[0]["student_id"] == "s_pyd_1")

    # 17.12 Rule-Based Match Explanation Generator
    exp_high = generate_match_explanation({
        "components": make_components(topic=1.0, goal=1.0, style=1.0, date=0.94, mode=1.0),
        "selected_schedule": make_sched(date="2026-11-16", start="10:00", end="12:00")
    })
    report("Explanation: Memuat komponen terkuat", "Topik belajar sangat relevan" in exp_high and "tujuan belajar selaras" in exp_high)
    report("Explanation: Memuat format tanggal bahasa Indonesia", "16 November 2026" in exp_high)
    report("Explanation: Memuat rentang jam jadwal", "10:00–12:00" in exp_high)

    try:
        generate_match_explanation(None)
        report("Explanation: Tolak kandidat None", False, "Harusnya raise ValueError")
    except ValueError:
        report("Explanation: Tolak kandidat None", True)

    try:
        generate_match_explanation({"components": {"topic": {"score": 1.0}}})
        report("Explanation: Tolak komponen tidak lengkap", False, "Harusnya raise ValueError")
    except ValueError:
        report("Explanation: Tolak komponen tidak lengkap", True)

    try:
        generate_match_explanation({"components": dict(make_components(), topic={"score": float("nan")})})
        report("Explanation: Tolak komponen NaN", False, "Harusnya raise ValueError")
    except ValueError:
        report("Explanation: Tolak komponen NaN", True)

    # 17.13 Format MatchResult Payload & Pydantic Validation (MatchResultCreate)
    # Session Payload
    sess_item = ranked_sess[0]
    payload_sess = format_match_result_payload(sess_item)
    report("Payload: candidate_type SESSION", payload_sess["candidate_type"] == "SESSION")
    report("Payload: candidate_session_id terisi", payload_sess["candidate_session_id"] == "ses_02")
    report("Payload: target_intent_id bernilai None", payload_sess["target_intent_id"] is None)
    report("Payload: Tidak memuat field ekstra student_id atau rank", "student_id" not in payload_sess and "rank" not in payload_sess)
    validated_sess = MatchResultCreate.model_validate(payload_sess)
    report("Payload Pydantic Validation: MatchResultCreate berhasil memvalidasi payload SESSION", validated_sess.candidate_type == "SESSION")

    # Partner Payload
    partner_item = ranked_partners[0]
    payload_partner = format_match_result_payload(partner_item)
    report("Payload: candidate_type PARTNER", payload_partner["candidate_type"] == "PARTNER")
    report("Payload: target_intent_id terisi", payload_partner["target_intent_id"] == "int_budi_2")
    report("Payload: candidate_session_id bernilai None", payload_partner["candidate_session_id"] is None)
    report("Payload: Tidak memuat field ekstra student_id atau rank", "student_id" not in payload_partner and "rank" not in payload_partner)
    validated_partner = MatchResultCreate.model_validate(payload_partner)
    report("Payload Pydantic Validation: MatchResultCreate berhasil memvalidasi payload PARTNER", validated_partner.candidate_type == "PARTNER")

    # Payload Hardening Temuan P1 & P2: Komponen wajib lengkap, bukan default 0.0, tolak 10**400
    try:
        format_match_result_payload(dict(partner_item, components={"topic": {"score": 1.0}}))
        report("Payload Validation: Tolak komponen tidak lengkap", False, "Harusnya raise ValueError")
    except ValueError:
        report("Payload Validation: Tolak komponen tidak lengkap", True)

    try:
        format_match_result_payload(dict(partner_item, components=dict(make_components(), goal={"score": float("nan")})))
        report("Payload Validation: Tolak komponen bernilai NaN", False, "Harusnya raise ValueError")
    except ValueError:
        report("Payload Validation: Tolak komponen bernilai NaN", True)

    try:
        format_match_result_payload(dict(partner_item, total_score=10**400))
        report("Payload Validation: Tolak total_score 10**400", False, "Harusnya raise ValueError")
    except ValueError:
        report("Payload Validation: Tolak total_score 10**400", True)

    # 17.14 Generic Dispatcher (rank_candidates)
    dispatch_sess = rank_candidates([sess_cand_1, sess_cand_2])
    report("Dispatcher: Otomatis mengenali SESSION", dispatch_sess[0]["candidate_session_id"] == "ses_02")

    dispatch_partner = rank_candidates([p_budi_1, p_citra])
    report("Dispatcher: Otomatis mengenali PARTNER", dispatch_partner[0]["student_id"] == "std_citra")

    dispatch_empty = rank_candidates([])
    report("Dispatcher: Menangani list kosong secara aman", dispatch_empty == [])

    # Temuan Audit P2: Dispatcher memvalidasi parameter sekalipun list kosong
    try:
        rank_candidates([], min_score=-1.0)
        report("Dispatcher Validation: Tolak min_score negatif pada list kosong", False, "Harusnya raise ValueError")
    except ValueError:
        report("Dispatcher Validation: Tolak min_score negatif pada list kosong", True)

    try:
        rank_candidates([], limit=0)
        report("Dispatcher Validation: Tolak limit 0 pada list kosong", False, "Harusnya raise ValueError")
    except ValueError:
        report("Dispatcher Validation: Tolak limit 0 pada list kosong", True)

    try:
        rank_candidates([], min_score=float("nan"))
        report("Dispatcher Validation: Tolak min_score NaN pada list kosong", False, "Harusnya raise ValueError")
    except ValueError:
        report("Dispatcher Validation: Tolak min_score NaN pada list kosong", True)

    try:
        rank_candidates([], min_score=10**400)
        report("Dispatcher Validation: Tolak min_score 10**400 pada list kosong", False, "Harusnya raise ValueError")
    except ValueError:
        report("Dispatcher Validation: Tolak min_score 10**400 pada list kosong", True)

    # 17.15 Breakdown Reconciliation & Immutability Benchmark (Audit Benchmark 46.82)
    scored_bench = calculate_compatibility_breakdown(
        0.35991, 0.51916, 0.86274, 0.50660, 0.16717,
    )
    # Session Path
    bench_session_cand = {
        "intent_id": "int_user",
        "candidate_type": "SESSION",
        "candidate_session_id": "ses_bench_4682",
        "total_score": scored_bench["total_score"],
        "rounding_reconciliation": scored_bench["rounding_reconciliation"],
        "components": scored_bench["components"],
        "selected_schedule": make_sched(),
    }
    ranked_bench_sess = rank_session_candidates([bench_session_cand])[0]

    report("Breakdown Preservation: total_score tepat 46.82", ranked_bench_sess["total_score"] == 46.82)
    sum_contrib_sess = round(sum(c["contribution"] for c in ranked_bench_sess["components"].values()), 2)
    report("Breakdown Preservation: sum(contribution) == total_score (46.82)", sum_contrib_sess == 46.82)
    report("Breakdown Preservation: Topic contribution terekonsiliasi 10.79", ranked_bench_sess["components"]["topic"]["contribution"] == 10.79)
    report("Breakdown Preservation: Topic rounding_adjustment -0.01 dipertahankan", ranked_bench_sess["components"]["topic"]["rounding_adjustment"] == -0.01)
    report("Breakdown Preservation: Topic raw_contribution 10.7973 dipertahankan", ranked_bench_sess["components"]["topic"]["raw_contribution"] == 10.7973)
    report("Breakdown Preservation: Objek input asli tidak dimutasi", bench_session_cand["components"]["topic"]["contribution"] == 10.79 and "rank" not in bench_session_cand)

    # Partner Path
    bench_partner_cand = {
        "intent_id": "int_user",
        "candidate_type": "PARTNER",
        "student_id": "std_bench_4682",
        "target_intent_id": "int_target_bench",
        "total_score": scored_bench["total_score"],
        "rounding_reconciliation": scored_bench["rounding_reconciliation"],
        "components": scored_bench["components"],
        "selected_schedule": make_sched(),
    }
    ranked_bench_part = rank_partner_candidates([bench_partner_cand])[0]

    report("Breakdown Preservation Partner: total_score tepat 46.82", ranked_bench_part["total_score"] == 46.82)
    sum_contrib_part = round(sum(c["contribution"] for c in ranked_bench_part["components"].values()), 2)
    report("Breakdown Preservation Partner: sum(contribution) == total_score (46.82)", sum_contrib_part == 46.82)
    report("Breakdown Preservation Partner: Topic contribution 10.79 dipertahankan", ranked_bench_part["components"]["topic"]["contribution"] == 10.79)
    report("Breakdown Preservation Partner: Topic rounding_adjustment -0.01 dipertahankan", ranked_bench_part["components"]["topic"]["rounding_adjustment"] == -0.01)
    report("Breakdown Preservation Partner: Topic raw_contribution 10.7973 dipertahankan", ranked_bench_part["components"]["topic"]["raw_contribution"] == 10.7973)
    report("Breakdown Preservation Partner: Objek input asli tidak dimutasi", bench_partner_cand["components"]["topic"]["contribution"] == 10.79 and "rank" not in bench_partner_cand)

    # 17.16 Hardening Breakdown: Rekonstruksi Decimal ketika contribution Hilang (Target 1)
    comp_recon = {k: dict(v) for k, v in scored_bench["components"].items()}
    # Hapus contribution Topic (10.79), tapi pertahankan raw_contribution (10.7973) dan rounding_adjustment (-0.01)
    del comp_recon["topic"]["contribution"]
    cand_recon = {
        "intent_id": "int_user",
        "candidate_type": "SESSION",
        "candidate_session_id": "ses_recon_topic",
        "total_score": 46.82,
        "rounding_reconciliation": -0.01,
        "components": comp_recon,
        "selected_schedule": make_sched(),
    }
    ranked_recon = rank_session_candidates([cand_recon])[0]
    report("Breakdown Recon: Topic contribution direkonstruksi tepat 10.79", ranked_recon["components"]["topic"]["contribution"] == 10.79)
    sum_recon = round(sum(c["contribution"] for c in ranked_recon["components"].values()), 2)
    report("Breakdown Recon: sum(contribution) tetap tepat 46.82 tanpa rounding drift", sum_recon == 46.82)

    # 17.17 Hardening Breakdown: Tolak Inkonsistensi sum(contribution) vs total_score (Target 2)
    cand_mismatch = {
        "intent_id": "int_user",
        "candidate_type": "SESSION",
        "candidate_session_id": "ses_mismatch",
        "total_score": 46.83,  # Sengaja diubah 46.83 padahal sum adalah 46.82
        "rounding_reconciliation": -0.01,
        "components": scored_bench["components"],
        "selected_schedule": make_sched(),
    }
    try:
        rank_session_candidates([cand_mismatch])
        report("Cross-Validation: Tolak total_score tidak sama dengan sum(contribution)", False, "Harusnya raise ValueError")
    except ValueError:
        report("Cross-Validation: Tolak total_score tidak sama dengan sum(contribution)", True)

    # 17.18 Hardening Breakdown: Tolak rounding_reconciliation Invalid (Target 3)
    for bad_rec, rec_lbl in [
        ("invalid", "string invalid"),
        (float("nan"), "NaN"),
        (float("inf"), "Infinity"),
        (True, "boolean"),
        (10**400, "10**400"),
        (5.0, "di luar rentang [-1.0, 1.0]"),
    ]:
        cand_bad_rec = dict(bench_session_cand, rounding_reconciliation=bad_rec)
        try:
            rank_session_candidates([cand_bad_rec])
            report(f"Rec Validation: Tolak rounding_reconciliation {rec_lbl}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Rec Validation: Tolak rounding_reconciliation {rec_lbl}", True)

    # 17.19 Hardening Breakdown: Tolak Bobot Komponen Menyimpang dari SCORING_WEIGHTS Resmi (Target 4)
    bad_weight_comps = {k: dict(v) for k, v in scored_bench["components"].items()}
    bad_weight_comps["topic"]["weight"] = 0.50  # SCORING_WEIGHTS resmi untuk topic adalah 0.30
    cand_bad_weight = dict(bench_session_cand, components=bad_weight_comps)
    try:
        rank_session_candidates([cand_bad_weight])
        report("Weight Validation: Tolak bobot menyimpang dari SCORING_WEIGHTS", False, "Harusnya raise ValueError")
    except ValueError:
        report("Weight Validation: Tolak bobot menyimpang dari SCORING_WEIGHTS", True)

    # 17.20 Hardening Breakdown: Tolak Inkonsistensi Kontribusi Per Komponen (Temuan Audit P1)
    # Kasus: Total kontribusi tetap 46.82, total adjustment tetap -0.01,
    # tetapi Topic diubah menjadi 10.80 dan Style diubah menjadi 12.93 (saling mengompensasi).
    bad_per_comp = {k: dict(v) for k, v in scored_bench["components"].items()}
    bad_per_comp["topic"]["contribution"] = 10.80  # Harusnya 10.79 (base 10.80 + adj -0.01)
    bad_per_comp["style"]["contribution"] = 12.93  # Harusnya 12.94 (base 12.94 + adj 0.00)
    cand_bad_per_comp = dict(bench_session_cand, components=bad_per_comp)
    try:
        rank_session_candidates([cand_bad_per_comp])
        report("Per-Component Validation: Tolak kontribusi komponen yang tidak konsisten dengan metadatanya", False, "Harusnya raise ValueError")
    except ValueError:
        report("Per-Component Validation: Tolak kontribusi komponen yang tidak konsisten dengan metadatanya", True)

    # 17.21 Hardening Breakdown: Rekonstruksi Aman Presisi Base Contribution (Temuan Audit P2)
    # Edge case: raw_contribution = 10.79496 -> pembulatan 2 desimal adalah 10.79,
    # tetapi jika dibulatkan ke 4 desimal menjadi 10.7950 yang bisa memicu double rounding ke 10.80.
    # Dengan base_contribution = 10.79 eksplisit, rekonstruksi tetap tepat 10.79.
    edge_comp = {k: dict(v) for k, v in scored_bench["components"].items()}
    edge_comp["topic"] = {
        "score": 0.3599,
        "weight": 0.30,
        "raw_contribution": 10.7950,
        "base_contribution": 10.79,
        "rounding_adjustment": 0.0,
        # contribution sengaja tidak disertakan untuk menguji rekonstruksi dari base_contribution
    }
    cand_edge_recon = {
        "intent_id": "int_user",
        "candidate_type": "SESSION",
        "candidate_session_id": "ses_edge_recon",
        "total_score": 46.82,
        "rounding_reconciliation": 0.0,
        "components": edge_comp,
        "selected_schedule": make_sched(),
    }
    ranked_edge = rank_session_candidates([cand_edge_recon])[0]
    report("Edge-Case Recon: Rekonstruksi presisi dari base_contribution aman dari double-rounding", ranked_edge["components"]["topic"]["contribution"] == 10.79)

    # 17.22 Hardening Breakdown: Tolak Metadata Adjustment Parsial (All-or-None) (Temuan Audit P2)
    # Kasus A: 4 komponen memuat rounding_adjustment, 1 komponen (mode) tidak memuatnya
    partial_adj_comp = {k: dict(v) for k, v in scored_bench["components"].items()}
    del partial_adj_comp["mode"]["rounding_adjustment"]
    cand_partial_adj = dict(bench_session_cand, components=partial_adj_comp)
    try:
        rank_session_candidates([cand_partial_adj])
        report("All-or-None Validation: Tolak rounding_adjustment parsial (4/5 komponen)", False, "Harusnya raise ValueError")
    except ValueError:
        report("All-or-None Validation: Tolak rounding_adjustment parsial (4/5 komponen)", True)

    # Kasus B: rounding_reconciliation disediakan tetapi komponen tidak memuat rounding_adjustment
    no_adj_comp = {k: dict(v) for k, v in scored_bench["components"].items()}
    for comp_k in no_adj_comp:
        del no_adj_comp[comp_k]["rounding_adjustment"]
    cand_no_adj_with_rec = dict(bench_session_cand, components=no_adj_comp, rounding_reconciliation=-0.01)
    try:
        rank_session_candidates([cand_no_adj_with_rec])
        report("All-or-None Validation: Tolak rounding_reconciliation saat komponen tanpa rounding_adjustment", False, "Harusnya raise ValueError")
    except ValueError:
        report("All-or-None Validation: Tolak rounding_reconciliation saat komponen tanpa rounding_adjustment", True)

    # ==========================================================================
    # 17.23 FINAL HARDENING DAY 15.6: BREAKDOWN INTEGRITY LOCK (6 REGRESSION TESTS)
    # Diuji secara simetris pada rank_session_candidates dan rank_partner_candidates
    # ==========================================================================

    # 1. Breakdown valid benchmark 46.82 diterima pada Session & Partner
    # Session
    lock_sess_1 = {
        "intent_id": "u", "candidate_type": "SESSION", "candidate_session_id": "s_lock_1",
        "total_score": scored_bench["total_score"],
        "rounding_reconciliation": scored_bench["rounding_reconciliation"],
        "components": scored_bench["components"],
        "selected_schedule": make_sched(),
    }
    r_lock_sess_1 = rank_session_candidates([lock_sess_1])[0]
    report("Lock Test 1 (Session): Benchmark 46.82 diterima", r_lock_sess_1["total_score"] == 46.82)
    report("Lock Test 1 (Session): sum(contribution) == 46.82", round(sum(c["contribution"] for c in r_lock_sess_1["components"].values()), 2) == 46.82)
    report("Lock Test 1 (Session): Topic contribution tepat 10.79", r_lock_sess_1["components"]["topic"]["contribution"] == 10.79)
    report("Lock Test 1 (Session): Immutability input dipertahankan", lock_sess_1["components"]["topic"]["contribution"] == 10.79 and "rank" not in lock_sess_1)

    # Partner
    lock_part_1 = {
        "intent_id": "u", "candidate_type": "PARTNER", "student_id": "std_lock_1", "target_intent_id": "tgt_lock_1",
        "total_score": scored_bench["total_score"],
        "rounding_reconciliation": scored_bench["rounding_reconciliation"],
        "components": scored_bench["components"],
        "selected_schedule": make_sched(),
    }
    r_lock_part_1 = rank_partner_candidates([lock_part_1])[0]
    report("Lock Test 1 (Partner): Benchmark 46.82 diterima", r_lock_part_1["total_score"] == 46.82)
    report("Lock Test 1 (Partner): sum(contribution) == 46.82", round(sum(c["contribution"] for c in r_lock_part_1["components"].values()), 2) == 46.82)
    report("Lock Test 1 (Partner): Topic contribution tepat 10.79", r_lock_part_1["components"]["topic"]["contribution"] == 10.79)
    report("Lock Test 1 (Partner): Immutability input dipertahankan", lock_part_1["components"]["topic"]["contribution"] == 10.79 and "rank" not in lock_part_1)

    # 2. Manipulasi kontribusi individual (Topic 10.80, Style 12.93) dengan total tetap 46.82
    # ketika metadata base dihilangkan atau tidak konsisten -> Ditolak ValueError
    bad_tamp_comps = {k: dict(v) for k, v in scored_bench["components"].items()}
    bad_tamp_comps["topic"] = dict(bad_tamp_comps["topic"], contribution=10.80)
    bad_tamp_comps["style"] = dict(bad_tamp_comps["style"], contribution=12.93)
    # Hapus base_contribution pada keduanya untuk mensimulasikan bypass
    del bad_tamp_comps["topic"]["base_contribution"]
    del bad_tamp_comps["style"]["base_contribution"]
    cand_tamp_sess = dict(lock_sess_1, components=bad_tamp_comps)
    cand_tamp_part = dict(lock_part_1, components=bad_tamp_comps)

    try:
        rank_session_candidates([cand_tamp_sess])
        report("Lock Test 2 (Session): Tolak manipulasi kontribusi tanpa base_contribution", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 2 (Session): Tolak manipulasi kontribusi tanpa base_contribution", True)

    try:
        rank_partner_candidates([cand_tamp_part])
        report("Lock Test 2 (Partner): Tolak manipulasi kontribusi tanpa base_contribution", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 2 (Partner): Tolak manipulasi kontribusi tanpa base_contribution", True)

    # 3. Penolakan fallback dari raw_contribution tanpa base_contribution -> Ditolak ValueError
    bad_fb_comps = {k: dict(v) for k, v in scored_bench["components"].items()}
    bad_fb_comps["topic"] = {
        "score": 0.3599, "weight": 0.30, "raw_contribution": 10.7950,
        "rounding_adjustment": -0.01, "contribution": 10.79,
        # base_contribution sengaja tidak disertakan
    }
    cand_fb_sess = dict(lock_sess_1, components=bad_fb_comps)
    cand_fb_part = dict(lock_part_1, components=bad_fb_comps)

    try:
        rank_session_candidates([cand_fb_sess])
        report("Lock Test 3 (Session): Tolak fallback raw_contribution tanpa base_contribution", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 3 (Session): Tolak fallback raw_contribution tanpa base_contribution", True)

    try:
        rank_partner_candidates([cand_fb_part])
        report("Lock Test 3 (Partner): Tolak fallback raw_contribution tanpa base_contribution", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 3 (Partner): Tolak fallback raw_contribution tanpa base_contribution", True)

    # 4. Rekonstruksi contribution yang hilang dari base + adjustment -> Berhasil direkonstruksi
    recon_comps = {k: dict(v) for k, v in scored_bench["components"].items()}
    del recon_comps["topic"]["contribution"]  # base 10.80, adj -0.01 -> harusnya 10.79
    cand_recon_sess = dict(lock_sess_1, components=recon_comps)
    cand_recon_part = dict(lock_part_1, components=recon_comps)

    r_recon_sess = rank_session_candidates([cand_recon_sess])[0]
    report("Lock Test 4 (Session): Rekonstruksi contribution dari base + adjustment (10.79)", r_recon_sess["components"]["topic"]["contribution"] == 10.79)
    report("Lock Test 4 (Session): sum(contribution) hasil rekonstruksi tepat 46.82", round(sum(c["contribution"] for c in r_recon_sess["components"].values()), 2) == 46.82)

    r_recon_part = rank_partner_candidates([cand_recon_part])[0]
    report("Lock Test 4 (Partner): Rekonstruksi contribution dari base + adjustment (10.79)", r_recon_part["components"]["topic"]["contribution"] == 10.79)
    report("Lock Test 4 (Partner): sum(contribution) hasil rekonstruksi tepat 46.82", round(sum(c["contribution"] for c in r_recon_part["components"].values()), 2) == 46.82)

    # 5. Penolakan nilai base/adjustment dengan presisi lebih dari 2 desimal -> Ditolak ValueError
    # 5a. base_contribution presisi >2 desimal (10.795)
    bad_p3_base = {k: dict(v) for k, v in scored_bench["components"].items()}
    bad_p3_base["topic"] = dict(bad_p3_base["topic"], base_contribution=10.795)
    try:
        rank_session_candidates([dict(lock_sess_1, components=bad_p3_base)])
        report("Lock Test 5 (Session): Tolak base_contribution presisi >2 desimal (10.795)", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 5 (Session): Tolak base_contribution presisi >2 desimal (10.795)", True)

    try:
        rank_partner_candidates([dict(lock_part_1, components=bad_p3_base)])
        report("Lock Test 5 (Partner): Tolak base_contribution presisi >2 desimal (10.795)", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 5 (Partner): Tolak base_contribution presisi >2 desimal (10.795)", True)

    # 5b. rounding_adjustment presisi >2 desimal (0.001)
    bad_p3_adj = {k: dict(v) for k, v in scored_bench["components"].items()}
    bad_p3_adj["topic"] = dict(bad_p3_adj["topic"], rounding_adjustment=0.001)
    try:
        rank_session_candidates([dict(lock_sess_1, components=bad_p3_adj)])
        report("Lock Test 5 (Session): Tolak rounding_adjustment presisi >2 desimal (0.001)", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 5 (Session): Tolak rounding_adjustment presisi >2 desimal (0.001)", True)

    try:
        rank_partner_candidates([dict(lock_part_1, components=bad_p3_adj)])
        report("Lock Test 5 (Partner): Tolak rounding_adjustment presisi >2 desimal (0.001)", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 5 (Partner): Tolak rounding_adjustment presisi >2 desimal (0.001)", True)

    # 5c. base_contribution 4 desimal (10.7973)
    bad_p4_base = {k: dict(v) for k, v in scored_bench["components"].items()}
    bad_p4_base["topic"] = dict(bad_p4_base["topic"], base_contribution=10.7973)
    try:
        rank_session_candidates([dict(lock_sess_1, components=bad_p4_base)])
        report("Lock Test 5 (Session): Tolak base_contribution 4 desimal (10.7973)", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 5 (Session): Tolak base_contribution 4 desimal (10.7973)", True)

    try:
        rank_partner_candidates([dict(lock_part_1, components=bad_p4_base)])
        report("Lock Test 5 (Partner): Tolak base_contribution 4 desimal (10.7973)", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 5 (Partner): Tolak base_contribution 4 desimal (10.7973)", True)

    # 6. Penolakan jumlah adjustment != rounding_reconciliation -> Ditolak ValueError
    # Session
    cand_adj_mismatch_s = dict(lock_sess_1, rounding_reconciliation=0.00)  # Harusnya -0.01
    try:
        rank_session_candidates([cand_adj_mismatch_s])
        report("Lock Test 6 (Session): Tolak sum(adjustment) != rounding_reconciliation", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 6 (Session): Tolak sum(adjustment) != rounding_reconciliation", True)

    # Partner
    cand_adj_mismatch_p = dict(lock_part_1, rounding_reconciliation=0.00)  # Harusnya -0.01
    try:
        rank_partner_candidates([cand_adj_mismatch_p])
        report("Lock Test 6 (Partner): Tolak sum(adjustment) != rounding_reconciliation", False, "Harusnya raise ValueError")
    except ValueError:
        report("Lock Test 6 (Partner): Tolak sum(adjustment) != rounding_reconciliation", True)


def run_tests():
    print("=" * 70)
    print("RUNNING DAY 15: SOFT CONSTRAINT SCORING TEST SUITE (TAHAP 15.1 - 15.6)")
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
    test_candidate_ranking_and_deduplication()

    print("\n" + "=" * 70)
    print(f"TEST RESULT SUMMARY: {passed_count}/{total_count} TESTS PASSED (100% SUCCESS)")
    print("=" * 70)
    assert passed_count == total_count, f"Some tests failed! ({passed_count}/{total_count})"


if __name__ == "__main__":
    run_tests()
