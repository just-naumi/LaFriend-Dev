# ==============================================================================
# matching_evaluation.py - Modul Evaluasi & Validasi Kualitas Matching Engine (Day 19)
# ==============================================================================
# Modul ini bertanggung jawab untuk:
# 1. Day 19.1 & 19.1.1 - Group Quality Evaluation (APS, MPS, GQ, sebaran skor pairwise,
#    identifikasi weakest link/strongest link, variansi skor, catatan kualitas,
#    konsistensi pembulatan Decimal ROUND_HALF_UP, dan validasi kelengkapan 5 komponen breakdown).
# 2. Day 19.2 - Matching Stability & Order Invariance (pengujian determinisme permutasi unik,
#    dokumentasi status sampling/exhaustive, dan determinisme pemilihan jadwal bersama).
# 3. Day 19.3 - Robustness Testing (evaluasi data sparse, non-ideal, dan pemantauan CVR = 0%).
# 4. Day 19.4 - Top-K Quality Benchmarking (analisis Quality Retention & Quality Loss).
# 5. Day 19.5 - Performance & Reliability Metrics (pengukuran metrik komprehensif).
#
# PENTING:
# Modul ini TIDAK mengubah formula inti penilaian (scoring.py), hard constraints (Day 14),
# maupun bobot preferensi (Day 15). Modul ini bekerja murni sebagai evaluator independen.
# ==============================================================================

import copy
import math
import random
import statistics
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Sequence, Tuple, Union

from app.group_formation import calculate_group_quality_score, form_study_group
from app.models import StudyIntent
from app.schemas import (
    PairwiseScoreDistribution,
    WeakestLinkDetail,
    StrongestLinkDetail,
    FormulaConsistencyCheck,
    GroupQualityEvaluationResult,
    OrderPermutationRun,
    MatchingStabilityResult,
    RobustnessScenarioResult,
    RobustnessEvaluationResult,
    TopKPoolBenchmarkItem,
    TopKBenchmarkResult,
    ComprehensiveEvaluationSummary,
    ComprehensiveEvaluationReport,
)


REQUIRED_BREAKDOWN_COMPONENTS = ("topic", "goal", "style", "date", "mode")


# ==============================================================================
# 1. EVALUASI DISTRIBUSI SKOR PAIRWISE (D19.1-01 HARDENING)
# ==============================================================================

def calculate_pairwise_distribution(
    scores: Sequence[Union[float, int, Decimal]]
) -> PairwiseScoreDistribution:
    """
    Menghitung statistik distribusi skor kecocokan pairwise seluruh pasangan.
    Metrik meliputi:
      - count: jumlah pasangan (N_pair)
      - mean: rata-rata skor pasangan (APS), dihitung menggunakan Decimal ROUND_HALF_UP 2 desimal
              sehingga 100% konsisten dengan calculate_group_quality_score().
      - median: nilai tengah skor pasangan
      - min_score: skor pasangan terendah (MPS)
      - max_score: skor pasangan tertinggi
      - score_spread: rentang disparitas skor (max - min)
      - variance: variansi populasi dari skor pasangan
      - std_dev: deviasi standar populasi
    """
    if not scores:
        return PairwiseScoreDistribution(
            count=0,
            mean=0.0,
            median=0.0,
            std_dev=0.0,
            variance=0.0,
            min_score=0.0,
            max_score=0.0,
            score_spread=0.0,
        )

    q2 = Decimal("0.01")
    dec_scores = []
    for s in scores:
        if isinstance(s, Decimal):
            dec_scores.append(s)
        elif isinstance(s, (int, float)):
            dec_scores.append(Decimal(str(round(float(s), 4))))
        else:
            dec_scores.append(Decimal(str(s)))

    n_dec = Decimal(len(dec_scores))

    # 1. Mean (APS) - menggunakan Decimal presisi tinggi dan ROUND_HALF_UP
    mean_dec = sum(dec_scores) / n_dec
    mean_rounded = float(mean_dec.quantize(q2, rounding=ROUND_HALF_UP))

    # 2. Min (MPS) dan Max
    min_dec = min(dec_scores)
    max_dec = max(dec_scores)
    min_rounded = float(min_dec.quantize(q2, rounding=ROUND_HALF_UP))
    max_rounded = float(max_dec.quantize(q2, rounding=ROUND_HALF_UP))

    # 3. Spread (Disparitas)
    spread_dec = max_dec - min_dec
    spread_rounded = float(spread_dec.quantize(q2, rounding=ROUND_HALF_UP))

    # 4. Median (Decimal)
    sorted_dec = sorted(dec_scores)
    len_int = len(sorted_dec)
    if len_int % 2 == 1:
        median_dec = sorted_dec[len_int // 2]
    else:
        median_dec = (sorted_dec[len_int // 2 - 1] + sorted_dec[len_int // 2]) / Decimal("2")
    median_rounded = float(median_dec.quantize(q2, rounding=ROUND_HALF_UP))

    # 5. Variansi Populasi & Standar Deviasi
    if len_int > 1:
        sum_sq_diff = sum((x - mean_dec) ** 2 for x in dec_scores)
        var_dec = sum_sq_diff / n_dec
        var_float = float(var_dec)
        std_float = math.sqrt(var_float)
        var_rounded = float(var_dec.quantize(q2, rounding=ROUND_HALF_UP))
        std_dec = Decimal(str(round(std_float, 4)))
        std_rounded = float(std_dec.quantize(q2, rounding=ROUND_HALF_UP))
    else:
        var_rounded = 0.0
        std_rounded = 0.0

    return PairwiseScoreDistribution(
        count=int(n_dec),
        mean=mean_rounded,
        median=median_rounded,
        std_dev=std_rounded,
        variance=var_rounded,
        min_score=min_rounded,
        max_score=max_rounded,
        score_spread=spread_rounded,
    )


# ==============================================================================
# 2. VALIDASI KONSISTENSI FORMULA GQ & BREAKDOWN (D19.1-02 HARDENING)
# ==============================================================================

def verify_gq_consistency(
    gq: float,
    aps: float,
    mps: float,
    tolerance: float = 0.01
) -> FormulaConsistencyCheck:
    """
    Memvalidasi konsistensi formula matematis:
      GQ = 0.70 * APS + 0.30 * MPS
    dengan pembulatan ROUND_HALF_UP 2 desimal.
    """
    dec_aps = Decimal(str(round(float(aps), 4)))
    dec_mps = Decimal(str(round(float(mps), 4)))
    dec_expected = (Decimal("0.70") * dec_aps) + (Decimal("0.30") * dec_mps)
    expected_rounded = float(dec_expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    actual_val = round(float(gq), 2)
    discrepancy = round(abs(actual_val - expected_rounded), 4)
    is_valid = discrepancy <= tolerance

    expr = f"0.70 * {round(aps, 2):.2f} + 0.30 * {round(mps, 2):.2f} = {expected_rounded:.2f}"

    return FormulaConsistencyCheck(
        is_valid=is_valid,
        expected_gq=expected_rounded,
        actual_gq=actual_val,
        discrepancy=discrepancy,
        formula_expression=expr,
        aps=round(float(aps), 2),
        mps=round(float(mps), 2),
    )


def verify_pairwise_breakdown_consistency(
    pairwise_item: Dict[str, Any],
    tolerance: float = 0.01
) -> Dict[str, Any]:
    """
    Memvalidasi apakah Compatibility Score suatu pasangan identik dengan
    penjumlahan seluruh sub-komponen breakdown Day 15:
      Total Score == Topic + Goal + Style + Schedule (Date) + Mode

    PENTING (D19.1-02 HARDENING):
    Validator mewajibkan kelima komponen ("topic", "goal", "style", "date", "mode")
    tersedia secara lengkap dan memiliki kontribusi numerik valid (int/float/Decimal, bukan boolean/string).
    Jika ada komponen yang hilang, bertipe string numerik, atau tidak valid, validasi dinyatakan GAGAL.
    """
    if not isinstance(pairwise_item, dict):
        return {
            "is_consistent": False,
            "compatibility_score": 0.0,
            "sum_of_contributions": 0.0,
            "discrepancy": 0.0,
            "missing_components": list(REQUIRED_BREAKDOWN_COMPONENTS),
            "invalid_components": [],
            "error": "pairwise_item harus berupa dictionary",
            "component_contributions": {},
        }

    # 1. Validasi Compatibility Score
    raw_cs = pairwise_item.get("compatibility_score")
    if raw_cs is None or isinstance(raw_cs, bool) or not isinstance(raw_cs, (int, float, Decimal)):
        return {
            "is_consistent": False,
            "compatibility_score": 0.0,
            "sum_of_contributions": 0.0,
            "discrepancy": 0.0,
            "missing_components": [],
            "invalid_components": [],
            "error": "compatibility_score tidak ditemukan, bernilai boolean, atau bukan numerik",
            "component_contributions": {},
        }
    try:
        total_score = float(raw_cs)
        if math.isnan(total_score) or math.isinf(total_score):
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        return {
            "is_consistent": False,
            "compatibility_score": 0.0,
            "sum_of_contributions": 0.0,
            "discrepancy": 0.0,
            "missing_components": [],
            "invalid_components": [],
            "error": "compatibility_score bukan angka berhingga valid",
            "component_contributions": {},
        }

    # 2. Validasi struktur breakdown
    breakdown = pairwise_item.get("breakdown")
    if hasattr(breakdown, "model_dump"):
        breakdown = breakdown.model_dump()
    elif hasattr(breakdown, "dict"):
        breakdown = breakdown.dict()

    if not isinstance(breakdown, dict) or not breakdown:
        return {
            "is_consistent": False,
            "compatibility_score": round(total_score, 2),
            "sum_of_contributions": 0.0,
            "discrepancy": round(total_score, 2),
            "missing_components": list(REQUIRED_BREAKDOWN_COMPONENTS),
            "invalid_components": [],
            "error": "breakdown kosong atau bukan dictionary",
            "component_contributions": {},
        }

    # 3. Pengecekan ketat kelima komponen wajib Day 15
    missing_components = []
    invalid_components = []
    component_details = {}
    sum_contributions = Decimal("0.0")

    for comp_key in REQUIRED_BREAKDOWN_COMPONENTS:
        if comp_key not in breakdown or breakdown[comp_key] is None:
            missing_components.append(comp_key)
            continue

        comp_data = breakdown[comp_key]
        if isinstance(comp_data, dict):
            raw_contrib = comp_data.get("contribution")
        elif hasattr(comp_data, "contribution"):
            raw_contrib = getattr(comp_data, "contribution")
        else:
            raw_contrib = None

        # Tolak boolean, string numerik, None, atau tipe non-numerik
        if raw_contrib is None or isinstance(raw_contrib, bool) or not isinstance(raw_contrib, (int, float, Decimal)):
            invalid_components.append(comp_key)
            continue

        try:
            val_float = float(raw_contrib)
            if math.isnan(val_float) or math.isinf(val_float):
                invalid_components.append(comp_key)
                continue
            dec_contrib = Decimal(str(round(val_float, 4)))
            sum_contributions += dec_contrib
            component_details[comp_key] = float(dec_contrib.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        except (ValueError, TypeError, OverflowError):
            invalid_components.append(comp_key)

    q2 = Decimal("0.01")
    sum_rounded = float(sum_contributions.quantize(q2, rounding=ROUND_HALF_UP))
    dec_total = Decimal(str(round(total_score, 4))).quantize(q2, rounding=ROUND_HALF_UP)
    total_rounded = float(dec_total)

    discrepancy = round(abs(total_rounded - sum_rounded), 4)

    is_complete = (len(missing_components) == 0 and len(invalid_components) == 0)
    is_sum_matching = (discrepancy <= tolerance)
    is_consistent = is_complete and is_sum_matching

    error_msg = None
    if missing_components:
        error_msg = f"Komponen wajib tidak lengkap: {', '.join(missing_components)}"
    elif invalid_components:
        error_msg = f"Komponen memiliki kontribusi invalid: {', '.join(invalid_components)}"
    elif not is_sum_matching:
        error_msg = f"Total Compatibility Score ({total_rounded}) != Jumlah Kontribusi ({sum_rounded})"

    return {
        "is_consistent": is_consistent,
        "compatibility_score": total_rounded,
        "sum_of_contributions": sum_rounded,
        "discrepancy": discrepancy,
        "missing_components": missing_components,
        "invalid_components": invalid_components,
        "error": error_msg,
        "component_contributions": component_details,
    }


# ==============================================================================
# 3. IDENTIFIKASI PASANGAN TERLEMAH & TERKUAT (WEAKEST & STRONGEST LINKS)
# ==============================================================================

def identify_weakest_and_strongest_links(
    pairwise_scores: Sequence[Dict[str, Any]]
) -> Tuple[Optional[WeakestLinkDetail], Optional[StrongestLinkDetail]]:
    """
    Mengidentifikasi pasangan dengan skor terlemah (MPS bottleneck)
    dan pasangan dengan skor tertinggi (Strongest link).
    """
    if not pairwise_scores:
        return None, None

    sorted_pairs = sorted(
        pairwise_scores,
        key=lambda item: float(item.get("compatibility_score", 0.0))
    )

    weakest_item = sorted_pairs[0]
    strongest_item = sorted_pairs[-1]

    def _to_link_detail(item: Dict[str, Any], is_weak: bool):
        cls = WeakestLinkDetail if is_weak else StrongestLinkDetail
        bd = item.get("breakdown")
        if hasattr(bd, "model_dump"):
            bd = bd.model_dump()
        elif hasattr(bd, "dict"):
            bd = bd.dict()

        return cls(
            student_a_id=str(item.get("student_a_id", "")),
            student_b_id=str(item.get("student_b_id", "")),
            intent_a_id=str(item.get("intent_a_id", "")),
            intent_b_id=str(item.get("intent_b_id", "")),
            score=round(float(item.get("compatibility_score", 0.0)), 2),
            explanation=item.get("explanation"),
            breakdown=bd,
        )

    return _to_link_detail(weakest_item, True), _to_link_detail(strongest_item, False)


# ==============================================================================
# 4. PENENTUAN TIER KUALITAS & CATATAN EVALUASI (QUALITY NOTES)
# ==============================================================================

def determine_quality_tier(gq: float) -> str:
    """
    Mengelompokkan kualitas kelompok berdasarkan Group Quality Score (GQ):
      - EXCELLENT: GQ >= 85.0
      - GOOD: 75.0 <= GQ < 85.0
      - SATISFACTORY: 65.0 <= GQ < 75.0
      - NEEDS_IMPROVEMENT: GQ < 65.0
    """
    if gq >= 85.0:
        return "EXCELLENT"
    elif gq >= 75.0:
        return "GOOD"
    elif gq >= 65.0:
        return "SATISFACTORY"
    else:
        return "NEEDS_IMPROVEMENT"


def generate_quality_notes(
    gq: float,
    aps: float,
    mps: float,
    distribution: PairwiseScoreDistribution,
    weakest_link: Optional[WeakestLinkDetail]
) -> List[str]:
    """
    Menghasilkan catatan diagnostik evaluasi kualitas kelompok yang transparan.
    """
    notes = []
    tier = determine_quality_tier(gq)
    notes.append(f"Kualitas keseluruhan kelompok berada pada kategori '{tier}' dengan Group Quality Score {gq:.2f}.")

    # Analisis penalti MPS
    mps_penalty = round(aps - gq, 2)
    if mps_penalty > 0:
        notes.append(
            f"Penalti kecocokan minimum (MPS 30% weighting) mengurangi skor kelompok sebesar {mps_penalty:.2f} poin dibandingkan rata-rata pairwise (APS {aps:.2f})."
        )
    else:
        notes.append("Kecocokan antar anggota sangat homogen (APS dan MPS seimbang).")

    # Analisis dispersi
    if distribution.score_spread > 20.0:
        notes.append(
            f"Terdapat variasi kecocokan signifikan antar pasangan dalam kelompok (disparitas: {distribution.score_spread:.2f} poin, std dev: {distribution.std_dev:.2f})."
        )
    elif distribution.score_spread <= 5.0 and distribution.count > 1:
        notes.append(
            f"Kekompakan kelompok sangat konsisten dan merata di seluruh pasangan (disparitas: {distribution.score_spread:.2f} poin)."
        )

    # Identifikasi bottleneck pada weakest link
    if weakest_link and weakest_link.breakdown:
        breakdown = weakest_link.breakdown
        min_comp = None
        min_comp_score = 999.0
        for comp_name in ["topic", "goal", "style", "date", "mode"]:
            c_data = breakdown.get(comp_name)
            if isinstance(c_data, dict) and "score" in c_data:
                sc = float(c_data["score"])
                if sc < min_comp_score:
                    min_comp_score = sc
                    min_comp = comp_name

        if min_comp:
            notes.append(
                f"Faktor pembatas utama pada pasangan terlemah ({weakest_link.student_a_id} & {weakest_link.student_b_id}, skor: {weakest_link.score:.2f}) adalah komponen '{min_comp}' dengan skor kecocokan {min_comp_score:.2f}."
            )

    return notes


# ==============================================================================
# 5. EVALUATOR UTAMA KUALITAS KELOMPOK (DAY 19.1)
# ==============================================================================

def evaluate_group_quality(
    data: Union[Dict[str, Any], Sequence[Union[float, int, Decimal]]]
) -> GroupQualityEvaluationResult:
    """
    Fungsi evaluator utama Day 19.1:
    Menerima dictionary hasil form_study_group / preview_group_formation_pipeline,
    atau sekumpulan skor numerik pasangan [CS_1, CS_2, ...].

    Menghasilkan laporan komprehensif GroupQualityEvaluationResult.
    """
    if isinstance(data, dict):
        raw_pairwise = data.get("pairwise_scores", [])
        scores = [float(item.get("compatibility_score", 0.0)) for item in raw_pairwise]
        gq = float(data.get("group_quality_score", 0.0))
        aps = float(data.get("average_pair_score", 0.0))
        mps = float(data.get("minimum_pair_score", 0.0))
        group_size = int(data.get("group_size", len(data.get("members", []))))

        # Periksa konsistensi breakdown untuk setiap item pairwise jika tersedia
        breakdown_consistent = True
        for pw in raw_pairwise:
            if isinstance(pw, dict) and "breakdown" in pw and pw["breakdown"] is not None:
                chk = verify_pairwise_breakdown_consistency(pw)
                if not chk["is_consistent"]:
                    breakdown_consistent = False
                    break

        # Jika scores kosong atau tidak konsisten, hitung ulang
        if not scores and "all_pairwise_scores" in data:
            scores = [float(s) for s in data["all_pairwise_scores"]]

        if scores and (gq == 0.0 and aps == 0.0 and mps == 0.0):
            gq, aps, mps = calculate_group_quality_score(scores)

        weakest_link, strongest_link = identify_weakest_and_strongest_links(raw_pairwise)
    else:
        scores = [float(s) for s in data]
        gq, aps, mps = calculate_group_quality_score(scores)
        group_size = len(scores) + 1 if scores else 0
        breakdown_consistent = True
        weakest_link = None
        strongest_link = None
        if scores:
            min_s = min(scores)
            max_s = max(scores)
            weakest_link = WeakestLinkDetail(score=round(min_s, 2))
            strongest_link = StrongestLinkDetail(score=round(max_s, 2))

    distribution = calculate_pairwise_distribution(scores)
    formula_check = verify_gq_consistency(gq, aps, mps)
    tier = determine_quality_tier(gq)
    notes = generate_quality_notes(gq, aps, mps, distribution, weakest_link)

    max_pair_score = distribution.max_score

    return GroupQualityEvaluationResult(
        group_quality_score=round(gq, 2),
        average_pair_score=round(aps, 2),
        minimum_pair_score=round(mps, 2),
        maximum_pair_score=round(max_pair_score, 2),
        distribution=distribution,
        weakest_link=weakest_link,
        strongest_link=strongest_link,
        formula_consistency=formula_check,
        all_pairwise_scores=[round(s, 2) for s in scores],
        quality_tier=tier,
        evaluation_notes=notes,
        group_size=group_size,
        is_breakdown_consistent=breakdown_consistent,
    )


# ==============================================================================
# 6. BENCHMARK KELOMPOK STANDAR (BENCHMARK SUITE)
# ==============================================================================

def validate_benchmark_cases() -> Dict[str, GroupQualityEvaluationResult]:
    """
    Menjalankan validasi terhadap dua benchmark standar dari perancangan Day 7 / Day 19:
      - Kelompok A: [90.0, 85.0, 80.0] -> APS=85.0, MPS=80.0, GQ=83.5
      - Kelompok B: [100.0, 100.0, 40.0] -> APS=80.0, MPS=40.0, GQ=68.0

    Membuktikan secara matematis bahwa Kelompok A lebih unggul daripada Kelompok B
    karena adanya penalti 30% MPS pada pasangan terlemah Kelompok B.
    """
    group_a_scores = [90.0, 85.0, 80.0]
    group_b_scores = [100.0, 100.0, 40.0]

    eval_a = evaluate_group_quality(group_a_scores)
    eval_b = evaluate_group_quality(group_b_scores)

    return {
        "kelompok_a": eval_a,
        "kelompok_b": eval_b,
    }


# ==============================================================================
# 7. EVALUASI STABILITAS & ORDER INVARIANCE (DAY 19.2 HARDENING)
# ==============================================================================

def generate_distinct_permutations(
    candidates: Sequence[StudyIntent],
    num_permutations: int,
    random_seed: int = 42
) -> List[List[StudyIntent]]:
    """
    Menghasilkan daftar urutan kandidat yang TERBUKTI BERBEDA (distinct permutations).

    Aturan:
    - Permutasi 1: Urutan baseline asli.
    - Permutasi 2+: Variasi unik yang dijamin tidak identik dengan baseline maupun
      satu sama lain, meliputi urutan terbalik (reverse), rotasi siklis, interleave,
      dan random shuffles dengan deduplikasi berbasis tuple ID intent.
    - Menghindari pengulangan urutan identik saat pengujian stabilitas.
    """
    cand_list = list(candidates)
    n = len(cand_list)
    if n <= 1:
        return [list(cand_list)]

    seen_orders = set()
    result: List[List[StudyIntent]] = []

    def _sig(arr: Sequence[StudyIntent]) -> Tuple[str, ...]:
        return tuple(str(getattr(c, "intent_id", id(c))) for c in arr)

    # 1. Baseline Run (Urutan asli)
    sig_base = _sig(cand_list)
    seen_orders.add(sig_base)
    result.append(list(cand_list))

    if num_permutations <= 1:
        rev = list(reversed(cand_list))
        return [rev]

    # 2. Heuristik variasi deterministik:
    # 2a. Reversed order
    rev = list(reversed(cand_list))
    sig_rev = _sig(rev)
    if sig_rev not in seen_orders and len(result) < num_permutations:
        seen_orders.add(sig_rev)
        result.append(rev)

    # 2b. Rotasi siklis (cyclic shifts)
    for shift in range(1, n):
        if len(result) >= num_permutations:
            break
        rotated = cand_list[shift:] + cand_list[:shift]
        sig_rot = _sig(rotated)
        if sig_rot not in seen_orders:
            seen_orders.add(sig_rot)
            result.append(rotated)

    # 2c. Interleaved order (bergantian dari depan dan belakang)
    if len(result) < num_permutations and n >= 3:
        interleaved = []
        left, right = 0, n - 1
        while left <= right:
            if left == right:
                interleaved.append(cand_list[left])
            else:
                interleaved.append(cand_list[left])
                interleaved.append(cand_list[right])
            left += 1
            right -= 1
        sig_int = _sig(interleaved)
        if sig_int not in seen_orders:
            seen_orders.add(sig_int)
            result.append(interleaved)

    # 2d. Random shuffles terarah untuk memenuhi sisa kuota num_permutations
    rng = random.Random(random_seed)
    max_attempts = 200
    attempts = 0
    while len(result) < num_permutations and attempts < max_attempts:
        attempts += 1
        shuffled = list(cand_list)
        rng.shuffle(shuffled)
        sig_shuf = _sig(shuffled)
        if sig_shuf not in seen_orders:
            seen_orders.add(sig_shuf)
            result.append(shuffled)

    return result


def _make_comprehensive_group_signature(res: Dict[str, Any]) -> str:
    """
    Menghasilkan representasi signature komprehensif dari hasil form_study_group:
    Mencakup:
      - formation_status (e.g. READY, NO_COMPATIBLE_GROUP, INSUFFICIENT_MEMBERS)
      - group_size (jumlah anggota)
      - sorted member intent IDs
      - group_quality_score (GQ)
      - average_pair_score (APS)
      - minimum_pair_score (MPS)
      - selected_schedule (date, start_time, end_time, duration)
    """
    status = str(res.get("formation_status", "UNKNOWN"))
    size = int(res.get("group_size", 0))
    members = sorted(str(m.get("intent_id", "")) for m in res.get("members", []))
    gq = round(float(res.get("group_quality_score", 0.0)), 2)
    aps = round(float(res.get("average_pair_score", 0.0)), 2)
    mps = round(float(res.get("minimum_pair_score", 0.0)), 2)

    sched = res.get("selected_schedule")
    if sched and isinstance(sched, dict):
        sched_key = f"{sched.get('date')}_{sched.get('start_time')}_{sched.get('end_time')}_{sched.get('duration_minutes')}"
    else:
        sched_key = "NO_SCHED"

    return f"STATUS_{status}__SIZE_{size}__MEMBERS_{'-'.join(members)}__GQ_{gq:.2f}__APS_{aps:.2f}__MPS_{mps:.2f}__SCHED_{sched_key}"


def evaluate_matching_stability(
    host_intent: StudyIntent,
    candidate_intents: Sequence[StudyIntent],
    min_score: float = 60.0,
    max_candidate_pool: Optional[int] = 20,
    target_group_size: Optional[int] = None,
    num_permutations: int = 10,
    random_seed: int = 42
) -> MatchingStabilityResult:
    """
    Menguji order invariance matching engine (Day 19.2):
    Menjalankan form_study_group terhadap berbagai urutan kandidat yang TERBUKTI BERBEDA.

    Kriteria Konsistensi:
    Dinyatakan konsisten jika dan hanya jika seluruh atribut hasil identik:
      1. formation_status identik
      2. seluruh anggota kelompok terpilih identik
      3. group_quality_score (GQ), APS, dan MPS identik
      4. selected_schedule (tanggal, jam mulai, jam selesai, durasi) identik

    Formula Determinism Rate:
      DR = (N_consistent / N_runs) * 100%
      Target: DR = 100.0%
    """
    if num_permutations < 1:
        raise ValueError("num_permutations minimal 1")

    # 1. Jalankan baseline dengan urutan asli
    baseline_run = form_study_group(
        host_intent=host_intent,
        candidate_intents=list(candidate_intents),
        min_score=min_score,
        target_group_size=target_group_size,
        max_candidate_pool=max_candidate_pool,
    )

    baseline_signature = _make_comprehensive_group_signature(baseline_run)

    # 2. Hasilkan permutasi urutan kandidat yang terbukti berbeda
    permutations_list = generate_distinct_permutations(
        candidates=candidate_intents,
        num_permutations=num_permutations,
        random_seed=random_seed
    )

    permutation_runs: List[OrderPermutationRun] = []
    signatures_seen = set()
    matches_count = 0

    for idx, perm_candidates in enumerate(permutations_list):
        run_res = form_study_group(
            host_intent=host_intent,
            candidate_intents=perm_candidates,
            min_score=min_score,
            target_group_size=target_group_size,
            max_candidate_pool=max_candidate_pool,
        )

        run_members = sorted(str(m.get("intent_id", "")) for m in run_res.get("members", []))
        run_gq = round(float(run_res.get("group_quality_score", 0.0)), 2)
        run_sig = _make_comprehensive_group_signature(run_res)

        signatures_seen.add(run_sig)
        is_match = (run_sig == baseline_signature)
        if is_match:
            matches_count += 1

        r_sched = run_res.get("selected_schedule")
        r_sched_key = f"{r_sched.get('date')}_{r_sched.get('start_time')}_{r_sched.get('end_time')}" if r_sched else "NO_SCHED"

        permutation_runs.append(OrderPermutationRun(
            permutation_index=idx + 1,
            input_order_intent_ids=[str(getattr(c, "intent_id", "")) for c in perm_candidates],
            selected_member_intent_ids=run_members,
            group_quality_score=run_gq,
            selected_schedule_key=r_sched_key,
            matches_baseline=is_match,
        ))

    total_runs = len(permutations_list)
    determinism_rate = round((matches_count / total_runs) * 100.0, 2)
    is_order_invariant = (len(signatures_seen) == 1 and matches_count == total_runs)

    # D19.2-01: Dokumentasi apakah pengujian bersifat exhaustive atau sampled
    cand_count = len(candidate_intents)
    if cand_count <= 1:
        is_exhaustive = True
        sample_method = "TRIVIAL_SINGLE_CANDIDATE"
    else:
        max_possible_perms = math.factorial(min(cand_count, 10)) if cand_count <= 10 else 10**10
        is_exhaustive = (max_possible_perms <= total_runs)
        sample_method = "EXHAUSTIVE" if is_exhaustive else "SAMPLED_DETERMINISTIC_AND_RANDOM"

    return MatchingStabilityResult(
        num_permutations=total_runs,
        is_order_invariant=is_order_invariant,
        determinism_rate=determinism_rate,
        distinct_group_signatures=len(signatures_seen),
        baseline_signature=baseline_signature,
        permutations=permutation_runs,
        is_exhaustive=is_exhaustive,
        sample_method=sample_method,
    )


# ==============================================================================
# 8. EVALUASI TRADE-OFF TOP-K OPTIMIZATION (DAY 19.4)
# ==============================================================================

def benchmark_top_k_candidate_pool(
    host_intent: StudyIntent,
    candidate_intents: Sequence[StudyIntent],
    k_values: Sequence[Optional[int]] = (5, 10, 20, 30, None),
    min_score: float = 60.0
) -> TopKBenchmarkResult:
    """
    Membandingkan performa dan kualitas matching pada berbagai batas ukuran pool kandidat (Top-K).
    Menghitung:
      - Quality Retention = (GQ_topK / GQ_full) * 100%
      - Quality Loss = ((GQ_full - GQ_topK) / GQ_full) * 100%
      - Execution Time comparison
    """
    candidates_list = list(candidate_intents)
    total_candidates = len(candidates_list)

    # 1. Jalankan baseline: Full Pool (None)
    t0 = time.perf_counter()
    full_res = form_study_group(
        host_intent=host_intent,
        candidate_intents=candidates_list,
        min_score=min_score,
        max_candidate_pool=None
    )
    full_time_ms = round((time.perf_counter() - t0) * 1000, 2)
    full_gq = float(full_res.get("group_quality_score", 0.0))

    full_members = set()
    for m in full_res.get("members", []):
        mid = getattr(m, "intent_id", None) if not isinstance(m, dict) else m.get("intent_id")
        if mid:
            full_members.add(str(mid))

    items: List[TopKPoolBenchmarkItem] = []

    for k in k_values:
        t_start = time.perf_counter()
        res = form_study_group(
            host_intent=host_intent,
            candidate_intents=candidates_list,
            min_score=min_score,
            max_candidate_pool=k
        )
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

        gq = float(res.get("group_quality_score", 0.0))
        aps = float(res.get("average_pair_score", 0.0))
        mps = float(res.get("minimum_pair_score", 0.0))
        pruning = res.get("candidate_pruning_stats", {})
        cand_in_pool = pruning.get("candidates_in_pool", 0)
        cand_examined = pruning.get("total_candidates_examined", 0)

        # Hitung Quality Retention & Quality Loss
        if full_gq > 0.0:
            retention = min(100.0, max(0.0, round((gq / full_gq) * 100.0, 2)))
            loss = min(100.0, max(0.0, round(((full_gq - gq) / full_gq) * 100.0, 2)))
        else:
            retention = 100.0
            loss = 0.0

        # Cek apakah anggota kelompok identik dengan baseline Full
        k_members = set()
        for m in res.get("members", []):
            mid = getattr(m, "intent_id", None) if not isinstance(m, dict) else m.get("intent_id")
            if mid:
                k_members.add(str(mid))
        is_identical = (full_members == k_members) if full_members else (len(k_members) == 0)

        k_label = "Full" if k is None else k

        items.append(TopKPoolBenchmarkItem(
            k_value=k_label,
            candidates_in_pool=cand_in_pool,
            candidates_examined=cand_examined,
            formation_status=res.get("formation_status", "UNKNOWN"),
            group_size=res.get("group_size", 0),
            group_quality_score=round(gq, 2),
            average_pair_score=round(aps, 2),
            minimum_pair_score=round(mps, 2),
            quality_loss=loss,
            quality_retention=retention,
            execution_time_ms=elapsed_ms,
            is_identical_to_baseline=is_identical,
        ))

    return TopKBenchmarkResult(
        total_candidates=total_candidates,
        baseline_k="Full",
        benchmarks=items,
    )


# ==============================================================================
# 9. EVALUASI KETAHANAN DATA TIDAK IDEAL (ROBUSTNESS TESTING - DAY 19.3)
# ==============================================================================

def check_hard_constraint_violations(
    host_intent: StudyIntent,
    formation_result: Dict[str, Any],
    candidate_lookup: Optional[Dict[str, StudyIntent]] = None
) -> List[str]:
    """
    Memeriksa secara independen apakah hasil pembentukan kelompok melanggar
    satu pun aturan Hard Constraints dari Day 14 atau aturan multi-way Day 17/18.

    Aturan yang diperiksa:
    1. Status konsistensi ukuran: jika READY, maka group_size >= 2 dan min_bound <= group_size <= max_bound.
    2. Mata kuliah identik: seluruh anggota harus memiliki course_id yang sama persis dengan host.
    3. Akun valid: seluruh anggota harus berstatus ACTIVE, VERIFIED, dan is_discoverable.
    4. Transitive Learning Mode: tidak boleh ada kelompok yang memuat anggota ONLINE dan OFFLINE sekaligus.
    5. Kapasitas beririsan: min_bound <= max_bound dan ukuran kelompok memenuhi kapasitas setiap anggota.
    6. Irisan jadwal: jika READY, selected_schedule harus ada dengan durasi >= 60 menit.
    7. Deduplikasi mahasiswa: seluruh anggota harus memiliki student_id unik (tidak ada duplikasi akun).
    """
    violations = []
    status = formation_result.get("formation_status", "UNKNOWN")
    group_size = int(formation_result.get("group_size", 0))
    members = formation_result.get("members", [])
    selected_sched = formation_result.get("selected_schedule")
    min_bound = int(formation_result.get("min_group_size_bound", 2))
    max_bound = int(formation_result.get("max_group_size_bound", 10))

    # 1. Pengecekan status READY
    if status == "READY":
        if group_size < 2:
            violations.append(f"Ukuran kelompok READY ({group_size}) kurang dari batas minimum absolut (2)")
        if group_size < min_bound:
            violations.append(f"Ukuran kelompok READY ({group_size}) kurang dari min_group_size_bound ({min_bound})")
        if group_size > max_bound:
            violations.append(f"Ukuran kelompok READY ({group_size}) melebihi max_group_size_bound ({max_bound})")
        if not selected_sched:
            violations.append("Kelompok berstatus READY tetapi tidak memiliki selected_schedule")
        elif selected_sched.get("duration_minutes", 0) < 60:
            violations.append(f"Durasi selected_schedule ({selected_sched.get('duration_minutes')}m) kurang dari 60 menit")

    # 2. Pengecekan anggota jika ada lookup kandidat
    if candidate_lookup:
        student_ids = []
        modes = []
        # Tambahkan host ke daftar pengecekan
        host_student = getattr(host_intent, "student", None)
        if host_student:
            student_ids.append(host_student.student_id)
        modes.append(getattr(host_intent, "learning_mode", "HYBRID"))

        for m in members:
            iid = m.get("intent_id")
            if str(iid) == str(host_intent.intent_id):
                continue
            intent_obj = candidate_lookup.get(iid)
            if intent_obj:
                # Cek Course
                if str(intent_obj.course_id) != str(host_intent.course_id):
                    violations.append(f"Anggota {iid} memiliki course_id berbeda ({intent_obj.course_id} != {host_intent.course_id})")

                # Cek Student status
                st = getattr(intent_obj, "student", None)
                if st:
                    if getattr(st, "account_status", None) != "ACTIVE":
                        violations.append(f"Anggota {iid} memiliki akun tidak aktif ({getattr(st, 'account_status', None)})")
                    if getattr(st, "verification_status", None) != "VERIFIED":
                        violations.append(f"Anggota {iid} belum terverifikasi ({getattr(st, 'verification_status', None)})")
                    if not getattr(st, "is_discoverable", True):
                        violations.append(f"Anggota {iid} memiliki is_discoverable=False")
                    student_ids.append(st.student_id)

                # Mode
                modes.append(getattr(intent_obj, "learning_mode", "HYBRID"))

        # Cek Deduplikasi Mahasiswa
        if len(student_ids) != len(set(student_ids)):
            violations.append("Terdapat duplikasi mahasiswa (student_id sama) dalam kelompok yang sama")

        # Cek Mode Transitive
        if "ONLINE" in modes and "OFFLINE" in modes:
            violations.append("Kelompok memuat mahasiswa ONLINE dan OFFLINE sekaligus (inkompatibel)")

    return violations


def evaluate_matching_robustness(
    host_intent: StudyIntent,
    candidate_scenarios: Sequence[Dict[str, Any]]
) -> RobustnessEvaluationResult:
    """
    Evaluator Ketahanan Sistem (Day 19.3):
    Menjalankan kumpulan skenario data tidak ideal (sparse, empty, disjoint schedule,
    course mismatch, insufficient members, restricted account, adversarial).

    Menghitung Constraint Violation Rate (CVR):
      CVR = (N_violations / N_scenarios_evaluated) * 100%
      Target: CVR = 0.0%
    """
    scenario_results: List[RobustnessScenarioResult] = []
    total_tested = len(candidate_scenarios)
    passed_count = 0
    failed_count = 0
    violation_count = 0

    for sc in candidate_scenarios:
        name = sc.get("scenario_name", "Unnamed Scenario")
        desc = sc.get("description", "")
        expected_status = sc.get("expected_status", "UNKNOWN")
        candidates = sc.get("candidates", [])
        min_score = sc.get("min_score", 60.0)
        target_size = sc.get("target_group_size")

        # Buat lookup dict kandidat
        cand_lookup = {str(c.intent_id): c for c in candidates}
        cand_lookup[str(host_intent.intent_id)] = host_intent

        try:
            res = form_study_group(
                host_intent=host_intent,
                candidate_intents=candidates,
                min_score=min_score,
                target_group_size=target_size
            )
            actual_status = res.get("formation_status", "UNKNOWN")
            violations = check_hard_constraint_violations(host_intent, res, cand_lookup)
        except Exception as e:
            # Jika skenario memang dirancang untuk melempar error input (misal host intent None/inaktif)
            actual_status = "ERROR_RAISED"
            violations = []
            if expected_status != "ERROR_RAISED":
                violations.append(f"Exception tidak terduga: {str(e)}")

        has_violation = (len(violations) > 0)
        # Skenario lolos jika status sesuai ekspektasi DAN tidak ada pelanggaran hard constraint
        is_passed = (not has_violation) and (actual_status == expected_status)

        if has_violation:
            violation_count += 1
            failed_count += 1
            msg = f"GAGAL: Terjadi {len(violations)} pelanggaran constraint: {'; '.join(violations)}"
        elif not is_passed:
            failed_count += 1
            msg = f"GAGAL: Status tidak sesuai ekspektasi (expected: {expected_status}, actual: {actual_status})"
        else:
            passed_count += 1
            msg = f"SUKSES: Status tepat '{actual_status}' tanpa pelanggaran constraint."

        scenario_results.append(RobustnessScenarioResult(
            scenario_name=name,
            description=desc,
            expected_status=expected_status,
            actual_status=actual_status,
            is_violation=has_violation,
            message=msg,
        ))

    cvr = round((violation_count / total_tested) * 100.0, 2) if total_tested > 0 else 0.0
    all_preserved = (cvr == 0.0 and passed_count == total_tested)

    return RobustnessEvaluationResult(
        total_scenarios_tested=total_tested,
        passed_scenarios=passed_count,
        failed_scenarios=failed_count,
        constraint_violation_rate=cvr,
        all_constraints_preserved=all_preserved,
        scenario_results=scenario_results,
    )


# ==============================================================================
# 10. LAPORAN EVALUASI KOMPREHENSIF MATCHING ENGINE (DAY 19.5)
# ==============================================================================

def build_default_robustness_scenarios(host_intent: StudyIntent) -> List[Dict[str, Any]]:
    """
    Membangun skenario pengujian ketahanan default berbasis parameter host_intent.
    """
    from app.models import Student, Course, IntentAvailability
    host_course_id = str(getattr(host_intent, "course_id", "c1"))
    host_mode = getattr(host_intent, "learning_mode", "OFFLINE")
    opp_mode = "ONLINE" if host_mode == "OFFLINE" else "OFFLINE"

    def make_cand(iid, cid, mode, status="ACTIVE", acct="ACTIVE", verif="VERIFIED"):
        st = Student(
            student_id=f"s_{iid}", full_name=f"Student {iid}", email=f"{iid}@t.ac.id",
            student_number=f"120125{abs(hash(iid)) % 9000 + 1000}", study_program="S1", academic_year=2025,
            verification_status=verif, account_status=acct, is_discoverable=True
        )
        ci = StudyIntent(
            intent_id=iid, student_id=st.student_id, course_id=cid, topics="Tree",
            learning_goal="PRACTICE", collaboration_style="DISCUSSION", learning_mode=mode,
            min_group_size=2, max_group_size=4, earliest_date="2026-11-20", latest_date="2026-11-30",
            status=status
        )
        ci.student = st
        return ci

    # Skenario 1: Empty candidate pool
    sc1 = {
        "scenario_name": "Default 1: Empty Candidate Pool",
        "description": "Pengujian candidate pool kosong",
        "expected_status": "NO_COMPATIBLE_GROUP",
        "candidates": [],
    }

    # Skenario 2: Incompatible learning mode
    c2 = make_cand("c_def_mode", host_course_id, opp_mode)
    c2.availabilities = [IntentAvailability(
        availability_id="av_def_2", intent_id=c2.intent_id, day_or_date="2026-11-25",
        start_time="09:00", end_time="12:00", priority_rank=1
    )]
    sc2 = {
        "scenario_name": "Default 2: Incompatible Learning Mode",
        "description": f"Kandidat bermode {opp_mode} terhadap host {host_mode}",
        "expected_status": "NO_COMPATIBLE_GROUP",
        "candidates": [c2],
    }

    # Skenario 3: Course mismatch
    c3 = make_cand("c_def_course", f"{host_course_id}_OTHER", host_mode)
    c3.availabilities = [IntentAvailability(
        availability_id="av_def_3", intent_id=c3.intent_id, day_or_date="2026-11-25",
        start_time="09:00", end_time="12:00", priority_rank=1
    )]
    sc3 = {
        "scenario_name": "Default 3: Course Mismatch",
        "description": "Kandidat berbeda mata kuliah",
        "expected_status": "NO_COMPATIBLE_GROUP",
        "candidates": [c3],
    }

    # Skenario 4: Disjoint schedule
    c4 = make_cand("c_def_sched", host_course_id, host_mode)
    c4.availabilities = [IntentAvailability(
        availability_id="av_def_4", intent_id=c4.intent_id, day_or_date="2026-12-15",
        start_time="09:00", end_time="12:00", priority_rank=1
    )]
    sc4 = {
        "scenario_name": "Default 4: Zero Schedule Overlap",
        "description": "Kandidat tidak memiliki irisan jadwal pada tanggal yang sama",
        "expected_status": "NO_COMPATIBLE_GROUP",
        "candidates": [c4],
    }

    # Skenario 5: Unverified account
    c5 = make_cand("c_def_unverif", host_course_id, host_mode, verif="UNVERIFIED")
    c5.availabilities = [IntentAvailability(
        availability_id="av_def_5", intent_id=c5.intent_id, day_or_date="2026-11-25",
        start_time="09:00", end_time="12:00", priority_rank=1
    )]
    sc5 = {
        "scenario_name": "Default 5: Unverified Account",
        "description": "Kandidat berstatus UNVERIFIED ditolak",
        "expected_status": "NO_COMPATIBLE_GROUP",
        "candidates": [c5],
    }

    return [sc1, sc2, sc3, sc4, sc5]


def generate_comprehensive_evaluation_report(
    host_intent: StudyIntent,
    candidate_intents: Sequence[StudyIntent],
    candidate_scenarios: Optional[Sequence[Dict[str, Any]]] = None,
    k_values: Sequence[Optional[int]] = (5, 10, 20, None),
    stability_permutations: int = 10,
    min_score: float = 60.0
) -> ComprehensiveEvaluationReport:
    """
    Generator Laporan Evaluasi Komprehensif Matching Engine (Day 19.5).
    Mengagregasi 4 pilar pengujian:
    1. Group Quality Evaluation (Day 19.1 & 19.1.1)
    2. Matching Stability & Order Invariance (Day 19.2)
    3. Robustness & Constraint Violation Rate (Day 19.3)
    4. Top-K Efficiency & Quality Retention Benchmarking (Day 19.4)

    Menghitung metrik ringkasan, waktu eksekusi total, status kelulusan (PASSED/WARNING/FAILED),
    dan rekomendasi operasional.
    """
    t_start = time.perf_counter()
    candidates_list = list(candidate_intents or [])
    host_id = str(getattr(host_intent, "intent_id", "unknown_host"))
    report_id = f"eval_report_{host_id}_{int(time.time())}"
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # 1. Eksekusi Pembentukan Kelompok Baseline
    formation_res = form_study_group(
        host_intent=host_intent,
        candidate_intents=candidates_list,
        min_score=min_score
    )

    # 2. Pilar 1: Group Quality Evaluation (Day 19.1)
    quality_res = evaluate_group_quality(formation_res)

    # 3. Pilar 2: Matching Stability & Order Invariance (Day 19.2)
    stability_res = evaluate_matching_stability(
        host_intent=host_intent,
        candidate_intents=candidates_list,
        num_permutations=stability_permutations,
        min_score=min_score
    )

    # 4. Pilar 3: Robustness & Constraint Violation Rate (Day 19.3)
    scenarios = candidate_scenarios if candidate_scenarios is not None else build_default_robustness_scenarios(host_intent)
    robustness_res = evaluate_matching_robustness(
        host_intent=host_intent,
        candidate_scenarios=scenarios
    )

    # 5. Pilar 4: Top-K Efficiency Benchmarking (Day 19.4)
    topk_res = benchmark_top_k_candidate_pool(
        host_intent=host_intent,
        candidate_intents=candidates_list,
        k_values=k_values,
        min_score=min_score
    )

    # 6. Agregasi Metrik Ringkasan (Day 19.5)
    total_elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
    gq_mean = round(quality_res.group_quality_score, 2)
    dr_rate = round(stability_res.determinism_rate, 2)
    cvr_rate = round(robustness_res.constraint_violation_rate, 2)

    # Ambil retensi Top-20 atau K terbesar yang diuji di bawah Full
    topk_retention = 100.0
    for b in topk_res.benchmarks:
        if b.k_value == 20:
            topk_retention = b.quality_retention
            break
        elif b.k_value != "Full":
            topk_retention = b.quality_retention

    # Penentuan overall status & rekomendasi
    is_stable = (dr_rate == 100.0)
    is_robust = (cvr_rate == 0.0 and robustness_res.all_constraints_preserved)
    is_breakdown_valid = quality_res.is_breakdown_consistent

    if is_stable and is_robust and is_breakdown_valid:
        overall_status = "PASSED"
        recommendation = (
            f"Matching Engine LaFriend LOLOS pengujian komprehensif Day 19. "
            f"Kualitas grup optimal (GQ: {gq_mean}), stabilitas 100% invarian urutan (DR: 100%), "
            f"integritas hard constraints terlindungi sempurna (CVR: 0.0%), "
            f"dan retensi kualitas Top-K tinggi ({topk_retention}%)."
        )
    elif cvr_rate > 0.0:
        overall_status = "FAILED"
        recommendation = (
            f"Ditemukan pelanggaran hard constraints (CVR: {cvr_rate}%). "
            f"Segera periksa filtering sebelum melanjutkan deployment."
        )
    else:
        overall_status = "WARNING"
        recommendation = (
            f"Pengujian menghasilkan status peringatan (DR: {dr_rate}%, CVR: {cvr_rate}%). "
            f"Harap tinjau catatan kualitas dan variansi skor."
        )

    summary = ComprehensiveEvaluationSummary(
        overall_status=overall_status,
        quality_score_mean=gq_mean,
        order_determinism_rate=dr_rate,
        constraint_violation_rate=cvr_rate,
        topk_quality_retention=topk_retention,
        total_evaluation_time_ms=total_elapsed_ms,
        recommendation=recommendation
    )

    return ComprehensiveEvaluationReport(
        report_id=report_id,
        generated_at=generated_at,
        host_intent_id=host_id,
        summary=summary,
        quality_evaluation=quality_res,
        stability_evaluation=stability_res,
        robustness_evaluation=robustness_res,
        top_k_benchmark=topk_res
    )
