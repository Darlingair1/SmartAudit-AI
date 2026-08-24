from __future__ import annotations
import hashlib,json
from collections import Counter
from pathlib import Path
import argparse

REQUIRED={"case_id","document_id","risk_type","claim","evidence_text","evidence_id","evidence_span","gold_label","review_status","annotation_notes"}
LABELS={"SUPPORTED","PARTIAL","UNSUPPORTED"}; STATUSES={"reviewed","draft"}

def validate(dataset: Path, metadata: Path) -> dict:
    rows=[json.loads(x) for x in dataset.read_text(encoding="utf-8").splitlines() if x.strip()]
    meta=json.loads(metadata.read_text(encoding="utf-8")); errors=[]; ids=[]
    for number,row in enumerate(rows,1):
        missing=REQUIRED-set(row); errors.extend(f"line {number}: missing {x}" for x in sorted(missing)); ids.append(row.get("case_id"))
        if row.get("gold_label") not in LABELS: errors.append(f"line {number}: invalid gold_label")
        if row.get("review_status") not in STATUSES: errors.append(f"line {number}: invalid review_status")
        for key in ("case_id","document_id","claim","evidence_text","evidence_id","annotation_notes"):
            if not str(row.get(key) or "").strip(): errors.append(f"line {number}: empty {key}")
        if row.get("evidence_span",{}).get("text") != row.get("evidence_text"): errors.append(f"line {number}: evidence span mismatch")
        if "audit_status" in row and row["audit_status"] not in {"KEEP","RELABEL","REWRITE","DROP"}: errors.append(f"line {number}: invalid audit_status")
    if len(ids)!=len(set(ids)): errors.append("duplicate case_id")
    digest=hashlib.sha256(dataset.read_bytes()).hexdigest()
    expected_hash=meta.get("dataset_sha256") or meta.get("audited_dataset_sha256")
    if expected_hash!=digest: errors.append("dataset_sha256 mismatch")
    distribution=dict(Counter(x.get("gold_label") for x in rows))
    if meta.get("label_distribution")!=distribution: errors.append("label_distribution mismatch")
    return {"status":"valid" if not errors else "invalid","case_count":len(rows),"dataset_sha256":digest,"label_distribution":distribution,"reviewed_count":sum(x.get("review_status")=="reviewed" for x in rows),"draft_count":sum(x.get("review_status")=="draft" for x in rows),"errors":errors}

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--dataset",type=Path,required=True); parser.add_argument("--metadata",type=Path,required=True); args=parser.parse_args(); result=validate(args.dataset,args.metadata); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result["status"]=="valid" else 1)
