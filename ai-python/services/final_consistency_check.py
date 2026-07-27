from __future__ import annotations

import re
from typing import Any, Dict, List

from services.legal_tokenizer import tokenize_legal_text
from services.v3_types import ClaimCheck, FinalCheckResult, RetrievalCandidate


def _split_claims(risk_desc: str, suggestion: str, excerpt: str) -> List[str]:
    raw = "。".join([risk_desc or "", suggestion or "", excerpt or ""])
    raw = re.sub(r"\s+", " ", raw)
    parts = re.split(r"[。！？!?;\n]", raw)
    claims: List[str] = []
    for p in parts:
        p = p.strip()
        if len(p) >= 8:
            claims.append(p[:200])
    if not claims and excerpt:
        claims = [excerpt[:200]]
    return claims[:6]


def _claim_score(claim: str, evidence: str) -> float:
    c = set(tokenize_legal_text(claim))
    e = set(tokenize_legal_text(evidence))
    if not c or not e:
        return 0.0
    return len(c & e) / max(1, len(c))


def run_claim_level_final_check(
    *,
    risk_item: Dict[str, Any],
    evidence_candidates: List[RetrievalCandidate],
) -> FinalCheckResult:
    claims = _split_claims(
        str(risk_item.get("riskDesc") or ""),
        str(risk_item.get("suggestion") or ""),
        str(risk_item.get("contractExcerpt") or ""),
    )
    results: List[ClaimCheck] = []
    unsupported_claims: List[str] = []

    for idx, claim in enumerate(claims, start=1):
        scored = []
        for cand in evidence_candidates[:8]:
            s = _claim_score(claim, cand.snippet)
            scored.append((s, cand))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][0] if scored else 0.0
        top_ids = [x[1].candidate_id for x in scored[:2] if x[0] > 0]
        if best >= 0.5:
            status = "SUPPORTED"
            code = "OK"
        elif best >= 0.25:
            status = "WEAK_SUPPORTED"
            code = "WEAK_EVIDENCE"
        else:
            status = "UNSUPPORTED"
            code = "NO_EVIDENCE"
            unsupported_claims.append(claim)

        results.append(
            ClaimCheck(
                claim_id=f"claim-{idx}",
                claim_text=claim,
                support_status=status,  # type: ignore[arg-type]
                supporting_evidence_ids=top_ids,
                reason_code=code,
            )
        )

    if not results:
        return FinalCheckResult(
            claims=[],
            overall_support_status="UNSUPPORTED",
            unsupported_claims=[],
            requires_human_review=True,
        )

    if any(x.support_status == "UNSUPPORTED" for x in results):
        overall = "UNSUPPORTED"
    elif any(x.support_status == "WEAK_SUPPORTED" for x in results):
        overall = "WEAK_SUPPORTED"
    else:
        overall = "SUPPORTED"

    return FinalCheckResult(
        claims=results,
        overall_support_status=overall,  # type: ignore[arg-type]
        unsupported_claims=unsupported_claims,
        requires_human_review=(overall != "SUPPORTED"),
    )

