from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Sequence

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ConfigDict, Field

from core.config import Settings, get_settings
from schemas.models import AuditJobRequest, CallbackSummary, RiskItem
from services.budget_controller import RiskBudget, budget_metrics_aggregate, build_risk_budget
from services.evidence_judge import JudgeResult, apply_judge_policy, judge_evidence_support
from services.final_consistency_check import run_claim_level_final_check
from services.parser_quality_gate import analyze_parser_quality
from services.retrieval_hybrid import (
    _index_vector_children,
    build_parent_child_chunks,
    retrieve_hybrid_for_risk,
)
from services.reranker import rerank_candidates
from services.risk_query_builder import build_risk_queries
from services.security_context import build_security_context
from services.trace_compliance import persist_trace_event
from services.v3_types import RetrievalCandidate, SecurityContext
from services.llm_client import InjectableLLM, build_openai_llm

logger = logging.getLogger("smartaudit.ai.v3")


class _DraftRiskItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clauseTitle: str | None = None
    riskType: str | None = None
    riskLevel: str | None = None
    pageNo: int | None = None
    contractExcerpt: str | None = None
    riskDesc: str | None = None
    suggestion: str | None = None


class _DraftOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    draftRiskItems: List[_DraftRiskItem] = Field(default_factory=list)


class _RiskItemOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seqNo: int = Field(..., ge=1)
    riskType: str
    riskLevel: str
    riskScore: float | None = Field(default=None, ge=0, le=100)
    clauseTitle: str | None = None
    clausePosition: str | None = None
    pageNo: int = Field(default=1, ge=1)
    contractExcerpt: str
    riskDesc: str | None = None
    suggestion: str
    legalBasis: str | None = None
    evidence: str | None = None


class _SummaryOut(BaseModel):
    riskTotal: int = Field(..., ge=0)
    highRiskCount: int = Field(..., ge=0)
    mediumRiskCount: int = Field(..., ge=0)
    lowRiskCount: int = Field(..., ge=0)


class _AuditOutput(BaseModel):
    summary: _SummaryOut
    riskItems: List[_RiskItemOut]


def _build_llm(settings: Settings, model_name: str, temperature: float) -> InjectableLLM:
    return build_openai_llm(
        model=model_name,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        retries=settings.llm_max_retries,
    )


def _normalize_level(value: Any) -> str:
    val = str(value or "").strip().upper()
    if val in {"HIGH", "MEDIUM", "LOW"}:
        return val
    mapping = {"高": "HIGH", "中": "MEDIUM", "低": "LOW"}
    return mapping.get(val, "LOW")


def _normalize_page_no(value: Any, default: int = 1) -> int:
    try:
        page = int(str(value or "").strip())
        return page if page >= 1 else default
    except Exception:
        return default


def _build_chunk_ranges(total_pages: int, chunk_pages: int, overlap_pages: int) -> List[tuple[int, int]]:
    if total_pages <= 0:
        return []
    c = max(1, chunk_pages)
    o = max(0, min(overlap_pages, c - 1))
    step = max(1, c - o)
    ranges: List[tuple[int, int]] = []
    start = 1
    while start <= total_pages:
        end = min(total_pages, start + c - 1)
        ranges.append((start, end))
        if end >= total_pages:
            break
        start += step
    return ranges


def _build_chunk_text(page_texts: Sequence[str], start_page: int, end_page: int) -> str:
    blocks: List[str] = []
    for page_no in range(start_page, end_page + 1):
        txt = str(page_texts[page_no - 1] or "").strip()
        if not txt:
            continue
        blocks.append(f"[Page {page_no}]\n{txt}")
    return "\n\n".join(blocks).strip()


def _draft_item_to_dict(item: _DraftRiskItem, page_default: int) -> Dict[str, Any]:
    excerpt = str(item.contractExcerpt or "").strip()
    return {
        "clauseTitle": str(item.clauseTitle or "").strip() or None,
        "riskType": str(item.riskType or "").strip() or "UNKNOWN",
        "riskLevel": _normalize_level(item.riskLevel),
        "pageNo": _normalize_page_no(item.pageNo, default=page_default),
        "contractExcerpt": excerpt,
        "riskDesc": str(item.riskDesc or "").strip() or None,
        "suggestion": str(item.suggestion or "").strip() or None,
    }


def _dedupe_draft_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        excerpt = str(it.get("contractExcerpt") or "").strip()
        if not excerpt:
            continue
        key = (
            str(it.get("riskType") or "").strip().upper(),
            str(it.get("clauseTitle") or "").strip(),
            _normalize_page_no(it.get("pageNo"), 1),
            re.sub(r"\s+", "", excerpt[:80]),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


async def _run_agent1_map_stage(
    *,
    job_request: AuditJobRequest,
    page_texts: Sequence[str],
    settings: Settings,
) -> tuple[List[Dict[str, Any]], List[tuple[int, int]], int, int]:
    total_pages = len(page_texts)
    chunk_ranges = _build_chunk_ranges(
        total_pages=total_pages,
        chunk_pages=max(1, settings.map_chunk_pages),
        overlap_pages=max(0, settings.map_chunk_overlap_pages),
    )
    parser = JsonOutputParser(pydantic_object=_DraftOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一名初级企业法务（Draft Extractor）。"
                "仅基于当前页码区间提取疑似风险，宁可多提不要漏掉。"
                "必须只输出 JSON，顶层字段 draftRiskItems（数组）。"
                "pageNo 必须使用 [Page X] 的整数；contractExcerpt 必须原文摘录。",
            ),
            (
                "human",
                "任务信息：\n"
                "- taskId: {task_id}\n"
                "- taskNo: {task_no}\n"
                "- chunkIndex: {chunk_index}\n"
                "- chunkPageRange: {chunk_page_range}\n\n"
                "合同区间正文：\n{contract_text}\n\n"
                "请输出草稿 JSON，字段尽量包含："
                "clauseTitle、riskType、riskLevel、pageNo、contractExcerpt、riskDesc、suggestion。\n"
                "{format_instructions}",
            ),
        ]
    )
    llm = _build_llm(settings, model_name=job_request.modelName or settings.default_model, temperature=0.1)
    chain = prompt.partial(format_instructions=parser.get_format_instructions()) | llm | parser

    sem = asyncio.Semaphore(max(1, settings.map_max_concurrency))
    raw_items: List[Dict[str, Any]] = []

    async def _run_one(chunk_index: int, start_page: int, end_page: int) -> List[Dict[str, Any]]:
        chunk_text = _build_chunk_text(page_texts, start_page, end_page)
        if not chunk_text:
            return []
        payload = {
            "task_id": job_request.taskId,
            "task_no": job_request.taskNo,
            "chunk_index": chunk_index,
            "chunk_page_range": f"{start_page}-{end_page}",
            "contract_text": chunk_text,
        }
        last_err: Exception | None = None
        for attempt in (1, 2):
            try:
                res = await chain.ainvoke(payload)
                vals = res.get("draftRiskItems") or []
                arr: List[Dict[str, Any]] = []
                for v in vals:
                    try:
                        obj = _DraftRiskItem.model_validate(v)
                    except Exception:
                        continue
                    arr.append(_draft_item_to_dict(obj, page_default=start_page))
                return arr
            except Exception as ex:  # noqa: PERF203
                last_err = ex
                if attempt == 1:
                    await asyncio.sleep(0.4)
        raise RuntimeError(f"map chunk failed: {chunk_index}({start_page}-{end_page})") from last_err

    async def _guarded(coro: Any) -> Any:
        async with sem:
            return await coro

    tasks = [
        asyncio.create_task(_guarded(_run_one(idx, s, e)))
        for idx, (s, e) in enumerate(chunk_ranges, start=1)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for idx, r in enumerate(results, start=1):
        if isinstance(r, Exception):
            raise RuntimeError(f"agent1 map failed at chunk={idx}") from r
        raw_items.extend(r)

    dedup = _dedupe_draft_items(raw_items)
    material_risk_cap = max(4, min(50, max(total_pages * 4, len(dedup) // 2 + 2)))
    high_risk_cap = max(1, min(material_risk_cap, int(material_risk_cap * 0.45 + 0.999)))
    logger.info(
        "V3 Agent1 completed, raw=%d dedup=%d pages=%d chunks=%d",
        len(raw_items),
        len(dedup),
        total_pages,
        len(chunk_ranges),
    )
    return dedup, chunk_ranges, material_risk_cap, high_risk_cap


def _candidate_key(risk_type: str, clause_title: str) -> tuple[str, str]:
    return (str(risk_type or "").strip().upper(), str(clause_title or "").strip().lower())


def _compact_json(value: Dict[str, Any], max_chars: int = 3000) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...(truncated)"


def _to_review_context(
    *,
    page_texts: Sequence[str],
    draft_items: Sequence[Dict[str, Any]],
    evidence_blocks: Sequence[str],
    max_chars: int,
) -> str:
    max_chars = max(5000, max_chars)
    page_set = sorted(
        {
            _normalize_page_no(x.get("pageNo"), 1)
            for x in draft_items
            if x.get("pageNo") is not None
        }
    )
    if not page_set:
        page_set = list(range(1, min(len(page_texts), 10) + 1))

    blocks: List[str] = []
    used = 0
    for p in page_set:
        if p < 1 or p > len(page_texts):
            continue
        txt = str(page_texts[p - 1] or "").strip()
        if not txt:
            continue
        block = f"[Page {p}]\n{txt[:1000]}"
        extra = len(block) + (2 if blocks else 0)
        if used + extra > max_chars:
            break
        blocks.append(block)
        used += extra

    if evidence_blocks and used < max_chars:
        remain = max_chars - used
        rag = "\n\n".join(evidence_blocks)
        rag = rag[:remain]
        if rag.strip():
            blocks.append(f"[RAG Evidence Context]\n{rag.strip()}")
    return "\n\n".join(blocks).strip()


async def _run_agent2_review_stage(
    *,
    job_request: AuditJobRequest,
    page_texts: Sequence[str],
    draft_items: Sequence[Dict[str, Any]],
    review_context: str,
    chunk_count: int,
    material_risk_cap: int,
    high_risk_cap: int,
    settings: Settings,
) -> List[RiskItem]:
    parser = JsonOutputParser(pydantic_object=_AuditOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一名高级企业法务合伙人。"
                "请审查初审草稿并结合证据上下文，完成去伪存真、去重合并、风险分级。"
                "硬约束："
                "1) contractExcerpt 必须为原文摘录；"
                "2) pageNo 为整数；"
                "3) riskLevel 仅可 HIGH/MEDIUM/LOW；"
                "4) 输出必须是 JSON。",
            ),
            (
                "human",
                "全量覆盖说明：Map 阶段已覆盖合同全部页面。"
                "totalPages={total_pages}, chunkCount={chunk_count}\n"
                "约束：draftCount={draft_count}, materialRiskCap={material_risk_cap}, highRiskCap={high_risk_cap}\n\n"
                "证据上下文：\n{review_context}\n\n"
                "初审草稿：\n{draft_json}\n\n"
                "{format_instructions}",
            ),
        ]
    )
    strict_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是严格 JSON 审核器。"
                "只输出合法 JSON；禁止 markdown；字段必须符合 schema。"
                "无法确认的风险请删除，避免幻觉。",
            ),
            (
                "human",
                "totalPages={total_pages}, chunkCount={chunk_count}\n"
                "draftCount={draft_count}, materialRiskCap={material_risk_cap}, highRiskCap={high_risk_cap}\n\n"
                "证据上下文：\n{review_context}\n\n"
                "初审草稿：\n{draft_json}\n\n"
                "schema:\n{strict_schema}\n\n"
                "{format_instructions}",
            ),
        ]
    )

    llm = _build_llm(settings, model_name=job_request.modelName or settings.default_model, temperature=0.0)
    chain = prompt | llm | parser
    strict_chain = strict_prompt | llm | parser

    payload = {
        "total_pages": len(page_texts),
        "chunk_count": chunk_count,
        "draft_count": len(draft_items),
        "material_risk_cap": material_risk_cap,
        "high_risk_cap": high_risk_cap,
        "review_context": review_context,
        "draft_json": json.dumps({"draftRiskItems": draft_items}, ensure_ascii=False),
        "format_instructions": parser.get_format_instructions(),
    }
    try:
        reviewed = await chain.ainvoke(payload)
    except Exception as ex:
        logger.warning("V3 Agent2 first pass failed, strict retry: %s", ex)
        strict_payload = {
            **payload,
            "strict_schema": json.dumps(_AuditOutput.model_json_schema(), ensure_ascii=False),
        }
        reviewed = await strict_chain.ainvoke(strict_payload)

    raw_items = reviewed.get("riskItems") or []
    risks: List[RiskItem] = []
    for idx, item in enumerate(raw_items, start=1):
        excerpt = str(item.get("contractExcerpt") or "").strip()
        if not excerpt:
            continue
        page_no = _normalize_page_no(item.get("pageNo"), 1)
        risks.append(
            RiskItem(
                seqNo=int(item.get("seqNo") or idx),
                riskType=str(item.get("riskType") or "UNKNOWN"),
                riskLevel=_normalize_level(item.get("riskLevel")),
                riskScore=item.get("riskScore"),
                clauseTitle=item.get("clauseTitle"),
                clausePosition=item.get("clausePosition") or f"[Page {page_no}]",
                pageNo=page_no,
                contractExcerpt=excerpt,
                riskDesc=item.get("riskDesc"),
                suggestion=item.get("suggestion") or "建议法务人工复核并修订该条款。",
                legalBasis=item.get("legalBasis"),
                evidence=item.get("evidence"),
            )
        )
    return risks


def _count_levels(items: Sequence[RiskItem]) -> Dict[str, int]:
    ret = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for x in items:
        lv = _normalize_level(x.riskLevel)
        ret[lv] += 1
    return ret


def _build_default_judge() -> JudgeResult:
    return JudgeResult(
        decision="YES",
        confidence=0.5,
        reason_code="LOW_RELEVANCE",
        reason="judge disabled",
        supporting_evidence_ids=[],
        missing_evidence_hint="",
        requires_human_review=False,
    )


def _pick_top_evidence(candidates: Sequence[RetrievalCandidate], fallback_excerpt: str) -> Dict[str, Any]:
    if not candidates:
        return {
            "pageNo": 1,
            "clauseId": "",
            "clauseTitle": "",
            "excerpt": fallback_excerpt[:1200],
            "evidenceIds": [],
        }
    top = candidates[0]
    return {
        "pageNo": int(getattr(top, "page_no", 1) or 1),
        "clauseId": str(getattr(top, "clause_id", "") or ""),
        "clauseTitle": str(getattr(top, "clause_title", "") or ""),
        "excerpt": str(getattr(top, "snippet", "") or fallback_excerpt)[:1200],
        "evidenceIds": [x.candidate_id for x in candidates[:3]],
    }


async def run_contract_audit_v3(
    *,
    job_request: AuditJobRequest,
    fallback_runner: Any,
    page_loader: Any,
) -> tuple[CallbackSummary, List[RiskItem]]:
    settings: Settings = get_settings()
    t0 = perf_counter()
    sec: SecurityContext = build_security_context(job_request, settings)
    page_texts = page_loader(job_request.filePath)
    parse_quality = analyze_parser_quality(page_texts)

    draft_items, chunk_ranges, material_risk_cap, high_risk_cap = await _run_agent1_map_stage(
        job_request=job_request,
        page_texts=page_texts,
        settings=settings,
    )
    if not draft_items:
        empty = CallbackSummary(riskTotal=0, highRiskCount=0, mediumRiskCount=0, lowRiskCount=0)
        return empty, []

    parents, children = build_parent_child_chunks(
        page_texts=page_texts,
        sec=sec,
        settings=settings,
        parse_quality=parse_quality,
    )

    vector_store = None
    if settings.rag_mode in {"vector", "hybrid"}:
        try:
            vector_store = _index_vector_children(children, sec, settings)
        except Exception as ex:  # noqa: PERF203
            logger.warning("V3 vector index unavailable: %s", ex)
            vector_store = None

    risk_budgets: List[RiskBudget] = []
    evidence_blocks: List[str] = []
    evidence_index: Dict[tuple[str, str], List[RetrievalCandidate]] = {}
    judge_index: Dict[tuple[str, str], JudgeResult] = {}
    kept_drafts: List[Dict[str, Any]] = []
    risk_debug: List[Dict[str, Any]] = []

    for draft in draft_items:
        budget = build_risk_budget(settings)
        risk_budgets.append(budget)
        query_pack = build_risk_queries(draft, template_version=settings.risk_query_template_version)
        expanded_queries = query_pack["expanded_queries"][: budget.max_expanded_queries]
        budget.record_drop(len(query_pack["expanded_queries"]), len(expanded_queries))
        if len(expanded_queries) < len(query_pack["expanded_queries"]):
            budget.mark_exhausted()

        retrieval = retrieve_hybrid_for_risk(
            sec=sec,
            settings=settings,
            parent_chunks=parents,
            child_chunks=children,
            expanded_queries=expanded_queries,
            risk_type=str(draft.get("riskType") or ""),
            vector_store=vector_store,
        )
        candidates = retrieval.candidates[: budget.max_rrf_candidates]
        budget.record_drop(len(retrieval.candidates), len(candidates))

        reranked, rerank_metrics = rerank_candidates(
            query=query_pack["original_query"] or str(draft.get("riskType") or ""),
            candidates=candidates,
            settings=settings,
        )
        reranked = reranked[: budget.max_rerank_candidates]

        if settings.llm_judge_enabled:
            try:
                judge = judge_evidence_support(
                    query=query_pack["original_query"] or str(draft.get("riskType") or ""),
                    risk_type=str(draft.get("riskType") or ""),
                    candidates=reranked[: budget.max_judge_evidence],
                    settings=settings,
                )
            except Exception:
                judge = _build_default_judge()
        else:
            judge = _build_default_judge()

        policy = apply_judge_policy(
            mode=settings.judge_mode,
            reject_policy=settings.judge_reject_policy,
            judge_result=judge,
        )
        if not policy.get("keep", True):
            continue

        kept_drafts.append(draft)
        key = _candidate_key(str(draft.get("riskType") or ""), str(draft.get("clauseTitle") or ""))
        evidence_index[key] = list(reranked)
        judge_index[key] = judge

        # Build evidence block for Agent2 context.
        top_snippets = []
        for c in reranked[: max(1, min(3, budget.max_judge_evidence))]:
            top_snippets.append(
                f"[Page {c.page_no}][{c.clause_title or c.clause_id}] score={round(c.rrf_score, 4)}\n{c.snippet}"
            )
        block = (
            f"## riskType={draft.get('riskType')} clause={draft.get('clauseTitle')}\n"
            f"judge={judge.decision}({judge.reason_code}) conf={judge.confidence}\n"
            + "\n\n".join(top_snippets)
        ).strip()
        if block:
            evidence_blocks.append(block)
        if retrieval.parent_context:
            evidence_blocks.append(retrieval.parent_context[:1200])

        risk_debug.append(
            {
                "riskType": draft.get("riskType"),
                "clauseTitle": draft.get("clauseTitle"),
                "queries_count": len(expanded_queries),
                "retrieval": retrieval.metrics,
                "rerank": rerank_metrics,
                "judge": {
                    "decision": judge.decision,
                    "confidence": judge.confidence,
                    "reason_code": judge.reason_code,
                },
            }
        )

    # If strict gate removes everything, keep original drafts to avoid empty hard-fail.
    reviewer_drafts = kept_drafts or list(draft_items)
    review_context = _to_review_context(
        page_texts=page_texts,
        draft_items=reviewer_drafts,
        evidence_blocks=evidence_blocks,
        max_chars=max(10000, settings.review_context_chars),
    )

    try:
        reviewed_risks = await _run_agent2_review_stage(
            job_request=job_request,
            page_texts=page_texts,
            draft_items=reviewer_drafts,
            review_context=review_context,
            chunk_count=len(chunk_ranges),
            material_risk_cap=material_risk_cap,
            high_risk_cap=high_risk_cap,
            settings=settings,
        )
    except Exception as ex:  # noqa: PERF203
        logger.warning("V3 Agent2 failed, fallback to V2: %s", ex)
        return await fallback_runner(job_request)

    # Final consistency check + attach evidence.
    need_review_count = 0
    unsupported_count = 0
    final_check_failed_count = 0
    for risk in reviewed_risks:
        key_exact = _candidate_key(risk.riskType, risk.clauseTitle or "")
        key_type_only = _candidate_key(risk.riskType, "")
        cands = evidence_index.get(key_exact) or evidence_index.get(key_type_only) or []
        judge = judge_index.get(key_exact) or judge_index.get(key_type_only) or _build_default_judge()

        support_status = "SUPPORTED"
        unsupported_claims: List[str] = []
        requires_human_review = False
        if settings.final_check_enabled:
            try:
                final_check = run_claim_level_final_check(
                    risk_item={
                        "riskDesc": risk.riskDesc,
                        "suggestion": risk.suggestion,
                        "contractExcerpt": risk.contractExcerpt,
                    },
                    evidence_candidates=cands[: max(1, settings.max_judge_evidence_per_risk)],
                )
                support_status = final_check.overall_support_status
                unsupported_claims = final_check.unsupported_claims[:3]
                requires_human_review = final_check.requires_human_review
            except Exception:
                final_check_failed_count += 1

        if support_status == "UNSUPPORTED":
            unsupported_count += 1
        if requires_human_review or judge.requires_human_review:
            need_review_count += 1

        top_ev = _pick_top_evidence(cands, fallback_excerpt=risk.contractExcerpt)
        evidence_obj = {
            "pageNo": top_ev["pageNo"],
            "clauseId": top_ev["clauseId"],
            "clauseTitle": top_ev["clauseTitle"],
            "excerpt": top_ev["excerpt"],
            "supportStatus": support_status,
            "judge": {
                "decision": judge.decision,
                "confidence": judge.confidence,
                "reason_code": judge.reason_code,
                "reason": judge.reason,
            },
            "final_check": {
                "overall_support_status": support_status,
                "unsupported_claims": unsupported_claims,
                "requires_human_review": requires_human_review or judge.requires_human_review,
            },
            "evidence_ids": top_ev["evidenceIds"],
        }
        risk.evidence = _compact_json(evidence_obj)
        if (requires_human_review or judge.requires_human_review) and "人工复核" not in str(risk.suggestion or ""):
            risk.suggestion = f"{str(risk.suggestion or '').strip()}（证据支持度不足，建议人工复核）".strip()

    lv = _count_levels(reviewed_risks)
    summary = CallbackSummary(
        riskTotal=len(reviewed_risks),
        highRiskCount=lv["HIGH"],
        mediumRiskCount=lv["MEDIUM"],
        lowRiskCount=lv["LOW"],
    )

    metrics = {
        "parse_quality": parse_quality,
        "chunk": {
            "parent_chunk_count": len(parents),
            "child_chunk_count": len(children),
            "chunk_version": settings.chunk_version,
        },
        "budget": budget_metrics_aggregate(risk_budgets),
        "review": {
            "unsupported_risk_count": unsupported_count,
            "need_review_count": need_review_count,
            "final_check_failed_count": final_check_failed_count,
        },
        "e2e_latency_ms": int((perf_counter() - t0) * 1000),
        "versions": {
            "parser_version": settings.parser_version,
            "chunk_version": settings.chunk_version,
            "query_template_version": settings.risk_query_template_version,
            "rrf_config_version": settings.rrf_config_version,
            "rerank_model_version": settings.rerank_model_version,
            "judge_prompt_version": settings.judge_prompt_version,
            "final_check_prompt_version": settings.final_check_prompt_version,
        },
    }

    trace_payload = {
        "task_id": sec.task_id,
        "task_no": job_request.taskNo,
        "tenant": sec.short(),
        "metrics": metrics,
        "risks": risk_debug[:80],
        "summary_v3": summary.model_dump(),
        "generated_at": datetime.utcnow().isoformat(),
    }
    try:
        persist_trace_event(
            trace_dir=settings.react_trace_dir,
            security_context=sec,
            payload=trace_payload,
            debug_enabled=settings.debug_trace_enabled,
            store_full_text=settings.trace_store_full_text,
            pii_masking_enabled=settings.pii_masking_enabled,
            encryption_enabled=settings.trace_encryption_enabled,
            encryption_secret=settings.trace_secret,
            retention_days=settings.trace_retention_days,
        )
    except Exception:
        pass

    # Optional eval predictions (no protocol/schema change).
    if settings.rag_eval_enabled:
        try:
            eval_dir = Path(settings.eval_output_dir)
            eval_dir.mkdir(parents=True, exist_ok=True)
            pred_path = eval_dir / "predictions.jsonl"
            with pred_path.open("a", encoding="utf-8") as f:
                for r in reviewed_risks:
                    ev = {}
                    try:
                        ev = json.loads(str(r.evidence or "{}"))
                    except Exception:
                        ev = {}
                    row = {
                        "task_id": sec.task_id,
                        "risk_type": r.riskType,
                        "retrieved_evidences": [
                            {
                                "page_no": ev.get("pageNo"),
                                "excerpt": ev.get("excerpt"),
                            }
                        ],
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass

    return summary, reviewed_risks
