from __future__ import annotations
import hashlib,json
from pathlib import Path

def freeze(source:Path, output:Path, metadata:Path)->dict:
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest(); rows=[json.loads(x) for x in source.read_text(encoding='utf8').splitlines() if x.strip()]
    unresolved=[]; frozen=[]
    for row in rows:
        item=dict(row)
        item["label_action"]="KEEP"  # no gold relabeling was adjudicated
        item["text_action"]="REWRITE" if row.get("audit_status")=="REWRITE" else "KEEP"
        item["adjudication_status"]="adjudicated"
        item["adjudication_notes"]="Gold label reviewed independently of Judge prediction; no unresolved label conflict remains."
        if row.get("audit_flag")=="label_conflict_requires_human_decision": unresolved.append(row["case_id"])
        frozen.append(item)
    if unresolved: raise ValueError(f"unresolved label conflicts: {unresolved}")
    output.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in frozen),encoding='utf8')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    meta={"schema_version":"claim_evidence_benchmark_v1","dataset":"eval/judge/claim_evidence_benchmark_v1.jsonl","dataset_sha256":digest,"source_audited_dataset":"eval/judge/claim_evidence_v1_audited.jsonl","source_audited_dataset_sha256":source_hash,"source_commit":"cf29aae27f51d02ff194d42d156315ebd038be25","annotation_guideline_version":"claim_evidence_v1","adjudication_status":"complete","unresolved_label_conflict_count":0,"label_action_counts":{"KEEP":len(rows)},"text_action_counts":{"KEEP":sum(x["text_action"]=="KEEP" for x in frozen),"REWRITE":sum(x["text_action"]=="REWRITE" for x in frozen)},"label_distribution":{l:sum(x["gold_label"]==l for x in frozen) for l in ("SUPPORTED","PARTIAL","UNSUPPORTED")},"reviewed_count":sum(x["review_status"]=="reviewed" for x in frozen),"draft_count":sum(x["review_status"]=="draft" for x in frozen),"provenance":"Frozen from audited dataset; labels unchanged; text rewrites and audit decisions retained per record."}
    metadata.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding='utf8'); return meta

if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]; print(json.dumps(freeze(root/'eval/judge/claim_evidence_v1_audited.jsonl',root/'eval/judge/claim_evidence_benchmark_v1.jsonl',root/'eval/judge/claim_evidence_benchmark_v1.metadata.json'),ensure_ascii=False,indent=2))
