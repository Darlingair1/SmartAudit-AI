from __future__ import annotations
import argparse,json,time,statistics
from pathlib import Path
from eval.judge.validate_generalization_benchmark import validate
from services.evidence_judge_v2 import judge_claim_evidence_v2

def evaluate(dataset:Path,metadata:Path):
    checked=validate(dataset,metadata)
    if checked["status"]!="valid": raise ValueError(checked["errors"])
    rows=[json.loads(x) for x in dataset.read_text(encoding="utf8").splitlines() if x.strip() and json.loads(x)["review_status"]=="reviewed"]
    predictions=[]; latencies=[]
    for r in rows:
        started=time.perf_counter(); result=judge_claim_evidence_v2(r["claim"],r["evidence_text"],[r["evidence_id"]]); latency_ms=(time.perf_counter()-started)*1000; latencies.append(latency_ms)
        predictions.append({"case_id":r["case_id"],"document_id":r["document_id"],"risk_type":r["risk_type"],"challenge_type":r["challenge_type"],"claim":r["claim"],"evidence_text":r["evidence_text"],"gold_label":r["gold_label"],"predicted_label":result["predicted_label"],"reason_code":result["reason_code"],"requires_human_review":result["requires_human_review"],"latency_ms":round(latency_ms,6),"feature_result":result})
    ordered=sorted(latencies); p95=ordered[min(len(ordered)-1,max(0,int(len(ordered)*.95)-1))]
    return {"metadata":{"judge":"evidence_judge_v2","dataset_sha256":checked["dataset_sha256"],"case_count":len(predictions),"semantic_implementation":"model-free normalization/concept coverage/guards","fallback_count":0,"timeout_count":0,"error_count":0,"invocation_count":len(predictions),"latency_ms":{"mean":round(statistics.mean(latencies),6),"p50":round(statistics.median(latencies),6),"p95":round(p95,6),"max":round(max(latencies),6)},"estimated_cost":0.0},"predictions":predictions}
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--dataset",type=Path,required=True); p.add_argument("--metadata",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(evaluate(a.dataset,a.metadata),ensure_ascii=False,indent=2)+"\n",encoding="utf8")
