from eval.metrics.retrieval_metrics import (
    aggregate_latency,
    aggregate_retrieval_metrics,
    calculate_case_metrics,
)


def test_hit_recall_and_mrr_for_multiple_gold_items():
    metrics = calculate_case_metrics(
        [[False, False], [True, False], [False, True]], 2, (1, 3, 5, 10)
    )
    assert metrics["hit_at_1"] is False
    assert metrics["recall_at_1"] == 0.0
    assert metrics["recall_at_3"] == 1.0
    assert metrics["hit_at_3"] is True
    assert metrics["mrr"] == 0.5


def test_relevant_result_at_rank_five_and_partial_recall():
    relevance = [[False, False]] * 4 + [[True, False]]
    metrics = calculate_case_metrics(relevance, 2, (1, 5))
    assert metrics["hit_at_1"] is False
    assert metrics["hit_at_5"] is True
    assert metrics["recall_at_5"] == 0.5
    assert metrics["first_relevant_rank"] == 5
    assert metrics["mrr"] == 0.2


def test_empty_results_and_latency():
    metrics = calculate_case_metrics([], 1)
    assert metrics["hit_at_1"] is False
    assert metrics["recall_at_10"] == 0.0
    assert metrics["mrr"] == 0.0
    assert aggregate_latency([10, 20, 30]) == {
        "mean_ms": 20.0,
        "median_ms": 20.0,
        "p95_ms": 30.0,
    }
    assert aggregate_latency([])["p95_ms"] is None


def test_aggregate_metrics_are_macro_averages():
    cases = [
        {"hit_at_1": True, "recall_at_1": 1.0, "mrr": 1.0, "latency_ms": 10},
        {"hit_at_1": False, "recall_at_1": 0.0, "mrr": 0.0, "latency_ms": 30},
    ]
    output = aggregate_retrieval_metrics(cases, (1,))
    assert output["hit_at_1"] == 0.5
    assert output["recall_at_1"] == 0.5
    assert output["latency"]["median_ms"] == 20.0


def test_non_executed_and_error_cases_do_not_enter_quality_metrics():
    cases = [
        {
            "status": "document_not_found",
            "retrieval_executed": False,
            "retrieval_successful": False,
            "hit_at_1": False,
            "recall_at_1": 0.0,
            "mrr": 0.0,
            "latency_ms": None,
        },
        {
            "status": "retrieval_error",
            "retrieval_executed": True,
            "retrieval_successful": False,
            "hit_at_1": False,
            "recall_at_1": 0.0,
            "mrr": 0.0,
            "latency_ms": 25.0,
        },
        {
            "status": "success",
            "retrieval_executed": True,
            "retrieval_successful": True,
            "hit_at_1": True,
            "recall_at_1": 1.0,
            "mrr": 1.0,
            "latency_ms": 15.0,
        },
    ]
    output = aggregate_retrieval_metrics(cases, (1,))
    assert output["hit_at_1"] == 1.0
    assert output["recall_at_1"] == 1.0
    assert output["mrr"] == 1.0
    assert output["latency"]["mean_ms"] == 20.0


def test_evaluation_coverage_counts_attempts_and_outcomes():
    from eval.metrics.retrieval_metrics import calculate_evaluation_coverage

    coverage = calculate_evaluation_coverage(
        [
            {"status": "document_not_found", "retrieval_executed": False, "retrieval_successful": False},
            {"status": "retrieval_error", "retrieval_executed": True, "retrieval_successful": False},
            {"status": "success", "retrieval_executed": True, "retrieval_successful": True},
            {"status": "partial_evidence_retrieved", "retrieval_executed": True, "retrieval_successful": True},
        ]
    )
    assert coverage == {
        "total_case_count": 4,
        "retrieval_executed_count": 3,
        "retrieval_success_count": 2,
        "document_not_found_count": 1,
        "retrieval_error_count": 1,
        "evaluation_coverage": 0.75,
    }
