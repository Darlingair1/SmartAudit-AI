import json
from pathlib import Path

def test_benchmark_v1_freeze_metadata_is_self_consistent() -> None:
    meta=json.loads(Path("eval/judge/claim_evidence_benchmark_v1.metadata.json").read_text(encoding="utf8"))
    assert meta["adjudication_status"]=="complete"
    assert meta["unresolved_label_conflict_count"]==0
    assert meta["label_action_counts"]=={"KEEP":120}
    assert meta["text_action_counts"]=={"KEEP":72,"REWRITE":48}
