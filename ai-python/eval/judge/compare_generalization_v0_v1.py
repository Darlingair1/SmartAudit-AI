"""Fresh v0 versus immutable blind v1 comparison on one frozen dataset."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from collections import Counter
from pathlib import Path
from eval.judge.evaluate_evidence_judge_v0 import evaluate as evaluate_v0
from eval.judge.validate_generalization_benchmark import validate

LABELS=("SUPPORTED","PARTIAL","UNSUPPORTED")
def div(a,b): return round(a/b,6) if b else 0.0

def unified(result):
    rows=result["predictions"]; n=len(rows); matrix={g:{p:0 for p in LABELS} for g in LABELS}
    for x in rows: matrix[x["gold_label"]][x["predicted_label"]]+=1
    per={}; f1=[]
    for l in LABELS:
        tp=matrix[l][l]; fp=sum(matrix[g][l] for g in LABELS if g!=l); fn=sum(matrix[l][p] for p in LABELS if p!=l)
        p=div(tp,tp+fp); r=div(tp,tp+fn); f=div(2*p*r,p+r); per[l]={"precision":p,"recall":r,"f1":f,"support":sum(matrix[l].values())}; f1.append(f)
    supported=[x for x in rows if x["gold_label"]=="SUPPORTED"]
    non_partial=[x for x in rows if x["predicted_label"]!="PARTIAL"]
    unsafe=[x for x in rows if x["gold_label"] in {"PARTIAL","UNSUPPORTED"} and x["predicted_label"]=="SUPPORTED"]
    unsafe_den=sum(x["gold_label"] in {"PARTIAL","UNSUPPORTED"} for x in rows)
    # Keep the benchmark's existing operational convention: PARTIAL is an
    # abstention requiring review; SUPPORTED/UNSUPPORTED are automated outputs.
    review_count=sum(x["predicted_label"]=="PARTIAL" for x in rows)
    return {"accuracy":div(sum(x["gold_label"]==x["predicted_label"] for x in rows),n),"macro_f1":div(sum(f1),3),"per_class":per,"supported_precision":per["SUPPORTED"]["precision"],"supported_recall":per["SUPPORTED"]["recall"],"unsupported_recall":per["UNSUPPORTED"]["recall"],"partial_f1":per["PARTIAL"]["f1"],"abstention_precision":div(sum(x["gold_label"]=="PARTIAL" for x in rows if x["predicted_label"]=="PARTIAL"),review_count),"abstention_recall":div(sum(x["predicted_label"]=="PARTIAL" for x in rows if x["gold_label"]=="PARTIAL"),sum(x["gold_label"]=="PARTIAL" for x in rows)),"human_review_rate":div(review_count,n),"automation_coverage":div(n-review_count,n),"unsafe_acceptance_rate":div(len(unsafe),unsafe_den),"supported_false_rejection_rate":div(sum(x["gold_label"]=="SUPPORTED" and x["predicted_label"]!="SUPPORTED" for x in rows),len(supported)),"hard_false_rejection_rate":div(sum(x["gold_label"]=="SUPPORTED" and x["predicted_label"]=="UNSUPPORTED" for x in rows),len(supported)),"selective_accuracy":div(sum(x["gold_label"]==x["predicted_label"] for x in non_partial),len(non_partial))}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main(dataset,metadata,v1_result,output,summary):
    checked=validate(dataset,metadata)
    if checked["status"]!="valid": raise ValueError(checked["errors"])
    v0=evaluate_v0(dataset,metadata)
    blind=json.loads(v1_result.read_text(encoding="utf-8"))
    if blind["metadata"]["dataset_sha256"]!=checked["dataset_sha256"]: raise ValueError("v1 result dataset mismatch")
    # Preserve the original v1 prediction rows and calculate the same metrics
    # from them; do not execute or overwrite the blind result.
    v1={"predictions":blind["predictions"]}
    root=Path(__file__).parents[2]
    repo_root=root.parent
    try: commit=subprocess.check_output(["git","-c",f"safe.directory={repo_root.as_posix()}","rev-parse","HEAD"],cwd=repo_root,text=True).strip()
    except Exception: commit="unknown"
    config={"label_mapping":{"YES":"SUPPORTED","UNCERTAIN":"PARTIAL","NO":"UNSUPPORTED"},"v0_settings":{"judge_top_n":8},"metrics":"unified_v1"}
    config_fingerprint=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    provenance={"dataset_sha256":checked["dataset_sha256"],"dataset_source_commit":json.loads(metadata.read_text(encoding="utf-8-sig"))["source_commit_sha"],"judge_implementation_commit_sha":commit,"evaluator_config":config,"evaluator_config_fingerprint":config_fingerprint,"v0_implementation_file_sha256":sha(root/"services/evidence_judge.py"),"v1_implementation_file_sha256":sha(root/"services/evidence_judge_v1.py"),"v1_blind_result_sha256":sha(v1_result)}
    controlled=json.loads((root/"eval/experiments/evidence_judge_v1_20260823/results.json").read_text(encoding="utf-8"))
    report={"provenance":provenance,"dataset":{"path":"eval/judge/claim_evidence_generalization_v1.jsonl","case_count":checked["case_count"]},"generalization":{"v0":{"metrics":unified(v0),"confusion_matrix":v0["confusion_matrix"],"predictions":v0["predictions"]},"v1":{"metrics":unified(v1),"confusion_matrix":blind["confusion_matrix"],"predictions":blind["predictions"]}},"controlled_v1":{"metrics":controlled["metrics"],"confusion_matrix":controlled["confusion_matrix"],"case_count":controlled["metadata"]["case_count"]}}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Evidence Judge v0/v1 Generalization Comparison","",f"Dataset SHA256: `{checked['dataset_sha256']}`",f"Dataset source commit: `{provenance['dataset_source_commit']}`",f"Judge implementation commit SHA: `{commit}`",f"Evaluator config fingerprint: `{config_fingerprint}`","", "## Generalization Dataset", "", "| Metric | v0 | v1 |", "|---|---:|---:|"]
    keys=("accuracy","macro_f1","supported_precision","supported_recall","unsupported_recall","partial_f1","supported_false_rejection_rate","hard_false_rejection_rate","selective_accuracy","unsafe_acceptance_rate","human_review_rate","automation_coverage")
    for k in keys: lines.append(f"| {k} | {report['generalization']['v0']['metrics'][k]:.6f} | {report['generalization']['v1']['metrics'][k]:.6f} |")
    lines += ["", "## Generalization Confusion Matrices", "", "v0:", "```json", json.dumps(v0["confusion_matrix"],ensure_ascii=False), "```", "v1:", "```json", json.dumps(blind["confusion_matrix"],ensure_ascii=False), "```", "", "## Controlled Benchmark V1 (separate)", "", "Controlled V1 metrics and matrix are copied from the frozen report and are not pooled with generalization metrics.", "", "## Provenance", "", f"- v0 implementation file SHA256: `{provenance['v0_implementation_file_sha256']}`", f"- v1 implementation file SHA256: `{provenance['v1_implementation_file_sha256']}`", f"- immutable blind v1 result SHA256: `{provenance['v1_blind_result_sha256']}`"]
    summary.parent.mkdir(parents=True,exist_ok=True); summary.write_text("\n".join(lines)+"\n",encoding="utf-8")
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--dataset",type=Path,required=True); p.add_argument("--metadata",type=Path,required=True); p.add_argument("--v1-result",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--summary",type=Path,required=True); a=p.parse_args(); main(a.dataset,a.metadata,a.v1_result,a.output,a.summary)
