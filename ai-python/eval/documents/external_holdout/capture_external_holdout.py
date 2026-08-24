"""Capture External Holdout cases through production stages, stopping before Judge."""

from __future__ import annotations

import asyncio
import hashlib
import json
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import get_settings
from schemas.models import AuditJobRequest
from services.audit_agent import _load_pdf_pages
from services.retrieval_hybrid import _index_vector_children, build_parent_child_chunks, retrieve_hybrid_for_risk
from services.reranker import rerank_candidates
from services.risk_query_builder import build_risk_queries
from services.security_context import build_security_context
from services.v3_pipeline import _run_agent1_map_stage


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "ai-python/eval/documents/external_holdout"
SOURCE_SET = BASE / "pipeline_source_set.json"
CAPTURE_ROOT = ROOT / "ai-python/eval/experiments" / f"external_holdout_{datetime.now().strftime('%Y%m%d')}" / "pipeline_capture"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unavailable"


def _git_status() -> list[str]:
    try:
        output = subprocess.check_output(["git", "-C", str(ROOT), "status", "--short"], text=True)
        return output.splitlines()
    except Exception:
        return []


def _candidate_to_dict(candidate: Any, rank: int) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "rank": rank,
        "parent_id": candidate.parent_id,
        "child_id": candidate.child_id,
        "page_no": candidate.page_no,
        "page_nos": list(candidate.page_nos),
        "page_start": candidate.page_start,
        "page_end": candidate.page_end,
        "clause_id": candidate.clause_id,
        "clause_title": candidate.clause_title,
        "text": candidate.snippet,
        "bm25_rank": candidate.bm25_rank,
        "vector_rank": candidate.vector_rank,
        "rrf_score": candidate.rrf_score,
        "query_source": candidate.query_source,
        "matched_terms": list(candidate.matched_terms),
        "metadata": dict(candidate.metadata),
    }


def _config_snapshot(settings: Any) -> dict[str, Any]:
    keys = (
        "llm_provider", "default_model", "rag_mode", "rag_v3_enabled", "parent_child_enabled",
        "legal_bm25_enabled", "rrf_enabled", "rerank_enabled", "map_chunk_pages",
        "map_chunk_overlap_pages", "map_max_concurrency", "parser_version", "chunk_version",
        "bm25_top_k", "vector_top_k_v3", "rrf_top_k", "rrf_k", "rerank_model_version",
        "rerank_top_n", "rerank_batch_size", "rerank_max_length", "rerank_timeout_ms",
    )
    return {key: getattr(settings, key) for key in keys}


async def _capture_one(source: dict[str, Any], settings: Any, run_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = ROOT / source["relative_path"]
    task_id = f"external-{run_id}-{source['document_id']}"
    request = AuditJobRequest(
        taskId=task_id,
        taskNo=task_id,
        filePath=str(path),
        fileName=source["filename"],
        callbackUrl="http://127.0.0.1/disabled-external-holdout-callback",
        modelName=settings.default_model,
        tenantId="external-holdout",
        orgId="external-holdout",
        userId="capture",
        permissionScope="audit:read",
        documentId=source["document_id"],
        contractId=source["document_id"],
    )
    pages = _load_pdf_pages(str(path))
    sec = build_security_context(request, settings)
    draft_items, chunk_ranges, _, _ = await _run_agent1_map_stage(
        job_request=request,
        page_texts=pages,
        settings=settings,
    )
    parse_quality = {"page_count": len(pages), "non_empty_pages": sum(bool(x.strip()) for x in pages)}
    parents, children = build_parent_child_chunks(
        page_texts=pages,
        sec=sec,
        settings=settings,
        parse_quality=parse_quality,
    )
    vector_store = None
    vector_index_error = None
    if settings.rag_mode in {"vector", "hybrid"}:
        try:
            vector_store = _index_vector_children(children, sec, settings)
        except Exception as exc:
            vector_index_error = f"{type(exc).__name__}: {exc}"

    cases: list[dict[str, Any]] = []
    retrieval_failures: list[dict[str, Any]] = []
    for index, draft in enumerate(draft_items, start=1):
        try:
            query_pack = build_risk_queries(draft, template_version=settings.risk_query_template_version)
            retrieval = retrieve_hybrid_for_risk(
                sec=sec,
                settings=settings,
                parent_chunks=parents,
                child_chunks=children,
                expanded_queries=query_pack["expanded_queries"],
                risk_type=str(draft.get("riskType") or ""),
                vector_store=vector_store,
            )
            candidates = retrieval.candidates[: max(1, settings.max_rrf_candidates_per_risk)]
            reranked, rerank_metrics = rerank_candidates(
                query=query_pack["original_query"] or str(draft.get("riskType") or ""),
                candidates=candidates,
                settings=settings,
            )
            case_id = f"{source['document_id']}_capture_{index:04d}"
            cases.append({
                "case_id": case_id,
                "document_id": source["document_id"],
                "document_filename": source["filename"],
                "document_sha256": source["original_sha256"],
                "claim_id": f"{case_id}_claim",
                "claim": draft,
                "claim_provenance": {
                    "stage": "production_agent1_map",
                    "chunk_ranges": chunk_ranges,
                    "draft_index": index,
                },
                "query": query_pack,
                "retrieval_metrics": retrieval.metrics,
                "rerank_metrics": rerank_metrics,
                "evidence_candidates": [_candidate_to_dict(candidate, rank) for rank, candidate in enumerate(reranked, start=1)],
                "pipeline_run_id": run_id,
                "config_fingerprint": _sha256_json(_config_snapshot(settings)),
            })
        except Exception as exc:
            retrieval_failures.append({"draft_index": index, "reason_code": "RETRIEVAL_OR_RERANK_ERROR", "error_type": type(exc).__name__, "error": str(exc)})

    return cases, {
        "document_id": source["document_id"],
        "filename": source["filename"],
        "page_count": len(pages),
        "chunk_ranges": chunk_ranges,
        "claims_generated": len(draft_items),
        "raw_cases": len(cases),
        "parent_count": len(parents),
        "child_count": len(children),
        "vector_index_error": vector_index_error,
        "retrieval_failures": retrieval_failures,
    }


async def main() -> None:
    source_set = json.loads(SOURCE_SET.read_text(encoding="utf-8"))
    if source_set.get("status") != "READY_FOR_PIPELINE_CAPTURE" or source_set.get("eligible_count") != 3:
        raise RuntimeError("source set is not ready")
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("BLOCKED_PIPELINE_CREDENTIALS_MISSING")
    run_id = f"external_holdout_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    config = _config_snapshot(settings)
    provenance = {
        "pipeline_run_id": run_id,
        "capture_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_sha(),
        "working_tree_status": _git_status(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "model_provider": settings.llm_provider,
        "model_name": settings.default_model,
        "config": config,
        "config_fingerprint": _sha256_json(config),
        "implementation_sha256": {
            str(path.relative_to(ROOT)): _sha256_file(path)
            for path in [
                ROOT / "ai-python/services/document_parser.py",
                ROOT / "ai-python/services/audit_agent.py",
                ROOT / "ai-python/services/v3_pipeline.py",
                ROOT / "ai-python/services/retrieval_hybrid.py",
                ROOT / "ai-python/services/reranker.py",
            ]
        },
        "judge_invocation": {"invoked": False, "prediction_files_created": False},
        "source_set_sha256": _sha256_file(SOURCE_SET),
    }
    all_cases: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for source in source_set["sources"]:
        cases, summary = await _capture_one(source, settings, run_id)
        all_cases.extend(cases)
        summaries.append(summary)
        excluded.extend({"document_id": source["document_id"], **failure} for failure in summary["retrieval_failures"])

    (CAPTURE_ROOT / "pipeline_provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (CAPTURE_ROOT / "cases_raw.jsonl").open("w", encoding="utf-8") as handle:
        for case in all_cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    (CAPTURE_ROOT / "excluded_cases.json").write_text(json.dumps(excluded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "status": "CAPTURE_COMPLETED",
        "pipeline_run_id": run_id,
        "document_count": len(source_set["sources"]),
        "documents": summaries,
        "claims_generated_total": sum(x["claims_generated"] for x in summaries),
        "raw_case_count": len(all_cases),
        "evidence_candidate_count": sum(len(x["evidence_candidates"]) for x in all_cases),
        "multi_evidence_case_count": sum(1 for x in all_cases if len(x["evidence_candidates"]) > 1),
        "multi_evidence_case_definition": "case has more than one retrieved evidence candidate; this is not a human support label",
        "pipeline_failures": sum(len(x["retrieval_failures"]) for x in summaries),
        "excluded_case_count": len(excluded),
        "judge_invocation_count": 0,
    }
    (CAPTURE_ROOT / "capture_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "external_holdout_pipeline_capture_v1",
        "pipeline_run_id": run_id,
        "source_set": str(SOURCE_SET.relative_to(ROOT)).replace("\\", "/"),
        "provenance_file": "pipeline_provenance.json",
        "cases_file": "cases_raw.jsonl",
        "excluded_file": "excluded_cases.json",
        "summary_file": "capture_summary.json",
        "stopped_before_evidence_judge": True,
    }
    (CAPTURE_ROOT / "pipeline_capture_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    annotation_path = CAPTURE_ROOT.parent / "annotation_package"
    annotation_path.mkdir(parents=True, exist_ok=True)
    with (annotation_path / "annotation_review.jsonl").open("w", encoding="utf-8") as handle:
        for case in all_cases:
            handle.write(json.dumps({
                "case_id": case["case_id"],
                "document_id": case["document_id"],
                "document_filename": case["document_filename"],
                "document_sha256": case["document_sha256"],
                "claim_id": case["claim_id"],
                "claim": case["claim"],
                "evidence_candidates": case["evidence_candidates"],
                "gold_label": None,
                "adjudicated_label": None,
                "reviewed": False,
                "reviewer_notes": None,
                "unresolved": False,
                "pipeline_run_id": run_id,
            }, ensure_ascii=False) + "\n")
    (annotation_path / "annotation_guidelines.md").write_text(
        "# External Holdout Annotation Guidelines\n\n"
        "Review only the claim and retrieved evidence candidates. Assign `SUPPORTED`, `PARTIAL`, or `UNSUPPORTED` after human review.\n\n"
        "Do not use any Judge prediction or score. Leave `gold_label` and `adjudicated_label` empty until review.\n",
        encoding="utf-8",
    )
    print(json.dumps({"capture_root": str(CAPTURE_ROOT), "annotation_package": str(annotation_path), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
