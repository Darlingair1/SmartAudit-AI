"""Replay a frozen candidate snapshot through reranking only."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from types import SimpleNamespace
from services.reranker import rerank_candidates, reset_reranker_circuit
from services.v3_types import RetrievalCandidate
from eval.candidate_snapshot import load_snapshot

def run(path: Path, strict: bool = True, rerank: bool = True) -> dict:
    snapshot = load_snapshot(path)
    reset_reranker_circuit()
    from core.config import get_settings
    base = get_settings()
    settings = SimpleNamespace(rerank_enabled=True, rerank_strict=strict, rerank_top_n=10, rerank_batch_size=8, rerank_max_length=256, rerank_timeout_ms=3000, rerank_model_path=base.rerank_model_path, rerank_model_version="bge-reranker-v2-m3", embedding_device="cpu")
    cases=[]
    for record in snapshot["cases"]:
        candidates=[RetrievalCandidate(candidate_id=x["candidate_id"], parent_id=x.get("parent_id") or "", child_id=x["candidate_id"].split(":")[-1], page_no=int(x.get("page") or 1), clause_id="", clause_title="", snippet=x.get("text", ""), rrf_score=float(x.get("rrf_score") or 0), metadata=dict(x.get("metadata") or {}), page_nos=list(x.get("page_nos") or [])) for x in record["candidates"]]
        if rerank:
            reranked, metrics=rerank_candidates(query=record["query"], candidates=candidates, settings=settings)
        else:
            reranked, metrics = candidates, {"rerank_backend": "snapshot_noop", "rerank_applied": False}
        cases.append({"case_id":record["case_id"], "candidate_ids":[c.candidate_id for c in reranked], "reranker":metrics})
    lines=[f"{x['case_id']}\t{'|'.join(x['candidate_ids'])}" for x in sorted(cases,key=lambda x:x['case_id'])]
    return {"snapshot_sha256":snapshot["snapshot_sha256"],"case_count":len(cases),"ranking_fingerprint":hashlib.sha256("\n".join(lines).encode()).hexdigest(),"cases":cases}

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("snapshot",type=Path); p.add_argument("--output",type=Path); p.add_argument("--no-op",action="store_true"); a=p.parse_args(); out=run(a.snapshot,True,not a.no_op); text=json.dumps(out,ensure_ascii=False,indent=2)+"\n"; a.output.write_text(text,encoding="utf-8") if a.output else print(text)
