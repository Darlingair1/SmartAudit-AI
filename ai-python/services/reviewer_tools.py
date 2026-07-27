import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import Settings, get_settings

logger = logging.getLogger("smartaudit.ai.reviewer_tools")

_EMBEDDING_CACHE: Dict[Tuple[str, str, bool, int], HuggingFaceEmbeddings] = {}

_LEGAL_BASIS_KB: Dict[str, List[str]] = {
    "付款": [
        "《民法典》第五百零九条（全面履行原则）",
        "《民法典》第五百一十条（约定不明时的补充规则）",
    ],
    "违约": [
        "《民法典》第五百七十七条（违约责任）",
        "《民法典》第五百八十五条（违约金）",
    ],
    "解除": [
        "《民法典》第五百六十三条（法定解除）",
        "《民法典》第五百六十五条（解除权行使）",
    ],
    "争议": [
        "《民事诉讼法》第二十四条（合同纠纷管辖）",
        "《仲裁法》第十六条（仲裁协议）",
    ],
    "保密": [
        "《反不正当竞争法》第九条（商业秘密保护）",
        "《民法典》第一百二十二条（民事权益保护）",
    ],
    "知识产权": [
        "《民法典》第一百二十三条（知识产权客体）",
        "《著作权法》相关条款（软件著作权归属）",
    ],
}


def _ok(tool: str, data: Dict[str, Any], message: str = "ok") -> Dict[str, Any]:
    return {"ok": True, "tool": tool, "message": message, "data": data}


def _error(tool: str, message: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"ok": False, "tool": tool, "message": message, "data": data or {}}


def _normalize_task_id(task_id: str) -> str:
    return str(task_id or "").strip()


def _normalize_query(query: str, max_len: int = 120) -> str:
    value = str(query or "").strip()
    return value[:max_len]


def _normalize_top_k(top_k: int | None, default: int = 3, max_limit: int = 20) -> int:
    if top_k is None:
        return default
    try:
        value = int(top_k)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, max_limit))


def _normalize_page_no(page_no: int | str | None) -> int | None:
    try:
        value = int(page_no)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _clip_text(text: str, max_chars: int) -> str:
    value = str(text or "").strip()
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return value[:max_chars]


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _resolve_local_path(path_value: str) -> Path:
    candidate = Path(str(path_value or "").strip())
    if candidate.is_absolute():
        return candidate
    return (Path(__file__).resolve().parents[2] / candidate).resolve()


def _safe_collection_name(prefix: str, task_id: str) -> str:
    raw = f"{prefix}-{task_id}".lower()
    value = re.sub(r"[^a-z0-9_-]", "-", raw)
    value = re.sub(r"-{2,}", "-", value).strip("-_")
    if len(value) < 3:
        value = "smartaudit-task"
    return value[:63]


def _get_hf_embeddings(settings: Settings) -> HuggingFaceEmbeddings:
    model_dir = _resolve_local_path(settings.embedding_model_path)
    if not model_dir.exists():
        raise FileNotFoundError(f"Embedding model path not found: {model_dir}")

    key = (
        str(model_dir),
        settings.embedding_device,
        settings.embedding_normalize,
        max(1, settings.embedding_batch_size),
    )
    cached = _EMBEDDING_CACHE.get(key)
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
    _EMBEDDING_CACHE[key] = embeddings
    return embeddings


def _build_page_documents(page_texts: Sequence[str], task_id: str) -> List[Document]:
    docs: List[Document] = []
    for page_no, text in enumerate(page_texts, start=1):
        content = str(text or "").strip()
        if not content:
            continue
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "task_id": task_id,
                    "page_no": page_no,
                },
            )
        )
    return docs


def _split_documents(documents: Sequence[Document], settings: Settings) -> List[Document]:
    if not documents:
        return []
    chunk_size = max(200, settings.vector_chunk_size)
    chunk_overlap = max(0, min(settings.vector_chunk_overlap, chunk_size - 1))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )
    return splitter.split_documents(list(documents))


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

    tokens = [t for t in re.split(r"[\s,，。；;:：()（）【】\[\]/\\]+", query) if t]
    score = 0
    for token in tokens:
        compact_token = _compact_text(token)
        if len(compact_token) >= 2 and compact_token in compact_page:
            score += 2
    return score


def _extract_snippet(page_text: str, query: str, max_len: int = 700) -> str:
    if not page_text:
        return ""
    if not query:
        return _clip_text(page_text, max_len)

    idx = page_text.find(query)
    if idx < 0:
        tokens = [t for t in re.split(r"[\s,，。；;:：()（）【】\[\]/\\]+", query) if t]
        for token in tokens:
            idx = page_text.find(token)
            if idx >= 0:
                break

    if idx < 0:
        return _clip_text(page_text, max_len)

    left = max(0, idx - 200)
    right = min(len(page_text), idx + max_len)
    return _clip_text(page_text[left:right], max_len)


def vector_search(
    task_id: str,
    query: str,
    *,
    top_k: int | None = None,
    page_texts: Sequence[str] | None = None,
    index: bool = False,
    reindex: bool = False,
    settings: Settings | None = None,
) -> Dict[str, Any]:
    tool = "vector_search"
    settings = settings or get_settings()
    normalized_task_id = _normalize_task_id(task_id)
    normalized_query = _normalize_query(query)
    if not normalized_task_id:
        return _error(tool, "task_id cannot be blank")
    if not normalized_query:
        return _error(tool, "query cannot be blank")

    if index and not page_texts:
        return _error(tool, "index=True requires page_texts")

    final_top_k = _normalize_top_k(top_k, default=max(1, settings.vector_top_k))
    try:
        persist_dir = _resolve_local_path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        embeddings = _get_hf_embeddings(settings)
        collection_name = _safe_collection_name(settings.chroma_collection_prefix, normalized_task_id)
        vector_store = Chroma(
            collection_name=collection_name,
            persist_directory=str(persist_dir),
            embedding_function=embeddings,
        )

        if index and page_texts:
            page_docs = _build_page_documents(page_texts, normalized_task_id)
            chunk_docs = _split_documents(page_docs, settings)
            if chunk_docs:
                if reindex:
                    try:
                        vector_store.delete(where={"task_id": normalized_task_id})
                    except Exception as ex:  # noqa: PERF203
                        logger.warning(
                            "vector_search reindex delete failed, taskId=%s, err=%s",
                            normalized_task_id,
                            ex,
                        )
                for idx, doc in enumerate(chunk_docs, start=1):
                    doc.metadata["task_id"] = normalized_task_id
                    doc.metadata["chunk_index"] = idx
                ids = [f"{normalized_task_id}-chunk-{idx}" for idx in range(1, len(chunk_docs) + 1)]
                vector_store.add_documents(chunk_docs, ids=ids)

        results = vector_store.similarity_search_with_score(
            normalized_query,
            k=final_top_k,
            filter={"task_id": normalized_task_id},
        )
    except Exception as ex:
        logger.warning("vector_search failed, taskId=%s, err=%s", normalized_task_id, ex)
        return _error(tool, f"vector search failed: {ex}")

    hits: List[Dict[str, Any]] = []
    for doc, distance in results:
        page_no = _normalize_page_no(doc.metadata.get("page_no")) or 1
        snippet = _clip_text(doc.page_content, 700)
        hits.append(
            {
                "pageNo": page_no,
                "distance": round(float(distance), 6),
                "snippet": snippet,
                "chunkIndex": _normalize_page_no(doc.metadata.get("chunk_index")),
            }
        )

    return _ok(
        tool,
        {
            "taskId": normalized_task_id,
            "query": normalized_query,
            "topK": final_top_k,
            "hitCount": len(hits),
            "hits": hits,
        },
    )


def keyword_search(
    query: str,
    page_texts: Sequence[str],
    *,
    top_k: int = 3,
    max_snippet_chars: int = 700,
) -> Dict[str, Any]:
    tool = "keyword_search"
    normalized_query = _normalize_query(query)
    if not normalized_query:
        return _error(tool, "query cannot be blank")
    if not page_texts:
        return _error(tool, "page_texts cannot be empty")

    final_top_k = _normalize_top_k(top_k, default=3)
    scored: List[Tuple[int, int]] = []
    for idx, text in enumerate(page_texts, start=1):
        score = _score_page_for_query(str(text or ""), normalized_query)
        if score > 0:
            scored.append((score, idx))

    scored.sort(reverse=True)
    hits: List[Dict[str, Any]] = []
    for score, page_no in scored[:final_top_k]:
        snippet = _extract_snippet(str(page_texts[page_no - 1] or ""), normalized_query, max_len=max_snippet_chars)
        hits.append(
            {
                "pageNo": page_no,
                "score": score,
                "snippet": snippet,
            }
        )
    return _ok(
        tool,
        {
            "query": normalized_query,
            "topK": final_top_k,
            "hitCount": len(hits),
            "hits": hits,
        },
    )


def get_page_text(
    page_texts: Sequence[str],
    page_no: int,
    *,
    max_chars: int = 1200,
) -> Dict[str, Any]:
    tool = "get_page_text"
    if not page_texts:
        return _error(tool, "page_texts cannot be empty")
    normalized_page_no = _normalize_page_no(page_no)
    if normalized_page_no is None:
        return _error(tool, "invalid page_no")
    if normalized_page_no > len(page_texts):
        return _error(tool, f"page_no out of range: {normalized_page_no}/{len(page_texts)}")

    text = _clip_text(str(page_texts[normalized_page_no - 1] or ""), max_chars)
    return _ok(
        tool,
        {
            "pageNo": normalized_page_no,
            "chars": len(text),
            "text": text,
        },
    )


def find_excerpt_page(
    page_texts: Sequence[str],
    excerpt: str,
    *,
    max_scan_pages: int = 0,
) -> Dict[str, Any]:
    tool = "find_excerpt_page"
    normalized_excerpt = _normalize_query(excerpt, max_len=2000)
    if not normalized_excerpt:
        return _error(tool, "excerpt cannot be blank")
    if not page_texts:
        return _error(tool, "page_texts cannot be empty")

    scan_limit = len(page_texts) if max_scan_pages <= 0 else min(len(page_texts), max_scan_pages)
    compact_excerpt = _compact_text(normalized_excerpt)
    for idx, raw in enumerate(page_texts[:scan_limit], start=1):
        text = str(raw or "")
        start_offset = text.find(normalized_excerpt)
        if start_offset >= 0:
            end_offset = start_offset + len(normalized_excerpt)
            return _ok(
                tool,
                {
                    "matched": True,
                    "pageNo": idx,
                    "startOffset": start_offset,
                    "endOffset": end_offset,
                    "mode": "exact",
                },
            )
        if compact_excerpt and compact_excerpt in _compact_text(text):
            return _ok(
                tool,
                {
                    "matched": True,
                    "pageNo": idx,
                    "startOffset": None,
                    "endOffset": None,
                    "mode": "compact",
                },
            )
    return _ok(
        tool,
        {
            "matched": False,
            "pageNo": None,
            "startOffset": None,
            "endOffset": None,
            "mode": "none",
        },
    )


def law_lookup(risk_type: str, risk_desc: str | None = None) -> Dict[str, Any]:
    tool = "law_lookup"
    normalized_risk_type = _normalize_query(risk_type, max_len=120)
    normalized_risk_desc = _normalize_query(risk_desc or "", max_len=300)
    if not normalized_risk_type and not normalized_risk_desc:
        return _error(tool, "risk_type or risk_desc is required")

    probe = f"{normalized_risk_type} {normalized_risk_desc}".strip()
    matched_basis: List[str] = []
    for key, basis in _LEGAL_BASIS_KB.items():
        if key in probe:
            matched_basis.extend(basis)

    if not matched_basis:
        matched_basis = [
            "《民法典》第四百六十五条（合同效力与约束力）",
            "《民法典》第五百零九条（全面履行原则）",
        ]
    dedup_basis = list(dict.fromkeys(matched_basis))
    return _ok(
        tool,
        {
            "riskType": normalized_risk_type or None,
            "riskDesc": normalized_risk_desc or None,
            "legalBasis": dedup_basis,
        },
    )


async def run_tool_with_timeout(
    tool_name: str,
    tool_fn: Callable[..., Dict[str, Any]],
    timeout_ms: int,
    **kwargs: Any,
) -> Dict[str, Any]:
    timeout_seconds = max(0.1, timeout_ms / 1000.0)
    try:
        return await asyncio.wait_for(asyncio.to_thread(tool_fn, **kwargs), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return _error(tool_name, f"tool timeout after {timeout_ms}ms")
    except Exception as ex:  # noqa: PERF203
        logger.exception("tool execution failed, tool=%s", tool_name)
        return _error(tool_name, f"tool execution failed: {ex}")


def get_reviewer_tool_registry() -> Dict[str, Callable[..., Dict[str, Any]]]:
    return {
        "vector_search": vector_search,
        "keyword_search": keyword_search,
        "get_page_text": get_page_text,
        "find_excerpt_page": find_excerpt_page,
        "law_lookup": law_lookup,
    }


def get_reviewer_tool_schemas() -> List[Dict[str, Any]]:
    # OpenAI-compatible function/tool schemas, used by native tool-calling path.
    return [
        {
            "type": "function",
            "function": {
                "name": "vector_search",
                "description": "按语义向量检索与当前风险最相关的合同片段。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "检索关键词或短句"},
                        "top_k": {"type": "integer", "description": "返回条数上限（建议1-3）"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "keyword_search",
                "description": "按关键词在合同页中匹配并返回候选证据片段。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "关键词"},
                        "top_k": {"type": "integer", "description": "返回条数上限"},
                        "max_snippet_chars": {"type": "integer", "description": "单条片段最大字符数"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_page_text",
                "description": "按页号读取该页文本（可截断）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_no": {"type": "integer", "description": "页码，从1开始"},
                        "max_chars": {"type": "integer", "description": "最大返回字符数"},
                    },
                    "required": ["page_no"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_excerpt_page",
                "description": "根据摘录内容定位其所在页码。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "excerpt": {"type": "string", "description": "原文摘录"},
                        "max_scan_pages": {"type": "integer", "description": "最大扫描页数，0代表全部"},
                    },
                    "required": ["excerpt"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "law_lookup",
                "description": "根据风险类型返回中国法条建议。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "risk_type": {"type": "string", "description": "风险类型"},
                        "risk_desc": {"type": "string", "description": "风险描述"},
                    },
                    "required": ["risk_type"],
                },
            },
        },
    ]


__all__ = [
    "vector_search",
    "keyword_search",
    "get_page_text",
    "find_excerpt_page",
    "law_lookup",
    "run_tool_with_timeout",
    "get_reviewer_tool_registry",
    "get_reviewer_tool_schemas",
]
