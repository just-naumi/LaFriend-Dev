# ==============================================================================
# matching_evaluation.py - Modul Evaluasi & Validasi Kualitas Matching Engine (Day 19)
# ==============================================================================
# Modul ini bertanggung jawab untuk:
# 1. Day 19.1 - Group Quality Evaluation (APS, MPS, GQ, sebaran skor pairwise,
#    identifikasi weakest link/strongest link, variansi skor, dan catatan kualitas).
# 2. Day 19.2 - Matching Stability & Order Invariance (pengujian determinisme permutasi).
# 3. Day 19.3 - Robustness Testing (evaluasi data sparse, non-ideal, dan hard constraints).
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
)


# ==============================================================================
# 1. EVALUASI DISTRIBUSI SKOR PAIRWISE
# ==============================================================================

def calculate_pairwise_distribution(
    scores: Sequence[Union[float, int, Decimal]]
) -> PairwiseScoreDistribution:
    """
    Menghitung statistik distribusi skor kecocokan pairwise seluruh pasangan.
    Metrik meliputi:
      - count: jumlah pasangan (N_pair)
      - mean: rata-rata skor pasangan (APS)
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

    float_scores = [round(float(s), 4) for s in scores]
    n = len(float_scores)

    mean_val = float(Decimal(str(sum(float_scores))) / Decimal(str(n)))
    mean_rounded = round(mean_val, 2)

    median_val = round(float(statistics.median(float_scores)), 2)
    min_val = round(float(min(float_scores)), 2)
    max_val = round(float(max(float_scores)), 2)
    spread = round(max_val - min_val, 2)

    if n > 1:
        # Gunakan variansi populasi (pvariance) untuk mengukur dispersi seluruh pasangan dalam grup
        var_val = float(statistics.pvariance(float_scores))
        std_val = float(math.sqrt(var_val))
    else:
        var_val = 0.0
        std_val = 0.0

    return PairwiseScoreDistribution(
        count=n,
        mean=mean_rounded,
        median=median_val,
        std_dev=round(std_val, 2),
        variance=round(var_val, 2),
        min_score=min_val,
        max_score=max_val,
        score_spread=spread,
    )


# ==============================================================================
# 2. VALIDASI KONSISTENSI FORMULA GQ
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
      Total Score == Topic + Goal + Style + Schedule + Mode
    """
    total_score = float(pairwise_item.get("compatibility_score", 0.0))
    breakdown = pairwise_item.get("breakdown", {})

    sum_contributions = 0.0
    component_details = {}

    for comp_key in ["topic", "goal", "style", "date", "mode"]:
        comp_data = breakdown.get(comp_key)
        if isinstance(comp_data, dict):
            contrib = float(comp_data.get("contribution", 0.0))
        elif hasattr(comp_data, "contribution"):
            contrib = float(getattr(comp_data, "contribution", 0.0))
        else:
            contrib = 0.0
        sum_contributions += contrib
        component_details[comp_key] = contrib

    sum_rounded = round(sum_contributions, 2)
    discrepancy = round(abs(total_score - sum_rounded), 4)
    is_consistent = discrepancy <= tolerance

    return {
        "is_consistent": is_consistent,
        "compatibility_score": round(total_score, 2),
        "sum_of_contributions": sum_rounded,
        "discrepancy": discrepancy,
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

        # Jika scores kosong atau tidak konsisten, hitung ulang
        if not scores and "all_pairwise_scores" in data:
            scores = [float(s) for s in data["all_pairwise_scores"]]

        if scores and (gq == 0.0 and aps == 0.0 and mps == 0.0):
            gq, aps, mps = calculate_group_quality_score(scores)

        weakest_link, strongest_link = identify_weakest_and_strongest_links(raw_pairwise)
    else:
        scores = [float(s) for s in data]
        gq, aps, mps = calculate_group_quality_score(scores)
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
# 7. EVALUASI STABILITAS & ORDER INVARIANCE (DAY 19.2)
# ==============================================================================

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
    Menguji order invariance engine:
    Menjalankan algoritma form_study_group sebanyak num_permutations kali dengan urutan
    candidate_intents yang diacak secara berbeda-beda.

    Engine yang stabil dan deterministik harus menghasilkan keanggotaan kelompok,
    Group Quality Score, dan jadwal yang 100% IDENTIK tanpa terpengaruh urutan input.
    """
    if num_permutations < 1:
        raise ValueError("num_permutations minimal 1")

    # Jalankan baseline dengan urutan asli
    baseline_run = form_study_group(
        host_intent=host_intent,
        candidate_intents=list(candidate_intents),
        min_score=min_score,
        target_group_size=target_group_size,
        max_candidate_pool=max_candidate_pool,
    )

    baseline_members = sorted([m["intent_id"] for m in baseline_run.get("members", [])])
    baseline_gq = round(float(baseline_run.get("group_quality_score", 0.0)), 2)
    sched = baseline_run.get("selected_schedule")
    baseline_sched_key = f"{sched['date']}_{sched['start_time']}_{sched['end_time']}" if sched else "NO_SCHED"
    baseline_signature = f"{'-'.join(baseline_members)}__GQ_{baseline_gq:.2f}__{baseline_sched_key}"

    rng = random.Random(random_seed)
    candidates_list = list(candidate_intents)

    permutation_runs: List[OrderPermutationRun] = []
    signatures_seen = set()
    matches_count = 0

    for idx in range(num_permutations):
        # Acak urutan kandidat
        shuffled = list(candidates_list)
        if idx > 0:
            rng.shuffle(shuffled)

        run_res = form_study_group(
            host_intent=host_intent,
            candidate_intents=shuffled,
            min_score=min_score,
            target_group_size=target_group_size,
            max_candidate_pool=max_candidate_pool,
        )

        run_members = sorted([m["intent_id"] for m in run_res.get("members", [])])
        run_gq = round(float(run_res.get("group_quality_score", 0.0)), 2)
        r_sched = run_res.get("selected_schedule")
        r_sched_key = f"{r_sched['date']}_{r_sched['start_time']}_{r_sched['end_time']}" if r_sched else "NO_SCHED"
        run_sig = f"{'-'.join(run_members)}__GQ_{run_gq:.2f}__{r_sched_key}"

        signatures_seen.add(run_sig)
        is_match = (run_sig == baseline_signature)
        if is_match:
            matches_count += 1

        permutation_runs.append(OrderPermutationRun(
            permutation_index=idx + 1,
            input_order_intent_ids=[str(c.intent_id) for c in shuffled],
            selected_member_intent_ids=run_members,
            group_quality_score=run_gq,
            selected_schedule_key=r_sched_key,
            matches_baseline=is_match,
        ))

    determinism_rate = round((matches_count / num_permutations) * 100.0, 2)
    is_order_invariant = (len(signatures_seen) == 1 and matches_count == num_permutations)

    return MatchingStabilityResult(
        num_permutations=num_permutations,
        is_order_invariant=is_order_invariant,
        determinism_rate=determinism_rate,
        distinct_group_signatures=len(signatures_seen),
        baseline_signature=baseline_signature,
        permutations=permutation_runs,
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
            retention = round((gq / full_gq) * 100.0, 2)
            loss = round(((full_gq - gq) / full_gq) * 100.0, 2)
        else:
            retention = 100.0
            loss = 0.0

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
        ))

    return TopKBenchmarkResult(
        total_candidates=total_candidates,
        baseline_k="Full",
        benchmarks=items,
    )
