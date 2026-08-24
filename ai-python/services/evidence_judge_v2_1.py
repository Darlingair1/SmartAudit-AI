"""One-shot safety hardening of evidence judge v2.

This module preserves v2 and adds only sufficiency/contradiction arbitration.
It does not expand semantic recall, aliases, normalization, or synonyms.
"""
from __future__ import annotations
import re
from typing import Any
from services.evidence_judge_v2 import judge_claim_evidence_v2

EN_STOP={"what","when","which","where","who","how","does","must","may","the","and","or","to","of","a","an","is","are","be","it","then","any","under","after","before","with","for","from","into","according","contract"}
ZH_MATERIAL=("付款","期限","价款","金额","比例","条件","预付款","验收","交付","延期","违约","责任","保证金","保密","披露","解除","终止","数据","删除","迁出","故障","响应","恢复","知识产权","发票","暂停","赔偿","通知","质保","争议")

def material_anchors(text:str)->set[str]:
    english={x.lower() for x in re.findall(r"[A-Za-z]{3,}",text) if x.lower() not in EN_STOP}
    chinese={x for x in ZH_MATERIAL if x in text}
    return english|chinese

def _segment_coverage(claim:str,evidence:str)->dict[str,Any]:
    segments=[x.strip() for x in re.split(r"[？?；;]|\b(?:and|then)\b|以及|并且|分别",claim,flags=re.I) if x.strip()]
    evidence_lower=evidence.lower(); details=[]
    for segment in segments:
        anchors=material_anchors(segment); matched=sorted(x for x in anchors if x.lower() in evidence_lower); ratio=len(matched)/max(1,len(anchors))
        if anchors: details.append({"segment":segment,"anchors":sorted(anchors),"matched":matched,"coverage":round(ratio,6)})
    return {"segments":details,"missing_segments":[x["segment"] for x in details if x["coverage"]<0.5]}

def judge_claim_evidence_v2_1(claim:str,evidence_text:str,evidence_ids:list[str]|None=None)->dict[str,Any]:
    result=judge_claim_evidence_v2(claim,evidence_text,evidence_ids); coverage=float(result["coverage"]["coverage"]); anchors=material_anchors(claim); matched=sorted(x for x in anchors if x.lower() in evidence_text.lower()); anchor_coverage=len(matched)/max(1,len(anchors)); segment=_segment_coverage(claim,evidence_text)
    guard=result["checks"]["deterministic_guards"]
    if guard["status"]=="FAIL":
        label="UNSUPPORTED"; reason="CONFLICT_DETECTED"
    elif coverage < 0.075 and anchor_coverage < 0.5:
        label="UNSUPPORTED"; reason="SEMANTIC_RELEVANCE_NOT_SUFFICIENCY"
    elif result["predicted_label"]=="SUPPORTED" and (anchor_coverage < 0.5 or segment["missing_segments"]):
        label="PARTIAL"; reason="MISSING_MATERIAL_ELEMENT"
    else:
        label=result["predicted_label"]; reason=result["reason_code"]
    result.update({"predicted_label":label,"decision":{"SUPPORTED":"YES","PARTIAL":"UNCERTAIN","UNSUPPORTED":"NO"}[label],"reason_code":reason,"requires_human_review":label!="SUPPORTED"})
    result["safety_arbitration"]={"anchor_coverage":round(anchor_coverage,6),"anchors":sorted(anchors),"matched_anchors":matched,"segment_coverage":segment,"veto_applied":label!=result["checks"]["semantic_sufficiency"].get("predicted_label",result.get("predicted_label")),"reason_code":reason}
    return result
