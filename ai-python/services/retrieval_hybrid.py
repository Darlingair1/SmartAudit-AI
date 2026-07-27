from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Sequence, Tuple

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from core.config import Settings
from services.legal_tokenizer import tokenize_legal_text
from services.v3_types import ChildChunk, ParentChunk, RetrievalCandidate, SecurityContext

_EMBED_CACHE: Dict[Tuple[str, str, bool, int], HuggingFaceEmbeddings] = {}


def _resolve_local_path(path_value: str) -> Path:
    candidate = Path((path_value or "").strip())
    if candidate.is_absolute():
        return candidate
    return (Path(__file__).resolve().parents[2] / candidate).resolve()


def _safe_collection_name(prefix: str, sec: SecurityContext) -> str:
    raw = f"{prefix}-{sec.tenant_id}-{sec.task_id}".lower()
    value = re.sub(r"[^a-z0-9_-]", "-", raw)
    value = re.sub(r"-{2,}", "-", value).strip("-_")
    if len(value) < 3:
        value = "smartaudit-v3"
    return value[:63]


def _get_embeddings(settings: Settings) -> HuggingFaceEmbeddings:
    model_dir = _resolve_local_path(settings.embedding_model_path)
    key = (str(model_dir), settings.embedding_device, settings.embedding_normalize, max(1, settings.embedding_batch_size))
    cached = _EMBED_CACHE.get(key)
    if cached is not None:
        return cached
    embeddings = HuggingFaceEmbeddings(
        model_name=str(model_dir),
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={
            "normalize_embeddings": settings.embedding_normalize,
            "batch_size": max(1, settings.embedding_batch_size),
        },
    )
    _EMBED_CACHE[key] = embeddings
    return embeddings


def _approx_tokens(text: str) -> int:
    return max(1, len(str(text or "").strip()) // 2)


def build_parent_child_chunks(
    page_texts: Sequence[str],
    sec: SecurityContext,
    settings: Settings,
    parse_quality: Dict[str, Any],
) -> tuple[List[ParentChunk], List[ChildChunk]]:
    parents: List[ParentChunk] = []
    children: List[ChildChunk] = []
    parent_min = max(100, settings.parent_chunk_min_tokens)
    parent_max = max(parent_min, settings.parent_chunk_max_tokens)
    child_size = max(80, settings.child_chunk_size_tokens)
    child_overlap = max(0, min(settings.child_chunk_overlap_tokens, child_size - 1))

    parent_idx = 0
    child_idx = 0
    carry_pages: List[Tuple[int, str]] = []
    carry_tokens = 0

    def flush_parent() -> None:
        nonlocal parent_idx, child_idx, carry_pages, carry_tokens
        if not carry_pages:
            return
        parent_idx += 1
        p_id = f"p-{parent_idx:04d}"
        page_start = carry_pages[0][0]
        page_end = carry_pages[-1][0]
        parent_text = "\n".join([f"[Page {p}] {t}" for p, t in carry_pages]).strip()
        parent_meta = {
            "tenant_id": sec.tenant_id,
            "org_id": sec.org_id,
            "user_id": sec.user_id,
            "permission_scope": sec.permission_scope,
            "task_id": sec.task_id,
            "document_id": sec.document_id,
            "contract_id": sec.contract_id,
            "page_start": page_start,
            "page_end": page_end,
            "chapter_no": None,
            "clause_id": f"{parent_idx}",
            "clause_title": f"ParentChunk-{parent_idx}",
            "parent_id": p_id,
            "chunk_version": settings.chunk_version,
            "parser_version": settings.parser_version,
            "source_type": settings.source_type_default,
            "parse_quality": parse_quality.get("parse_quality", "WARNING"),
        }
        parent = ParentChunk(parent_id=p_id, text=parent_text, page_start=page_start, page_end=page_end, metadata=parent_meta)
        parents.append(parent)

        # split into children by char sliding window with token approximation.
        compact = parent_text
        char_size = max(160, child_size * 2)
        char_overlap = max(0, child_overlap * 2)
        step = max(1, char_size - char_overlap)
        offset = 0
        while offset < len(compact):
            chunk = compact[offset : offset + char_size].strip()
            if not chunk:
                break
            child_idx += 1
            c_id = f"c-{parent_idx:04d}-{child_idx:04d}"
            page_no = page_start
            # choose first page marker within chunk if present
            m = re.search(r"\[Page\s+(\d+)\]", chunk)
            if m:
                page_no = int(m.group(1))
            meta = dict(parent_meta)
            meta.update(
                {
                    "page_no": page_no,
                    "parent_id": p_id,
                    "child_id": c_id,
                    "offset_start": offset,
                    "offset_end": min(len(compact), offset + char_size),
                }
            )
            children.append(
                ChildChunk(
                    child_id=c_id,
                    parent_id=p_id,
                    text=chunk,
                    page_no=page_no,
                    offset_start=offset,
                    offset_end=min(len(compact), offset + char_size),
                    metadata=meta,
                )
            )
            offset += step

        carry_pages = []
        carry_tokens = 0

    for page_no, text in enumerate(page_texts, start=1):
        txt = str(text or "").strip()
        if not txt:
            continue
        tks = _approx_tokens(txt)
        if carry_pages and carry_tokens + tks > parent_max:
            flush_parent()
        carry_pages.append((page_no, txt))
        carry_tokens += tks
        if carry_tokens >= parent_min:
            flush_parent()

    flush_parent()
    return parents, children


def _score_bm25_like(query: str, text: str) -> float:
    q_tokens = tokenize_legal_text(query)
    t_tokens = tokenize_legal_text(text)
    if not q_tokens or not t_tokens:
        return 0.0
    tf = defaultdict(int)
    for token in t_tokens:
        tf[token] += 1
    score = 0.0
    doc_len = len(t_tokens)
    for q in q_tokens:
        f = tf.get(q, 0)
        if f == 0:
            continue
        score += (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * doc_len / 120.0))
    return score


def _extract_matched_terms(query: str, text: str, cap: int = 8) -> List[str]:
    terms = []
    for q in tokenize_legal_text(query):
        if q and q in text:
            terms.append(q)
        if len(terms) >= cap:
            break
    return terms


def _rrf_fuse(
    bm25_ranked: List[RetrievalCandidate],
    vector_ranked: List[RetrievalCandidate],
    k: int,
    top_k: int,
) -> List[RetrievalCandidate]:
    merged: Dict[str, RetrievalCandidate] = {}
    for idx, c in enumerate(bm25_ranked, start=1):
        if c.candidate_id not in merged:
            merged[c.candidate_id] = c
        merged[c.candidate_id].bm25_rank = idx
        merged[c.candidate_id].rrf_score += 1.0 / (k + idx)
    for idx, c in enumerate(vector_ranked, start=1):
        if c.candidate_id not in merged:
            merged[c.candidate_id] = c
        merged[c.candidate_id].vector_rank = idx
        merged[c.candidate_id].rrf_score += 1.0 / (k + idx)

    fused = sorted(merged.values(), key=lambda x: x.rrf_score, reverse=True)
    return fused[: max(1, top_k)]


def _index_vector_children(children: Sequence[ChildChunk], sec: SecurityContext, settings: Settings) -> Chroma:
    persist_dir = _resolve_local_path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    embeddings = _get_embeddings(settings)
    collection_name = _safe_collection_name(settings.chroma_collection_prefix + "-v3", sec)
    store = Chroma(collection_name=collection_name, persist_directory=str(persist_dir), embedding_function=embeddings)

    if settings.vector_reindex_each_run:
        try:
            store.delete(where={"tenant_id": sec.tenant_id, "task_id": sec.task_id})
        except Exception:
            pass

    docs = []
    ids = []
    for chunk in children:
        meta = dict(chunk.metadata)
        meta["tenant_id"] = sec.tenant_id
        meta["task_id"] = sec.task_id
        docs.append(Document(page_content=chunk.text, metadata=meta))
        ids.append(f"{sec.tenant_id}-{sec.task_id}-{chunk.child_id}")
    if docs:
        store.add_documents(docs, ids=ids)
    return store


@dataclass
class RetrievalOutput:
    candidates: List[RetrievalCandidate]
    parent_context: str
    metrics: Dict[str, Any]
    fallback_path: str


def retrieve_hybrid_for_risk(
    *,
    sec: SecurityContext,
    settings: Settings,
    parent_chunks: Sequence[ParentChunk],
    child_chunks: Sequence[ChildChunk],
    expanded_queries: Sequence[str],
    risk_type: str,
    vector_store: Chroma | None = None,
) -> RetrievalOutput:
    t0 = perf_counter()
    fallback_path = "hybrid"
    queries = [q for q in expanded_queries if q.strip()][: max(1, settings.max_expanded_queries_per_risk)]
    bm25_hits = 0
    vector_hits = 0

    # BM25-like retrieval on child chunks
    bm25_candidates: List[RetrievalCandidate] = []
    if settings.legal_bm25_enabled:
        scored: Dict[str, Tuple[float, RetrievalCandidate]] = {}
        for query in queries:
            for ch in child_chunks:
                score = _score_bm25_like(query, ch.text)
                if score <= 0:
                    continue
                cid = f"{sec.document_id}:{ch.child_id}"
                cand = RetrievalCandidate(
                    candidate_id=cid,
                    parent_id=ch.parent_id,
                    child_id=ch.child_id,
                    page_no=ch.page_no,
                    clause_id=str(ch.metadata.get("clause_id") or ""),
                    clause_title=str(ch.metadata.get("clause_title") or ""),
                    snippet=ch.text[:700],
                    query_source=query,
                    matched_terms=_extract_matched_terms(query, ch.text),
                    metadata=dict(ch.metadata),
                )
                old = scored.get(cid)
                if old is None or score > old[0]:
                    scored[cid] = (score, cand)
        bm25_sorted = sorted(scored.values(), key=lambda x: x[0], reverse=True)
        for _, cand in bm25_sorted[: settings.bm25_top_k]:
            bm25_candidates.append(cand)
        bm25_hits = len(bm25_candidates)

    # vector retrieval on child chunks
    vector_candidates: List[RetrievalCandidate] = []
    if settings.rag_mode in {"vector", "hybrid"} and vector_store is not None:
        try:
            seen = set()
            for query in queries:
                results = vector_store.similarity_search_with_score(
                    query,
                    k=max(1, settings.vector_top_k_v3),
                    filter={"tenant_id": sec.tenant_id, "task_id": sec.task_id},
                )
                for rank, (doc, distance) in enumerate(results, start=1):
                    child_id = str(doc.metadata.get("child_id") or "")
                    if not child_id:
                        continue
                    cid = f"{sec.document_id}:{child_id}"
                    if cid in seen:
                        continue
                    seen.add(cid)
                    cand = RetrievalCandidate(
                        candidate_id=cid,
                        parent_id=str(doc.metadata.get("parent_id") or ""),
                        child_id=child_id,
                        page_no=int(doc.metadata.get("page_no") or 1),
                        clause_id=str(doc.metadata.get("clause_id") or ""),
                        clause_title=str(doc.metadata.get("clause_title") or ""),
                        snippet=str(doc.page_content or "")[:700],
                        query_source=query,
                        matched_terms=_extract_matched_terms(query, str(doc.page_content or "")),
                        metadata=dict(doc.metadata),
                    )
                    cand.vector_rank = rank
                    # Keep pure RRF fusion semantics:
                    # base score is always 0, only rank-based RRF terms contribute.
                    cand.rrf_score = 0.0
                    cand.metadata["vector_distance"] = float(distance)
                    vector_candidates.append(cand)
            vector_candidates = vector_candidates[: max(1, settings.vector_top_k_v3)]
            vector_hits = len(vector_candidates)
        except Exception:
            fallback_path = "bm25_only" if bm25_candidates else "keyword_regex"

    # fallback logic
    if not bm25_candidates and not vector_candidates:
        fallback_path = "keyword_regex"
        # cheap fallback: use first children mentioning risk_type
        for ch in child_chunks:
            if risk_type and risk_type in ch.text:
                cid = f"{sec.document_id}:{ch.child_id}"
                vector_candidates.append(
                    RetrievalCandidate(
                        candidate_id=cid,
                        parent_id=ch.parent_id,
                        child_id=ch.child_id,
                        page_no=ch.page_no,
                        clause_id=str(ch.metadata.get("clause_id") or ""),
                        clause_title=str(ch.metadata.get("clause_title") or ""),
                        snippet=ch.text[:700],
                        query_source="keyword_regex",
                        matched_terms=[risk_type],
                        metadata=dict(ch.metadata),
                    )
                )
            if len(vector_candidates) >= 5:
                break

    if settings.rrf_enabled:
        fused = _rrf_fuse(
            bm25_candidates[: settings.max_risk_candidates_before_rrf],
            vector_candidates[: settings.max_risk_candidates_before_rrf],
            k=max(1, settings.rrf_k),
            top_k=max(1, settings.rrf_top_k),
        )
    else:
        fused = (bm25_candidates + vector_candidates)[: max(1, settings.rrf_top_k)]

    # parent context expansion by candidate parent ids
    parent_map = {p.parent_id: p for p in parent_chunks}
    context_blocks: List[str] = []
    used_parents = set()
    char_budget = max(1000, settings.max_parent_context_tokens * 2)
    current = 0
    for cand in fused[: max(1, settings.max_rrf_candidates_per_risk)]:
        pid = cand.parent_id
        if pid in used_parents:
            continue
        used_parents.add(pid)
        parent = parent_map.get(pid)
        if not parent:
            continue
        block = f"[Parent {pid}][Page {parent.page_start}-{parent.page_end}]\n{parent.text[:1200]}"
        extra = len(block) + (2 if context_blocks else 0)
        if current + extra > char_budget:
            break
        context_blocks.append(block)
        current += extra

    latency_ms = int((perf_counter() - t0) * 1000)
    metrics = {
        "bm25_hit_count": bm25_hits,
        "vector_hit_count": vector_hits,
        "rrf_candidate_count": len(fused),
        "rrf_overlap_count": len({x.candidate_id for x in bm25_candidates} & {x.candidate_id for x in vector_candidates}),
        "retrieval_latency_ms": latency_ms,
        "fallback_path": fallback_path,
    }
    return RetrievalOutput(
        candidates=fused,
        parent_context="\n\n".join(context_blocks).strip(),
        metrics=metrics,
        fallback_path=fallback_path,
    )


def build_rag_cache_key(
    *,
    sec: SecurityContext,
    query: str,
    risk_type: str,
    settings: Settings,
) -> str:
    payload = "|".join(
        [
            sec.tenant_id,
            sec.org_id,
            sec.user_id,
            sec.permission_scope,
            sec.task_id,
            sec.document_id,
            hashlib.sha256(query.encode("utf-8")).hexdigest()[:16],
            risk_type,
            settings.parser_version,
            settings.chunk_version,
            settings.bm25_index_version,
            settings.vector_index_version,
            settings.rrf_config_version,
            settings.rerank_model_version,
            settings.risk_query_template_version,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
