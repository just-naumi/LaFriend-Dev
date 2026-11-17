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
import datetime
import math
import random
import re
import statistics
import time
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, DivisionByZero
from typing import List, Dict, Any, Optional, Sequence, Tuple, Union

from app.group_formation import calculate_group_quality_score, form_study_group
from app.matching import resolve_availability_windows, parse_time_minutes
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
    Aman terhadap elemen None, non-dict, atau non-numerik (D19.6.5-03).
    """
    if not pairwise_scores:
        return None, None

    valid_items = []
    for item in pairwise_scores:
        if isinstance(item, dict):
            raw_cs = item.get("compatibility_score")
            if raw_cs is not None and not isinstance(raw_cs, bool) and isinstance(raw_cs, (int, float, Decimal)):
                try:
                    cs_f = float(raw_cs)
                    if not math.isnan(cs_f) and not math.isinf(cs_f):
                        valid_items.append((cs_f, item))
                except Exception:
                    pass

    if not valid_items:
        return None, None

    valid_items.sort(key=lambda t: t[0])
    weakest_item = valid_items[0][1]
    strongest_item = valid_items[-1][1]

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
# 5. EVALUATOR UTAMA KUALITAS KELOMPOK (DAY 19.1 & DAY 19.6.5)
# ==============================================================================

def evaluate_group_quality(
    data: Union[Dict[str, Any], Sequence[Union[float, int, Decimal]]]
) -> GroupQualityEvaluationResult:
    """
    Fungsi evaluator utama Day 19.1:
    Menerima dictionary hasil form_study_group / preview_group_formation_pipeline,
    atau sekumpulan skor numerik pasangan [CS_1, CS_2, ...].

    Menghasilkan laporan komprehensif GroupQualityEvaluationResult.
    (D19.6.5-01 & D19.6.5-03: Sanitasi payload pairwise & verifikasi skor agregat vs pairwise)
    """
    aggregate_match_valid = True
    aggregate_discrepancy = 0.0
    verified_gq, verified_aps, verified_mps = 0.0, 0.0, 0.0

    if isinstance(data, dict):
        raw_pairwise = data.get("pairwise_scores", [])
        if not isinstance(raw_pairwise, list):
            raw_pairwise = []
            has_malformed_pairwise = True
        else:
            has_malformed_pairwise = False

        valid_pairwise = []
        scores = []
        for item in raw_pairwise:
            if not isinstance(item, dict):
                has_malformed_pairwise = True
                continue
            raw_cs = item.get("compatibility_score")
            if raw_cs is None or isinstance(raw_cs, bool) or not isinstance(raw_cs, (int, float, Decimal)):
                has_malformed_pairwise = True
                continue
            try:
                cs_val = float(raw_cs)
                if math.isnan(cs_val) or math.isinf(cs_val):
                    has_malformed_pairwise = True
                    continue
                scores.append(cs_val)
                valid_pairwise.append(item)
            except (ValueError, TypeError, OverflowError):
                has_malformed_pairwise = True
                continue

        # D19.6.5-03: Periksa konsistensi breakdown untuk setiap item pairwise valid
        breakdown_consistent = not has_malformed_pairwise
        if valid_pairwise:
            for pw in valid_pairwise:
                chk = verify_pairwise_breakdown_consistency(pw)
                if not chk.get("is_consistent", False):
                    breakdown_consistent = False
                    break
        elif raw_pairwise:
            # raw_pairwise tidak kosong tapi seluruh elemennya malformed
            breakdown_consistent = False

        # Jika scores kosong tapi data menyediakan "all_pairwise_scores"
        if not scores and "all_pairwise_scores" in data and isinstance(data["all_pairwise_scores"], list):
            for s in data["all_pairwise_scores"]:
                try:
                    if not isinstance(s, bool) and isinstance(s, (int, float, Decimal)):
                        sf = float(s)
                        if not math.isnan(sf) and not math.isinf(sf):
                            scores.append(sf)
                except Exception:
                    pass

        reported_gq = float(data.get("group_quality_score", 0.0))
        reported_aps = float(data.get("average_pair_score", 0.0))
        reported_mps = float(data.get("minimum_pair_score", 0.0))
        group_size = int(data.get("group_size", len(data.get("members", []))))

        # Hitung skor terverifikasi dari pairwise_scores yang ada
        if scores:
            verified_gq, verified_aps, verified_mps = calculate_group_quality_score(scores)

        # Jika data tidak melaporkan skor agregat (semua 0.0), gunakan hasil perhitungan
        has_reported_aggregates = not (reported_gq == 0.0 and reported_aps == 0.0 and reported_mps == 0.0)
        if not has_reported_aggregates and scores:
            gq, aps, mps = verified_gq, verified_aps, verified_mps
        else:
            gq, aps, mps = reported_gq, reported_aps, reported_mps

        # D19.6.5-01: Verifikasi kecocokan skor agregat yang dilaporkan vs skor terverifikasi dari pairwise
        if scores and has_reported_aggregates:
            disc_gq = abs(round(reported_gq, 2) - round(verified_gq, 2))
            disc_aps = abs(round(reported_aps, 2) - round(verified_aps, 2))
            disc_mps = abs(round(reported_mps, 2) - round(verified_mps, 2))
            aggregate_discrepancy = max(disc_gq, disc_aps, disc_mps)
            if aggregate_discrepancy > 0.01:
                aggregate_match_valid = False

        weakest_link, strongest_link = identify_weakest_and_strongest_links(valid_pairwise)
    else:
        scores = [float(s) for s in data]
        gq, aps, mps = calculate_group_quality_score(scores)
        verified_gq, verified_aps, verified_mps = gq, aps, mps
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

    # D19.6.5-01: Jika terjadi ketidakcocokan skor agregat vs skor pairwise, tandai formula_check tidak valid
    if not aggregate_match_valid:
        formula_check.is_valid = False
        formula_check.discrepancy = max(formula_check.discrepancy, round(aggregate_discrepancy, 4))
        formula_check.formula_expression += f" [MISMATCH WITH PAIRWISE: Expected GQ={verified_gq:.2f}, APS={verified_aps:.2f}, MPS={verified_mps:.2f}]"

    tier = determine_quality_tier(gq)
    notes = generate_quality_notes(gq, aps, mps, distribution, weakest_link)
    if not aggregate_match_valid:
        notes.append(
            f"PERINGATAN INTEGRITAS: Skor agregat yang dilaporkan (GQ={gq:.2f}, APS={aps:.2f}, MPS={mps:.2f}) "
            f"tidak konsisten dengan skor pairwise aktual (GQ={verified_gq:.2f}, APS={verified_aps:.2f}, MPS={verified_mps:.2f})."
        )

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

        # Hitung Quality Retention & Quality Loss (D19.6.5-04)
        # Jika full_gq <= 0.0 (misal kelompok tidak terbentuk), retention & loss adalah None
        if full_gq > 0.0:
            retention = min(100.0, max(0.0, round((gq / full_gq) * 100.0, 2)))
            loss = min(100.0, max(0.0, round(((full_gq - gq) / full_gq) * 100.0, 2)))
        else:
            retention = None
            loss = None

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

VALID_LEARNING_MODES = {"ONLINE", "OFFLINE", "HYBRID"}


def check_hard_constraint_violations(
    host_intent: StudyIntent,
    formation_result: Dict[str, Any],
    candidate_lookup: Optional[Dict[str, StudyIntent]] = None,
    min_score: float = 60.0
) -> List[str]:
    """
    Memeriksa secara independen apakah hasil pembentukan kelompok melanggar
    satu pun aturan Hard Constraints dari Day 14 atau aturan multi-way Day 17/18.
    (Day 19.6.4 Closed Independent Evaluator Specification)

    Empat Kelompok Pemeriksaan Utama:
    1. Formation Integrity:
       - Parameter min_score tervalidasi numerik, berhingga, dan dalam rentang [0.0, 100.0].
       - group_size, min_bound, max_bound wajib integer murni (bukan float, string, bool).
       - host_intent_id pada metadata cocok dengan host_intent.
       - Host wajib terdapat dalam members tepat satu kali.
       - Tidak ada anggota duplikat dan setiap anggota memiliki intent_id valid.
       - READY: 2 <= group_size, min_bound <= group_size <= max_bound, min_bound <= max_bound.
       - INSUFFICIENT_MEMBERS: 2 <= group_size < min_bound (bukan violation!).
       - NO_COMPATIBLE_GROUP: group_size == 1 (jika group_size >= 2 maka violation!).
       - Unknown status: ditandai sebagai hasil tidak valid.
       - Konsistensi jumlah elemen members == group_size.
    2. Candidate & Host Integrity:
       - Host intent: status == ACTIVE, domain learning_mode valid (ONLINE/OFFLINE/HYBRID),
         profil student tersedia, account_status == ACTIVE, verification_status == VERIFIED,
         is_discoverable == True.
       - Jika ada anggota non-host, candidate_lookup WAJIB disediakan. Jika tidak, catat violation.
       - Setiap anggota non-host: wajib ada di candidate_lookup, mapping key == intent_id,
         status intent == ACTIVE, domain learning_mode valid, course_id sama dengan host,
         profil student tersedia, akun ACTIVE, VERIFIED, is_discoverable.
       - Deduplikasi mahasiswa: tidak ada student_id ganda.
       - Transitive Learning Mode: tidak ada kombinasi ONLINE dan OFFLINE sekaligus.
       - Perhitungan ulang independen rentang kapasitas [MinGroup, MaxGroup] dari objek intent anggota.
    3. Pairwise Integrity (khusus status READY):
       - Jumlah pairwise_scores wajib tepat N*(N-1)/2.
       - Himpunan pasangan aktual wajib identik dengan himpunan seluruh pasangan kombinasi anggota (A, B).
       - Tidak boleh ada pasangan duplikat, pasangan hilang, atau pasangan asing.
       - Nilai compatibility_score wajib numerik, finite, non-boolean, berada dalam rentang [0.0, 100.0],
         dan >= min_score.
    4. Schedule Integrity (khusus status READY):
       - selected_schedule wajib ada dan berupa dictionary.
       - Field date, start_time, end_time, dan duration_minutes wajib lengkap dan valid.
       - Format date YYYY-MM-DD dan kalender riil valid.
       - Format waktu HH:MM, durasi selisih >= 60 menit.
       - Field duration_minutes wajib numerik integer berhingga (tahan NaN/Inf/Decimal Infinity)
         dan tepat sama dengan selisih waktu.
       - Seluruh anggota kelompok (host + kandidat) wajib memiliki jendela ketersediaan
         yang mencakup jadwal terpilih (fail-closed resolver exception handling).
    """
    violations = []

    # =========================================================================
    # 0. VALIDASI PARAMETER INPUT (D19.6.4-05 & D19.6.4-06)
    # =========================================================================
    min_score_val = 60.0
    if min_score is None or isinstance(min_score, bool) or not isinstance(min_score, (int, float, Decimal)):
        violations.append(f"Parameter min_score ({min_score}) tidak valid: harus numerik berhingga antara 0.0 dan 100.0")
    else:
        try:
            val_f = float(min_score)
            if math.isnan(val_f) or math.isinf(val_f):
                violations.append(f"Parameter min_score ({min_score}) tidak valid: harus numerik berhingga antara 0.0 dan 100.0")
            elif val_f < 0.0 or val_f > 100.0:
                violations.append(f"Parameter min_score ({min_score}) tidak valid: harus numerik berhingga antara 0.0 dan 100.0")
            else:
                min_score_val = val_f
        except (ValueError, TypeError, OverflowError):
            violations.append(f"Parameter min_score ({min_score}) tidak valid: gagal dikonversi ke numerik")

    # =========================================================================
    # 1. FORMATION INTEGRITY & STRICT INTEGER VALIDATION (D19.6.4-01 & D19.6.4-03)
    # =========================================================================
    status = formation_result.get("formation_status", "UNKNOWN")
    raw_group_size = formation_result.get("group_size")
    if raw_group_size is None or isinstance(raw_group_size, bool) or not isinstance(raw_group_size, int):
        violations.append(f"Field group_size ({raw_group_size}) harus berupa integer numerik murni (bukan float, string, atau boolean)")
        try:
            group_size = int(raw_group_size) if (raw_group_size is not None and not isinstance(raw_group_size, bool)) else 0
        except (ValueError, TypeError):
            group_size = 0
    else:
        group_size = raw_group_size

    raw_min_bound = formation_result.get("min_group_size_bound")
    if raw_min_bound is not None:
        if isinstance(raw_min_bound, bool) or not isinstance(raw_min_bound, int):
            violations.append(f"Field min_group_size_bound ({raw_min_bound}) harus berupa integer numerik murni")
            try:
                reported_min_bound = int(raw_min_bound) if not isinstance(raw_min_bound, bool) else 2
            except (ValueError, TypeError):
                reported_min_bound = 2
        else:
            reported_min_bound = raw_min_bound
    else:
        reported_min_bound = None

    raw_max_bound = formation_result.get("max_group_size_bound")
    if raw_max_bound is not None:
        if isinstance(raw_max_bound, bool) or not isinstance(raw_max_bound, int):
            violations.append(f"Field max_group_size_bound ({raw_max_bound}) harus berupa integer numerik murni")
            try:
                reported_max_bound = int(raw_max_bound) if not isinstance(raw_max_bound, bool) else 10
            except (ValueError, TypeError):
                reported_max_bound = 10
        else:
            reported_max_bound = raw_max_bound
    else:
        reported_max_bound = None

    members = formation_result.get("members", [])
    if not isinstance(members, list):
        violations.append(f"Field members ({members}) harus berupa list")
        members = []
    selected_sched = formation_result.get("selected_schedule")

    if len(members) != group_size:
        violations.append(f"Jumlah anggota aktual ({len(members)}) tidak sesuai dengan group_size ({group_size})")

    # D19.6.4-01: Validasi host_intent_id pada formation_result
    host_id = str(getattr(host_intent, "intent_id", "host")).strip()
    reported_host_id = formation_result.get("host_intent_id")
    if reported_host_id is not None:
        if str(reported_host_id).strip() != host_id:
            violations.append(f"host_intent_id pada formation_result ('{reported_host_id}') tidak cocok dengan host_intent ('{host_id}')")

    # D19.6.4-01: Validasi kelengkapan, keunikan anggota, dan kehadiran host
    member_id_list = []
    for idx, m in enumerate(members):
        if isinstance(m, dict):
            mid = str(m.get("intent_id", "")).strip()
        else:
            mid = str(getattr(m, "intent_id", "")).strip()
        if not mid:
            violations.append(f"Anggota pada index {idx} tidak memiliki intent_id yang valid")
        else:
            member_id_list.append(mid)

    if len(member_id_list) != len(set(member_id_list)):
        violations.append("Terdapat duplikasi anggota (intent_id ganda) pada members")

    host_count = member_id_list.count(host_id)
    if host_count == 0:
        violations.append(f"Host {host_id} tidak terdapat dalam daftar members")
    elif host_count > 1:
        violations.append(f"Host {host_id} muncul lebih dari satu kali dalam daftar members ({host_count} kali)")

    # =========================================================================
    # 2. CANDIDATE & HOST INTEGRITY (D19.6.4-02 & D19.6.4-04)
    # =========================================================================
    all_member_intents: List[StudyIntent] = []
    student_ids: List[str] = []
    modes: List[str] = []

    # 2.A. Validasi Host
    if getattr(host_intent, "status", None) != "ACTIVE":
        violations.append(f"Host {host_id} memiliki status intent tidak aktif ('{getattr(host_intent, 'status', None)}')")

    host_mode = getattr(host_intent, "learning_mode", None)
    if host_mode not in VALID_LEARNING_MODES:
        violations.append(f"Host {host_id} memiliki learning_mode tidak valid: '{host_mode}' (wajib salah satu dari ONLINE, OFFLINE, HYBRID)")
    else:
        modes.append(host_mode)

    host_st = getattr(host_intent, "student", None)
    if host_st is None:
        violations.append(f"Data profil mahasiswa untuk host {host_id} tidak tersedia")
    else:
        if (getattr(host_st, "account_status", None) or "").upper() != "ACTIVE":
            violations.append(f"Host {host_id} memiliki akun mahasiswa tidak aktif ('{getattr(host_st, 'account_status', None)}')")
        if (getattr(host_st, "verification_status", None) or "").upper() != "VERIFIED":
            violations.append(f"Host {host_id} belum terverifikasi ('{getattr(host_st, 'verification_status', None)}')")
        if getattr(host_st, "is_discoverable", None) is not True:
            violations.append(f"Host {host_id} tidak discoverable (is_discoverable={getattr(host_st, 'is_discoverable', None)})")
        student_ids.append(str(host_st.student_id))

    all_member_intents.append(host_intent)

    # 2.B. Validasi Anggota Non-Host
    non_host_members = [mid for mid in member_id_list if mid != host_id]
    if non_host_members:
        if candidate_lookup is None:
            violations.append(f"candidate_lookup wajib disediakan untuk memverifikasi integritas {len(non_host_members)} anggota kandidat non-host")
        else:
            for mid in non_host_members:
                if mid not in candidate_lookup:
                    violations.append(f"Anggota {mid} tidak ditemukan pada candidate_lookup sehingga tidak dapat diverifikasi")
                    continue

                cand_intent = candidate_lookup[mid]
                cand_iid = str(getattr(cand_intent, "intent_id", "")).strip()
                if cand_iid != mid:
                    violations.append(f"Integritas candidate_lookup gagal: key '{mid}' memetakan ke objek dengan intent_id berbeda ('{cand_iid}')")
                    continue

                all_member_intents.append(cand_intent)

                if getattr(cand_intent, "status", None) != "ACTIVE":
                    violations.append(f"Anggota {mid} memiliki status intent tidak aktif ('{getattr(cand_intent, 'status', None)}')")

                cand_mode = getattr(cand_intent, "learning_mode", None)
                if cand_mode not in VALID_LEARNING_MODES:
                    violations.append(f"Anggota {mid} memiliki learning_mode tidak valid: '{cand_mode}' (wajib salah satu dari ONLINE, OFFLINE, HYBRID)")
                else:
                    modes.append(cand_mode)

                if str(cand_intent.course_id) != str(host_intent.course_id):
                    violations.append(f"Anggota {mid} memiliki course_id berbeda ({cand_intent.course_id} != {host_intent.course_id})")

                st = getattr(cand_intent, "student", None)
                if st is None:
                    violations.append(f"Data profil mahasiswa untuk intent {mid} tidak tersedia")
                else:
                    if (getattr(st, "account_status", None) or "").upper() != "ACTIVE":
                        violations.append(f"Anggota {mid} memiliki akun mahasiswa tidak aktif ({getattr(st, 'account_status', None)})")
                    if (getattr(st, "verification_status", None) or "").upper() != "VERIFIED":
                        violations.append(f"Anggota {mid} belum terverifikasi ({getattr(st, 'verification_status', None)})")
                    if getattr(st, "is_discoverable", None) is not True:
                        violations.append(f"Anggota {mid} tidak discoverable (is_discoverable={getattr(st, 'is_discoverable', None)})")
                    student_ids.append(str(st.student_id))

    # Deduplikasi mahasiswa
    if len(student_ids) != len(set(student_ids)):
        violations.append("Terdapat duplikasi mahasiswa (student_id sama) dalam kelompok yang sama")

    # Mode transitivity
    if "ONLINE" in modes and "OFFLINE" in modes:
        violations.append("Kelompok memuat mahasiswa ONLINE dan OFFLINE sekaligus (inkompatibel)")

    # 2.C. Perhitungan Ulang Independen Batas Kapasitas (D19.6.5-02)
    has_capacity_calc_error = False
    intent_min_bounds = []
    intent_max_bounds = []

    for mem_intent in all_member_intents:
        mem_iid = str(getattr(mem_intent, "intent_id", "?")).strip()
        raw_min = getattr(mem_intent, "min_group_size", None)
        raw_max = getattr(mem_intent, "max_group_size", None)

        # Strict integer check: tolak float (e.g. 2.9), string (e.g. "2"), None, bool (e.g. True)
        if raw_min is None or isinstance(raw_min, bool) or not isinstance(raw_min, int):
            violations.append(f"Intent {mem_iid} memiliki min_group_size ({raw_min}) yang tidak valid (wajib integer murni)")
            has_capacity_calc_error = True
        elif raw_min < 2:
            violations.append(f"Intent {mem_iid} memiliki min_group_size ({raw_min}) < 2 (batas minimum absolut)")
            has_capacity_calc_error = True
        else:
            intent_min_bounds.append(raw_min)

        if raw_max is None or isinstance(raw_max, bool) or not isinstance(raw_max, int):
            violations.append(f"Intent {mem_iid} memiliki max_group_size ({raw_max}) yang tidak valid (wajib integer murni)")
            has_capacity_calc_error = True
        elif isinstance(raw_min, int) and not isinstance(raw_min, bool) and raw_max < raw_min:
            violations.append(f"Intent {mem_iid} memiliki rentang kapasitas tidak valid: min_group_size ({raw_min}) > max_group_size ({raw_max})")
            has_capacity_calc_error = True
        else:
            intent_max_bounds.append(raw_max)

    if not has_capacity_calc_error and intent_min_bounds and intent_max_bounds:
        recomputed_min_bound = max(intent_min_bounds)
        recomputed_max_bound = min(intent_max_bounds)
    else:
        # PENTING (D19.6.5-02): ELIMINASI DEFAULT FALLBACK KE [2, 10]
        recomputed_min_bound = None
        recomputed_max_bound = None
        if "Kapasitas anggota tidak valid sehingga rentang kapasitas kelompok tidak dapat dihitung" not in violations:
            violations.append("Kapasitas anggota tidak valid sehingga rentang kapasitas kelompok tidak dapat dihitung")

    if recomputed_min_bound is not None and recomputed_max_bound is not None:
        if reported_min_bound is not None and reported_min_bound != recomputed_min_bound:
            violations.append(f"Metadata min_group_size_bound ({reported_min_bound}) tidak cocok dengan hasil perhitungan independen ({recomputed_min_bound})")
        if reported_max_bound is not None and reported_max_bound != recomputed_max_bound:
            violations.append(f"Metadata max_group_size_bound ({reported_max_bound}) tidak cocok dengan hasil perhitungan independen ({recomputed_max_bound})")

        # Validasi kapasitas kelompok berdasarkan status (baik reported maupun recomputed)
        if reported_min_bound is not None and reported_max_bound is not None and reported_min_bound > reported_max_bound:
            violations.append(f"Kelompok READY memiliki rentang kapasitas tidak valid: min_bound ({reported_min_bound}) > max_bound ({reported_max_bound})")
        elif recomputed_min_bound > recomputed_max_bound:
            violations.append(f"Kelompok READY memiliki rentang kapasitas tidak valid: min_bound ({recomputed_min_bound}) > max_bound ({recomputed_max_bound})")

        if status == "READY":
            if group_size < 2:
                violations.append(f"Ukuran kelompok READY ({group_size}) kurang dari batas minimum absolut (2)")
            if reported_min_bound is not None and reported_max_bound is not None and (group_size < reported_min_bound or group_size > reported_max_bound):
                violations.append(f"Kelompok READY memiliki group_size ({group_size}) di luar batas kapasitas [{reported_min_bound}, {reported_max_bound}]")
            elif group_size < recomputed_min_bound or group_size > recomputed_max_bound:
                violations.append(f"Kelompok READY memiliki group_size ({group_size}) di luar batas kapasitas [{recomputed_min_bound}, {recomputed_max_bound}]")
            if not selected_sched:
                violations.append("Kelompok berstatus READY tetapi tidak memiliki selected_schedule")
        elif status == "INSUFFICIENT_MEMBERS":
            if group_size < 2:
                violations.append(f"Status INSUFFICIENT_MEMBERS tetapi group_size ({group_size}) < 2")
            effective_min = recomputed_min_bound if reported_min_bound is None else min(reported_min_bound, recomputed_min_bound)
            if group_size >= effective_min:
                violations.append(f"Status INSUFFICIENT_MEMBERS tetapi group_size ({group_size}) >= min_bound ({effective_min})")
        elif status == "NO_COMPATIBLE_GROUP":
            if group_size != 1:
                violations.append(f"Status NO_COMPATIBLE_GROUP tetapi group_size ({group_size}) != 1")
        else:
            violations.append(f"Status pembentukan kelompok tidak dikenal atau tidak valid: '{status}'")
    else:
        # Kapasitas tidak dapat dihitung secara valid
        if status == "READY":
            violations.append("Kelompok READY tidak dapat memverifikasi batas kapasitas karena ada data kapasitas intent anggota yang tidak valid")
            if not selected_sched:
                violations.append("Kelompok berstatus READY tetapi tidak memiliki selected_schedule")
        elif status == "INSUFFICIENT_MEMBERS":
            violations.append("Kelompok INSUFFICIENT_MEMBERS tidak dapat memverifikasi batas kapasitas karena ada data kapasitas intent anggota yang tidak valid")
        elif status == "NO_COMPATIBLE_GROUP":
            if group_size != 1:
                violations.append(f"Status NO_COMPATIBLE_GROUP tetapi group_size ({group_size}) != 1")
        else:
            violations.append(f"Status pembentukan kelompok tidak dikenal atau tidak valid: '{status}'")

    # =========================================================================
    # 3. PAIRWISE INTEGRITY (Khusus Status READY - D19.6.4-05)
    # =========================================================================
    if status == "READY":
        expected_pairs = set()
        for i in range(len(member_id_list)):
            for j in range(i + 1, len(member_id_list)):
                if member_id_list[i] and member_id_list[j]:
                    expected_pairs.add(tuple(sorted([member_id_list[i], member_id_list[j]])))

        n = group_size
        expected_n_pairs = (n * (n - 1)) // 2
        pairwise_scores = formation_result.get("pairwise_scores", [])
        if not isinstance(pairwise_scores, list):
            violations.append(f"Field pairwise_scores ({pairwise_scores}) harus berupa list")
            pairwise_scores = []

        if len(pairwise_scores) != expected_n_pairs:
            violations.append(f"Jumlah pairwise_scores ({len(pairwise_scores)}) tidak sesuai dengan formula N*(N-1)/2 ({expected_n_pairs}) untuk n={n}")

        seen_pairs = set()
        valid_cs_list = []

        for pw in pairwise_scores:
            if not isinstance(pw, dict):
                violations.append("Elemen pairwise_scores bukan merupakan dictionary")
                continue

            id_a = str(pw.get("intent_a_id", "")).strip()
            id_b = str(pw.get("intent_b_id", "")).strip()

            if not id_a or not id_b:
                violations.append(f"Pairwise item tidak memiliki intent_a_id atau intent_b_id yang valid: {pw}")
                continue
            if id_a == id_b:
                violations.append(f"Pairwise item menghubungkan intent yang sama ({id_a} == {id_b})")
                continue

            pair_key = tuple(sorted([id_a, id_b]))
            if pair_key in seen_pairs:
                violations.append(f"Ditemukan pasangan duplikat pada pairwise_scores: {pair_key}")
            seen_pairs.add(pair_key)

            # Validasi numerik dan finiteness skor
            raw_cs = pw.get("compatibility_score")
            if raw_cs is None or isinstance(raw_cs, bool) or not isinstance(raw_cs, (int, float, Decimal)):
                violations.append(f"Compatibility score untuk pasangan {pair_key} tidak bernilai numerik valid: {raw_cs}")
                continue

            try:
                cs_float = float(raw_cs)
                if math.isnan(cs_float) or math.isinf(cs_float):
                    violations.append(f"Compatibility score untuk pasangan {pair_key} bernilai NaN atau Inf")
                    continue
            except (ValueError, TypeError, OverflowError):
                violations.append(f"Compatibility score untuk pasangan {pair_key} gagal dikonversi ke float")
                continue

            if cs_float < 0.0 or cs_float > 100.0:
                violations.append(f"Compatibility score untuk pasangan {pair_key} ({cs_float}) di luar rentang valid [0.0, 100.0]")

            if cs_float < min_score_val:
                violations.append(f"Pasangan ({id_a} - {id_b}) memiliki Compatibility Score ({cs_float}) < min_score ({min_score_val})")

            valid_cs_list.append(cs_float)

        # Cek pasangan yang hilang dan pasangan asing
        missing_pairs = expected_pairs - seen_pairs
        if missing_pairs:
            violations.append(f"Terdapat pasangan yang hilang pada pairwise_scores: {sorted(list(missing_pairs))}")

        extraneous_pairs = seen_pairs - expected_pairs
        if extraneous_pairs:
            violations.append(f"Terdapat pasangan asing pada pairwise_scores yang bukan anggota kelompok: {sorted(list(extraneous_pairs))}")

        # D19.6.5-01: Verifikasi skor agregat yang dilaporkan (group_quality_score, average_pair_score, minimum_pair_score)
        # terhadap hasil perhitungan aktual dari pairwise_scores
        if len(valid_cs_list) == expected_n_pairs and expected_n_pairs > 0:
            calc_gq, calc_aps, calc_mps = calculate_group_quality_score(valid_cs_list)

            rep_gq = formation_result.get("group_quality_score")
            if rep_gq is not None and not isinstance(rep_gq, bool) and isinstance(rep_gq, (int, float, Decimal)):
                try:
                    rep_gq_f = float(rep_gq)
                    if abs(round(rep_gq_f, 2) - round(calc_gq, 2)) > 0.01:
                        violations.append(f"group_quality_score yang dilaporkan ({rep_gq_f}) tidak cocok dengan hasil perhitungan skor pairwise ({calc_gq})")
                except Exception:
                    pass

            rep_aps = formation_result.get("average_pair_score")
            if rep_aps is not None and not isinstance(rep_aps, bool) and isinstance(rep_aps, (int, float, Decimal)):
                try:
                    rep_aps_f = float(rep_aps)
                    if abs(round(rep_aps_f, 2) - round(calc_aps, 2)) > 0.01:
                        violations.append(f"average_pair_score yang dilaporkan ({rep_aps_f}) tidak cocok dengan rata-rata skor pairwise ({calc_aps})")
                except Exception:
                    pass

            rep_mps = formation_result.get("minimum_pair_score")
            if rep_mps is not None and not isinstance(rep_mps, bool) and isinstance(rep_mps, (int, float, Decimal)):
                try:
                    rep_mps_f = float(rep_mps)
                    if abs(round(rep_mps_f, 2) - round(calc_mps, 2)) > 0.01:
                        violations.append(f"minimum_pair_score yang dilaporkan ({rep_mps_f}) tidak cocok dengan skor minimum pairwise ({calc_mps})")
                except Exception:
                    pass

    # =========================================================================
    # 4. SCHEDULE INTEGRITY (Khusus Status READY - D19.6.4-06 & D19.6.4-07)
    # =========================================================================
    if status == "READY":
        if not selected_sched or not isinstance(selected_sched, dict):
            if "Kelompok berstatus READY tetapi tidak memiliki selected_schedule" not in violations:
                violations.append("Kelompok berstatus READY tetapi selected_schedule tidak valid atau bukan dictionary")
        else:
            sched_date = str(selected_sched.get("date", "")).strip()
            sched_start_str = str(selected_sched.get("start_time", "")).strip()
            sched_end_str = str(selected_sched.get("end_time", "")).strip()
            raw_dur = selected_sched.get("duration_minutes")

            # Validasi keberadaan field wajib
            for req_f in ("date", "start_time", "end_time", "duration_minutes"):
                if selected_sched.get(req_f) is None or str(selected_sched.get(req_f)).strip() == "":
                    violations.append(f"Field jadwal '{req_f}' pada selected_schedule tidak boleh kosong")

            # Validasi format tanggal YYYY-MM-DD dan kalender riil
            is_calendar_date_valid = False
            if sched_date:
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", sched_date):
                    violations.append(f"Format tanggal selected_schedule '{sched_date}' tidak valid (wajib YYYY-MM-DD)")
                else:
                    try:
                        datetime.date.fromisoformat(sched_date)
                        is_calendar_date_valid = True
                    except ValueError:
                        violations.append(f"Tanggal selected_schedule '{sched_date}' bukan tanggal kalender yang valid")

            # Validasi durasi yang dilaporkan (D19.6.4-07: penanganan Decimal infinity & non-finite)
            reported_dur = None
            if raw_dur is not None:
                if isinstance(raw_dur, bool) or not isinstance(raw_dur, (int, float, Decimal)):
                    violations.append(f"Field duration_minutes ({raw_dur}) harus numerik valid")
                elif isinstance(raw_dur, float):
                    if math.isnan(raw_dur) or math.isinf(raw_dur):
                        violations.append(f"Field duration_minutes ({raw_dur}) bernilai non-finite / NaN / Inf")
                    elif not raw_dur.is_integer():
                        violations.append(f"Field duration_minutes ({raw_dur}) harus berupa bilangan bulat integer, bukan desimal pecahan")
                    else:
                        reported_dur = int(raw_dur)
                elif isinstance(raw_dur, Decimal):
                    if not raw_dur.is_finite() or raw_dur.is_nan():
                        violations.append(f"Field duration_minutes ({raw_dur}) bernilai non-finite / NaN / Inf")
                    else:
                        try:
                            if raw_dur % 1 != 0:
                                violations.append(f"Field duration_minutes ({raw_dur}) harus berupa bilangan bulat integer, bukan desimal pecahan")
                            else:
                                reported_dur = int(raw_dur)
                        except (InvalidOperation, DivisionByZero):
                            violations.append(f"Field duration_minutes ({raw_dur}) menghasilkan operasi Decimal tidak valid")
                else:
                    try:
                        reported_dur = int(raw_dur)
                    except (ValueError, TypeError):
                        violations.append(f"Field duration_minutes ({raw_dur}) gagal dikonversi ke integer")

            if reported_dur is not None and reported_dur < 60:
                violations.append(f"Durasi selected_schedule ({reported_dur}m) kurang dari 60 menit")

            # Validasi waktu mulai dan selesai
            s_min, e_min = None, None
            if sched_start_str and sched_end_str:
                try:
                    s_min = parse_time_minutes(sched_start_str)
                    e_min = parse_time_minutes(sched_end_str)
                    if e_min <= s_min:
                        violations.append(f"Waktu selesai ({sched_end_str}) harus lebih besar dari waktu mulai ({sched_start_str})")
                    else:
                        dur = e_min - s_min
                        if dur < 60 and f"Durasi selected_schedule ({dur}m) kurang dari 60 menit" not in violations:
                            violations.append(f"Durasi selected_schedule ({dur}m) kurang dari 60 menit")
                        if reported_dur is not None and reported_dur != dur and reported_dur >= 60:
                            violations.append(f"Field duration_minutes ({reported_dur}m) tidak sesuai selisih waktu ({dur}m)")
                except Exception as ve:
                    violations.append(f"Format waktu selected_schedule tidak valid: {ve}")

            # Verifikasi independen ketersediaan jadwal seluruh anggota (D19.6.4-06: fail-closed resolver exception handling)
            if s_min is not None and e_min is not None and is_calendar_date_valid:
                for member_intent in all_member_intents:
                    mem_id = getattr(member_intent, "intent_id", "?")
                    avs = getattr(member_intent, "availabilities", None)
                    if avs is None or not isinstance(avs, list) or any(a is None for a in avs):
                        violations.append(f"Ketersediaan anggota {mem_id} tidak valid atau memuat nilai None")
                        continue
                    try:
                        mem_windows = resolve_availability_windows(member_intent)
                    except Exception as exc:
                        violations.append(f"Ketersediaan anggota {mem_id} tidak dapat diverifikasi karena error pada resolver: {str(exc)}")
                        continue

                    mem_covers = False
                    for w in mem_windows:
                        if str(w.get("date", "")) == sched_date:
                            try:
                                w_start = parse_time_minutes(str(w.get("start_time", "00:00")))
                                w_end = parse_time_minutes(str(w.get("end_time", "00:00")))
                                if w_start <= s_min and w_end >= e_min:
                                    mem_covers = True
                                    break
                            except Exception:
                                continue
                    if not mem_covers:
                        violations.append(f"Selected schedule ({sched_date} {sched_start_str}-{sched_end_str}) tidak tercakup dalam ketersediaan anggota {mem_id}")
            else:
                violations.append("Jadwal selected_schedule tidak lengkap atau tidak valid sehingga tidak dapat diverifikasi terhadap ketersediaan anggota kelompok")

    return violations

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
            violations = check_hard_constraint_violations(host_intent, res, cand_lookup, min_score=min_score)
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
    all_preserved = (total_tested > 0 and cvr == 0.0 and passed_count == total_tested)

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
    formation_res = None
    baseline_violations = []
    try:
        formation_res = form_study_group(
            host_intent=host_intent,
            candidate_intents=candidates_list,
            min_score=min_score
        )
    except Exception as exc:
        baseline_violations.append(f"Eksekusi form_study_group gagal dengan exception: {str(exc)}")
        formation_res = {
            "formation_status": "FAILED",
            "host_intent_id": host_id,
            "members": [host_intent],
            "group_size": 1,
            "pairwise_scores": [],
        }

    if not isinstance(formation_res, dict):
        baseline_violations.append(f"form_study_group menghasilkan tipe data tidak valid: {type(formation_res)}")
        formation_res = {
            "formation_status": "FAILED",
            "host_intent_id": host_id,
            "members": [host_intent],
            "group_size": 1,
            "pairwise_scores": [],
        }

    # 1.B. Verifikasi Integritas Baseline Formation (D19.6.4-08 & D19.6.5-03)
    cand_lookup = {}
    for c in candidates_list:
        try:
            cid = str(getattr(c, "intent_id", "")).strip()
            if cid:
                cand_lookup[cid] = c
        except Exception:
            pass
    cand_lookup[host_id] = host_intent

    try:
        v_list = check_hard_constraint_violations(
            host_intent=host_intent,
            formation_result=formation_res,
            candidate_lookup=cand_lookup,
            min_score=min_score
        )
        baseline_violations.extend(v_list)
    except Exception as exc:
        baseline_violations.append(f"Pemeriksaan check_hard_constraint_violations gagal dengan exception: {str(exc)}")

    has_baseline_violations = (len(baseline_violations) > 0)

    # 2. Pilar 1: Group Quality Evaluation (Day 19.1)
    try:
        quality_res = evaluate_group_quality(formation_res)
    except Exception as exc:
        quality_res = GroupQualityEvaluationResult(
            group_quality_score=0.0,
            average_pair_score=0.0,
            minimum_pair_score=0.0,
            maximum_pair_score=0.0,
            distribution=calculate_pairwise_distribution([]),
            weakest_link=None,
            strongest_link=None,
            formula_consistency=FormulaConsistencyCheck(
                is_valid=False,
                expected_gq=0.0,
                actual_gq=0.0,
                discrepancy=0.0,
                formula_expression=f"ERROR: {str(exc)}",
                aps=0.0,
                mps=0.0
            ),
            all_pairwise_scores=[],
            quality_tier="NEEDS_IMPROVEMENT",
            evaluation_notes=[f"Evaluasi kualitas gagal dengan exception: {str(exc)}"],
            group_size=0,
            is_breakdown_consistent=False
        )

    # 3. Pilar 2: Matching Stability & Order Invariance (Day 19.2)
    try:
        stability_res = evaluate_matching_stability(
            host_intent=host_intent,
            candidate_intents=candidates_list,
            num_permutations=stability_permutations,
            min_score=min_score
        )
    except Exception as exc:
        stability_res = MatchingStabilityResult(
            num_permutations=stability_permutations,
            is_order_invariant=False,
            determinism_rate=0.0,
            distinct_group_signatures=0,
            baseline_signature="ERROR",
            permutations=[]
        )

    # 4. Pilar 3: Robustness & Constraint Violation Rate (Day 19.3)
    try:
        scenarios = candidate_scenarios if candidate_scenarios is not None else build_default_robustness_scenarios(host_intent)
        robustness_res = evaluate_matching_robustness(
            host_intent=host_intent,
            candidate_scenarios=scenarios
        )
    except Exception as exc:
        robustness_res = RobustnessEvaluationResult(
            total_scenarios_tested=0,
            passed_scenarios=0,
            failed_scenarios=0,
            constraint_violation_rate=100.0,
            all_constraints_preserved=False,
            scenario_results=[]
        )

    # 5. Pilar 4: Top-K Efficiency Benchmarking (Day 19.4)
    try:
        topk_res = benchmark_top_k_candidate_pool(
            host_intent=host_intent,
            candidate_intents=candidates_list,
            k_values=k_values,
            min_score=min_score
        )
    except Exception as exc:
        topk_res = TopKBenchmarkResult(
            total_candidates=len(candidates_list),
            baseline_k="Full",
            benchmarks=[]
        )

    # 6. Agregasi Metrik Ringkasan (Day 19.5 & Day 19.6.1)
    total_elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
    gq_val = round(quality_res.group_quality_score, 2)
    aps_val = round(quality_res.average_pair_score, 2)
    dr_rate = round(stability_res.determinism_rate, 2)
    cvr_rate = round(robustness_res.constraint_violation_rate, 2)

    # Ambil retensi Top-K secara konsisten (Day 19.6.1 s/d Day 19.6.4):
    baseline_status = formation_res.get("formation_status", "UNKNOWN")
    is_ready = (baseline_status == "READY")

    topk_retention: Optional[float] = None
    if is_ready and gq_val > 0.0:
        numeric_benchmarks = []
        for b in topk_res.benchmarks:
            if isinstance(b.k_value, int):
                numeric_benchmarks.append((b.k_value, b.quality_retention))
            elif isinstance(b.k_value, str) and b.k_value.isdigit():
                numeric_benchmarks.append((int(b.k_value), b.quality_retention))

        if numeric_benchmarks:
            b_20 = [ret for k_val, ret in numeric_benchmarks if k_val == 20]
            if b_20:
                topk_retention = b_20[0]
            else:
                numeric_benchmarks.sort(key=lambda item: item[0], reverse=True)
                topk_retention = numeric_benchmarks[0][1]

    # Penentuan overall status & rekomendasi (Day 19.6.1 s/d Day 19.6.4)
    is_stable = (dr_rate == 100.0)
    is_robust = (robustness_res.total_scenarios_tested > 0 and cvr_rate == 0.0 and robustness_res.all_constraints_preserved)
    is_breakdown_valid = quality_res.is_breakdown_consistent
    is_formula_valid = quality_res.formula_consistency.is_valid

    if is_ready and gq_val > 0.0:
        has_topk_benchmark = (topk_retention is not None)
        is_topk_satisfactory = (has_topk_benchmark and topk_retention >= 90.0)
    else:
        # Jika kelompok tidak terbentuk, Top-K retention tidak dapat diukur/diaplikasikan
        has_topk_benchmark = True
        is_topk_satisfactory = True

    if has_baseline_violations:
        overall_status = "FAILED"
        recommendation = (
            f"Ditemukan {len(baseline_violations)} pelanggaran hard constraints pada baseline formation: "
            f"{'; '.join(baseline_violations)}. Segera periksa integritas pembentukan kelompok."
        )
    elif cvr_rate > 0.0 or (robustness_res.total_scenarios_tested > 0 and not robustness_res.all_constraints_preserved):
        overall_status = "FAILED"
        recommendation = (
            f"Ditemukan pelanggaran hard constraints pada skenario robustness (CVR: {cvr_rate}%). "
            f"Segera periksa filtering sebelum melanjutkan deployment."
        )
    elif is_stable and is_robust and is_breakdown_valid and is_formula_valid and is_topk_satisfactory:
        overall_status = "PASSED"
        if is_ready:
            recommendation = (
                f"Matching Engine LaFriend LOLOS pengujian komprehensif Day 19. "
                f"Kualitas grup optimal (GQ: {gq_val}), stabilitas 100% invarian urutan (DR: 100%), "
                f"integritas hard constraints terlindungi sempurna (CVR: 0.0%), "
                f"dan retensi kualitas Top-K memenuhi ambang operasional ({topk_retention}% >= 90.0%)."
            )
        else:
            recommendation = (
                f"Matching Engine LaFriend LOLOS pengujian komprehensif Day 19 untuk kondisi tanpa kelompok "
                f"(status baseline: {baseline_status}). Stabilitas deterministik (DR: 100%), "
                f"seluruh batasan integritas terjaga (CVR: 0.0%), dan Top-K retention tidak dapat dihitung karena tidak ada kelompok yang terbentuk."
            )
    else:
        overall_status = "WARNING"
        warning_reasons = []
        if robustness_res.total_scenarios_tested == 0:
            warning_reasons.append("Tidak ada skenario robustness yang diuji")
        if not is_stable:
            warning_reasons.append(f"DR {dr_rate}% < 100%")
        if not is_breakdown_valid:
            warning_reasons.append("Breakdown pairwise tidak valid")
        if not is_formula_valid:
            warning_reasons.append(f"Inkonsistensi formula GQ vs APS/MPS (discrepancy: {quality_res.formula_consistency.discrepancy})")
        if is_ready and gq_val > 0.0:
            if not has_topk_benchmark:
                warning_reasons.append("Benchmark Top-K numerik tidak dijalankan")
            elif not is_topk_satisfactory:
                warning_reasons.append(f"Top-K retention {topk_retention}% < 90.0%")
        recommendation = (
            f"Pengujian menghasilkan status peringatan ({', '.join(warning_reasons)}). "
            f"Harap tinjau catatan kualitas dan parameter tuning engine."
        )

    summary = ComprehensiveEvaluationSummary(
        overall_status=overall_status,
        group_quality_score=gq_val,
        average_pair_score=aps_val,
        quality_score_mean=gq_val,
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
