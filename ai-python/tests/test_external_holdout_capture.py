from pathlib import Path

from eval.documents.external_holdout.validate_pipeline_capture import validate


def test_external_holdout_capture_has_no_judge_leakage() -> None:
    capture = Path("eval/experiments/external_holdout_20260824/pipeline_capture")
    result = validate(capture)
    assert result["status"] == "PASS", result["errors"]
    assert result["raw_case_count"] == 289
    assert result["annotation_case_count"] == 289
    assert result["judge_invocation_count"] == 0
