from __future__ import annotations
import argparse,json,statistics,time
from pathlib import Path
from eval.judge.validate_generalization_benchmark import validate
from services.evidence_judge_v2_1 import judge_claim_evidence_v2_1

def evaluate(dataset:Path,metadata:Path):
    checked=validate(dataset,metadata)
    if checked["status"]!="valid": raise ValueError(checked["errors"])
    rows=[json.loads(x) for x in dataset.read_text(encoding="utf8").splitlines() if x.strip()]; predictions=[]; times=[]
    for r in rows:
        started=time.perf_counter(); result=judge_claim_evidence_v2_1(r["claim"],r["evidence_text"],[r["evidence_id"]]); elapsed=(time.perf_counter()-started)*1000; times.append(elapsed)
        predictions.append({"case_id":r["case_id"],"document_id":r["document_id"],"risk_type":r["risk_type"],"challenge_type":r["challenge_type"],"claim":r["claim"],"evidence_text":r["evidence_text"],"gold_label":r["gold_label"],"predicted_label":result["predicted_label"],"reason_code":result["reason_code"],"requires_human_review":result["requires_human_review"],"latency_ms":round(elapsed,6),"feature_result":result})
    ordered=sorted(times); p95=ordered[min(len(ordered)-1,int(len(ordered)*.95)-1)]
    return {"metadata":{"judge":"evidence_judge_v2_1","dataset_sha256":checked["dataset_sha256"],"case_count":len(rows),"one_shot_safety_iteration":True,"model":None,"invocation_count":len(rows),"timeout_count":0,"error_count":0,"fallback_count":0,"estimated_cost":0.0,"latency_ms":{"mean":round(statistics.mean(times),6),"p50":round(statistics.median(times),6),"p95":round(p95,6),"max":round(max(times),6)}},"predictions":predictions}
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--dataset",type=Path,required=True); p.add_argument("--metadata",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(evaluate(a.dataset,a.metadata),ensure_ascii=False,indent=2)+"\n",encoding="utf8")
