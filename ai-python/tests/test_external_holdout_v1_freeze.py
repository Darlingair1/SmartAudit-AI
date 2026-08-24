from pathlib import Path

from eval.documents.external_holdout.validate_external_holdout_v1 import validate


def test_external_holdout_v1_is_frozen_and_traceable() -> None:
    result = validate(
        Path("eval/judge/external_holdout_v1"),
        Path("eval/experiments/external_holdout_20260824/adjudication_sample_v1"),
    )
    assert result["status"] == "PASS", result["errors"]
    assert result["total"] == result["reviewed"] == 120
    assert result["draft"] == result["unresolved"] == 0
    assert result["source_sample_integrity"] is True
    assert result["judge_invocation_count"] == 0
