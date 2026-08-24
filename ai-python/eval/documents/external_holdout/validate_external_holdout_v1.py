from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


LABELS = {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}
REVIEW_FIELDS = {"gold_label", "adjudicated_label", "reviewed", "reviewer_notes", "unresolved"}
FORBIDDEN = {"predicted_label", "v0_prediction", "v1_prediction", "v2_prediction", "v2_1_prediction", "judge", "judge_reason", "judge_confidence"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def keys(value: object, output: set[str]) -> None:
    if isinstance(value, dict):
        output.update(str(key).lower() for key in value)
        for child in value.values():
            keys(child, output)
    elif isinstance(value, list):
        for child in value:
            keys(child, output)


def validate(dataset_dir: Path, sample_dir: Path) -> dict:
    errors: list[str] = []
    dataset_path = dataset_dir / "external_holdout_v1.jsonl"
    metadata_path = dataset_dir / "external_holdout_v1.metadata.json"
    summary_path = dataset_dir / "adjudication_summary.json"
    freeze_path = dataset_dir / "freeze_manifest.json"
    dataset = rows(dataset_path)
    source = rows(sample_dir / "external_evaluation_sample_v1.jsonl")
    annotation = rows(sample_dir / "annotation_review_sample_v1.jsonl")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    sample_metadata = json.loads((sample_dir / "external_evaluation_sample_v1.metadata.json").read_text(encoding="utf-8"))
    sampling = json.loads((sample_dir / "sampling_manifest.json").read_text(encoding="utf-8"))
    universe = json.loads((sample_dir / "capture_universe_manifest.json").read_text(encoding="utf-8"))

    digest = sha256(dataset_path)
    if len(dataset) != len(source) or len(dataset) != len(annotation) or len(dataset) != 120:
        errors.append("dataset/sample/annotation count mismatch")
    if digest != metadata.get("dataset_sha256") or digest != freeze.get("dataset_sha256") or digest != summary.get("dataset_sha256"):
        errors.append("dataset SHA256 chain mismatch")
    if freeze.get("metadata_sha256") != sha256(metadata_path) or freeze.get("adjudication_summary_sha256") != sha256(summary_path):
        errors.append("freeze artifact hash mismatch")
    if freeze.get("sampling_manifest_sha256") != sha256(sample_dir / "sampling_manifest.json"):
        errors.append("sampling manifest hash mismatch")
    if freeze.get("capture_universe_manifest_sha256") != sha256(sample_dir / "capture_universe_manifest.json"):
        errors.append("universe manifest hash mismatch")
    if sample_metadata.get("sample_sha256") != sha256(sample_dir / "external_evaluation_sample_v1.jsonl") or sampling.get("sample_sha256") != sample_metadata.get("sample_sha256"):
        errors.append("source sample hash invalid")
    if universe.get("capture_universe_sha256") != metadata.get("capture_universe_sha256") or universe.get("capture_universe_sha256") != freeze.get("capture_universe_sha256"):
        errors.append("capture universe provenance mismatch")
    if any(obj.get("judge_invocation_count") != 0 for obj in (metadata, summary, freeze)):
        errors.append("Judge invocation count is not zero")

    labels = Counter()
    per_doc: dict[str, Counter[str]] = defaultdict(Counter)
    for index, (gold, sample, reviewed) in enumerate(zip(dataset, source, annotation), start=1):
        immutable = {key: value for key, value in gold.items() if key not in REVIEW_FIELDS}
        if immutable != sample:
            errors.append(f"line {index}: frozen immutable fields differ from source sample")
        if gold != reviewed:
            errors.append(f"line {index}: frozen row differs from adjudicated annotation")
        if gold.get("reviewed") is not True or gold.get("unresolved") is not False:
            errors.append(f"line {index}: invalid final review state")
        if gold.get("gold_label") not in LABELS or gold.get("adjudicated_label") != gold.get("gold_label"):
            errors.append(f"line {index}: invalid final label")
        all_keys: set[str] = set()
        keys(gold, all_keys)
        if FORBIDDEN & all_keys:
            errors.append(f"line {index}: Judge prediction leakage")
        labels[gold.get("gold_label")] += 1
        per_doc[gold["document_filename"]][gold["gold_label"]] += 1

    if dict(labels) != metadata.get("label_distribution") or dict(labels) != summary.get("label_distribution"):
        errors.append("label distribution mismatch")
    expected_per_doc = {name: dict(counts) for name, counts in sorted(per_doc.items())}
    if expected_per_doc != metadata.get("per_document_label_distribution") or expected_per_doc != summary.get("per_document_label_distribution"):
        errors.append("per-document label distribution mismatch")
    if metadata.get("freeze_status") != "EXTERNAL_HOLDOUT_V1_FROZEN" or freeze.get("status") != "EXTERNAL_HOLDOUT_V1_FROZEN":
        errors.append("freeze status invalid")

    return {
        "status": "PASS" if not errors else "FAIL",
        "dataset_sha256": digest,
        "total": len(dataset),
        "reviewed": sum(row.get("reviewed") is True for row in dataset),
        "draft": sum(row.get("reviewed") is not True for row in dataset),
        "unresolved": sum(row.get("unresolved") is True for row in dataset),
        "label_distribution": dict(labels),
        "per_document_label_distribution": expected_per_doc,
        "source_sample_integrity": not any("source sample" in error or "immutable" in error for error in errors),
        "judge_invocation_count": metadata.get("judge_invocation_count"),
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_dir", type=Path)
    parser.add_argument("sample_dir", type=Path)
    args = parser.parse_args()
    result = validate(args.dataset_dir, args.sample_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
