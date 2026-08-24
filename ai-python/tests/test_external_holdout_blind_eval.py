from eval.judge.evaluate_external_holdout_blind import (
    canonical_hash,
    metric_bundle,
    transition_analysis,
    wilson_interval,
)


def _row(case_id: str, gold: str, predicted: str) -> dict:
    return {
        "case_id": case_id,
        "document_id": "doc",
        "risk_type": "risk",
        "gold_label": gold,
        "predicted_label": predicted,
        "reason_code": "TEST",
        "feature_result": {},
        "used_evidence_ids": ["e1"],
    }


def test_unified_metrics_include_counts_and_expected_safety_rates() -> None:
    rows = [
        _row("1", "SUPPORTED", "SUPPORTED"),
        _row("2", "SUPPORTED", "PARTIAL"),
        _row("3", "PARTIAL", "SUPPORTED"),
        _row("4", "UNSUPPORTED", "UNSUPPORTED"),
    ]
    result = metric_bundle(rows)
    assert result["accuracy"] == 0.5
    assert result["unsafe_acceptance_count"] == {"numerator": 1, "denominator": 2}
    assert result["supported_false_rejection_count"] == {"numerator": 1, "denominator": 2}
    assert result["hard_false_rejection_count"] == {"numerator": 0, "denominator": 2}
    assert result["human_review_count"] == {"numerator": 1, "denominator": 4}
    assert result["selective_accuracy_count"] == {"numerator": 2, "denominator": 3}


def test_wilson_interval_is_bounded_and_records_counts() -> None:
    result = wilson_interval(3, 10)
    assert result["numerator"] == 3 and result["denominator"] == 10
    assert 0 <= result["low"] < 0.3 < result["high"] <= 1
    assert wilson_interval(0, 0)["low"] is None


def test_config_fingerprint_is_order_independent() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


def test_transition_categories_are_explicit() -> None:
    before = [_row("1", "SUPPORTED", "PARTIAL"), _row("2", "PARTIAL", "PARTIAL")]
    after = [_row("1", "SUPPORTED", "SUPPORTED"), _row("2", "PARTIAL", "SUPPORTED")]
    result = transition_analysis(before, after, "v1_to_v2_1")
    assert result["counts"]["v1_wrong_to_v2_1_correct"] == 1
    assert result["counts"]["v1_false_rejection_to_v2_1_correct"] == 1
    assert result["counts"]["v1_correct_to_v2_1_wrong"] == 1
    assert result["counts"]["v1_safe_to_v2_1_unsafe"] == 1
