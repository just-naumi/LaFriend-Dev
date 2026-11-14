# test_day15_scoring_ranking.py - Automated Test Suite untuk Scoring Engine LaFriend (Day 15)
# Tahap 15.1: Canonicalizer, Matriks Kompatibilitas, Priority, Duration, dan Date Scoring

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


def run_tests():
    print("=" * 70)
    print("RUNNING DAY 15: SOFT CONSTRAINT SCORING TEST SUITE (TAHAP 15.1)")
    print("=" * 70)

    # --------------------------------------------------------------------------
    # SUITE 1: Canonicalizer Learning Goal & Collaboration Style
    # --------------------------------------------------------------------------
    print("\n--- SUITE 1: Canonicalizer Normalization & Idempotence ---")

    # 1.1 Learning goal canonical values preserved
    for cg in CANONICAL_LEARNING_GOALS:
        res = normalize_learning_goal(cg)
        report(f"Goal: Kanonis '{cg}' dipertahankan", res == cg)
        report(f"Goal: Idempoten untuk '{cg}'", normalize_learning_goal(res) == cg)

    # 1.2 Learning goal aliases
    report("Goal: Alias 'CONCEPT' -> 'UNDERSTAND'", normalize_learning_goal("CONCEPT") == "UNDERSTAND")
    report("Goal: Alias 'EXAM_PREP' -> 'EXAM_PREPARATION'", normalize_learning_goal("EXAM_PREP") == "EXAM_PREPARATION")
    report("Goal: Alias 'DISCUSSION' -> 'KNOWLEDGE_SHARING'", normalize_learning_goal("DISCUSSION") == "KNOWLEDGE_SHARING")

    # 1.3 Case insensitivity and whitespace stripping
    report("Goal: Case insensitivity 'concept' -> 'UNDERSTAND'", normalize_learning_goal("concept") == "UNDERSTAND")
    report("Goal: Whitespace stripped '  exam_prep  ' -> 'EXAM_PREPARATION'", normalize_learning_goal("  exam_prep  ") == "EXAM_PREPARATION")

    # 1.4 Learning goal rejection
    for bad_goal in ["UNKNOWN_GOAL", "", "   ", None, 123, []]:
        try:
            normalize_learning_goal(bad_goal)
            report(f"Goal: Tolak nilai invalid ({bad_goal})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Goal: Tolak nilai invalid ({bad_goal})", True)

    # 1.5 Collaboration style canonical values preserved
    for cs in CANONICAL_COLLABORATION_STYLES:
        res = normalize_collaboration_style(cs)
        report(f"Style: Kanonis '{cs}' dipertahankan", res == cs)
        report(f"Style: Idempoten untuk '{cs}'", normalize_collaboration_style(res) == cs)

    # 1.6 Collaboration style aliases
    report("Style: Alias 'TEACHING' -> 'PEER_TUTORING'", normalize_collaboration_style("TEACHING") == "PEER_TUTORING")
    report("Style: Alias 'SILENT' -> 'FOCUS_STUDY'", normalize_collaboration_style("SILENT") == "FOCUS_STUDY")
    report("Style: DISCUSSION pada style tetap 'DISCUSSION'", normalize_collaboration_style("DISCUSSION") == "DISCUSSION")

    # 1.7 Style Case insensitivity and whitespace stripping
    report("Style: Case insensitivity 'teaching' -> 'PEER_TUTORING'", normalize_collaboration_style("teaching") == "PEER_TUTORING")
    report("Style: Whitespace stripped '  silent  ' -> 'FOCUS_STUDY'", normalize_collaboration_style("  silent  ") == "FOCUS_STUDY")

    # 1.8 Collaboration style rejection
    for bad_style in ["RANDOM_STYLE", "", "   ", None, 456, {}]:
        try:
            normalize_collaboration_style(bad_style)
            report(f"Style: Tolak nilai invalid ({bad_style})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Style: Tolak nilai invalid ({bad_style})", True)

    # --------------------------------------------------------------------------
    # SUITE 2: Matriks Kompatibilitas (Kelengkapan, Simetri, Bounds)
    # --------------------------------------------------------------------------
    print("\n--- SUITE 2: Compatibility Matrices Properties ---")

    # 2.1 Goal Matrix Completeness & Diagonal
    for g1 in CANONICAL_LEARNING_GOALS:
        report(f"Goal Matrix: '{g1}' memiliki baris lengkap", set(GOAL_COMPATIBILITY[g1].keys()) == CANONICAL_LEARNING_GOALS)
        report(f"Goal Matrix: Diagonal G('{g1}', '{g1}') == 1.00", GOAL_COMPATIBILITY[g1][g1] == 1.00)

    # 2.2 Goal Matrix Symmetry & Bounds
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

    # 2.3 Style Matrix Completeness & Diagonal
    for s1 in CANONICAL_COLLABORATION_STYLES:
        report(f"Style Matrix: '{s1}' memiliki baris lengkap", set(STYLE_COMPATIBILITY[s1].keys()) == CANONICAL_COLLABORATION_STYLES)
        report(f"Style Matrix: Diagonal S('{s1}', '{s1}') == 1.00", STYLE_COMPATIBILITY[s1][s1] == 1.00)

    # 2.4 Style Matrix Symmetry & Bounds
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

    # 2.5 Perhitungan compatibility dengan alias
    g_alias_score = calculate_goal_compatibility("concept", "exam_prep")
    report("calculate_goal_compatibility: 'concept' vs 'exam_prep' bernilai 0.80", g_alias_score == 0.80)

    s_alias_score = calculate_style_compatibility("teaching", "silent")
    report("calculate_style_compatibility: 'teaching' vs 'silent' bernilai 0.20", s_alias_score == 0.20)

    # --------------------------------------------------------------------------
    # SUITE 3: Priority Scoring (Partner & Session)
    # --------------------------------------------------------------------------
    print("\n--- SUITE 3: Priority Scoring (Partner & Session) ---")

    # 3.1 Partner Priority Table (6 Kombinasi Unik & Simetris)
    expected_partner_pairs = {
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
    for (p1, p2), exp_score in expected_partner_pairs.items():
        score = calculate_priority_score(p1, p2)
        report(f"Partner Priority: ({p1}, {p2}) == {exp_score}", math.isclose(score, exp_score))

    # 3.2 Partner Priority Rejection (Nilai di luar 1, 2, 3)
    for bad_p in [(0, 1), (1, 4), (0, 0), (4, 4), (-1, 2), (True, 1), ("1", 2)]:
        try:
            calculate_priority_score(bad_p[0], bad_p[1])
            report(f"Partner Priority: Tolak input invalid {bad_p}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Partner Priority: Tolak input invalid {bad_p}", True)

    # 3.3 Session Priority Scores
    report("Session Priority: rank 1 == 1.00", math.isclose(calculate_session_priority_score(1), 1.00))
    report("Session Priority: rank 2 == 0.70", math.isclose(calculate_session_priority_score(2), 0.70))
    report("Session Priority: rank 3 == 0.30", math.isclose(calculate_session_priority_score(3), 0.30))

    # 3.4 Session Priority Rejection
    for bad_sp in [0, 4, -1, 5, "1", None, True]:
        try:
            calculate_session_priority_score(bad_sp)
            report(f"Session Priority: Tolak rank invalid ({bad_sp})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Session Priority: Tolak rank invalid ({bad_sp})", True)

    # --------------------------------------------------------------------------
    # SUITE 4: Duration Scoring L(d)
    # --------------------------------------------------------------------------
    print("\n--- SUITE 4: Duration Scoring L(d) ---")

    # 4.1 Titik batas target
    report("Duration: 59 menit (di bawah batas minimal) bernilai 0.00", calculate_duration_score(59) == 0.0)
    report("Duration: 60 menit bernilai tepat 0.50", math.isclose(calculate_duration_score(60), 0.50))
    report("Duration: 75 menit bernilai tepat 0.65", math.isclose(calculate_duration_score(75), 0.65))
    report("Duration: 90 menit bernilai tepat 0.80", math.isclose(calculate_duration_score(90), 0.80))
    report("Duration: 105 menit bernilai tepat 0.90", math.isclose(calculate_duration_score(105), 0.90))
    report("Duration: 120 menit bernilai tepat 1.00", math.isclose(calculate_duration_score(120), 1.00))
    report("Duration: 150 menit (di atas 120) tetap 1.00", math.isclose(calculate_duration_score(150), 1.00))

    # 4.2 Validasi input duration
    for bad_d in [-1, -60, float("nan"), float("inf"), "60", None, True]:
        try:
            calculate_duration_score(bad_d)
            report(f"Duration: Tolak durasi invalid ({bad_d})", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Duration: Tolak durasi invalid ({bad_d})", True)

    # --------------------------------------------------------------------------
    # SUITE 5: Date Score (0.70 Priority + 0.30 Duration)
    # --------------------------------------------------------------------------
    print("\n--- SUITE 5: Date Score Integration (70:30) ---")

    # 5.1 Perhitungan nilai gabungan
    # Kasus A: Priority 1.00, Duration 1.00 -> 1.00
    report("Date Score: P=1.0, L=1.0 -> 1.00", math.isclose(calculate_date_score(1.0, 1.0), 1.00))

    # Kasus B: Priority 1.00, Duration 0.50 (60 menit) -> 0.70 + 0.15 = 0.85
    report("Date Score: P=1.0, L=0.5 -> 0.85", math.isclose(calculate_date_score(1.0, 0.5), 0.85))

    # Kasus C: Priority 0.60 (prio 1 & 3), Duration 0.80 (90 menit) -> 0.42 + 0.24 = 0.66
    report("Date Score: P=0.6, L=0.8 -> 0.66", math.isclose(calculate_date_score(0.6, 0.8), 0.66))

    # Kasus D: Priority 0.30 (prio 3 & 3), Duration 0.00 (59 menit) -> 0.21
    report("Date Score: P=0.3, L=0.0 -> 0.21", math.isclose(calculate_date_score(0.3, 0.0), 0.21))

    # 5.2 Validasi input out-of-bounds Date Score
    for bad_ds in [(-0.1, 0.5), (1.1, 0.5), (0.5, -0.1), (0.5, 1.1), ("0.5", 0.5), (None, 0.5), (True, 0.5)]:
        try:
            calculate_date_score(bad_ds[0], bad_ds[1])
            report(f"Date Score: Tolak input di luar batas {bad_ds}", False, "Harusnya raise ValueError")
        except ValueError:
            report(f"Date Score: Tolak input di luar batas {bad_ds}", True)

    # --------------------------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"TEST RESULT SUMMARY: {passed_count}/{total_count} TESTS PASSED (100% SUCCESS)")
    print("=" * 70)
    assert passed_count == total_count, f"Some tests failed! ({passed_count}/{total_count})"


if __name__ == "__main__":
    run_tests()
