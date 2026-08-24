from __future__ import annotations
import argparse, hashlib, json
from collections import Counter
from pathlib import Path
REQUIRED={"case_id","document_id","risk_type","claim","evidence_text","evidence_id","evidence_span","gold_label","review_status","annotation_notes","challenge_type","sample_provenance"}
LABELS={"SUPPORTED","PARTIAL","UNSUPPORTED"}
TYPES={"paraphrase_synonym","implicit_entity_coreference","chinese_numeral_or_amount","cross_sentence_qualifier","complex_negation_exception","implicit_risk_inference","multi_evidence_support","conflicting_evidence","semantically_related_but_insufficient"}
def validate(dataset:Path, metadata:Path):
    rows=[json.loads(x) for x in dataset.read_text(encoding="utf-8").splitlines() if x.strip()]; meta=json.loads(metadata.read_text(encoding="utf-8")); errors=[]
    ids=[]
    for n,r in enumerate(rows,1):
        ids.append(r.get("case_id")); miss=REQUIRED-set(r); errors += [f"line {n}: missing {x}" for x in sorted(miss)]
        if r.get("gold_label") not in LABELS: errors.append(f"line {n}: invalid label")
        if r.get("review_status") != "reviewed": errors.append(f"line {n}: not reviewed")
        if r.get("challenge_type") not in TYPES: errors.append(f"line {n}: invalid challenge_type")
        if not str(r.get("evidence_text") or "").strip(): errors.append(f"line {n}: empty evidence")
        if r.get("evidence_span",{}).get("text") != r.get("evidence_text"): errors.append(f"line {n}: evidence span mismatch")
        if not r.get("sample_provenance",{}).get("source_case_id"): errors.append(f"line {n}: missing provenance")
    digest=hashlib.sha256(dataset.read_bytes()).hexdigest(); labels=dict(Counter(r.get("gold_label") for r in rows)); types=dict(Counter(r.get("challenge_type") for r in rows))
    if len(ids)!=len(set(ids)): errors.append("duplicate case_id")
    if meta.get("dataset_sha256") != digest: errors.append("dataset_sha256 mismatch")
    if meta.get("label_distribution") != labels: errors.append("label_distribution mismatch")
    return {"status":"valid" if not errors else "invalid","case_count":len(rows),"dataset_sha256":digest,"reviewed_count":sum(r.get("review_status")=="reviewed" for r in rows),"draft_count":sum(r.get("review_status")=="draft" for r in rows),"label_distribution":labels,"challenge_type_distribution":types,"errors":errors}
if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--dataset",type=Path,required=True); p.add_argument("--metadata",type=Path,required=True); a=p.parse_args(); result=validate(a.dataset,a.metadata); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result["status"] == "valid" else 1)
