from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


FORBIDDEN_KEYS = {
    "predicted_label",
    "v0_prediction",
    "v1_prediction",
    "v2_prediction",
    "v2_1_prediction",
    "judge",
    "judge_reason",
    "judge_confidence",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collect_keys(value: object, output: set[str]) -> None:
    if isinstance(value, dict):
        output.update(str(key).lower() for key in value)
        for child in value.values():
            collect_keys(child, output)
    elif isinstance(value, list):
        for child in value:
            collect_keys(child, output)


def validate(sample_dir: Path) -> dict:
    errors: list[str] = []
    experiment = sample_dir.parent
    universe_path = experiment / "pipeline_capture" / "cases_raw.jsonl"
    sample_path = sample_dir / "external_evaluation_sample_v1.jsonl"
    annotation_path = sample_dir / "annotation_review_sample_v1.jsonl"
    metadata = json.loads((sample_dir / "external_evaluation_sample_v1.metadata.json").read_text(encoding="utf-8"))
    sampling = json.loads((sample_dir / "sampling_manifest.json").read_text(encoding="utf-8"))
    universe_manifest = json.loads((sample_dir / "capture_universe_manifest.json").read_text(encoding="utf-8"))
    universe = rows(universe_path)
    sample = rows(sample_path)
    annotation = rows(annotation_path)
    universe_by_id = {row["case_id"]: row for row in universe}

    if len(universe) != 289 or universe_manifest.get("case_count") != 289:
        errors.append("capture universe count must remain 289")
    if sha256(universe_path) != universe_manifest.get("capture_universe_sha256"):
        errors.append("capture universe SHA256 mismatch")
    if len(sample) != 120 or metadata.get("sample_size") != 120:
        errors.append("sample size must be 120")
    if sha256(sample_path) != metadata.get("sample_sha256") or sha256(sample_path) != sampling.get("sample_sha256"):
        errors.append("sample SHA256 mismatch")
    if len(annotation) != len(sample):
        errors.append("annotation/sample count mismatch")
    if sampling.get("status") != "COMPLETED_BEFORE_ANNOTATION" or sampling.get("judge_invocation_count") != 0:
        errors.append("sampling manifest status/Judge count invalid")
    if metadata.get("freeze_status") != "FROZEN_BEFORE_GOLD_ANNOTATION" or metadata.get("judge_invocation_count") != 0:
        errors.append("sample metadata freeze/Judge count invalid")

    expected_allocation = {
        "1746527472741_5024.pdf": 40,
        "8a69c65e95a7fec40195faa1360d1770.pdf": 25,
        "8a69c8e290831b250190964f57453e46.pdf": 55,
    }
    distribution = dict(Counter(row["document_filename"] for row in sample))
    if distribution != expected_allocation or metadata.get("per_document_sample_count") != expected_allocation:
        errors.append("per-document allocation mismatch")

    for index, (sample_row, annotation_row) in enumerate(zip(sample, annotation), start=1):
        case_id = sample_row.get("case_id")
        if case_id not in universe_by_id:
            errors.append(f"sample line {index}: case absent from universe")
            continue
        if sample_row != universe_by_id[case_id]:
            errors.append(f"sample line {index}: immutable capture content changed")
        review_fields = {"gold_label", "adjudicated_label", "reviewed", "reviewer_notes", "unresolved"}
        immutable_annotation = {key: value for key, value in annotation_row.items() if key not in review_fields}
        if immutable_annotation != sample_row:
            errors.append(f"annotation line {index}: immutable content mismatch")
        gold = annotation_row.get("gold_label")
        adjudicated = annotation_row.get("adjudicated_label")
        if gold is not None or adjudicated is not None or annotation_row.get("reviewed") is not False:
            if gold not in {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}:
                errors.append(f"annotation line {index}: invalid completed gold label")
            if adjudicated != gold or annotation_row.get("reviewed") is not True:
                errors.append(f"annotation line {index}: completed adjudication state mismatch")
        keys: set[str] = set()
        collect_keys(annotation_row, keys)
        leaked = FORBIDDEN_KEYS & keys
        if leaked:
            errors.append(f"annotation line {index}: forbidden Judge keys {sorted(leaked)}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "capture_universe_count": len(universe),
        "capture_universe_sha256": sha256(universe_path),
        "sample_size": len(sample),
        "sample_sha256": sha256(sample_path),
        "annotation_count": len(annotation),
        "completed_annotation_count": sum(row.get("reviewed") is True for row in annotation),
        "per_document_sample_count": distribution,
        "sampling_seed": sampling.get("sampling_seed"),
        "sampling_algorithm_fingerprint": sampling.get("sampling_algorithm_fingerprint"),
        "judge_invocation_count": metadata.get("judge_invocation_count"),
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_dir", type=Path)
    args = parser.parse_args()
    result = validate(args.sample_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
