from services.evidence_judge_v2 import aggregate_evidence, chinese_number, normalize_numbers, judge_claim_evidence_v2

def test_number_normalization():
    assert chinese_number("三十") == 30
    assert "30" in normalize_numbers("三十日")
    assert "pct:10" in normalize_numbers("百分之十")

def test_multi_evidence_aggregation():
    result=aggregate_evidence("甲方在十个工作日内支付百分之三十价款", [{"evidence_id":"a","text":"甲方应支付价款百分之三十。"},{"evidence_id":"b","text":"收到发票后十个工作日内付款。"}])
    assert result["predicted_label"] == "SUPPORTED"
    assert result["used_evidence_ids"] == ["a","b"]

def test_conflict_guard_is_not_lexical_rejection():
    result=judge_claim_evidence_v2("甲方支付百分之三十价款", "甲方支付百分之二十价款")
    assert result["predicted_label"] == "UNSUPPORTED"
    assert result["reason_code"] == "EXPLICIT_NUMERIC_OR_TEMPORAL_CONFLICT"

def test_insufficient_evidence_abstains():
    result=judge_claim_evidence_v2("甲方应在验收后十五个工作日内支付全部价款", "甲方应支付价款")
    assert result["predicted_label"] == "PARTIAL"
    assert result["requires_human_review"] is True

def test_v2_result_has_local_latency_provenance():
    import json
    from pathlib import Path
    result=json.loads(Path("eval/experiments/evidence_judge_v2_20260823/results.json").read_text(encoding="utf8"))
    assert result["metadata"]["invocation_count"] == 107
    assert result["metadata"]["estimated_cost"] == 0.0
    assert result["metadata"]["latency_ms"]["max"] >= result["metadata"]["latency_ms"]["p50"]
    assert all("latency_ms" in x for x in result["predictions"])
