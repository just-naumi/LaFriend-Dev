# scoring.py - Modul Soft Constraint Scoring & Compatibility Ranking Engine (Day 15)
# Bertanggung jawab menghitung tingkat kecocokan kandidat yang lolos Hard Constraint Day 14.

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
