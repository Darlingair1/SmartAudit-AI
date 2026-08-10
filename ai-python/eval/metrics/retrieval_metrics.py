from __future__ import annotations

import math
from statistics import mean, median
from typing import Any, Iterable, Sequence


DEFAULT_TOP_KS = (1, 3, 5, 10)


def calculate_case_metrics(
    relevance: Sequence[Sequence[bool]],
    gold_count: int,
    top_ks: Sequence[int] = DEFAULT_TOP_KS,
) -> dict[str, Any]:
    """Calculate retrieval metrics for one case.

    Each relevance row represents one ranked result and contains one boolean
    per gold evidence. Hit@K is one when any gold is covered in top K.
    Recall@K is the fraction of distinct gold evidences covered in top K.
    MRR is the reciprocal rank of the first result covering any gold.
    """

    if gold_count < 0:
        raise ValueError("gold_count cannot be negative")
    ks = sorted(set(int(k) for k in top_ks))
    if not ks or any(k <= 0 for k in ks):
        raise ValueError("top_ks must contain positive integers")

    first_rank = next(
        (rank for rank, row in enumerate(relevance, start=1) if any(row)), None
    )
    result: dict[str, Any] = {
        "first_relevant_rank": first_rank,
        "mrr": 1.0 / first_rank if first_rank is not None else 0.0,
    }
    for k in ks:
        covered = {
            gold_index
            for row in relevance[:k]
            for gold_index, matched in enumerate(row[:gold_count])
            if matched
        }
        result[f"hit_at_{k}"] = bool(covered)
        result[f"recall_at_{k}"] = len(covered) / gold_count if gold_count else 0.0
    return result


def aggregate_latency(latencies_ms: Iterable[float]) -> dict[str, float | None]:
    """Return mean, median, and nearest-rank P95 latency in milliseconds."""

    values = sorted(float(value) for value in latencies_ms)
    if not values:
        return {"mean_ms": None, "median_ms": None, "p95_ms": None}
    p95_index = max(0, math.ceil(0.95 * len(values)) - 1)
    return {
        "mean_ms": round(mean(values), 3),
        "median_ms": round(median(values), 3),
        "p95_ms": round(values[p95_index], 3),
    }


def aggregate_retrieval_metrics(
    case_results: Sequence[dict[str, Any]],
    top_ks: Sequence[int] = DEFAULT_TOP_KS,
) -> dict[str, Any]:
    """Aggregate quality over completed retrievals and latency over attempts."""

    ks = sorted(set(int(k) for k in top_ks))
    quality_cases = [
        case
        for case in case_results
        if case.get("retrieval_successful", True)
    ]
    output: dict[str, Any] = {}
    for k in ks:
        output[f"hit_at_{k}"] = round(
            mean(float(case.get(f"hit_at_{k}", False)) for case in quality_cases),
            6,
        ) if quality_cases else None
        output[f"recall_at_{k}"] = round(
            mean(float(case.get(f"recall_at_{k}", 0.0)) for case in quality_cases),
            6,
        ) if quality_cases else None
    output["mrr"] = (
        round(mean(float(case.get("mrr", 0.0)) for case in quality_cases), 6)
        if quality_cases
        else None
    )
    output["latency"] = aggregate_latency(
        case["latency_ms"]
        for case in case_results
        if case.get("retrieval_executed", True)
        and isinstance(case.get("latency_ms"), (int, float))
    )
    return output


def calculate_evaluation_coverage(
    case_results: Sequence[dict[str, Any]],
) -> dict[str, int | float]:
    total = len(case_results)
    executed = sum(bool(case.get("retrieval_executed")) for case in case_results)
    successful = sum(bool(case.get("retrieval_successful")) for case in case_results)
    document_not_found = sum(
        case.get("status") == "document_not_found" for case in case_results
    )
    retrieval_errors = sum(
        case.get("status") == "retrieval_error" for case in case_results
    )
    return {
        "total_case_count": total,
        "retrieval_executed_count": executed,
        "retrieval_success_count": successful,
        "document_not_found_count": document_not_found,
        "retrieval_error_count": retrieval_errors,
        "evaluation_coverage": round(executed / total, 6) if total else 0.0,
    }
