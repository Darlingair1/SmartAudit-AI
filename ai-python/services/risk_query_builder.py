from __future__ import annotations

from typing import Any, Dict, List

from services.legal_tokenizer import expand_query_with_synonyms

TEMPLATES: Dict[str, List[str]] = {
    "LIABILITY_CAP": ["赔偿责任 上限", "责任限制 间接损失 可得利益", "无限责任 连带责任", "违约责任 损失赔偿"],
    "TERMINATION": ["单方解除 合同终止", "提前终止 解除权", "无理由解除", "解除通知期限"],
    "AUTO_RENEWAL": ["自动续期", "期满续展", "未提前通知 自动延长", "续约 续签"],
    "JURISDICTION": ["管辖法院", "争议解决", "仲裁委员会", "适用法律"],
    "PAYMENT": ["付款周期", "付款条件", "分期付款", "验收后付款"],
    "CONFIDENTIALITY": ["保密义务", "商业秘密", "信息披露 限制", "保密期限"],
}


def _normalize_risk_type(value: str) -> str:
    val = str(value or "").strip().upper()
    return val or "UNKNOWN"


def _extract_seed_query(item: Dict[str, Any]) -> str:
    risk_type = str(item.get("riskType") or "")
    clause_title = str(item.get("clauseTitle") or "")
    risk_desc = str(item.get("riskDesc") or "")
    seed = " ".join([risk_type, clause_title, risk_desc]).strip()
    return seed[:200]


def _zh_fallback_templates(seed_text: str) -> List[str]:
    out: List[str] = []
    if any(x in seed_text for x in ["违约", "赔偿", "责任上限"]):
        out.extend(TEMPLATES["LIABILITY_CAP"])
    if any(x in seed_text for x in ["解除", "终止"]):
        out.extend(TEMPLATES["TERMINATION"])
    if any(x in seed_text for x in ["续约", "续期", "自动延长"]):
        out.extend(TEMPLATES["AUTO_RENEWAL"])
    if any(x in seed_text for x in ["管辖", "仲裁", "争议"]):
        out.extend(TEMPLATES["JURISDICTION"])
    if any(x in seed_text for x in ["付款", "账期", "结算"]):
        out.extend(TEMPLATES["PAYMENT"])
    if any(x in seed_text for x in ["保密", "商业秘密", "披露"]):
        out.extend(TEMPLATES["CONFIDENTIALITY"])
    return out


def build_risk_queries(draft_item: Dict[str, Any], template_version: str = "v1") -> Dict[str, Any]:
    risk_type = _normalize_risk_type(str(draft_item.get("riskType") or "UNKNOWN"))
    seed = _extract_seed_query(draft_item)
    expanded: List[str] = []

    if risk_type in TEMPLATES:
        expanded.extend(TEMPLATES[risk_type])

    expanded.extend(_zh_fallback_templates(str(draft_item.get("riskType") or "")))
    expanded.extend(_zh_fallback_templates(str(draft_item.get("riskDesc") or "")))
    if seed:
        expanded.append(seed)
        expanded.extend(expand_query_with_synonyms(seed))

    seen = set()
    dedup: List[str] = []
    for q in expanded:
        q = str(q or "").strip()
        if len(q) < 2 or q in seen:
            continue
        seen.add(q)
        dedup.append(q)

    return {
        "risk_type": risk_type,
        "original_query": seed,
        "expanded_queries": dedup,
        "query_strategy": "template|synonym",
        "version": f"risk_query_template_{template_version}",
    }

