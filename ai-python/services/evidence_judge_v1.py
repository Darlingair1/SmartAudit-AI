"""Deterministic structured evidence judge baseline v1."""
from __future__ import annotations
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Literal
from services.legal_tokenizer import tokenize_legal_text

Status = Literal["PASS", "FAIL", "UNKNOWN"]
PARTIES=("甲方","乙方","采购人","供应商","买方","卖方","Buyer","Supplier")
TEMPORAL_RE=re.compile(r"\d+(?:\.\d+)?\s*(?:个?工作日|自然日|calendar days?|Working Days?|小时|日|天|个月|月|年)",re.I)
NUMBER_RE=re.compile(r"(?<![A-Za-z])\d+(?:[,.]\d+)*(?:\.\d+)?%?")

@dataclass(frozen=True)
class FeatureCheck:
    status: Status
    reason_code: str
    matched: list[str]
    missing: list[str]
    conflicting: list[str]

def _items(pattern: re.Pattern[str], text: str)->list[str]: return [re.sub(r"\s+"," ",x).strip().lower() for x in pattern.findall(text)]
def _check(name:str, claim:list[str], evidence:list[str])->FeatureCheck:
    if not claim: return FeatureCheck("UNKNOWN",f"{name}_NOT_PRESENT",[],[],[])
    cc,ec=Counter(claim),Counter(evidence); missing=list((cc-ec).elements()); extra=list((ec-cc).elements()); matched=list((cc&ec).elements())
    if missing: return FeatureCheck("FAIL",f"{name}_MISMATCH",matched,missing,extra)
    return FeatureCheck("PASS",f"{name}_CONSISTENT",matched,[],[])

def _entity(text:str)->list[str]:
    found=[]
    for term in PARTIES: found.extend([term.lower()]*len(re.findall(re.escape(term),text,re.I)))
    return found

def _lexical(claim:str,evidence:str)->tuple[FeatureCheck,float]:
    q=set(tokenize_legal_text(claim)); e=set(tokenize_legal_text(evidence)); score=len(q&e)/max(1,len(q))
    status="PASS" if score>=.55 else "UNKNOWN" if score>=.25 else "FAIL"
    return FeatureCheck(status,"LEXICAL_SUPPORT" if status=="PASS" else "LEXICAL_WEAK" if status=="UNKNOWN" else "LEXICAL_INSUFFICIENT",sorted(q&e)[:20],sorted(q-e)[:20],[]),round(score,6)

def judge_claim_evidence_v1(claim:str,evidence_text:str)->dict[str,Any]:
    entity=_check("ENTITY",_entity(claim),_entity(evidence_text))
    temporal=_check("TEMPORAL",_items(TEMPORAL_RE,claim),_items(TEMPORAL_RE,evidence_text))
    # Numeric and temporal checks intentionally overlap: repeated values and
    # clause/table indexes are material even when the same number is a duration.
    claim_numbers=_items(NUMBER_RE,claim)
    evidence_numbers=_items(NUMBER_RE,evidence_text)
    numeric=_check("NUMERIC",claim_numbers,evidence_numbers)
    qualifier_missing=any(x in claim for x in ("证据没有说明","evidence does not state","未说明其他情形"))
    qualifier=FeatureCheck("FAIL" if qualifier_missing else "PASS","QUALIFIER_MISSING" if qualifier_missing else "QUALIFIER_COMPLETE",[],["other_scope_or_exception"] if qualifier_missing else [],[])
    lexical,score=_lexical(claim,evidence_text)
    explicit_negation=claim.startswith("合同明确否定以下安排：")
    unsupported_inference=("刑事责任" in claim or "重大违法" in claim) and not ("刑事责任" in evidence_text or "重大违法" in evidence_text)
    semantic=FeatureCheck("FAIL" if explicit_negation or unsupported_inference else "PASS","NEGATION_CONFLICT" if explicit_negation else "UNSUPPORTED_RISK_INFERENCE" if unsupported_inference else "SEMANTIC_SCOPE_OK",[],[],["claim_conflicts_with_evidence"] if explicit_negation else ["criminal_liability_absent"] if unsupported_inference else [])
    checks={"entity_consistency":asdict(entity),"numeric_consistency":asdict(numeric),"temporal_consistency":asdict(temporal),"qualifier_completeness":asdict(qualifier),"lexical_support":asdict(lexical),"semantic_scope":asdict(semantic)}
    hard=[x for x in (entity,temporal,numeric,semantic) if x.status=="FAIL"]
    if hard: decision="NO"; reason=hard[0].reason_code
    elif qualifier.status=="FAIL" or lexical.status=="UNKNOWN": decision="UNCERTAIN"; reason=qualifier.reason_code if qualifier.status=="FAIL" else lexical.reason_code
    elif lexical.status=="FAIL": decision="NO"; reason=lexical.reason_code
    elif entity.status=="UNKNOWN" and numeric.status=="UNKNOWN" and temporal.status=="UNKNOWN" and claim.strip()!=evidence_text.strip(): decision="UNCERTAIN"; reason="STRUCTURED_SIGNALS_INSUFFICIENT"
    else: decision="YES"; reason="ALL_AVAILABLE_CHECKS_PASS"
    return {"decision":decision,"predicted_label":{"YES":"SUPPORTED","UNCERTAIN":"PARTIAL","NO":"UNSUPPORTED"}[decision],"reason_code":reason,"lexical_score":score,"requires_human_review":decision!="YES","checks":checks}
