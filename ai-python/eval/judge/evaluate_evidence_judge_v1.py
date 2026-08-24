from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from eval.judge.evaluate_evidence_judge_v0 import LABELS,_divide,_failure
from eval.judge.validate_claim_evidence import validate
from services.evidence_judge_v1 import judge_claim_evidence_v1

def evaluate(dataset:Path,metadata:Path)->dict:
    checked=validate(dataset,metadata)
    if checked["status"]!="valid": raise ValueError(checked["errors"])
    rows=[json.loads(x) for x in dataset.read_text(encoding='utf8').splitlines() if x.strip() and json.loads(x)["review_status"]=="reviewed"]
    predictions=[]
    for row in rows:
        result=judge_claim_evidence_v1(row["claim"],row["evidence_text"]); predictions.append({"case_id":row["case_id"],"document_id":row["document_id"],"risk_type":row["risk_type"],"claim":row["claim"],"evidence_text":row["evidence_text"],"gold_label":row["gold_label"],"predicted_label":result["predicted_label"],"judge_decision":result["decision"],"reason_code":result["reason_code"],"score":result["lexical_score"],"requires_human_review":result["requires_human_review"],"feature_result":result["checks"],"failure_mode":None if result["predicted_label"]==row["gold_label"] else _failure(row)})
    matrix={g:{p:0 for p in LABELS} for g in LABELS}
    for x in predictions: matrix[x["gold_label"]][x["predicted_label"]]+=1
    per={}; f1s=[]
    for label in LABELS:
        tp=matrix[label][label]; fp=sum(matrix[g][label] for g in LABELS if g!=label); fn=sum(matrix[label][p] for p in LABELS if p!=label); precision=_divide(tp,tp+fp); recall=_divide(tp,tp+fn); f1=_divide(2*precision*recall,precision+recall); f1s.append(f1); per[label]={"precision":round(precision,6),"recall":round(recall,6),"f1":round(f1,6),"support":sum(matrix[label].values())}
    abst=[x for x in predictions if x["judge_decision"]=="UNCERTAIN"]; partial=[x for x in predictions if x["gold_label"]=="PARTIAL"]; unsafe=sum(x["gold_label"] in {"PARTIAL","UNSUPPORTED"} and x["predicted_label"]=="SUPPORTED" for x in predictions); errors=[x for x in predictions if x["gold_label"]!=x["predicted_label"]]
    metrics={"accuracy":round(_divide(sum(x["gold_label"]==x["predicted_label"] for x in predictions),len(predictions)),6),"macro_f1":round(sum(f1s)/3,6),"per_label":per,"supported_precision":per["SUPPORTED"]["precision"],"unsupported_recall":per["UNSUPPORTED"]["recall"],"abstention_precision":round(_divide(sum(x["gold_label"]=="PARTIAL" for x in abst),len(abst)),6),"abstention_recall":round(_divide(sum(x["predicted_label"]=="PARTIAL" for x in partial),len(partial)),6),"human_review_rate":round(_divide(sum(x["requires_human_review"] for x in predictions),len(predictions)),6),"unsafe_acceptance_rate":round(_divide(unsafe,80),6),"unsafe_acceptance_count":unsafe,"false_rejection_count":sum(x["gold_label"]=="SUPPORTED" and x["predicted_label"]!="SUPPORTED" for x in predictions)}
    return {"metadata":{"judge":"evidence_judge_v1","dataset_sha256":checked["dataset_sha256"],"case_count":len(predictions)},"metrics":metrics,"confusion_matrix":matrix,"failure_mode_counts":dict(Counter(x["failure_mode"] for x in errors)),"errors":errors,"predictions":predictions}
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--dataset',type=Path,required=True); p.add_argument('--metadata',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); r=evaluate(a.dataset,a.metadata); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
