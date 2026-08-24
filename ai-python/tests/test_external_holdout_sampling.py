from pathlib import Path

from eval.documents.external_holdout.validate_adjudication_sample import validate


def test_external_holdout_sample_is_frozen_and_annotation_does_not_mutate_it() -> None:
    sample_dir = Path("eval/experiments/external_holdout_20260824/adjudication_sample_v1")
    result = validate(sample_dir)
    assert result["status"] == "PASS", result["errors"]
    assert result["capture_universe_count"] == 289
    assert result["sample_size"] == 120
    assert result["annotation_count"] == 120
    assert result["completed_annotation_count"] == 120
    assert result["judge_invocation_count"] == 0
