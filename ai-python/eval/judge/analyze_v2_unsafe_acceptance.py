from __future__ import annotations
import argparse,json
from pathlib import Path

def category(row):
    typ=row.get("challenge_type")
    if typ=="conflicting_evidence": return "CONTRADICTION_PRECEDENCE_FAILURE"
    if typ=="semantically_related_but_insufficient": return "SEMANTIC_RELEVANCE_NOT_SUFFICIENCY"
    if typ=="multi_evidence_support": return "OVER_AGGREGATION"
    if typ in {"cross_sentence_qualifier","complex_negation_exception"}: return "MISSING_QUALIFIER_ACCEPTED"
    return "OTHER"

def main(comparison:Path,output:Path):
    data=json.loads(comparison.read_text(encoding="utf8")); records=[]
    for row in data["transitions"]:
        if row["gold"] not in {"PARTIAL","UNSUPPORTED"} or row["v2_prediction"]!="SUPPORTED": continue
        feature=row.get("v2_feature_result") or {}; coverage=feature.get("coverage",{}); checks=feature.get("checks",{}); semantic=checks.get("semantic_sufficiency",{})
        source=next(x for x in data["predictions"]["v2"] if x["case_id"]==row["case_id"])
        records.append({"case_id":row["case_id"],"gold":row["gold"],"v1_prediction":row["v1_prediction"],"v2_prediction":row["v2_prediction"],"challenge_type":source.get("challenge_type"),"used_evidence_ids":row.get("used_evidence_ids",[]),"supported_elements":coverage.get("matched",[]),"missing_elements":coverage.get("missing",[]),"conflicting_elements":semantic.get("conflicting",[]),"reason_codes":row.get("reason_codes",[]),"root_cause_category":category(source)})
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps({"taxonomy":["CONTRADICTION_PRECEDENCE_FAILURE","SEMANTIC_RELEVANCE_NOT_SUFFICIENCY","MISSING_QUALIFIER_ACCEPTED","CROSS_EVIDENCE_CONFLICT_MISSED","OVER_AGGREGATION","OTHER"],"count":len(records),"cases":records},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--comparison",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(); main(a.comparison,a.output)
