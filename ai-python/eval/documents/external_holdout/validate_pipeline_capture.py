from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


FORBIDDEN_KEYS = {
    "predicted_label",
    "v0_prediction",
    "v1_prediction",
    "v2_prediction",
    "v2_1_prediction",
    "judge_reason",
    "judge_confidence",
}


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(capture_dir: Path) -> dict:
    errors: list[str] = []
    manifest = json.loads((capture_dir / "pipeline_capture_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((capture_dir / "capture_summary.json").read_text(encoding="utf-8"))
    provenance = json.loads((capture_dir / "pipeline_provenance.json").read_text(encoding="utf-8"))
    raw = _rows(capture_dir / "cases_raw.jsonl")
    annotation_path = capture_dir.parent / "annotation_package" / "annotation_review.jsonl"
    annotation = _rows(annotation_path)

    if not manifest.get("stopped_before_evidence_judge"):
        errors.append("manifest does not confirm pre-Judge stop")
    if summary.get("judge_invocation_count") != 0:
        errors.append("summary reports Judge invocation")
    judge_provenance = provenance.get("judge_invocation") or {}
    if judge_provenance.get("invoked") or judge_provenance.get("prediction_files_created"):
        errors.append("provenance reports Judge activity")
    if len(raw) != summary.get("raw_case_count"):
        errors.append("raw case count mismatch")
    if len(annotation) != len(raw):
        errors.append("annotation/raw count mismatch")
    raw_ids = [row.get("case_id") for row in raw]
    annotation_ids = [row.get("case_id") for row in annotation]
    if len(raw_ids) != len(set(raw_ids)):
        errors.append("duplicate raw case_id")
    if raw_ids != annotation_ids:
        errors.append("annotation case order/identity mismatch")

    for index, row in enumerate(annotation, start=1):
        if row.get("gold_label") is not None or row.get("adjudicated_label") is not None:
            errors.append(f"annotation line {index}: label populated")
        if row.get("reviewed") is not False or row.get("reviewer_notes") is not None:
            errors.append(f"annotation line {index}: review state populated")
        serialized_keys = set()

        def collect(value: object) -> None:
            if isinstance(value, dict):
                serialized_keys.update(str(key).lower() for key in value)
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        collect(row)
        leaked = FORBIDDEN_KEYS & serialized_keys
        if leaked:
            errors.append(f"annotation line {index}: forbidden prediction keys {sorted(leaked)}")

    evidence_count = sum(len(row.get("evidence_candidates") or []) for row in raw)
    if evidence_count != summary.get("evidence_candidate_count"):
        errors.append("evidence candidate count mismatch")
    rerank_backends = Counter((row.get("rerank_metrics") or {}).get("rerank_backend", "missing") for row in raw)
    rerank_reasons = Counter((row.get("rerank_metrics") or {}).get("rerank_failure_reason", "none") for row in raw)
    return {
        "status": "PASS" if not errors else "FAIL",
        "raw_case_count": len(raw),
        "annotation_case_count": len(annotation),
        "evidence_candidate_count": evidence_count,
        "judge_invocation_count": summary.get("judge_invocation_count"),
        "rerank_backend_distribution": dict(rerank_backends),
        "rerank_failure_reason_distribution": dict(rerank_reasons),
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_dir", type=Path)
    args = parser.parse_args()
    result = validate(args.capture_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
