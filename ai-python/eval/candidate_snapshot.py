"""Frozen retrieval candidate snapshot export and replay helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from eval.dataset_loader import load_dataset, select_evaluation_cases


def _sha_payload(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("snapshot_sha256", None)
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def export_snapshot(report_path: Path, dataset_path: Path, output_path: Path) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    cases_by_id = {c.case_id: c for c in select_evaluation_cases(load_dataset(dataset_path))}
    records = []
    for result in report.get("cases", []):
        case = cases_by_id[result["case_id"]]
        diagnostics = result.get("timing", {}).get("retrieval_stage_diagnostics", {})
        lexical = {x["candidate_id"].split(":")[-1]: x for x in diagnostics.get("lexical_candidates", [])}
        vector = {x["candidate_id"].split(":")[-1]: x for x in diagnostics.get("vector_candidates", [])}
        rrf = {x["candidate_id"].split(":")[-1]: x for x in diagnostics.get("rrf_scores", [])}
        candidates = []
        for item in result.get("top_results", []):
            cid = item["chunk_id"]
            candidates.append({
                "candidate_id": cid,
                "rank": item["rank"],
                "text": item.get("text_preview", ""),
                "parent_id": item.get("parent_id"),
                "page": item.get("page"),
                "page_nos": item.get("page_nos", []),
                "score": item.get("score"),
                "lexical_score": lexical.get(cid, {}).get("score"),
                "vector_rank": vector.get(cid, {}).get("rank"),
                "vector_distance": vector.get(cid, {}).get("distance"),
                "rrf_score": rrf.get(cid, {}).get("score", item.get("score", 0.0)),
                "metadata": {"matched_gold": item.get("matched_gold", [])},
            })
        records.append({
            "case_id": case.case_id,
            "query": case.query,
            "document_id": case.document_id,
            "candidates": candidates,
            "expected_evidence": [{"page": e.page, "text": e.text} for e in case.expected_evidence],
        })
    metadata = {
        "schema_version": "candidate_snapshot_v1",
        "source_report": str(report_path).replace("\\", "/"),
        "source_commit": report.get("metadata", {}).get("git_commit"),
        "dataset": str(dataset_path).replace("\\", "/"),
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "settings_fingerprint": sorted({c.get("timing", {}).get("settings_fingerprint") for c in report.get("cases", [])}),
        "retrieval_profile": "hybrid_rrf",
        "case_count": len(records),
    }
    payload = {"metadata": metadata, "cases": records}
    payload["snapshot_sha256"] = _sha_payload(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def load_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("snapshot_sha256") != _sha_payload(payload):
        raise ValueError("snapshot_sha256 mismatch")
    if payload.get("metadata", {}).get("schema_version") != "candidate_snapshot_v1":
        raise ValueError("unsupported snapshot schema")
    if len(payload.get("cases", [])) != payload.get("metadata", {}).get("case_count"):
        raise ValueError("snapshot case count mismatch")
    return payload
