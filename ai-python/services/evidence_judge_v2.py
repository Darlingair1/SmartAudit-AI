"""Deterministic semantic/hybrid evidence judge v2.

The semantic layer is deliberately model-free: contract concept aliases,
number/amount normalization, entity aliases, and evidence coverage are kept in
one normalization module. It is not a replacement for an LLM entailment model.
"""
from __future__ import annotations
import re
from dataclasses import asdict, dataclass
from typing import Any

from services.evidence_judge_v1 import _entity, _items, NUMBER_RE, TEMPORAL_RE
from services.legal_tokenizer import tokenize_legal_text

CN_DIGITS={"零":0,"〇":0,"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}
ALIASES={"付款期限":"付款","支付期限":"付款","付款时间":"付款","付清":"付款","违约金":"违约","赔偿":"责任","交付":"到货","供货":"到货","验收通过":"验收","试运行":"验收","解除合同":"解除","终止合同":"解除","秘密":"保密","工作秘密":"保密","服务期限":"期限","合同期限":"期限","供应商":"乙方","采购人":"甲方","买方":"甲方","卖方":"乙方","无回复":"未回复","没有回复":"未回复"}
STOP=set("什么 是否 哪些 如何 分几个 分别 约定 可以 需要 时候 时 应当 能够 情况 下 发生 合同 条款 怎么样".split())

def chinese_number(s:str)->int|None:
    if s.isdigit(): return int(s)
    if s in CN_DIGITS: return CN_DIGITS[s]
    total=0; current=0
    units={"十":10,"百":100,"千":1000,"万":10000}
    for ch in s:
        if ch in CN_DIGITS: current=CN_DIGITS[ch]
        elif ch in units:
            unit=units[ch]; current=current or 1; total += current*unit; current=0
        else: return None
    return total+current if total or current else None

def normalize_numbers(text:str)->list[str]:
    text=text.replace(",","").replace("，","")
    out=[]
    for m in re.finditer(r"\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万]+",text):
        raw=m.group(); value=chinese_number(raw)
        if value is not None: out.append(str(value))
    for m in re.finditer(r"百分之([零〇一二两三四五六七八九十百千万]+)|(?<!\w)(\d+(?:\.\d+)?)%",text):
        value=chinese_number(m.group(1)) if m.group(1) else float(m.group(2)); out.append(f"pct:{value:g}")
    return out

def normalize_concepts(text:str)->set[str]:
    value=text.lower()
    for src,dst in sorted(ALIASES.items(),key=lambda x:-len(x[0])): value=value.replace(src,dst)
    tokens=set(tokenize_legal_text(value))
    tokens |= {x for x in re.findall(r"[\u4e00-\u9fff]{2,8}|[a-z]{2,}|\d+",value) if x not in STOP}
    return tokens

@dataclass(frozen=True)
class Guard:
    status:str; reason_code:str; matched:list[str]; missing:list[str]; conflicting:list[str]

def _guard(claim,evidence)->Guard:
    cn=set(normalize_numbers(claim)); en=set(normalize_numbers(evidence)); conflict=sorted(x for x in cn if x not in en and (x.startswith("pct:") or x.isdigit()) and any(y.isdigit() or y.startswith("pct:") for y in en))
    if conflict and any(x in claim for x in ("%","百分之","日","天","工作日","小时","金额","价款")):
        return Guard("FAIL","EXPLICIT_NUMERIC_OR_TEMPORAL_CONFLICT",sorted(cn&en),sorted(cn-en),conflict)
    if any(x in claim for x in ("明确否定","不是","不得","不视为")) and not any(x in evidence for x in ("不","不得","未","除外")):
        return Guard("FAIL","EXPLICIT_NEGATION_CONFLICT",[],["negation_scope"],[claim])
    return Guard("PASS","DETERMINISTIC_GUARDS_PASS",sorted(cn&en),[],[])

def judge_claim_evidence_v2(claim:str,evidence_text:str,evidence_ids:list[str]|None=None)->dict[str,Any]:
    guard=_guard(claim,evidence_text); c=normalize_concepts(claim); e=normalize_concepts(evidence_text); matched=sorted(c&e); missing=sorted(c-e)
    coverage=len(matched)/max(1,len(c)); lexical=len(set(tokenize_legal_text(claim))&set(tokenize_legal_text(evidence_text)))/max(1,len(set(tokenize_legal_text(claim))))
    if guard.status=="FAIL": label="UNSUPPORTED"; reason=guard.reason_code
    elif coverage>=0.42 or (coverage>=0.25 and lexical>=0.2): label="SUPPORTED"; reason="SEMANTIC_CONCEPTS_COVERED"
    elif coverage>=0.16 or lexical>=0.15: label="PARTIAL"; reason="INSUFFICIENT_EVIDENCE_COVERAGE"
    else: label="PARTIAL"; reason="SEMANTIC_INSUFFICIENT"
    return {"predicted_label":label,"decision":{"SUPPORTED":"YES","PARTIAL":"UNCERTAIN","UNSUPPORTED":"NO"}[label],"confidence":round(min(0.99,max(0.05,coverage)),6),"reason_code":reason,"used_evidence_ids":evidence_ids or ["evidence:0"],"coverage":{"claim_concepts":sorted(c),"matched":matched,"missing":missing,"coverage":round(coverage,6),"lexical_overlap":round(lexical,6)},"checks":{"deterministic_guards":asdict(guard),"normalization":{"claim_numbers":normalize_numbers(claim),"evidence_numbers":normalize_numbers(evidence_text)},"semantic_sufficiency":{"status":"PASS" if label=="SUPPORTED" else "UNKNOWN","reason_code":reason,"matched":matched,"missing":missing,"conflicting":guard.conflicting}},"requires_human_review":label!="SUPPORTED"}

def aggregate_evidence(claim:str,evidence_items:list[dict[str,Any]])->dict[str,Any]:
    text="\n".join(x.get("text","") for x in evidence_items)
    return judge_claim_evidence_v2(claim,text,[x.get("evidence_id",f"evidence:{i}") for i,x in enumerate(evidence_items)])
