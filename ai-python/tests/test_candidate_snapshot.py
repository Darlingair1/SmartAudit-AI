import json
from pathlib import Path

import pytest

from eval.candidate_snapshot import _sha_payload, load_snapshot
from eval.run_snapshot_rerank import run
from services import reranker
from services.v3_types import RetrievalCandidate


def test_snapshot_hash_and_integrity(tmp_path: Path) -> None:
    payload = {"metadata": {"schema_version": "candidate_snapshot_v1", "case_count": 0}, "cases": []}
    payload["snapshot_sha256"] = _sha_payload(payload)
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_snapshot(path)["snapshot_sha256"] == payload["snapshot_sha256"]
    payload["cases"].append({"case_id": "x"})
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_snapshot(path)


def test_snapshot_replay_is_deterministic() -> None:
    path = Path("eval/experiments/crossencoder_snapshot_20260823/candidate_snapshot.json")
    first = run(path, rerank=False)
    second = run(path, rerank=False)
    assert first["ranking_fingerprint"] == second["ranking_fingerprint"]
    assert [x["candidate_ids"] for x in first["cases"]] == [x["candidate_ids"] for x in second["cases"]]


def test_timeout_opens_circuit_and_next_call_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    reranker.reset_reranker_circuit()
    candidate = RetrievalCandidate("d:c", "p", "c", 1, "", "", "text", rrf_score=0.2)
    settings = type("Settings", (), {"rerank_enabled": True, "rerank_strict": False, "rerank_top_n": 1, "rerank_batch_size": 1, "rerank_max_length": 256, "rerank_timeout_ms": 500, "rerank_model_path": "", "rerank_model_version": "x", "embedding_device": "cpu"})()
    monkeypatch.setattr(reranker, "_get_cross_encoder", lambda _: object())
    monkeypatch.setattr(reranker, "_predict_cross_encoder_with_timeout", lambda **_: (_ for _ in ()).throw(reranker.FutureTimeoutError()))
    _, first = reranker.rerank_candidates(query="q", candidates=[candidate], settings=settings)
    _, second = reranker.rerank_candidates(query="q", candidates=[candidate], settings=settings)
    assert first["rerank_backend"] == "cross_encoder_circuit_open"
    assert second["rerank_backend"] == "cross_encoder_circuit_open"
    assert second["rerank_failure_reason"] == "circuit_open_after_timeout"
    reranker.reset_reranker_circuit()
