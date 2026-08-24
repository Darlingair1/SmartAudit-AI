from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path
from eval.judge.validate_generalization_benchmark import validate
from services.evidence_judge_v1 import judge_claim_evidence_v1

LABELS=("SUPPORTED","PARTIAL","UNSUPPORTED")
def div(a,b): return round(a/b,6) if b else 0.0
def score(rows):
    matrix={g:{p:0 for p in LABELS} for g in LABELS}; predictions=[]
    for r in rows:
        x=judge_claim_evidence_v1(r["claim"],r["evidence_text"]); p=x["predicted_label"]; matrix[r["gold_label"]][p]+=1
        predictions.append({"case_id":r["case_id"],"document_id":r["document_id"],"risk_type":r["risk_type"],"challenge_type":r["challenge_type"],"claim":r["claim"],"evidence_text":r["evidence_text"],"gold_label":r["gold_label"],"predicted_label":p,"reason_code":x["reason_code"],"score":x["lexical_score"],"requires_human_review":x["requires_human_review"],"feature_result":x["checks"]})
    per={}; f=[]
    for l in LABELS:
        tp=matrix[l][l]; fp=sum(matrix[g][l] for g in LABELS if g!=l); fn=sum(matrix[l][p] for p in LABELS if p!=l); pr=div(tp,tp+fp); re=div(tp,tp+fn); f1=div(2*pr*re,pr+re); per[l]={"precision":pr,"recall":re,"f1":f1,"support":sum(matrix[l].values())}; f.append(f1)
    n=len(rows); abst=[x for x in predictions if x["predicted_label"]=="PARTIAL"]; gold_abst=[x for x in predictions if x["gold_label"]=="PARTIAL"]; unsafe=[x for x in predictions if x["gold_label"] in {"PARTIAL","UNSUPPORTED"} and x["predicted_label"]=="SUPPORTED"]
    metrics={"accuracy":div(sum(x["gold_label"]==x["predicted_label"] for x in predictions),n),"macro_f1":div(sum(f),3),"per_class":per,"supported_precision":per["SUPPORTED"]["precision"],"unsupported_recall":per["UNSUPPORTED"]["recall"],"abstention_precision":div(sum(x["gold_label"]=="PARTIAL" for x in abst),len(abst)),"abstention_recall":div(sum(x["predicted_label"]=="PARTIAL" for x in gold_abst),len(gold_abst)),"human_review_rate":div(len(abst),n),"automation_coverage":div(n-len(abst),n),"unsafe_acceptance_rate":div(len(unsafe),sum(x["gold_label"] in {"PARTIAL","UNSUPPORTED"} for x in predictions)),"unsafe_acceptance_count":len(unsafe)}
    errors=[x for x in predictions if x["gold_label"]!=x["predicted_label"]]
    return metrics,matrix,predictions,errors
def main(dataset:Path, metadata:Path, output:Path, summary:Path):
    if output.exists():
        raise FileExistsError(f"blind result is immutable and already exists: {output}")
    checked=validate(dataset,metadata)
    if checked["status"]!="valid": raise SystemExit(json.dumps(checked,ensure_ascii=False))
    rows=[json.loads(x) for x in dataset.read_text(encoding="utf-8").splitlines() if x.strip()]
    metrics,matrix,predictions,errors=score(rows); by=defaultdict(list)
    for x in predictions: by[x["challenge_type"]].append(x)
    challenge_metrics={}
    for typ,items in sorted(by.items()): challenge_metrics[typ]={"count":len(items),"metrics":_metrics_only(items)}
    report={"metadata":{"judge":"evidence_judge_v1","dataset":"eval/judge/claim_evidence_generalization_v1.jsonl","dataset_sha256":checked["dataset_sha256"],"case_count":len(rows),"blind_run":True,"blind_result_immutable":True,"controlled_benchmark_report":"eval/experiments/evidence_judge_v1_20260823/results.json"},"metrics":metrics,"confusion_matrix":matrix,"challenge_type_metrics":challenge_metrics,"errors":errors,"predictions":predictions}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Evidence Judge Generalization v1 (blind)","",f"Dataset SHA256: `{checked['dataset_sha256']}`",f"Samples: {len(rows)}", "", "## Metrics", "", "| Metric | Value |", "|---|---:|"]
    for k in ("accuracy","macro_f1","supported_precision","unsupported_recall","unsafe_acceptance_rate","human_review_rate","automation_coverage"): lines.append(f"| {k} | {metrics[k]:.6f} |")
    lines += ["", "## Naturalistic Challenge Types", "", "| Type | Count | Accuracy |", "|---|---:|---:|"]
    for typ,v in challenge_metrics.items(): lines.append(f"| {typ} | {v['count']} | {v['metrics']['accuracy']:.6f} |")
    lines += ["",f"Errors: {len(errors)}", "", "## Blind Failure Analysis", ""]
    for x in errors: lines.append(f"- `{x['case_id']}` gold={x['gold_label']} predicted={x['predicted_label']} reason={x['reason_code']} type={x['challenge_type']}")
    lines += ["", "Controlled benchmark v1 metrics remain separate and are referenced without aggregation.", "No Judge v2 changes were implemented."]
    summary.parent.mkdir(parents=True,exist_ok=True); summary.write_text("\n".join(lines)+"\n",encoding="utf-8")
def _metrics_only(items):
    m={g:{p:0 for p in LABELS} for g in LABELS}
    for x in items:m[x["gold_label"]][x["predicted_label"]]+=1
    correct=sum(m[l][l] for l in LABELS); per={}
    for l in LABELS:
        tp=m[l][l]; fp=sum(m[g][l] for g in LABELS if g!=l); fn=sum(m[l][p] for p in LABELS if p!=l)
        pr=div(tp,tp+fp); re=div(tp,tp+fn); per[l]={"precision":pr,"recall":re,"f1":div(2*pr*re,pr+re),"support":sum(m[l].values())}
    return {"accuracy":div(correct,len(items)),"per_class":per,"confusion_matrix":m}
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--dataset",type=Path,required=True); p.add_argument("--metadata",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--summary",type=Path,required=True); a=p.parse_args(); main(a.dataset,a.metadata,a.output,a.summary)
