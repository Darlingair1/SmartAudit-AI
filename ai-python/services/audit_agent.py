import asyncio
import json
import logging
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from langchain_chroma import Chroma
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from services.llm_client import InjectableLLM, build_openai_llm
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, ConfigDict, Field
from services.document_parser import load_pdf_pages

from core.config import get_settings
from schemas.models import AuditJobRequest, CallbackSummary, RiskItem
from services.reviewer_tools import (
    get_reviewer_tool_registry,
    get_reviewer_tool_schemas,
    run_tool_with_timeout,
)

logger = logging.getLogger("smartaudit.ai.audit_agent")

# High-signal legal/commercial query terms for retrieval augmentation.
CRITICAL_RAG_QUERIES = [
    "违约金",
    "违约责任",
    "付款周期",
    "付款条件",
    "分期付款",
    "解约",
    "单方解除",
    "争议解决",
    "管辖法院",
    "仲裁",
    "赔偿",
    "保密",
    "知识产权",
    "验收",
]

_EMBEDDING_CACHE: Dict[Tuple[str, str, bool, int], HuggingFaceEmbeddings] = {}


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


def _load_pdf_pages(file_path: str) -> List[str]:
    return load_pdf_pages(file_path)


def _build_chunk_ranges(total_pages: int, chunk_pages: int, overlap_pages: int) -> List[Tuple[int, int]]:
    if total_pages <= 0:
        return []
    chunk_pages = max(1, chunk_pages)
    overlap_pages = max(0, min(overlap_pages, chunk_pages - 1))
    step = max(1, chunk_pages - overlap_pages)

    ranges: List[Tuple[int, int]] = []
    start = 1
    while start <= total_pages:
        end = min(total_pages, start + chunk_pages - 1)
        ranges.append((start, end))
        if end >= total_pages:
            break
        start += step
    return ranges


def _build_chunk_text(page_texts: Sequence[str], start_page: int, end_page: int) -> str:
    blocks: List[str] = []
    for page_no in range(start_page, end_page + 1):
        text = (page_texts[page_no - 1] or "").strip()
        if not text:
            continue
        blocks.append(f"[Page {page_no}]\n{text}")
    return "\n\n".join(blocks).strip()


def _resolve_local_path(path_value: str) -> Path:
    candidate = Path((path_value or "").strip())
    if candidate.is_absolute():
        return candidate
    return (Path(__file__).resolve().parents[2] / candidate).resolve()


def _safe_collection_name(prefix: str, task_id: str) -> str:
    # Chroma collection names should be compact and filesystem-safe.
    raw = f"{prefix}-{task_id}".lower()
    value = re.sub(r"[^a-z0-9_-]", "-", raw)
    value = re.sub(r"-{2,}", "-", value).strip("-_")
    if len(value) < 3:
        value = "smartaudit-task"
    return value[:63]


def _build_page_documents(page_texts: Sequence[str], job_request: AuditJobRequest) -> List[Document]:
    docs: List[Document] = []
    task_id = str(job_request.taskId)
    for page_no, text in enumerate(page_texts, start=1):
        content = (text or "").strip()
        if not content:
            continue
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "task_id": task_id,
                    "task_no": str(job_request.taskNo or ""),
                    "file_path": str(job_request.filePath or ""),
                    "page_no": page_no,
                },
            )
        )
    return docs


def _split_vector_documents(
    documents: Sequence[Document],
    chunk_size: int,
    chunk_overlap: int,
) -> List[Document]:
    if not documents:
        return []
    chunk_size = max(200, chunk_size)
    chunk_overlap = max(0, min(chunk_overlap, chunk_size - 1))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )
    return splitter.split_documents(list(documents))


def _get_hf_embeddings(
    model_path: str,
    device: str,
    normalize_embeddings: bool,
    batch_size: int,
) -> HuggingFaceEmbeddings:
    model_dir = _resolve_local_path(model_path)
    if not model_dir.exists():
        raise FileNotFoundError(f"Embedding model path not found: {model_dir}")

    key = (str(model_dir), device, normalize_embeddings, max(1, batch_size))
    cached = _EMBEDDING_CACHE.get(key)
    if cached is not None:
        return cached

    embeddings = HuggingFaceEmbeddings(
        model_name=str(model_dir),
        model_kwargs={"device": device},
        encode_kwargs={
            "normalize_embeddings": normalize_embeddings,
            "batch_size": max(1, batch_size),
        },
    )
    _EMBEDDING_CACHE[key] = embeddings
    return embeddings


def _build_vector_rag_context(
    page_texts: Sequence[str],
    queries: Sequence[str],
    job_request: AuditJobRequest,
    settings: Any,
) -> str:
    if not page_texts or not queries:
        return ""

    persist_dir = _resolve_local_path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    embeddings = _get_hf_embeddings(
        model_path=settings.embedding_model_path,
        device=settings.embedding_device,
        normalize_embeddings=settings.embedding_normalize,
        batch_size=settings.embedding_batch_size,
    )

    task_id = str(job_request.taskId)
    collection_name = _safe_collection_name(settings.chroma_collection_prefix, task_id)
    vector_store = Chroma(
        collection_name=collection_name,
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
    )

    page_docs = _build_page_documents(page_texts, job_request)
    chunk_docs = _split_vector_documents(
        page_docs,
        chunk_size=settings.vector_chunk_size,
        chunk_overlap=settings.vector_chunk_overlap,
    )
    if not chunk_docs:
        return ""

    if settings.vector_reindex_each_run:
        try:
            vector_store.delete(where={"task_id": task_id})
        except Exception as ex:  # noqa: PERF203
            logger.warning("Vector RAG delete old task chunks failed, taskId=%s, err=%s", task_id, ex)

    for idx, doc in enumerate(chunk_docs, start=1):
        doc.metadata["task_id"] = task_id
        doc.metadata["chunk_index"] = idx

    doc_ids = [f"{task_id}-chunk-{idx}" for idx in range(1, len(chunk_docs) + 1)]
    vector_store.add_documents(chunk_docs, ids=doc_ids)

    top_k = max(1, settings.vector_top_k)
    max_chars = max(1000, settings.vector_max_chars)
    blocks: List[str] = []
    current_chars = 0
    dedupe_keys: set[Tuple[int, str]] = set()

    for query in queries:
        results = vector_store.similarity_search_with_score(
            query,
            k=top_k,
            filter={"task_id": task_id},
        )
        for doc, distance in results:
            page_no = _normalize_page_no(doc.metadata.get("page_no"), default=1)
            snippet = (doc.page_content or "").strip()
            if not snippet:
                continue
            snippet = snippet[:700]
            dedupe_key = (page_no, _compact_text(snippet)[:120])
            if dedupe_key in dedupe_keys:
                continue
            dedupe_keys.add(dedupe_key)

            block = f"[VectorQuery:{query}][Page {page_no}][Distance {distance:.4f}]\n{snippet}"
            extra_chars = len(block) + (2 if blocks else 0)
            if current_chars + extra_chars > max_chars:
                logger.info(
                    "Vector RAG context reached max chars, blocks=%d, max_chars=%d",
                    len(blocks),
                    max_chars,
                )
                return "\n\n".join(blocks).strip()
            blocks.append(block)
            current_chars += extra_chars

    logger.info(
        "Vector RAG context built, collection=%s, blocks=%d, queries=%d",
        collection_name,
        len(blocks),
        len(queries),
    )
    return "\n\n".join(blocks).strip()


def cleanup_task_vector_index(task_id: str, settings: Any | None = None) -> bool:
    settings = settings or get_settings()
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        raise ValueError("task_id cannot be blank")

    persist_dir = _resolve_local_path(settings.chroma_persist_dir)
    if not persist_dir.exists():
        logger.info("Vector cleanup skipped, chroma dir not found: %s", persist_dir)
        return True

    collection_name = _safe_collection_name(settings.chroma_collection_prefix, normalized_task_id)
    try:
        vector_store = Chroma(
            collection_name=collection_name,
            persist_directory=str(persist_dir),
        )
        # Prefer dropping whole task collection for deterministic cleanup.
        vector_store.delete_collection()
        logger.info(
            "Vector cleanup completed, taskId=%s, collection=%s",
            normalized_task_id,
            collection_name,
        )
        return True
    except Exception as ex:  # noqa: PERF203
        msg = str(ex).lower()
        if "not exist" in msg or "not found" in msg:
            logger.info(
                "Vector cleanup idempotent skip, taskId=%s, collection=%s",
                normalized_task_id,
                collection_name,
            )
            return True
        logger.warning(
            "Vector cleanup failed, taskId=%s, collection=%s, err=%s",
            normalized_task_id,
            collection_name,
            ex,
        )
        return False


def _normalize_level(level: str) -> str:
    if not level:
        return "LOW"
    lvl = level.strip().upper()
    if lvl not in {"HIGH", "MEDIUM", "LOW"}:
        return "LOW"
    return lvl


def _to_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return score


def _normalize_page_no(value: Any, default: int = 1) -> int:
    try:
        page_no = int(value)
    except (TypeError, ValueError):
        return default
    return page_no if page_no > 0 else default


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _clip_text(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _excerpt_in_page(excerpt: str, page_text: str) -> bool:
    if not excerpt or not page_text:
        return False
    if excerpt in page_text:
        return True
    return _compact_text(excerpt) in _compact_text(page_text)


def _infer_page_no_from_excerpt(excerpt: str, page_texts: Sequence[str]) -> int:
    if not excerpt:
        return 1
    for idx, text in enumerate(page_texts, start=1):
        if _excerpt_in_page(excerpt, text):
            return idx
    return 1


def _resolve_page_no(page_no: int, excerpt: str, page_texts: Sequence[str]) -> int:
    if page_no <= 0 or page_no > len(page_texts):
        return _infer_page_no_from_excerpt(excerpt, page_texts)

    selected_page = page_texts[page_no - 1]
    if _excerpt_in_page(excerpt, selected_page):
        return page_no

    return _infer_page_no_from_excerpt(excerpt, page_texts)


def _count_by_level(items: List[RiskItem]) -> Dict[str, int]:
    summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in items:
        summary[item.riskLevel] += 1
    return summary


def _level_priority(level: str) -> int:
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(_normalize_level(level), 1)


def _pick_longer_text(current: str | None, candidate: str | None) -> str | None:
    c1 = (current or "").strip()
    c2 = (candidate or "").strip()
    if not c1:
        return c2 or None
    if not c2:
        return c1
    return c2 if len(c2) > len(c1) else c1


def _join_unique_text(current: str | None, candidate: str | None) -> str | None:
    c1 = (current or "").strip()
    c2 = (candidate or "").strip()
    if not c1:
        return c2 or None
    if not c2:
        return c1
    if c2 in c1:
        return c1
    if c1 in c2:
        return c2
    return f"{c1}；{c2}"


def _risk_confidence(item: RiskItem) -> float:
    score = item.riskScore if item.riskScore is not None else 50.0
    if item.legalBasis:
        score += 5
    if item.riskDesc:
        score += 3
    if item.clauseTitle:
        score += 2
    return score


def _merge_and_denoise_items(
    items: List[RiskItem],
    page_count: int,
    draft_count: int,
) -> tuple[List[RiskItem], int]:
    # Step1: merge same-clause items to avoid fragmented duplicates.
    merged_map: Dict[Tuple[int, str, str], RiskItem] = {}
    for item in items:
        excerpt_compact = _compact_text(item.contractExcerpt)
        if len(excerpt_compact) < 10:
            continue

        clause_anchor = _compact_text(item.clauseTitle or "")[:24]
        if not clause_anchor:
            clause_anchor = excerpt_compact[:48]
        risk_anchor = _compact_text(item.riskType or "UNKNOWN")[:24]
        key = (item.pageNo, clause_anchor, risk_anchor)

        existing = merged_map.get(key)
        if existing is None:
            merged_map[key] = item
            continue

        if _level_priority(item.riskLevel) > _level_priority(existing.riskLevel):
            existing.riskLevel = item.riskLevel
            existing.riskScore = item.riskScore
        elif item.riskScore is not None and (existing.riskScore is None or item.riskScore > existing.riskScore):
            existing.riskScore = item.riskScore

        existing.contractExcerpt = _pick_longer_text(existing.contractExcerpt, item.contractExcerpt) or existing.contractExcerpt
        existing.riskDesc = _join_unique_text(existing.riskDesc, item.riskDesc)
        existing.suggestion = _pick_longer_text(existing.suggestion, item.suggestion) or existing.suggestion
        existing.legalBasis = _join_unique_text(existing.legalBasis, item.legalBasis)
        existing.evidence = _join_unique_text(existing.evidence, item.evidence)
        existing.clausePosition = _pick_longer_text(existing.clausePosition, item.clausePosition)

    merged_items = list(merged_map.values())

    # Step2: remove exact duplicated excerpts.
    dedup_map: Dict[Tuple[int, str], RiskItem] = {}
    for item in merged_items:
        dedup_key = (item.pageNo, _compact_text(item.contractExcerpt))
        existing = dedup_map.get(dedup_key)
        if existing is None:
            dedup_map[dedup_key] = item
            continue
        if _level_priority(item.riskLevel) > _level_priority(existing.riskLevel):
            dedup_map[dedup_key] = item
        elif _risk_confidence(item) > _risk_confidence(existing):
            dedup_map[dedup_key] = item

    denoised = list(dedup_map.values())

    # Step3: cap HIGH proportion to prevent over-harsh grading.
    high_indices = [idx for idx, it in enumerate(denoised) if it.riskLevel == "HIGH"]
    high_cap = max(1, math.ceil(max(len(denoised), 1) * 0.45))
    downgraded_high = 0
    if len(high_indices) > high_cap:
        ranked = sorted(
            high_indices,
            key=lambda i: _risk_confidence(denoised[i]),
            reverse=True,
        )
        keep_set = set(ranked[:high_cap])
        for idx in high_indices:
            if idx not in keep_set:
                denoised[idx].riskLevel = "MEDIUM"
                downgraded_high += 1

    # Step4: cap total item count with materiality preference.
    max_final_items = max(4, min(40, max(page_count * 5, draft_count // 2 + 2)))
    if len(denoised) > max_final_items:
        denoised = sorted(
            denoised,
            key=lambda it: (
                _level_priority(it.riskLevel),
                _risk_confidence(it),
                len(_compact_text(it.contractExcerpt)),
            ),
            reverse=True,
        )[:max_final_items]

    denoised.sort(key=lambda it: (it.pageNo, -_level_priority(it.riskLevel), _compact_text(it.riskType or "")))
    for idx, item in enumerate(denoised, start=1):
        item.seqNo = idx
        item.riskLevel = _normalize_level(item.riskLevel)
    return denoised, downgraded_high


def _dedupe_draft_items(items: List[Dict[str, Any]], page_texts: Sequence[str]) -> List[Dict[str, Any]]:
    dedup: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for item in items:
        excerpt = str(item.get("contractExcerpt") or "").strip()
        if not excerpt:
            continue

        page_no = _normalize_page_no(item.get("pageNo"), default=1)
        page_no = _resolve_page_no(page_no, excerpt, page_texts)
        key = (page_no, _compact_text(excerpt))
        normalized = {
            "clauseTitle": item.get("clauseTitle"),
            "riskType": str(item.get("riskType") or "UNKNOWN"),
            "riskLevel": _normalize_level(str(item.get("riskLevel") or "LOW")),
            "pageNo": page_no,
            "contractExcerpt": excerpt,
            "riskDesc": item.get("riskDesc"),
            "suggestion": str(item.get("suggestion") or "").strip() or "建议法务人工复核并修订该条款。",
        }

        existing = dedup.get(key)
        if existing is None:
            dedup[key] = normalized
            continue

        # Keep richer draft content.
        if len(json.dumps(normalized, ensure_ascii=False)) > len(json.dumps(existing, ensure_ascii=False)):
            dedup[key] = normalized

    return list(dedup.values())


def _normalize_chunk_drafts(
    chunk_items: List[Dict[str, Any]],
    start_page: int,
    end_page: int,
    page_texts: Sequence[str],
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in chunk_items:
        excerpt = str(item.get("contractExcerpt") or "").strip()
        if not excerpt:
            continue

        page_no = _normalize_page_no(item.get("pageNo"), default=start_page)
        page_no = _resolve_page_no(page_no, excerpt, page_texts)
        if not (start_page <= page_no <= end_page):
            inferred = _infer_page_no_from_excerpt(excerpt, page_texts)
            if start_page <= inferred <= end_page:
                page_no = inferred
            else:
                page_no = max(start_page, min(end_page, page_no))

        normalized.append(
            {
                "clauseTitle": item.get("clauseTitle"),
                "riskType": str(item.get("riskType") or "UNKNOWN"),
                "riskLevel": _normalize_level(str(item.get("riskLevel") or "LOW")),
                "pageNo": page_no,
                "contractExcerpt": excerpt,
                "riskDesc": item.get("riskDesc"),
                "suggestion": str(item.get("suggestion") or "").strip() or "建议法务人工复核并修订该条款。",
            }
        )
    return normalized


def _build_rag_queries(draft_items: Sequence[Dict[str, Any]]) -> List[str]:
    query_set = set(CRITICAL_RAG_QUERIES)
    for item in draft_items[:300]:
        for field in ("riskType", "clauseTitle"):
            value = str(item.get(field) or "").strip()
            if len(value) >= 2:
                query_set.add(value[:30])
    return list(query_set)


def _score_page_for_query(page_text: str, query: str) -> int:
    if not page_text or not query:
        return 0
    compact_page = _compact_text(page_text)
    compact_query = _compact_text(query)
    if not compact_query:
        return 0

    exact_count = compact_page.count(compact_query)
    if exact_count > 0:
        return 10 * exact_count + min(20, len(compact_query))

    # Fallback token overlap score.
    tokens = [t for t in re.split(r"[\s,，。；;:：()（）【】\[\]/\\]+", query) if t]
    score = 0
    for token in tokens:
        c_token = _compact_text(token)
        if len(c_token) >= 2 and c_token in compact_page:
            score += 2
    return score


def _extract_snippet(page_text: str, query: str, max_len: int = 800) -> str:
    if not page_text:
        return ""
    query = (query or "").strip()
    if not query:
        return page_text[:max_len]

    idx = page_text.find(query)
    if idx < 0:
        # try fuzzy token
        tokens = [t for t in re.split(r"[\s,，。；;:：()（）【】\[\]/\\]+", query) if t]
        for token in tokens:
            idx = page_text.find(token)
            if idx >= 0:
                break

    if idx < 0:
        return page_text[:max_len]

    left = max(0, idx - 200)
    right = min(len(page_text), idx + max_len)
    return page_text[left:right]


def _build_rag_context(
    page_texts: Sequence[str],
    queries: Sequence[str],
    top_k_per_query: int,
    max_chars: int,
) -> str:
    if not page_texts or not queries:
        return ""

    top_k_per_query = max(1, top_k_per_query)
    max_chars = max(1000, max_chars)

    blocks: List[str] = []
    current_chars = 0
    used_keys: set[Tuple[str, int]] = set()

    for query in queries:
        scored_pages: List[Tuple[int, int]] = []
        for idx, text in enumerate(page_texts, start=1):
            score = _score_page_for_query(text, query)
            if score > 0:
                scored_pages.append((score, idx))

        if not scored_pages:
            continue

        scored_pages.sort(reverse=True)
        for score, page_no in scored_pages[:top_k_per_query]:
            key = (query, page_no)
            if key in used_keys:
                continue
            used_keys.add(key)

            snippet = _extract_snippet(page_texts[page_no - 1], query, max_len=700)
            if not snippet:
                continue
            block = f"[Query:{query}][Page {page_no}][Score {score}]\n{snippet}"
            extra_chars = len(block) + (2 if blocks else 0)
            if current_chars + extra_chars > max_chars:
                return "\n\n".join(blocks).strip()
            blocks.append(block)
            current_chars += extra_chars

    return "\n\n".join(blocks).strip()


def _build_review_context(
    page_texts: Sequence[str],
    draft_items: Sequence[Dict[str, Any]],
    rag_context: str,
    max_chars: int,
) -> str:
    max_chars = max(5000, max_chars)

    candidate_pages = sorted(
        {
            _normalize_page_no(item.get("pageNo"), 1)
            for item in draft_items
            if item.get("pageNo") is not None
        }
    )
    candidate_pages = [p for p in candidate_pages if 1 <= p <= len(page_texts)]
    if not candidate_pages:
        candidate_pages = list(range(1, min(len(page_texts), 12) + 1))

    blocks: List[str] = []
    current_chars = 0

    for page_no in candidate_pages:
        text = (page_texts[page_no - 1] or "").strip()
        if not text:
            continue
        snippet = text[:1200]
        block = f"[Page {page_no}]\n{snippet}"
        extra_chars = len(block) + (2 if blocks else 0)
        if current_chars + extra_chars > max_chars:
            break
        blocks.append(block)
        current_chars += extra_chars

    if rag_context and current_chars < max_chars:
        remain = max_chars - current_chars
        rag_part = rag_context[:remain]
        if rag_part.strip():
            blocks.append(f"[RAG Critical Context]\n{rag_part.strip()}")

    return "\n\n".join(blocks).strip()


def _build_llm(
    model_name: str,
    temperature: float,
    timeout_seconds: int,
    max_retries: int,
    api_key: str,
    base_url: str,
) -> InjectableLLM:
    return build_openai_llm(
        model=model_name,
        temperature=temperature,
        timeout=timeout_seconds,
        api_key=api_key,
        base_url=base_url,
        retries=max_retries,
    )


def _safe_json_dumps(value: Any, max_chars: int = 4000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except Exception:
        text = str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...(truncated)"


def _extract_json_object(text: str) -> Dict[str, Any] | None:
    # Legacy fallback parser:
    # Native tool-calling path should NOT depend on this parser for control flow.
    # Keep it as a last-resort extractor in final/repair fallback scenarios.
    if not text:
        return None
    content = text.strip()
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = content[start : end + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _normalize_react_action(raw: Dict[str, Any]) -> Dict[str, Any]:
    action = str(raw.get("action") or "").strip().lower()
    if action not in {"tool", "final"}:
        # Backward compatible fallback: if model directly outputs final schema.
        if "riskItems" in raw:
            action = "final"
        elif "tool_name" in raw:
            action = "tool"
        else:
            action = ""

    tool_name = str(raw.get("tool_name") or raw.get("toolName") or "").strip()
    tool_args = raw.get("tool_args")
    if tool_args is None:
        tool_args = raw.get("toolArgs")
    if tool_args is None:
        tool_args = raw.get("input")
    if not isinstance(tool_args, dict):
        tool_args = {}

    final_json = raw.get("final_json")
    if final_json is None:
        final_json = raw.get("finalJson")
    if final_json is None and "riskItems" in raw:
        final_json = raw

    return {
        "action": action,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "final_json": final_json,
        "thought": str(raw.get("thought") or "").strip(),
    }


def _build_tool_call_kwargs(
    tool_name: str,
    tool_args: Dict[str, Any],
    *,
    task_id: str,
    page_texts: Sequence[str],
    settings: Any,
    vector_ready: bool,
) -> Dict[str, Any]:
    query = str(tool_args.get("query") or "").strip()
    top_k = tool_args.get("top_k")
    if top_k is None:
        top_k = tool_args.get("topK")

    if tool_name == "vector_search":
        return {
            "task_id": task_id,
            "query": query,
            "top_k": top_k,
            "page_texts": page_texts,
            # build vector index on demand only when not ready
            "index": not vector_ready,
            "reindex": False,
            "settings": settings,
        }
    if tool_name == "keyword_search":
        return {
            "query": query,
            "page_texts": page_texts,
            "top_k": top_k or 3,
            "max_snippet_chars": int(tool_args.get("max_snippet_chars") or 700),
        }
    if tool_name == "get_page_text":
        return {
            "page_texts": page_texts,
            "page_no": int(tool_args.get("page_no") or tool_args.get("pageNo") or 1),
            "max_chars": int(tool_args.get("max_chars") or 4000),
        }
    if tool_name == "find_excerpt_page":
        return {
            "page_texts": page_texts,
            "excerpt": str(tool_args.get("excerpt") or ""),
            "max_scan_pages": int(tool_args.get("max_scan_pages") or 0),
        }
    if tool_name == "law_lookup":
        return {
            "risk_type": str(tool_args.get("risk_type") or tool_args.get("riskType") or ""),
            "risk_desc": str(tool_args.get("risk_desc") or tool_args.get("riskDesc") or ""),
        }
    return {}


def _compact_tool_runtime_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for key, value in payload.items():
        if key == "page_texts":
            try:
                page_count = len(value)  # type: ignore[arg-type]
            except Exception:
                page_count = -1
            compact[key] = f"<page_texts:{page_count}>"
            continue
        if key == "settings":
            compact[key] = "<settings>"
            continue
        if isinstance(value, str):
            compact[key] = _clip_text(value, 260)
            continue
        if isinstance(value, (list, tuple, set)):
            compact[key] = f"<{type(value).__name__}:len={len(value)}>"
            continue
        if isinstance(value, dict):
            compact[key] = f"<dict:keys={list(value.keys())[:8]}>"
            continue
        compact[key] = value
    return compact


def _parse_tool_call_args(raw_args: Any) -> Dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _extract_native_tool_calls(message: Any) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    raw_calls = getattr(message, "tool_calls", None)
    if not isinstance(raw_calls, list):
        raw_calls = []
    for item in raw_calls:
        if not isinstance(item, dict):
            continue
        calls.append(
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "args": _parse_tool_call_args(item.get("args")),
            }
        )

    # compatibility: some gateways place tool_calls in additional_kwargs
    if not calls:
        extra = getattr(message, "additional_kwargs", None)
        if isinstance(extra, dict):
            extra_calls = extra.get("tool_calls") or []
            if isinstance(extra_calls, list):
                for item in extra_calls:
                    if not isinstance(item, dict):
                        continue
                    fn = item.get("function") or {}
                    if not isinstance(fn, dict):
                        fn = {}
                    calls.append(
                        {
                            "id": str(item.get("id") or ""),
                            "name": str(fn.get("name") or item.get("name") or ""),
                            "args": _parse_tool_call_args(fn.get("arguments")),
                        }
                    )
    return [c for c in calls if c["name"]]


def _build_tool_observation_view(
    tool_name: str,
    tool_result: Dict[str, Any],
    *,
    obs_max_chars: int,
    obs_topk_cap: int,
) -> Dict[str, Any]:
    view: Dict[str, Any] = {
        "ok": bool(tool_result.get("ok")),
        "tool": tool_name,
        "message": _clip_text(str(tool_result.get("message") or ""), 160),
    }
    data = tool_result.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    if tool_name in {"vector_search", "keyword_search"}:
        hits = data.get("hits") or []
        if not isinstance(hits, list):
            hits = []
        normalized_hits: List[Dict[str, Any]] = []
        for hit in hits[: max(1, obs_topk_cap)]:
            if not isinstance(hit, dict):
                continue
            normalized_hits.append(
                {
                    "pageNo": _normalize_page_no(hit.get("pageNo"), default=1),
                    "score": hit.get("score"),
                    "distance": hit.get("distance"),
                    "snippet": _clip_text(str(hit.get("snippet") or ""), min(320, obs_max_chars)),
                }
            )
        view["data"] = {
            "query": _clip_text(str(data.get("query") or ""), 120),
            "topK": data.get("topK"),
            "hitCount": int(data.get("hitCount") or 0),
            "hits": normalized_hits,
        }
        return view

    if tool_name == "get_page_text":
        view["data"] = {
            "pageNo": _normalize_page_no(data.get("pageNo"), default=1),
            "chars": int(data.get("chars") or 0),
            "text": _clip_text(str(data.get("text") or ""), obs_max_chars),
        }
        return view

    if tool_name == "find_excerpt_page":
        view["data"] = {
            "matched": bool(data.get("matched")),
            "pageNo": data.get("pageNo"),
            "mode": _clip_text(str(data.get("mode") or ""), 32),
        }
        return view

    if tool_name == "law_lookup":
        legal = data.get("legalBasis") or []
        if not isinstance(legal, list):
            legal = []
        view["data"] = {
            "riskType": _clip_text(str(data.get("riskType") or ""), 120),
            "legalBasis": [str(x).strip() for x in legal[:5] if str(x).strip()],
        }
        return view

    view["data"] = _clip_text(_safe_json_dumps(data, max_chars=obs_max_chars), obs_max_chars)
    return view


def _recompute_summary_from_items(payload: Dict[str, Any]) -> Dict[str, Any]:
    items = payload.get("riskItems") or []
    if not isinstance(items, list):
        items = []
    level_count = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in items:
        if not isinstance(item, dict):
            continue
        level = _normalize_level(str(item.get("riskLevel") or "LOW"))
        level_count[level] += 1
    payload["summary"] = {
        "riskTotal": len(items),
        "highRiskCount": level_count["HIGH"],
        "mediumRiskCount": level_count["MEDIUM"],
        "lowRiskCount": level_count["LOW"],
    }
    return payload


def _persist_react_trace(task_id: str, trace_payload: Dict[str, Any], settings: Any) -> None:
    if not bool(getattr(settings, "react_trace_enabled", False)):
        return
    try:
        trace_dir = _resolve_local_path(str(getattr(settings, "react_trace_dir", "logs/react-traces")))
        trace_dir.mkdir(parents=True, exist_ok=True)
        safe_task = re.sub(r"[^0-9A-Za-z_-]+", "-", str(task_id or "task")).strip("-_") or "task"
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        trace_path = trace_dir / f"react_trace_{safe_task}_{ts}.json"
        trace_path.write_text(
            json.dumps(trace_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as ex:  # noqa: PERF203
        logger.warning("Persist ReAct trace failed, taskId=%s, err=%s", task_id, ex)


async def _post_verify_final_with_tools(
    *,
    task_id: str,
    payload: Dict[str, Any],
    page_texts: Sequence[str],
    settings: Any,
    tools: Dict[str, Any],
    tool_timeout_ms: int,
    observations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    risk_items = payload.get("riskItems") or []
    if not isinstance(risk_items, list) or not risk_items:
        return _recompute_summary_from_items(payload)

    find_excerpt_tool = tools.get("find_excerpt_page")
    law_lookup_tool = tools.get("law_lookup")
    drop_unmatched = bool(getattr(settings, "react_drop_unmatched_excerpt", True))
    autofill_legal_basis = bool(getattr(settings, "react_autofill_legal_basis", True))

    verified_items: List[Dict[str, Any]] = []
    dropped_count = 0
    fixed_page_count = 0
    autofilled_law_count = 0

    for item in risk_items:
        if not isinstance(item, dict):
            continue
        current = dict(item)
        excerpt = str(current.get("contractExcerpt") or "").strip()
        if not excerpt:
            dropped_count += 1
            continue

        # Quick local match first; fall back to tool scan only when pageNo seems wrong.
        page_no = _normalize_page_no(current.get("pageNo"), default=1)
        local_matched = False
        if 1 <= page_no <= len(page_texts):
            local_matched = _excerpt_in_page(excerpt, page_texts[page_no - 1])

        matched_page_no: int | None = page_no if local_matched else None
        if not local_matched and callable(find_excerpt_tool):
            find_res = await run_tool_with_timeout(
                tool_name="find_excerpt_page",
                tool_fn=find_excerpt_tool,
                timeout_ms=tool_timeout_ms,
                page_texts=page_texts,
                excerpt=excerpt,
                max_scan_pages=0,
            )
            data = find_res.get("data") or {}
            if find_res.get("ok") and data.get("matched") and data.get("pageNo"):
                try:
                    matched_page_no = int(data.get("pageNo"))
                except (TypeError, ValueError):
                    matched_page_no = None

        if matched_page_no is None:
            if drop_unmatched:
                dropped_count += 1
                observations.append(
                    {
                        "kind": "post_verify_drop",
                        "reason": "excerpt_not_found",
                        "excerptPreview": _clip_text(excerpt, 160),
                    }
                )
                continue
            matched_page_no = page_no

        if matched_page_no != page_no:
            fixed_page_count += 1
        current["pageNo"] = matched_page_no
        if not str(current.get("clausePosition") or "").strip():
            current["clausePosition"] = f"[Page {matched_page_no}]"

        if autofill_legal_basis and not str(current.get("legalBasis") or "").strip() and callable(law_lookup_tool):
            law_res = await run_tool_with_timeout(
                tool_name="law_lookup",
                tool_fn=law_lookup_tool,
                timeout_ms=tool_timeout_ms,
                risk_type=str(current.get("riskType") or ""),
                risk_desc=str(current.get("riskDesc") or ""),
            )
            law_data = law_res.get("data") or {}
            law_list = law_data.get("legalBasis") or []
            if law_res.get("ok") and isinstance(law_list, list) and law_list:
                current["legalBasis"] = "；".join([str(x).strip() for x in law_list if str(x).strip()])
                autofilled_law_count += 1

        verified_items.append(current)

    payload["riskItems"] = verified_items
    payload = _recompute_summary_from_items(payload)
    observations.append(
        {
            "kind": "post_verify_summary",
            "taskId": task_id,
            "inputItems": len(risk_items),
            "outputItems": len(verified_items),
            "droppedItems": dropped_count,
            "fixedPageCount": fixed_page_count,
            "autofilledLawCount": autofilled_law_count,
        }
    )
    return payload


def _ensure_audit_output_schema(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("final_json must be a JSON object")

    candidate = payload
    if "summary" not in candidate and "riskItems" in candidate:
        risk_items = candidate.get("riskItems") or []
        level_count = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for item in risk_items:
            if not isinstance(item, dict):
                continue
            level = _normalize_level(str(item.get("riskLevel") or "LOW"))
            level_count[level] += 1
        candidate = {
            "summary": {
                "riskTotal": len(risk_items),
                "highRiskCount": level_count["HIGH"],
                "mediumRiskCount": level_count["MEDIUM"],
                "lowRiskCount": level_count["LOW"],
            },
            "riskItems": risk_items,
        }

    return _AuditOutput.model_validate(candidate).model_dump()


def _is_effective_evidence_result(tool_name: str, tool_result: Dict[str, Any]) -> bool:
    if not isinstance(tool_result, dict) or not tool_result.get("ok"):
        return False
    data = tool_result.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    if tool_name in {"vector_search", "keyword_search"}:
        try:
            return int(data.get("hitCount") or 0) > 0
        except (TypeError, ValueError):
            return False
    if tool_name == "find_excerpt_page":
        return bool(data.get("matched"))
    if tool_name == "get_page_text":
        return bool(str(data.get("text") or "").strip())
    return False


async def _run_reviewer_react_legacy(
    *,
    reviewer_llm: ChatOpenAI,
    task_id: str,
    total_pages: int,
    chunk_count: int,
    draft_items: Sequence[Dict[str, Any]],
    review_context: str,
    page_texts: Sequence[str],
    settings: Any,
    material_risk_cap: int,
    high_risk_cap: int,
    vector_ready: bool,
    strict_mode: bool = False,
) -> Dict[str, Any]:
    tools = get_reviewer_tool_registry()
    evidence_tool_names = {"vector_search", "keyword_search", "get_page_text", "find_excerpt_page"}
    if strict_mode:
        max_steps = max(1, int(getattr(settings, "react_strict_max_steps", 6)))
        max_tool_calls = max(1, int(getattr(settings, "react_strict_max_tool_calls", 8)))
    else:
        max_steps = max(1, int(getattr(settings, "react_max_steps", 8)))
        max_tool_calls = max(1, int(getattr(settings, "react_max_tool_calls", 12)))
    tool_timeout_ms = max(100, int(getattr(settings, "react_tool_timeout_ms", 2000)))
    require_evidence_before_final = bool(getattr(settings, "react_require_evidence_before_final", True))
    min_evidence_tool_calls = max(0, int(getattr(settings, "react_min_evidence_tool_calls", 1)))

    tool_instructions = {
        "vector_search": {"required": ["query"], "optional": ["top_k"]},
        "keyword_search": {"required": ["query"], "optional": ["top_k", "max_snippet_chars"]},
        "get_page_text": {"required": ["page_no"], "optional": ["max_chars"]},
        "find_excerpt_page": {"required": ["excerpt"], "optional": ["max_scan_pages"]},
        "law_lookup": {"required": ["risk_type"], "optional": ["risk_desc"]},
    }

    react_system_prompt = (
        "你是一名高级企业法务合伙人（ReAct Reviewer）。"
        "你要用工具进行证据核验后再给最终结论。"
        "每一步只能输出一个 JSON 对象，且只能是以下两种形态之一：\n"
        "1) 工具调用："
        '{"action":"tool","tool_name":"<tool>","tool_args":{...},"thought":"..."}\n'
        "2) 最终答案："
        '{"action":"final","final_json":{...完整审查结果...},"thought":"..."}\n'
        "约束：\n"
        "- 工具不足以支撑结论时，必须继续调用工具，不要直接猜测。\n"
        "- final_json 必须满足：summary + riskItems 结构，riskLevel 只能 HIGH/MEDIUM/LOW。\n"
        "- contractExcerpt 必须尽可能逐字摘录。\n"
        "- 仅输出 JSON，不要输出 markdown 或解释文字。"
    )
    if require_evidence_before_final and min_evidence_tool_calls > 0:
        react_system_prompt += (
            f"\n- 在输出 final 前，至少完成 {min_evidence_tool_calls} 次有效证据调用："
            "vector_search / keyword_search / get_page_text / find_excerpt_page。"
        )
    if strict_mode:
        react_system_prompt += (
            "\n[STRICT MODE]\n"
            "- 必须优先删除证据不足风险，宁缺毋滥。\n"
            "- 同一条款同类风险必须合并，不得碎片化。\n"
            "- 如 legalBasis 缺失，请调用 law_lookup；如 pageNo 存疑，请调用 find_excerpt_page。\n"
            "- 在预算耗尽前必须返回 final。"
        )

    observations: List[Dict[str, Any]] = []
    tool_calls = 0
    evidence_tool_calls = 0
    final_rejected_no_evidence_count = 0
    vector_index_ready = vector_ready
    draft_json = _safe_json_dumps({"draftRiskItems": list(draft_items)}, max_chars=12000)
    condensed_context = _clip_text(review_context, max_chars=max(8000, settings.review_context_chars // 2))
    trace_payload: Dict[str, Any] = {
        "taskId": task_id,
        "mode": "react_strict" if strict_mode else "react",
        "startedAt": datetime.utcnow().isoformat(),
        "maxSteps": max_steps,
        "maxToolCalls": max_tool_calls,
        "toolTimeoutMs": tool_timeout_ms,
        "requireEvidenceBeforeFinal": require_evidence_before_final,
        "minEvidenceToolCalls": min_evidence_tool_calls,
    }
    final_output: Dict[str, Any] | None = None
    error_message: str | None = None

    try:
        for step in range(1, max_steps + 1):
            recent_observations = observations[-6:]
            human_prompt = (
                f"任务ID={task_id}，总页数={total_pages}，分块数={chunk_count}\n"
                f"约束：最终风险条数建议上限={material_risk_cap}，高风险建议上限={high_risk_cap}\n"
                f"步骤预算：step={step}/{max_steps}，tool_calls={tool_calls}/{max_tool_calls}\n"
                f"可用工具定义：{_safe_json_dumps(tool_instructions, max_chars=2500)}\n\n"
                f"证据上下文：\n{condensed_context}\n\n"
                f"初审草稿：\n{draft_json}\n\n"
                f"历史观察（最近6条）：\n{_safe_json_dumps(recent_observations, max_chars=4500)}\n\n"
                "请输出本步 JSON。"
            )
            llm_resp = await reviewer_llm.ainvoke(
                [
                    SystemMessage(content=react_system_prompt),
                    HumanMessage(content=human_prompt),
                ]
            )
            content = llm_resp.content if isinstance(llm_resp.content, str) else _safe_json_dumps(llm_resp.content)
            parsed = _extract_json_object(content)
            if parsed is None:
                observations.append(
                    {
                        "step": step,
                        "kind": "parse_error",
                        "message": "model output is not valid json object",
                        "raw": _clip_text(content, 800),
                    }
                )
                continue

            action_payload = _normalize_react_action(parsed)
            action = action_payload["action"]
            if action == "final":
                if require_evidence_before_final and evidence_tool_calls < min_evidence_tool_calls:
                    final_rejected_no_evidence_count += 1
                    observations.append(
                        {
                            "step": step,
                            "kind": "final_rejected_no_evidence",
                            "required": min_evidence_tool_calls,
                            "current": evidence_tool_calls,
                            "hint": "call evidence tools before final",
                        }
                    )
                    continue

                final_json = action_payload.get("final_json")
                validated = _ensure_audit_output_schema(final_json)
                validated = await _post_verify_final_with_tools(
                    task_id=task_id,
                    payload=validated,
                    page_texts=page_texts,
                    settings=settings,
                    tools=tools,
                    tool_timeout_ms=tool_timeout_ms,
                    observations=observations,
                )
                validated = _ensure_audit_output_schema(validated)
                final_output = validated
                logger.info(
                    "ReAct reviewer completed, taskId=%s, strict=%s, steps=%d, tool_calls=%d, risks=%d",
                    task_id,
                    strict_mode,
                    step,
                    tool_calls,
                    len(validated.get("riskItems") or []),
                )
                return validated

            if action != "tool":
                observations.append(
                    {
                        "step": step,
                        "kind": "invalid_action",
                        "payload": action_payload,
                    }
                )
                continue

            if tool_calls >= max_tool_calls:
                observations.append(
                    {
                        "step": step,
                        "kind": "budget_exhausted",
                        "message": "tool call budget reached",
                    }
                )
                continue

            tool_name = action_payload.get("tool_name", "")
            tool_fn = tools.get(tool_name)
            if tool_fn is None:
                observations.append(
                    {
                        "step": step,
                        "kind": "unknown_tool",
                        "tool_name": tool_name,
                    }
                )
                continue

            tool_args = action_payload.get("tool_args") or {}
            kwargs = _build_tool_call_kwargs(
                tool_name=tool_name,
                tool_args=tool_args,
                task_id=task_id,
                page_texts=page_texts,
                settings=settings,
                vector_ready=vector_index_ready,
            )
            tool_result = await run_tool_with_timeout(
                tool_name=tool_name,
                tool_fn=tool_fn,
                timeout_ms=tool_timeout_ms,
                **kwargs,
            )
            tool_calls += 1
            if tool_name == "vector_search" and tool_result.get("ok"):
                vector_index_ready = True
            if tool_name in evidence_tool_names and _is_effective_evidence_result(tool_name, tool_result):
                evidence_tool_calls += 1
            observations.append(
                {
                    "step": step,
                    "kind": "tool_result",
                    "tool_name": tool_name,
                    "tool_args": _compact_tool_runtime_payload(kwargs),
                    "tool_result": _safe_json_dumps(tool_result, max_chars=1600),
                }
            )

        error_message = (
            f"ReAct reviewer exhausted budget without final answer: "
            f"max_steps={max_steps}, max_tool_calls={max_tool_calls}, strict={strict_mode}"
        )
        raise RuntimeError(error_message)
    except Exception as ex:
        if error_message is None:
            error_message = str(ex)
        raise
    finally:
        trace_payload["finishedAt"] = datetime.utcnow().isoformat()
        trace_payload["toolCalls"] = tool_calls
        trace_payload["evidenceToolCalls"] = evidence_tool_calls
        trace_payload["finalRejectedNoEvidenceCount"] = final_rejected_no_evidence_count
        trace_payload["observationCount"] = len(observations)
        trace_payload["observations"] = observations
        if final_output is not None:
            trace_payload["finalSummary"] = final_output.get("summary")
            trace_payload["finalRiskCount"] = len(final_output.get("riskItems") or [])
        if error_message:
            trace_payload["error"] = error_message
        _persist_react_trace(task_id=task_id, trace_payload=trace_payload, settings=settings)


def _stringify_ai_content(value: Any, max_chars: int = 1200) -> str:
    if isinstance(value, str):
        return _clip_text(value, max_chars)
    return _clip_text(_safe_json_dumps(value, max_chars=max_chars), max_chars)


def _extract_post_verify_metrics(observations: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    post = None
    for obs in reversed(list(observations)):
        if isinstance(obs, dict) and obs.get("kind") == "post_verify_summary":
            post = obs
            break
    if not post:
        return {"excerpt_locate_success_rate": 0.0}

    try:
        input_items = int(post.get("inputItems") or 0)
    except (TypeError, ValueError):
        input_items = 0
    try:
        output_items = int(post.get("outputItems") or 0)
    except (TypeError, ValueError):
        output_items = 0
    if input_items <= 0:
        return {"excerpt_locate_success_rate": 0.0}
    return {"excerpt_locate_success_rate": round(output_items / input_items, 4)}


def _compute_legal_basis_fill_rate(risk_items: Sequence[Dict[str, Any]]) -> float:
    items = [x for x in risk_items if isinstance(x, dict)]
    if not items:
        return 0.0
    filled = 0
    for item in items:
        if str(item.get("legalBasis") or "").strip():
            filled += 1
    return round(filled / len(items), 4)


async def _run_reviewer_react_native(
    *,
    reviewer_llm: ChatOpenAI,
    task_id: str,
    total_pages: int,
    chunk_count: int,
    draft_items: Sequence[Dict[str, Any]],
    review_context: str,
    page_texts: Sequence[str],
    settings: Any,
    material_risk_cap: int,
    high_risk_cap: int,
    vector_ready: bool,
    strict_mode: bool = False,
) -> Dict[str, Any]:
    tools = get_reviewer_tool_registry()
    tool_schemas = get_reviewer_tool_schemas()
    evidence_tool_names = {"vector_search", "keyword_search", "get_page_text", "find_excerpt_page"}
    if strict_mode:
        max_steps = max(1, int(getattr(settings, "react_strict_max_steps", 6)))
        max_tool_calls = max(1, int(getattr(settings, "react_strict_max_tool_calls", 8)))
    else:
        max_steps = max(1, int(getattr(settings, "react_max_steps", 8)))
        max_tool_calls = max(1, int(getattr(settings, "react_max_tool_calls", 12)))

    tool_timeout_ms = max(100, int(getattr(settings, "react_tool_timeout_ms", 2000)))
    require_evidence_before_final = bool(getattr(settings, "react_require_evidence_before_final", True))
    min_evidence_tool_calls = max(0, int(getattr(settings, "react_min_evidence_tool_calls", 1)))
    allow_tools_in_final = bool(getattr(settings, "react_final_allow_tools", False))
    finalize_on_budget_exhaust = bool(getattr(settings, "react_finalize_on_budget_exhaust", True))
    obs_max_chars = max(200, int(getattr(settings, "react_obs_max_chars", 1200)))
    obs_topk_cap = max(1, int(getattr(settings, "react_obs_topk_cap", 2)))
    trace_include_detail = bool(getattr(settings, "react_trace_include_detail", True))

    tool_llm = reviewer_llm.bind_tools(tool_schemas, tool_choice="auto")
    final_llm = reviewer_llm if not allow_tools_in_final else reviewer_llm.bind_tools(tool_schemas, tool_choice="none")
    final_parser = JsonOutputParser(pydantic_object=_AuditOutput)

    react_system_prompt = (
        "你是一名高级企业法务合伙人（Native Tool-Calling Reviewer）。"
        "你的职责是先调用工具核验证据，再输出最终审查结论。"
        "要求：\n"
        "- 每轮优先使用最少必要工具获取证据；禁止猜测。\n"
        "- 证据不足时，优先继续工具调用。\n"
        "- 最终输出必须满足 summary + riskItems，riskLevel 只能 HIGH/MEDIUM/LOW。\n"
        "- contractExcerpt 尽量逐字摘录，pageNo 必须整数。"
    )
    if require_evidence_before_final and min_evidence_tool_calls > 0:
        react_system_prompt += (
            f"\n- 在最终输出前至少完成 {min_evidence_tool_calls} 次有效证据调用"
            "（vector_search / keyword_search / get_page_text / find_excerpt_page）。"
        )
    if strict_mode:
        react_system_prompt += (
            "\n[STRICT MODE]\n"
            "- 优先删除证据不足风险，宁缺毋滥；"
            "- 同一条款同类风险必须合并；"
            "- legalBasis 缺失时应补法条。"
        )

    final_system_prompt = (
        "你是一名高级企业法务合伙人。"
        "现在只做最终结果收敛：基于给定证据输出最终 JSON。"
        "禁止调用任何工具，禁止输出 markdown，禁止解释性前后缀。"
        "必须仅输出合法 JSON，结构为 summary + riskItems。"
    )

    draft_json = _safe_json_dumps({"draftRiskItems": list(draft_items)}, max_chars=12000)
    condensed_context = _clip_text(review_context, max_chars=max(6000, settings.review_context_chars // 2))

    observations: List[Dict[str, Any]] = []
    observation_views: List[Dict[str, Any]] = []
    tool_phase_messages: List[Any] = []
    tool_calls = 0
    evidence_tool_calls = 0
    final_rejected_no_evidence_count = 0
    vector_index_ready = vector_ready
    budget_exhausted = False
    final_output: Dict[str, Any] | None = None
    error_message: str | None = None

    trace_payload: Dict[str, Any] = {
        "taskId": task_id,
        "mode": "react_native_strict" if strict_mode else "react_native",
        "startedAt": datetime.utcnow().isoformat(),
        "maxSteps": max_steps,
        "maxToolCalls": max_tool_calls,
        "toolTimeoutMs": tool_timeout_ms,
        "requireEvidenceBeforeFinal": require_evidence_before_final,
        "minEvidenceToolCalls": min_evidence_tool_calls,
        "finalAllowTools": allow_tools_in_final,
        "finalizeOnBudgetExhaust": finalize_on_budget_exhaust,
    }

    def _append_observation(entry: Dict[str, Any]) -> None:
        observations.append(entry)
        view = entry.get("observation_view")
        if isinstance(view, dict):
            observation_views.append(view)

    def _parse_final_output_from_text(raw_text: str) -> Dict[str, Any]:
        parsed_payload = final_parser.parse(raw_text)
        if isinstance(parsed_payload, dict):
            return _ensure_audit_output_schema(parsed_payload)
        return _ensure_audit_output_schema(parsed_payload.model_dump())  # type: ignore[union-attr]

    async def _generate_final_json(reason: str) -> Dict[str, Any]:
        recent_obs = observation_views[-8:]
        final_prompt = (
            f"任务ID={task_id}，总页数={total_pages}，分块数={chunk_count}\n"
            f"收敛原因：{reason}\n"
            f"风险数量建议上限={material_risk_cap}，高风险建议上限={high_risk_cap}\n"
            f"证据上下文：\n{condensed_context}\n\n"
            f"初审草稿：\n{draft_json}\n\n"
            f"证据观察摘要（最近8条）：\n{_safe_json_dumps(recent_obs, max_chars=5000)}\n\n"
            f"请严格按以下格式输出最终 JSON：\n{final_parser.get_format_instructions()}"
        )
        final_messages: List[Any] = [SystemMessage(content=final_system_prompt), HumanMessage(content=final_prompt)]
        if allow_tools_in_final:
            final_messages.extend(tool_phase_messages[-6:])
        llm_resp = await final_llm.ainvoke(final_messages)
        raw_text = _stringify_ai_content(llm_resp.content, max_chars=12000)

        native_calls = _extract_native_tool_calls(llm_resp)
        if native_calls and not allow_tools_in_final:
            _append_observation(
                {
                    "kind": "final_unexpected_tool_calls",
                    "reason": reason,
                    "observation_view": {
                        "kind": "final_unexpected_tool_calls",
                        "count": len(native_calls),
                    },
                    "trace_detail": {
                        "raw": _clip_text(raw_text, 1200),
                    },
                }
            )

        try:
            return _parse_final_output_from_text(raw_text)
        except Exception:
            fallback_json = _extract_json_object(raw_text)
            if isinstance(fallback_json, dict):
                return _ensure_audit_output_schema(fallback_json)
            raise

    try:
        for step in range(1, max_steps + 1):
            if tool_calls >= max_tool_calls:
                budget_exhausted = True
                _append_observation(
                    {
                        "step": step,
                        "kind": "budget_exhausted",
                        "observation_view": {
                            "kind": "budget_exhausted",
                            "toolCalls": tool_calls,
                            "maxToolCalls": max_tool_calls,
                        },
                    }
                )
                if finalize_on_budget_exhaust:
                    break

            recent_obs = observation_views[-6:]
            tool_prompt = (
                f"任务ID={task_id}，总页数={total_pages}，分块数={chunk_count}\n"
                f"步骤预算：step={step}/{max_steps}，tool_calls={tool_calls}/{max_tool_calls}\n"
                f"约束：最终风险条数建议上限={material_risk_cap}，高风险建议上限={high_risk_cap}\n"
                f"证据上下文：\n{condensed_context}\n\n"
                f"初审草稿：\n{draft_json}\n\n"
                f"历史观察（最近6条）：\n{_safe_json_dumps(recent_obs, max_chars=4000)}\n\n"
                "请按需要调用工具；如果你认为证据已充分，也可以直接给出简短收敛判断。"
            )
            llm_resp = await tool_llm.ainvoke(
                [
                    SystemMessage(content=react_system_prompt),
                    HumanMessage(content=tool_prompt),
                    *tool_phase_messages[-10:],
                ]
            )
            tool_phase_messages.append(llm_resp)
            native_calls = _extract_native_tool_calls(llm_resp)
            if not native_calls:
                _append_observation(
                    {
                        "step": step,
                        "kind": "no_tool_call",
                        "observation_view": {
                            "kind": "no_tool_call",
                            "preview": _stringify_ai_content(llm_resp.content, max_chars=360),
                        },
                    }
                )
                # no tool call usually means model is ready to finalize.
                break

            for call in native_calls:
                if tool_calls >= max_tool_calls:
                    budget_exhausted = True
                    _append_observation(
                        {
                            "step": step,
                            "kind": "budget_exhausted",
                            "observation_view": {
                                "kind": "budget_exhausted",
                                "toolCalls": tool_calls,
                                "maxToolCalls": max_tool_calls,
                            },
                        }
                    )
                    break

                tool_name = str(call.get("name") or "")
                tool_fn = tools.get(tool_name)
                if tool_fn is None:
                    _append_observation(
                        {
                            "step": step,
                            "kind": "unknown_tool",
                            "observation_view": {
                                "kind": "unknown_tool",
                                "tool": tool_name,
                            },
                        }
                    )
                    continue

                kwargs = _build_tool_call_kwargs(
                    tool_name=tool_name,
                    tool_args=call.get("args") or {},
                    task_id=task_id,
                    page_texts=page_texts,
                    settings=settings,
                    vector_ready=vector_index_ready,
                )
                tool_result = await run_tool_with_timeout(
                    tool_name=tool_name,
                    tool_fn=tool_fn,
                    timeout_ms=tool_timeout_ms,
                    **kwargs,
                )
                tool_calls += 1
                if tool_name == "vector_search" and tool_result.get("ok"):
                    vector_index_ready = True
                if tool_name in evidence_tool_names and _is_effective_evidence_result(tool_name, tool_result):
                    evidence_tool_calls += 1

                obs_view = _build_tool_observation_view(
                    tool_name=tool_name,
                    tool_result=tool_result,
                    obs_max_chars=obs_max_chars,
                    obs_topk_cap=obs_topk_cap,
                )
                obs_entry: Dict[str, Any] = {
                    "step": step,
                    "kind": "tool_result",
                    "tool_name": tool_name,
                    "observation_view": obs_view,
                }
                if trace_include_detail:
                    obs_entry["trace_detail"] = {
                        "tool_args": _compact_tool_runtime_payload(kwargs),
                        "tool_result": _safe_json_dumps(tool_result, max_chars=4500),
                    }
                _append_observation(obs_entry)
                tool_phase_messages.append(
                    ToolMessage(
                        content=_safe_json_dumps(obs_view, max_chars=max(800, obs_max_chars * 2)),
                        tool_call_id=str(call.get("id") or f"{step}-{tool_calls}"),
                    )
                )

            if budget_exhausted and finalize_on_budget_exhaust:
                break

        if require_evidence_before_final and evidence_tool_calls < min_evidence_tool_calls:
            final_rejected_no_evidence_count += 1
            _append_observation(
                {
                    "kind": "final_with_limited_evidence",
                    "observation_view": {
                        "kind": "final_with_limited_evidence",
                        "required": min_evidence_tool_calls,
                        "current": evidence_tool_calls,
                    },
                }
            )

        final_reason = "budget_exhausted" if budget_exhausted else "tool_phase_completed"
        validated = await _generate_final_json(final_reason)
        validated = await _post_verify_final_with_tools(
            task_id=task_id,
            payload=validated,
            page_texts=page_texts,
            settings=settings,
            tools=tools,
            tool_timeout_ms=tool_timeout_ms,
            observations=observations,
        )
        validated = _ensure_audit_output_schema(validated)
        final_output = validated
        logger.info(
            "ReAct native reviewer completed, taskId=%s, strict=%s, tool_calls=%d, risks=%d",
            task_id,
            strict_mode,
            tool_calls,
            len(validated.get("riskItems") or []),
        )
        return validated
    except Exception as ex:
        if error_message is None:
            error_message = str(ex)
        raise
    finally:
        trace_payload["finishedAt"] = datetime.utcnow().isoformat()
        trace_payload["toolCalls"] = tool_calls
        trace_payload["evidenceToolCalls"] = evidence_tool_calls
        trace_payload["finalRejectedNoEvidenceCount"] = final_rejected_no_evidence_count
        view_items: List[Dict[str, Any]] = []
        detail_items: List[Dict[str, Any]] = []
        for obs in observations:
            item = {
                "step": obs.get("step"),
                "kind": obs.get("kind"),
                "tool": obs.get("tool_name"),
                "observation": obs.get("observation_view"),
            }
            view_items.append(item)
            if trace_include_detail and "trace_detail" in obs:
                detail_items.append(
                    {
                        "step": obs.get("step"),
                        "kind": obs.get("kind"),
                        "tool": obs.get("tool_name"),
                        "detail": obs.get("trace_detail"),
                    }
                )
        trace_payload["observationCount"] = len(view_items)
        trace_payload["observations"] = view_items
        if trace_include_detail:
            trace_payload["traceDetail"] = detail_items
        if final_output is not None:
            final_items = final_output.get("riskItems") or []
            trace_payload["finalSummary"] = final_output.get("summary")
            trace_payload["finalRiskCount"] = len(final_items)
            quality = _extract_post_verify_metrics(observations)
            quality["legal_basis_fill_rate"] = _compute_legal_basis_fill_rate(final_items)
            trace_payload["qualityMetrics"] = quality
        if error_message:
            trace_payload["error"] = error_message
        _persist_react_trace(task_id=task_id, trace_payload=trace_payload, settings=settings)


async def _run_reviewer_react(
    *,
    reviewer_llm: ChatOpenAI,
    task_id: str,
    total_pages: int,
    chunk_count: int,
    draft_items: Sequence[Dict[str, Any]],
    review_context: str,
    page_texts: Sequence[str],
    settings: Any,
    material_risk_cap: int,
    high_risk_cap: int,
    vector_ready: bool,
    strict_mode: bool = False,
) -> Dict[str, Any]:
    use_native = bool(getattr(settings, "react_use_native_tool_calling", True))
    if use_native:
        return await _run_reviewer_react_native(
            reviewer_llm=reviewer_llm,
            task_id=task_id,
            total_pages=total_pages,
            chunk_count=chunk_count,
            draft_items=draft_items,
            review_context=review_context,
            page_texts=page_texts,
            settings=settings,
            material_risk_cap=material_risk_cap,
            high_risk_cap=high_risk_cap,
            vector_ready=vector_ready,
            strict_mode=strict_mode,
        )
    return await _run_reviewer_react_legacy(
        reviewer_llm=reviewer_llm,
        task_id=task_id,
        total_pages=total_pages,
        chunk_count=chunk_count,
        draft_items=draft_items,
        review_context=review_context,
        page_texts=page_texts,
        settings=settings,
        material_risk_cap=material_risk_cap,
        high_risk_cap=high_risk_cap,
        vector_ready=vector_ready,
        strict_mode=strict_mode,
    )


async def _extract_chunk_draft(
    chunk_idx: int,
    start_page: int,
    end_page: int,
    page_texts: Sequence[str],
    draft_chain: Any,
    job_request: AuditJobRequest,
) -> List[Dict[str, Any]]:
    chunk_text = _build_chunk_text(page_texts, start_page, end_page)
    if not chunk_text:
        logger.info("Map chunk %d pages=%d-%d has no extractable text", chunk_idx, start_page, end_page)
        return []

    payload = {
        "task_id": job_request.taskId,
        "task_no": job_request.taskNo,
        "file_name": job_request.fileName,
        "chunk_index": chunk_idx,
        "chunk_page_range": f"{start_page}-{end_page}",
        "contract_text": chunk_text,
    }

    last_exception: Exception | None = None
    for attempt in (1, 2):
        try:
            result = await draft_chain.ainvoke(payload)
            chunk_items = result.get("draftRiskItems") or []
            normalized = _normalize_chunk_drafts(chunk_items, start_page, end_page, page_texts)
            logger.info(
                "Map chunk completed index=%d pages=%d-%d, draft_count=%d",
                chunk_idx,
                start_page,
                end_page,
                len(normalized),
            )
            return normalized
        except Exception as ex:  # noqa: PERF203
            last_exception = ex
            if attempt == 2:
                break
            logger.warning(
                "Map chunk failed index=%d pages=%d-%d, retrying once: %s",
                chunk_idx,
                start_page,
                end_page,
                ex,
            )
            await asyncio.sleep(0.5)

    raise RuntimeError(f"map chunk failed index={chunk_idx}, pages={start_page}-{end_page}") from last_exception


async def _run_contract_audit_v2(job_request: AuditJobRequest) -> tuple[CallbackSummary, List[RiskItem]]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("Missing API key. Set DEEPSEEK_API_KEY in your local environment")

    page_texts = _load_pdf_pages(job_request.filePath)
    total_pages = len(page_texts)

    chunk_pages = max(1, settings.map_chunk_pages)
    overlap_pages = max(0, min(settings.map_chunk_overlap_pages, chunk_pages - 1))
    max_concurrency = max(1, settings.map_max_concurrency)
    chunk_ranges = _build_chunk_ranges(total_pages, chunk_pages, overlap_pages)

    covered_pages = {p for start, end in chunk_ranges for p in range(start, end + 1)}
    if len(covered_pages) != total_pages:
        raise RuntimeError(
            f"chunk coverage error: covered_pages={len(covered_pages)}, total_pages={total_pages}"
        )

    logger.info(
        "Map extraction started, total_pages=%d, chunk_pages=%d, overlap=%d, chunks=%d, concurrency=%d",
        total_pages,
        chunk_pages,
        overlap_pages,
        len(chunk_ranges),
        max_concurrency,
    )

    # Agent 1: Draft Extractor (Map stage)
    draft_parser = JsonOutputParser(pydantic_object=_DraftOutput)
    draft_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一名初级企业法务（Draft Extractor）。"
                "你将收到合同的一部分页码区间，请在该区间内尽可能完整提取潜在风险，宁可多提不要漏掉。"
                "这只是草稿，不做最终裁决。"
                "必须仅输出 JSON，不要输出解释文字或 Markdown。"
                "输出顶层字段必须是 draftRiskItems（数组）。"
                "每条风险的 pageNo 必须使用 [Page X] 里的绝对页码整数。"
                "contractExcerpt 必须是原文摘录，不允许改写。",
            ),
            (
                "human",
                "任务信息：\n"
                "- taskId: {task_id}\n"
                "- taskNo: {task_no}\n"
                "- fileName: {file_name}\n"
                "- chunkIndex: {chunk_index}\n"
                "- chunkPageRange: {chunk_page_range}\n\n"
                "合同区间正文（含页码标记）:\n{contract_text}\n\n"
                "请输出草稿 JSON，字段尽量包含：clauseTitle、riskType、riskLevel、pageNo、contractExcerpt、riskDesc、suggestion。\n"
                "格式要求：\n{format_instructions}",
            ),
        ]
    )

    draft_llm = _build_llm(
        model_name=job_request.modelName or settings.default_model,
        temperature=0.1,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    draft_chain = draft_prompt.partial(
        format_instructions=draft_parser.get_format_instructions()
    ) | draft_llm | draft_parser

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _run_with_semaphore(coro: Any) -> Any:
        async with semaphore:
            return await coro

    tasks = [
        asyncio.create_task(
            _run_with_semaphore(
                _extract_chunk_draft(
                    chunk_idx=index,
                    start_page=start,
                    end_page=end,
                    page_texts=page_texts,
                    draft_chain=draft_chain,
                    job_request=job_request,
                )
            )
        )
        for index, (start, end) in enumerate(chunk_ranges, start=1)
    ]

    map_results = await asyncio.gather(*tasks, return_exceptions=True)
    raw_draft_items: List[Dict[str, Any]] = []
    for idx, result in enumerate(map_results, start=1):
        if isinstance(result, Exception):
            raise RuntimeError(f"map stage failed at chunk {idx}") from result
        raw_draft_items.extend(result)

    dedup_draft_items = _dedupe_draft_items(raw_draft_items, page_texts)
    logger.info(
        "Map extraction completed, raw_draft_count=%d, dedup_draft_count=%d, coverage=%d/%d pages",
        len(raw_draft_items),
        len(dedup_draft_items),
        len(covered_pages),
        total_pages,
    )

    if not dedup_draft_items:
        summary = CallbackSummary(
            riskTotal=0,
            highRiskCount=0,
            mediumRiskCount=0,
            lowRiskCount=0,
        )
        return summary, []

    material_risk_cap = max(4, min(50, max(total_pages * 4, len(dedup_draft_items) // 2 + 2)))
    high_risk_cap = max(1, min(material_risk_cap, math.ceil(material_risk_cap * 0.45)))

    rag_queries = _build_rag_queries(dedup_draft_items)
    rag_mode = (settings.rag_mode or "hybrid").strip().lower()
    if rag_mode not in {"keyword", "vector", "hybrid"}:
        logger.warning("Unknown RAG_MODE=%s, fallback to hybrid", rag_mode)
        rag_mode = "hybrid"

    keyword_rag_context = ""
    if rag_mode in {"keyword", "hybrid"}:
        keyword_rag_context = _build_rag_context(
            page_texts=page_texts,
            queries=rag_queries,
            top_k_per_query=max(1, settings.rag_top_k_per_query),
            max_chars=max(3000, settings.rag_max_chars),
        )

    vector_rag_context = ""
    if rag_mode in {"vector", "hybrid"}:
        try:
            vector_rag_context = _build_vector_rag_context(
                page_texts=page_texts,
                queries=rag_queries,
                job_request=job_request,
                settings=settings,
            )
        except Exception as ex:  # noqa: PERF203
            logger.warning("Vector RAG failed, fallback without vector context: %s", ex)

    rag_parts: List[str] = []
    if keyword_rag_context.strip():
        rag_parts.append(f"[Keyword RAG]\n{keyword_rag_context.strip()}")
    if vector_rag_context.strip():
        rag_parts.append(f"[Vector RAG]\n{vector_rag_context.strip()}")
    rag_context = "\n\n".join(rag_parts).strip()

    logger.info(
        "RAG context prepared, mode=%s, keyword_chars=%d, vector_chars=%d, total_chars=%d",
        rag_mode,
        len(keyword_rag_context),
        len(vector_rag_context),
        len(rag_context),
    )

    review_context = _build_review_context(
        page_texts=page_texts,
        draft_items=dedup_draft_items,
        rag_context=rag_context,
        max_chars=max(10000, settings.review_context_chars),
    )

    # Agent 2: Senior Reviewer (Reduce stage)
    final_parser = JsonOutputParser(pydantic_object=_AuditOutput)
    reviewer_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一名高级企业法务合伙人。请审查初审草稿。你的核心任务是‘去伪存真、合并同类项、降噪’：\n"
                "1. 事实核查：剔除草稿中在证据上下文里找不到对应原话的‘幻觉’风险。\n"
                "2. 风险降级与剔除：剔除属于‘行业正常商业博弈’的常规条款。只有造成重大资金损失或严重法律后果的，才定为 HIGH。\n"
                "3. 去重与合并：同一条款同类风险必须合并，禁止碎片化输出。\n"
                "4. 补充法条：必须为每个保留风险给出中国法律依据（如《民法典》具体条款）。\n"
                "5. 严格按 JSON Schema 输出。\n"
                "额外硬约束：\n"
                "- contractExcerpt 必须是原文逐字摘录。\n"
                "- pageNo 必须是整数且与 [Page X] 一致。\n"
                "- riskLevel 只能为 HIGH / MEDIUM / LOW。\n"
                "- 仅输出 JSON，不要输出解释文本。",
            ),
            (
                "human",
                "全量覆盖说明：Map 阶段已覆盖合同全部页面（totalPages={total_pages}，chunkCount={chunk_count}）。\n"
                "审查约束：\n"
                "- 初审草稿条数：{draft_count}\n"
                "- 建议最终风险条数上限：{material_risk_cap}\n"
                "- 建议高风险条数上限：{high_risk_cap}\n\n"
                "证据上下文（由全量扫描结果与检索增强生成）：\n{review_context}\n\n"
                "初审草稿 JSON:\n{draft_json}\n\n"
                "请输出最终审查结果 JSON：\n{format_instructions}",
            ),
        ]
    )

    strict_reviewer_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一名高级法务合伙人（Strict Reviewer）。"
                "你必须输出严格合法的 JSON，且必须完全符合给定 schema。"
                "禁止输出 markdown、注释、解释、额外字段。"
                "若不确定风险是否真实存在，必须删除该风险。"
                "必须执行去重合并，同一条款同类风险最多保留 1 条。"
                "高风险仅在重大资金损失或严重法律后果时使用。"
                "每条保留风险都必须满足："
                "1) contractExcerpt 为原文逐字摘录；"
                "2) pageNo 为 [Page X] 对应整数；"
                "3) legalBasis 为中国法律依据；"
                "4) riskLevel 仅允许 HIGH/MEDIUM/LOW。"
                "若无法产出合法结果，返回 riskItems 空数组且 summary 全 0。",
            ),
            (
                "human",
                "全量覆盖说明：Map 阶段已覆盖合同全部页面（totalPages={total_pages}，chunkCount={chunk_count}）。\n"
                "审查约束：\n"
                "- 初审草稿条数：{draft_count}\n"
                "- 建议最终风险条数上限：{material_risk_cap}\n"
                "- 建议高风险条数上限：{high_risk_cap}\n\n"
                "证据上下文：\n{review_context}\n\n"
                "初审草稿 JSON:\n{draft_json}\n\n"
                "目标 JSON Schema:\n{strict_schema}\n\n"
                "输出格式要求:\n{format_instructions}\n\n"
                "请只返回最终 JSON。",
            ),
        ]
    )

    react_repair_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一名企业法务 JSON 修复器。"
                "上一步 ReAct 审查失败，你的任务是一次性输出严格合法的最终 JSON。"
                "必须遵守：\n"
                "1) 只输出 JSON，不要输出解释文本。\n"
                "2) 顶层结构必须为 summary + riskItems。\n"
                "3) riskLevel 仅允许 HIGH/MEDIUM/LOW。\n"
                "4) 对证据不充分条目直接删除，不要猜测。\n"
                "5) contractExcerpt 必须为原文摘录，pageNo 必须为整数。\n"
                "6) 若某项字段不确定，宁可留空或降级，不要生成幻觉。"
            ),
            (
                "human",
                "失败原因：\n{react_error}\n\n"
                "全量覆盖说明：Map 阶段已覆盖合同全部页面（totalPages={total_pages}，chunkCount={chunk_count}）。\n"
                "审查约束：\n"
                "- 初审草稿条数：{draft_count}\n"
                "- 建议最终风险条数上限：{material_risk_cap}\n"
                "- 建议高风险条数上限：{high_risk_cap}\n\n"
                "证据上下文（已裁剪）：\n{repair_context}\n\n"
                "初审草稿 JSON:\n{draft_json}\n\n"
                "目标 JSON Schema:\n{strict_schema}\n\n"
                "输出格式要求：\n{format_instructions}",
            ),
        ]
    )

    reviewer_llm = _build_llm(
        model_name=job_request.modelName or settings.default_model,
        temperature=0.0,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    reviewer_chain = reviewer_prompt | reviewer_llm | final_parser
    reviewer_payload = {
        "total_pages": total_pages,
        "chunk_count": len(chunk_ranges),
        "review_context": review_context,
        "draft_json": json.dumps({"draftRiskItems": dedup_draft_items}, ensure_ascii=False),
        "draft_count": len(dedup_draft_items),
        "material_risk_cap": material_risk_cap,
        "high_risk_cap": high_risk_cap,
        "format_instructions": final_parser.get_format_instructions(),
    }
    fallback_context_chars = max(
        2000,
        min(
            int(getattr(settings, "fallback_review_context_chars", 6000)),
            max(3000, settings.review_context_chars // 3),
        ),
    )
    fallback_review_context = _build_review_context(
        page_texts=page_texts,
        draft_items=dedup_draft_items,
        rag_context=rag_context,
        max_chars=fallback_context_chars,
    )
    if not fallback_review_context.strip():
        fallback_review_context = _clip_text(review_context, fallback_context_chars)

    reviewer_payload_light = {
        **reviewer_payload,
        "review_context": fallback_review_context,
    }
    logger.info(
        "Reviewer contexts prepared, full_chars=%d, light_chars=%d, light_cap=%d",
        len(review_context),
        len(fallback_review_context),
        fallback_context_chars,
    )

    async def _run_workflow_reviewer(
        use_lightweight_context: bool = False,
        single_pass: bool = False,
    ) -> Dict[str, Any]:
        payload = reviewer_payload_light if use_lightweight_context else reviewer_payload
        context_mode = "light" if use_lightweight_context else "full"
        strict_chain = strict_reviewer_prompt | reviewer_llm | final_parser
        strict_payload = {
            **payload,
            "strict_schema": json.dumps(_AuditOutput.model_json_schema(), ensure_ascii=False),
        }

        if single_pass:
            try:
                return await strict_chain.ainvoke(strict_payload)
            except Exception as ex:
                logger.warning(
                    "Workflow reviewer strict single-pass failed, retrying once with normal schema, context_mode=%s: %s",
                    context_mode,
                    ex,
                )
                return await reviewer_chain.ainvoke(payload)

        try:
            return await reviewer_chain.ainvoke(payload)
        except Exception as ex:
            logger.warning(
                "Senior review first attempt failed, retrying with strict schema guard, context_mode=%s: %s",
                context_mode,
                ex,
            )
            return await strict_chain.ainvoke(strict_payload)

    async def _run_react_json_repair_once(react_error: str) -> Dict[str, Any]:
        repair_chain = react_repair_prompt | reviewer_llm | final_parser
        repair_payload = {
            "react_error": _clip_text(str(react_error or ""), 1500),
            "total_pages": total_pages,
            "chunk_count": len(chunk_ranges),
            "draft_count": len(dedup_draft_items),
            "material_risk_cap": material_risk_cap,
            "high_risk_cap": high_risk_cap,
            "repair_context": _clip_text(review_context, max(5000, settings.review_context_chars // 3)),
            "draft_json": json.dumps({"draftRiskItems": dedup_draft_items}, ensure_ascii=False),
            "strict_schema": json.dumps(_AuditOutput.model_json_schema(), ensure_ascii=False),
            "format_instructions": final_parser.get_format_instructions(),
        }
        return await repair_chain.ainvoke(repair_payload)

    agent2_mode = str(getattr(settings, "agent2_mode", "workflow") or "workflow").strip().lower()
    if agent2_mode not in {"workflow", "react"}:
        logger.warning("Unknown AGENT2_MODE=%s, fallback to workflow", agent2_mode)
        agent2_mode = "workflow"
    fallback_single_pass = bool(getattr(settings, "fallback_workflow_single_pass", True))

    reviewed_result: Dict[str, Any]
    if agent2_mode == "react":
        try:
            reviewed_result = await _run_reviewer_react(
                reviewer_llm=reviewer_llm,
                task_id=str(job_request.taskId),
                total_pages=total_pages,
                chunk_count=len(chunk_ranges),
                draft_items=dedup_draft_items,
                review_context=review_context,
                page_texts=page_texts,
                settings=settings,
                material_risk_cap=material_risk_cap,
                high_risk_cap=high_risk_cap,
                vector_ready=bool(vector_rag_context.strip()),
                strict_mode=False,
            )
        except Exception as ex:  # noqa: PERF203
            strict_retry_enabled = bool(getattr(settings, "react_retry_strict_once", True))
            if strict_retry_enabled:
                logger.warning(
                    "ReAct reviewer failed, retrying once with JSON repair chain, taskId=%s, err=%s",
                    job_request.taskId,
                    ex,
                )
                try:
                    reviewed_result = await _run_react_json_repair_once(str(ex))
                except Exception as ex2:  # noqa: PERF203
                    logger.warning(
                        "ReAct JSON repair failed, fallback to workflow reviewer, taskId=%s, err=%s",
                        job_request.taskId,
                        ex2,
                    )
                    reviewed_result = await _run_workflow_reviewer(
                        use_lightweight_context=True,
                        single_pass=fallback_single_pass,
                    )
            else:
                logger.warning(
                    "ReAct reviewer failed and strict retry disabled, fallback to workflow reviewer, taskId=%s, err=%s",
                    job_request.taskId,
                    ex,
                )
                reviewed_result = await _run_workflow_reviewer(
                    use_lightweight_context=True,
                    single_pass=fallback_single_pass,
                )
    else:
        reviewed_result = await _run_workflow_reviewer()

    raw_items = reviewed_result.get("riskItems") or []
    logger.info("Senior review completed, finalized %d risks", len(raw_items))

    risk_items: List[RiskItem] = []
    for index, item in enumerate(raw_items, start=1):
        excerpt = str(item.get("contractExcerpt") or "").strip()
        if not excerpt:
            continue

        raw_page_no = _normalize_page_no(item.get("pageNo"), default=1)
        page_no = _resolve_page_no(raw_page_no, excerpt, page_texts)

        risk_items.append(
            RiskItem(
                seqNo=item.get("seqNo") or index,
                riskType=item.get("riskType") or "UNKNOWN",
                riskLevel=_normalize_level(item.get("riskLevel")),
                riskScore=_to_score(item.get("riskScore")),
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

    before_denoise = len(risk_items)
    risk_items, downgraded_high = _merge_and_denoise_items(
        items=risk_items,
        page_count=total_pages,
        draft_count=len(dedup_draft_items),
    )
    logger.info(
        "Post-review denoise completed, reduced from %d to %d risks, downgraded %d high-risk items",
        before_denoise,
        len(risk_items),
        downgraded_high,
    )

    level_count = _count_by_level(risk_items)
    summary = CallbackSummary(
        riskTotal=len(risk_items),
        highRiskCount=level_count["HIGH"],
        mediumRiskCount=level_count["MEDIUM"],
        lowRiskCount=level_count["LOW"],
    )
    return summary, risk_items


async def run_contract_audit(job_request: AuditJobRequest) -> tuple[CallbackSummary, List[RiskItem]]:
    settings = get_settings()
    if settings.rag_v3_enabled:
        try:
            from services.v3_pipeline import run_contract_audit_v3

            return await run_contract_audit_v3(
                job_request=job_request,
                fallback_runner=_run_contract_audit_v2,
                page_loader=_load_pdf_pages,
            )
        except Exception as ex:  # noqa: PERF203
            logger.warning("RAG_V3 enabled but V3 pipeline failed, fallback to V2: %s", ex)
            return await _run_contract_audit_v2(job_request)
    return await _run_contract_audit_v2(job_request)
