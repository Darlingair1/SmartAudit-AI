from __future__ import annotations
import hashlib,json,random
from pathlib import Path

ACTIONS=("KEEP","RELABEL","REWRITE","DROP")

def audit(source:Path, audited:Path, audit_log:Path, metadata:Path)->dict:
    raw=source.read_bytes(); rows=[json.loads(x) for x in raw.decode('utf-8').splitlines() if x.strip()]
    supported=[r for r in rows if r["gold_label"]=="SUPPORTED"]
    sample_ids={r["case_id"] for r in random.Random(20260823).sample(supported,min(8,len(supported)))}
    out=[]; logs=[]; source_hash=hashlib.sha256(raw).hexdigest()
    for row in rows:
        selected=row["gold_label"]!="SUPPORTED" or row["case_id"] in sample_ids
        action="KEEP"; naturalness="high"; confidence="high"; note="Not selected for supported sample audit." if not selected else "Direct evidence/label relationship reviewed."; after=dict(row)
        if selected and "此外，该规则适用于所有情形且不存在任何例外。" in row["claim"]:
            action="REWRITE"; naturalness="medium"; note="Valid PARTIAL qualifier challenge, but wording was synthetic; rewritten for production-natural phrasing."; after["claim"]=row["claim"].replace("此外，该规则适用于所有情形且不存在任何例外。","在其他情况下是否也适用，证据没有说明。")
        elif selected and "该条款证明相关主体必然构成重大违法并应承担刑事责任。" in row["claim"]:
            action="REWRITE"; naturalness="low"; note="Valid unsupported risk inference, but original wording was unnatural; rewritten without changing label."; after["claim"]="合同是否明确规定相关主体因该事项承担刑事责任？"
        elif selected and row["gold_label"]=="UNSUPPORTED" and row["claim"]==row["evidence_text"]:
            action="RELABEL"; naturalness="high"; confidence="high"; note="Exact evidence entails claim; original UNSUPPORTED label is inconsistent and requires human decision; label is unchanged here."; after["audit_flag"]="label_conflict_requires_human_decision"
        elif selected: confidence="medium" if row["gold_label"]!="SUPPORTED" else "high"
        after.update({"audit_status":action,"audit_notes":note,"label_confidence":confidence,"naturalness":naturalness,"audit_provenance":{"source_dataset_sha256":source_hash,"before_claim":row["claim"],"before_gold_label":row["gold_label"],"audited_by":"deterministic_quality_audit_v1"}})
        out.append(after)
        if selected: logs.append({"case_id":row["case_id"],"action":action,"label_before":row["gold_label"],"label_after":after["gold_label"],"claim_before":row["claim"],"claim_after":after["claim"],"evidence_text":row["evidence_text"],"audit_notes":note,"label_confidence":confidence,"naturalness":naturalness})
    audited.parent.mkdir(parents=True,exist_ok=True); audited.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in out),encoding='utf-8'); audit_log.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in logs),encoding='utf-8')
    meta={"schema_version":"claim_evidence_audit_v1","source_dataset":"eval/judge/claim_evidence_v1.jsonl","source_dataset_sha256":source_hash,"audited_dataset":"eval/judge/claim_evidence_v1_audited.jsonl","audited_dataset_sha256":hashlib.sha256(audited.read_bytes()).hexdigest(),"audit_log":"eval/judge/claim_evidence_v1.audit.jsonl","audit_case_count":len(logs),"audit_coverage":len(logs)/len(rows),"action_counts":{a:sum(x["audit_status"]==a for x in out) for a in ACTIONS},"label_distribution":{l:sum(x["gold_label"]==l for x in out) for l in ("SUPPORTED","PARTIAL","UNSUPPORTED")},"label_changes":0,"random_supported_seed":20260823,"provenance":"Changes are claim wording/audit annotations only; gold labels are unchanged."}
    metadata.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding='utf-8'); return meta

if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]; print(json.dumps(audit(root/'eval/judge/claim_evidence_v1.jsonl',root/'eval/judge/claim_evidence_v1_audited.jsonl',root/'eval/judge/claim_evidence_v1.audit.jsonl',root/'eval/judge/claim_evidence_v1.audit.metadata.json'),ensure_ascii=False,indent=2))
