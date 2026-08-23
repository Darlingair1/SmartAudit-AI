from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Sequence

import torch

from core.config import get_settings
from services.reranker import _RERANKER_CACHE, _get_cross_encoder


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return round(float(ordered[index]), 3)


def distribution(values: Iterable[float]) -> dict[str, float | None]:
    samples = [float(value) for value in values]
    if not samples:
        return {"mean": None, "p50": None, "p95": None, "max": None}
    return {
        "mean": round(statistics.fmean(samples), 3),
        "p50": _percentile(samples, 0.5),
        "p95": _percentile(samples, 0.95),
        "max": round(max(samples), 3),
    }


def _pairs(case: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (str(case.get("query") or ""), str(result.get("text_preview") or ""))
        for result in case.get("top_results", [])
    ]


def _batches(values: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def profile(
    *,
    source_report: Path,
    max_length: int,
    batch_size: int,
    micro_batch_size: int,
    cpu_threads: int,
    warmup_pairs: int,
    case_limit: int | None,
) -> dict[str, Any]:
    source = json.loads(source_report.read_text(encoding="utf-8"))
    cases = list(source.get("cases", []))
    if case_limit is not None:
        cases = cases[:case_limit]

    torch.set_num_threads(max(1, cpu_threads))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    settings = get_settings()
    object.__setattr__(settings, "rerank_max_length", max_length)
    _RERANKER_CACHE.clear()
    init_started = perf_counter()
    model = _get_cross_encoder(settings)
    model_init_ms = (perf_counter() - init_started) * 1000
    cache_started = perf_counter()
    cached_model = _get_cross_encoder(settings)
    cache_lookup_ms = (perf_counter() - cache_started) * 1000
    if cached_model is not model:
        raise RuntimeError("CrossEncoder cache returned a different model instance")

    all_pairs = [pair for case in cases for pair in _pairs(case)]
    warmup_ms = 0.0
    if warmup_pairs and all_pairs:
        started = perf_counter()
        model.predict(
            all_pairs[:warmup_pairs],
            batch_size=min(batch_size, warmup_pairs),
            show_progress_bar=False,
        )
        warmup_ms = (perf_counter() - started) * 1000

    case_results: list[dict[str, Any]] = []
    for case in cases:
        pairs = _pairs(case)
        started = perf_counter()
        tokenization_ms = 0.0
        inference_ms = 0.0
        token_lengths: list[int] = []
        raw_scores: list[float] = []
        for logical_batch in _batches(pairs, max(1, batch_size)):
            for micro_batch in _batches(logical_batch, max(1, micro_batch_size)):
                token_started = perf_counter()
                features = model.tokenizer(
                    list(micro_batch),
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                tokenization_ms += (perf_counter() - token_started) * 1000
                token_lengths.extend(
                    int(value)
                    for value in features["attention_mask"].sum(dim=1).tolist()
                )
                features.to(model.model.device)
                inference_started = perf_counter()
                with torch.inference_mode():
                    predictions = model.model(**features, return_dict=True)
                    logits = model.activation_fn(predictions.logits)
                inference_ms += (perf_counter() - inference_started) * 1000
                raw_scores.extend(float(value) for value in logits.flatten().tolist())
        rerank_total_ms = (perf_counter() - started) * 1000
        source_timing = case.get("timing", {})
        case_results.append(
            {
                "case_id": case.get("case_id"),
                "candidate_count": len(pairs),
                "batch_size": batch_size,
                "micro_batch_size": micro_batch_size,
                "input_char_length": {
                    "mean": round(statistics.fmean(len(a) + len(b) for a, b in pairs), 3)
                    if pairs
                    else 0,
                    "max": max((len(a) + len(b) for a, b in pairs), default=0),
                },
                "input_token_length": {
                    "mean": round(statistics.fmean(token_lengths), 3)
                    if token_lengths
                    else 0,
                    "max": max(token_lengths, default=0),
                },
                "tokenization_ms": round(tokenization_ms, 3),
                "batched_inference_ms": round(inference_ms, 3),
                "rerank_total_ms": round(rerank_total_ms, 3),
                "source_end_to_end_retrieval_ms": case.get("latency_ms"),
                "source_reranker_ms": source_timing.get("reranker_ms"),
                "source_reranker_status": case.get("reranker_status"),
                "score_count": len(raw_scores),
            }
        )

    timeout_ms = int(getattr(settings, "rerank_timeout_ms", 3000))
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
            "source_report": source_report.as_posix(),
            "python_version": sys.version.split()[0],
            "torch_version": torch.__version__,
            "torch_num_threads": torch.get_num_threads(),
            "torch_num_interop_threads": torch.get_num_interop_threads(),
            "model": str(getattr(settings, "rerank_model_version", "")),
            "model_init_ms": round(model_init_ms, 3),
            "model_cache_lookup_ms": round(cache_lookup_ms, 3),
            "model_cache_reused_instance": True,
            "warmup_pairs": warmup_pairs,
            "warmup_ms": round(warmup_ms, 3),
            "max_length": max_length,
            "batch_size": batch_size,
            "micro_batch_size": micro_batch_size,
            "production_timeout_ms": timeout_ms,
            "case_count": len(case_results),
            "benchmark_process_model": "one process for all cases in a profile",
            "production_predict_uses_batch": True,
        },
        "summary": {
            "candidate_count": distribution(
                item["candidate_count"] for item in case_results
            ),
            "input_char_length": distribution(
                item["input_char_length"]["mean"] for item in case_results
            ),
            "input_token_length": distribution(
                item["input_token_length"]["mean"] for item in case_results
            ),
            "tokenization_ms": distribution(
                item["tokenization_ms"] for item in case_results
            ),
            "batched_inference_ms": distribution(
                item["batched_inference_ms"] for item in case_results
            ),
            "rerank_total_ms": distribution(
                item["rerank_total_ms"] for item in case_results
            ),
            "source_end_to_end_retrieval_ms": distribution(
                item["source_end_to_end_retrieval_ms"]
                for item in case_results
                if item["source_end_to_end_retrieval_ms"] is not None
            ),
            "would_exceed_production_timeout_count": sum(
                item["rerank_total_ms"] > timeout_ms for item in case_results
            ),
            "source_fallback_reasons": {
                status: sum(
                    item["source_reranker_status"] == status for item in case_results
                )
                for status in sorted(
                    {str(item["source_reranker_status"]) for item in case_results}
                )
            },
        },
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile CrossEncoder stages")
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--micro-batch-size", type=int, default=8)
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--warmup-pairs", type=int, default=0)
    parser.add_argument("--case-limit", type=int)
    args = parser.parse_args()
    report = profile(
        source_report=args.source_report,
        max_length=max(64, args.max_length),
        batch_size=max(1, args.batch_size),
        micro_batch_size=max(1, args.micro_batch_size),
        cpu_threads=max(1, args.cpu_threads),
        warmup_pairs=max(0, args.warmup_pairs),
        case_limit=args.case_limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
