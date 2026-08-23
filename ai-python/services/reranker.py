from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Sequence

from sentence_transformers import CrossEncoder

from services.legal_tokenizer import tokenize_legal_text
from services.v3_types import RetrievalCandidate

logger = logging.getLogger("smartaudit.ai.reranker")

_RERANKER_CACHE: Dict[tuple[str, str, int], CrossEncoder] = {}
_RERANK_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rerank-ce")


class CrossEncoderError(RuntimeError):
    """CrossEncoder failed without permitting heuristic fallback."""


def _resolve_model_path(path_value: str) -> str:
    candidate = Path((path_value or "").strip())
    if candidate.is_absolute():
        return str(candidate)
    return str((Path(__file__).resolve().parents[2] / candidate).resolve())


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _lexical_relevance(query: str, text: str) -> float:
    q = set(tokenize_legal_text(query))
    t = set(tokenize_legal_text(text))
    if not q or not t:
        return 0.0
    return len(q & t) / max(1, len(q))


def _heuristic_rerank(
    query: str,
    limited: Sequence[RetrievalCandidate],
) -> tuple[List[RetrievalCandidate], List[float]]:
    scores: List[float] = []
    for c in limited:
        s = _lexical_relevance(query, c.snippet)
        final_s = 0.7 * s + 0.3 * max(0.0, c.rrf_score)
        c.metadata["lexical_score"] = round(s, 6)
        c.metadata["rerank_score"] = round(final_s, 6)
        scores.append(final_s)
    reranked = sorted(limited, key=lambda x: float(x.metadata.get("rerank_score", 0.0)), reverse=True)
    return reranked, scores


def _get_cross_encoder(settings: Any) -> CrossEncoder:
    model_path = _resolve_model_path(str(getattr(settings, "rerank_model_path", "") or ""))
    max_length = max(64, int(getattr(settings, "rerank_max_length", 512)))
    device = str(getattr(settings, "embedding_device", "cpu") or "cpu")
    key = (model_path, device, max_length)
    cached = _RERANKER_CACHE.get(key)
    if cached is not None:
        return cached
    model_dir = Path(model_path)
    if not model_dir.exists():
        raise FileNotFoundError(
            f"Cross-encoder model path not found: {model_path}. "
            f"Please download model to this path first."
        )
    config_path = model_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Cross-encoder model is incomplete at {model_path} (missing config.json). "
            "Please finish model download."
        )
    model = CrossEncoder(model_name_or_path=model_path, device=device, max_length=max_length)
    _RERANKER_CACHE[key] = model
    return model


def _predict_cross_encoder_with_timeout(
    model: CrossEncoder,
    pairs: Sequence[tuple[str, str]],
    batch_size: int,
    timeout_ms: int,
) -> List[float]:
    def _run_predict() -> List[float]:
        out = model.predict(
            list(pairs),
            batch_size=max(1, batch_size),
            show_progress_bar=False,
        )
        return [float(x) for x in out]

    future = _RERANK_EXECUTOR.submit(_run_predict)
    return future.result(timeout=max(0.1, timeout_ms / 1000.0))


def rerank_candidates(
    *,
    query: str,
    candidates: List[RetrievalCandidate],
    settings: Any,
) -> tuple[List[RetrievalCandidate], Dict[str, Any]]:
    t0 = perf_counter()
    model_version = str(getattr(settings, "rerank_model_version", "na"))
    if not candidates:
        return [], {
            "rerank_applied": False,
            "rerank_latency_ms": 0,
            "rerank_model_version": model_version,
            "top1_rerank_score": 0.0,
            "topk_avg_rerank_score": 0.0,
            "rerank_backend": "none",
        }

    if not bool(getattr(settings, "rerank_enabled", True)):
        return candidates, {
            "rerank_applied": False,
            "rerank_latency_ms": int((perf_counter() - t0) * 1000),
            "rerank_model_version": "disabled",
            "top1_rerank_score": candidates[0].rrf_score if candidates else 0.0,
            "topk_avg_rerank_score": 0.0,
            "rerank_backend": "disabled",
        }

    top_n = max(1, int(getattr(settings, "rerank_top_n", 10)))
    limited = candidates[:top_n]
    tail = candidates[top_n:]
    batch_size = max(1, int(getattr(settings, "rerank_batch_size", 8)))
    timeout_ms = max(500, int(getattr(settings, "rerank_timeout_ms", 3000)))
    strict = bool(getattr(settings, "rerank_strict", False))

    try:
        model = _get_cross_encoder(settings)
        pairs = [(query, str(c.snippet or "")) for c in limited]
        raw_scores = _predict_cross_encoder_with_timeout(
            model=model,
            pairs=pairs,
            batch_size=batch_size,
            timeout_ms=timeout_ms,
        )
        ce_scores: List[float] = []
        for c, raw in zip(limited, raw_scores):
            ce = _sigmoid(float(raw))
            final_s = 0.9 * ce + 0.1 * max(0.0, c.rrf_score)
            c.metadata["cross_encoder_raw_score"] = round(float(raw), 6)
            c.metadata["cross_encoder_score"] = round(ce, 6)
            c.metadata["rerank_score"] = round(final_s, 6)
            ce_scores.append(final_s)

        reranked = sorted(limited, key=lambda x: float(x.metadata.get("rerank_score", 0.0)), reverse=True)
        reranked.extend(tail)
        latency = int((perf_counter() - t0) * 1000)
        top1 = float(reranked[0].metadata.get("rerank_score", 0.0)) if reranked else 0.0
        avg = sum(ce_scores) / max(1, len(ce_scores))
        return reranked, {
            "rerank_applied": True,
            "rerank_latency_ms": latency,
            "rerank_model_version": model_version,
            "top1_rerank_score": round(top1, 6),
            "topk_avg_rerank_score": round(avg, 6),
            "rerank_backend": "cross_encoder",
            "candidate_count": len(limited),
            "batch_size": batch_size,
            "max_length": int(getattr(settings, "rerank_max_length", 512)),
        }
    except FileNotFoundError as ex:
        logger.warning("Cross-encoder model missing, fallback to heuristic rerank: %s", ex)
        failure_reason = f"model_missing: {ex}"
    except FutureTimeoutError:
        logger.warning("Cross-encoder rerank timeout, fallback to heuristic rerank")
        failure_reason = f"timeout_after_{timeout_ms}ms"
    except Exception as ex:  # noqa: PERF203
        logger.warning("Cross-encoder rerank failed, fallback to heuristic rerank: %s", ex)
        failure_reason = f"error: {type(ex).__name__}: {ex}"

    if strict:
        return candidates, {
            "rerank_applied": False,
            "rerank_latency_ms": int((perf_counter() - t0) * 1000),
            "rerank_model_version": model_version,
            "top1_rerank_score": 0.0,
            "topk_avg_rerank_score": 0.0,
            "rerank_backend": "cross_encoder_error",
            "rerank_failure_reason": failure_reason,
            "candidate_count": len(limited),
            "batch_size": batch_size,
            "max_length": int(getattr(settings, "rerank_max_length", 512)),
        }

    fallback_sorted, scores = _heuristic_rerank(query, limited)
    fallback_sorted.extend(tail)
    latency = int((perf_counter() - t0) * 1000)
    top1 = float(fallback_sorted[0].metadata.get("rerank_score", 0.0)) if fallback_sorted else 0.0
    avg = sum(scores) / max(1, len(scores))
    return fallback_sorted, {
        "rerank_applied": True,
        "rerank_latency_ms": latency,
        "rerank_model_version": "heuristic-fallback",
        "top1_rerank_score": round(top1, 6),
        "topk_avg_rerank_score": round(avg, 6),
        "rerank_backend": "heuristic_fallback",
        "rerank_failure_reason": failure_reason,
        "candidate_count": len(limited),
        "batch_size": batch_size,
        "max_length": int(getattr(settings, "rerank_max_length", 512)),
    }
