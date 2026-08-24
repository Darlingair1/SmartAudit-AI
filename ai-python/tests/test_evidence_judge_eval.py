import json
from pathlib import Path
from eval.judge.evaluate_evidence_judge_v0 import DECISION_MAP, evaluate
from eval.judge.validate_claim_evidence import validate

def test_fixed_label_mapping() -> None:
    assert DECISION_MAP == {"YES":"SUPPORTED","UNCERTAIN":"PARTIAL","NO":"UNSUPPORTED"}

def test_claim_evidence_dataset_validates() -> None:
    result=validate(Path("eval/judge/claim_evidence_v1.jsonl"),Path("eval/judge/claim_evidence_v1.metadata.json"))
    assert result["status"]=="valid"
    assert result["label_distribution"]=={"SUPPORTED":40,"PARTIAL":40,"UNSUPPORTED":40}

def test_judge_eval_metrics_are_bounded() -> None:
    result=evaluate(Path("eval/judge/claim_evidence_v1.jsonl"),Path("eval/judge/claim_evidence_v1.metadata.json"))
    assert result["metadata"]["case_count"]==120
    for key in ("accuracy","macro_f1","unsupported_recall","supported_precision","abstention_precision","abstention_recall","human_review_rate"):
        assert 0<=result["metrics"][key]<=1
    assert result["metrics"]["unsafe_acceptance_rate"] == 0.8625
    assert result["confusion_matrix"] == {
        "SUPPORTED":{"SUPPORTED":40,"PARTIAL":0,"UNSUPPORTED":0},
        "PARTIAL":{"SUPPORTED":37,"PARTIAL":3,"UNSUPPORTED":0},
        "UNSUPPORTED":{"SUPPORTED":32,"PARTIAL":0,"UNSUPPORTED":8},
    }
