from pathlib import Path
from eval.judge.evaluate_evidence_judge_v1 import evaluate

def test_v1_frozen_benchmark_evaluation() -> None:
    result=evaluate(Path('eval/judge/claim_evidence_benchmark_v1.jsonl'),Path('eval/judge/claim_evidence_benchmark_v1.metadata.json'))
    assert result['metadata']['dataset_sha256']=='e8c68404be3ef8535c8f3cc3f9fe54418616870ad993bf2d676f2eee4cf189f7'
    assert result['metrics']['accuracy']==1.0
    assert result['metrics']['unsafe_acceptance_rate']==0.0
    assert result['metrics']['false_rejection_count']==0
