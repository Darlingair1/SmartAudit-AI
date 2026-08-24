from __future__ import annotations
import argparse,hashlib,json,subprocess
from collections import Counter,defaultdict
from pathlib import Path
from eval.judge.evaluate_evidence_judge_v0 import evaluate as eval_v0
from eval.judge.validate_generalization_benchmark import validate

LABELS=("SUPPORTED","PARTIAL","UNSUPPORTED")
def div(a,b): return round(a/b,6) if b else 0.0
def metrics(rows):
    m={g:{p:0 for p in LABELS} for g in LABELS}
    for x in rows:m[x["gold_label"]][x["predicted_label"]]+=1
    per={}; fs=[]
    for l in LABELS:
        tp=m[l][l]; fp=sum(m[g][l] for g in LABELS if g!=l); fn=sum(m[l][p] for p in LABELS if p!=l); p=div(tp,tp+fp); r=div(tp,tp+fn); f=div(2*p*r,p+r); per[l]={"precision":p,"recall":r,"f1":f,"support":sum(m[l].values())}; fs.append(f)
    n=len(rows); partial=sum(x["predicted_label"]=="PARTIAL" for x in rows); supported=[x for x in rows if x["gold_label"]=="SUPPORTED"]; unsafe=[x for x in rows if x["gold_label"] in {"PARTIAL","UNSUPPORTED"} and x["predicted_label"]=="SUPPORTED"]; nonpartial=[x for x in rows if x["predicted_label"]!="PARTIAL"]
    return {"accuracy":div(sum(x["gold_label"]==x["predicted_label"] for x in rows),n),"macro_f1":div(sum(fs),3),"per_class":per,"supported_precision":per["SUPPORTED"]["precision"],"supported_recall":per["SUPPORTED"]["recall"],"partial_f1":per["PARTIAL"]["f1"],"unsupported_recall":per["UNSUPPORTED"]["recall"],"unsafe_acceptance_rate":div(len(unsafe),sum(x["gold_label"] in {"PARTIAL","UNSUPPORTED"} for x in rows)),"supported_false_rejection_rate":div(sum(x["gold_label"]=="SUPPORTED" and x["predicted_label"]!="SUPPORTED" for x in rows),len(supported)),"hard_false_rejection_rate":div(sum(x["gold_label"]=="SUPPORTED" and x["predicted_label"]=="UNSUPPORTED" for x in rows),len(supported)),"human_review_rate":div(partial,n),"automation_coverage":div(n-partial,n),"selective_accuracy":div(sum(x["gold_label"]==x["predicted_label"] for x in nonpartial),len(nonpartial)),"confusion_matrix":m}
def normalize_v0(rows): return rows
def main(dataset,metadata,v1_result,v2_result,out,summary):
    check=validate(dataset,metadata)
    if check["status"]!="valid": raise ValueError(check["errors"])
    v0=eval_v0(dataset,metadata)["predictions"]; v1=json.loads(v1_result.read_text(encoding="utf8"))["predictions"]; v2=json.loads(v2_result.read_text(encoding="utf8"))["predictions"]
    source_rows=[json.loads(x) for x in dataset.read_text(encoding="utf8").splitlines() if x.strip()]
    type_by_id={x["case_id"]:x["challenge_type"] for x in source_rows}
    for rows in (v0,v1,v2):
        for x in rows: x.setdefault("challenge_type",type_by_id.get(x["case_id"],"other"))
    by1={x["case_id"]:x for x in v1}; by2={x["case_id"]:x for x in v2}; transitions=[]
    for x in v0:
        y=by1[x["case_id"]]; z=by2[x["case_id"]]; transitions.append({"case_id":x["case_id"],"gold":x["gold_label"],"v0_prediction":x["predicted_label"],"v1_prediction":y["predicted_label"],"v2_prediction":z["predicted_label"],"v2_feature_result":z.get("feature_result"),"reason_codes":[x.get("reason_code"),y.get("reason_code"),z.get("reason_code")],"used_evidence_ids":z.get("feature_result",{}).get("used_evidence_ids",[])})
    provenance=json.loads(metadata.read_text(encoding="utf-8-sig")); root=Path(__file__).parents[2]; repo_root=root.parent; commit=subprocess.check_output(["git","-c",f"safe.directory={repo_root.as_posix()}","rev-parse","HEAD"],cwd=repo_root,text=True).strip(); cfg={"semantic":"normalization+concept_coverage+guards","thresholds":{"supported":0.42,"partial":0.16},"model":None}; fp=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    report={"provenance":{"dataset_sha256":check["dataset_sha256"],"dataset_source_commit":provenance["source_commit_sha"],"judge_implementation_commit_sha":commit,"evaluator_config":cfg,"evaluator_config_fingerprint":fp,"v0_file_sha256":hashlib.sha256((root/"services/evidence_judge.py").read_bytes()).hexdigest(),"v1_file_sha256":hashlib.sha256((root/"services/evidence_judge_v1.py").read_bytes()).hexdigest(),"v2_file_sha256":hashlib.sha256((root/"services/evidence_judge_v2.py").read_bytes()).hexdigest()},"metrics":{"v0":metrics(v0),"v1":metrics(v1),"v2":metrics(v2)},"predictions":{"v0":v0,"v1":v1,"v2":v2},"transitions":transitions,"transition_summary":{"v1_wrong_v2_correct":sum(x["v1_prediction"]!=x["gold"] and x["v2_prediction"]==x["gold"] for x in transitions),"v1_correct_v2_wrong":sum(x["v1_prediction"]==x["gold"] and x["v2_prediction"]!=x["gold"] for x in transitions),"supported_false_rejection_repaired":sum(x["gold"]=="SUPPORTED" and x["v1_prediction"]!="SUPPORTED" and x["v2_prediction"]=="SUPPORTED" for x in transitions),"partial_correctly_recovered":sum(x["gold"]=="PARTIAL" and x["v1_prediction"]!="PARTIAL" and x["v2_prediction"]=="PARTIAL" for x in transitions),"new_unsafe_acceptance":sum(x["gold"] in {"PARTIAL","UNSUPPORTED"} and x["v1_prediction"]!="SUPPORTED" and x["v2_prediction"]=="SUPPORTED" for x in transitions),"unsupported_upgraded_to_supported":sum(x["gold"]=="UNSUPPORTED" and x["v2_prediction"]=="SUPPORTED" for x in transitions)},"failure_type_metrics":{}}
    controlled=json.loads((root/"eval/experiments/evidence_judge_v1_20260823/results.json").read_text(encoding="utf8"))
    report["controlled_v1"]={"case_count":controlled["metadata"]["case_count"],"metrics":controlled["metrics"],"confusion_matrix":controlled["confusion_matrix"]}
    for typ in sorted({x["challenge_type"] for x in v0}):
        report["failure_type_metrics"][typ]={"count":sum(x["challenge_type"]==typ for x in v0),"v0":metrics([x for x in v0 if x["challenge_type"]==typ]),"v1":metrics([x for x in v1 if x["challenge_type"]==typ]),"v2":metrics([x for x in v2 if x["challenge_type"]==typ])}
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    lines=["# Evidence Judge v0/v1/v2 Development Comparison","",f"Dataset SHA256: `{check['dataset_sha256']}`","", "| Metric | v0 | v1 | v2 |", "|---|---:|---:|---:|"]
    for key in ("accuracy","macro_f1","supported_precision","supported_recall","partial_f1","unsupported_recall","unsafe_acceptance_rate","supported_false_rejection_rate","hard_false_rejection_rate","human_review_rate","automation_coverage","selective_accuracy"):
        lines.append(f"| {key} | {report['metrics']['v0'][key]:.6f} | {report['metrics']['v1'][key]:.6f} | {report['metrics']['v2'][key]:.6f} |")
    lines += ["", "## Transition Summary", "", json.dumps(report["transition_summary"],ensure_ascii=False,indent=2), "", "## Failure Types", "", "| Type | Count | v0 Acc | v1 Acc | v2 Acc |", "|---|---:|---:|---:|---:|"]
    for typ,data in report["failure_type_metrics"].items(): lines.append(f"| {typ} | {data['count']} | {data['v0']['accuracy']:.6f} | {data['v1']['accuracy']:.6f} | {data['v2']['accuracy']:.6f} |")
    lines += ["", "Semantic implementation: model-free normalization, alias/concept coverage, multi-evidence concatenation, and deterministic conflict guards. No LLM/service invocation; latency/cost are local deterministic inference with zero timeout/error/fallback.", "", "No Judge v3 or external holdout was created."]
    summary.parent.mkdir(parents=True,exist_ok=True); summary.write_text("\n".join(lines)+"\n",encoding="utf8")
if __name__=="__main__":
    p=argparse.ArgumentParser();
    for name in ("dataset","metadata","v1_result","v2_result","out","summary"): p.add_argument("--"+name.replace("_","-"),type=Path,required=True)
    a=p.parse_args(); main(a.dataset,a.metadata,a.v1_result,a.v2_result,a.out,a.summary)
