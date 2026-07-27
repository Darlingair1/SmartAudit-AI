from __future__ import annotations

from typing import Any, Dict, List

from services.legal_tokenizer import tokenize_legal_text
from services.v3_types import JudgeResult, RetrievalCandidate

REASON_CODES = {
    "LOW_RELEVANCE",
    "NO_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "OUT_OF_SCOPE",
    "FORMAT_INVALID",
    "CLAUSE_NOT_FOUND",
    "WEAK_EVIDENCE",
    "EVIDENCE_TOO_BROAD",
    "PAGE_MISMATCH",
    "AMBIGUOUS_SUBJECT",
    "PARTY_MISMATCH",
    "NEGATION_CONFLICT",
    "TIME_CONDITION_MISMATCH",
    "AMOUNT_CONDITION_MISMATCH",
    "CONDITION_MISMATCH",
    "TABLE_PARSE_UNCERTAIN",
    "APPENDIX_REFERENCE_MISSING",
}


def _overlap_score(query: str, snippet: str) -> float:
    q = set(tokenize_legal_text(query))
    s = set(tokenize_legal_text(snippet))
    if not q or not s:
        return 0.0
    return len(q & s) / max(1, len(q))


def judge_evidence_support(
    *,
    query: str,
    risk_type: str,
    candidates: List[RetrievalCandidate],
    settings: Any,
) -> JudgeResult:
    if not candidates:
        return JudgeResult(
            decision="NO",
            confidence=0.92,
            reason_code="NO_EVIDENCE",
            reason="未检索到可支持该风险判断的证据",
            supporting_evidence_ids=[],
            missing_evidence_hint=f"补充与[{risk_type}]相关的条款证据",
            requires_human_review=True,
        )

    top_n = max(1, int(getattr(settings, "judge_top_n", 8)))
    scoped = candidates[:top_n]
    scores = [_overlap_score(query, x.snippet) for x in scoped]
    best = max(scores) if scores else 0.0
    avg = sum(scores) / max(1, len(scores))
    conf = min(0.99, max(0.01, 0.6 * best + 0.4 * avg))

    if best >= 0.55:
        decision = "YES"
        code = "LOW_RELEVANCE" if avg < 0.35 else "WEAK_EVIDENCE"
        reason = "证据与风险语义相关，可用于复核"
        need_review = avg < 0.4
    elif best >= 0.25:
        decision = "UNCERTAIN"
        code = "WEAK_EVIDENCE"
        reason = "存在部分相关证据，但支持强度不足"
        need_review = True
    else:
        decision = "NO"
        code = "NO_EVIDENCE"
        reason = "候选证据与风险相关性过低"
        need_review = True

    if code not in REASON_CODES:
        code = "FORMAT_INVALID"

    return JudgeResult(
        decision=decision,  # type: ignore[arg-type]
        confidence=round(conf, 4),
        reason_code=code,
        reason=reason,
        supporting_evidence_ids=[x.candidate_id for x in scoped[: max(1, min(3, len(scoped)))]],
        missing_evidence_hint="" if decision == "YES" else f"补充涉及[{risk_type}]的直接条款原文",
        requires_human_review=need_review,
    )


def apply_judge_policy(
    *,
    mode: str,
    reject_policy: str,
    judge_result: JudgeResult,
) -> Dict[str, Any]:
    mode = (mode or "observe").strip().lower()
    reject_policy = (reject_policy or "soft").strip().lower()

    if mode == "observe":
        return {"keep": True, "tag": "JUDGE_OBSERVE", "requires_human_review": judge_result.requires_human_review}
    if mode == "soft_gate":
        if judge_result.decision == "NO":
            return {"keep": True, "tag": "EVIDENCE_INSUFFICIENT", "requires_human_review": True}
        if judge_result.decision == "UNCERTAIN":
            return {"keep": True, "tag": "NEED_REVIEW", "requires_human_review": True}
        return {"keep": True, "tag": "SUPPORTED", "requires_human_review": judge_result.requires_human_review}

    # strict gate
    if judge_result.decision == "NO" and reject_policy == "strict":
        return {"keep": False, "tag": "REJECTED_BY_JUDGE", "requires_human_review": True}
    return {"keep": True, "tag": "STRICT_PASS", "requires_human_review": judge_result.requires_human_review}

