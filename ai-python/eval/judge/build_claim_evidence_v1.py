from __future__ import annotations
import hashlib, json, re, subprocess
from collections import Counter
from pathlib import Path

LABELS = ("SUPPORTED", "PARTIAL", "UNSUPPORTED")

def _unsupported(text: str, index: int) -> tuple[str, str]:
    if index % 5 == 0:
        return "该条款证明相关主体必然构成重大违法并应承担刑事责任。", "unsupported_risk_inference"
    if index % 3 == 0 and re.search(r"\d+.*(?:日|天|月|年|Working Days|calendar days)", text, re.I):
        match = re.search(r"\d+", text)
        assert match is not None
        return text[:match.start()] + str(int(match.group()) + 1) + text[match.end():], "temporal_mismatch"
    swaps = (("甲方", "乙方"), ("乙方", "甲方"), ("Buyer", "Supplier"), ("Supplier", "Buyer"), ("采购人", "供应商"), ("供应商", "采购人"))
    for old, new in swaps:
        if old in text:
            return text.replace(old, new, 1), "wrong_entity"
    match = re.search(r"\d+", text)
    if match:
        value = str(int(match.group()) + 1)
        return text[:match.start()] + value + text[match.end():], "numeric_mismatch"
    return f"合同明确否定以下安排：{text}", "semantic_overlap_but_insufficient"

def build(source: Path, output: Path, metadata_path: Path) -> None:
    source_rows=[json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    reviewed=[row for row in source_rows if row.get("metadata",{}).get("annotation_status")=="reviewed"]
    rows=[]
    for index,row in enumerate(reviewed,1):
        evidence=row["expected_evidence"][0]
        base={"document_id":row["document_id"],"risk_type":row.get("risk_type") or "UNSPECIFIED","evidence_text":evidence["text"],"evidence_id":f"{row['case_id']}:gold:0","evidence_span":{"page":evidence.get("page"),"text":evidence["text"]},"review_status":"reviewed"}
        rows.append({**base,"case_id":f"judge_v1_{index:03d}_supported","claim":evidence["text"],"gold_label":"SUPPORTED","annotation_notes":"Direct claim copied from reviewed retrieval gold; controlled positive pair."})
        rows.append({**base,"case_id":f"judge_v1_{index:03d}_partial","claim":f"{evidence['text']} 此外，该规则适用于所有情形且不存在任何例外。","gold_label":"PARTIAL","annotation_notes":"Evidence supports the base fact but not the added universal/no-exception qualifier; failure_mode=missing_qualifier."})
        claim,mode=_unsupported(evidence["text"], index)
        rows.append({**base,"case_id":f"judge_v1_{index:03d}_unsupported","claim":claim,"gold_label":"UNSUPPORTED","annotation_notes":f"Controlled hard negative preserving lexical overlap; failure_mode={mode}."})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text("".join(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n" for row in rows),encoding="utf-8")
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    repo_root = source.parents[3]
    try: commit=subprocess.check_output(["git","-c",f"safe.directory={repo_root.as_posix()}","rev-parse","HEAD"],cwd=repo_root,text=True).strip()
    except Exception: commit=""
    metadata={"schema_version":"claim_evidence_v1","dataset":"eval/judge/claim_evidence_v1.jsonl","dataset_sha256":digest,"source_dataset":"eval/datasets/rag_eval_dev_v1.jsonl","source_dataset_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"source_commit":commit,"case_count":len(rows),"label_distribution":dict(Counter(x["gold_label"] for x in rows)),"reviewed_count":sum(x["review_status"]=="reviewed" for x in rows),"draft_count":sum(x["review_status"]=="draft" for x in rows),"construction":"Three controlled pairs per reviewed retrieval case using its first human-reviewed gold evidence."}
    metadata_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]
    build(root/"eval/datasets/rag_eval_dev_v1.jsonl",root/"eval/judge/claim_evidence_v1.jsonl",root/"eval/judge/claim_evidence_v1.metadata.json")
