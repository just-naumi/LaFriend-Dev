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
    tokens_bst = tokenize_topic("Binary Search Tree, AVL Tree")
    report("Tokenize: Istilah teknis BST & AVL terpisah bersih", tokens_bst == {"binary", "search", "tree", "avl"})

    tokens_graph = tokenize_topic("Algoritma Graph: BFS dan DFS")
    report("Tokenize: Istilah BFS, DFS, Graph tidak hilang", {"graph", "bfs", "dfs"}.issubset(tokens_graph))

    tokens_cpp = tokenize_topic("Pemrograman C++ dan OOP")
    report("Tokenize: C++ dan OOP dipertahankan sebagai token", {"c++", "oop"}.issubset(tokens_cpp))

    # 6.4 Stopwords penyaring noise tanpa membuang makna
    tokens_noise = tokenize_topic("Materi bab tentang Integral")
    report("Tokenize: Stopwords disaring sehingga tersisa kata kunci", tokens_noise == {"integral"})


def test_jaccard_similarity():
    """Menguji perhitungan kemiripan leksikal Jaccard."""
    print("\n--- SUITE 7: Jaccard Lexical Similarity ---")

    # 7.1 Identik -> 1.00
    j_same = calculate_jaccard_similarity("Binary Search Tree", "binary search tree")
    report("Jaccard: Topik identik bernilai 1.00", math.isclose(j_same, 1.00))

    # 7.2 Disjoint -> 0.00
    j_disjoint = calculate_jaccard_similarity("Struktur Data Graph BFS", "Kalkulus Integral Lipat")
    report("Jaccard: Topik tanpa irisan bernilai 0.00", math.isclose(j_disjoint, 0.00))

    # 7.3 Irisan parsial terukur akurat
    # "Binary Search Tree" -> {"binary", "search", "tree"} (3)
    # "AVL Tree" -> {"avl", "tree"} (2)
    # Irisan: {"tree"} (1), Union: {"binary", "search", "tree", "avl"} (4) -> 1/4 = 0.25
    j_partial = calculate_jaccard_similarity("Binary Search Tree", "AVL Tree")
    report("Jaccard: Irisan parsial 1/4 terhitung 0.25", math.isclose(j_partial, 0.25))

    # 7.4 Simetri J(A, B) == J(B, A)
    j_ab = calculate_jaccard_similarity("Pengurutan QuickSort dan MergeSort", "QuickSort Algorithm")
    j_ba = calculate_jaccard_similarity("QuickSort Algorithm", "Pengurutan QuickSort dan MergeSort")
    report("Jaccard: Simetris sempurna J(A, B) == J(B, A)", math.isclose(j_ab, j_ba))


def test_embedding_vector_validation():
    """Menguji validasi ketat kelayakan vektor embedding."""
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


class MockEmbeddingService:
    """Mock service untuk pengujian unit Topic Similarity."""
    def __init__(self, vector_map=None, should_fail=False, return_invalid=False):
        self.vector_map = vector_map or {}
        self.should_fail = should_fail
        self.return_invalid = return_invalid

    def get_embedding(self, text: str):
        if self.should_fail:
            raise RuntimeError("Embedding API timeout or service unavailable")
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

    # 10.3 Service melempar error -> Otomatis fallback ke Jaccard tanpa crash
    svc_fail = MockEmbeddingService(should_fail=True)
    t_fallback = calculate_topic_similarity("QuickSort", "QuickSort Algorithm", embedding_service=svc_fail)
    report("Topic Sim: Service error otomatis fallback ke Jaccard", math.isclose(t_fallback, 0.50))

    det_fallback = calculate_topic_similarity_detailed("QuickSort", "QuickSort Algorithm", embedding_service=svc_fail)
    report("Topic Sim Detailed: Mencatat error penyebab fallback", det_fallback["method"] == "JACCARD_FALLBACK" and det_fallback["error"] is not None)

    # 10.4 Service mengembalikan vector invalid (NaN) -> Otomatis fallback ke Jaccard
    svc_invalid = MockEmbeddingService(return_invalid=True)
    t_inv_fallback = calculate_topic_similarity("Linear Algebra", "Linear Algebra", embedding_service=svc_invalid)
    report("Topic Sim: Vector invalid otomatis fallback ke Jaccard", math.isclose(t_inv_fallback, 1.00))

    # 10.5 Topik kosong -> Tetap raise ValueError (jangan disamakan dengan fallback)
    for bad_t in ["", "   ", None]:
        try:
            calculate_topic_similarity(bad_t, "Kalkulus", embedding_service=svc_good)
            report(f"Topic Sim: Tolak topik kosong/None ({bad_t})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Topic Sim: Tolak topik kosong/None ({bad_t})", True)


def run_tests():
    print("=" * 70)
    print("RUNNING DAY 15: SOFT CONSTRAINT SCORING TEST SUITE (TAHAP 15.1 & 15.2)")
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

    print("\n" + "=" * 70)
    print(f"TEST RESULT SUMMARY: {passed_count}/{total_count} TESTS PASSED (100% SUCCESS)")
    print("=" * 70)
    assert passed_count == total_count, f"Some tests failed! ({passed_count}/{total_count})"


if __name__ == "__main__":
    run_tests()
