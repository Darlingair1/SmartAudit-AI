import json
from pathlib import Path

from eval.judge.validate_generalization_benchmark import validate

ROOT = Path(__file__).parents[1]
DATA = ROOT / "eval/judge/claim_evidence_generalization_v1.jsonl"
META = ROOT / "eval/judge/claim_evidence_generalization_v1.metadata.json"
RESULT = ROOT / "eval/experiments/evidence_judge_generalization_v1_20260823/results.json"
COMPARISON = ROOT / "eval/experiments/evidence_judge_generalization_v1_20260823/v0_v1_comparison.json"

def test_generalization_dataset_is_frozen_and_valid():
    result = validate(DATA, META)
    assert result["status"] == "valid", result["errors"]
    assert result["case_count"] >= 80
    assert result["reviewed_count"] == result["case_count"]
    assert set(result["label_distribution"]) == {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}

def test_generalization_provenance_is_real_retrieval_output():
    rows = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert all(r["sample_provenance"]["source_dataset"] == "eval/datasets/rag_eval_dev_v1.jsonl" for r in rows)
    assert all(r["sample_provenance"]["source_case_id"] for r in rows)
    assert all(r["evidence_span"]["text"] == r["evidence_text"] for r in rows)

def test_blind_result_is_complete_and_kept_separate():
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8-sig"))
    assert report["metadata"]["dataset_sha256"] == meta["dataset_sha256"]
    assert report["metadata"]["controlled_benchmark_report"] != report["metadata"]["dataset"]
    assert len(report["predictions"]) == meta["reviewed_count"]
    assert all({"case_id", "reason_code", "feature_result"} <= set(row) for row in report["errors"])

def test_v0_v1_comparison_has_unified_safety_metrics():
    comparison = json.loads(COMPARISON.read_text(encoding="utf-8"))
    required = {"supported_false_rejection_rate", "hard_false_rejection_rate", "selective_accuracy", "unsafe_acceptance_rate", "human_review_rate", "automation_coverage"}
    for version in ("v0", "v1"):
        assert required <= set(comparison["generalization"][version]["metrics"])
        assert len(comparison["generalization"][version]["predictions"]) == 107
    assert comparison["provenance"]["v1_blind_result_sha256"]
    assert comparison["controlled_v1"]["case_count"] == 120
