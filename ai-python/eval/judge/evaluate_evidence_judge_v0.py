from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from services.evidence_judge import judge_evidence_support
from services.v3_types import RetrievalCandidate
from eval.judge.validate_claim_evidence import validate

LABELS=("SUPPORTED","PARTIAL","UNSUPPORTED")
DECISION_MAP={"YES":"SUPPORTED","UNCERTAIN":"PARTIAL","NO":"UNSUPPORTED"}

def _divide(a:int,b:int)->float: return a/b if b else 0.0
def _failure(row:dict[str,Any])->str:
    note=row.get("annotation_notes","")
    for name in ("missing_qualifier","wrong_entity","numeric_mismatch","temporal_mismatch","semantic_overlap_but_insufficient","unsupported_risk_inference"):
        if f"failure_mode={name}" in note: return name
    return "other"

def evaluate(dataset:Path, metadata:Path)->dict[str,Any]:
    checked=validate(dataset,metadata)
    if checked["status"]!="valid": raise ValueError(f"invalid dataset: {checked['errors']}")
    rows=[json.loads(x) for x in dataset.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows=[x for x in rows if x["review_status"]=="reviewed"]
    settings=SimpleNamespace(judge_top_n=8)
    predictions=[]
    for row in rows:
        candidate=RetrievalCandidate(candidate_id=row["evidence_id"],parent_id="",child_id=row["evidence_id"],page_no=int(row.get("evidence_span",{}).get("page") or 1),clause_id="",clause_title="",snippet=row["evidence_text"])
        result=judge_evidence_support(query=row["claim"],risk_type=row["risk_type"],candidates=[candidate],settings=settings)
        predicted=DECISION_MAP[result.decision]
        predictions.append({"case_id":row["case_id"],"document_id":row["document_id"],"risk_type":row["risk_type"],"claim":row["claim"],"evidence_text":row["evidence_text"],"gold_label":row["gold_label"],"predicted_label":predicted,"judge_decision":result.decision,"confidence":result.confidence,"reason_code":result.reason_code,"reason":result.reason,"requires_human_review":result.requires_human_review,"failure_mode":None if predicted==row["gold_label"] else _failure(row)})
    matrix={gold:{pred:0 for pred in LABELS} for gold in LABELS}
    for x in predictions: matrix[x["gold_label"]][x["predicted_label"]]+=1
    per={}; f1s=[]
    for label in LABELS:
        tp=matrix[label][label]; fp=sum(matrix[g][label] for g in LABELS if g!=label); fn=sum(matrix[label][p] for p in LABELS if p!=label)
        precision=_divide(tp,tp+fp); recall=_divide(tp,tp+fn); f1=_divide(2*precision*recall,precision+recall)
        per[label]={"precision":round(precision,6),"recall":round(recall,6),"f1":round(f1,6),"support":sum(matrix[label].values())}; f1s.append(f1)
    abstained=[x for x in predictions if x["judge_decision"]=="UNCERTAIN"]
    partial=[x for x in predictions if x["gold_label"]=="PARTIAL"]
    correct=sum(x["gold_label"]==x["predicted_label"] for x in predictions)
    failures=[x for x in predictions if x["gold_label"]!=x["predicted_label"]]
    unsafe=sum(x["gold_label"] in {"PARTIAL","UNSUPPORTED"} and x["predicted_label"]=="SUPPORTED" for x in predictions)
    unsafe_den=sum(x["gold_label"] in {"PARTIAL","UNSUPPORTED"} for x in predictions)
    return {"metadata":{"judge":"evidence_judge_v0","label_mapping":DECISION_MAP,"case_count":len(predictions),"dataset_sha256":checked["dataset_sha256"]},"metrics":{"accuracy":round(_divide(correct,len(predictions)),6),"macro_f1":round(sum(f1s)/len(f1s),6),"per_label":per,"unsupported_recall":per["UNSUPPORTED"]["recall"],"supported_precision":per["SUPPORTED"]["precision"],"abstention_precision":round(_divide(sum(x["gold_label"]=="PARTIAL" for x in abstained),len(abstained)),6),"abstention_recall":round(_divide(sum(x["judge_decision"]=="UNCERTAIN" for x in partial),len(partial)),6),"human_review_rate":round(_divide(sum(x["requires_human_review"] for x in predictions),len(predictions)),6),"unsafe_acceptance_rate":round(_divide(unsafe,unsafe_den),6),"unsafe_acceptance_count":unsafe,"unsafe_acceptance_denominator":unsafe_den},"confusion_matrix":matrix,"failure_mode_counts":dict(Counter(x["failure_mode"] for x in failures)),"errors":failures,"predictions":predictions}

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("--dataset",type=Path,required=True); p.add_argument("--metadata",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(); result=evaluate(a.dataset,a.metadata); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
