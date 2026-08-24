from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from pathlib import Path

DEVELOPMENT_DOCUMENTS={"synthetic-contract-smoke","synthetic_purchase_contract_001","synthetic_software_service_contract_001","public_jiyuan_vehicle_procurement_2024_245_a","public_guangdong_tax_e_tax_development_2023_gpcgd23c500fg157f","public_uk_dwp_dos010_curam_technical_architect_2017"}
LABELS={"SUPPORTED","PARTIAL","UNSUPPORTED"}
TAGS={"paraphrase","multi_evidence","implicit_entity","numeric_or_amount","temporal","qualifier_or_exception","conflicting_evidence","implicit_risk_inference","semantically_related_but_insufficient","other"}
REQUIRED={"case_id","document_id","risk_type","claim","evidence","gold_label","review_status","annotation_notes","challenge_tags","source_pipeline_provenance","initial_label","adjudicated_label","adjudication_notes","label_confidence"}
FORBIDDEN_PROVENANCE={"controlled_perturbation","entity_replacement","number_replacement","date_replacement","keyword_replacement","synthetic_negative"}

def validate(dataset:Path,metadata:Path,root:Path)->dict:
    errors=[]
    try: rows=[json.loads(x) for x in dataset.read_text(encoding="utf8").splitlines() if x.strip()]
    except Exception as exc: return {"status":"invalid","errors":[f"dataset read error: {exc}"]}
    meta=json.loads(metadata.read_text(encoding="utf-8-sig")); ids=[]
    documents={x["document_id"]:x for x in meta.get("source_documents",[])}
    for n,row in enumerate(rows,1):
        ids.append(row.get("case_id")); errors += [f"line {n}: missing {x}" for x in sorted(REQUIRED-set(row))]
        if row.get("document_id") in DEVELOPMENT_DOCUMENTS: errors.append(f"line {n}: development document forbidden")
        if row.get("document_id") not in documents: errors.append(f"line {n}: document absent from metadata")
        if row.get("gold_label") not in LABELS or row.get("adjudicated_label")!=row.get("gold_label"): errors.append(f"line {n}: invalid/adjudication label mismatch")
        if row.get("initial_label") not in LABELS: errors.append(f"line {n}: invalid initial_label")
        if row.get("review_status")!="reviewed": errors.append(f"line {n}: not reviewed")
        if row.get("annotation_status") in {"unresolved","draft"} or row.get("unresolved_conflict"): errors.append(f"line {n}: unresolved annotation")
        evidence=row.get("evidence");
        if not isinstance(evidence,list) or not evidence: errors.append(f"line {n}: evidence must be non-empty array")
        else:
            for i,item in enumerate(evidence):
                if not str(item.get("evidence_id") or "").strip() or not str(item.get("text") or "").strip(): errors.append(f"line {n}: invalid evidence {i}")
        tags=row.get("challenge_tags")
        if not isinstance(tags,list) or any(x not in TAGS for x in tags): errors.append(f"line {n}: invalid challenge tags")
        provenance=row.get("source_pipeline_provenance") or {}
        if not provenance.get("pipeline_run_id") or not provenance.get("claim_source") or not provenance.get("retrieval_source"): errors.append(f"line {n}: incomplete pipeline provenance")
        serialized=json.dumps(provenance,ensure_ascii=False).lower()
        if any(x in serialized for x in FORBIDDEN_PROVENANCE): errors.append(f"line {n}: controlled perturbation forbidden")
    if len(ids)!=len(set(ids)): errors.append("duplicate case_id")
    for doc_id,doc in documents.items():
        if doc_id in DEVELOPMENT_DOCUMENTS: errors.append(f"metadata: development document forbidden: {doc_id}")
        path=doc.get("repository_path")
        if path:
            target=root/path
            if not target.is_file(): errors.append(f"metadata: missing document: {doc_id}")
            elif hashlib.sha256(target.read_bytes()).hexdigest()!=doc.get("document_hash"): errors.append(f"metadata: document hash mismatch: {doc_id}")
        elif not doc.get("source_url"): errors.append(f"metadata: document has neither repository_path nor source_url: {doc_id}")
    digest=hashlib.sha256(dataset.read_bytes()).hexdigest(); labels=dict(Counter(x.get("gold_label") for x in rows)); doc_dist=dict(Counter(x.get("document_id") for x in rows)); tag_dist=dict(Counter(t for x in rows for t in x.get("challenge_tags",[])))
    if meta.get("dataset_sha256")!=digest: errors.append("dataset SHA256 mismatch")
    if meta.get("reviewed_count")!=len(rows) or meta.get("draft_count")!=0 or meta.get("unresolved_count")!=0: errors.append("freeze status counts invalid")
    if meta.get("label_distribution")!=labels or meta.get("document_distribution")!=doc_dist or meta.get("challenge_type_distribution")!=tag_dist: errors.append("metadata distribution mismatch")
    if meta.get("adjudication_status")!="complete": errors.append("adjudication incomplete")
    return {"status":"valid" if not errors else "invalid","case_count":len(rows),"dataset_sha256":digest,"label_distribution":labels,"document_distribution":doc_dist,"challenge_type_distribution":tag_dist,"errors":errors}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--dataset",type=Path,required=True); p.add_argument("--metadata",type=Path,required=True); p.add_argument("--root",type=Path,required=True); a=p.parse_args(); result=validate(a.dataset,a.metadata,a.root); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result["status"]=="valid" else 1)
